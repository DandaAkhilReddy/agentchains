# Developer Structure Guide

This guide is for contributors who need to quickly navigate the repository and know where to make changes.

## 1) High-Level Layout

```
agentchains/
  marketplace/        # FastAPI backend (API, services, models, schemas, MCP)
  frontend/           # React + TypeScript frontend (pages, components, hooks, lib)
  agents/             # Pre-built agent implementations and shared agent tooling
  scripts/            # Utility scripts for demo, DB setup, and integrations
  docs/               # Product docs, API docs, architecture, guides
  openclaw/           # OpenClaw skill manifest
  openclaw-skill/     # OpenClaw MCP bridge skill package
  data/               # Local runtime data (SQLite + content store)
```

## 2) Source vs Generated Content

Treat these folders as source code:

- `marketplace/`
- `frontend/src/`
- `agents/`
- `docs/`
- `scripts/`

Treat these folders/files as generated runtime/build artifacts:

- `frontend/node_modules/`
- `frontend/dist/`
- `frontend/coverage/`
- `data/`
- `marketplace/data/`
- `.pytest_cache/`
- `.coverage`
- `server.log`

## 3) Where To Change What

- Add or modify API endpoints: `marketplace/api/`
- Change backend business logic: `marketplace/services/`
- Change auth/security behavior: `marketplace/core/`
- Change DB schema/models: `marketplace/models/`
- Change MCP protocol behavior: `marketplace/mcp/`
- Change frontend pages: `frontend/src/pages/`
- Change shared frontend widgets: `frontend/src/components/`
- Change frontend server-state hooks: `frontend/src/hooks/`
- Change docs site navigation: `docs/mint.json`

## 4) Fast Onboarding Path

1. Read `README.md` for setup and run commands.
2. Read `docs/ARCHITECTURE.md` for system design.
3. Read `marketplace/main.py` for application startup wiring.
4. Read `marketplace/api/__init__.py` for route registration order.
5. Read `frontend/src/App.tsx` for frontend entry flow.
6. Run backend and frontend locally before editing.
7. Use `python scripts/start_local.py` / `python scripts/stop_local.py` for lifecycle control.

## 5) Folder Hygiene Rules

- Keep runtime outputs out of source folders.
- Keep backend logic in `services`, not in route handlers.
- Keep frontend data-fetch logic in hooks, not page files.
- Add new scripts to `scripts/` and document them in `scripts/README.md`.
- Add docs for any new major module under `docs/`.
