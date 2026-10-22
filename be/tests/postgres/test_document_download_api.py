from unittest.mock import Mock

import pytest
from botocore.exceptions import ClientError, EndpointConnectionError

from app.core import storage
from app.core.config import settings
from app.models import Document, DocumentVersion, StoredFile
from app.modules.documents import services


@pytest.fixture
def r2(monkeypatch):
    client = Mock()
    client.head_object.return_value = {}
    client.generate_presigned_url.return_value = "https://test.r2.cloudflarestorage.com/file?signature=test"
    monkeypatch.setattr(storage, "get_r2_client", lambda: client)
    return client


@pytest.fixture
def records(db, actors):
    document = Document(code="DOWNLOAD", title="Download test", created_by=actors["STAFF"])
    other = Document(code="OTHER", title="Other document", created_by=actors["ADMIN"])
    empty = Document(code="EMPTY", title="Without files", created_by=actors["ADMIN"])
    db.add_all([document, other, empty])
    db.flush()
    versions = []
    for number, owner in ((1, document), (2, document), (1, other)):
        file = StoredFile(
            storage_provider="r2", storage_key=f"documents/{owner.id}/version-{number}",
            original_name="Quy chế.pdf" if number == 1 else "Biểu mẫu.docx",
            mime_type="application/pdf" if number == 1 else services.MIME_BY_EXTENSION[".docx"],
            size_bytes=1024 * number, uploaded_by=actors["STAFF"],
        )
        version = DocumentVersion(
            document=owner, file=file, version_number=number,
            is_current=(owner is other or number == 2), created_by=actors["STAFF"],
        )
        db.add(version)
        versions.append(version)
    db.commit()
    return document, other, empty, versions


@pytest.mark.parametrize("role", ["ADMIN", "STAFF"])
def test_current_and_selected_versions_download(client, headers, records, r2, monkeypatch, role):
    document, _, _, versions = records
    monkeypatch.setattr(settings, "R2_DOWNLOAD_URL_EXPIRE_SECONDS", 120)
    for selected, params in ((versions[1], {}), (versions[0], {"version_id": versions[0].id})):
        response = client.get(f"/api/v1/documents/{document.id}/download-url", headers=headers[role], params=params)
        assert response.status_code == 200, response.text
        assert response.headers["Cache-Control"] == "no-store"
        assert response.json()["data"] == {
            "document_id": document.id, "version_id": selected.id,
            "file_name": selected.file.original_name, "mime_type": selected.file.mime_type,
            "size_bytes": selected.file.size_bytes, "url": r2.generate_presigned_url.return_value,
            "expires_in": 120,
        }
        r2.head_object.assert_called_with(Bucket=settings.R2_BUCKET_NAME, Key=selected.file.storage_key)
        signing = r2.generate_presigned_url.call_args
        assert signing.args == ("get_object",)
        assert signing.kwargs["ExpiresIn"] == 120
        assert signing.kwargs["Params"]["ResponseContentDisposition"].startswith("attachment;")


def test_version_list_is_paginated_and_scoped(client, headers, records, r2):
    document, _, empty, versions = records
    for role in ("ADMIN", "STAFF"):
        for page, expected in ((1, [versions[1].id]), (2, [versions[0].id]), (3, [])):
            response = client.get(
                f"/api/v1/documents/{document.id}/versions", headers=headers[role],
                params={"page": page, "itemsPerPage": 1},
            )
            assert response.status_code == 200, response.text
            result = response.json()
            assert [version["id"] for version in result["data"]] == expected
            assert result["meta"] == {"page": page, "itemsPerPage": 1, "total": 2, "totalPages": 2}
            if page == 1:
                assert result["data"][0]["is_current"] is True
                assert result["data"][0]["file"]["original_name"] == "Biểu mẫu.docx"
    assert client.get(f"/api/v1/documents/{empty.id}/versions", headers=headers["STAFF"]).json()["data"] == []
    assert client.get("/api/v1/documents/999999/versions", headers=headers["STAFF"]).status_code == 404
    r2.head_object.assert_not_called()


