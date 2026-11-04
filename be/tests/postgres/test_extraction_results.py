"""Run lifecycle, atomicity, evidence history, API permissions and queue recovery."""
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from uuid import uuid4
from unittest.mock import patch
from pathlib import Path
from collections import Counter
import json
import os

import pytest
from sqlalchemy import func, select, inspect
from sqlalchemy.exc import IntegrityError

from app.models import Document, DocumentSegment, DocumentVersion, StoredFile
from app.modules.documents.enums import DocumentParseStatus
from app.modules.extractions import result_service as service
from app.modules.extractions.field_extractor import extract_fields
from app.modules.extractions.field_types import FieldSegment
from app.modules.extractions.models import ExtractedField, ExtractionRun, FieldEvidence
from app.modules.extractions.segment_service import claim_version_for_parsing, replace_segments_and_mark_parsed
from app.modules.extractions.structure_extractor import extract_structure
from app.modules.extractions.text_normalizer import normalize_pages


@pytest.fixture
def source(db, actors):
    document = Document(code="EXTRACT-TEST", title="Extraction persistence test", created_by=actors["ADMIN"])
    stored = StoredFile(storage_provider="r2", storage_key="documents/test/extract.pdf", original_name="extract.pdf",
                        mime_type="application/pdf", size_bytes=10, checksum_sha256="a" * 64, uploaded_by=actors["ADMIN"])
    db.add_all([document, stored])
    db.flush()
    version = DocumentVersion(document_id=document.id, file_id=stored.id, version_number=1,
                              created_by=actors["ADMIN"], parse_status=DocumentParseStatus.PROCESSING)
    db.add(version)
    db.commit()
    structure = extract_structure(normalize_pages([{"page_number": 1, "content":
        "Điều 5. Hồ sơ\n1. Sinh viên phải nộp hồ sơ trước ngày 15/12/2026."}]))
    replace_segments_and_mark_parsed(db, version.id, structure)
    return document, version


def row_count(db, model):
    return db.scalar(select(func.count()).select_from(model))


def test_run_is_atomic_idempotent_and_separate_manual_runs_keep_history(db, source, actors):
    _, version = source
    key = f"manual:{uuid4()}"
    run = service.create_run(db, version.id, request_key=key, requested_by=actors["ADMIN"])
    assert run.status == "pending" and run.attempt_count == 0
    assert service.create_run(db, version.id, request_key=key).id == run.id
    result = service.execute_run(db, run.id)
    assert result.status == "completed" and result.field_count == 2
    assert result.attempt_count == 1
    assert result.execution_token is None and result.lease_expires_at is None
    fields, total = service.list_fields(db, run.id, 1, 100)
    assert total == 2 and {field.field_key for field in fields} == {"deadline", "obligation"}
    for field in fields:
        assert field.review_status == "pending"
        for evidence in field.evidences:
            assert evidence.document_segment_id == evidence.source_segment_id
            assert evidence.segment_content_snapshot[evidence.start_offset:evidence.end_offset] == evidence.quote
    before_ids = [field.id for field in fields]
    assert service.execute_run(db, run.id).attempt_count == 1
    assert [field.id for field in service.list_fields(db, run.id, 1, 100)[0]] == before_ids
    another = service.create_run(db, version.id, request_key=f"manual:{uuid4()}")
    service.execute_run(db, another.id)
    assert another.id != run.id
    assert row_count(db, ExtractionRun) == 2 and row_count(db, ExtractedField) == 4
    db.refresh(version)
    assert version.parse_status == DocumentParseStatus.PARSED


def test_parser_commit_contains_pending_run_and_auto_key_is_timezone_stable(db, source):
    _, version = source
    claim_version_for_parsing(db, version.id, force=True)
    structure = extract_structure(normalize_pages([{"page_number": 1, "content": "Nộp trước 15/12/2026."}]))
    replace_segments_and_mark_parsed(db, version.id, structure, create_field_run=True)
    pending = db.scalar(select(ExtractionRun))
    assert pending and pending.status == "pending"
    assert service.create_run(db, version.id).id == pending.id
    db.refresh(version)
    fingerprint = pending.source_fingerprint
    first = service._automatic_key(version, fingerprint)
    version.parsed_at = version.parsed_at.astimezone(timezone(timedelta(hours=-5)))
    assert service._automatic_key(version, fingerprint) == first
    db.rollback()
    assert row_count(db, ExtractionRun) == 1


