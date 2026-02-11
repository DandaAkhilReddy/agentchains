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
    jwt_expire_hours: int = 24 * 7  # 7 days

    # Payments
    payment_mode: str = "simulated"  # simulated | testnet | mainnet
    x402_facilitator_url: str = "https://x402.org/facilitator"
    x402_network: str = "base-sepolia"

    # Azure OpenAI (for agents)
    azure_openai_endpoint: str = ""
    azure_openai_api_key: str = ""
    azure_openai_deployment: str = "gpt-4o"
    azure_openai_api_version: str = "2024-12-01-preview"

    # ARD Token Economy
    token_name: str = "ARD"
    token_peg_usd: float = 0.001  # 1 ARD = $0.001 USD (1000 ARD = $1)
    token_platform_fee_pct: float = 0.02  # 2% fee on transfers
    token_burn_pct: float = 0.50  # 50% of fees burned
    token_signup_bonus: float = 100.0  # Free ARD for new agents
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

    # OpenClaw Integration
    openclaw_webhook_max_retries: int = 3
    openclaw_webhook_timeout_seconds: int = 10
    openclaw_webhook_max_failures: int = 5

    # Creator Economy
    creator_royalty_pct: float = 1.0  # 100% — creator gets all agent earnings
    creator_royalty_mode: str = "full"  # "full" | "percentage"
    creator_min_withdrawal_ard: float = 10000.0  # 10,000 ARD = $10 USD
    creator_payout_day: int = 1  # Day of month for auto-payout

    # Redemption
    redemption_min_api_credits_ard: float = 100.0
    redemption_min_gift_card_ard: float = 1000.0
    redemption_min_bank_ard: float = 10000.0
    redemption_min_upi_ard: float = 5000.0
    redemption_gift_card_margin_pct: float = 0.05  # 5% margin
    razorpay_key_id: str = ""
    razorpay_key_secret: str = ""

    # Rate Limiting
    rest_rate_limit_authenticated: int = 120  # req/min for JWT-authenticated
    rest_rate_limit_anonymous: int = 30  # req/min for unauthenticated

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}


settings = Settings()
