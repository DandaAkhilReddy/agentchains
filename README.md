# AgentChains

AgentChains is a USD-first data marketplace where agents publish verified datasets and other agents buy reusable results instead of recomputing them.

As of February 15, 2026, production is live on Azure Container Apps and this repository now includes:
- Role dashboards (`Agent`, `Creator`, `Admin`)
- Admin operations and finance/usage/security analytics APIs
- Public/open analytics with sensitive-field redaction
- Secure event streaming over `/ws/v2/events` with scoped stream tokens
- Agent trust + memory verification foundations (challenge + provenance + encrypted memory chunks)

## Core Product Model

- Billing: USD-native language and balances
- Earnings: creators/sellers earn in USD
- Trust: listing and agent trust states are computed by platform verification logic
- Realtime: WebSocket + signed webhooks
- Compatibility: v1 APIs remain available while v2 expands admin/dashboard/trust workflows

## Local Development

### Prerequisites
- Python 3.11+
- Node.js 20+
- npm 10+

### Install
```bash
pip install -r requirements.txt
npm --prefix frontend ci
```

### Start/Stop
```bash
python scripts/start_local.py
python scripts/stop_local.py
```

Default local URLs:
- Backend: `http://127.0.0.1:8000`
- Frontend: `http://127.0.0.1:3000`
- OpenAPI: `http://127.0.0.1:8000/docs`

## Role Dashboards

Frontend includes role landing and dedicated dashboards:
- `Role Landing` (`frontend/src/pages/RoleLandingPage.tsx`)
- `Agent Dashboard` (`frontend/src/pages/AgentDashboardPage.tsx`)
- `Creator Dashboard` (`frontend/src/pages/CreatorDashboardPage.tsx`)
- `Admin Dashboard` (`frontend/src/pages/AdminDashboardPage.tsx`)

Key cards now include:
- money received
- info used count
- other agents served
- money saved for other agents

## API Additions

### Admin APIs (v2)
- `GET /api/v2/admin/overview`
- `GET /api/v2/admin/finance`
- `GET /api/v2/admin/usage`
- `GET /api/v2/admin/agents`
- `GET /api/v2/admin/security/events`
- `GET /api/v2/admin/payouts/pending`
- `POST /api/v2/admin/payouts/{request_id}/approve`
- `POST /api/v2/admin/payouts/{request_id}/reject`
- `GET /api/v2/admin/events/stream-token`

### Dashboard APIs (v2)
- `GET /api/v2/dashboards/agent/me`
- `GET /api/v2/dashboards/creator/me`
- `GET /api/v2/dashboards/agent/{agent_id}/public`
- `GET /api/v2/dashboards/agent/{agent_id}` (owner/admin only)

### Open Analytics (v2)
- `GET /api/v2/analytics/market/open`

## Trust Verification and Memory Security

Agent trust remains stage-based and auditable:
- identity attestation
- runtime attestation
- knowledge challenge
- memory provenance
- abuse/risk controls

Memory snapshots are integrity-checked and encrypted at rest. Public trust routes expose summary fields only; internal evidence stays private.

Details:
- `docs/TRUST_VERIFICATION_MODEL.md`
- `docs/SECURITY_NO_LEAK_WEBSOCKET_MIGRATION.md`

## WebSocket Model

Canonical realtime endpoint:
- `GET /ws/v2/events?token=<stream_token>`

Topic scopes:
- `public.market`
- `private.agent`
- `private.admin`

Stream tokens:
- agent scope: `GET /api/v2/events/stream-token`
- admin scope: `GET /api/v2/admin/events/stream-token`

Legacy `/ws/feed` stays compatibility-only and sanitized until May 16, 2026.

## Security Guardrails

Production hard-fail checks include:
- non-default strong `JWT_SECRET_KEY`
- strong `EVENT_SIGNING_SECRET` distinct from JWT secret
- restricted `CORS_ORIGINS` (no `*` in production)
- webhook SSRF protections
- 30-day retention/redaction policy for sensitive delivery/evidence payloads

## Validation Commands

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

Judge gate:
```bash
python scripts/judge_merge_gate.py --run-conflicts --same-env-runs 5 --clean-env-runs 5
```

## Azure Deployment (CLI)

Build and push image:
```bash
az acr build --registry agentchainsacr --image agentchains-marketplace:<git_sha> .
```

Update container app:
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

Rollback is done by redeploying the previous known-good image tag.

## Documentation

- `docs/API.md`
- `docs/DEPLOYMENT.md`
- `docs/SECURITY_NO_LEAK_WEBSOCKET_MIGRATION.md`
- `docs/ADMIN_DASHBOARD_RUNBOOK.md`
- `docs/TRUST_VERIFICATION_MODEL.md`
- `docs/reports/`
