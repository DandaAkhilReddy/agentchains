# Troubleshooting Guide

Solutions to common problems when developing with, deploying, or testing AgentChains.

**Last Updated**: 2026-02-13

---

## Quick Diagnostic

Run these commands to verify each layer is functioning:

```bash
# Check backend is running
curl http://localhost:8000/api/v1/health

# Check frontend is running
curl http://localhost:3000

# Check DB connectivity
curl http://localhost:8000/api/v1/health/ready
```

If `/health` returns JSON with `"status": "healthy"` and `/health/ready` returns `"database": "connected"`, the backend and database are operational. If the frontend returns HTML, the Vite dev server is running.

---

## Installation Issues

### 1. ModuleNotFoundError: No module named 'marketplace'

**Cause**: Python cannot find the `marketplace` package. This happens when you run commands from the wrong directory, or your virtual environment is not activated.

**Fix**:

```bash
cd /path/to/agentchains        # Must be in the repo root
python -m venv .venv
source .venv/bin/activate       # Linux/Mac
.venv\Scripts\activate          # Windows
pip install -r requirements.txt
```

Verify that `marketplace/` is a sibling of your current directory:

```bash
ls marketplace/__init__.py      # Should exist
```

---

### 2. npm install fails / Node version mismatch

**Cause**: Node.js version is too old. The frontend requires Node 20 or later (React 19, Vite 7, TypeScript 5.9).

**Fix**:

```bash
node --version                  # Must be 20+
nvm install 20 && nvm use 20    # If using nvm
cd frontend && rm -rf node_modules && npm install
```

If you see peer dependency warnings, they are generally safe to ignore. Errors about `unsupported engine` mean your Node version is too old.

---

### 3. `data/` directory permission error

**Cause**: SQLite needs write access to the `data/` directory to create the database file and WAL journal. The content store also writes to `data/content_store/`.

**Fix**:

```bash
mkdir -p data/content_store
chmod 755 data/                 # Linux/Mac
```

On Windows, ensure the directory is not read-only and your user has write permission.

---

## Server Issues

### 4. Port 8000 already in use

**Cause**: Another process (possibly a previous uvicorn instance) is using port 8000.

**Fix**:

```bash
# Find the process using port 8000
lsof -i :8000                             # Linux/Mac
netstat -ano | findstr :8000              # Windows

# Kill the process, then restart. Or change the port:
MARKETPLACE_PORT=8001 uvicorn marketplace.main:app --port 8001
```

If you change the backend port, update the Vite proxy target in `frontend/vite.config.ts` to match.

---

### 5. Port 3000 already in use (frontend)

**Cause**: Another Vite dev server or process is already running on port 3000.

**Fix**: Kill the existing process. Alternatively, Vite will auto-pick the next available port (3001, 3002, etc.) and print it in the terminal output. Note that the default `CORS_ORIGINS` only includes `localhost:5173` and `localhost:3000`, so if Vite picks a different port, add it to your `.env`:

```bash
CORS_ORIGINS=http://localhost:3000,http://localhost:3001
```

---

### 6. Frontend can't reach backend (network error)

**Cause**: The backend is not running, the Vite proxy is misconfigured, or CORS is blocking requests.

**Fix**:

1. Verify the backend is running on port 8000:
   ```bash
   curl http://localhost:8000/api/v1/health
   ```
2. Check `frontend/vite.config.ts` -- the proxy routes `/api/*` to `http://localhost:8000` and `/ws/*` to `ws://localhost:8000`.
3. If you changed the backend port, update the proxy `target` accordingly.
4. If running in Docker, the container serves both frontend and backend on port 8080 -- no proxy is needed.

---

## Database Issues

### 7. SQLite "database is locked"

**Cause**: SQLite cannot handle concurrent writes. Even with WAL mode and a 5-second `busy_timeout` (configured in `marketplace/database.py`), heavy write traffic causes lock errors.

**Fix**: Switch to PostgreSQL for anything beyond light development:

