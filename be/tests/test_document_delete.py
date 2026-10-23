"""Deletion contract and transaction checks without a database connection."""
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy.dialects.postgresql import dialect

from app.core.database import get_db
from app.main import app
from app.modules.auth.dependencies import get_current_user
from app.modules.documents import repository, services
from app.modules.documents.schemas import DocumentFilter


@pytest.mark.parametrize("role,expected", [("ADMIN", 200), ("STAFF", 200), ("STUDENT", 403)])
def test_delete_route_contract_and_role_gate(monkeypatch, role, expected):
    db = Mock()
    actor = SimpleNamespace(id=42, user_roles=[SimpleNamespace(role=SimpleNamespace(code=role))])
    delete = Mock()
    monkeypatch.setattr(services, "delete_document", delete)
    overrides = app.dependency_overrides.copy()
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_current_user] = lambda: actor
    try:
        with TestClient(app) as client:
            response = client.delete("/api/v1/documents/12")
        assert response.status_code == expected
        if expected == 200:
            assert response.json() == {"message": "Document deleted", "status_code": 200, "data": None, "meta": None}
            delete.assert_called_once_with(db, 12, 42)
        else:
            delete.assert_not_called()
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(overrides)


def test_delete_without_authentication_never_calls_service(monkeypatch):
    delete = Mock()
    monkeypatch.setattr(services, "delete_document", delete)
    overrides = app.dependency_overrides.copy()
    app.dependency_overrides[get_db] = lambda: Mock()
    try:
        with TestClient(app) as client:
            assert client.delete("/api/v1/documents/12").status_code == 401
        delete.assert_not_called()
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(overrides)


def test_delete_locks_record_and_commits_audit_fields_without_removing_rows_or_files(monkeypatch):
    db = Mock()
    document = SimpleNamespace(deleted_at=None, deleted_by=None)
    get_document = Mock(return_value=document)
    storage = Mock()
    monkeypatch.setattr(services, "get_document", get_document)
    monkeypatch.setattr(services, "delete_object", storage)
    services.delete_document(db, 12, 42)
    get_document.assert_called_once_with(db, 12, for_update=True)
    assert document.deleted_at is not None
    assert document.deleted_by == document.updated_by == 42
    db.commit.assert_called_once()
    db.rollback.assert_not_called()
    db.delete.assert_not_called()
    storage.assert_not_called()


@pytest.mark.parametrize("missing", [False, True])
def test_delete_rolls_back_on_missing_record_or_commit_failure(monkeypatch, missing):
    db = Mock()
    if missing:
        monkeypatch.setattr(services, "get_document", Mock(side_effect=HTTPException(404, "Document not found")))
        expected = HTTPException
    else:
        monkeypatch.setattr(services, "get_document", Mock(return_value=SimpleNamespace()))
        db.commit.side_effect = RuntimeError("Commit failed")
        expected = RuntimeError
    with pytest.raises(expected):
        services.delete_document(db, 12, 42)
    db.rollback.assert_called_once()
    if missing:
        db.commit.assert_not_called()


def test_deleted_documents_are_excluded_from_detail_list_and_total_even_when_archived():
    db = Mock()
    db.scalar.return_value = 0
    db.scalars.return_value.all.return_value = []
    repository.get_document(db, 12, for_update=True)
    detail_sql = str(db.scalar.call_args.args[0].compile(dialect=dialect()))
    assert "documents.deleted_at IS NULL" in detail_sql
    assert "FOR UPDATE" in detail_sql
    repository.list_documents(db, DocumentFilter(publication_status="archived", search="QD"))
    count_sql = str(db.scalar.call_args.args[0].compile(dialect=dialect()))
    list_sql = str(db.scalars.call_args.args[0].compile(dialect=dialect()))
    assert "documents.deleted_at IS NULL" in count_sql
    assert "documents.deleted_at IS NULL" in list_sql
