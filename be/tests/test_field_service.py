"""Service preconditions and no-write contract; PostgreSQL cases live separately."""
from contextlib import nullcontext
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from app.modules.documents.enums import DocumentParseStatus
from app.modules.extractions.field_service import (
    NoSegmentsError, VersionNotParsedError, extract_fields_for_version,
)
from app.modules.extractions.segment_service import VersionNotFoundError


def session(status=DocumentParseStatus.PARSED, rows=None):
    db = MagicMock()
    db.no_autoflush = nullcontext()
    db.scalar.return_value = SimpleNamespace(parse_status=status)
    db.scalars.return_value.all.return_value = rows or []
    return db


def test_service_keeps_persisted_segment_ids_and_does_not_write():
    db = session(rows=[SimpleNamespace(id=302, segment_index=0, page_number=3,
                                      section_title="Điều 5", content="Sinh viên phải nộp trước 15/12/2026.")])
    result = extract_fields_for_version(db, 25)
    assert result.document_version_id == 25
    assert {c.field_key for c in result.candidates} == {"deadline", "obligation"}
    assert all(e.document_segment_id == 302 for c in result.candidates for e in c.evidences)
    for method in (db.add, db.execute, db.commit, db.rollback, db.flush):
        method.assert_not_called()


@pytest.mark.parametrize("status", [DocumentParseStatus.PENDING, DocumentParseStatus.PROCESSING, DocumentParseStatus.FAILED])
def test_only_successfully_parsed_versions_are_eligible(status):
    db = session(status)
    with pytest.raises(VersionNotParsedError):
        extract_fields_for_version(db, 25)
    db.scalars.assert_not_called()


def test_missing_version_and_empty_segments_have_distinct_errors():
    db = session()
    db.scalar.return_value = None
    with pytest.raises(VersionNotFoundError):
        extract_fields_for_version(db, 25)
    with pytest.raises(NoSegmentsError):
        extract_fields_for_version(session(), 25)


@pytest.mark.parametrize("version_id", [0, -1, True, "25"])
def test_invalid_version_id_never_queries_database(version_id):
    db = session()
    with pytest.raises(ValueError):
        extract_fields_for_version(db, version_id)
    db.scalar.assert_not_called()
