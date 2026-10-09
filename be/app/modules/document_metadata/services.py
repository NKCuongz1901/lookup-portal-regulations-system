from typing import TypeVar

from fastapi import HTTPException
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.persistence import commit_or_rollback
from app.core.schemas import PaginationQuery, PartialUpdate, RequestSchema
from app.modules.document_metadata.models import DocumentType, IssuingUnit, Tag
from app.modules.document_metadata.schemas import LookupFilter


MetadataModel = TypeVar("MetadataModel", DocumentType, IssuingUnit, Tag)


def list_metadata(
    db: Session, model: type[MetadataModel], filters: PaginationQuery,
) -> tuple[list[MetadataModel], int]:
    conditions = []
    if filters.search:
        key_column = model.slug if model is Tag else model.code
        conditions.append(or_(
            model.name.icontains(filters.search, autoescape=True),
            key_column.icontains(filters.search, autoescape=True),
        ))
    if isinstance(filters, LookupFilter) and filters.is_active is not None:
        conditions.append(model.is_active == filters.is_active)
    total = db.scalar(select(func.count()).select_from(model).where(*conditions)) or 0
    records = db.scalars(
        select(model).where(*conditions).order_by(model.name, model.id)
        .offset((filters.page - 1) * filters.itemsPerPage).limit(filters.itemsPerPage)
    ).all()
    return list(records), total


def get_metadata(db: Session, model: type[MetadataModel], record_id: int) -> MetadataModel:
    record = db.get(model, record_id)
    if record is None:
        raise HTTPException(404, "Metadata record not found")
    return record


def ensure_unique(db: Session, model: type[MetadataModel], values: dict, record_id=None):
    key = "slug" if model is Tag else "code"
    if key not in values:
        return
    query = select(model.id).where(getattr(model, key) == values[key])
    if record_id is not None:
        query = query.where(model.id != record_id)
    if db.scalar(query) is not None:
        raise HTTPException(409, f"{key} already exists")


def create_metadata(
    db: Session, model: type[MetadataModel], payload: RequestSchema,
) -> MetadataModel:
    with commit_or_rollback(db):
        values = payload.model_dump()
        ensure_unique(db, model, values)
        record = model(**values)
        db.add(record)
    db.refresh(record)
    return record


def update_metadata(
    db: Session, model: type[MetadataModel], record_id: int, payload: PartialUpdate,
) -> MetadataModel:
    with commit_or_rollback(db):
        record = get_metadata(db, model, record_id)
        values = payload.model_dump(exclude_unset=True)
        ensure_unique(db, model, values, record_id)
        for name, value in values.items():
            setattr(record, name, value)
    db.refresh(record)
    return record
