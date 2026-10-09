from datetime import datetime, timedelta, timezone

import jwt
import pytest
from sqlalchemy import func, select

from app.core.config import settings
from app.models import Document, DocumentTag
from app.modules.documents import repository


def create(client, headers, path, payload, role="STAFF"):
    response = client.post(f"/api/v1/{path}", headers=headers[role], json=payload)
    assert response.status_code == 201, response.text
    assert response.json()["status_code"] == 201
    return response.json()["data"]


def make_document(client, headers, code="QD-01", **fields):
    return create(client, headers, "documents", {"code": code, "title": f"Văn bản {code}", **fields})


def test_document_lifecycle(client, headers, actors, db):
    kind = create(client, headers, "document-types", {"code": "QD", "name": "Quy định"}, "ADMIN")
    unit = create(client, headers, "issuing-units", {"code": "DT", "name": "Phòng đào tạo"}, "ADMIN")
    tag = create(client, headers, "tags", {"name": "Đào tạo", "slug": "dao-tao"})
    document = make_document(
        client, headers, title=" Quy định đào tạo ", description="Mô tả",
        document_type_id=kind["id"], issuing_unit_id=unit["id"],
        tag_ids=[tag["id"], tag["id"]], applicable_subject_codes=["STUDENT"],
        effective_from="2026-10-01", effective_until="2027-10-01",
    )
    document_id = document["id"]
    path = f"/api/v1/documents/{document_id}"
    assert document["publication_status"] == "draft"
    assert document["published_at"] is None
    assert document["created_by"] == actors["STAFF"]
    assert document["title"] == "Quy định đào tạo"
    assert document["document_type"]["name"] == kind["name"]
    assert document["issuing_unit"]["name"] == unit["name"]
    assert [item["id"] for item in document["tags"]] == [tag["id"]]

    response = client.patch(path, headers=headers["ADMIN"], json={"description": None, "title": "Tên mới"})
    assert response.status_code == 200, response.text
    updated = response.json()["data"]
    assert updated["description"] is None
    assert updated["updated_by"] == actors["ADMIN"]
    assert updated["created_by"] == actors["STAFF"]
    assert len(updated["tags"]) == 1
    assert updated["effective_from"] == "2026-10-01"

    response = client.patch(path, headers=headers["STAFF"], json={
        "tag_ids": [], "document_type_id": None, "applicable_subject_codes": [],
    })
    assert response.status_code == 200
    assert response.json()["data"]["tags"] == []
    assert response.json()["data"]["document_type"] is None
    assert db.scalar(select(func.count()).select_from(DocumentTag)) == 0

    archived = client.patch(path + "/archive", headers=headers["STAFF"])
    assert archived.status_code == 200
    assert archived.json()["data"]["publication_status"] == "archived"
    repeated = client.patch(path + "/archive", headers=headers["ADMIN"])
    assert repeated.json()["data"]["updated_by"] == actors["STAFF"]
    assert client.get(path, headers=headers["STAFF"]).status_code == 200
    assert client.get("/api/v1/documents", headers=headers["STAFF"]).json()["meta"]["total"] == 0
    listing = client.get("/api/v1/documents?publication_status=archived", headers=headers["ADMIN"]).json()
    assert listing["meta"]["total"] == 1
    assert listing["data"][0]["id"] == document_id


@pytest.mark.parametrize("path, payload, unique_key", [
    ("document-types", {"code": "QD", "name": "Quy định"}, "code"),
    ("issuing-units", {"code": "DT", "name": "Đào tạo"}, "code"),
    ("tags", {"slug": "dao-tao", "name": "Đào tạo"}, "slug"),
])
def test_metadata_crud_and_conflicts(client, headers, path, payload, unique_key):
    first = create(client, headers, path, payload, "ADMIN")
    second = create(client, headers, path, {**payload, unique_key: "other"}, "ADMIN")
    duplicate = client.post(f"/api/v1/{path}", headers=headers["ADMIN"], json=payload)
    assert duplicate.status_code == 409
    response = client.patch(
        f"/api/v1/{path}/{second['id']}", headers=headers["ADMIN"],
        json={unique_key: payload[unique_key]},
    )
    assert response.status_code == 409
    response = client.patch(
        f"/api/v1/{path}/{first['id']}", headers=headers["ADMIN"], json={"name": "Tên mới"},
    )
    assert response.status_code == 200
    listing = client.get(f"/api/v1/{path}?search=Tên&itemsPerPage=1", headers=headers["STAFF"]).json()
    assert listing["meta"] == {"page": 1, "itemsPerPage": 1, "total": 1, "totalPages": 1}
    assert listing["data"][0]["name"] == "Tên mới"
    assert client.get(f"/api/v1/{path}/99999", headers=headers["STAFF"]).status_code == 404