@pytest.mark.parametrize("breakage", ["bad_quote", "bad_constraint", "wrong_segment"])
def test_failed_result_rolls_back_all_fields_and_same_run_can_retry(db, source, breakage):
    _, version = source
    sources = db.scalars(select(DocumentSegment).where(DocumentSegment.document_version_id == version.id).order_by(DocumentSegment.segment_index)).all()
    original = extract_fields([FieldSegment(row.segment_index, row.content, row.id, row.page_number, row.section_title) for row in sources], document_version_id=version.id)
    candidate = original.candidates[-1]
    if breakage == "bad_constraint":
        candidate = replace(candidate, item_index=-1)
    else:
        bad = replace(candidate.evidences[0], **({"quote": "secret invalid text"} if breakage == "bad_quote" else {"document_segment_id": 999999}))
        candidate = replace(candidate, evidences=(bad,) + candidate.evidences[1:])
    broken = replace(original, candidates=original.candidates[:-1] + (candidate,))
    run = service.create_run(db, version.id)
    with patch.object(service, "extract_fields", return_value=broken):
        with pytest.raises((ValueError, IntegrityError)):
            service.execute_run(db, run.id)
    db.refresh(run)
    assert run.status == "failed" and run.field_count == 0
    assert run.error_code == "extraction_failed" and "secret" not in run.error_message
    assert row_count(db, ExtractedField) == row_count(db, FieldEvidence) == 0
    db.refresh(version)
    assert version.parse_status == DocumentParseStatus.PARSED
    assert service.prepare_retry(db, run.id).status == "pending"
    retried = service.execute_run(db, run.id)
    assert retried.status == "completed" and retried.attempt_count == 2
    assert retried.field_count == 2 and row_count(db, ExtractionRun) == 1


def test_reparse_keeps_snapshot_and_stale_queued_run_cannot_use_new_source(db, source):
    _, version = source
    completed = service.create_run(db, version.id)
    service.execute_run(db, completed.id)
    queued = service.create_run(db, version.id, request_key=f"manual:{uuid4()}")
    evidence_before = db.scalars(select(FieldEvidence).order_by(FieldEvidence.id)).all()
    snapshots = [(e.id, e.source_segment_id, e.quote, e.segment_content_snapshot) for e in evidence_before]
    claim_version_for_parsing(db, version.id, force=True)
    new_structure = extract_structure(normalize_pages([{"page_number": 2, "content": "Nộp trước 20/01/2027."}]))
    replace_segments_and_mark_parsed(db, version.id, new_structure, create_field_run=True)
    db.expire_all()
    evidence_after = db.scalars(select(FieldEvidence).order_by(FieldEvidence.id)).all()
    assert [(e.id, e.source_segment_id, e.quote, e.segment_content_snapshot) for e in evidence_after] == snapshots
    assert all(e.document_segment_id is None for e in evidence_after)
    with pytest.raises(service.SourceChangedError):
        service.execute_run(db, queued.id)
    assert service.get_run(db, queued.id).error_code == "source_changed"
    with pytest.raises(service.SourceChangedError):
        service.prepare_retry(db, queued.id)
    assert service.execute_run(db, completed.id).status == "completed"
    latest = service.create_run(db, version.id)
    assert latest.id not in {completed.id, queued.id}
    service.execute_run(db, latest.id)
    fields, _ = service.list_fields(db, latest.id, 1, 10)
    assert fields[0].normalized_value["date"] == "2027-01-20"


def test_active_lease_excludes_duplicates_and_old_attempt_cannot_fail_new_attempt(db, source):
    _, version = source
    run = service.create_run(db, version.id)
    first = service.claim_run(db, run.id)
    assert first and service.claim_run(db, run.id) is None
    with pytest.raises(service.RunConflictError):
        service.prepare_retry(db, run.id)
    run = service.get_run(db, run.id)
    run.lease_expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
    db.commit()
    second = service.claim_run(db, run.id)
    assert second and second != first
    service.mark_run_failed(db, run.id, first, RuntimeError("old worker"))
    assert service.get_run(db, run.id).execution_token == second
    assert service.get_run(db, run.id).status == "processing"
    service.mark_run_failed(db, run.id, second, RuntimeError("current worker"))
    assert service.execute_run(db, run.id).status == "completed"
    service.mark_run_failed(db, run.id, second, RuntimeError("late error"))
    assert service.get_run(db, run.id).status == "completed"


