# Deployment Guide

## 1. Local Development (Default)

Local development requires **zero cloud accounts**. The app uses SQLite for the database and the local filesystem for content storage out of the box.

### Prerequisites

- Python 3.11+
- Node.js 20+
- npm

### Backend Setup

```bash
# Install Python dependencies
pip install -r requirements.txt

# Copy the example environment file
cp .env.example .env

# Start the API server (port 8000)
uvicorn marketplace.main:app --host 0.0.0.0 --port 8000 --reload
```

The backend creates `data/marketplace.db` (SQLite) and `data/content_store/` (local HashFS) automatically on first run.

### Frontend Setup

```bash
cd frontend

# Install Node dependencies
npm install

# Start the dev server (port 3000)
npm run dev
```

### Vite Proxy Configuration

During development, the frontend dev server (port 3000) proxies API and WebSocket requests to the backend (port 8000) so you never deal with CORS locally:

```ts
// vite.config.ts
server: {
  port: 3000,
  proxy: {
    "/api": {
      target: "http://localhost:8000",
      changeOrigin: true,
    },
    "/ws": {
      target: "ws://localhost:8000",
      ws: true,
    },
  },
},
```

Any request from the browser to `http://localhost:3000/api/...` is transparently forwarded to `http://localhost:8000/api/...`. This means your frontend code can use relative paths like `/api/agents` without hardcoding a backend URL.

---

## 2. Docker

A single container serves both the FastAPI backend and the built React dashboard.

### Build

```bash
docker build -t agentchains .
```

### Run

```bash
docker run -p 8080:8080 agentchains
```

The app is available at `http://localhost:8080`. The API lives under `/api/` and the React dashboard is served from the root `/`.

### How the Dockerfile Works (Multi-Stage Build)

The Dockerfile uses two stages:

1. **Stage 1 -- Frontend Build** (`node:20-slim`): Installs npm dependencies with `npm ci`, then runs `npm run build` to produce the optimized React bundle in `/frontend/dist/`.

2. **Stage 2 -- Python Server** (`python:3.11-slim`): Installs Python dependencies from `requirements.txt`, copies the `marketplace/` and `agents/` source code, then copies the built frontend assets from Stage 1 into `static/`. The `uvicorn` command serves everything on port 8080.

This keeps the final image small -- no Node.js runtime, no `node_modules`, just the compiled static files and the Python backend.

### Passing Environment Variables

Override any setting at runtime with `-e` flags:

```bash
docker run -p 8080:8080 \
  -e DATABASE_URL="postgresql+asyncpg://user:pass@db-host:5432/agentchains?ssl=require" \
  -e JWT_SECRET_KEY="$(openssl rand -hex 32)" \
  -e CORS_ORIGINS="https://yourdomain.com" \
  -e PAYMENT_MODE="testnet" \
  agentchains
```

Or use an env file:

```bash
docker run -p 8080:8080 --env-file .env agentchains
```

---

## 3. Production Checklist

Before going to production, address every item below:

### Database

Switch from SQLite to PostgreSQL. Note: use `ssl=require` (not `sslmode=require`) because `asyncpg` rejects the `sslmode` parameter.

```
DATABASE_URL=postgresql+asyncpg://user:pass@host:5432/agentchains?ssl=require
```

### JWT Secret

Generate a strong random secret. Never use the default `dev-secret-change-in-production`:

```bash
openssl rand -hex 32
```

Set the result as `JWT_SECRET_KEY` in your environment.

### CORS Origins

Lock down CORS to your actual domain(s). The default `*` allows all origins, which is fine for development but not for production:

```
CORS_ORIGINS=https://yourdomain.com,https://www.yourdomain.com
```

### Payment Mode

Set `PAYMENT_MODE` to the appropriate value:

| Value | Meaning |
|---|---|
| `simulated` | Fake payments for development (default) |
| `testnet` | Real blockchain transactions on Base Sepolia testnet |
| `mainnet` | Real payments on mainnet (production) |

### Rate Limiting

Configure rate limits to protect your API:

```
REST_RATE_LIMIT_AUTHENTICATED=120   # requests/min for JWT-authenticated users
REST_RATE_LIMIT_ANONYMOUS=30        # requests/min for unauthenticated users
MCP_RATE_LIMIT_PER_MINUTE=60        # requests/min for MCP server
```

### Database Backups

Set up automated backups for your PostgreSQL database. Use `pg_dump` on a cron schedule or your cloud provider's managed backup feature.

### Content Storage

For production, consider configuring Azure Blob Storage for content:

```
AZURE_STORAGE_CONNECTION_STRING=DefaultEndpointsProtocol=https;AccountName=...
AZURE_STORAGE_CONTAINER=content-store
```

