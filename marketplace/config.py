from pydantic_settings import BaseSettings
from pathlib import Path


class Settings(BaseSettings):
    # Server
    marketplace_host: str = "0.0.0.0"
    marketplace_port: int = 8000

    # Database
    database_url: str = "sqlite+aiosqlite:///./data/marketplace.db"

    # Content storage
    content_store_path: str = "./data/content_store"

    # Auth
    jwt_secret_key: str = "dev-secret-change-in-production"
    jwt_algorithm: str = "HS256"  # HS256 for dev simplicity, RS256 for production
    jwt_expire_hours: int = 24 * 30  # 30 days

    # Payments
    payment_mode: str = "simulated"  # simulated | testnet | mainnet
    x402_facilitator_url: str = "https://x402.org/facilitator"
    x402_network: str = "base-sepolia"

    # Google ADK
    google_api_key: str = ""

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}


settings = Settings()
