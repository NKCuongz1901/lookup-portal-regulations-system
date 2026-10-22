from urllib.parse import parse_qs, unquote, urlsplit

import boto3
import pytest
from botocore.config import Config
from botocore.exceptions import ClientError
from botocore.stub import Stubber
from pydantic import ValidationError

from app.core import storage
from app.core.config import Settings, settings
from app.main import app


@pytest.mark.parametrize("name,mime_type", [
    ('Quy chế đào tạo "2026".pdf', "application/pdf"),
    ("Biểu mẫu.docx", "application/vnd.openxmlformats-officedocument.wordprocessingml.document"),
])
def test_download_signs_get_with_original_filename_and_expiry(monkeypatch, name, mime_type):
    client = boto3.client(
        "s3", endpoint_url="https://test.r2.cloudflarestorage.com", region_name="auto",
        aws_access_key_id="test-access", aws_secret_access_key="test-secret",
        config=Config(signature_version="s3v4"),
    )
    monkeypatch.setattr(storage, "get_r2_client", lambda: client)
    key = "documents/12/unique-object"
    with Stubber(client) as stubber:
        stubber.add_response("head_object", {}, {"Bucket": settings.R2_BUCKET_NAME, "Key": key})
        url = storage.generate_download_url(
            storage_key=key, original_name=name, mime_type=mime_type, expires_in=120,
        )
        stubber.assert_no_pending_responses()
    query = parse_qs(urlsplit(url).query)
    assert query["X-Amz-Expires"] == ["120"]
    assert query["X-Amz-Signature"]
    assert unquote(urlsplit(url).path).endswith("/" + key)
    assert query["response-content-type"] == [mime_type]
    assert query["response-cache-control"] == ["private, no-store"]
    disposition = query["response-content-disposition"][0]
    assert disposition.startswith('attachment; filename="')
    assert unquote(disposition.split("filename*=UTF-8''", 1)[1]) == name
    assert disposition.isascii()


@pytest.mark.parametrize("name,expected", [
    ("../../Quy chế.pdf", "Quy chế.pdf"),
    ("C:\\files\\Report.pdf", "Report.pdf"),
    ('test\r\nX-Injected: yes\x00.pdf', "testX-Injected: yes.pdf"),
    ("\u202etest.pdf", "test.pdf"),
    ("", "download"),
    ("..", "download"),
])
def test_download_filename_cannot_inject_headers_or_paths(name, expected):
    disposition = storage.download_content_disposition(name)
    assert unquote(disposition.split("filename*=UTF-8''", 1)[1]) == expected
    assert disposition.isascii()
    assert "\r" not in disposition and "\n" not in disposition and "\x00" not in disposition
    assert "\\" not in disposition


def test_missing_object_is_checked_before_signing(monkeypatch):
    client = boto3.client(
        "s3", endpoint_url="https://test.r2.cloudflarestorage.com", region_name="auto",
        aws_access_key_id="test-access", aws_secret_access_key="test-secret",
        config=Config(signature_version="s3v4"),
    )
    monkeypatch.setattr(storage, "get_r2_client", lambda: client)
    with Stubber(client) as stubber:
        stubber.add_client_error("head_object", service_error_code="404", http_status_code=404)
        with pytest.raises(ClientError):
            storage.generate_download_url(
                storage_key="missing", original_name="file.pdf", mime_type="application/pdf", expires_in=600,
            )


@pytest.mark.parametrize("expiry", [0, -1, 604801])
def test_download_expiry_respects_sigv4_limits(expiry):
    with pytest.raises(ValidationError):
        Settings.model_validate({**settings.model_dump(), "R2_DOWNLOAD_URL_EXPIRE_SECONDS": expiry})


def test_download_openapi_documents_json_and_version_selection():
    endpoint = app.openapi()["paths"]["/api/v1/documents/{document_id}/download-url"]["get"]
    assert endpoint["security"]
    assert {param["name"] for param in endpoint["parameters"]} == {"document_id", "version_id"}
    assert "application/json" in endpoint["responses"]["200"]["content"]