def test_zero_candidates_complete_and_rule_version_change_requires_new_run(db, source):
    _, version = source
    rows = db.scalars(select(DocumentSegment).where(DocumentSegment.document_version_id == version.id)).all()
    for row in rows:
        row.content = "Nội dung thông thường."
    db.commit()
    run = service.create_run(db, version.id)
    assert service.execute_run(db, run.id).field_count == 0
    assert service.get_run(db, run.id).status == "completed"
    queued = service.create_run(db, version.id, request_key=f"manual:{uuid4()}")
    queued.rule_version = "fields-obsolete"
    db.commit()
    with pytest.raises(service.RuleVersionChangedError):
        service.execute_run(db, queued.id)
    assert service.get_run(db, queued.id).error_code == "rule_version_changed"


def test_api_create_read_filter_retry_and_queue_outage(client, db, source, headers):
    _, version = source
    path = f"/api/v1/document-versions/{version.id}/extraction-runs"
    payload = {"idempotency_key": str(uuid4())}
    with patch("app.modules.extractions.router.enqueue_field_extraction", return_value=False):
        response = client.post(path, headers=headers["STAFF"], json=payload)
    assert response.status_code == 503
    run_id = response.json()["data"]["id"]
    assert response.json()["data"]["error_code"] == "queue_unavailable"
    with patch("app.modules.extractions.router.enqueue_field_extraction", return_value=True) as enqueue:
        response = client.post(path, headers=headers["STAFF"], json=payload)
        assert response.status_code == 202 and response.json()["data"]["id"] == run_id
        enqueue.assert_called_once_with(run_id)
    service.execute_run(db, run_id)
    response = client.get(path, headers=headers["ADMIN"], params={"page": 1, "itemsPerPage": 1})
    assert response.status_code == 200 and response.json()["meta"]["total"] == 1
    detail = client.get(f"/api/v1/extraction-runs/{run_id}", headers=headers["STAFF"])
    assert detail.json()["data"]["status"] == "completed"
    assert "execution_token" not in detail.json()["data"]
    response = client.get(f"/api/v1/extraction-runs/{run_id}/fields", headers=headers["STAFF"],
                          params={"field_key": "deadline", "review_status": "pending", "itemsPerPage": 1})
    assert response.status_code == 200 and response.json()["meta"]["total"] == 1
    field = response.json()["data"][0]
    assert field["normalized_value"]["date"] == "2026-12-15"
    for e in field["evidences"]:
        assert e["segment_content_snapshot"][e["start_offset"]:e["end_offset"]] == e["quote"]
    with patch("app.modules.extractions.router.enqueue_field_extraction") as enqueue:
        assert client.post(path, headers=headers["STAFF"], json=payload).status_code == 200
        assert client.post(f"/api/v1/extraction-runs/{run_id}/retry", headers=headers["STAFF"]).status_code == 200
        enqueue.assert_not_called()


def test_api_authorization_deleted_sources_and_validation(client, db, source, headers):
    document, version = source
    run = service.create_run(db, version.id)
    path = f"/api/v1/document-versions/{version.id}/extraction-runs"
    urls = [path, f"/api/v1/extraction-runs/{run.id}", f"/api/v1/extraction-runs/{run.id}/fields"]
    for url in urls:
        assert client.get(url).status_code in {401, 403}
        assert client.get(url, headers=headers["STUDENT"]).status_code == 403
        assert client.get(url, headers=headers["INACTIVE"]).status_code == 401
    assert client.post(path, headers=headers["STUDENT"], json={"idempotency_key": str(uuid4())}).status_code == 403
    assert client.post(f"/api/v1/extraction-runs/{run.id}/retry", headers=headers["STUDENT"]).status_code == 403
    assert client.post(path, headers=headers["ADMIN"], json={}).status_code == 422
    assert client.get(path, headers=headers["STAFF"], params={"itemsPerPage": 101}).status_code == 422
    assert client.get(urls[-1], headers=headers["STAFF"], params={"field_key": "unknown"}).status_code == 422
    document.deleted_at = datetime.now(timezone.utc)
    db.commit()
    for url in urls:
        assert client.get(url, headers=headers["STAFF"]).status_code == 404
    assert client.post(path, headers=headers["STAFF"], json={"idempotency_key": str(uuid4())}).status_code == 404
    assert client.post(f"/api/v1/extraction-runs/{run.id}/retry", headers=headers["STAFF"]).status_code == 404


