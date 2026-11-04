"""Read stored segments for Step 4.3. No field persistence or task enqueue."""
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.documents.enums import DocumentParseStatus
from app.modules.documents.models import Document, DocumentSegment, DocumentVersion
from app.modules.extractions.field_extractor import extract_fields
from app.modules.extractions.field_types import FieldExtractionResult, FieldSegment
from app.modules.extractions.segment_service import VersionNotFoundError


class VersionNotParsedError(ValueError):
    pass


class NoSegmentsError(ValueError):
    pass


def extract_fields_for_version(db: Session, document_version_id: int) -> FieldExtractionResult:
    """Caller owns session/transaction and authorization for this version.

    A shared row lock prevents a concurrent parser from replacing the source
    while it is read. No commit/rollback here; caller closes the read transaction.
    Persistence/orchestration belongs to result_service, which saves snapshots.
    """
    if type(document_version_id) is not int or document_version_id <= 0:
        raise ValueError("document_version_id must be a positive integer")
    with db.no_autoflush:
        version = db.scalar(
            select(DocumentVersion)
            .join(Document, Document.id == DocumentVersion.document_id)
            .where(DocumentVersion.id == document_version_id, Document.deleted_at.is_(None))
            .with_for_update(read=True, of=DocumentVersion)
            .execution_options(populate_existing=True)
        )
        if version is None:
            raise VersionNotFoundError(f"document version {document_version_id} not found")
        if version.parse_status != DocumentParseStatus.PARSED:
            raise VersionNotParsedError(f"document version {document_version_id} is not parsed")
        rows = db.scalars(
            select(DocumentSegment)
            .where(DocumentSegment.document_version_id == document_version_id)
            .order_by(DocumentSegment.segment_index)
            .execution_options(populate_existing=True)
        ).all()
        if not rows:
            raise NoSegmentsError(f"document version {document_version_id} has no segments")
        inputs = [FieldSegment(row.segment_index, row.content, row.id, row.page_number, row.section_title) for row in rows]
        return extract_fields(inputs, document_version_id=document_version_id)
