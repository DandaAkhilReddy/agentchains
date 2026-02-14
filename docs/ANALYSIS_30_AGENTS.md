# Deep Analysis: 30-Agent Engineering Pass

Date: February 14, 2026  
Scope: Entire `agentchains` workspace (backend, frontend, tests, docs, scripts)

## Snapshot

- Backend source files (`marketplace/`, excluding tests): 93
- Backend test files (`marketplace/tests`): 109
- Frontend TS/TSX source files (`frontend/src`): 98
- Frontend test files (`frontend/src`): 19
- API routes by decorator count (`marketplace/api` + `marketplace/mcp`): 81
- Inline app routes in `marketplace/main.py`: 4

## 30-Agent Assignment Matrix

| # | Agent Role | Scope | Key Finding | Assigned Task | Priority |
|---|---|---|---|---|---|
| 1 | Repo Cartographer | Whole repo | Layout is broad and non-obvious for new contributors | Maintain a structure guide and onboarding path | P0 |
| 2 | Backend Bootstrap Agent | `marketplace/main.py` | App wiring and route registration were dense | Keep startup flow modular and readable | P0 |
| 3 | Router Registry Agent | `marketplace/api/` | Router imports were manual and repetitive | Use central router registry in `api/__init__.py` | P0 |
| 4 | Auth Boundary Agent | `marketplace/core/auth.py` + APIs | Auth is reused well but spread across many routes | Keep auth in dependencies only | P1 |
| 5 | Security Headers Agent | Middleware path | Security headers are present and centralized | Keep policy updates in one middleware class | P1 |
| 6 | Rate Limit Agent | Middleware + config | Limits exist for auth/anon paths | Add route-level exception notes in docs | P1 |
| 7 | Transaction Integrity Agent | `token_service.py` | Ledger logic is comprehensive but large | Split ledger internals into smaller modules | P1 |
| 8 | Listing Lifecycle Agent | `listing_service.py` | Listing flow is clear but does event scheduling inline | Extract event scheduling helper utilities | P1 |
| 9 | Express Path Agent | `express_service.py` + API | Fast path is good but instrumentation is dispersed | Consolidate latency instrumentation hooks | P1 |
| 10 | Discovery Demand Agent | discovery/automatch/express APIs | Demand logging pattern repeated in multiple handlers | Normalize with shared background logging helper | P1 |
| 11 | ZKP Agent | `zkp_service.py` | Feature-rich and sizeable module | Break into proof-gen/verify/util submodules | P2 |
| 12 | Reputation Agent | reputation services/routes | Reputation logic coupled with analytics patterns | Add explicit reputation calculation contracts | P2 |
| 13 | Catalog Agent | catalog services/routes | Catalog domain includes broad responsibilities | Separate matching vs publishing responsibilities | P2 |
| 14 | Creator Economy Agent | creators/payout/redemptions | Domain is broad and cross-cuts token logic | Define creator domain boundary document | P1 |
| 15 | OpenClaw Integration Agent | integration routes/services | Integration exists in multiple surfaces | Add integration runbook and failure playbook | P1 |
| 16 | MCP Surface Agent | `marketplace/mcp/` | MCP and REST share service layer (good) | Keep parity checklist for new endpoints/tools | P1 |
| 17 | Data Store Agent | local `data/` + `marketplace/data/` | Runtime data appears in multiple locations | Standardize one canonical local data path | P0 |
| 18 | Database Engine Agent | `database.py` | SQLite/Postgres split is handled well | Add migration strategy notes (Alembic plan) | P1 |
| 19 | Schema Contract Agent | `marketplace/schemas/` | Contracts exist but grow quickly | Add schema ownership map and version notes | P2 |
| 20 | API Contract Agent | `marketplace/api/` | Many endpoints; consistency risk rises with growth | Enforce route naming and response contract rules | P1 |
| 21 | Frontend Architecture Agent | `frontend/src` | Large pages/components have high line counts | Split oversized pages into feature modules | P1 |
| 22 | Frontend Hooks Agent | `frontend/src/hooks` | Hooks are well-separated; test coverage exists | Standardize hook error/loading state shape | P2 |
| 23 | Frontend Docs UX Agent | `frontend/README.md` + docs | Dev docs existed but lacked clear structure bridge | Link frontend docs to repo structure guide | P1 |
| 24 | Test Strategy Agent | backend + frontend tests | High volume tests; hard to discover by domain | Add test index by domain and confidence level | P1 |
| 25 | Performance Agent | API + services | Performance claims exist in docs | Add reproducible benchmark script paths | P2 |
| 26 | CI Health Agent | `.github/workflows/` | Workflow exists but discoverability is low | Add CI overview section in docs | P2 |
| 27 | Script Hygiene Agent | `scripts/` | Script purposes were not indexed | Maintain `scripts/README.md` with usage | P0 |
| 28 | Docs Topology Agent | `docs/` | Docs are rich but entry points are many | Add developer-first docs index | P0 |
| 29 | Release Discipline Agent | `CHANGELOG.md` + docs | Release docs exist in two formats | Keep single source process for release notes | P2 |
| 30 | Developer Experience Agent | onboarding flow | New contributors lacked short path to first change | Maintain "where to edit" map and quick path | P0 |