@pytest.mark.parametrize("resource, field", [("document-types", "document_type_id"), ("issuing-units", "issuing_unit_id")])
def test_inactive_lookup_can_be_preserved_but_not_newly_assigned(client, headers, resource, field):
    lookup = create(client, headers, resource, {"code": "OLD", "name": "Old"}, "ADMIN")
    document = make_document(client, headers, **{field: lookup["id"]})
    changed = client.patch(f"/api/v1/{resource}/{lookup['id']}", headers=headers["ADMIN"], json={"is_active": False})
    assert changed.status_code == 200
    path = f"/api/v1/documents/{document['id']}"
    assert client.patch(path, headers=headers["STAFF"], json={field: lookup["id"], "title": "Kept"}).status_code == 200
    assert client.get(path, headers=headers["STAFF"]).json()["data"][field.removesuffix("_id")]["is_active"] is False
    response = client.post("/api/v1/documents", headers=headers["STAFF"], json={
        "code": "NEW", "title": "New", field: lookup["id"],
    })
    assert response.status_code == 422
    other = make_document(client, headers, "OTHER")
    assert client.patch(f"/api/v1/documents/{other['id']}", headers=headers["STAFF"], json={field: lookup["id"]}).status_code == 422
    assert client.get(f"/api/v1/{resource}?is_active=true", headers=headers["STAFF"]).json()["data"] == []


def test_merged_dates_and_reference_validation_leave_document_unchanged(client, headers):
    document = make_document(client, headers, effective_from="2026-10-01", effective_until="2027-10-01")
    path = f"/api/v1/documents/{document['id']}"
    for payload in (
        {"effective_until": "2026-09-01"}, {"effective_from": "2028-01-01"},
        {"tag_ids": [99999]}, {"document_type_id": 99999}, {"issuing_unit_id": 99999},
    ):
        response = client.patch(path, headers=headers["STAFF"], json={"title": "Invalid change", **payload})
        assert response.status_code == 422, response.text
        assert client.get(path, headers=headers["STAFF"]).json()["data"]["title"] == document["title"]
    response = client.patch(path, headers=headers["STAFF"], json={"effective_from": None, "effective_until": "2026-09-01"})
    assert response.status_code == 200
    assert response.json()["data"]["effective_from"] is None


def test_filters_pagination_and_literal_search(client, headers):
    kind = create(client, headers, "document-types", {"code": "QD", "name": "Quy định"}, "ADMIN")
    unit = create(client, headers, "issuing-units", {"code": "DT", "name": "Đào tạo"}, "ADMIN")
    tags = [create(client, headers, "tags", {"slug": f"tag-{i}", "name": f"Tag {i}"}) for i in range(2)]
    fields = {"document_type_id": kind["id"], "issuing_unit_id": unit["id"], "academic_year": "2026-2027", "tag_ids": [tag["id"] for tag in tags]}
    first = make_document(client, headers, "QD-A", title="Đào tạo 100%", **fields)
    second = make_document(client, headers, "QD-B", title="Đào tạo", **fields)
    make_document(client, headers, "OTHER", title="Khác")
    params = {"search": "đào tạo", "document_type_id": kind["id"], "issuing_unit_id": unit["id"], "academic_year": "2026-2027", "tag_id": tags[0]["id"], "publication_status": "draft", "itemsPerPage": 1}
    response = client.get("/api/v1/documents", headers=headers["STAFF"], params=params)
    assert response.status_code == 200, response.text
    assert response.json()["meta"] == {"page": 1, "itemsPerPage": 1, "total": 2, "totalPages": 2}
    assert response.json()["data"][0]["id"] == second["id"]
    page_two = client.get("/api/v1/documents", headers=headers["STAFF"], params={**params, "page": 2}).json()
    assert page_two["data"][0]["id"] == first["id"]
    assert client.get("/api/v1/documents", headers=headers["STAFF"], params={**params, "page": 3}).json()["data"] == []
    literal = client.get("/api/v1/documents?search=%25", headers=headers["STAFF"]).json()
    assert literal["meta"]["total"] == 1
    assert literal["data"][0]["id"] == first["id"]


