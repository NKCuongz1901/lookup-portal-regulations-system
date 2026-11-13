"""Allow model tests to run without a local .env or a database connection."""
import os
from dataclasses import replace

import pytest


for name, value in {
    "DATABASE_NAME": "document_models_test",
    "DATABASE_USERNAME": "document_models_test",
    "DATABASE_PASSWORD": "unused",
    "JWT_SECRET_KEY": "unused-offline-model-test-secret",
    "JWT_ALGORITHM": "HS256",
    "ACCESS_TOKEN_EXPIRE_MINUTES": "30",
    "R2_ACCOUNT_ID": "offline-test-account",
    "R2_ACCESS_KEY_ID": "offline-test-access-key",
    "R2_SECRET_ACCESS_KEY": "offline-test-secret-key",
    "R2_BUCKET_NAME": "offline-test-bucket",
    "R2_ENDPOINT": "https://offline-test-account.r2.cloudflarestorage.com",
    "R2_DOWNLOAD_URL_EXPIRE_SECONDS": "600",
    "CELERY_BROKER_URL": "memory://",
    "CELERY_RESULT_BACKEND": "cache+memory://",
    "GEMINI_API_KEY": "",
}.items():
    os.environ.setdefault(name, value)


@pytest.fixture(autouse=True)
def no_live_gemini_in_tests(monkeypatch):
    from app.modules.extractions import gemini_extractor

    def forbidden(*args, **kwargs):
        pytest.fail("Tests must mock Gemini; live provider calls belong in explicit smoke runs")

    monkeypatch.setattr(gemini_extractor, "_request", forbidden)


@pytest.fixture
def fake_gemini_fields():
    """Stable fixtures for persistence tests, independent of model nondeterminism."""
    from app.modules.extractions.field_extractor import extract_fields
    from app.modules.extractions.gemini_extractor import extraction_version

    def extract(segments, **kwargs):
        result = extract_fields(segments, **kwargs)
        version = extraction_version()
        return replace(result, rule_version=version, candidates=tuple(
            replace(c, rule_version=version, rule_id=f"gemini.{c.field_key}") for c in result.candidates))
    return extract
