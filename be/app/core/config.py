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
    
    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore"
    )


settings = Settings()