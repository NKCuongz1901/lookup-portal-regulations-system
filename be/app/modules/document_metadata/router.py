from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.responses import ApiResponse, paginate, success
from app.core.schemas import PaginationQuery
from app.modules.auth.dependencies import require_roles
from app.modules.document_metadata import services
from app.modules.document_metadata.models import DocumentType, IssuingUnit, Tag
from app.modules.document_metadata.schemas import (
    DocumentTypeCreate,
    DocumentTypeResponse,
    DocumentTypeUpdate,
    IssuingUnitCreate,
    IssuingUnitResponse,
    IssuingUnitUpdate,
    LookupFilter,
    TagCreate,
    TagResponse,
    TagUpdate,
)
from app.modules.users.models import User


router = APIRouter(tags=["document metadata"])
DB = Annotated[Session, Depends(get_db)]
Editor = Annotated[User, Depends(require_roles("ADMIN", "STAFF"))]
Admin = Annotated[User, Depends(require_roles("ADMIN"))]
MetadataId = Annotated[int, Path(gt=0, le=9223372036854775807)]


def list_response(db, model, filters):
    records, total = services.list_metadata(db, model, filters)
    return success(data=records, meta=paginate(filters.page, filters.itemsPerPage, total))


@router.get("/document-types", response_model=ApiResponse[list[DocumentTypeResponse]])
def list_document_types(filters: Annotated[LookupFilter, Query()], db: DB, actor: Editor):
    return list_response(db, DocumentType, filters)


@router.get("/document-types/{record_id}", response_model=ApiResponse[DocumentTypeResponse])
def get_document_type(record_id: MetadataId, db: DB, actor: Editor):
    return success(data=services.get_metadata(db, DocumentType, record_id))


@router.post("/document-types", response_model=ApiResponse[DocumentTypeResponse], status_code=201)
def create_document_type(payload: DocumentTypeCreate, db: DB, actor: Admin):
    return success(
        data=services.create_metadata(db, DocumentType, payload),
        message="Document type created", status_code=201,
    )


@router.patch("/document-types/{record_id}", response_model=ApiResponse[DocumentTypeResponse])
def update_document_type(record_id: MetadataId, payload: DocumentTypeUpdate, db: DB, actor: Admin):
    return success(
        data=services.update_metadata(db, DocumentType, record_id, payload),
        message="Document type updated",
    )


@router.get("/issuing-units", response_model=ApiResponse[list[IssuingUnitResponse]])
def list_issuing_units(filters: Annotated[LookupFilter, Query()], db: DB, actor: Editor):
    return list_response(db, IssuingUnit, filters)


@router.get("/issuing-units/{record_id}", response_model=ApiResponse[IssuingUnitResponse])
def get_issuing_unit(record_id: MetadataId, db: DB, actor: Editor):
    return success(data=services.get_metadata(db, IssuingUnit, record_id))


@router.post("/issuing-units", response_model=ApiResponse[IssuingUnitResponse], status_code=201)
def create_issuing_unit(payload: IssuingUnitCreate, db: DB, actor: Admin):
    return success(
        data=services.create_metadata(db, IssuingUnit, payload),
        message="Issuing unit created", status_code=201,
    )


@router.patch("/issuing-units/{record_id}", response_model=ApiResponse[IssuingUnitResponse])
def update_issuing_unit(record_id: MetadataId, payload: IssuingUnitUpdate, db: DB, actor: Admin):
    return success(
        data=services.update_metadata(db, IssuingUnit, record_id, payload),
        message="Issuing unit updated",
    )


@router.get("/tags", response_model=ApiResponse[list[TagResponse]])
def list_tags(filters: Annotated[PaginationQuery, Query()], db: DB, actor: Editor):
    return list_response(db, Tag, filters)


@router.get("/tags/{record_id}", response_model=ApiResponse[TagResponse])
def get_tag(record_id: MetadataId, db: DB, actor: Editor):
    return success(data=services.get_metadata(db, Tag, record_id))


@router.post("/tags", response_model=ApiResponse[TagResponse], status_code=201)
def create_tag(payload: TagCreate, db: DB, actor: Editor):
    return success(
        data=services.create_metadata(db, Tag, payload), message="Tag created", status_code=201,
    )


@router.patch("/tags/{record_id}", response_model=ApiResponse[TagResponse])
def update_tag(record_id: MetadataId, payload: TagUpdate, db: DB, actor: Editor):
    return success(
        data=services.update_metadata(db, Tag, record_id, payload), message="Tag updated",
    )
