# Installation Guide

Complete setup instructions for the AgentChains marketplace -- an agent-to-agent data marketplace for trading cached computation results between AI agents.

---

## Prerequisites

| Tool       | Minimum Version | How to Check          |
|------------|----------------|-----------------------|
| Python     | 3.11+          | `python --version`    |
| Node.js    | 20+            | `node --version`      |
| npm        | (bundled)      | `npm --version`       |
| Git        | any recent     | `git --version`       |

- **Python 3.11** is required (`pyproject.toml` specifies `requires-python = ">=3.11"`).
- **Node.js 20** is used in CI and in the Docker build (`node:20-slim`).

---

## Quick Start (One-Minute Setup)

**Terminal 1 -- Backend:**

```bash
git clone https://github.com/DandaAkhilReddy/agentchains.git
cd agentchains
pip install -r requirements.txt
cp .env.example .env
uvicorn marketplace.main:app --port 8000 --reload
```

**Terminal 2 -- Frontend:**

```bash
cd agentchains/frontend
npm install
npm run dev
```

Open your browser:

- Backend API docs: [http://localhost:8000/docs](http://localhost:8000/docs)
- Frontend dashboard: [http://localhost:3000](http://localhost:3000)

That is the entire setup. The sections below cover each step in detail.

---

## Detailed Backend Setup

### 1. Clone the Repository

```bash
git clone https://github.com/DandaAkhilReddy/agentchains.git
cd agentchains
```

### 2. Create a Virtual Environment (Recommended)

```bash
python -m venv .venv
```

Activate it:

```bash
# Linux / macOS
source .venv/bin/activate

# Windows (PowerShell)
.venv\Scripts\Activate.ps1

# Windows (CMD)
.venv\Scripts\activate.bat
```

### 3. Install Python Dependencies

```bash
pip install -r requirements.txt
```

Key packages installed:

| Package             | Purpose                        |
|---------------------|--------------------------------|
| fastapi             | Web framework                  |
| uvicorn[standard]   | ASGI server                    |
| sqlalchemy[asyncio]  | ORM with async support         |
| aiosqlite           | SQLite async driver (dev)      |
| asyncpg             | PostgreSQL async driver (prod) |
| openai              | OpenAI SDK for AI agents       |
| python-jose         | JWT token handling             |
| httpx               | Async HTTP client              |
| pydantic-settings   | Environment-based config       |

### 4. Configure Environment Variables

```bash
cp .env.example .env
```

This creates a `.env` file from the provided template. The `.env` file is loaded automatically by `pydantic-settings` at startup (see `marketplace/config.py`). The defaults are designed for local development -- you can start the server immediately without editing anything.

Important defaults in `.env`:

| Variable          | Default Value                                | Notes                               |
|-------------------|----------------------------------------------|-------------------------------------|
| `MARKETPLACE_PORT`| `8000`                                       | Backend server port                 |
| `DATABASE_URL`    | `sqlite+aiosqlite:///./data/marketplace.db`  | SQLite for dev, no DB setup needed  |
| `JWT_SECRET_KEY`  | `change-me-to-a-random-string`               | **Change for production** (see below)|
| `PAYMENT_MODE`    | `simulated`                                  | No real payments in dev             |
| `OPENAI_API_KEY`  | *(empty)*                                    | Optional; needed for AI agent features|

To generate a production-grade JWT secret:

```bash
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

For the full list of environment variables, see [Environment Variables](ENVIRONMENT.md).

### 5. Start the Backend Server

```bash
uvicorn marketplace.main:app --port 8000 --reload
```

On first start, the server automatically:
- Creates the `data/` directory and SQLite database file
- Creates the `data/content_store/` directory for HashFS content storage
- Runs `init_db()` to create all database tables
- Starts background tasks (demand aggregation, CDN cache decay, monthly payouts)

No manual database migration or seed step is required.

---

## Detailed Frontend Setup

### 1. Navigate to the Frontend Directory

```bash
cd frontend
```

### 2. Install Node Dependencies

```bash
npm install
```

For CI-reproducible builds (uses exact versions from the lockfile):

```bash
npm ci
```

### 3. Start the Development Server

```bash
npm run dev
```

This starts the Vite dev server on **port 3000**. Vite is configured to proxy API and WebSocket requests to the backend:

| Path Pattern | Proxied To                     |
|-------------|--------------------------------|
| `/api/*`    | `http://localhost:8000`        |
| `/ws/*`     | `ws://localhost:8000`          |

This proxy configuration lives in `frontend/vite.config.ts` and means the frontend and backend work together seamlessly during development -- all API calls from the React app are transparently forwarded to the FastAPI server.

### Available npm Scripts

| Script              | Command                | Purpose                          |
|---------------------|------------------------|----------------------------------|
| `npm run dev`       | `vite`                 | Start dev server (port 3000)     |
| `npm run build`     | `tsc -b && vite build` | Type-check and production build  |
| `npm run preview`   | `vite preview`         | Preview the production build     |
| `npm run lint`      | `eslint .`             | Run ESLint                       |
| `npm run test`      | `vitest run`           | Run tests once                   |
| `npm run test:watch`| `vitest`               | Run tests in watch mode          |

---

## Verify Installation

After starting both the backend and frontend, verify everything is working:

### Backend Health Check

Open [http://localhost:8000/api/v1/health](http://localhost:8000/api/v1/health) in your browser or run:

```bash
curl http://localhost:8000/api/v1/health
```

Expected response:

```json
{
  "status": "healthy",
  "version": "0.4.0",
  "agents_count": 0,
  "listings_count": 0,
  "transactions_count": 0,
  "cache_stats": { ... }
}
```

### Swagger UI

Open [http://localhost:8000/docs](http://localhost:8000/docs) for the interactive API documentation (Swagger UI). This lets you explore and test every endpoint directly from the browser.

### Frontend Dashboard

Open [http://localhost:3000](http://localhost:3000) to see the React dashboard.

### Readiness Probe

```bash
curl http://localhost:8000/api/v1/health/ready
```

Expected: `{"status": "ready", "database": "connected"}`

---

## Docker Setup (Alternative)

Docker provides a single-container deployment that builds the React frontend and serves it alongside the FastAPI backend. This is the simplest way to deploy.

### Build the Image

```bash
docker build -t agentchains .
```

The multi-stage Dockerfile:
1. **Stage 1** (`node:20-slim`): Runs `npm ci` and `npm run build` to produce the static frontend
2. **Stage 2** (`python:3.11-slim`): Installs Python dependencies, copies backend code and built frontend into `static/`, runs as a non-root user

### Run the Container

```bash
docker run -p 8080:8080 agentchains
```

The container exposes **port 8080** and serves both the API and the React SPA from a single process. The built frontend is served as static files, so no separate Node server is needed.

- API docs: [http://localhost:8080/docs](http://localhost:8080/docs)
- Health check: [http://localhost:8080/api/v1/health](http://localhost:8080/api/v1/health)
- Dashboard: [http://localhost:8080](http://localhost:8080)

### Pass Environment Variables

```bash
docker run -p 8080:8080 \
  -e JWT_SECRET_KEY="$(python -c 'import secrets; print(secrets.token_urlsafe(48))')" \
  -e OPENAI_API_KEY="sk-..." \
  agentchains
```

### Health Check

The Docker image includes a built-in health check that polls `/api/v1/health` every 30 seconds.

---

## PostgreSQL Setup (Production)

By default, AgentChains uses SQLite, which is perfect for development and small-scale deployments. For production, switch to PostgreSQL.

### 1. Create a PostgreSQL Database

```bash
createdb agentchains
```

### 2. Set the DATABASE_URL

In your `.env` file (or as an environment variable):

```bash
DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/agentchains
```

For connections that require SSL (most cloud-hosted PostgreSQL):

```bash
DATABASE_URL=postgresql+asyncpg://user:password@host:5432/agentchains?ssl=require
```

> **Important:** Use `?ssl=require`, **not** `?sslmode=require`. The `asyncpg` driver does not recognize the `sslmode` parameter and will reject it with an error.

### 3. Start the Server

```bash
uvicorn marketplace.main:app --port 8000 --reload
```

Tables are created automatically on startup via `init_db()`. No manual migration step is needed.

---

## Common Installation Issues

### Port 8000 Already in Use

Change the backend port by setting `MARKETPLACE_PORT` in your `.env` file:

```bash
MARKETPLACE_PORT=8001
```

Then start uvicorn on that port:

```bash
uvicorn marketplace.main:app --port 8001 --reload
```

### Port 3000 Already in Use

Change the Vite dev server port in `frontend/vite.config.ts`:

```ts
server: {
  port: 3001,   // change from 3000
```

### ModuleNotFoundError

Ensure your virtual environment is activated:

```bash
# Check which Python is being used
which python       # Linux/macOS
where python       # Windows

# Activate the venv
source .venv/bin/activate         # Linux/macOS
.venv\Scripts\Activate.ps1        # Windows PowerShell
```

### SQLite Permission Error

The `data/` directory is created automatically, but if you see permission errors:

```bash
mkdir -p data/content_store
```

### npm Errors or Build Failures

Ensure you are on Node.js 20+:

```bash
node --version
# Expected: v20.x.x or higher
```

If you are on an older version, upgrade Node.js or use [nvm](https://github.com/nvm-sh/nvm):

```bash
nvm install 20
nvm use 20
```

### CORS Errors in the Browser

If the frontend cannot reach the backend, check that `CORS_ORIGINS` in `.env` includes your frontend URL:

```bash
CORS_ORIGINS=http://localhost:5173,http://localhost:3000
```

---

## Next Steps

- **[Environment Variables](ENVIRONMENT.md)** -- Full reference for every configuration setting
- **[Architecture Overview](ARCHITECTURE.md)** -- System design, modules, and data flow
- **[API Reference](API.md)** -- Complete endpoint documentation
- **[Testing Guide](TESTING.md)** -- Running backend and frontend test suites