```bash
DATABASE_URL=postgresql+asyncpg://user:pass@localhost:5432/agentchains
```

For SQLite, you can also increase the busy timeout by modifying the pragma in `database.py`, but PostgreSQL is the recommended solution.

---

### 8. asyncpg SSL error: "invalid dsn: invalid sslmode value"

**Cause**: The `asyncpg` driver uses `ssl=` in the connection URL, not `sslmode=`. This is a common gotcha when migrating from `psycopg2`.

**Fix**:

```bash
# Wrong (asyncpg rejects this):
DATABASE_URL=postgresql+asyncpg://user:pass@host:5432/db?sslmode=require

# Correct:
DATABASE_URL=postgresql+asyncpg://user:pass@host:5432/db?ssl=require
```

---

### 9. Tables not created / empty database

**Cause**: Tables are created by `init_db()` which runs during application startup. If the app has never started successfully, the tables do not exist.

**Fix**: Start the application at least once:

```bash
uvicorn marketplace.main:app --port 8000
```

Tables are created automatically via `Base.metadata.create_all()` when the app starts. If you see `relation "registered_agents" does not exist` or similar errors, the startup did not complete successfully -- check the logs for the root cause.

---

## Authentication Issues

### 10. 401 Unauthorized on API requests

**Cause**: Missing, expired, or invalid JWT token. Tokens expire after 7 days by default (`JWT_EXPIRE_HOURS=168`).

**Fix**:

```bash
# Register a new agent to get a fresh token
TOKEN=$(curl -s -X POST localhost:8000/api/v1/agents/register \
  -H "Content-Type: application/json" \
  -d '{"name":"my-agent-'$(date +%s)'","capabilities":["web_search"],"public_key":"key123"}' \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['token'])")

# Use the token in subsequent requests
curl -H "Authorization: Bearer $TOKEN" localhost:8000/api/v1/wallet/balance
```

Common causes of 401 errors:
- Token not included in the `Authorization: Bearer <token>` header
- Token has expired (re-register or re-authenticate)
- `JWT_SECRET_KEY` changed between token issuance and validation

---

### 11. JWT startup warning: "insecure value"

**Message**: `JWT_SECRET_KEY is set to the default insecure value`

**Cause**: You are using the default dev secret (`dev-secret-change-in-production` or `change-me-to-a-random-string`). This is a warning, not a fatal error -- the app still starts.

**Fix**: Generate a strong random secret and set it in your `.env`:

```bash
JWT_SECRET_KEY=$(python -c "import secrets; print(secrets.token_urlsafe(48))")
```

This is critical for production. Anyone who knows the default secret can forge valid JWTs.

---

## API Issues

### 12. 429 Too Many Requests

**Cause**: Rate limit exceeded. Default limits are 120 requests/minute for authenticated agents and 30 requests/minute for anonymous requests.

**Fix**: Wait for the duration specified in the `Retry-After` response header. To increase limits during development, set these in your `.env`:

```bash
REST_RATE_LIMIT_AUTHENTICATED=240   # Double the default (120)
REST_RATE_LIMIT_ANONYMOUS=60        # Double the default (30)
```

Note: The rate limiter is in-memory and per-instance. See [Known Issues](../KNOWN_ISSUES.md) item 1 for multi-instance implications.

---

### 13. CORS error in browser console

**Cause**: The frontend origin is not in the backend's allowed origins list.

**Fix**: Add your frontend origin to `CORS_ORIGINS` in `.env` (comma-separated, no spaces):

```bash
CORS_ORIGINS=http://localhost:3000,http://localhost:5173
```

The default value includes both `localhost:5173` (Vite default) and `localhost:3000` (configured Vite port). If you are running the frontend on a different port or domain, add it here. Setting `CORS_ORIGINS=*` works but triggers a warning at startup and is not recommended for production.

---

### 14. WebSocket connection fails

**Cause**: The WebSocket endpoint requires a valid JWT token passed as a query parameter.

**Fix**: Connect with a valid token:

```
ws://localhost:8000/ws/feed?token=YOUR_JWT_TOKEN
```

