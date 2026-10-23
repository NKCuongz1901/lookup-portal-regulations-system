from unittest.mock import Mock

import pytest
from sqlalchemy import inspect, select

from app.models import Document, DocumentRelation, DocumentSegment, DocumentTag, DocumentVersion, StoredFile, Tag
from app.modules.documents import services
from app.modules.documents.enums import DocumentPublicationStatus, DocumentRelationType


@pytest.fixture
def graph(db, actors):
    document = Document(code="DELETE-ME", title="Văn bản cần xóa", created_by=actors["STAFF"])
    other = Document(code="KEEP-ME", title="Văn bản giữ lại", created_by=actors["STAFF"])
    tag = Tag(name="Đào tạo", slug="dao-tao")
    file = StoredFile(storage_provider="r2", storage_key="documents/delete-me/file.pdf",
                      original_name="file.pdf", mime_type="application/pdf", size_bytes=1024)
    version = DocumentVersion(document=document, file=file, version_number=1, is_current=True, created_by=actors["STAFF"])
    segment = DocumentSegment(document_version=version, segment_index=0, content="Điều 1")
    relation = DocumentRelation(source_document=document, target_document=other,
                                relation_type=DocumentRelationType.REPLACED_BY, created_by=actors["STAFF"])
    link = DocumentTag(document=document, tag=tag)
    db.add_all([document, other, tag, file, version, segment, relation, link])
    db.commit()
    return document, other, version, file, segment, relation, tag


@pytest.mark.parametrize("role", ["ADMIN", "STAFF"])
def test_delete_hides_document_preserves_history_and_never_calls_storage(client, db, headers, actors, graph, monkeypatch, role):
    document, other, version, file, segment, relation, tag = graph
    storage = Mock(side_effect=AssertionError("Soft deletion must not access R2"))
    for name in ("delete_object", "upload_bytes", "generate_download_url"):
        monkeypatch.setattr(services, name, storage)
    path = f"/api/v1/documents/{document.id}"
    response = client.delete(path, headers=headers[role])
    assert response.status_code == 200, response.text
    assert response.json()["data"] is None
    db.refresh(document)
    assert document.deleted_at is not None
    assert document.deleted_by == actors[role]
    assert document.updated_by == actors[role]
    deleted_at = document.deleted_at

    for suffix in ("", "/versions", f"/download-url?version_id={version.id}", "/download-url"):
        assert client.get(path + suffix, headers=headers[role]).status_code == 404
    assert client.patch(path, headers=headers[role], json={"title": "Cannot edit"}).status_code == 404
    assert client.patch(path + "/archive", headers=headers[role]).status_code == 404
    assert client.post(path + "/versions", headers=headers[role], files={
        "file": ("file.pdf", b"%PDF-1.7\nTest", "application/pdf"),
    }).status_code == 404
    assert client.delete(path, headers=headers[role]).status_code == 404
    db.refresh(document)
    assert document.deleted_at == deleted_at
    assert document.title == "Văn bản cần xóa"

    listing = client.get("/api/v1/documents", headers=headers[role]).json()
    assert listing["meta"]["total"] == 1
    assert [item["id"] for item in listing["data"]] == [other.id]
    for params in ({"search": document.code}, {"tag_id": tag.id}, {"publication_status": "draft", "search": document.code}):
        filtered = client.get("/api/v1/documents", headers=headers[role], params=params).json()
        assert filtered["data"] == []
        assert filtered["meta"]["total"] == 0
    for model, record in ((DocumentVersion, version), (StoredFile, file), (DocumentSegment, segment), (DocumentRelation, relation), (Tag, tag)):
        assert db.get(model, record.id) is not None
    assert db.get(DocumentTag, (document.id, tag.id)) is not None
    storage.assert_not_called()


def test_all_publication_states_can_be_deleted_and_deleted_codes_stay_reserved(client, db, headers, actors):
    for status in DocumentPublicationStatus:
        doc = Document(code=f"DELETE-{status.value}", title="Test", publication_status=status, created_by=actors["STAFF"])
        db.add(doc); db.commit()
        assert client.delete(f"/api/v1/documents/{doc.id}", headers=headers["ADMIN"]).status_code == 200
        listing = client.get("/api/v1/documents", headers=headers["STAFF"], params={"publication_status": status.value}).json()
        assert listing["data"] == []
        assert listing["meta"]["total"] == 0
        assert client.post("/api/v1/documents", headers=headers["STAFF"], json={"code": doc.code, "title": "Reused"}).status_code == 409


def test_delete_enforces_authentication_role_and_positive_ids(client, db, headers, graph):
    document = graph[0]
    path = f"/api/v1/documents/{document.id}"
    for auth, expected in (({}, 401), ({"Authorization": "Bearer invalid"}, 401), (headers["INACTIVE"], 401), (headers["STUDENT"], 403)):
        assert client.delete(path, headers=auth).status_code == expected
    db.refresh(document)
    assert document.deleted_at is None
    for value in ("0", "-1", str(2**63), "invalid"):
        assert client.delete(f"/api/v1/documents/{value}", headers=headers["ADMIN"]).status_code == 422
    assert client.delete("/api/v1/documents/999999", headers=headers["STAFF"]).status_code == 404


def test_failed_commit_rolls_back_deletion(db, actors, graph, monkeypatch):
    document = graph[0]
    with monkeypatch.context() as patch:
        patch.setattr(db, "commit", Mock(side_effect=RuntimeError("Commit failed")))
        with pytest.raises(RuntimeError, match="Commit failed"):
            services.delete_document(db, document.id, actors["ADMIN"])
    db.refresh(document)
    assert document.deleted_at is None
    assert document.deleted_by is None


def test_upload_rechecks_deletion_after_storage_write(client, db, headers, actors, graph, monkeypatch):
    document, _, existing_version, *_ = graph
    cleanup = Mock()
    monkeypatch.setattr(services, "delete_object", cleanup)
    # Simulate deletion while an upload is in flight, before its version transaction.
    monkeypatch.setattr(services, "upload_bytes", lambda **kwargs: services.delete_document(db, document.id, actors["ADMIN"]))
    response = client.post(f"/api/v1/documents/{document.id}/versions", headers=headers["STAFF"], files={
        "file": ("new.pdf", b"%PDF-1.7\nTest", "application/pdf"),
    })
    assert response.status_code == 404, response.text
    assert list(db.scalars(select(DocumentVersion.id).where(DocumentVersion.document_id == document.id))) == [existing_version.id]
    cleanup.assert_called_once()
    assert cleanup.call_args.args[0].startswith(f"documents/{document.id}/")


def test_audit_migration_matches_real_postgresql_schema(db):
    inspector = inspect(db.connection())
    columns = {column["name"]: column for column in inspector.get_columns("documents")}
    assert columns["deleted_at"]["nullable"]
    assert columns["deleted_at"]["type"].timezone
    assert columns["deleted_by"]["nullable"]
    foreign_key = next(key for key in inspector.get_foreign_keys("documents") if key["constrained_columns"] == ["deleted_by"])
    assert foreign_key["referred_table"] == "users"
    assert foreign_key["options"]["ondelete"] == "SET NULL"
