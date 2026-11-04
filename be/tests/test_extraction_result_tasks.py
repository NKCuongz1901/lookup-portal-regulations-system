from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from app.modules.documents.enums import DocumentParseStatus
from app.modules.extractions import tasks
from app.modules.extractions.segment_service import VersionNotClaimableError


def test_field_enqueue_does_not_retry_broker_publish_inline():
    with patch.object(tasks.extract_document_fields, "apply_async") as send:
        assert tasks.enqueue_field_extraction(12)
        send.assert_called_once_with(args=[12], retry=False)
    with patch.object(tasks.extract_document_fields, "apply_async", side_effect=ConnectionError("offline")):
        assert tasks.enqueue_field_extraction(12) is False


def test_parse_creates_pending_run_atomically_and_handles_queue_failure():
    db = MagicMock()
    db.scalar.return_value = SimpleNamespace(file=SimpleNamespace(mime_type="application/pdf", storage_provider="r2", storage_key="test.pdf"))
    run = SimpleNamespace(id=12, status="pending")
    with (patch.object(tasks, "claim_version_for_parsing"),
          patch.object(tasks, "download_bytes", return_value=b"PDF"),
          patch.object(tasks, "parse_pdf", return_value=[{"page_number": 1, "content": "Sinh viên phải nộp đơn."}]),
          patch.object(tasks, "replace_segments_and_mark_parsed", return_value=1) as persist,
          patch.object(tasks.result_service, "create_run", return_value=run),
          patch.object(tasks, "enqueue_field_extraction", return_value=False),
          patch.object(tasks.result_service, "record_queue_failure") as record,
          patch.object(tasks, "mark_parse_failed") as fail):
        result = tasks._process_document(db, 7)
    assert persist.call_args.kwargs == {"create_field_run": True}
    assert result["extraction_run_id"] == 12
    record.assert_called_once_with(db, 12)
    fail.assert_not_called()


def test_parse_failure_never_starts_field_extraction():
    db = MagicMock()
    db.scalar.return_value = SimpleNamespace(file=SimpleNamespace(mime_type="application/pdf", storage_provider="r2", storage_key="test.pdf"))
    with (patch.object(tasks, "claim_version_for_parsing"),
          patch.object(tasks, "download_bytes", side_effect=RuntimeError("storage unavailable")),
          patch.object(tasks, "mark_parse_failed") as fail,
          patch.object(tasks.result_service, "create_run") as create):
        with pytest.raises(RuntimeError):
            tasks._process_document(db, 7)
    fail.assert_called_once_with(db, 7)
    create.assert_not_called()


def test_redelivered_parse_does_not_reparse_or_repeat_completed_extraction():
    db = MagicMock()
    db.get.return_value = SimpleNamespace(parse_status=DocumentParseStatus.PARSED)
    with (patch.object(tasks, "claim_version_for_parsing", side_effect=VersionNotClaimableError()),
          patch.object(tasks, "download_bytes") as download,
          patch.object(tasks.result_service, "create_run", return_value=SimpleNamespace(id=12, status="completed")),
          patch.object(tasks, "enqueue_field_extraction") as send):
        result = tasks._process_document(db, 7)
    assert result["skipped"]
    download.assert_not_called()
    send.assert_not_called()


def test_field_task_reads_run_id_and_keeps_pdf_path_out_of_worker():
    context = MagicMock()
    db = context.__enter__.return_value
    with (patch.object(tasks, "SessionLocal", return_value=context),
          patch.object(tasks.result_service, "execute_run", return_value=SimpleNamespace(id=12, status="completed", field_count=4)) as execute,
          patch.object(tasks, "download_bytes") as download):
        result = tasks.extract_document_fields.run(12)
    assert result == {"extraction_run_id": 12, "status": "completed", "field_count": 4}
    execute.assert_called_once_with(db, 12)
    download.assert_not_called()
    context.__exit__.assert_called_once()