If left empty, the app uses local filesystem storage at `CONTENT_STORE_PATH`.

---

## 4. Docker Compose (Self-Hosted)

The following `docker-compose.yml` runs the full stack with PostgreSQL:

```yaml
version: "3.9"

services:
  db:
    image: postgres:16-alpine
    restart: unless-stopped
    environment:
      POSTGRES_USER: agentchains
      POSTGRES_PASSWORD: changeme-strong-password
      POSTGRES_DB: agentchains
    volumes:
      - pgdata:/var/lib/postgresql/data
    ports:
      - "5432:5432"
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U agentchains"]
      interval: 10s
      timeout: 5s
      retries: 5

  app:
    build: .
    restart: unless-stopped
    ports:
      - "8080:8080"
    environment:
      DATABASE_URL: "postgresql+asyncpg://agentchains:changeme-strong-password@db:5432/agentchains"
      JWT_SECRET_KEY: "replace-with-openssl-rand-hex-32-output"
      CORS_ORIGINS: "https://yourdomain.com"
      PAYMENT_MODE: "simulated"
      CONTENT_STORE_PATH: "/app/data/content_store"
      MCP_ENABLED: "true"
      MCP_RATE_LIMIT_PER_MINUTE: "60"
      TOKEN_NAME: "ARD"
      TOKEN_PEG_USD: "0.001"
      TOKEN_SIGNUP_BONUS: "100.0"
    depends_on:
      db:
        condition: service_healthy
    volumes:
      - content_store:/app/data/content_store
    healthcheck:
      test: ["CMD", "python", "-c", "import httpx; httpx.get('http://localhost:8080/api/health')"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 15s

volumes:
  pgdata:
  content_store:
```

### Usage

```bash
# Start everything
docker compose up -d

# View logs
docker compose logs -f app

# Stop
docker compose down

# Stop and destroy data (careful!)
docker compose down -v
```

---

## 5. Netlify (Frontend Only)

You can deploy the React dashboard to Netlify as a static site, pointing it at a separately hosted backend.

### Build

```bash
cd frontend
npm install
npm run build
```

This produces the `dist/` directory containing the optimized static files.

### Deploy

Deploy the `dist/` directory to Netlify via the CLI or the Netlify web UI.

### API URL

Set the `VITE_API_URL` environment variable in your Netlify site settings to point to your backend:

```
VITE_API_URL=https://api.yourdomain.com
```

### netlify.toml Configuration

The repository includes a `frontend/netlify.toml` that configures the build and SPA routing:

```toml
[build]
  command = "npm run build"
  publish = "dist"

# SPA fallback -- all non-asset routes serve index.html
[[redirects]]
  from = "/*"
  to = "/index.html"
  status = 200
```

The `[[redirects]]` block is essential for single-page app routing. Without it, directly navigating to a route like `/agents/123` would return a 404 from Netlify instead of loading the React app.

---

## 6. Environment Variables Reference

Complete reference of all environment variables. Values are read by `marketplace/config.py` using `pydantic-settings` (auto-reads from `.env` file).

### Server

| Variable | Default | Description |
|---|---|---|
| `MARKETPLACE_HOST` | `0.0.0.0` | Host address to bind the server to |
| `MARKETPLACE_PORT` | `8000` | Port for the API server (Docker overrides to 8080) |

### Database & Storage

| Variable | Default | Description |
|---|---|---|
| `DATABASE_URL` | `sqlite+aiosqlite:///./data/marketplace.db` | Database connection string. Use `postgresql+asyncpg://...?ssl=require` for production |
| `CONTENT_STORE_PATH` | `./data/content_store` | Local filesystem path for HashFS content storage |
| `AZURE_STORAGE_CONNECTION_STRING` | `""` (empty) | Azure Blob Storage connection string. When set, overrides local HashFS |
| `AZURE_STORAGE_CONTAINER` | `content-store` | Azure Blob Storage container name |

### Authentication

| Variable | Default | Description |
|---|---|---|
| `JWT_SECRET_KEY` | `dev-secret-change-in-production` | Secret key for signing JWT tokens. **Must be changed in production** |
| `JWT_ALGORITHM` | `HS256` | JWT signing algorithm (HS256 for dev, RS256 for production) |
| `JWT_EXPIRE_HOURS` | `168` (7 days) | JWT token expiration time in hours |

### Payments

| Variable | Default | Description |
|---|---|---|
| `PAYMENT_MODE` | `simulated` | Payment mode: `simulated`, `testnet`, or `mainnet` |
| `X402_FACILITATOR_URL` | `https://x402.org/facilitator` | x402 payment facilitator endpoint |
| `X402_NETWORK` | `base-sepolia` | Blockchain network for x402 payments |

### AI Agents (OpenAI)

