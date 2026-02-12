# Testing Guide

## 1. Overview

- **1,947+ total tests** (627 backend + 391 frontend + 929 pipeline-generated)
- **Backend**: pytest with pytest-asyncio (auto mode) -- all async test functions are automatically detected
- **Frontend**: Vitest with @testing-library/react and jsdom environment
- **No external services needed** -- tests use in-memory SQLite via `aiosqlite` with `StaticPool` (shared connection across sessions)

## 2. Running Tests

```bash
# Backend -- all 627 tests
python -m pytest marketplace/tests/ -v

# Backend -- specific file
python -m pytest marketplace/tests/test_token_service.py -v

# Backend -- with coverage
python -m pytest marketplace/tests/ --cov=marketplace --cov-report=html

# Frontend -- all 391 tests
cd frontend && npx vitest run

# Frontend -- watch mode (re-runs on file change)
cd frontend && npx vitest

# Frontend -- with coverage (via @vitest/coverage-v8)
cd frontend && npx vitest run --coverage
```

## 3. Backend Test Architecture

### Test Configuration

Configured in `pyproject.toml`:

```toml
[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["marketplace/tests"]
```

- **pytest-asyncio in "auto" mode**: all `async def test_*` functions are automatically treated as async tests -- no need for `@pytest.mark.asyncio` on every test (though it can be added explicitly).
- **conftest.py** provides an in-memory SQLite engine with `StaticPool`, ensuring all sessions share the same connection and committed data is visible across sessions.

### Database Lifecycle

Every test gets a clean database. The `_setup_db` fixture (autouse) runs before each test:

1. Clears all singleton caches (listing cache, content cache, agent cache)
2. Clears rate limiter buckets
3. Clears CDN hot cache and stats
4. Creates all tables via `Base.metadata.create_all`
5. After the test, drops all tables via `Base.metadata.drop_all`

### Test Categories

All 88 test files organized by category:

**Route Tests** (API endpoint testing via httpx AsyncClient):

| File | Description |
|------|-------------|
| `test_health_discovery_verification_routes.py` | Health check, agent discovery, content verification endpoints |
| `test_wallet_routes.py` | Wallet balance, deposit, withdrawal endpoints |
| `test_listings_routes.py` | Listing CRUD endpoints |
| `test_transactions_routes.py` | Transaction lifecycle endpoints |
| `test_analytics_routes.py` | Analytics and reporting endpoints |
| `test_catalog_routes.py` | Data catalog browsing endpoints |
| `test_seller_routes.py` | Seller-specific endpoints |
| `test_reputation_zkp_routes.py` | Reputation proofs and ZKP endpoints |
| `test_audit_registry_routes.py` | Audit trail and agent registry endpoints |
| `test_routing_routes.py` | Request routing endpoints |
| `test_automatch_routes.py` | Auto-matching buyer/seller endpoints |
| `test_creator_routes.py` | Creator dashboard endpoints |
| `test_express_deep_routes.py` | Express purchase flow endpoints |
| `test_redemption_routes.py` | Token redemption endpoints |
| `test_openclaw_routes.py` | OpenClaw integration endpoints |

**Service Tests** (business logic, no HTTP layer):

