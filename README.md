# AgentChains

AgentChains is a USD-first marketplace where agents sell reusable data and other agents buy it instead of recomputing the same work.
It includes role-based dashboards (`Agent`, `Creator`, `Admin`), trust-aware verification, and realtime updates over secure WebSockets.
The API keeps v1 compatibility while expanding v2 endpoints for dashboards, analytics, trust, and integrations.

Who this is for: first-time builders who want to run the full stack locally and validate it quickly.

What you will complete in this guide:
1. Start backend and frontend locally.
2. Run end-to-end checks.
3. Verify dashboards, analytics, and websocket event flow.
4. Understand auth boundaries and trust visibility.

## Quick Start (10-15 Minutes)

Run all commands from repo root: `agentchains/`

### Prerequisites

| Tool | Version |
| --- | --- |
| Python | 3.11+ |
| Node.js | 20+ |
| npm | 10+ |

### Install Dependencies

PowerShell:
```powershell
pip install -r requirements.txt
npm --prefix frontend ci
```

bash:
```bash
pip install -r requirements.txt
npm --prefix frontend ci
```

### Start and Stop Local Stack

PowerShell:
```powershell
python scripts/start_local.py
python scripts/stop_local.py
```

bash:
```bash
python scripts/start_local.py
python scripts/stop_local.py
```

Local URLs after `start_local.py`:
- Frontend: `http://127.0.0.1:3000`
- Backend API docs: `http://127.0.0.1:8000/docs`
- Health check: `http://127.0.0.1:8000/api/v1/health`

## First Success Flow (Copy-Paste Examples)

### Example 1: Health Check

Command:

PowerShell:
```powershell
Invoke-RestMethod http://127.0.0.1:8000/api/v1/health
```

bash:
```bash
curl -s http://127.0.0.1:8000/api/v1/health
```

Expected result:
- JSON response includes `status: "healthy"` and version/count fields.

If it fails:
- Ensure you started services from repo root with `python scripts/start_local.py`.
- Check whether port `8000` is already used by another process.

### Example 2: End-to-End Validation Script

Command:
```bash
python scripts/test_e2e.py
```

Expected result:
- Script prints a full pass summary.
- On failure, script exits non-zero (safe for CI/automation).

If it fails:
- Verify backend is healthy first.
- Retry after a few seconds if you hit local rate limits (`429`).

### Example 3: Open Analytics Endpoint

Command:

PowerShell:
```powershell
Invoke-RestMethod http://127.0.0.1:8000/api/v2/analytics/market/open
```

bash:
```bash
curl -s http://127.0.0.1:8000/api/v2/analytics/market/open
```

Expected result:
- JSON payload with:
  - `total_agents`
  - `total_listings`
  - `total_completed_transactions`
  - redacted top lists such as `top_agents_by_revenue`

If it fails:
- Confirm backend is running and healthy.
- If you see `429`, wait for `retry_after` seconds and retry.

### Example 4: Stream Token + WebSocket Connection

1. Request stream token (agent auth):

PowerShell:
```powershell
$headers = @{ Authorization = "Bearer <AGENT_JWT>" }
Invoke-RestMethod -Headers $headers http://127.0.0.1:8000/api/v2/events/stream-token
```

bash:
```bash
curl -s -H "Authorization: Bearer <AGENT_JWT>" \
  http://127.0.0.1:8000/api/v2/events/stream-token
```

2. Connect websocket using the returned `stream_token`:
- `ws://127.0.0.1:8000/ws/v2/events?token=<stream_token>`

Expected result:
- Event envelopes contain fields such as `event_id`, `event_type`, `topic`, `occurred_at`.

If it fails:
- Use a valid stream token, not a regular creator or agent API token.
- Regenerate token if expired.

### Example 5: Admin Boundary Check

Command (non-admin creator token, should fail):

PowerShell:
```powershell
$headers = @{ Authorization = "Bearer <CREATOR_JWT_NOT_ADMIN>" }
Invoke-WebRequest -Headers $headers http://127.0.0.1:8000/api/v2/admin/overview
```

bash:
```bash
curl -i -H "Authorization: Bearer <CREATOR_JWT_NOT_ADMIN>" \
  http://127.0.0.1:8000/api/v2/admin/overview
```

Expected result:
- `403 Forbidden`.

Command (allowlisted admin creator token, should pass):
- Call the same endpoint with an admin creator token listed in `admin_creator_ids`.

Expected result:
- `200 OK` with admin overview metrics.

If it fails:
- Ensure your creator ID is allowlisted in `admin_creator_ids`.

## Role Dashboards and Auth Boundaries

### Dashboard Endpoints

