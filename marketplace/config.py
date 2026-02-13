import logging
import warnings

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Server
    marketplace_host: str = "0.0.0.0"
    marketplace_port: int = 8000

    # Database (sqlite for local dev, postgresql+asyncpg for production)
    database_url: str = "sqlite+aiosqlite:///./data/marketplace.db"

    # Content storage — local HashFS path
    content_store_path: str = "./data/content_store"

    # Auth
    jwt_secret_key: str = "dev-secret-change-in-production"
    jwt_algorithm: str = "HS256"
    admin_creator_ids: str = ""  # Comma-separated creator IDs with admin access
    jwt_expire_hours: int = 24 * 7  # 7 days

    # Payments
    payment_mode: str = "simulated"  # simulated | testnet | mainnet
    x402_facilitator_url: str = "https://x402.org/facilitator"
    x402_network: str = "base-sepolia"

    # OpenAI (for AI agents)
    openai_api_key: str = ""
    openai_model: str = "gpt-4o"

    # Billing
    platform_fee_pct: float = 0.02  # 2% fee on purchases
    signup_bonus_usd: float = 0.10  # $0.10 welcome credit for new agents

    # CORS
    cors_origins: str = "http://localhost:5173,http://localhost:3000"

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
    creator_min_withdrawal_usd: float = 10.00  # Minimum $10 USD for withdrawal
    creator_payout_day: int = 1  # Day of month for auto-payout

    # Redemption
    redemption_min_api_credits_usd: float = 0.10
    redemption_min_gift_card_usd: float = 1.00
    redemption_min_bank_usd: float = 10.00
    redemption_min_upi_usd: float = 5.00
    redemption_gift_card_margin_pct: float = 0.05  # 5% margin
    razorpay_key_id: str = ""
    razorpay_key_secret: str = ""

    # Rate Limiting
    rest_rate_limit_authenticated: int = 120  # req/min for JWT-authenticated
    rest_rate_limit_anonymous: int = 30  # req/min for unauthenticated

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}


settings = Settings()

# Warn on insecure defaults (logged at startup, not a hard error for dev convenience)
_logger = logging.getLogger("marketplace.config")
_INSECURE_SECRETS = {"dev-secret-change-in-production", "change-me-to-a-random-string", "change-me-to-a-random-64-char-string"}
if settings.jwt_secret_key in _INSECURE_SECRETS:
    if "postgresql" in settings.database_url or "postgres" in settings.database_url:
        raise RuntimeError(
            "FATAL: JWT_SECRET_KEY is set to an insecure default. "
            "Set a strong random secret via the JWT_SECRET_KEY environment variable before deploying to production."
        )
    warnings.warn(
        "JWT_SECRET_KEY is set to the default insecure value. "
        "Set a strong random secret via the JWT_SECRET_KEY environment variable for production.",
        stacklevel=1,
    )
if settings.cors_origins == "*":
    _logger.warning(
        "CORS_ORIGINS is set to '*' (allow all). "
        "Configure specific origins for production via the CORS_ORIGINS environment variable."
    )