| File | Description |
|------|-------------|
| `test_token_service.py` | ARD token minting, transfer, burning |
| `test_token_models.py` | Token model validation and constraints |
| `test_listing_service.py` | Listing creation, search, update |
| `test_listing_service_deep.py` | Extended listing service edge cases |
| `test_transaction_service.py` | Transaction state machine |
| `test_transaction_service_deep.py` | Extended transaction scenarios |
| `test_deposit_service.py` | USDC-to-ARD deposit flow |
| `test_deposit_service_deep.py` | Extended deposit edge cases |
| `test_catalog_service.py` | Data catalog registration and search |
| `test_demand_service.py` | Demand signal detection |
| `test_demand_catalog_deep.py` | Extended demand/catalog scenarios |
| `test_router_service.py` | Request routing logic |
| `test_match_service.py` | Buyer-seller matching |
| `test_match_router_deep.py` | Extended match/router scenarios |
| `test_analytics_service.py` | Analytics aggregation |
| `test_reputation_analytics_deep.py` | Extended reputation/analytics |
| `test_seller_service.py` | Seller management |
| `test_openclaw_service.py` | OpenClaw integration logic |
| `test_openclaw_seller_deep.py` | Extended OpenClaw/seller scenarios |
| `test_zkp_service.py` | Zero-knowledge proof generation |
| `test_redemption.py` | Token redemption logic |
| `test_redemption_service_deep.py` | Extended redemption scenarios |
| `test_redemption_payout_service.py` | Payout processing |
| `test_payout_creator_deep.py` | Extended payout/creator scenarios |
| `test_payout_audit_cdn.py` | Payout audit trail and CDN |
| `test_cdn_service.py` | CDN tiered caching service |
| `test_verification_audit_service.py` | Content verification and audit |
| `test_registry_creator_service.py` | Agent registry and creator service |
| `test_creator_system.py` | Creator registration and management |
| `test_creator_lifecycle_deep.py` | Extended creator lifecycle |
| `test_payment_service_deep.py` | Extended payment scenarios |
| `test_cache_ratelimiter.py` | Cache service and rate limiter |
| `test_mcp_units.py` | MCP protocol unit tests |
| `test_mcp_deep.py` | Extended MCP scenarios |
| `test_express_tokens.py` | Express token purchase flow |
| `test_registration_tokens.py` | Agent registration with token grants |
| `test_wallet_deep.py` | Extended wallet scenarios |
| `test_storage_layer_deep.py` | HashFS content-addressable storage |

**Schema and Model Tests**:

| File | Description |
|------|-------------|
| `test_schemas_models.py` | Pydantic schema validation, model constraints |
| `test_data_serialization.py` | JSON serialization roundtrips |

**Infrastructure Tests**:

| File | Description |
|------|-------------|
| `test_core_auth_hashing.py` | JWT creation, password hashing |
| `test_exceptions_payment_storage.py` | Custom exceptions, payment, storage |
| `test_middleware_config.py` | Middleware and configuration |
| `test_middleware_websocket.py` | WebSocket middleware |
| `test_config_impact.py` | Configuration impact on behavior |
| `test_database_lifecycle.py` | Database connection lifecycle |
| `test_background_tasks.py` | Background task execution |

**Integration Tests** (cross-module flows):

| File | Description |
|------|-------------|
| `test_e2e_flows.py` | Full end-to-end purchase flows |
| `test_e2e_cross_module.py` | Cross-module integration scenarios |
| `test_express_integration.py` | Express purchase integration |
| `test_creator_integration.py` | Creator system integration |
| `test_mcp_integration.py` | MCP protocol integration |
| `test_catalog_demand_integration.py` | Catalog + demand signal integration |
| `test_reputation_zkp_integration.py` | Reputation + ZKP integration |
| `test_seller_openclaw_integration.py` | Seller + OpenClaw integration |
| `test_token_economy_integration.py` | Full token economy integration |
| `test_cross_service_pipeline.py` | Multi-service pipeline testing |

**Security Tests**:

| File | Description |
|------|-------------|
| `test_adversarial_inputs.py` | Unicode, SQL injection, XSS payloads, CRLF injection, null bytes -- invariant: never return 500 |
| `test_auth_permission_matrix.py` | Authorization matrix: who can access what |
| `test_security.py` | General security validations |
| `test_security_hardening.py` | Security hardening measures |

**Judge Tests** (3-layer review system):

The judge test suite implements a multi-dimensional review system where each "judge" validates a different aspect of system correctness:

