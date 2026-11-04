"""Unit coverage for parse enqueue helpers (no Redis/R2)."""
from unittest.mock import patch

from app.modules.extractions.tasks import enqueue_document_parse


def test_enqueue_skips_non_pdf():
    with patch("app.modules.extractions.tasks.process_document.delay") as delay:
        assert enqueue_document_parse(12, mime_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document") is False
        delay.assert_not_called()


def test_enqueue_pdf_calls_delay():
    with patch("app.modules.extractions.tasks.process_document.delay") as delay:
        assert enqueue_document_parse(12, mime_type="application/pdf") is True
        delay.assert_called_once_with(12)


def test_enqueue_broker_failure_returns_false():
    with patch(
        "app.modules.extractions.tasks.process_document.delay",
        side_effect=ConnectionError("redis down"),
    ):
        assert enqueue_document_parse(12, mime_type="application/pdf") is False
