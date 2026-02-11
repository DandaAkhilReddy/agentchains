"""Application configuration using pydantic-settings."""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Database
    database_url: str = ""  # REQUIRED — set via DATABASE_URL env var

    # OpenAI
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"
    openai_embedding_model: str = "text-embedding-3-small"

    # File uploads (local filesystem)
    upload_dir: str = "./uploads"

    # Firebase
    firebase_project_id: str = ""
    firebase_service_account_base64: str = ""  # base64-encoded service account JSON

    # App
    environment: str = "development"
    log_level: str = "INFO"
    cors_origins: str = "http://localhost:5173"  # comma-separated

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()
