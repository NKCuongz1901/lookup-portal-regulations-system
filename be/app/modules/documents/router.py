from typing import Annotated

from fastapi import APIRouter, Depends, File, Path, Query, Response, UploadFile
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.responses import ApiResponse, paginate, success
from app.modules.auth.dependencies import require_roles
from app.modules.documents import services
from app.modules.documents.schemas import (
    DocumentCreate,
    DocumentDetail,
    DocumentDownloadQuery,
    DocumentDownloadResponse,
    DocumentFilter,
    DocumentListItem,
    DocumentUpdate,
    DocumentVersionQuery,
    DocumentVersionResponse,
)
from app.modules.users.models import User


router = APIRouter(prefix="/documents", tags=["documents"])
DB = Annotated[Session, Depends(get_db)]
Editor = Annotated[User, Depends(require_roles("ADMIN", "STAFF"))]
DocumentId = Annotated[int, Path(gt=0, le=9223372036854775807)]


@router.get("", response_model=ApiResponse[list[DocumentListItem]])
def list_documents(filters: Annotated[DocumentFilter, Query()], db: DB, actor: Editor):
    documents, total = services.list_documents(db, filters)
    return success(
        data=[DocumentListItem.model_validate(document) for document in documents],
        meta=paginate(filters.page, filters.itemsPerPage, total),
    )


@router.get("/{document_id}", response_model=ApiResponse[DocumentDetail])
def get_document(document_id: DocumentId, db: DB, actor: Editor):
    return success(data=DocumentDetail.model_validate(services.get_document(db, document_id)))


@router.post("", response_model=ApiResponse[DocumentDetail], status_code=201)
def create_document(payload: DocumentCreate, db: DB, actor: Editor):
    document = services.create_document(db, payload, actor.id)
    return success(
        data=DocumentDetail.model_validate(document), message="Document created", status_code=201,
    )


@router.patch("/{document_id}", response_model=ApiResponse[DocumentDetail])
def update_document(document_id: DocumentId, payload: DocumentUpdate, db: DB, actor: Editor):
    document = services.update_document(db, document_id, payload, actor.id)
    return success(data=DocumentDetail.model_validate(document), message="Document updated")


@router.patch("/{document_id}/archive", response_model=ApiResponse[DocumentDetail])
def archive_document(document_id: DocumentId, db: DB, actor: Editor):
    document = services.archive_document(db, document_id, actor.id)
    return success(data=DocumentDetail.model_validate(document), message="Document archived")


@router.get("/{document_id}/versions", response_model=ApiResponse[list[DocumentVersionResponse]])
def list_document_versions(
    document_id: DocumentId, filters: Annotated[DocumentVersionQuery, Query()], db: DB, actor: Editor,
):
    versions, total = services.list_versions(db, document_id, filters)
    return success(
        data=[DocumentVersionResponse.model_validate(version) for version in versions],
        meta=paginate(filters.page, filters.itemsPerPage, total),
    )


@router.get(
    "/{document_id}/download-url",
    response_model=ApiResponse[DocumentDownloadResponse],
    summary="Get a temporary R2 download URL",
    description="ADMIN/STAFF only. Omit version_id to download the current version. Returns JSON, not file bytes.",
)
def get_document_download_url(
    document_id: DocumentId,
    filters: Annotated[DocumentDownloadQuery, Query()],
    response: Response,
    db: DB,
    actor: Editor,
):
    # A sync endpoint runs blocking SQLAlchemy/boto3 work in FastAPI's thread pool.
    data = services.get_download_url(db, document_id, filters.version_id)
    response.headers["Cache-Control"] = "no-store"
    return success(data=data)


@router.post(
    "/{document_id}/versions",
    response_model=ApiResponse[DocumentVersionResponse],
    status_code=201,
)
async def upload_document_version(
    document_id: DocumentId,
    db: DB,
    actor: Editor,
    file: Annotated[UploadFile, File(description="PDF or DOCX file, max 20MB")],
):
    version = await services.upload_version(db, document_id, file, actor.id)
    return success(
        data=DocumentVersionResponse.model_validate(version),
        message="Document version uploaded",
        status_code=201,
    )

