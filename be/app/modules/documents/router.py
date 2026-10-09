from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.responses import ApiResponse, paginate, success
from app.modules.auth.dependencies import require_roles
from app.modules.documents import services
from app.modules.documents.schemas import (
    DocumentCreate,
    DocumentDetail,
    DocumentFilter,
    DocumentListItem,
    DocumentUpdate,
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
