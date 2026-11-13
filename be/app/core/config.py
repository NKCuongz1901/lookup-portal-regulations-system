from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    DATABASE_NAME: str
    DATABASE_USERNAME: str
    DATABASE_PASSWORD: str
    DATABASE_HOST: str = "localhost"
    DATABASE_PORT: int = 5432
    # JWT
    JWT_SECRET_KEY: str
    JWT_ALGORITHM: str
    ACCESS_TOKEN_EXPIRE_MINUTES: int

    # R2
    R2_ACCOUNT_ID: str
    R2_ACCESS_KEY_ID: str
    R2_SECRET_ACCESS_KEY: str
    R2_BUCKET_NAME: str
    R2_ENDPOINT: str
    R2_DOWNLOAD_URL_EXPIRE_SECONDS: int = Field(default=600, ge=1, le=604800)

    # Celery
    CELERY_BROKER_URL: str
    CELERY_RESULT_BACKEND: str

    # Gemini
    GEMINI_API_KEY: SecretStr = Field(default=SecretStr(""), repr=False)
    GEMINI_MODEL: str = Field(default="gemini-3.1-flash-lite", min_length=1, max_length=100, pattern=r"^[a-zA-Z0-9._/-]+$")
    GEMINI_TIMEOUT_SECONDS: int = Field(default=60, ge=5, le=60)
    GEMINI_BATCH_CHARS: int = Field(default=24000, ge=1000, le=60000)
    GEMINI_MAX_BATCHES: int = Field(default=8, ge=1, le=8)

    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore"
    )


settings = Settings()
