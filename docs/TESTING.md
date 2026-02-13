# Testing Guide

## Overview

AgentChains maintains a comprehensive test suite with **2,745+ total tests** across the full stack:

| Layer    | Framework                        | Tests  | Files |
|----------|----------------------------------|--------|-------|
| Backend  | pytest + pytest-asyncio          | 2,369 passing + 2 xfail | 120 |
| Frontend | vitest + React Testing Library   | 376 passing | 19 |

- **Backend**: Fully async test suite using SQLAlchemy async sessions and httpx `AsyncClient` against the FastAPI app. In-memory SQLite via `StaticPool` -- no external database required.
- **Frontend**: Component, hook, and utility tests using vitest with jsdom environment and `@testing-library/react`.

---

## Quick Commands

```bash
# Run all backend tests
python -m pytest marketplace/tests/ -v

# Run all frontend tests
cd frontend && npx vitest run

# Run both (CI-equivalent)
python -m pytest marketplace/tests/ -q --tb=short -x && cd frontend && npx vitest run
```

---

## Backend Testing

### Setup

- Tests use an **in-memory SQLite** database with `StaticPool` (automatic, no config needed).
- `conftest.py` creates and drops all tables for **every test** via an `autouse` fixture.
- All singleton caches (listing, content, agent), rate limiter buckets, and CDN hot cache are cleared before each test to ensure isolation.
- All tests are async -- `asyncio_mode = "auto"` is configured in `pyproject.toml`, so `@pytest.mark.asyncio` is not required on individual tests.

### Running Tests

```bash
# All tests (verbose)
python -m pytest marketplace/tests/ -v

# Single file
python -m pytest marketplace/tests/test_listings_routes.py -v

# By keyword
python -m pytest marketplace/tests/ -k "test_express" -v

# With coverage
python -m pytest marketplace/tests/ --cov=marketplace --cov-report=term-missing

# Stop on first failure (fast feedback)
python -m pytest marketplace/tests/ -x --tb=short

# Quiet mode (CI-style)
python -m pytest marketplace/tests/ -q --tb=short -x
```

### Test Categories

| Category | File Pattern | What They Test |
|----------|-------------|----------------|
| **Route tests** | `test_*_routes*.py` (e.g., `test_listings_routes.py`, `test_wallet_routes.py`, `test_seller_routes.py`) | HTTP endpoint behavior -- status codes, request/response schemas, auth enforcement |
| **Service tests** | `test_*_service*.py` (e.g., `test_listing_service.py`, `test_token_service.py`, `test_zkp_service.py`) | Business logic in isolation -- service-layer functions called directly |
| **Integration tests** | `test_e2e_*.py`, `test_*_integration.py` (e.g., `test_e2e_flows.py`, `test_token_economy_integration.py`) | Cross-module flows -- full purchase pipelines, multi-service interactions |
| **Judge tests** | `test_judge_*.py` (e.g., `test_judge_security.py`, `test_judge_token_economy.py`, `test_judge_api_contracts.py`) | Security invariants, financial correctness, API contract compliance |
| **Edge case tests** | `test_adversarial_*.py`, `test_boundary_*.py`, `test_edge_cases.py` | Boundary values, malicious input, schema validation edge cases |
| **Deep tests** | `test_*_deep.py` (e.g., `test_match_router_deep.py`, `test_wallet_deep.py`) | Thorough coverage of a single module -- pagination, sorting, error paths |
| **Unit tests** | `test_*_unit.py` (e.g., `test_reputation_service_unit.py`, `test_payment_service_unit.py`) | Focused unit tests for individual functions or classes |
| **Concurrency tests** | `test_concurrent_financial_ops.py` | Race conditions, deadlock prevention, concurrent transfer consistency |
| **Infrastructure tests** | `test_cache_ratelimiter.py`, `test_cdn_service.py`, `test_middleware_websocket.py` | Caching, rate limiting, CDN tiers, WebSocket resilience |

### Test Fixtures (from `conftest.py`)

All core fixtures are defined in `marketplace/tests/conftest.py`:

| Fixture | Type | Description |
|---------|------|-------------|
| `_setup_db` | `autouse` | Creates/drops all tables per test; clears caches, rate limiter, CDN state |
| `db` | `AsyncSession` | Fresh SQLAlchemy async session for direct service-layer calls |
| `client` | `httpx.AsyncClient` | HTTP test client wired to the FastAPI app with DB override via `ASGITransport` |
| `auth_header` | callable | Returns a callable `_build(token) -> {"Authorization": "Bearer {token}"}` |
| `seed_platform` | async | Creates the platform treasury account |
| `make_agent` | async factory | Creates a `RegisteredAgent` and returns `(agent, jwt_token)` |
| `make_token_account` | async factory | Creates a `TokenAccount` with a specified balance |
| `make_listing` | async factory | Creates a `DataListing` with content stored in storage |
| `make_transaction` | async factory | Creates a `Transaction` between buyer and seller |
| `make_creator` | async factory | Registers a `Creator` with hashed password and returns `(creator, jwt_token)` |
| `make_catalog_entry` | async factory | Creates a `DataCatalogEntry` in a namespace/topic |
| `make_catalog_subscription` | async factory | Creates a `CatalogSubscription` with pattern matching |
| `make_search_log` | async factory | Creates a `SearchLog` entry |
| `make_demand_signal` | async factory | Creates a `DemandSignal` with velocity and fulfillment metrics |

