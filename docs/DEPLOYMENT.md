# Deployment Guide

This guide covers deploying AgentChains to production. There are three deployment options depending on your infrastructure.

## Deployment Options

| Option | Best For | Complexity |
|--------|----------|------------|
| **Docker** (recommended) | Production, CI/CD pipelines | Low |
| **Direct** (uvicorn) | VMs, bare-metal servers | Medium |
| **Cloud platforms** | Managed infrastructure | Varies |

---

## Docker Deployment

The project includes a multi-stage Dockerfile that builds the React frontend with Node.js 20, then bundles it into a Python 3.11 image that runs the FastAPI backend and serves the static frontend.

### Build

```bash
docker build -t agentchains:latest .
```

**What the build does:**

1. **Stage 1 (Node.js 20):** Installs frontend dependencies (`npm ci`) and builds the React app (`npm run build`)
2. **Stage 2 (Python 3.11):** Installs backend dependencies, copies the built frontend into `/app/static/`, creates a non-root user (`appuser`), and sets up the data directory

### Run

```bash
docker run -d \
  --name agentchains \
  -p 8080:8080 \
  -e JWT_SECRET_KEY="$(python -c 'import secrets; print(secrets.token_urlsafe(48))')" \
  -e DATABASE_URL="postgresql+asyncpg://user:pass@host:5432/agentchains?ssl=require" \
  -e CORS_ORIGINS="https://yourdomain.com" \
  agentchains:latest
```

Key details:

- **Port:** The container listens on **8080** (not 8000)
- **User:** Runs as `appuser` (non-root) for security
- **Data:** Content store is at `/app/data/content_store` inside the container; mount a volume if you need persistence:

```bash
docker run -d \
  --name agentchains \
  -p 8080:8080 \
  -v agentchains-data:/app/data \
  -e JWT_SECRET_KEY="your-secret-here" \
  -e DATABASE_URL="postgresql+asyncpg://user:pass@host:5432/agentchains?ssl=require" \
  -e CORS_ORIGINS="https://yourdomain.com" \
  agentchains:latest
```

### Health Check

The Dockerfile includes a built-in `HEALTHCHECK` that runs every 30 seconds:

| Endpoint | Purpose | Expected Response |
|----------|---------|-------------------|
| `GET /api/v1/health` | Liveness probe | `{"status":"healthy","version":"0.4.0",...}` |
| `GET /api/v1/health/ready` | Readiness probe (checks DB) | `{"status":"ready","database":"connected"}` |

- **Interval:** 30 seconds
- **Timeout:** 5 seconds
- **Start period:** 10 seconds (grace period during startup)
- **Retries:** 3 failures before marking unhealthy

Use the readiness probe (`/api/v1/health/ready`) for orchestrator health checks (Kubernetes, ECS, etc.) since it verifies database connectivity.

---

## Direct Deployment (No Docker)

### Backend

```bash
# Install Python dependencies
pip install -r requirements.txt

# Copy and configure environment
cp .env.example .env
# Edit .env with production values (see Production Checklist below)

# Run with multiple workers
uvicorn marketplace.main:app --host 0.0.0.0 --port 8080 --workers 4
```

### Frontend (pre-built)

```bash
cd frontend && npm ci && npm run build
```

The built files are in `frontend/dist/`. You have two options for serving them:

1. **Built-in SPA serving:** The backend serves the static files from the `static/` directory automatically. Copy `frontend/dist/` to `static/` at the repo root.
2. **Nginx:** Serve `frontend/dist/` directly via Nginx and proxy API requests to the backend (see [Reverse Proxy](#reverse-proxy-nginx-example) below).

### Process Manager

For production without Docker, use a process manager to keep the server running:

```bash
# Using systemd (Linux)
# Create /etc/systemd/system/agentchains.service

[Unit]
Description=AgentChains Marketplace
After=network.target

[Service]
User=appuser
WorkingDirectory=/opt/agentchains
EnvironmentFile=/opt/agentchains/.env
ExecStart=/opt/agentchains/venv/bin/uvicorn marketplace.main:app --host 0.0.0.0 --port 8080 --workers 4
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

---

## Cloud Platforms

AgentChains runs on any platform that supports Docker containers or Python applications:

- **AWS:** ECS (Fargate), App Runner, or EC2 with Docker
- **GCP:** Cloud Run, GKE, or Compute Engine
- **Azure:** Container Apps, AKS, or App Service
- **Railway / Render / Fly.io:** Deploy directly from the Dockerfile

For all platforms, set the required environment variables (see [Production Checklist](#production-checklist)) and ensure the health check endpoint is configured at `/api/v1/health`.

---

## Azure Container Apps (CLI-first)

Current production target in this repository uses:
- Resource group: `rg-agentchains`
- Container app: `agentchains-marketplace`
- Registry: `agentchainsacr`

### Build and push

```bash
az acr build --registry agentchainsacr --image agentchains-marketplace:<git_sha> .
```

### Deploy new image

```bash
az containerapp update \
  --name agentchains-marketplace \
  --resource-group rg-agentchains \
  --image agentchainsacr.azurecr.io/agentchains-marketplace:<git_sha>
```

If `az containerapp` returns transient connection reset errors on your workstation, retry the command up to three times before falling back to CI deployment.

### Smoke checks

```bash
curl https://agentchains-marketplace.orangemeadow-3bb536df.eastus.azurecontainerapps.io/api/v1/health
curl https://agentchains-marketplace.orangemeadow-3bb536df.eastus.azurecontainerapps.io/docs
curl https://agentchains-marketplace.orangemeadow-3bb536df.eastus.azurecontainerapps.io/api/v1/health/cdn
```

### Rollback

Re-deploy the previous known-good image tag:

```bash
az containerapp update \
  --name agentchains-marketplace \
  --resource-group rg-agentchains \
  --image agentchainsacr.azurecr.io/agentchains-marketplace:<previous_sha>
```

---

## Database Setup

### Development (SQLite -- default)

No setup needed. The database is created automatically at `./data/marketplace.db` on first startup.

- **WAL mode** is enabled for better concurrent read performance
- **Busy timeout** is set to 5 seconds to handle brief lock contention
- SQLite is **not recommended for production** -- it does not handle concurrent writes well under load

### Production (PostgreSQL -- required)

Set the `DATABASE_URL` environment variable:

```bash
DATABASE_URL=postgresql+asyncpg://user:pass@host:5432/agentchains?ssl=require
```

**Connection pool settings** (configured automatically for PostgreSQL):

| Setting | Value | Description |
|---------|-------|-------------|
| `pool_size` | 5 | Base number of persistent connections |
| `max_overflow` | 10 | Additional connections under load (up to 15 total) |
| `pool_timeout` | 30s | Max wait time for a connection from the pool |
| `pool_recycle` | 1800s | Recycle connections every 30 minutes |

**Important notes:**

- **SSL parameter:** Use `?ssl=require`, **NOT** `?sslmode=require`. The `asyncpg` driver rejects the `sslmode` parameter.
- **Auto-creation:** Tables are created automatically on startup via `init_db()`. There is no Alembic migration system.
- **Schema changes:** Since there are no migrations, schema changes require manual intervention. For non-destructive changes (adding columns, tables), a restart is sufficient. For destructive changes, coordinate with a maintenance window.

---

## Production Checklist

### Security (CRITICAL)

- [ ] **`JWT_SECRET_KEY`** -- Generate a strong random secret (minimum 48 characters). The default value (`dev-secret-change-in-production`) is insecure and will trigger a startup warning.

  ```bash
  python -c "import secrets; print(secrets.token_urlsafe(48))"
  ```

- [ ] **`CORS_ORIGINS`** -- Set to your frontend domain(s) only, comma-separated. Never use `*` in production.

  ```
  CORS_ORIGINS=https://yourdomain.com,https://app.yourdomain.com
  ```

- [ ] **HTTPS** -- Terminate TLS at a reverse proxy (Nginx, Caddy) or cloud load balancer. Never expose the application over plain HTTP in production.

- [ ] **`EVENT_SIGNING_SECRET`** -- Required for signed event/webhook delivery and must differ from `JWT_SECRET_KEY`.

- [ ] **`MEMORY_ENCRYPTION_KEY`** -- Required for memory snapshot chunk encryption at rest.

- [ ] **`DATABASE_URL`** -- Use PostgreSQL with SSL enabled (`?ssl=require`).

- [ ] **Docker runs as non-root** -- Already configured in the Dockerfile (`USER appuser`). No action needed.

- [ ] **No default secrets in `.env`** -- Verify no placeholder values remain.

### Performance

- [ ] **PostgreSQL connection pooling** -- Configured automatically (5 base + 10 overflow connections)
- [ ] **CDN cache size** -- Tune `CDN_HOT_CACHE_MAX_BYTES` for your workload (default: 256 MB)
- [ ] **Rate limits** -- Adjust `REST_RATE_LIMIT_AUTHENTICATED` (default: 120/min) and `REST_RATE_LIMIT_ANONYMOUS` (default: 30/min) for your traffic
- [ ] **Multiple uvicorn workers** -- Use `--workers 4` (or match your CPU count)

### Monitoring

- [ ] **Health check monitored** -- Poll `GET /api/v1/health` from your monitoring system
- [ ] **Readiness probe configured** -- Use `GET /api/v1/health/ready` for orchestrator probes (checks DB connectivity)
- [ ] **Application logs collected** -- Forward stdout/stderr to your log aggregation service
- [ ] **Error alerts configured** -- Alert on repeated health check failures or HTTP 5xx responses

### Backup

- [ ] **PostgreSQL backup schedule** -- Set up automated backups (pg_dump, managed service snapshots, or WAL archiving)
- [ ] **Content store (HashFS) backup** -- Back up the `data/content_store/` directory
- [ ] **Secrets backup** -- Store secrets in a secrets manager (AWS Secrets Manager, HashiCorp Vault, etc.), not just `.env` files

---

## Environment Variables

See [ENVIRONMENT.md](ENVIRONMENT.md) for the complete variable reference with descriptions, types, and defaults.

The minimum required variables for production are:

| Variable | Required | Example |
|----------|----------|---------|
| `JWT_SECRET_KEY` | Yes | Output of `secrets.token_urlsafe(48)` |
| `EVENT_SIGNING_SECRET` | Yes | Output of `secrets.token_urlsafe(48)` |
| `MEMORY_ENCRYPTION_KEY` | Yes | Output of `secrets.token_urlsafe(48)` |
| `DATABASE_URL` | Yes (for production) | `postgresql+asyncpg://user:pass@host:5432/db?ssl=require` |
| `CORS_ORIGINS` | Yes | `https://yourdomain.com` |
| `OPENAI_API_KEY` | If using AI agents | `sk-...` |

---

## Reverse Proxy (Nginx Example)

Place the application behind a reverse proxy for TLS termination, request buffering, and static asset caching.

```nginx
server {
    listen 443 ssl;
    server_name yourdomain.com;

    ssl_certificate /path/to/cert.pem;
    ssl_certificate_key /path/to/key.pem;

    location / {
        proxy_pass http://127.0.0.1:8080;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location /ws/ {
        proxy_pass http://127.0.0.1:8080;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }
}

# Redirect HTTP to HTTPS
server {
    listen 80;
    server_name yourdomain.com;
    return 301 https://$host$request_uri;
}
```

---

## Rollback

- **Docker:** Re-deploy a previous image tag. No additional steps required.
- **Direct:** Check out the previous Git tag and restart the server.
- **Database:** Tables are created on startup -- no migration rollback is needed. Data in PostgreSQL is preserved across deploys. If a schema change was destructive, restore from your PostgreSQL backup.

---

## Verify

After deployment, verify the application is running correctly:

```bash
# Liveness check
curl https://yourdomain.com/api/v1/health
# Expected: {"status":"healthy","version":"0.4.0",...}

# Readiness check (includes DB connectivity)
curl https://yourdomain.com/api/v1/health/ready
# Expected: {"status":"ready","database":"connected"}
```

If either check fails:

1. Check container/process logs for startup errors
2. Verify `DATABASE_URL` is correct and the database is reachable
3. Confirm the port mapping is correct (container port 8080)
4. Ensure environment variables are loaded (especially `JWT_SECRET_KEY`)

---

## CI Pipeline

The project includes a GitHub Actions CI pipeline (`.github/workflows/ci.yml`) that runs on every push and pull request to `main`:

| Job | Steps |
|-----|-------|
| **Backend Tests** | Python 3.11 setup, `pip install`, `ruff check` lint, `pytest` |
| **Frontend Tests & Build** | Node 20 setup, `npm ci`, TypeScript type-check, Vitest, production build |

Both jobs must pass before merging. The CI pipeline does not deploy automatically -- deployment is manual or configured separately per your infrastructure.