def test_api_unparsed_source_and_live_retry_are_conflicts(client, db, source, headers):
    _, version = source
    run = service.create_run(db, version.id)
    service.claim_run(db, run.id)
    assert client.post(f"/api/v1/extraction-runs/{run.id}/retry", headers=headers["STAFF"]).status_code == 409
    version = db.get(DocumentVersion, version.id)
    version.parse_status = DocumentParseStatus.PROCESSING
    db.commit()
    response = client.post(f"/api/v1/document-versions/{version.id}/extraction-runs", headers=headers["STAFF"],
                           json={"idempotency_key": str(uuid4())})
    assert response.status_code == 409


def test_new_migration_downgrade_and_upgrade_leave_document_tables(db):
    from alembic.config import Config
    from alembic.migration import MigrationContext
    from alembic.operations import Operations
    from alembic.script import ScriptDirectory

    config = Config()
    config.set_main_option("script_location", str(Path(__file__).resolve().parents[2] / "alembic"))
    migration = ScriptDirectory.from_config(config).get_revision("b8f31d2c9a60").module
    connection = db.connection()
    with Operations.context(MigrationContext.configure(connection)):
        migration.downgrade()
    tables = set(inspect(connection).get_table_names())
    assert "document_segments" in tables
    assert not {"extraction_runs", "extracted_fields", "field_evidences"} & tables
    with Operations.context(MigrationContext.configure(connection)):
        migration.upgrade()
    assert {"extraction_runs", "extracted_fields", "field_evidences"} <= set(inspect(connection).get_table_names())


@pytest.mark.parametrize("name,pages_file,expected", [
    ("admissions", "regulations.pages.json", {"deadline": 1, "obligation": 5, "applicable_subject": 7}),
    ("tuition", "tuition-notice.pages.json", {"deadline": 2, "legal_basis": 1}),
])
def test_supplied_pdf_segments_persist_with_exact_evidence(db, source, name, pages_file, expected):
    """Optional local smoke test for the two previously downloaded R2 PDFs."""
    if os.environ.get("RUN_EXTRACTION_PDF_SMOKE") != "1":
        pytest.skip("Set RUN_EXTRACTION_PDF_SMOKE=1 to use the cached R2 PDF page text")
    root = Path(__file__).resolve().parents[2] / ".cache"
    path = root / "extraction-smoke" / pages_file
    if not path.is_file():
        pytest.fail(f"Missing cached source: {path}")
    _, version = source
    structure = extract_structure(normalize_pages(json.loads(path.read_text(encoding="utf-8"))))
    claim_version_for_parsing(db, version.id, force=True)
    replace_segments_and_mark_parsed(db, version.id, structure, create_field_run=True)
    run = service.create_run(db, version.id)
    service.execute_run(db, run.id)
    fields, total = service.list_fields(db, run.id, 1, 100)
    assert dict(Counter(field.field_key for field in fields)) == expected
    assert run.field_count == total == sum(expected.values())
    for field in fields:
        for evidence in field.evidences:
            segment = db.get(DocumentSegment, evidence.document_segment_id)
            assert segment.content == evidence.segment_content_snapshot
            assert segment.content[evidence.start_offset:evidence.end_offset] == evidence.quote
            assert segment.page_number == evidence.page_number
    from app.modules.extractions.schemas import RunResponse, ExtractedFieldResponse

    output = root / "extraction-persistence"
    output.mkdir(parents=True, exist_ok=True)
    report = {"database": "isolated PostgreSQL test schema; rolled back after test",
              "source": str(path), "run": RunResponse.model_validate(run).model_dump(mode="json"),
              "fields": [ExtractedFieldResponse.model_validate(field).model_dump(mode="json") for field in fields]}
    (output / f"{name}.persisted.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
