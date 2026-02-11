from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Server
    marketplace_host: str = "0.0.0.0"
    marketplace_port: int = 8000

    # Database (sqlite for local dev, postgresql+asyncpg for Azure)
    database_url: str = "sqlite+aiosqlite:///./data/marketplace.db"

    # Content storage — local HashFS path (used when azure_storage_connection_string is empty)
    content_store_path: str = "./data/content_store"

    # Azure Blob Storage (when set, overrides local HashFS)
    azure_storage_connection_string: str = ""
    azure_storage_container: str = "content-store"

    # Auth
    jwt_secret_key: str = "dev-secret-change-in-production"
    jwt_algorithm: str = "HS256"  # HS256 for dev simplicity, RS256 for production
    jwt_expire_hours: int = 24 * 30  # 30 days

    # Payments
    payment_mode: str = "simulated"  # simulated | testnet | mainnet
    x402_facilitator_url: str = "https://x402.org/facilitator"
    x402_network: str = "base-sepolia"

    # Azure OpenAI (for agents)
    azure_openai_endpoint: str = ""
    azure_openai_api_key: str = ""
    azure_openai_deployment: str = "gpt-4o"
    azure_openai_api_version: str = "2024-12-01-preview"

    # AXN Token Economy
    token_name: str = "AXN"
    token_peg_usd: float = 0.001  # 1 AXN = $0.001 USD (1000 AXN = $1)
    token_platform_fee_pct: float = 0.02  # 2% fee on transfers
    token_burn_pct: float = 0.50  # 50% of fees burned
    token_signup_bonus: float = 100.0  # Free AXN for new agents
    token_quality_bonus_pct: float = 0.10  # +10% bonus for quality > threshold
    token_quality_threshold: float = 0.80  # Min quality for bonus

    # CORS
    cors_origins: str = "*"  # Comma-separated origins, or "*" for all

    # MCP Server
    mcp_enabled: bool = True
    mcp_rate_limit_per_minute: int = 60

    # CDN
    cdn_hot_cache_max_bytes: int = 256 * 1024 * 1024  # 256MB
    cdn_decay_interval_seconds: int = 60

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}


settings = Settings()
