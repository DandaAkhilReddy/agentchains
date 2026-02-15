# Phase 0 Baseline

Date: 2026-02-15  
Branch: `codex/admin-analytics-trust-20260215`

## Repository Baseline

- Source branch at start: `master`
- Working branch created for implementation: `codex/admin-analytics-trust-20260215`
- Working tree at baseline: clean

## Production Baseline (Azure Container Apps)

Deployment target:
- `https://agentchains-marketplace.orangemeadow-3bb536df.eastus.azurecontainerapps.io`

Baseline health checks:
- `GET /` -> 200
- `GET /docs` -> 200
- `GET /api/v1/health` -> 200
- `GET /api/v1/health/cdn` -> 200

## Local Validation Baseline

Local services verified:
- `http://127.0.0.1:8000/api/v1/health` -> 200
- `http://127.0.0.1:8000/docs` -> 200
- `http://127.0.0.1:3000` -> 200

## Baseline Gate Commands

Executed:
- `python -m pytest marketplace/tests -q`
- `npm --prefix frontend run test`
- `npm --prefix frontend run lint`
- `npm --prefix frontend run build`
- `python scripts/test_e2e.py`
- `python scripts/test_adk_agents.py`
- `python scripts/test_azure.py`

Result summary:
- Backend tests: pass
- Frontend tests/lint/build: pass (lint has pre-existing warnings only)
- E2E scripts: pass
