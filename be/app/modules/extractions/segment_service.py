"""Persist structure-extraction rows into document_segments.

Claim a version for processing, then replace its segments and mark ``parsed``
in one transaction. On pipeline failure, mark ``failed`` in a separate short
transaction so prior successful segments stay intact when replace rolls back.

``ExtractionResult.full_text`` is not stored here — DocumentVersion has no
canonical-text column yet. Callers that need offsets later must keep
``full_text`` (or regenerate with the same ``parser_version``).
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.modules.documents.enums import DocumentParseStatus
from app.modules.documents.models import DocumentSegment, DocumentVersion
from app.modules.extractions.structure_extractor import ExtractionResult

CLAIMABLE_STATUSES = frozenset({
    DocumentParseStatus.PENDING,
    DocumentParseStatus.FAILED,
})
SEGMENT_FIELDS = (
    "segment_index",
    "page_number",
    "paragraph_index",
    "section_title",
    "content",
    "char_start",
    "char_end",
)


class VersionNotFoundError(LookupError):
    """No document_versions row for the given id."""


class VersionNotClaimableError(RuntimeError):
    """Version is already processing, already parsed, or otherwise not claimable."""


class VersionNotProcessingError(RuntimeError):
    """Replace was called while the version is not in processing state."""


def claim_version_for_parsing(
    db: Session,
    document_version_id: int,
    *,
    force: bool = False,
) -> DocumentVersion:
    """Lock the version and move it to ``processing``.

    Returns the locked version after commit. Raises if missing or not claimable.
    ``force=True`` reclaims ``parsed`` / ``processing`` (manual re-run).
    """
    version = db.scalar(
        select(DocumentVersion)
        .where(DocumentVersion.id == document_version_id)
        .with_for_update()
    )
    if version is None:
        raise VersionNotFoundError(f"document version {document_version_id} not found")

    status = version.parse_status
    if force:
        allowed = True
    elif status in CLAIMABLE_STATUSES:
        allowed = True
    else:
        allowed = False

    if not allowed:
        raise VersionNotClaimableError(
            f"document version {document_version_id} has parse_status={status.value}"
        )

    version.parse_status = DocumentParseStatus.PROCESSING
    db.commit()
    return version


def replace_segments_and_mark_parsed(
    db: Session,
    document_version_id: int,
    result: ExtractionResult,
) -> int:
    """Atomically replace segments and mark the version ``parsed``.

    Deletes existing rows for the version, inserts ``result.to_rows()``, sets
    ``parser_version`` / ``parsed_at``. On any error the transaction rolls back
    and previous segments remain unchanged.
    """
    try:
        version = db.scalar(
            select(DocumentVersion)
            .where(DocumentVersion.id == document_version_id)
            .with_for_update()
        )
        if version is None:
            raise VersionNotFoundError(f"document version {document_version_id} not found")
        if version.parse_status != DocumentParseStatus.PROCESSING:
            raise VersionNotProcessingError(
                f"document version {document_version_id} "
                f"has parse_status={version.parse_status.value}, expected processing"
            )

        db.execute(
            delete(DocumentSegment).where(
                DocumentSegment.document_version_id == document_version_id
            )
        )
        db.flush()

        rows = result.to_rows()
        for row in rows:
            payload = {field: row[field] for field in SEGMENT_FIELDS}
            if not str(payload["content"] or "").strip():
                raise ValueError(
                    f"segment_index={payload['segment_index']} has empty content"
                )
            db.add(
                DocumentSegment(
                    document_version_id=document_version_id,
                    **payload,
                )
            )

        version.parse_status = DocumentParseStatus.PARSED
        version.parser_version = result.parser_version[:50]
        version.parsed_at = datetime.now(timezone.utc)
        db.commit()
        return len(rows)
    except Exception:
        db.rollback()
        raise


def mark_parse_failed(db: Session, document_version_id: int) -> None:
    """Set ``failed`` after a pipeline error (own transaction)."""
    try:
        version = db.scalar(
            select(DocumentVersion)
            .where(DocumentVersion.id == document_version_id)
            .with_for_update()
        )
        if version is None:
            raise VersionNotFoundError(f"document version {document_version_id} not found")
        # Only fail an in-flight or still-pending claim; leave parsed alone.
        if version.parse_status in {
            DocumentParseStatus.PROCESSING,
            DocumentParseStatus.PENDING,
        }:
            version.parse_status = DocumentParseStatus.FAILED
            db.commit()
        else:
            db.rollback()
    except Exception:
        db.rollback()
        raise
