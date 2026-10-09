import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.main import app
from app.modules.document_metadata.schemas import DocumentTypeUpdate, IssuingUnitUpdate, TagCreate, TagUpdate
from app.modules.documents.schemas import DocumentCreate, DocumentFilter, DocumentUpdate


def test_create_normalizes_text_and_deduplicates_collections():
    payload = DocumentCreate(
        code=" QD-01 ", title=" Quy định ", tag_ids=[1, 1, 2],
        applicable_subject_codes=[" STUDENT ", "STUDENT", "STAFF"],
    )
    assert payload.code == "QD-01"
    assert payload.title == "Quy định"
    assert payload.tag_ids == [1, 2]
    assert payload.applicable_subject_codes == ["STUDENT", "STAFF"]


@pytest.mark.parametrize("fields", [
    {"title": " "}, {"code": "x" * 101}, {"tag_ids": [0]},
    {"applicable_subject_codes": [" "]},
    {"effective_from": "2026-10-01", "effective_until": "2026-09-01"},
])
def test_invalid_document_creation(fields):
    with pytest.raises(ValidationError):
        DocumentCreate.model_validate({"code": "QD-01", "title": "Quy định", **fields})


@pytest.mark.parametrize("field, value", [
    ("created_by", 1), ("updated_by", 1), ("publication_status", "published"),
    ("published_at", "2026-10-01T00:00:00Z"), ("created_at", "2026-10-01T00:00:00Z"),
])
def test_audit_and_publication_fields_are_read_only(field, value):
    for schema, base in ((DocumentCreate, {"code": "QD-01", "title": "Title"}), (DocumentUpdate, {})):
        with pytest.raises(ValidationError):
            schema.model_validate({**base, field: value})


@pytest.mark.parametrize("schema, field", [
    (DocumentUpdate, "code"), (DocumentUpdate, "title"),
    (DocumentUpdate, "tag_ids"), (DocumentUpdate, "applicable_subject_codes"),
    (DocumentTypeUpdate, "code"), (DocumentTypeUpdate, "name"),
    (DocumentTypeUpdate, "is_active"), (IssuingUnitUpdate, "name"),
    (TagUpdate, "name"), (TagUpdate, "slug"),
])
def test_required_fields_cannot_be_explicitly_cleared(schema, field):
    assert schema().model_dump(exclude_unset=True) == {}
    with pytest.raises(ValidationError):
        schema.model_validate({field: None})


def test_patch_distinguishes_omitted_null_and_empty_list():
    payload = DocumentUpdate(description=None, document_type_id=None, tag_ids=[])
    assert payload.model_dump(exclude_unset=True) == {
        "description": None, "document_type_id": None, "tag_ids": [],
    }


@pytest.mark.parametrize("filters", [{"page": 0}, {"itemsPerPage": 101}, {"tag_id": -1}, {"publication_status": "invalid"}])
def test_invalid_filters(filters):
    with pytest.raises(ValidationError):
        DocumentFilter.model_validate(filters)


@pytest.mark.parametrize("slug", ["Đào tạo", "UPPERCASE", "two words", "--", ""])
def test_tag_slug_is_url_friendly(slug):
    with pytest.raises(ValidationError):
        TagCreate(name="Đào tạo", slug=slug)


def test_openapi_exposes_filters_and_protected_requests():
    schema = app.openapi()
    endpoint = schema["paths"]["/api/v1/documents"]["get"]
    assert {parameter["name"] for parameter in endpoint["parameters"]} == {
        "page", "itemsPerPage", "search", "document_type_id", "issuing_unit_id",
        "academic_year", "tag_id", "publication_status",
    }
    assert endpoint["security"]
    assert "publication_status" not in schema["components"]["schemas"]["DocumentUpdate"]["properties"]


def test_management_endpoints_require_authentication_without_accessing_database():
    with TestClient(app) as client:
        for path in ("documents", "document-types", "issuing-units", "tags"):
            response = client.get(f"/api/v1/{path}")
            assert response.status_code == 401
            assert response.json()["status_code"] == 401