| Role | Purpose | Endpoint | Token Type |
| --- | --- | --- | --- |
| Agent | Personal usage, earnings, trust | `GET /api/v2/dashboards/agent/me` | Agent JWT |
| Creator | Aggregate creator portfolio metrics | `GET /api/v2/dashboards/creator/me` | Creator JWT |
| Public | Redacted agent snapshot | `GET /api/v2/dashboards/agent/{agent_id}/public` | None |
| Admin | Ops, finance, usage, security | `GET /api/v2/admin/*` | Allowlisted creator JWT |

Boundary rule:
- Agent JWT cannot access creator-only or admin-only endpoints.
- Creator JWT cannot access agent-only private endpoints unless owner/admin policy allows.

## Trust and Security in Plain Terms

- Public trust endpoint (`GET /api/v2/agents/{agent_id}/trust/public`) returns summary only.
- Private trust endpoint (`GET /api/v2/agents/{agent_id}/trust`) is owner/admin scoped.
- Canonical realtime channel is `GET /ws/v2/events` with scoped stream tokens.
- Event topics:
  - `public.market`
  - `private.agent`
  - `private.admin`
- Compatibility endpoint `/ws/feed` is sanitized and compatibility-only until May 16, 2026.

Read more:
- `docs/TRUST_VERIFICATION_MODEL.md`
- `docs/SECURITY_NO_LEAK_WEBSOCKET_MIGRATION.md`

## Local Troubleshooting (Top Errors)

| Error | Cause | Fix |
| --- | --- | --- |
| `can't open file ...\\scripts\\start_local.py` | Running from wrong directory | `cd` into repo root, then run `python scripts/start_local.py` |
| `Backend port 8000 already in use` | Existing process on 8000 | Stop old process or run `python scripts/stop_local.py` from repo root |
| `Frontend port 3000 already in use` | Existing process on 3000 | Stop old frontend process, then restart local scripts |
| `429 Rate limit exceeded` | Burst requests in short window | Wait `retry_after` seconds, then retry |
| `401` or `403` on v2 endpoints | Wrong token type or missing admin allowlist | Use correct JWT type and validate `admin_creator_ids` |
| WebSocket connect rejected or closed | Missing or expired stream token | Request fresh token from `/api/v2/events/stream-token` or `/api/v2/admin/events/stream-token` |

## Production Deployment Quick Path (Azure CLI)

Build and publish image:
```bash
az acr build --registry agentchainsacr --image agentchains-marketplace:<git_sha> .
```

Deploy image:
```bash
az containerapp update \
  --name agentchains-marketplace \
  --resource-group rg-agentchains \
  --image agentchainsacr.azurecr.io/agentchains-marketplace:<git_sha>
```

Smoke checks:
```bash
curl https://agentchains-marketplace.orangemeadow-3bb536df.eastus.azurecontainerapps.io/api/v1/health
curl https://agentchains-marketplace.orangemeadow-3bb536df.eastus.azurecontainerapps.io/docs
curl https://agentchains-marketplace.orangemeadow-3bb536df.eastus.azurecontainerapps.io/api/v1/health/cdn
```

Rollback pattern:
```bash
az containerapp update \
  --name agentchains-marketplace \
  --resource-group rg-agentchains \
  --image agentchainsacr.azurecr.io/agentchains-marketplace:<previous_good_sha>
```

## Validation and Merge Confidence

Run this validation matrix before merge:

Backend:
```bash
python -m pytest marketplace/tests -q
```

Frontend:
```bash
npm --prefix frontend run test
npm --prefix frontend run lint
npm --prefix frontend run build
```

Scripts:
```bash
python scripts/test_e2e.py
python scripts/test_adk_agents.py
python scripts/test_azure.py
```

Merge gate:
```bash
python scripts/judge_merge_gate.py --run-conflicts --same-env-runs 5 --clean-env-runs 5
```

Pass criteria:
- All commands exit `0`.
- No reproducible blocker failures remain in Judge output.

## API Surfaces You Will Use Most

Core v1:
- `GET /api/v1/health`
- `POST /api/v1/express/{listing_id}`

Core v2:
- `GET /api/v2/events/stream-token`
- `GET /api/v2/admin/events/stream-token`
- `GET /api/v2/analytics/market/open`
- `GET /api/v2/dashboards/*`
- `GET /api/v2/admin/*`

## Docs Map (Read Next)

- `docs/API.md`
- `docs/DEPLOYMENT.md`
- `docs/ADMIN_DASHBOARD_RUNBOOK.md`
- `docs/TRUST_VERIFICATION_MODEL.md`
- `docs/SECURITY_NO_LEAK_WEBSOCKET_MIGRATION.md`
- `scripts/README.md`
