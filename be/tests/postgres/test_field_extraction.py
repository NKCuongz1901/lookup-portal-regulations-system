"""Opt-in PostgreSQL read service, using the rollback-only isolated schema fixture."""
from datetime import datetime, timezone

import pytest
from sqlalchemy import func, select

from app.models import Document, DocumentVersion, StoredFile
from app.modules.documents.enums import DocumentParseStatus
from app.modules.documents.models import DocumentSegment
from app.modules.extractions.field_service import extract_fields_for_version, NoSegmentsError, VersionNotParsedError
from app.modules.extractions.segment_service import VersionNotFoundError


def seed(db, actor, number):
    document = Document(code=f"FIELD-{number}", title="Field extraction test", created_by=actor)
    stored = StoredFile(storage_provider="r2", storage_key=f"fields/test-{number}.pdf", original_name="test.pdf",
                        mime_type="application/pdf", size_bytes=10, checksum_sha256=str(number) * 64, uploaded_by=actor)
    db.add_all([document, stored])
    db.flush()
    version = DocumentVersion(document_id=document.id, version_number=1, file_id=stored.id,
                              parse_status=DocumentParseStatus.PARSED, created_by=actor)
    db.add(version)
    db.flush()
    return document, version


def test_reads_only_requested_version_and_preserves_database(db, actors):
    _, wanted = seed(db, actors["ADMIN"], 1)
    _, other = seed(db, actors["ADMIN"], 2)
    first = DocumentSegment(document_version_id=wanted.id, segment_index=0, page_number=1,
                            section_title="Điều 5", content="Sinh viên phải nộp hồ sơ trước ngày")
    second = DocumentSegment(document_version_id=wanted.id, segment_index=1, page_number=2,
                             section_title="Điều 5", content="15/12/2026.")
    db.add_all([second, first, DocumentSegment(document_version_id=other.id, segment_index=0,
                                              page_number=1, content="Nộp trước ngày 01/01/2099.")])
    db.commit()
    before = db.scalar(select(func.count()).select_from(DocumentSegment))
    result = extract_fields_for_version(db, wanted.id)
    assert result.document_version_id == wanted.id
    assert result.segment_count == 2
    assert {e.document_segment_id for c in result.candidates for e in c.evidences} == {first.id, second.id}
    assert next(c for c in result.candidates if c.field_key == "deadline").normalized_value["date"] == "2026-12-15"
    assert db.scalar(select(func.count()).select_from(DocumentSegment)) == before
    assert wanted.parse_status == DocumentParseStatus.PARSED
    assert not db.new and not db.deleted and not db.dirty


def test_deleted_unparsed_missing_or_empty_versions(db, actors):
    document, version = seed(db, actors["ADMIN"], 1)
    db.commit()
    with pytest.raises(NoSegmentsError):
        extract_fields_for_version(db, version.id)
    version.parse_status = DocumentParseStatus.PROCESSING
    db.commit()
    with pytest.raises(VersionNotParsedError):
        extract_fields_for_version(db, version.id)
    document.deleted_at = datetime.now(timezone.utc)
    db.commit()
    with pytest.raises(VersionNotFoundError):
        extract_fields_for_version(db, version.id)
    with pytest.raises(VersionNotFoundError):
        extract_fields_for_version(db, 999999999)
