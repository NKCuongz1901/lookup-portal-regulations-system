from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.modules.documents.enums import DocumentPublicationStatus
from app.modules.documents.models import Document, DocumentTag
from app.modules.documents.schemas import DocumentFilter


def document_query():
    return select(Document).options(
        selectinload(Document.document_type),
        selectinload(Document.issuing_unit),
        selectinload(Document.tags),
    )


def get_document(db: Session, document_id: int, *, for_update=False) -> Document | None:
    query = document_query().where(Document.id == document_id)
    if for_update:
        query = query.with_for_update()
    return db.scalar(query.execution_options(populate_existing=True))


def code_exists(db: Session, code: str, excluding_id: int | None = None) -> bool:
    query = select(Document.id).where(Document.code == code)
    if excluding_id is not None:
        query = query.where(Document.id != excluding_id)
    return db.scalar(query) is not None


def list_documents(db: Session, filters: DocumentFilter) -> tuple[list[Document], int]:
    conditions = []
    if filters.publication_status is None:
        conditions.append(Document.publication_status != DocumentPublicationStatus.ARCHIVED)
    else:
        conditions.append(Document.publication_status == filters.publication_status)
    if filters.search:
        conditions.append(or_(
            Document.code.icontains(filters.search, autoescape=True),
            Document.title.icontains(filters.search, autoescape=True),
        ))
    for name in ("document_type_id", "issuing_unit_id", "academic_year"):
        value = getattr(filters, name)
        if value is not None:
            conditions.append(getattr(Document, name) == value)
    if filters.tag_id is not None:
        # EXISTS avoids duplicating rows and inflating pagination totals.
        conditions.append(Document.document_tags.any(DocumentTag.tag_id == filters.tag_id))
    total = db.scalar(select(func.count()).select_from(Document).where(*conditions)) or 0
    query = (
        document_query().where(*conditions)
        .order_by(Document.created_at.desc(), Document.id.desc())
        .offset((filters.page - 1) * filters.itemsPerPage).limit(filters.itemsPerPage)
    )
    return list(db.scalars(query).all()), total


def replace_tags(db: Session, document: Document, tag_ids: list[int]) -> None:
    existing = {link.tag_id: link for link in document.document_tags}
    wanted = set(tag_ids)
    for tag_id, link in existing.items():
        if tag_id not in wanted:
            document.document_tags.remove(link)
    for tag_id in tag_ids:
        if tag_id not in existing:
            document.document_tags.append(DocumentTag(tag_id=tag_id))
    db.flush()
    # The convenience relationship is view-only; reload it after association writes.
    db.expire(document, ["tags"])
