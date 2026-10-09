from fastapi import HTTPException
from sqlalchemy import select, func
from sqlalchemy.orm import Session

from app.core.persistence import commit_or_rollback
from app.modules.document_metadata.models import DocumentType, IssuingUnit, Tag
from app.modules.documents import repository
from app.modules.documents.enums import DocumentPublicationStatus
from app.modules.documents.models import Document
from app.modules.documents.schemas import DocumentCreate, DocumentFilter, DocumentUpdate


def get_document(db: Session, document_id: int, *, for_update=False) -> Document:
    document = repository.get_document(db, document_id, for_update=for_update)
    if document is None:
        raise HTTPException(404, "Document not found")
    return document


def list_documents(db: Session, filters: DocumentFilter):
    return repository.list_documents(db, filters)


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


def archive_document(db: Session, document_id: int, actor_id: int) -> Document:
    with commit_or_rollback(db):
        document = get_document(db, document_id, for_update=True)
        if document.publication_status != DocumentPublicationStatus.ARCHIVED:
            document.publication_status = DocumentPublicationStatus.ARCHIVED
            document.updated_by = actor_id
    return get_document(db, document_id)
