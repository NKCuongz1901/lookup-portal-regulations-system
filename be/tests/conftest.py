"""Allow model tests to run without a local .env or a database connection."""
import os


for name, value in {
    "DATABASE_NAME": "document_models_test",
    "DATABASE_USERNAME": "document_models_test",
    "DATABASE_PASSWORD": "unused",
    "JWT_SECRET_KEY": "unused-offline-model-test-secret",
    "JWT_ALGORITHM": "HS256",
    "ACCESS_TOKEN_EXPIRE_MINUTES": "30",
}.items():
    os.environ.setdefault(name, value)