### Known xfails

There are **2 xfail tests** in `test_concurrent_financial_ops.py`:

1. **`test_concurrent_transfers_between_same_pair`** -- Two transfers from A to B executed concurrently. Marked `xfail` because SQLite serializes concurrent writes; passes on PostgreSQL.
2. **`test_deadlock_prevention_via_sorted_lock_order`** -- A to B and B to A transfers execute without deadlock. Marked `xfail` for the same SQLite limitation; passes on PostgreSQL.

Both use `strict=False`, meaning they are allowed to either pass or fail depending on the database backend.

---

## Frontend Testing

### Setup

- Uses **jsdom** environment (simulates browser DOM) -- configured in `frontend/vitest.config.ts`.
- `@testing-library/react` for component rendering.
- `@testing-library/user-event` for simulating user interactions.
- `@testing-library/jest-dom` for extended DOM assertions (e.g., `toBeInTheDocument()`).
- Global setup file at `frontend/src/test/setup.ts` mocks `window.matchMedia` for jsdom compatibility.
- Vitest globals are enabled (`globals: true`), so `describe`, `it`, `expect`, and `vi` are available without imports.

### Running Tests

```bash
cd frontend

# Single run
npx vitest run

# Watch mode (re-runs on file changes)
npx vitest

# With coverage report (uses @vitest/coverage-v8)
npx vitest run --coverage

# Run a specific test file
npx vitest run src/pages/__tests__/DashboardPage.test.tsx
```

Or use the npm scripts defined in `package.json`:

```bash
cd frontend
npm test              # same as vitest run
npm run test:watch    # same as vitest (watch mode)
npm run test:coverage # same as vitest run --coverage
```

### Test Structure

Tests are co-located with source code in `__tests__/` directories:

```
frontend/src/
  pages/__tests__/
    AgentsPage.test.tsx
    CreatorDashboardPage.test.tsx
    CreatorLoginPage.test.tsx
    DashboardPage.test.tsx
    RedemptionPage.test.tsx
  components/__tests__/
    Badge.test.tsx
    DataTable.test.tsx
    StatCard.test.tsx
    Toast.test.tsx
    TokenBalance.test.tsx
  hooks/__tests__/
    useAgents.test.ts
    useAnalytics.test.ts
    useAuth.test.ts
    useCreatorAuth.test.ts
    useLiveFeed.test.ts
  lib/__tests__/
    api.test.ts
    format.test.ts
    format-usd.test.ts
    ws.test.ts
```

---

## Adding New Tests

### Backend Test Template

```python
import pytest
from httpx import AsyncClient


async def test_my_feature(client: AsyncClient, auth_header, make_agent):
    """Test description of what this verifies."""
    agent, token = await make_agent("test-agent")
    headers = auth_header(token)

    response = await client.get("/api/v1/my-endpoint", headers=headers)

    assert response.status_code == 200
    data = response.json()
    assert "expected_field" in data
```

Notes:
- No `@pytest.mark.asyncio` needed -- `asyncio_mode = "auto"` handles it.
- Use factory fixtures (`make_agent`, `make_listing`, etc.) to set up test data.
- The `client` fixture already has the test DB wired in.

### Frontend Test Template

```typescript
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect, vi } from "vitest";
import MyComponent from "../MyComponent";

describe("MyComponent", () => {
  it("renders correctly", () => {
    render(<MyComponent />);
    expect(screen.getByText("Expected Text")).toBeInTheDocument();
  });

  it("handles user interaction", async () => {
    const user = userEvent.setup();
    render(<MyComponent onSubmit={vi.fn()} />);

    await user.click(screen.getByRole("button", { name: /submit/i }));
    // assert expected behavior
  });
});
```

Notes:
- Vitest globals are enabled, but explicit imports from `vitest` are recommended for clarity.
- Use `@testing-library/user-event` (not `fireEvent`) for realistic user interaction simulation.

---

## CI/CD Integration

The GitHub Actions workflow at `.github/workflows/ci.yml` runs on every push to `main` and on pull requests targeting `main`.

### Backend Job (`backend-test`)

| Step | Command |
|------|---------|
| Setup | Python 3.11, pip cache |
| Install | `pip install -r requirements.txt` |
| Lint | `ruff check marketplace/` |
| Test | `pytest marketplace/tests/ -q --tb=short -x` |

### Frontend Job (`frontend-test`)

| Step | Command |
|------|---------|
| Setup | Node 20, npm cache |
| Install | `npm ci` |
| Type check | `npx tsc --noEmit` |
| Test | `npx vitest run` |
| Build | `npm run build` |

All steps must pass before a pull request can be merged.

---

## Linting & Type Checking

```bash
# Python linting (ruff)
pip install ruff
ruff check marketplace/

# TypeScript type checking
cd frontend && npx tsc --noEmit

# Frontend ESLint
cd frontend && npm run lint
```

---

## Full Verification

Run the complete CI-equivalent check locally before pushing:

```bash
# Backend: lint + test
ruff check marketplace/ && python -m pytest marketplace/tests/ -q --tb=short -x

# Frontend: types + test + build
cd frontend && npx tsc --noEmit && npx vitest run && npm run build
```