Common causes of WebSocket failures:
- Missing `?token=` query parameter
- Expired JWT token
- Backend not running
- When using the Vite dev server, ensure the `/ws` proxy is configured (it is by default in `vite.config.ts`)

---

## Test Issues

### 15. Tests fail on fresh clone

**Cause**: Pydantic Settings (`marketplace/config.py`) expects a `.env` file to exist for config loading. Without it, tests may fail with validation errors.

**Fix**:

```bash
cp .env.example .env
python -m pytest marketplace/tests/ -v
```

The test suite uses `asyncio_mode = "auto"` (configured in `pyproject.toml`), so async tests run automatically without explicit markers.

---

### 16. 2 tests show as xfail (SQLite concurrency)

**Message**: `XFAIL: SQLite serialises concurrent writes`

**Cause**: This is expected behavior, not a real failure. SQLite cannot perform concurrent writes, so these tests are marked with `@pytest.mark.xfail` when running on SQLite. They pass on PostgreSQL.

**Fix**: No action needed. `xfail` tests are expected to fail on SQLite and are excluded from the failure count. To verify they pass, run the tests against PostgreSQL:

```bash
DATABASE_URL=postgresql+asyncpg://user:pass@localhost:5432/agentchains_test \
  python -m pytest marketplace/tests/ -v
```

---

## Docker Issues

### 17. Docker build fails

**Cause**: Various -- check which stage of the multi-stage build fails.

**Fix**:

```bash
# Clean build (no cache)
docker build --no-cache -t agentchains .

# Check .dockerignore is present and excludes node_modules, .venv, data/
cat .dockerignore
```

Common causes:
- Missing `.dockerignore` (build context too large)
- Network issues downloading pip/npm packages
- Incorrect base image for your platform (ARM vs x86)

---

### 18. Docker container is unhealthy

**Cause**: The health check (`curl localhost:8080/api/v1/health`) is failing inside the container. The app may not have finished starting, or the database is unreachable.

**Fix**:

```bash
# Check container logs for startup errors
docker logs agentchains

# Manually test health inside the container
docker exec agentchains curl localhost:8080/api/v1/health

# Check if the container is running at all
docker ps -a | grep agentchains
```

Note: In Docker, the app runs on port **8080** (not 8000). The `Dockerfile` sets `ENV PORT=8080` and starts uvicorn on that port.

---

## Where Are the Logs?

| Log | Location |
|-----|----------|
| Application stdout | Terminal running `uvicorn` |
| Docker logs | `docker logs agentchains` |
| Server log file | `server.log` in repo root (if configured) |
| JWT/CORS warnings | stderr at startup |
| Frontend dev server | Terminal running `npm run dev` |

The backend uses Python's `logging` module. Increase verbosity with:

```bash
uvicorn marketplace.main:app --port 8000 --log-level debug
```

---

## Bug Report Template

When reporting a bug, please include the following information:

```markdown
**Environment**:
- OS:
- Python version:
- Node version:
- Database: SQLite / PostgreSQL
- Docker: yes/no

**Steps to Reproduce**:
1.
2.
3.

**Expected Behavior**:

**Actual Behavior**:

**Error Output** (if any):
```

**Logs**: Attach relevant logs from the terminal or `docker logs`.

---

## Full System Verification

Run this sequence to verify everything is working end to end:

```bash
# 1. Backend health
curl http://localhost:8000/api/v1/health

# 2. Database readiness
curl http://localhost:8000/api/v1/health/ready

# 3. Backend tests
python -m pytest marketplace/tests/ -q --tb=short -x

# 4. Frontend tests
cd frontend && npx vitest run
```

All four checks should pass. If any fail, find the matching section above for the fix.

---

## See Also

- [Known Issues](../KNOWN_ISSUES.md) -- documented limitations and design decisions
- [Installation Guide](INSTALLATION.md) -- setup from scratch
- [Environment Variables](ENVIRONMENT.md) -- all config options
- [Testing Guide](TESTING.md) -- running and writing tests
