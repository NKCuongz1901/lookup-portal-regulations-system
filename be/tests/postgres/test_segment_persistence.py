"""PostgreSQL persistence for document_segments (opt-in via TEST_DATABASE_URL)."""
from dataclasses import replace as dc_replace

import pytest
from sqlalchemy import func, select

from app.models import Document, DocumentVersion, StoredFile
from app.modules.documents.enums import DocumentParseStatus
from app.modules.documents.models import DocumentSegment
from app.modules.extractions.segment_service import (
    VersionNotClaimableError,
    claim_version_for_parsing,
    mark_parse_failed,
    replace_segments_and_mark_parsed,
)
from app.modules.extractions.structure_extractor import ExtractionResult, extract_structure
from app.modules.extractions.text_normalizer import normalize_pages


def _seed_version(db, actors, *, parse_status=DocumentParseStatus.PENDING):
    document = Document(code="SEG-TEST-1", title="Segment persist test", created_by=actors["ADMIN"])
    db.add(document)
    db.flush()
    stored = StoredFile(
        storage_provider="r2",
        storage_key="documents/test/file.pdf",
        original_name="file.pdf",
        mime_type="application/pdf",
        size_bytes=10,
        checksum_sha256="a" * 64,
        uploaded_by=actors["ADMIN"],
    )
    db.add(stored)
    db.flush()
    version = DocumentVersion(
        document_id=document.id,
        version_number=1,
        file_id=stored.id,
        is_current=True,
        parse_status=parse_status,
        created_by=actors["ADMIN"],
    )
    db.add(version)
    db.commit()
    return version


def _extract(text: str) -> ExtractionResult:
    return extract_structure(normalize_pages([{"page_number": 1, "content": text}]))


def test_claim_replace_and_force_rerun(db, actors):
    version = _seed_version(db, actors)
    claimed = claim_version_for_parsing(db, version.id)
    assert claimed.parse_status == DocumentParseStatus.PROCESSING

    with pytest.raises(VersionNotClaimableError):
        claim_version_for_parsing(db, version.id)

    result = _extract("Điều 5. Điều kiện\n1. Hoàn thành học phần.")
    count = replace_segments_and_mark_parsed(db, version.id, result)
    assert count == len(result.segments)

    db.refresh(version)
    assert version.parse_status == DocumentParseStatus.PARSED
    assert version.parser_version == result.parser_version
    assert version.parsed_at is not None

    rows = db.scalars(
        select(DocumentSegment)
        .where(DocumentSegment.document_version_id == version.id)
        .order_by(DocumentSegment.segment_index)
    ).all()
    assert len(rows) == count
    assert [row.segment_index for row in rows] == list(range(count))
    assert all(row.content.strip() for row in rows)

    claim_version_for_parsing(db, version.id, force=True)
    second = _extract("Điều 1. Phạm vi\n1. Nội dung mới.")
    replace_segments_and_mark_parsed(db, version.id, second)
    total = db.scalar(
        select(func.count()).select_from(DocumentSegment).where(
            DocumentSegment.document_version_id == version.id
        )
    )
    assert total == len(second.segments)


def test_failed_replace_keeps_previous_segments(db, actors):
    version = _seed_version(db, actors)
    claim_version_for_parsing(db, version.id)
    first = _extract("Điều 1. Phạm vi\n1. Giữ lại khi lỗi.")
    replace_segments_and_mark_parsed(db, version.id, first)
    before = db.scalar(
        select(func.count()).select_from(DocumentSegment).where(
            DocumentSegment.document_version_id == version.id
        )
    )

    claim_version_for_parsing(db, version.id, force=True)
    broken = _extract("Điều 2. Thử\n1. Đoạn hợp lệ.")
    bad = ExtractionResult(
        full_text=broken.full_text,
        segments=tuple(
            dc_replace(segment, content="   ") if index == 0 else segment
            for index, segment in enumerate(broken.segments)
        ),
        nodes=broken.nodes,
        page_spans=broken.page_spans,
        warnings=broken.warnings,
        parser_version=broken.parser_version,
    )
    with pytest.raises(ValueError, match="empty content"):
        replace_segments_and_mark_parsed(db, version.id, bad)

    after = db.scalar(
        select(func.count()).select_from(DocumentSegment).where(
            DocumentSegment.document_version_id == version.id
        )
    )
    assert after == before
    db.refresh(version)
    assert version.parse_status == DocumentParseStatus.PROCESSING
    mark_parse_failed(db, version.id)
    db.refresh(version)
    assert version.parse_status == DocumentParseStatus.FAILED


def test_mark_failed_from_pending(db, actors):
    version = _seed_version(db, actors)
    mark_parse_failed(db, version.id)
    db.refresh(version)
    assert version.parse_status == DocumentParseStatus.FAILED
