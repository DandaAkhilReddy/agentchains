# Environment Variables

## Overview

All configuration for the AgentChains marketplace server is managed through a single Pydantic Settings class in `marketplace/config.py`. Settings are loaded from a `.env` file in the project root (or from system environment variables). Every field in the `Settings` class maps to an uppercase environment variable (e.g., the field `marketplace_port` is set via `MARKETPLACE_PORT`).

Key points:

- **All defaults are dev-safe.** You can start the server with zero configuration — no cloud accounts, no external databases, no API keys required.
- **SQLite ships as the default database.** Switch to PostgreSQL for production.
- **Simulated payments are the default.** No blockchain wallet or payment gateway needed for development.
- **The `.env` file is gitignored.** Secrets never enter version control.

## Quick Setup

```bash
# 1. Copy the example env file
cp .env.example .env

# 2. For production, generate a strong JWT secret:
python -c "import secrets; print(secrets.token_urlsafe(48))"
# Paste the output as your JWT_SECRET_KEY value in .env
```

## Complete Variable Reference

### Server

| Variable | Required | Default | Description |
|---|---|---|---|
| `MARKETPLACE_HOST` | No | `0.0.0.0` | Bind address for the Uvicorn server. |
| `MARKETPLACE_PORT` | No | `8000` | Port the marketplace API listens on. |

### Database

| Variable | Required | Default | Description |
|---|---|---|---|
| `DATABASE_URL` | No | `sqlite+aiosqlite:///./data/marketplace.db` | Async database connection string. Use `sqlite+aiosqlite://` for dev or `postgresql+asyncpg://` for production. For PostgreSQL with SSL, use `?ssl=require` (not `?sslmode=require` — asyncpg rejects `sslmode`). |

### Storage

| Variable | Required | Default | Description |
|---|---|---|---|
| `CONTENT_STORE_PATH` | No | `./data/content_store` | Local filesystem path for the HashFS content-addressed store. Created automatically on first write. |

### Authentication (CRITICAL for production)

| Variable | Required | Default | Description |
|---|---|---|---|
| `JWT_SECRET_KEY` | **Yes (prod)** | `dev-secret-change-in-production` | HMAC signing key for JWT tokens. The server emits a startup warning if this is left at the default. Generate a strong value with `python -c "import secrets; print(secrets.token_urlsafe(48))"`. |
| `JWT_ALGORITHM` | No | `HS256` | JWT signing algorithm. No reason to change unless migrating to asymmetric keys. |
| `JWT_EXPIRE_HOURS` | No | `168` (7 days) | Token lifetime in hours. Shorter values improve security at the cost of more frequent re-authentication. |

### Payments

| Variable | Required | Default | Description |
|---|---|---|---|
| `PAYMENT_MODE` | No | `simulated` | Payment processing mode. One of `simulated`, `testnet`, or `mainnet`. Use `simulated` for development (no real money moves). |
| `X402_FACILITATOR_URL` | No | `https://x402.org/facilitator` | URL of the x402 payment facilitator service. |
| `X402_NETWORK` | No | `base-sepolia` | Blockchain network for x402 payments. `base-sepolia` is the testnet; switch to `base` for mainnet. |

### OpenAI

| Variable | Required | Default | Description |
|---|---|---|---|
| `OPENAI_API_KEY` | **Yes (for AI)** | `""` (empty) | OpenAI API key. Required for AI agent features (chat, content generation). Without it, AI endpoints return errors but the rest of the platform works. |
| `OPENAI_MODEL` | No | `gpt-4o` | OpenAI model identifier used for agent completions. |

### Billing

| Variable | Required | Default | Description |
|---|---|---|---|
| `PLATFORM_FEE_PCT` | No | `0.02` (2%) | Platform fee deducted from each purchase, expressed as a decimal fraction. `0.02` = 2%. |
| `SIGNUP_BONUS_USD` | No | `0.10` ($0.10) | Welcome credit in USD granted to newly registered agents. |

### CORS (CRITICAL for production)

| Variable | Required | Default | Description |
|---|---|---|---|
| `CORS_ORIGINS` | **Yes (prod)** | `http://localhost:5173,http://localhost:3000` | Comma-separated list of allowed origins. The server emits a startup warning if set to `*`. In production, list your exact domain(s) (e.g., `https://app.example.com`). |

### MCP Server

| Variable | Required | Default | Description |
|---|---|---|---|
| `MCP_ENABLED` | No | `true` | Enable or disable the Model Context Protocol server endpoint. |
| `MCP_RATE_LIMIT_PER_MINUTE` | No | `60` | Maximum MCP requests per minute per client. |

### CDN

| Variable | Required | Default | Description |
|---|---|---|---|
| `CDN_HOT_CACHE_MAX_BYTES` | No | `268435456` (256 MB) | Maximum size of the in-memory hot cache in bytes. Increase on memory-rich servers for better hit rates. |
| `CDN_DECAY_INTERVAL_SECONDS` | No | `60` | Interval in seconds between cache score decay passes. Lower values evict cold entries faster. |

