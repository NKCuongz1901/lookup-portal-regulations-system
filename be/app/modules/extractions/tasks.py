"""Celery tasks for document parse / structure extraction."""
from __future__ import annotations

import logging

from sqlalchemy import select
from sqlalchemy.orm import selectinload

import app.models  # noqa: F401 — register ORM relationships for Celery worker
from app.core.celery_app import celery_app
from app.core.database import SessionLocal
from app.core.storage import download_bytes
from app.modules.documents.models import DocumentVersion
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
    """Download PDF from R2, extract structure, persist document_segments."""
    db = SessionLocal()
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
            db, document_version_id, result,
        )
        logger.info(
            "Parsed document_version_id=%s segments=%s parser=%s",
            document_version_id,
            segment_count,
            result.parser_version,
        )
        return {
            "document_version_id": document_version_id,
            "segments": segment_count,
            "parser_version": result.parser_version,
        }
    except VersionNotClaimableError:
        logger.info(
            "Skip document_version_id=%s (not claimable)",
            document_version_id,
        )
        return {
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
    finally:
        db.close()


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
