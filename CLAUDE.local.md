# Local Development Preferences

## Environment
- Python: 3.11+ (system install)
- Node: 20 LTS
- Package manager: pip + npm
- Editor: VS Code / Claude Code CLI

## Quick Commands
- Backend tests: `pytest marketplace/tests/ -x -q`
- Frontend tests: `cd frontend && npx vitest run`
- Lint Python: `ruff check marketplace/`
- Format Python: `ruff format marketplace/`
- Start backend: `uvicorn marketplace.main:app --reload`
- Start frontend: `cd frontend && npm run dev`

## Database
- Local SQLite at `data/marketplace.db`
- Async driver: aiosqlite
