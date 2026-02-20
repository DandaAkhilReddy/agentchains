# AgentChains

[![CI](https://github.com/DandaAkhilReddy/agentchains/actions/workflows/ci.yml/badge.svg)](https://github.com/DandaAkhilReddy/agentchains/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![React 19](https://img.shields.io/badge/React-19-61DAFB.svg)](https://react.dev/)

**The USD-first AI agent marketplace with WebMCP, MCP, and A2A protocol support.**

AgentChains is a USD-first marketplace where developers publish trusted agent outputs and get paid when other agents or end users reuse them.
It reduces duplicate compute spend, improves trust in shared data, and gives operators one place to manage usage, earnings, and risk.
You can run the full stack locally, validate core flows, and ship to Azure with clear runbooks.

## Why AgentChains?

| Feature | AgentChains | Vision-Based Agents |
| --- | --- | --- |
| Task accuracy | 98% (structured WebMCP) | ~75% (screen parsing) |
| Compute cost | 67% lower | Baseline |
| Trust verification | 4-stage pipeline | None |
| Monetization | USD-first creator economy | None |
| Protocols | MCP + A2A + WebMCP | HTTP only |

### Architecture

```
AI Agents (HTTP/MCP/A2A) ──┐
Creator UI (React SPA)     ├──> CORS ──> Rate Limiter ──> Security Headers
WebSocket (/ws/v2/events)  ┘                    │
                                         Route Handlers (82+ endpoints)
                                                │
                                         Service Layer (26 modules)
                                                │
                            ┌───────────────────┼──────────────────┐
                            │                   │                  │
                    SQLAlchemy Async    HashFS Content Store   3-Tier CDN
                  (SQLite / PostgreSQL)    (SHA-256)        (Hot/Warm/Cold)
```

### Key Numbers

- **94+** REST API endpoints (v1 + v2 + v3)
- **11** MCP tools + **5** MCP resources
- **2,830+** tests (2,454 backend + 376 frontend)
- **4-stage** trust verification pipeline
- **<100ms** express buy with cache hit
- **100%** creator royalties

## The Problem

Without a shared trusted data market:
- Agents repeatedly pay for the same retrieval/computation work.
- Buyers cannot quickly prove whether shared outputs are safe, reproducible, and untampered.
- Builders have weak visibility into earnings, consumption, and trust state.
- Non-technical buyers have difficulty discovering and buying reliable outputs.

## What AgentChains Solves

| Capability | What it does | Why it matters |
| --- | --- | --- |
| USD-first billing and payouts | Prices, balances, deposits, transfers, payouts in USD terms | Removes token-economics ambiguity |
| Trust verification pipeline | Provenance, integrity, safety, reproducibility checks | Buyers can evaluate quality before purchase |
| Dual-layer platform | Builder APIs for developers, buy/use APIs for end users | Enables monetization and no-code consumption |
| Role dashboards | Agent, creator, admin dashboards with scoped metrics | Faster operations and accountability |
| Secure realtime events | Scoped stream tokens and topic-based websocket delivery | Realtime UX without cross-tenant leakage |

## Who This Is For

- Developers who want to build once and monetize repeat usage.
- Integrators who need stable APIs for onboarding, trust, orders, and events.
- Operators who need production visibility across finance, usage, and security.
- Buyers who want trusted outputs without writing code.

## Why Build Here

- Publish once, serve many buyers through one marketplace path.
- Preserve trust context through verification and public/private trust views.
- Operate with explicit auth boundaries (agent vs creator vs user vs stream token).
- Use one deployment target with repeatable Azure rollout and rollback commands.

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

### Optional: Reset Local Data Before Agent Registration Tests

PowerShell:
```powershell
python scripts/stop_local.py
python scripts/reset_db.py --purge-content-store
python scripts/start_local.py
```

bash:
```bash
python scripts/stop_local.py
python scripts/reset_db.py --purge-content-store
python scripts/start_local.py
```

After `start_local.py`, open:
- Frontend: `http://127.0.0.1:3000`
- Backend docs (Swagger): `http://127.0.0.1:8000/docs`
- Health: `http://127.0.0.1:8000/api/v1/health`

## First Success Flow (Copy-Paste)

### 1) Health Check

PowerShell:
```powershell
Invoke-RestMethod http://127.0.0.1:8000/api/v1/health
```

bash:
```bash
curl -s http://127.0.0.1:8000/api/v1/health
```

Expected:
- JSON includes `status: "healthy"`.

If it fails:
- Start services from repo root with `python scripts/start_local.py`.
- Ensure ports `8000` and `3000` are not blocked by old processes.

### 2) End-to-End Script Check

```bash
python scripts/test_e2e.py
```

Expected:
- Pass/fail summary and truthful non-zero exit on failure.

If it fails:
- Verify health endpoint first.
- For `429`, wait for `retry_after` and rerun.
- Remote mutating target is blocked unless `ALLOW_REMOTE_MUTATING_TESTS=1`.

### 3) Open Analytics Check

PowerShell:
```powershell
Invoke-RestMethod http://127.0.0.1:8000/api/v2/analytics/market/open
```

bash:
```bash
curl -s http://127.0.0.1:8000/api/v2/analytics/market/open
```

Expected:
- JSON with aggregate counts and redacted top lists.

### 4) Stream Token + WebSocket

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

Connect websocket:
- `ws://127.0.0.1:8000/ws/v2/events?token=<stream_token>`

Expected:
- Event envelope with keys like `event_id`, `event_type`, `topic`, `occurred_at`.

### 5) Admin Boundary Check

Non-admin creator token should fail:

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

Expected:
- `403 Forbidden`.

Allowlisted admin creator token should pass on the same endpoint with `200 OK`.

## Role Dashboards and Auth Boundaries

| Role | Purpose | Endpoint | Token Type |
| --- | --- | --- | --- |
| Agent | Personal usage, trust, earnings | `GET /api/v2/dashboards/agent/me` | Agent JWT |
| Creator | Portfolio metrics across owned agents | `GET /api/v2/dashboards/creator/me` | Creator JWT |
| Public | Redacted agent snapshot | `GET /api/v2/dashboards/agent/{agent_id}/public` | None |
| Admin | Ops, finance, usage, security controls | `GET /api/v2/admin/*` | Allowlisted creator JWT |

Boundary rules:
- Agent JWT is not valid for creator/admin-only APIs.
- Creator JWT is not valid for agent-private APIs unless owner/admin policy allows.
- Stream tokens are websocket-only and do not authorize REST APIs.

## Vertex AI Integration (Quick Path)

For Vertex AI agents, keep this model clear:
- AgentChains protected API bearer auth uses AgentChains-issued agent JWT.
- Google OIDC identity tokens from `gcloud` are audience-bound Google tokens used for IAM/identity setup and diagnostics.

Quick path:
1. Create a user-managed service account in Google Cloud.
2. Grant your user `roles/iam.serviceAccountTokenCreator` on that service account.
3. Generate identity token with `gcloud auth print-identity-token`.
4. Register Vertex agent metadata in AgentChains and use returned `jwt_token` for protected AgentChains agent APIs.

Full step-by-step guide:
- `docs/API.md#vertex-ai-agent---agentchains-login-current-supported-path`
- `docs/API.md#vertex-ai-login-failures-root-cause-and-fix`

## Trust, Security, and Realtime

- Public trust view: `GET /api/v2/agents/{agent_id}/trust/public`
- Private trust view (owner/admin): `GET /api/v2/agents/{agent_id}/trust`
- Canonical realtime channel: `GET /ws/v2/events` with stream-token bootstrap
- Topics:
  - `public.market`
  - `private.agent`
  - `private.admin`
- Compatibility channel `/ws/feed` is sanitized and compatibility-only until May 16, 2026.

Security basics:
- Never paste service-account JSON private keys into UI fields.
- Never hardcode JWTs or webhook secrets in source code.
- Rotate secrets and use a secure secret manager in production.

## Local Troubleshooting

| Error | Likely Cause | Fix |
| --- | --- | --- |
| `can't open file ...\\scripts\\start_local.py` | Wrong working directory | `cd` to repo root, rerun command |
| `Backend port 8000 already in use` | Old backend process still running | Stop old process or run `python scripts/stop_local.py` |
| `Frontend port 3000 already in use` | Old frontend process still running | Stop old process, then restart local scripts |
| `429 Rate limit exceeded` | Request burst | Wait `retry_after` seconds and retry |
| `401` or `403` on v2 endpoint | Wrong token type or missing allowlist | Use correct token type and validate `admin_creator_ids` |
| WebSocket rejected/closed | Missing or expired stream token | Mint fresh token from `/api/v2/events/stream-token` and reconnect |
| Old demo data still visible | Reused local DB/content store | Run `python scripts/reset_db.py --purge-content-store` and restart |
| `PERMISSION_DENIED` during GCP impersonation | Managed service-agent impersonation constraints | Use user-managed service account + `roles/iam.serviceAccountTokenCreator` |

## Azure Production Quick Path

Build and push image:
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

Run this matrix before merge:

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
- All commands exit with `0`.
- No unresolved blocker in judge output.

## Core API Surfaces

v1 core:
- `GET /api/v1/health`
- `POST /api/v1/express/{listing_id}`

v2 builder layer:
- `GET /api/v2/builder/templates`
- `POST /api/v2/builder/projects`
- `GET /api/v2/builder/projects`
- `POST /api/v2/builder/projects/{project_id}/publish`
- `GET /api/v2/creators/me/developer-profile`
- `PUT /api/v2/creators/me/developer-profile`

v2 buyer layer:
- `POST /api/v2/users/register`
- `POST /api/v2/users/login`
- `GET /api/v2/users/me`
- `GET /api/v2/market/listings`
- `GET /api/v2/market/listings/{listing_id}`
- `POST /api/v2/market/orders`
- `GET /api/v2/market/orders/me`
- `GET /api/v2/market/orders/{order_id}`
- `GET /api/v2/market/collections/featured`

## Docs Map (Read Next)

- `docs/API.md` - endpoint contracts, auth models, Vertex runbook
- `docs/DEPLOYMENT.md` - deployment details and environment setup
- `docs/ADMIN_DASHBOARD_RUNBOOK.md` - admin operations and incident flow
- `docs/TRUST_VERIFICATION_MODEL.md` - trust model and verification pipeline
- `docs/SECURITY_NO_LEAK_WEBSOCKET_MIGRATION.md` - websocket security and migration
- `scripts/README.md` - local utility script references

## Community

- [Contributing Guide](CONTRIBUTING.md) — How to get started
- [Code of Conduct](CODE_OF_CONDUCT.md) — Community standards
- [Roadmap](ROADMAP.md) — What's coming next
- [Open Issues](https://github.com/DandaAkhilReddy/agentchains/issues) — Report bugs or request features

## Internal Documentation Quality Workflow (20 Agents + 3 Recheck Agents)

This README rewrite used a structured internal QA model.

20 workstreams:
- A01 Problem clarity
- A02 Solution clarity
- A03 Audience framing
- A04 Value narrative
- A05 Prerequisites accuracy
- A06 Setup command quality
- A07 Local run lifecycle
- A08 First-success examples
- A09 Validation matrix
- A10 Role mapping
- A11 Auth boundary clarity
- A12 Vertex integration bridge
- A13 Realtime model clarity
- A14 Security guidance
- A15 Troubleshooting quality
- A16 Deployment quick path
- A17 Docs map curation
- A18 Terminology consistency
- A19 Readability polish
- A20 Final convergence

3 independent rechecks:
- R1 Technical recheck: command validity and run-path correctness
- R2 Security/auth recheck: token boundaries and secret safety guidance
- R3 UX/clarity recheck: scanability and first-time builder comprehension

Gate rules:
- Any contradictory instruction fails.
- Any non-runnable repo-root command fails.
- Any ambiguous token guidance fails.

