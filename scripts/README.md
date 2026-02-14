# Scripts Index

This folder contains operational and utility scripts for local development.

## Available Scripts

- `generate_keys.py`
  - Generates key material used by local/testing flows.
- `reset_db.py`
  - Resets local database state.
- `seed_db.py`
  - Seeds baseline marketplace entities.
- `seed_demand.py`
  - Seeds demand-signal data for analytics/testing.
- `run_demo.py`
  - Runs an end-to-end scripted demo against a running backend.
- `test_e2e.py`
  - Runs E2E-style API verification.
- `test_azure.py`
  - Runs Azure-integration related checks.
- `test_adk_agents.py`
  - Runs ADK/agent integration checks.

## Usage Pattern

Run scripts from repository root so relative imports and paths resolve consistently:

```bash
python scripts/run_demo.py
python scripts/seed_db.py
```

## Maintenance Rules

- Keep scripts idempotent where possible.
- Prefer explicit arguments over hardcoded constants.
- Document new scripts here when added.
