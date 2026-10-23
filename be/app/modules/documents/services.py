import hashlib
import io
import zipfile
from pathlib import Path

from botocore.exceptions import BotoCoreError, ClientError
from fastapi import HTTPException, UploadFile
from fastapi.concurrency import run_in_threadpool
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session, selectinload

from app.core.config import settings
from app.core.persistence import commit_or_rollback
from app.core.storage import build_storage_key, delete_object, generate_download_url, upload_bytes
from app.modules.document_metadata.models import DocumentType, IssuingUnit, Tag
from app.modules.documents import repository
from app.modules.documents.enums import DocumentParseStatus, DocumentPublicationStatus
from app.modules.documents.models import Document, DocumentVersion
from app.modules.documents.schemas import (
    DocumentCreate, DocumentDownloadResponse, DocumentFilter, DocumentUpdate, DocumentVersionQuery,
)
from app.modules.files.models import StoredFile

ALLOWED_EXTENSIONS = {".pdf", ".docx"}
MIME_BY_EXTENSION = {
    ".pdf": "application/pdf",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}
MAX_FILE_SIZE = 20 * 1024 * 1024  # 20 MB


def get_document(db: Session, document_id: int, *, for_update=False) -> Document:
    document = repository.get_document(db, document_id, for_update=for_update)
    if document is None:
        raise HTTPException(404, "Document not found")
    return document


def list_documents(db: Session, filters: DocumentFilter):
    return repository.list_documents(db, filters)


def list_versions(db: Session, document_id: int, filters: DocumentVersionQuery):
    get_document(db, document_id)
    return repository.list_versions(db, document_id, filters)


def get_download_url(
    db: Session, document_id: int, version_id: int | None = None,
) -> DocumentDownloadResponse:
    get_document(db, document_id)
    version = repository.get_download_version(db, document_id, version_id)
    if version is None:
        message = "Current document version not found" if version_id is None else "Document version not found"
        raise HTTPException(404, message)
    stored_file = version.file
    if stored_file.storage_provider != "r2":
        raise HTTPException(409, "File is not stored in R2")
    expires_in = settings.R2_DOWNLOAD_URL_EXPIRE_SECONDS
    try:
        url = generate_download_url(
            storage_key=stored_file.storage_key,
            original_name=stored_file.original_name,
            mime_type=stored_file.mime_type,
            expires_in=expires_in,
        )
    except ClientError as exc:
        code = exc.response.get("Error", {}).get("Code")
        if code in {"404", "NoSuchKey", "NotFound"}:
            raise HTTPException(404, "File not found in storage") from exc
        raise HTTPException(502, "Failed to access file storage") from exc
    except BotoCoreError as exc:
        raise HTTPException(502, "Failed to access file storage") from exc
    return DocumentDownloadResponse(
        document_id=document_id,
        version_id=version.id,
        file_name=stored_file.original_name,
        mime_type=stored_file.mime_type,
        size_bytes=stored_file.size_bytes,
        url=url,
        expires_in=expires_in,
    )


def validate_references(db: Session, values: dict, document: Document | None = None):
    for field, model in (("document_type_id", DocumentType), ("issuing_unit_id", IssuingUnit)):
        record_id = values.get(field)
        if record_id is None:
            continue
        record = db.scalar(
            select(model).where(model.id == record_id).with_for_update(read=True)
            .execution_options(populate_existing=True)
        )
        if record is None:
            raise HTTPException(422, f"{field} does not exist")
        unchanged = document is not None and getattr(document, field) == record_id
        if not record.is_active and not unchanged:
            raise HTTPException(422, f"{field} is inactive")
    if values.get("tag_ids"):
        found = set(db.scalars(
            select(Tag.id).where(Tag.id.in_(values["tag_ids"])).with_for_update(read=True)
        ))
        if found != set(values["tag_ids"]):
            raise HTTPException(422, "One or more tags do not exist")


def create_document(db: Session, payload: DocumentCreate, actor_id: int) -> Document:
    with commit_or_rollback(db):
        values = payload.model_dump()
        validate_references(db, values)
        if repository.code_exists(db, values["code"]):
            raise HTTPException(409, "Document code already exists")
        tag_ids = values.pop("tag_ids")
        document = Document(
            **values, publication_status=DocumentPublicationStatus.DRAFT, created_by=actor_id,
        )
        db.add(document)
        db.flush()
        repository.replace_tags(db, document, tag_ids)
    return get_document(db, document.id)


def update_document(
    db: Session, document_id: int, payload: DocumentUpdate, actor_id: int,
) -> Document:
    with commit_or_rollback(db):
        # Serialize edits and archive operations for the same document.
        document = get_document(db, document_id, for_update=True)
        values = payload.model_dump(exclude_unset=True)
        validate_references(db, values, document)
        if "code" in values and repository.code_exists(db, values["code"], document_id):
            raise HTTPException(409, "Document code already exists")
        start = values.get("effective_from", document.effective_from)
        end = values.get("effective_until", document.effective_until)
        if start is not None and end is not None and end < start:
            raise HTTPException(422, "effective_until must be on or after effective_from")
        tag_ids = values.pop("tag_ids", None)
        for name, value in values.items():
            setattr(document, name, value)
        if values or tag_ids is not None:
            document.updated_by = actor_id
            document.updated_at = func.now()
        if tag_ids is not None:
            repository.replace_tags(db, document, tag_ids)
    return get_document(db, document_id)


