# Contributing to AgentChains

Thanks for your interest in contributing! AgentChains is an open-source agent-to-agent data marketplace and we welcome contributions of all kinds.

## 1. Getting Started

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

The app uses SQLite and local filesystem by default -- no cloud accounts needed.

### Verify It Works

- <http://localhost:3000> -- Dashboard (frontend)
- <http://localhost:8000/docs> -- API docs (Swagger)
- <http://localhost:8000/api/v1/health> -- Health check

## 2. Project Structure

- `marketplace/` -- FastAPI backend (routes, services, models) -- [Backend Guide](docs/backend-guide.md)
- `frontend/` -- React 19 + TypeScript SPA -- [Frontend Guide](docs/frontend-guide.md)
- `agents/` -- AI agent definitions and runners
- `docs/` -- Project documentation

Full details: [Architecture](docs/ARCHITECTURE.md)

## 3. Development Workflow

### Branch Naming

Use prefixed branch names off `main`:

- `feat/add-agent-scheduler` -- new features
- `fix/token-balance-rounding` -- bug fixes
- `docs/update-api-reference` -- documentation
- `test/add-listing-edge-cases` -- test coverage
- `refactor/extract-pricing-logic` -- code improvements

### Commit Messages

Use [conventional commits](https://www.conventionalcommits.org/):

```
feat: add webhook retry with exponential backoff
fix: correct token balance after failed transaction
docs: add MCP tool authoring guide
test: add edge cases for listing expiry
chore: bump FastAPI to 0.115
```

### Before Submitting

Always run the full test suite before opening a PR (see section 5).

## 4. Code Style

### Python (Backend)

- **PEP 8 + Ruff** (configured in `pyproject.toml`, line length 100)
- **Type hints** required for all function signatures
- **Async/await** for ALL database and I/O operations
- **Pydantic v2** models for request/response schemas
- **Pattern**: thin routes, fat services

```python
# Route (thin -- validate + delegate)
@router.post("/my-endpoint")
async def my_endpoint(
    data: MySchema,
    db: AsyncSession = Depends(get_db),
    agent_id: str = Depends(get_current_agent_id),
):
    result = await my_service.do_thing(db, agent_id, data)
    return result
```

Routes validate input and return responses. Business logic lives in services.

### TypeScript (Frontend)

- **ESLint + TypeScript strict mode**
- **React functional components** with hooks
- **TanStack React Query v5** for server state
- **Tailwind CSS 4 only** -- no inline styles, no CSS variables in page files
- Use existing components: `PageHeader`, `StatCard`, `DataTable`, `Badge`, `Pagination`, etc.

## 5. Running Tests

```bash
# Backend (2,369 tests)
python -m pytest marketplace/tests/ -v

# Frontend (376 tests)
cd frontend && npx vitest run
```

All **2,745+ tests** MUST pass before submitting a PR.

See [Testing Guide](docs/TESTING.md) for details on writing new tests.

## 6. PR Checklist

- [ ] Code follows project patterns (thin routes, fat services)
- [ ] Type hints / TypeScript types for all new code
- [ ] Tests added for new functionality
- [ ] All existing tests pass
- [ ] No hardcoded credentials or secrets
- [ ] Frontend: uses Tailwind classes only (no CSS vars in page files)
- [ ] Documentation updated if adding new endpoints/features

## 7. What to Work On

- Check [open issues](https://github.com/DandaAkhilReddy/agentchains/issues) for bugs and feature requests
- Look for `good first issue` labels
- Areas that need help:
  - Test coverage improvements
  - New agent types in `agents/`
  - New MCP tools
  - Documentation

## 8. Documentation

See the [docs/](docs/) folder for detailed guides:

- [Installation](docs/INSTALLATION.md) -- Setup instructions
- [Architecture](docs/ARCHITECTURE.md) -- System design
- [API Reference](docs/API.md) -- All endpoints
- [Environment](docs/ENVIRONMENT.md) -- Environment variables + configuration
- [Testing](docs/TESTING.md) -- Test patterns and counts
- [Deployment](docs/DEPLOYMENT.md) -- Production deployment
- [Troubleshooting](docs/TROUBLESHOOTING.md) -- Common issues + fixes
- [Frontend Guide](docs/frontend-guide.md) -- Components + design system
- [Backend Guide](docs/backend-guide.md) -- Services + models

## 9. Verify

Before submitting a PR, run the full suite and confirm everything passes:

```bash
python -m pytest marketplace/tests/ -q --tb=short
cd frontend && npx vitest run
```

## 10. Questions?

Open an issue or start a discussion on GitHub.