| File | Judge | Purpose |
|------|-------|---------|
| `test_judge_security.py` | Security Judge | Authentication/authorization rejection, input sanitization, rate limiting enforcement, attack payload validation |
| `test_judge_data_integrity.py` | Data Integrity Judge | Referential integrity, no orphaned records, consistent state across tables |
| `test_judge_edge_cases.py` | Edge Cases Judge | Boundary conditions, empty inputs, max-length strings, zero values |
| `test_judge_token_economy.py` | Token Economy Judge | Fee calculations (2%), burn mechanics (50% of fee), supply conservation, peg stability |
| `test_judge_api_contracts.py` | API Contracts Judge | Response schema compliance, status codes, pagination, error format consistency |

Each judge file contains 15 focused negative-path tests. Together they form a comprehensive quality gate ensuring the system is correct from multiple independent perspectives.

**Financial Invariant Tests**:

| File | Description |
|------|-------------|
| `test_financial_invariants_deep.py` | Balance conservation, fee/burn calculations, double-entry bookkeeping, deposit/redemption lifecycle -- all assertions use `Decimal` to avoid floating-point drift |

**Concurrency Tests**:

| File | Description |
|------|-------------|
| `test_concurrency_safety.py` | Double-spend prevention, total supply conservation, ledger hash chain integrity, idempotency keys, deterministic fee (2%) and burn (50% of fee) calculations under rapid sequential operations |

**Boundary and State Machine Tests**:

| File | Description |
|------|-------------|
| `test_boundary_values.py` | Decimal precision edges, quality-score thresholds, listing schema constraints, pagination limits, HashFS content sizes, string edge cases (20 tests) |
| `test_state_machine_completeness.py` | All five state machines: Listing (active/deactivated), Transaction (initiated/paid/delivered/verified/completed/failed), Redemption (pending/completed/processing/rejected), Agent (active/deactivated), Token deposit (pending/completed/failed) -- 15 tests |

**Error Handling and Negative Path Tests**:

| File | Description |
|------|-------------|
| `test_edge_cases.py` | Cross-service edge cases (empty content, zero price, double confirm, etc.) |
| `test_error_recovery.py` | Graceful recovery from errors |
| `test_negative_path_coverage.py` | Explicit negative-path scenarios |
| `test_pagination_sorting_deep.py` | Pagination and sorting edge cases |

## 4. Frontend Test Setup

### Configuration

**`vitest.config.ts`**:

```typescript
import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: "src/test/setup.ts",
  },
});
```

**`src/test/setup.ts`** imports `@testing-library/jest-dom` for DOM matchers (e.g., `toBeInTheDocument()`) and mocks `window.matchMedia` for jsdom compatibility.

### Test Utilities

**`src/test/test-utils.tsx`** provides:

- `createTestQueryClient()` -- fresh QueryClient per test with `retry: false` and `gcTime: 0` to prevent shared state
- `createWrapper()` -- QueryClientProvider wrapper for hook tests
- `renderWithProviders(ui, options?)` -- render helper that wraps components with all necessary providers
- `mockLocalStorage()` -- in-memory localStorage mock

### Test Libraries

| Package | Purpose |
|---------|---------|
| `vitest` (v4.x) | Test runner |
| `jsdom` (v28.x) | Browser environment simulation |
| `@testing-library/react` (v16.x) | Component rendering and queries |
| `@testing-library/dom` (v10.x) | DOM query utilities |
| `@testing-library/jest-dom` (v6.x) | Custom DOM matchers |
| `@testing-library/user-event` (v14.x) | User interaction simulation |
| `@vitest/coverage-v8` (v4.x) | Code coverage via V8 |

### Frontend Test Files

**Component Tests** (`src/components/__tests__/`):

| File | Description |
|------|-------------|
| `Badge.test.tsx` | Badge variant rendering, category/status/agentType helpers |
| `StatCard.test.tsx` | Statistics card rendering |
| `DataTable.test.tsx` | Data table component |
| `TokenBalance.test.tsx` | Token balance display |
| `Toast.test.tsx` | Toast notification component |

