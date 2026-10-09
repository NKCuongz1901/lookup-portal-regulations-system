"""Opt-in PostgreSQL tests. Every test runs in a schema rolled back on exit.

Set TEST_DATABASE_URL to a PostgreSQL SQLAlchemy URL for an account allowed to
create schemas. Existing application tables and data are never modified.
"""
import os
from pathlib import Path
from uuid import uuid4

import pytest
from alembic.config import Config
from alembic.migration import MigrationContext
from alembic.operations import Operations
from alembic.script import ScriptDirectory
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import NullPool

from app.core.database import get_db
from app.core.security import create_access_token
from app.main import app
from app.models import Role, User, UserRole


@pytest.fixture
def db():
    url = os.environ.get("TEST_DATABASE_URL")
    if not url:
        pytest.skip("Set TEST_DATABASE_URL to run PostgreSQL API integration tests")
    engine = create_engine(url, poolclass=NullPool)
    if engine.dialect.name != "postgresql":
        pytest.fail("TEST_DATABASE_URL must use PostgreSQL")
    with engine.connect() as connection:
        transaction = connection.begin()
        try:
            schema = "test_documents_" + uuid4().hex
            connection.exec_driver_sql(f'CREATE SCHEMA "{schema}"')
            connection.exec_driver_sql(f'SET LOCAL search_path TO "{schema}"')
            config = Config()
            config.set_main_option("script_location", str(Path(__file__).resolve().parents[2] / "alembic"))
            scripts = ScriptDirectory.from_config(config)
            with Operations.context(MigrationContext.configure(connection)):
                for revision in reversed(list(scripts.walk_revisions())):
                    revision.module.upgrade()
            with Session(
                connection, autoflush=False, expire_on_commit=False,
                join_transaction_mode="create_savepoint",
            ) as session:
                yield session
        finally:
            transaction.rollback()
            engine.dispose()


@pytest.fixture
def actors(db):
    actors = {}
    for code in ("ADMIN", "STAFF", "STUDENT"):
        role = Role(code=code, name=code)
        user = User(email=f"{code.lower()}@example.com", password_hash="unused", full_name=code)
        db.add_all([role, user])
        db.flush()
        db.add(UserRole(user=user, role=role))
        actors[code] = user.id
    inactive = User(email="inactive@example.com", password_hash="unused", full_name="Inactive", is_active=False)
    db.add(inactive)
    db.commit()
    actors["INACTIVE"] = inactive.id
    return actors


@pytest.fixture
def headers(actors):
    return {
        code: {"Authorization": f"Bearer {create_access_token(user_id)}"}
        for code, user_id in actors.items()
    }


@pytest.fixture
def client(db):
    def test_db():
        yield db

    original = app.dependency_overrides.copy()
    app.dependency_overrides[get_db] = test_db
    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(original)
