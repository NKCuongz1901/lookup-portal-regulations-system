"""Celery tasks for document parse / structure extraction."""
from __future__ import annotations

import logging

from sqlalchemy import select
from sqlalchemy.exc import InterfaceError, OperationalError
from sqlalchemy.orm import selectinload

import app.models  # noqa: F401 — register ORM relationships for Celery worker
from app.core.celery_app import celery_app
from app.core.database import SessionLocal
from app.core.storage import download_bytes
from app.modules.documents.models import DocumentVersion
from app.modules.documents.enums import DocumentParseStatus
from app.modules.extractions import result_service
from app.modules.extractions.segment_service import (
    VersionNotClaimableError,
    VersionNotFoundError,
    claim_version_for_parsing,
    mark_parse_failed,
    replace_segments_and_mark_parsed,
)
from app.modules.extractions.services import parse_pdf
from app.modules.extractions.structure_extractor import extract_structure
from app.modules.extractions.text_normalizer import normalize_pages

logger = logging.getLogger(__name__)

PDF_MIME = "application/pdf"


@celery_app.task(name="extractions.process_document")
def process_document(document_version_id: int) -> dict:
    """Parse, save segments + pending run, then dispatch field extraction."""
    with SessionLocal() as db:
        return _process_document(db, document_version_id)


def _process_document(db, document_version_id: int) -> dict:
    claimed = False
    try:
        claim_version_for_parsing(db, document_version_id)
        claimed = True

        version = db.scalar(
            select(DocumentVersion)
            .options(selectinload(DocumentVersion.file))
            .where(DocumentVersion.id == document_version_id)
        )
        if version is None or version.file is None:
            raise VersionNotFoundError(
                f"document version {document_version_id} or its file not found"
            )

        if version.file.mime_type != PDF_MIME:
            raise ValueError(
                f"unsupported mime_type for parsing: {version.file.mime_type}"
            )
        if version.file.storage_provider != "r2":
            raise ValueError(
                f"unsupported storage_provider: {version.file.storage_provider}"
            )

        pdf_bytes = download_bytes(version.file.storage_key)
        result = extract_structure(normalize_pages(parse_pdf(pdf_bytes)))
        segment_count = replace_segments_and_mark_parsed(
            db, document_version_id, result, create_field_run=True,
        )
        logger.info(
            "Parsed document_version_id=%s segments=%s parser=%s",
            document_version_id,
            segment_count,
            result.parser_version,
        )
        summary = {
            "document_version_id": document_version_id,
            "segments": segment_count,
            "parser_version": result.parser_version,
        }
    except VersionNotClaimableError:
        logger.info(
            "Skip document_version_id=%s (not claimable)",
            document_version_id,
        )
        db.rollback()
        version = db.get(DocumentVersion, document_version_id)
        if version is None or version.parse_status != DocumentParseStatus.PARSED:
            return {"document_version_id": document_version_id, "skipped": True}
        summary = {
            "document_version_id": document_version_id,
            "skipped": True,
        }
    except Exception:
        logger.exception(
            "Failed parsing document_version_id=%s",
            document_version_id,
        )
        if claimed:
            try:
                mark_parse_failed(db, document_version_id)
            except Exception:
                logger.exception(
                    "Failed to mark document_version_id=%s as failed",
                    document_version_id,
                )
        raise
    # This stage has its own run/status. Queue failure never undoes parsed text.
    run = result_service.create_run(db, document_version_id)
    if run.status == "pending" and not enqueue_field_extraction(run.id):
        result_service.record_queue_failure(db, run.id)
    summary.update(extraction_run_id=run.id, extraction_status=run.status)
    return summary


@celery_app.task(
    name="extractions.extract_document_fields", bind=True, acks_late=True,
    autoretry_for=(OperationalError, InterfaceError), retry_backoff=True,
    retry_kwargs={"max_retries": 3}, soft_time_limit=570, time_limit=600,
)
def extract_document_fields(self, extraction_run_id: int) -> dict:
    with SessionLocal() as db:
        run = result_service.execute_run(db, extraction_run_id)
        if run.status == "processing":
            # A redelivery may arrive before a dead attempt's lease expires.
            db.rollback()
            raise self.retry(countdown=result_service.LEASE_SECONDS, max_retries=3)
        return {"extraction_run_id": run.id, "status": run.status, "field_count": run.field_count}


def enqueue_field_extraction(extraction_run_id: int) -> bool:
    try:
        extract_document_fields.apply_async(args=[extraction_run_id], retry=False)
        return True
    except Exception:
        logger.exception("Failed to enqueue extraction_run_id=%s", extraction_run_id)
        return False


def enqueue_document_parse(document_version_id: int, *, mime_type: str) -> bool:
    """Queue parse after a successful upload commit. Returns True if enqueued.

    Non-PDF uploads are skipped (left ``pending`` until a DOCX path exists).
    Broker failures are logged and do not fail the upload response.
    """
    if mime_type != PDF_MIME:
        logger.info(
            "Skip enqueue for document_version_id=%s mime_type=%s",
            document_version_id,
            mime_type,
        )
        return False
    try:
        process_document.delay(document_version_id)
    except Exception:
        logger.exception(
            "Failed to enqueue parse for document_version_id=%s; left pending",
            document_version_id,
        )
        return False
    logger.info("Enqueued parse for document_version_id=%s", document_version_id)
    return True