def test_missing_and_foreign_versions_never_access_r2(client, headers, records, r2, db):
    document, _, empty, versions = records
    requests = [
        (999999, {}), (empty.id, {}),
        (document.id, {"version_id": 999999}),
        (document.id, {"version_id": versions[2].id}),
    ]
    for document_id, params in requests:
        response = client.get(f"/api/v1/documents/{document_id}/download-url", headers=headers["STAFF"], params=params)
        assert response.status_code == 404, response.text
    versions[1].is_current = False
    db.commit()
    response = client.get(f"/api/v1/documents/{document.id}/download-url", headers=headers["STAFF"])
    assert response.status_code == 404  # Do not silently choose the newest historical version.
    r2.head_object.assert_not_called()
    r2.generate_presigned_url.assert_not_called()


@pytest.mark.parametrize("error,expected", [
    (ClientError({"Error": {"Code": "404", "Message": "private details"}}, "HeadObject"), 404),
    (ClientError({"Error": {"Code": "NoSuchKey"}}, "HeadObject"), 404),
    (ClientError({"Error": {"Code": "NotFound"}}, "HeadObject"), 404),
    (ClientError({"Error": {"Code": "AccessDenied", "Message": "private details"}}, "HeadObject"), 502),
    (ClientError({"Error": {"Code": "NoSuchBucket"}}, "HeadObject"), 502),
    (EndpointConnectionError(endpoint_url="https://private-details.invalid"), 502),
])
def test_storage_errors_do_not_leak_credentials_or_issue_urls(client, headers, records, r2, error, expected):
    r2.head_object.side_effect = error
    response = client.get(f"/api/v1/documents/{records[0].id}/download-url", headers=headers["STAFF"])
    assert response.status_code == expected, response.text
    assert response.json()["status_code"] == expected
    assert response.json()["data"] is None
    assert "private" not in response.text
    r2.generate_presigned_url.assert_not_called()


def test_unsupported_storage_provider_does_not_sign_an_r2_url(client, headers, records, db, r2):
    document, _, _, versions = records
    versions[1].file.storage_provider = "local"
    db.commit()
    response = client.get(f"/api/v1/documents/{document.id}/download-url", headers=headers["STAFF"])
    assert response.status_code == 409
    r2.head_object.assert_not_called()


def test_download_and_version_list_require_active_management_account(client, headers, records, r2):
    for endpoint in ("download-url", "versions"):
        for auth, expected in (({}, 401), ({"Authorization": "Bearer invalid"}, 401), (headers["INACTIVE"], 401), (headers["STUDENT"], 403)):
            response = client.get(f"/api/v1/documents/{records[0].id}/{endpoint}", headers=auth)
            assert response.status_code == expected, response.text
    r2.head_object.assert_not_called()


def test_invalid_ids_and_client_storage_parameters_are_rejected(client, headers, records, r2):
    path = f"/api/v1/documents/{records[0].id}"
    for params in ({"version_id": 0}, {"version_id": -1}, {"version_id": 2**63}, {"version_id": "bad"}, {"storage_key": "arbitrary"}, {"expires_in": 604800}):
        assert client.get(path + "/download-url", headers=headers["STAFF"], params=params).status_code == 422
    for params in ({"page": 0}, {"itemsPerPage": 101}, {"search": "unsupported"}):
        assert client.get(path + "/versions", headers=headers["STAFF"], params=params).status_code == 422
    assert client.get("/api/v1/documents/0/download-url", headers=headers["STAFF"]).status_code == 422
    r2.head_object.assert_not_called()


def test_uploaded_file_can_be_listed_and_downloaded(client, headers, actors, db, r2, monkeypatch):
    document = Document(code="UPLOAD", title="Upload and download", created_by=actors["STAFF"])
    db.add(document)
    db.commit()
    uploaded = Mock()
    monkeypatch.setattr(services, "upload_bytes", uploaded)
    path = f"/api/v1/documents/{document.id}"
    response = client.post(path + "/versions", headers=headers["STAFF"], files={
        "file": ("Quy chế.pdf", b"%PDF-1.7\nTest download\n%%EOF", "application/pdf"),
    })
    assert response.status_code == 201, response.text
    version = response.json()["data"]
    assert client.get(path + "/versions", headers=headers["STAFF"]).json()["data"][0]["id"] == version["id"]
    download = client.get(path + "/download-url", headers=headers["STAFF"])
    assert download.status_code == 200, download.text
    assert download.json()["data"]["version_id"] == version["id"]
    assert download.json()["data"]["file_name"] == "Quy chế.pdf"
    r2.head_object.assert_called_with(Bucket=settings.R2_BUCKET_NAME, Key=uploaded.call_args.kwargs["storage_key"])
