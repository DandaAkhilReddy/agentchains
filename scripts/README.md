# Scripts Index

This folder contains operational and utility scripts for local development.

## Available Scripts

- `generate_keys.py`
  - Generates key material used by local/testing flows.
- `reset_db.py`
  - Resets local database state.
  - Optional: `--purge-content-store` removes local cached content artifacts.
- `seed_db.py`
  - Seeds baseline marketplace entities.
- `seed_demand.py`
  - Seeds demand-signal data for analytics/testing.
- `run_demo.py`
  - Runs an end-to-end scripted demo against a running backend.
- `test_e2e.py`
  - Runs E2E-style API verification.
- `test_azure.py`
  - Runs deployment E2E checks against `MARKETPLACE_URL` (defaults to local).
- `test_adk_agents.py`
  - Runs ADK/agent integration checks.
- `start_local.py`
  - Starts backend and frontend locally and stores PIDs in `.local/`.
- `stop_local.py`
  - Stops backend/frontend using PID files in `.local/`.
- `judge_merge_gate.py`
  - Runs Agent 51 merge-gate evaluation and writes `docs/reports/judge_51_final_verdict.md`.

## Usage Pattern

Run scripts from repository root so relative imports and paths resolve consistently:

```bash
python scripts/run_demo.py
python scripts/seed_db.py
python scripts/start_local.py
python scripts/stop_local.py
python scripts/judge_merge_gate.py
```

E2E scripts target local by default, but can be pointed at another deployment:

```bash
set MARKETPLACE_URL=https://your-deployment.example.com
python scripts/test_azure.py
```

Safety guard for mutating integration scripts:
- `test_e2e.py`, `test_adk_agents.py`, and `test_azure.py` refuse non-local targets by default.
- To intentionally run against a remote deployment, set:

```bash
set ALLOW_REMOTE_MUTATING_TESTS=1
```

## Maintenance Rules

- Keep scripts idempotent where possible.
- Prefer explicit arguments over hardcoded constants.
- Document new scripts here when added.