**Hook Tests** (`src/hooks/__tests__/`):

| File | Description |
|------|-------------|
| `useAuth.test.ts` | Authentication hook |
| `useAgents.test.ts` | Agent management hook |
| `useCreatorAuth.test.ts` | Creator authentication hook |
| `useAnalytics.test.ts` | Analytics data hook |
| `useLiveFeed.test.ts` | WebSocket live feed hook |

**Page Tests** (`src/pages/__tests__/`):

| File | Description |
|------|-------------|
| `DashboardPage.test.tsx` | Main dashboard page |
| `AgentsPage.test.tsx` | Agent listing page |
| `RedemptionPage.test.tsx` | Token redemption page |
| `CreatorDashboardPage.test.tsx` | Creator dashboard page |
| `CreatorLoginPage.test.tsx` | Creator login page |

**Library Tests** (`src/lib/__tests__/`):

| File | Description |
|------|-------------|
| `api.test.ts` | API client functions |
| `format.test.ts` | Formatting utilities |
| `format-ard.test.ts` | ARD token formatting |
| `ws.test.ts` | WebSocket client |

## 5. Writing New Backend Tests

### Template

```python
"""Description of what this test file covers."""

from decimal import Decimal

import pytest
from sqlalchemy.ext.asyncio import AsyncSession


# async tests are auto-detected thanks to asyncio_mode = "auto"
async def test_my_feature(db: AsyncSession, make_agent, make_token_account, seed_platform):
    """One-line description of what this test verifies."""
    # Arrange -- set up test data using fixtures
    agent, jwt_token = await make_agent("test-agent")
    account = await make_token_account(agent.id, balance=100.0)

    # Act -- call the service under test
    from marketplace.services import token_service
    result = await token_service.get_balance(db, agent.id)

    # Assert -- verify the outcome
    assert result["balance"] == 100.0


async def test_my_api_endpoint(client, make_agent, auth_header):
    """Test an API route end-to-end."""
    # Arrange
    agent, token = await make_agent("route-tester")

    # Act
    resp = await client.get(
        "/api/v1/some-endpoint",
        headers=auth_header(token),
    )

    # Assert
    assert resp.status_code == 200
    data = resp.json()
    assert "expected_field" in data
```

### Key Patterns

- Use `db` fixture for service-layer tests (direct async SQLAlchemy session)
- Use `client` fixture for route tests (httpx AsyncClient wired to the FastAPI app)
- Use `auth_header(token)` to build `{"Authorization": "Bearer <token>"}` headers
- Use `Decimal` for all monetary assertions to avoid floating-point drift
- The `seed_platform` fixture must be included whenever token operations are tested (it creates the platform treasury account and TokenSupply singleton)

## 6. Writing New Frontend Tests

### Component Test Template

```typescript
import { describe, it, expect, vi } from "vitest";
import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { renderWithProviders } from "../../test/test-utils";
import MyComponent from "../MyComponent";

describe("MyComponent", () => {
  it("renders the title", () => {
    renderWithProviders(<MyComponent title="Hello" />);
    expect(screen.getByText("Hello")).toBeInTheDocument();
  });

  it("handles click interaction", async () => {
    const user = userEvent.setup();
    const onAction = vi.fn();

    renderWithProviders(<MyComponent onAction={onAction} />);
    await user.click(screen.getByRole("button", { name: /submit/i }));

    expect(onAction).toHaveBeenCalledOnce();
  });
});
```

### Hook Test Template

```typescript
import { describe, it, expect, vi, beforeEach } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";
import { createWrapper } from "../../test/test-utils";
import { useMyHook } from "../useMyHook";

// Mock the API module
vi.mock("../../lib/api");

describe("useMyHook", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("returns data on success", async () => {
    const { result } = renderHook(() => useMyHook(), {
      wrapper: createWrapper(),
    });

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    expect(result.current.data).toBeDefined();
  });
});
```

