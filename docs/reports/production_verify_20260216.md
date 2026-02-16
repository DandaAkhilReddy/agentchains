# Production Verification Report (Verify-Only)

Date: 2026-02-15T19:41:11-05:00  
Mode: Verify-only (no redeploy)  
Environment: Azure Container Apps (`agentchains-marketplace`)

## Baseline Lock

- `origin/master` short SHA: `170008c`
- Latest deploy workflow: `22042574419` (success)
- Latest CI workflow: `22042574420` (success)

Evidence links:
- Deploy run: <https://github.com/DandaAkhilReddy/agentchains/actions/runs/22042574419>
- CI run: <https://github.com/DandaAkhilReddy/agentchains/actions/runs/22042574420>

## Phase 1: Reachability Smoke

Commands:

```powershell
$base="https://agentchains-marketplace.orangemeadow-3bb536df.eastus.azurecontainerapps.io"
curl.exe -s -o NUL -w "health:%{http_code}`n" "$base/api/v1/health"
curl.exe -s -o NUL -w "docs:%{http_code}`n" "$base/docs"
curl.exe -s -o NUL -w "cdn:%{http_code}`n" "$base/api/v1/health/cdn"
```

Results:
- `health:200`
- `docs:200`
- `cdn:200`

Status: PASS

## Phase 2: Functional Surface

Commands:

```powershell
$base="https://agentchains-marketplace.orangemeadow-3bb536df.eastus.azurecontainerapps.io"
curl.exe -s -o NUL -w "openapi:%{http_code}`n" "$base/openapi.json"
curl.exe -s -o NUL -w "root:%{http_code}`n" "$base/"
```

Results:
- `openapi:200`
- `root:200`

App docs UI accessibility check:
- Docs chunk marker `Vertex AI JWT Login` found in production frontend bundle.

Status: PASS

## Phase 3: Security and Boundary Spot Checks

Commands:

```powershell
$base="https://agentchains-marketplace.orangemeadow-3bb536df.eastus.azurecontainerapps.io"
curl.exe -s -o NUL -w "admin_unauth:%{http_code}`n" "$base/api/v2/admin/overview"
curl.exe -s -o NUL -w "trust_public:%{http_code}`n" "$base/api/v2/agents/agent-demo/trust/public"
curl.exe -s -o NUL -w "stream_token_unauth:%{http_code}`n" "$base/api/v2/events/stream-token"
```

Results:
- `admin_unauth:401` (expected deny)
- `stream_token_unauth:401` (expected token model enforcement)
- `trust_public:500` (unexpected)

Additional spot checks:
- `GET /api/v1/agents?page=1&page_size=3` -> `500 Internal Server Error`
- `GET /api/v2/agents/does-not-exist/trust/public` -> `500 Internal Server Error`

Status: FAIL (blocker)

## Phase 4: Runtime Stability Snapshot

Deploy workflow history on `master` shows no newer failed deploy superseding current successful deploy.

Recent deploy runs (all success):
- `22042574419` (headSha `170008cb20992e223e328004f5da3eea0ab42665`)
- `22041880169` (headSha `4c9f44380659b6f11a65d1aa76be48fbbc5913fe`)
- `22041117443` (headSha `f9735fd6be9c5bccc898608b955371fcbcb9a766`)

Status: PASS

## Phase 5: Rollback Readiness (Prepared, Not Executed)

Previous known-good deploy SHA:
- `4c9f44380659b6f11a65d1aa76be48fbbc5913fe`

Prepared rollback command:

```powershell
az containerapp update `
  --name agentchains-marketplace `
  --resource-group rg-agentchains `
  --image agentchainsacr.azurecr.io/agentchains-marketplace:4c9f44380659b6f11a65d1aa76be48fbbc5913fe
```

Status: READY

## Final Verdict

Overall verification result: **NO-GO (degraded)** for strict acceptance because:

1. `GET /api/v2/agents/{agent_id}/trust/public` returns `500` for missing/nonexistent IDs.
2. `GET /api/v1/agents` returns `500`.

All other core smoke, CI, and deploy checks are healthy.

## Required Follow-up

1. Triage `v2_agents` public trust endpoint error handling for nonexistent agent IDs.
2. Triage v1 agent registry list endpoint regression (`GET /api/v1/agents`).
3. Add/confirm regression tests for both endpoints to guarantee non-500 behavior.