## Completed in This Pass

- Centralized API router registration in `marketplace/api/__init__.py`.
- Simplified backend startup wiring in `marketplace/main.py` without feature changes.
- Added `docs/DEVELOPER_STRUCTURE.md` for folder-level guidance.
- Added `scripts/README.md` for script discoverability.
- Linked new developer docs from root `README.md`.

## Immediate Next Batch (Recommended)

1. Split large backend modules (`token_service.py`, `redemption_service.py`, `zkp_service.py`) by domain sub-responsibility.
2. Normalize background task scheduling/logging in a shared utility module.
3. Standardize local data folder behavior so runtime state always lands in one path.
4. Break large frontend pages into feature-focused child modules.
5. Add a domain-indexed testing guide that maps tests to services/routes.

## Baseline Appendix (Agent 1)

### Working tree snapshot (pre-stabilization implementation)

- Branch at start: `master`
- Pre-existing local modifications:
  - `README.md`
  - `frontend/README.md`
  - `marketplace/api/__init__.py`
  - `marketplace/main.py`
  - `docs/ANALYSIS_30_AGENTS.md`
  - `docs/DEVELOPER_STRUCTURE.md`
  - `scripts/README.md`
- Runtime PID artifacts observed:
  - `.local/backend.pid`
  - `.local/frontend.pid`

### Known failing command matrix (pre-fix)

| Command | Status | Failure Signature |
|---|---|---|
| `python scripts/test_adk_agents.py` | Exit `0` but logically failed | `405 Method Not Allowed` on express purchase due `GET /express/{listing_id}` |
| `python scripts/test_azure.py` (as shipped) | Exit `1` | Hardcoded remote target + registration failures (`500`) |
| `python -c "import scripts.test_azure...; main()"` local override | Exit `1` | `405 Method Not Allowed` on express purchase due `GET /express/{listing_id}` |

## Release Gate Appendix (Agent 30)

Date: February 14, 2026

### Commands run and outcomes

| Command | Outcome |
|---|---|
| `python -m pytest marketplace/tests/test_express_deep_routes.py -q` | `24 passed` |
| `python -m pytest marketplace/tests/test_analytics_routes.py -q` | `22 passed` |
| `python -m pytest marketplace/tests/test_judge_api_contracts.py -q` | `15 passed` |
| `python -m pytest marketplace/tests/test_api_router_registry.py -q` | `2 passed` |
| `python -m pytest marketplace/tests -q` | `2371 passed, 2 xfailed` |
| `npm --prefix frontend run test` | `19 files passed, 376 tests passed` |
| `npm --prefix frontend run lint` | exit `0`, no errors (`17 warnings`) |
| `python scripts/test_e2e.py` | pass |
| `python scripts/test_e2e.py --spawn-server --port 8011` | pass |
| `python scripts/test_adk_agents.py` | pass (`Passed: 19, Failed: 0, Skipped: 0`) |
| `python scripts/test_azure.py` | pass (`25/25`) |
| Smoke checks (`/api/v1/health`, `/docs`, `/api/v1/health/cdn`, `http://127.0.0.1:3000/`, `http://127.0.0.1:3000/api/v1/health`) | all `200` |

### Contract and warning status

- Express purchase contract normalized to `POST /express/{listing_id}` in scripts and docs examples.
- Script summaries and exit codes are now counter-driven (no false pass totals).
- First-party `schema_json` field-shadow warning removed via internal rename + alias preservation.
- Pytest async loop scope set explicitly to function scope.
- Async background task teardown races mitigated via `drain_background_tasks()` in test teardown.
- Pytest warning policy updated for known intentional warnings.

### Remaining non-blockers

- Frontend lint still reports warnings (no errors), mostly unused vars in tests and `exhaustive-deps` in two pages.
- Frontend test output prints non-fatal React testing warnings (`act(...)` and chart container sizing), but suite is green.