### Page Test Template (with mocked hooks)

```typescript
import { describe, it, expect, vi, beforeEach } from "vitest";
import { screen, waitFor } from "@testing-library/react";
import { renderWithProviders } from "../../test/test-utils";
import MyPage from "../MyPage";
import * as useMyHookModule from "../../hooks/useMyHook";

vi.mock("../../hooks/useMyHook");

describe("MyPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.spyOn(useMyHookModule, "useMyHook").mockReturnValue({
      data: { items: [] },
      isLoading: false,
      error: null,
    });
  });

  it("renders the page heading", () => {
    renderWithProviders(<MyPage />);
    expect(screen.getByText(/my page/i)).toBeInTheDocument();
  });
});
```

## 7. Test Fixtures

### Backend Fixtures (from `conftest.py`)

| Fixture | Scope | Description |
|---------|-------|-------------|
| `_setup_db` | autouse, per-test | Creates/drops all tables, clears caches, rate limiter, and CDN state |
| `db` | per-test | Fresh `AsyncSession` for direct service-layer testing |
| `client` | per-test | `httpx.AsyncClient` with `ASGITransport` wired to the FastAPI app, with DB dependency overridden to use the test database |
| `auth_header` | per-test | Callable: `auth_header(token)` returns `{"Authorization": "Bearer <token>"}` |
| `seed_platform` | per-test | Creates platform treasury account and `TokenSupply` singleton -- required for any token operation tests |
| `make_agent` | per-test | Factory: `await make_agent("name", agent_type="both")` returns `(agent, jwt_token)` |
| `make_token_account` | per-test | Factory: `await make_token_account(agent_id, balance=100.0)` returns `TokenAccount` |
| `make_listing` | per-test | Factory: `await make_listing(seller_id, price_usdc=1.0, quality_score=0.85)` returns `DataListing` with content stored in HashFS |
| `make_transaction` | per-test | Factory: `await make_transaction(buyer_id, seller_id, listing_id, amount_usdc=1.0)` returns `Transaction` |
| `make_creator` | per-test | Factory: `await make_creator(email, password, display_name)` returns `(creator, jwt_token)` |
| `make_catalog_entry` | per-test | Factory: `await make_catalog_entry(agent_id, namespace, topic)` returns `DataCatalogEntry` |
| `make_catalog_subscription` | per-test | Factory: `await make_catalog_subscription(subscriber_id, namespace_pattern)` returns `CatalogSubscription` |
| `make_search_log` | per-test | Factory: `await make_search_log(query_text, category)` returns `SearchLog` |
| `make_demand_signal` | per-test | Factory: `await make_demand_signal(query_pattern, category)` returns `DemandSignal` |

### Frontend Test Utilities (from `src/test/test-utils.tsx`)

| Utility | Description |
|---------|-------------|
| `createTestQueryClient()` | Fresh `QueryClient` with `retry: false` and `gcTime: 0` |
| `createWrapper()` | Returns a React component wrapping children in `QueryClientProvider` |
| `renderWithProviders(ui, options?)` | Renders a component wrapped with all necessary providers |
| `mockLocalStorage()` | Creates an in-memory localStorage mock with `vi.fn()` spies |

## 8. CI/CD Integration

Tests are designed to run in any CI environment. The recommended configuration:

```yaml
# Example GitHub Actions workflow
jobs:
  backend-tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      - run: pip install -e ".[dev]"
      - run: python -m pytest marketplace/tests/ -v --cov=marketplace --cov-report=html

  frontend-tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: "20"
      - run: cd frontend && npm ci
      - run: cd frontend && npx vitest run --coverage
```

Both backend and frontend test suites must pass before merging. Coverage reports are generated via `--cov` (backend, pytest-cov) and `--coverage` (frontend, @vitest/coverage-v8).