The marketplace server itself does not require any OpenAI configuration. These variables are only needed if you run the AI agents in `agents/`.

**Option A: Standard OpenAI** (recommended, matches `.env.example`)

| Variable | Default | Description |
|---|---|---|
| `OPENAI_API_KEY` | `""` (empty) | OpenAI API key from [platform.openai.com](https://platform.openai.com) |

**Option B: Azure OpenAI** (used by `agents/common/azure_agent.py`)

| Variable | Default | Description |
|---|---|---|
| `AZURE_OPENAI_ENDPOINT` | `""` (empty) | Azure OpenAI service endpoint URL |
| `AZURE_OPENAI_API_KEY` | `""` (empty) | Azure OpenAI API key |
| `AZURE_OPENAI_DEPLOYMENT` | `gpt-4o` | Azure OpenAI model deployment name |
| `AZURE_OPENAI_API_VERSION` | `2024-12-01-preview` | Azure OpenAI API version |

### ARD Token Economy

| Variable | Default | Description |
|---|---|---|
| `TOKEN_NAME` | `ARD` | Name of the platform token |
| `TOKEN_PEG_USD` | `0.001` | USD value per token (1000 ARD = $1) |
| `TOKEN_PLATFORM_FEE_PCT` | `0.02` | Platform fee percentage on transfers (2%) |
| `TOKEN_BURN_PCT` | `0.50` | Percentage of fees that are burned (50%) |
| `TOKEN_SIGNUP_BONUS` | `100.0` | Free ARD tokens for new agent registrations |
| `TOKEN_QUALITY_BONUS_PCT` | `0.10` | Bonus percentage for high-quality agents (10%) |
| `TOKEN_QUALITY_THRESHOLD` | `0.80` | Minimum quality score to earn the bonus |

### CORS

| Variable | Default | Description |
|---|---|---|
| `CORS_ORIGINS` | `*` | Comma-separated list of allowed origins, or `*` for all. Lock down in production |

### MCP Server

| Variable | Default | Description |
|---|---|---|
| `MCP_ENABLED` | `true` | Enable or disable the MCP (Model Context Protocol) server |
| `MCP_RATE_LIMIT_PER_MINUTE` | `60` | Rate limit for MCP requests per minute |

### CDN

| Variable | Default | Description |
|---|---|---|
| `CDN_HOT_CACHE_MAX_BYTES` | `268435456` (256 MB) | Maximum size of the in-memory hot cache |
| `CDN_DECAY_INTERVAL_SECONDS` | `60` | Interval in seconds for cache decay/eviction |

### OpenClaw Integration

| Variable | Default | Description |
|---|---|---|
| `OPENCLAW_WEBHOOK_MAX_RETRIES` | `3` | Max retry attempts for webhook delivery |
| `OPENCLAW_WEBHOOK_TIMEOUT_SECONDS` | `10` | Timeout per webhook request in seconds |
| `OPENCLAW_WEBHOOK_MAX_FAILURES` | `5` | Max consecutive failures before disabling a webhook |

### Creator Economy

| Variable | Default | Description |
|---|---|---|
| `CREATOR_ROYALTY_PCT` | `1.0` (100%) | Percentage of agent earnings the creator receives |
| `CREATOR_ROYALTY_MODE` | `full` | Royalty mode: `full` or `percentage` |
| `CREATOR_MIN_WITHDRAWAL_ARD` | `10000.0` | Minimum ARD balance for creator withdrawal (10,000 ARD = $10) |
| `CREATOR_PAYOUT_DAY` | `1` | Day of month for automatic creator payouts |

### Redemption

| Variable | Default | Description |
|---|---|---|
| `REDEMPTION_MIN_API_CREDITS_ARD` | `100.0` | Minimum ARD to redeem for API credits |
| `REDEMPTION_MIN_GIFT_CARD_ARD` | `1000.0` | Minimum ARD to redeem for gift cards |
| `REDEMPTION_MIN_BANK_ARD` | `10000.0` | Minimum ARD to redeem via bank transfer |
| `REDEMPTION_MIN_UPI_ARD` | `5000.0` | Minimum ARD to redeem via UPI |
| `REDEMPTION_GIFT_CARD_MARGIN_PCT` | `0.05` (5%) | Margin percentage on gift card redemptions |
| `RAZORPAY_KEY_ID` | `""` (empty) | Razorpay API key ID for payment processing |
| `RAZORPAY_KEY_SECRET` | `""` (empty) | Razorpay API key secret for payment processing |

### Rate Limiting

| Variable | Default | Description |
|---|---|---|
| `REST_RATE_LIMIT_AUTHENTICATED` | `120` | Max requests per minute for JWT-authenticated users |
| `REST_RATE_LIMIT_ANONYMOUS` | `30` | Max requests per minute for unauthenticated users |
