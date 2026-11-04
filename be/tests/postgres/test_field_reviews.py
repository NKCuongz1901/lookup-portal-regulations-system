from datetime import datetime, timezone
from uuid import uuid4
from unittest.mock import patch

import pytest
from sqlalchemy import func, select

from app.models import User
from app.modules.extractions import result_service, review_service
from app.modules.extractions.models import FieldReview
from app.modules.extractions.schemas import ReviewCreate
from test_extraction_results import source  # Shared parsed document fixture.


@pytest.fixture
def field(db, source):
    run = result_service.create_run(db, source[1].id)
    result_service.execute_run(db, run.id)
    return result_service.list_fields(db, run.id, 1, 10)[0][0]


def command(action="approve", revision=0, **values):
    return {"action": action, "expected_revision": revision, "idempotency_key": str(uuid4()), **values}


def test_review_lifecycle_preserves_original_and_audits_every_action(client, db, field, headers):
    path = f"/api/v1/extracted-fields/{field.id}/reviews"
    original, normalized = field.raw_value, field.normalized_value.copy()
    quotes = [e.quote for e in field.evidences]
    approved = client.post(path, headers=headers["STAFF"], json=command())
    assert approved.status_code == 200 and approved.json()["data"]["review_status"] == "approved"
    corrected = client.post(path, headers=headers["ADMIN"], json=command("correct", 1, corrected_value="20/12/2026", note="Đã đối chiếu trang gốc"))
    assert corrected.status_code == 200
    data = corrected.json()["data"]
    assert data["review_revision"] == 2 and data["reviewed_value"] == "20/12/2026"
    assert data["raw_value"] == original and data["normalized_value"] == normalized
    assert [e["quote"] for e in data["evidences"]] == quotes
    rejected = client.post(path, headers=headers["STAFF"], json=command("reject", 2, note="Không áp dụng với văn bản này"))
    assert rejected.json()["data"]["review_status"] == "rejected"
    history = client.get(path, headers=headers["STAFF"], params={"page": 1, "itemsPerPage": 2}).json()
    assert history["meta"]["total"] == 3
    assert [item["action"] for item in history["data"]] == ["reject", "correct"]
    correction = history["data"][1]
    assert correction["previous_value"] == original and correction["new_value"] == "20/12/2026"
    assert correction["reviewer_name"] == "ADMIN" and correction["created_at"]
    assert "request_fingerprint" not in correction
    # Extraction retries are immutable even after human review.
    result_service.execute_run(db, field.extraction_run_id)
    assert review_service.get_field(db, field.id).review_revision == 3


def test_same_request_is_idempotent_and_stale_or_reused_keys_conflict(client, db, field, headers):
    path = f"/api/v1/extracted-fields/{field.id}/reviews"
    payload = command()
    assert client.post(path, headers=headers["ADMIN"], json=payload).status_code == 200
    assert client.post(path, headers=headers["ADMIN"], json=payload).status_code == 200
    assert db.scalar(select(func.count()).select_from(FieldReview)) == 1
    assert client.post(path, headers=headers["STAFF"], json=payload).status_code == 409
    assert client.post(path, headers=headers["ADMIN"], json={**payload, "note": "different"}).status_code == 409
    assert client.post(path, headers=headers["ADMIN"], json=command("reject", 0, note="stale")).status_code == 409
    assert review_service.get_field(db, field.id).review_revision == 1


@pytest.mark.parametrize("payload", [
    command("correct", note="missing value"), command("correct", corrected_value="  ", note="reason"),
    command("correct", corrected_value="value"), command("reject"),
    command("approve", corrected_value="value"), command("approve", revision=-1),
    {**command(), "reviewer_id": 99}, {**command(), "action": "publish"},
])
def test_invalid_review_requests_do_not_mutate(client, db, field, headers, payload):
    assert client.post(f"/api/v1/extracted-fields/{field.id}/reviews", headers=headers["STAFF"], json=payload).status_code == 422
    assert db.scalar(select(func.count()).select_from(FieldReview)) == 0


def test_permissions_missing_fields_and_deleted_documents(client, db, source, field, headers):
    path = f"/api/v1/extracted-fields/{field.id}/reviews"
    for verb in (client.get, client.post):
        kwargs = {"json": command()} if verb == client.post else {}
        assert verb(path, **kwargs).status_code in {401, 403}
        assert verb(path, headers=headers["STUDENT"], **kwargs).status_code == 403
        assert verb(path, headers=headers["INACTIVE"], **kwargs).status_code == 401
        assert verb("/api/v1/extracted-fields/999999/reviews", headers=headers["ADMIN"], **kwargs).status_code == 404
    source[0].deleted_at = datetime.now(timezone.utc)
    db.commit()
    assert client.get(path, headers=headers["ADMIN"]).status_code == 404
    assert client.post(path, headers=headers["ADMIN"], json=command()).status_code == 404


def test_commit_failure_rolls_back_field_and_history(db, field, actors):
    actor = db.get(User, actors["ADMIN"])
    with patch.object(db, "commit", side_effect=RuntimeError("transaction failed")):
        with pytest.raises(RuntimeError):
            review_service.review_field(db, field.id, ReviewCreate(**command()), actor)
    restored = review_service.get_field(db, field.id)
    assert restored.review_revision == 0 and restored.review_status == "pending"
    assert db.scalar(select(func.count()).select_from(FieldReview)) == 0


def test_cannot_review_an_incomplete_run(db, field, actors):
    field.run.status = "processing"
    db.commit()
    with pytest.raises(result_service.RunConflictError):
        review_service.review_field(db, field.id, ReviewCreate(**command()), db.get(User, actors["STAFF"]))
