"""Application configuration using pydantic-settings."""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Database
    database_url: str = ""  # REQUIRED — set via DATABASE_URL env var

    # Azure OpenAI
    azure_openai_endpoint: str = ""
    azure_openai_key: str = ""
    azure_openai_deployment: str = "gpt-4o-mini"

    # Azure Document Intelligence
    azure_doc_intel_endpoint: str = ""
    azure_doc_intel_key: str = ""

    # Azure Blob Storage
    azure_storage_connection_string: str = ""
    azure_storage_container: str = "loan-documents"

    # Azure Translator
    azure_translator_key: str = ""
    azure_translator_region: str = "centralindia"

    # Azure TTS
    azure_tts_key: str = ""
    azure_tts_region: str = "centralindia"

    # Firebase
    firebase_project_id: str = ""
    firebase_service_account_base64: str = ""  # base64-encoded service account JSON for Azure

    # App
    environment: str = "development"
    log_level: str = "INFO"
    cors_origins: str = "https://app-loan-analyzer-web.azurewebsites.net"  # comma-separated

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()