def delete_document(db: Session, document_id: int, actor_id: int) -> None:
    with commit_or_rollback(db):
        # Use the same row lock as edits, archive, and version creation.
        document = get_document(db, document_id, for_update=True)
        document.deleted_at = func.now()
        document.deleted_by = actor_id
        document.updated_by = actor_id
        document.updated_at = func.now()


def archive_document(db: Session, document_id: int, actor_id: int) -> Document:
    with commit_or_rollback(db):
        document = get_document(db, document_id, for_update=True)
        if document.publication_status != DocumentPublicationStatus.ARCHIVED:
            document.publication_status = DocumentPublicationStatus.ARCHIVED
            document.updated_by = actor_id
    return get_document(db, document_id)


def _validate_file_content(extension: str, content: bytes) -> None:
    if extension == ".pdf":
        if not content.startswith(b"%PDF-"):
            raise HTTPException(422, "File content is not a valid PDF")
    elif extension == ".docx":
        # DOCX is a ZIP package that must contain the main document part.
        try:
            with zipfile.ZipFile(io.BytesIO(content)) as archive:
                if "word/document.xml" not in archive.namelist():
                    raise HTTPException(422, "File content is not a valid DOCX")
        except zipfile.BadZipFile:
            raise HTTPException(422, "File content is not a valid DOCX")


def _get_version_with_file(db: Session, version_id: int) -> DocumentVersion:
    version = db.scalar(
        select(DocumentVersion)
        .options(selectinload(DocumentVersion.file))
        .where(DocumentVersion.id == version_id)
        .execution_options(populate_existing=True)
    )
    if version is None:
        raise HTTPException(404, "Document version not found")
    return version


async def upload_version(
    db: Session, document_id: int, file: UploadFile, actor_id: int,
) -> DocumentVersion:
    # 404 before reading/uploading anything.
    get_document(db, document_id)

    original_name = Path(file.filename or "").name
    if not original_name or len(original_name) > 500:
        raise HTTPException(422, "Invalid file name")
    extension = Path(original_name).suffix.lower()
    if extension not in ALLOWED_EXTENSIONS:
        raise HTTPException(422, "Only PDF and DOCX files are allowed")
    mime_type = MIME_BY_EXTENSION[extension]

    # Read with a hard size cap while hashing; never trust the client MIME/size.
    hasher = hashlib.sha256()
    chunks: list[bytes] = []
    size = 0
    while chunk := await file.read(1024 * 1024):
        size += len(chunk)
        if size > MAX_FILE_SIZE:
            raise HTTPException(422, "File exceeds the 20MB limit")
        hasher.update(chunk)
        chunks.append(chunk)
    content = b"".join(chunks)
    if not content:
        raise HTTPException(422, "File is empty")
    _validate_file_content(extension, content)
    checksum = hasher.hexdigest()

    storage_key = build_storage_key(document_id, original_name)
    try:
        await run_in_threadpool(
            upload_bytes,
            storage_key=storage_key,
            content=content,
            content_type=mime_type,
        )
    except Exception as exc:
        raise HTTPException(502, "Failed to upload file to storage") from exc

    try:
        with commit_or_rollback(db):
            # Lock the document row to serialize version numbers per document.
            get_document(db, document_id, for_update=True)
            db.execute(
                update(DocumentVersion)
                .where(
                    DocumentVersion.document_id == document_id,
                    DocumentVersion.is_current.is_(True),
                )
                .values(is_current=False)
            )
            next_version = (
                db.scalar(
                    select(func.coalesce(func.max(DocumentVersion.version_number), 0))
                    .where(DocumentVersion.document_id == document_id)
                )
                or 0
            ) + 1

            stored_file = StoredFile(
                storage_provider="r2",
                storage_key=storage_key,
                original_name=original_name,
                mime_type=mime_type,
                size_bytes=len(content),
                checksum_sha256=checksum,
                uploaded_by=actor_id,
            )
            db.add(stored_file)
            db.flush()

            version = DocumentVersion(
                document_id=document_id,
                version_number=next_version,
                file_id=stored_file.id,
                is_current=True,
                parse_status=DocumentParseStatus.PENDING,
                created_by=actor_id,
            )
            db.add(version)
            db.flush()
            version_id = version.id
    except Exception:
        # DB write failed: remove the orphaned object from R2.
        try:
            await run_in_threadpool(delete_object, storage_key)
        except Exception:
            pass
        raise

    return _get_version_with_file(db, version_id)
