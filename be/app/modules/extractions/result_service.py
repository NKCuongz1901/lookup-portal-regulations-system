"""Run lifecycle, atomic result persistence and historical evidence snapshots.

These services own their commits/rollbacks. Lock order is version, then run.
Worker leases have fencing tokens so an old attempt cannot overwrite a retry.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session, selectinload

from app.modules.documents.enums import DocumentParseStatus
from app.modules.documents.models import Document, DocumentSegment, DocumentVersion
from app.modules.extractions.field_extractor import extract_fields
from app.modules.extractions.field_types import FieldExtractionResult, FieldSegment, RULE_VERSION
from app.modules.extractions.models import ExtractedField, ExtractionRun, FieldEvidence
from app.modules.extractions.segment_service import VersionNotFoundError


LEASE_SECONDS = 600


class RunNotFoundError(LookupError):
    pass


class RunConflictError(ValueError):
    pass


class SourceChangedError(RunConflictError):
    pass


class RuleVersionChangedError(RunConflictError):
    pass


def _now() -> datetime:
    return datetime.now(timezone.utc)


def get_version(db: Session, version_id: int, *, lock: bool = False) -> DocumentVersion:
    statement = (select(DocumentVersion).join(Document, Document.id == DocumentVersion.document_id)
                 .where(DocumentVersion.id == version_id, Document.deleted_at.is_(None))
                 .execution_options(populate_existing=True))
    if lock:
        statement = statement.with_for_update(of=DocumentVersion)
    version = db.scalar(statement)
    if version is None:
        raise VersionNotFoundError("Document version not found")
    return version


def get_run(db: Session, run_id: int) -> ExtractionRun:
    run = db.scalar(select(ExtractionRun).join(DocumentVersion).join(Document)
                    .where(ExtractionRun.id == run_id, Document.deleted_at.is_(None))
                    .execution_options(populate_existing=True))
    if run is None:
        raise RunNotFoundError("Extraction run not found")
    return run


def _lock_run(db: Session, run_id: int) -> ExtractionRun:
    run = db.scalar(select(ExtractionRun).where(ExtractionRun.id == run_id)
                    .with_for_update().execution_options(populate_existing=True))
    if run is None:
        raise RunNotFoundError("Extraction run not found")
    return run


def _source(db: Session, version_id: int) -> list[DocumentSegment]:
    return list(db.scalars(select(DocumentSegment)
                          .where(DocumentSegment.document_version_id == version_id)
                          .order_by(DocumentSegment.segment_index)
                          .execution_options(populate_existing=True)).all())


def source_fingerprint(rows: list[DocumentSegment]) -> str:
    payload = [[row.id, row.segment_index, row.page_number, row.section_title, row.content] for row in rows]
    return hashlib.sha256(json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")).hexdigest()


def _automatic_key(version: DocumentVersion, fingerprint: str) -> str:
    timestamp = version.parsed_at.astimezone(timezone.utc).isoformat() if version.parsed_at else None
    generation = [fingerprint, version.parser_version, timestamp]
    digest = hashlib.sha256(json.dumps(generation).encode("utf-8")).hexdigest()
    return f"auto:{RULE_VERSION}:{digest}"


def _check_source(run: ExtractionRun, version: DocumentVersion, rows: list[DocumentSegment]) -> None:
    if run.rule_version != RULE_VERSION:
        raise RuleVersionChangedError("Rules have changed; create a new extraction run")
    if (version.parse_status != DocumentParseStatus.PARSED or version.parsed_at != run.source_parsed_at
            or version.parser_version != run.parser_version or source_fingerprint(rows) != run.source_fingerprint):
        raise SourceChangedError("Source segments have changed; create a new extraction run")


def ensure_automatic_run(db: Session, version: DocumentVersion) -> ExtractionRun:
    """Caller holds the version lock; add a pending run to the parse transaction."""
    rows = _source(db, version.id)
    fingerprint = source_fingerprint(rows)
    key = _automatic_key(version, fingerprint)
    existing = db.scalar(select(ExtractionRun).where(
        ExtractionRun.document_version_id == version.id, ExtractionRun.request_key == key))
    if existing:
        return existing
    run = ExtractionRun(document_version_id=version.id, request_key=key, rule_version=RULE_VERSION,
                        parser_version=version.parser_version, source_parsed_at=version.parsed_at,
                        source_fingerprint=fingerprint)
    db.add(run)
    return run


def create_run(db: Session, version_id: int, *, request_key: str | None = None,
               requested_by: int | None = None) -> ExtractionRun:
    """None means an automatic run for this source/rules generation.

    API callers pass manual:<UUID>. Reusing a key returns the same run, while a
    new key creates history. Version locking serializes concurrent requests.
    """
    if request_key is not None and not 1 <= len(request_key) <= 200:
        raise ValueError("Invalid request key")
    try:
        version = get_version(db, version_id, lock=True)
        if request_key is not None:
            existing = db.scalar(select(ExtractionRun).where(
                ExtractionRun.document_version_id == version_id, ExtractionRun.request_key == request_key))
            if existing:
                db.commit()
                return existing
        if version.parse_status != DocumentParseStatus.PARSED:
            raise RunConflictError("Document version must be parsed before extracting fields")
        rows = _source(db, version_id)
        fingerprint = source_fingerprint(rows)
        key = request_key or _automatic_key(version, fingerprint)
        existing = db.scalar(select(ExtractionRun).where(
            ExtractionRun.document_version_id == version_id, ExtractionRun.request_key == key))
        if existing:
            db.commit()
            return existing
        run = ExtractionRun(document_version_id=version_id, request_key=key, rule_version=RULE_VERSION,
                            parser_version=version.parser_version, source_parsed_at=version.parsed_at,
                            source_fingerprint=fingerprint, requested_by=requested_by)
        db.add(run)
        db.commit()
        return run
    except Exception:
        db.rollback()
        raise


def claim_run(db: Session, run_id: int) -> str | None:
    try:
        visible = get_run(db, run_id)
        get_version(db, visible.document_version_id, lock=True)
        run = _lock_run(db, run_id)
        now = _now()
        if run.status == "completed" or (run.status == "processing" and run.lease_expires_at and run.lease_expires_at > now):
            db.commit()
            return None
        token = str(uuid4())
        run.status = "processing"
        run.execution_token = token
        run.lease_expires_at = now + timedelta(seconds=LEASE_SECONDS)
        run.started_at = now
        run.finished_at = None
        run.error_code = run.error_message = None
        run.attempt_count += 1
        db.commit()
        return token
    except Exception:
        db.rollback()
        raise


def _persist_fields(db: Session, run: ExtractionRun, result: FieldExtractionResult,
                    sources: list[DocumentSegment]) -> None:
    """Called with source/run locks held; final commit belongs to execute_run."""
    if result.document_version_id != run.document_version_id or result.rule_version != run.rule_version:
        raise ValueError("Extraction result does not match run")
    if result.segment_count != len(sources):
        raise ValueError("Extraction result does not match source count")
    by_id = {row.id: row for row in sources}
    db.execute(delete(ExtractedField).where(ExtractedField.extraction_run_id == run.id))
    for candidate in result.candidates:
        if candidate.rule_version != run.rule_version or not candidate.evidences or candidate.review_status != "pending":
            raise ValueError("Invalid extraction candidate")
        item = ExtractedField(extraction_run_id=run.id, field_key=candidate.field_key,
                              item_index=candidate.item_index, raw_value=candidate.raw_value,
                              normalized_value=candidate.normalized_value, rule_id=candidate.rule_id,
                              rule_version=candidate.rule_version, review_status="pending")
        value_quotes = []
        for evidence in candidate.evidences:
            row = by_id.get(evidence.document_segment_id)
            if (row is None or row.segment_index != evidence.segment_index or row.page_number != evidence.page_number
                    or row.section_title != evidence.section_title
                    or not 0 <= evidence.start_offset < evidence.end_offset <= len(row.content)
                    or row.content[evidence.start_offset:evidence.end_offset] != evidence.quote):
                raise ValueError("Evidence does not match persisted source")
            if evidence.role == "value" and evidence.occurrence_index == 0:
                value_quotes.append(evidence.quote)
            item.evidences.append(FieldEvidence(
                document_segment_id=row.id, source_segment_id=row.id, segment_index=row.segment_index,
                page_number=row.page_number, section_title=row.section_title, segment_content_snapshot=row.content,
                quote=evidence.quote, start_offset=evidence.start_offset, end_offset=evidence.end_offset,
                role=evidence.role, occurrence_index=evidence.occurrence_index,
            ))
        if "\n".join(value_quotes) != candidate.raw_value:
            raise ValueError("Candidate value does not match evidence")
        db.add(item)
    db.flush()  # Constraint failures roll back every field and evidence in this run.
    run.field_count = len(result.candidates)
    run.warnings = list(result.warnings)
    run.status = "completed"
    run.finished_at = _now()
    run.execution_token = run.lease_expires_at = None
    run.error_code = run.error_message = None


def mark_run_failed(db: Session, run_id: int, token: str, error: Exception) -> None:
    try:
        run = _lock_run(db, run_id)
        if run.status == "processing" and run.execution_token == token:
            if isinstance(error, SourceChangedError):
                code, message = "source_changed", "Source changed; create a new extraction run."
            elif isinstance(error, RuleVersionChangedError):
                code, message = "rule_version_changed", "Rules changed; create a new extraction run."
            else:
                code, message = "extraction_failed", "Field extraction failed. Retry this run or check worker logs."
            run.status, run.error_code, run.error_message = "failed", code, message
            run.finished_at = _now()
            run.execution_token = run.lease_expires_at = None
        db.commit()
    except Exception:
        db.rollback()
        raise


def execute_run(db: Session, run_id: int) -> ExtractionRun:
    token = claim_run(db, run_id)
    if token is None:
        return get_run(db, run_id)
    try:
        visible = get_run(db, run_id)
        version = get_version(db, visible.document_version_id, lock=True)
        run = _lock_run(db, run_id)
        if run.status != "processing" or run.execution_token != token:
            db.commit()
            return run  # This attempt was superseded; never write over it.
        sources = _source(db, version.id)
        _check_source(run, version, sources)
        if not sources:
            raise RunConflictError("No segments available")
        result = extract_fields([FieldSegment(row.segment_index, row.content, row.id, row.page_number, row.section_title)
                                 for row in sources], document_version_id=version.id)
        _persist_fields(db, run, result, sources)
        db.commit()
        return run
    except Exception as error:
        db.rollback()
        mark_run_failed(db, run_id, token, error)
        raise


def prepare_retry(db: Session, run_id: int) -> ExtractionRun:
    try:
        visible = get_run(db, run_id)
        version = get_version(db, visible.document_version_id, lock=True)
        run = _lock_run(db, run_id)
        if run.status == "completed":
            db.commit()
            return run
        if run.status == "processing" and run.lease_expires_at and run.lease_expires_at > _now():
            raise RunConflictError("Extraction run is already processing")
        _check_source(run, version, _source(db, version.id))
        run.status = "pending"
        run.execution_token = run.lease_expires_at = run.finished_at = None
        run.error_code = run.error_message = None
        db.commit()
        return run
    except Exception:
        db.rollback()
        raise


def record_queue_failure(db: Session, run_id: int) -> None:
    try:
        run = _lock_run(db, run_id)
        if run.status == "pending":
            run.error_code = "queue_unavailable"
            run.error_message = "Run is saved but could not be queued. Retry this run."
        db.commit()
    except Exception:
        db.rollback()
        raise


def list_runs(db: Session, version_id: int, page: int, size: int):
    get_version(db, version_id)
    condition = ExtractionRun.document_version_id == version_id
    total = db.scalar(select(func.count()).select_from(ExtractionRun).where(condition)) or 0
    rows = db.scalars(select(ExtractionRun).where(condition)
                     .order_by(ExtractionRun.created_at.desc(), ExtractionRun.id.desc())
                     .offset((page - 1) * size).limit(size)).all()
    return rows, total


def list_fields(db: Session, run_id: int, page: int, size: int, field_key: str | None = None,
                review_status: str | None = None):
    get_run(db, run_id)
    conditions = [ExtractedField.extraction_run_id == run_id]
    if field_key:
        conditions.append(ExtractedField.field_key == field_key)
    if review_status:
        conditions.append(ExtractedField.review_status == review_status)
    total = db.scalar(select(func.count()).select_from(ExtractedField).where(*conditions)) or 0
    rows = db.scalars(select(ExtractedField).where(*conditions).options(selectinload(ExtractedField.evidences))
                     .order_by(ExtractedField.id).offset((page - 1) * size).limit(size)).all()
    return rows, total
