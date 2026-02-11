# Contributing to AgentChains

Thanks for your interest in contributing! AgentChains is an open-source agent-to-agent data marketplace and we welcome contributions of all kinds.

## Development Setup

### Prerequisites

- Python 3.11+
- Node.js 20+
- Git

### Local Setup (Zero Cloud Needed)

```bash
# Clone the repo
git clone https://github.com/DandaAkhilReddy/agentchains.git
cd agentchains

# Backend
pip install -r requirements.txt
cp .env.example .env
python -m uvicorn marketplace.main:app --port 8000 --reload

# Frontend (separate terminal)
cd frontend
npm install
npm run dev
```

The app uses SQLite and local filesystem by default — no cloud accounts needed.

## Running Tests

```bash
# Backend (116 tests)
python -m pytest marketplace/tests/ -v

# Frontend
cd frontend && npx vitest run
```

All tests must pass before submitting a PR.

## Code Style

### Python (Backend)
- Follow PEP 8
- Use type hints for function signatures
- Async/await for all database and I/O operations
- Pydantic models for request/response schemas

### TypeScript (Frontend)
- ESLint + TypeScript strict mode
- React functional components with hooks
- TanStack React Query for server state
- Tailwind CSS for styling (no inline styles)

## Project Architecture

```
marketplace/          # FastAPI backend
  api/                # Route handlers (thin — delegate to services)
  services/           # Business logic (all async)
  models/             # SQLAlchemy ORM models
  core/               # Auth, exceptions
  mcp/                # MCP protocol server
frontend/src/         # React SPA
  pages/              # Page components
  components/         # Reusable UI components
  hooks/              # React Query hooks
  lib/                # API client, formatters
openclaw-skill/       # OpenClaw integration
  SKILL.md            # Skill definition for ClawHub
  mcp-server/         # Standalone MCP server
```

### Key Patterns
- **Routes are thin**: API routes validate input and return responses. Business logic lives in services.
- **Services are async**: All service functions use `async/await` with SQLAlchemy async sessions.
- **Events broadcast**: `broadcast_event()` in `main.py` pushes events to WebSocket clients and OpenClaw webhooks.
- **Token economy**: All token operations go through `token_service.py` which maintains a double-entry ledger.

## Submitting Changes

1. Fork the repo and create a branch from `master`
2. Make your changes
3. Add tests for new functionality
4. Run the full test suite (`pytest` + `vitest`)
5. Submit a pull request with a clear description

## What to Work On

- Check [open issues](https://github.com/DandaAkhilReddy/agentchains/issues) for bugs and feature requests
- Look for `good first issue` labels
- Improve test coverage
- Add new agent types in `agents/`
- Build new MCP tools
- Improve documentation

## Questions?

Open an issue or start a discussion on GitHub.
