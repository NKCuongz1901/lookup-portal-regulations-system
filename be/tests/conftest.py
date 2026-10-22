"""Allow model tests to run without a local .env or a database connection."""
import os


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
}.items():
    os.environ.setdefault(name, value)