def test_unique_constraint_race_rolls_back_document_and_tags(client, headers, db, monkeypatch):
    tag = create(client, headers, "tags", {"name": "Tag", "slug": "tag"})
    make_document(client, headers, "TAKEN")
    document = make_document(client, headers, "EDIT", tag_ids=[tag["id"]])
    # Simulate a concurrent insert after the application-level uniqueness check.
    monkeypatch.setattr(repository, "code_exists", lambda *args, **kwargs: False)
    duplicate = client.post("/api/v1/documents", headers=headers["STAFF"], json={"code": "TAKEN", "title": "Duplicate"})
    assert duplicate.status_code == 409, duplicate.text
    path = f"/api/v1/documents/{document['id']}"
    failed = client.patch(path, headers=headers["STAFF"], json={"code": "TAKEN", "title": "Wrong", "tag_ids": []})
    assert failed.status_code == 409, failed.text
    unchanged = client.get(path, headers=headers["STAFF"]).json()["data"]
    assert unchanged["code"] == "EDIT"
    assert unchanged["title"] == document["title"]
    assert len(unchanged["tags"]) == 1
    assert db.scalar(select(func.count()).select_from(Document)) == 2
    assert client.patch(path, headers=headers["STAFF"], json={"title": "Recovered"}).status_code == 200


def test_replacing_tags_preserves_existing_links(client, headers, db):
    tags = [create(client, headers, "tags", {"name": f"Tag {i}", "slug": f"tag-{i}"}) for i in range(3)]
    document = make_document(client, headers, tag_ids=[tags[0]["id"], tags[1]["id"]])
    kept = db.get(DocumentTag, (document["id"], tags[1]["id"]))
    path = f"/api/v1/documents/{document['id']}"
    response = client.patch(path, headers=headers["STAFF"], json={"tag_ids": [tags[1]["id"], tags[2]["id"]]})
    assert response.status_code == 200
    assert {tag["id"] for tag in response.json()["data"]["tags"]} == {tags[1]["id"], tags[2]["id"]}
    assert db.get(DocumentTag, (document["id"], tags[1]["id"])) is kept


def test_rbac_and_authentication(client, headers, actors):
    routes = [
        ("GET", "documents", None), ("GET", "documents/1", None),
        ("POST", "documents", {"code": "X", "title": "X"}),
        ("PATCH", "documents/1", {"title": "X"}), ("PATCH", "documents/1/archive", None),
    ]
    for resource in ("document-types", "issuing-units", "tags"):
        payload = {"name": "X", "slug" if resource == "tags" else "code": "x"}
        routes.extend([
            ("GET", resource, None), ("GET", f"{resource}/1", None),
            ("POST", resource, payload), ("PATCH", f"{resource}/1", {"name": "X"}),
        ])
    for method, path, payload in routes:
        response = client.request(method, f"/api/v1/{path}", headers=headers["STUDENT"], json=payload)
        assert response.status_code == 403, (method, path, response.text)
    for resource in ("document-types", "issuing-units"):
        assert client.post(f"/api/v1/{resource}", headers=headers["STAFF"], json={"code": "X", "name": "X"}).status_code == 403
        assert client.patch(f"/api/v1/{resource}/1", headers=headers["STAFF"], json={"name": "X"}).status_code == 403
    expired = jwt.encode({"sub": str(actors["STAFF"]), "exp": datetime.now(timezone.utc) - timedelta(minutes=1)}, settings.JWT_SECRET_KEY, algorithm="HS256")
    for auth in ({}, {"Authorization": "Bearer invalid"}, {"Authorization": f"Bearer {expired}"}, headers["INACTIVE"]):
        response = client.get("/api/v1/documents", headers=auth)
        assert response.status_code == 401


def test_api_validation_and_missing_records(client, headers):
    document = make_document(client, headers)
    for fields in ({"title": None}, {"tag_ids": None}, {"publication_status": "published"}, {"created_by": 999}):
        response = client.patch(f"/api/v1/documents/{document['id']}", headers=headers["STAFF"], json=fields)
        assert response.status_code == 422, response.text
        assert response.json()["status_code"] == 422
    invalid_dates = client.post("/api/v1/documents", headers=headers["STAFF"], json={"code": "BAD", "title": "Bad", "effective_from": "2027-01-01", "effective_until": "2026-01-01"})
    assert invalid_dates.status_code == 422
    for query in ("page=0", "itemsPerPage=101", "publication_status=invalid", "unknown=1"):
        assert client.get(f"/api/v1/documents?{query}", headers=headers["STAFF"]).status_code == 422
    assert client.get("/api/v1/documents/99999", headers=headers["STAFF"]).status_code == 404
    assert client.patch("/api/v1/documents/99999", headers=headers["STAFF"], json={}).status_code == 404
    assert client.patch("/api/v1/documents/99999/archive", headers=headers["STAFF"]).status_code == 404