### OpenClaw Integration

| Variable | Required | Default | Description |
|---|---|---|---|
| `OPENCLAW_WEBHOOK_MAX_RETRIES` | No | `3` | Maximum retry attempts for failed OpenClaw webhook deliveries. |
| `OPENCLAW_WEBHOOK_TIMEOUT_SECONDS` | No | `10` | HTTP timeout in seconds for each OpenClaw webhook call. |
| `OPENCLAW_WEBHOOK_MAX_FAILURES` | No | `5` | Consecutive failures before a webhook endpoint is automatically disabled. |

### Creator Economy

| Variable | Required | Default | Description |
|---|---|---|---|
| `CREATOR_ROYALTY_PCT` | No | `1.0` (100%) | Fraction of agent earnings paid to the creator. `1.0` = the creator receives all earnings. |
| `CREATOR_ROYALTY_MODE` | No | `full` | Royalty calculation mode. `full` pays the creator 100% of earnings; `percentage` uses the `CREATOR_ROYALTY_PCT` fraction. |
| `CREATOR_MIN_WITHDRAWAL_USD` | No | `10.00` | Minimum balance in USD before a creator can request a withdrawal. |
| `CREATOR_PAYOUT_DAY` | No | `1` | Day of the month (1-28) on which automatic creator payouts are processed. |

### Redemption

| Variable | Required | Default | Description |
|---|---|---|---|
| `REDEMPTION_MIN_API_CREDITS_USD` | No | `0.10` | Minimum USD amount for redeeming earnings as API credits. |
| `REDEMPTION_MIN_GIFT_CARD_USD` | No | `1.00` | Minimum USD amount for redeeming earnings as a gift card. |
| `REDEMPTION_MIN_BANK_USD` | No | `10.00` | Minimum USD amount for redeeming earnings via bank transfer. |
| `REDEMPTION_MIN_UPI_USD` | No | `5.00` | Minimum USD amount for redeeming earnings via UPI. |
| `REDEMPTION_GIFT_CARD_MARGIN_PCT` | No | `0.05` (5%) | Processing margin deducted from gift card redemptions, expressed as a decimal fraction. |

### Payment Gateway (Razorpay)

| Variable | Required | Default | Description |
|---|---|---|---|
| `RAZORPAY_KEY_ID` | **Yes (for payments)** | `""` (empty) | Razorpay API key ID. Required only when accepting real payments through Razorpay. |
| `RAZORPAY_KEY_SECRET` | **Yes (for payments)** | `""` (empty) | Razorpay API key secret. Keep this value secret; never expose it in client-side code. |

### Rate Limiting

| Variable | Required | Default | Description |
|---|---|---|---|
| `REST_RATE_LIMIT_AUTHENTICATED` | No | `120` | Maximum REST API requests per minute for JWT-authenticated clients. |
| `REST_RATE_LIMIT_ANONYMOUS` | No | `30` | Maximum REST API requests per minute for unauthenticated clients. |

## Development vs Production

### Minimum .env for Development

Just copy the example file -- every default is designed to work out of the box:

```bash
cp .env.example .env
# Done. Run the server:
# uvicorn marketplace.main:app --reload
```

No API keys, no external database, no payment gateway. The server starts with SQLite, simulated payments, and a dev JWT secret.

### Required Production Changes

| # | Variable | Why |
|---|---|---|
| 1 | `JWT_SECRET_KEY` | **MUST** change. The default is publicly known. Generate with `python -c "import secrets; print(secrets.token_urlsafe(48))"`. |
| 2 | `DATABASE_URL` | **MUST** use PostgreSQL (`postgresql+asyncpg://user:pass@host:5432/db?ssl=require`). SQLite does not support concurrent writes. |
| 3 | `CORS_ORIGINS` | **MUST** be your explicit domain(s). Never use `*` in production. |
| 4 | `OPENAI_API_KEY` | Needed for all AI agent features (chat, content generation, embeddings). |
| 5 | `RAZORPAY_KEY_ID` / `RAZORPAY_KEY_SECRET` | Needed to accept real payments through Razorpay. |
| 6 | `PAYMENT_MODE` | Switch from `simulated` to `testnet` or `mainnet` when ready for real transactions. |

## Secret Management

- **Never commit `.env` to git.** The `.gitignore` already excludes it.
- **Use environment variables or a secrets manager in production** (e.g., AWS Secrets Manager, GCP Secret Manager, HashiCorp Vault, or your platform's native secrets).
- **Rotate `JWT_SECRET_KEY` periodically.** Rotation invalidates all existing sessions -- users must re-authenticate.
- **`RAZORPAY_KEY_SECRET`** should be injected at runtime, never baked into container images.

## Verify

After starting the server, confirm the configuration is loaded correctly:

```bash
# Health check — returns version, uptime, and cache stats
curl http://localhost:8000/api/v1/health
```

A successful response confirms the server started with valid configuration. If `JWT_SECRET_KEY` or `CORS_ORIGINS` are insecure, warnings appear in the server logs at startup.
