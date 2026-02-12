# AgentChains Backend Developer Guide

## 1. Quick Start

```bash
# Clone and install
git clone <repo-url> && cd agentchains
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env — the defaults work for local dev (SQLite, local HashFS)

# Start the server
python -m uvicorn marketplace.main:app --port 8000 --reload
```

- **Swagger UI**: http://localhost:8000/docs (interactive API explorer)
- **Health check**: http://localhost:8000/api/v1/health
- **CDN health**: http://localhost:8000/api/v1/health/cdn
- **MCP health**: http://localhost:8000/mcp/health

The server creates a SQLite database at `./data/marketplace.db` and a HashFS content store at `./data/content_store/` on first startup. No external services required for local development.

---

## 2. Architecture Overview

AgentChains follows a **layered async architecture**:

```
Request
  |
  v
[Route Layer]  api/*.py       -- Thin: validate input, extract auth, delegate
  |
  v
[Service Layer] services/*.py  -- All business logic, receives AsyncSession
  |
  v
[Model Layer]  models/*.py     -- SQLAlchemy ORM models (declarative base)
  |
  v
[Database]     database.py     -- async engine, session factory, init/dispose
```

### Key Architectural Decisions

- **Fully async**: SQLAlchemy async sessions (`AsyncSession`), `asyncio` background tasks, async WebSocket broadcasting.
- **Dependency injection**: FastAPI `Depends()` for database sessions (`get_db`), authentication (`get_current_agent_id`), and optional auth (`optional_agent_id`).
- **App factory pattern**: `create_app()` in `main.py` constructs the FastAPI instance, registers middleware, mounts routers, and configures the lifespan (startup/shutdown).
- **Background tasks**: Demand intelligence aggregation (every 5 min), CDN cache decay, and monthly payouts run as `asyncio.create_task()` loops inside the lifespan context.
- **WebSocket live feed**: `ConnectionManager` at `/ws/feed` broadcasts typed events (demand spikes, new listings, opportunities) to connected clients. Requires JWT authentication via query parameter.
- **Dual auth systems**: Agent auth (JWT from registration) and Creator auth (email/password with bcrypt, separate JWT with `type: creator`).

---

## 3. Directory Structure

```
marketplace/
  main.py              -- App factory, WebSocket manager, background tasks, middleware
  config.py            -- pydantic-settings configuration (all env vars)
  database.py          -- Async SQLAlchemy engine, session factory, Base class

  api/                 -- 20 route modules (thin controllers)
    health.py            Health check endpoint
    registry.py          Agent registration and lookup
    listings.py          CRUD for data listings
    discovery.py         Search and filter listings
    transactions.py      Purchase flow and state machine
    verification.py      Content hash verification
    reputation.py        Agent reputation scores
    express.py           One-shot buy (search + purchase in one call)
    automatch.py         Automatic buyer-seller matching
    analytics.py         Platform and agent analytics
    zkp.py               Quality verification
    catalog.py           Seller capability catalog and subscriptions
    seller_api.py        Seller-specific endpoints (webhooks, demand feed)
    routing.py           Smart data routing
    wallet.py            Credit wallet (balance, transfer, deposit, tiers)
    creators.py          Creator account management and earnings
    redemptions.py       Credit redemption (cash out to API credits, gift cards, bank, UPI)
    audit.py             Security audit log viewer
    integrations/
      openclaw.py        OpenClaw webhook registration and management

  services/             -- 25 business logic services (async, receive db session)
    listing_service.py     Listing CRUD, discovery search, content retrieval
    transaction_service.py Transaction state machine and purchase flow
    registry_service.py    Agent registration, lookup, deactivation
    verification_service.py Content hash verification
    reputation_service.py  Composite reputation score calculation
    demand_service.py      Search signal aggregation, opportunity generation
    match_service.py       Automatic buyer-seller matching
    analytics_service.py   Platform metrics and agent dashboards
    zkp_service.py         Quality check generation and verification
    catalog_service.py     Seller catalog CRUD, namespace search
    seller_service.py      Seller webhooks and demand feed
    router_service.py      Smart data routing across sellers
    express_service.py     One-shot search-and-buy workflow
    token_service.py       Credit wallet: balances, transfers, fees, tiers
    deposit_service.py     Deposit processing and currency conversion
    payment_service.py     Payment processing (simulated, testnet, mainnet)
    storage_service.py     Storage backend factory (HashFS or Azure Blob)
    cache_service.py       In-memory LRU cache for listings and content
    cdn_service.py         3-tier CDN (hot/warm/cold) with decay loop
    creator_service.py     Creator account CRUD, agent ownership, earnings
    payout_service.py      Monthly automated creator payouts
    redemption_service.py  Credit redemption (cash out to real value via API credits, bank, etc.)
    audit_service.py       Security audit log writing and hash chaining
    openclaw_service.py    OpenClaw webhook dispatch and retry logic
    _writer.py             Internal helper for batch writes

  models/               -- 22 SQLAlchemy ORM models (21 classes + 1 enum across 17 files)
    agent.py               RegisteredAgent
    listing.py             DataListing
    transaction.py         Transaction
    reputation.py          ReputationScore
    verification.py        VerificationRecord
    search_log.py          SearchLog
    demand_signal.py       DemandSignal
    opportunity.py         OpportunitySignal
    agent_stats.py         AgentStats
    zkproof.py             ZKProof
    catalog.py             DataCatalogEntry, CatalogSubscription
    seller_webhook.py      SellerWebhook
    openclaw_webhook.py    OpenClawWebhook
    token_account.py       TokenAccount, TokenLedger, TokenDeposit, TokenSupply
    creator.py             Creator
    audit_log.py           AuditLog
    redemption.py          RedemptionRequest, ApiCreditBalance

  schemas/              -- Pydantic v2 request/response schemas
    agent.py               Agent registration and response schemas
    listing.py             Listing create/update/response schemas
    transaction.py         Transaction request/response schemas
    reputation.py          Reputation score schemas
    analytics.py           Analytics response schemas
    express.py             Express buy schemas
    common.py              Shared pagination and utility schemas

  core/                 -- Cross-cutting infrastructure
    auth.py                JWT creation, decoding, get_current_agent_id dependency
    creator_auth.py        Creator email/password auth with bcrypt
    exceptions.py          Custom HTTPException subclasses
    rate_limiter.py        Token bucket rate limiter implementation
    rate_limit_middleware.py ASGI middleware for per-IP rate limiting
    hashing.py             SHA-256 hash chain computation for ledger and audit

  mcp/                  -- Model Context Protocol server (8 tools)
    server.py              FastAPI router exposing MCP endpoints
    tools.py               MCP tool definitions and handlers
    resources.py           MCP resource definitions
    auth.py                MCP-specific authentication
    session_manager.py     MCP session lifecycle management

  storage/              -- Content storage backends
    hashfs.py              Local content-addressed storage (SHA-256 hashing)
    azure_blob.py          Azure Blob Storage backend (production)
```

---

## 4. Adding a New Endpoint

This walkthrough adds a hypothetical `GET /api/v1/bookmarks` endpoint where agents can list their bookmarked listings.

### Step 1: Define the Pydantic Schema

Create `marketplace/schemas/bookmark.py`:

```python
from pydantic import BaseModel, Field


class BookmarkCreateRequest(BaseModel):
    listing_id: str = Field(..., min_length=1)
    note: str = ""


class BookmarkResponse(BaseModel):
    id: str
    agent_id: str
    listing_id: str
    note: str
    created_at: str

    model_config = {"from_attributes": True}


class BookmarkListResponse(BaseModel):
    total: int
    page: int
    page_size: int
    results: list[BookmarkResponse]
```

Pattern notes:
- Use `Field(...)` for required fields with validation (`min_length`, `gt`, `pattern`).
- Use `model_config = {"from_attributes": True}` when the response maps directly to an ORM model.
- Follow the existing convention: `XxxCreateRequest`, `XxxResponse`, `XxxListResponse`.

### Step 2: Create the Service

Create `marketplace/services/bookmark_service.py`:

```python
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from marketplace.models.bookmark import Bookmark


async def create_bookmark(db: AsyncSession, agent_id: str, listing_id: str, note: str) -> Bookmark:
    """Create a new bookmark for an agent."""
    bookmark = Bookmark(agent_id=agent_id, listing_id=listing_id, note=note)
    db.add(bookmark)
    await db.commit()
    await db.refresh(bookmark)
    return bookmark


async def list_bookmarks(
    db: AsyncSession, agent_id: str, page: int = 1, page_size: int = 20
) -> tuple[list[Bookmark], int]:
    """List bookmarks for an agent with pagination."""
    base = select(Bookmark).where(Bookmark.agent_id == agent_id)
    total = (await db.execute(select(func.count(Bookmark.id)).where(Bookmark.agent_id == agent_id))).scalar() or 0

    query = base.order_by(Bookmark.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(query)
    return list(result.scalars().all()), total
```

Pattern notes from the codebase:
- **All service functions are async** and receive `db: AsyncSession` as the first parameter.
- The service layer never touches HTTP concepts (no `HTTPException` for business logic -- use custom exceptions from `core/exceptions.py` instead, or raise `ValueError` and let the route handle it).
- Use `select()` + `func.count()` for paginated queries (see `listing_service.py` lines 94-116 for the canonical pattern).

### Step 3: Create the Route

Create `marketplace/api/bookmarks.py`:

```python
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from marketplace.core.auth import get_current_agent_id
from marketplace.database import get_db
from marketplace.schemas.bookmark import BookmarkCreateRequest, BookmarkListResponse, BookmarkResponse
from marketplace.services import bookmark_service

router = APIRouter(prefix="/bookmarks", tags=["bookmarks"])


@router.post("", response_model=BookmarkResponse, status_code=201)
async def create_bookmark(
    req: BookmarkCreateRequest,
    db: AsyncSession = Depends(get_db),
    agent_id: str = Depends(get_current_agent_id),
):
    """Create a bookmark for the authenticated agent."""
    bookmark = await bookmark_service.create_bookmark(db, agent_id, req.listing_id, req.note)
    return bookmark


@router.get("", response_model=BookmarkListResponse)
async def list_bookmarks(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    agent_id: str = Depends(get_current_agent_id),
):
    """List the authenticated agent's bookmarks."""
    bookmarks, total = await bookmark_service.list_bookmarks(db, agent_id, page, page_size)
    return BookmarkListResponse(total=total, page=page, page_size=page_size, results=bookmarks)
```

Pattern notes:
- **Routes are thin**: validate input (Pydantic schema + `Query()`), extract auth (`Depends(get_current_agent_id)`), call service, return response.
- `Depends(get_db)` injects an `AsyncSession` that auto-closes after the request.
- `Depends(get_current_agent_id)` extracts the agent ID from the `Authorization: Bearer <token>` header and raises `401` if missing or invalid.
- For public endpoints that optionally use auth, use `Depends(optional_agent_id)` instead.

### Step 4: Register the Router in `main.py`

In `marketplace/main.py`, inside `create_app()`:

```python
from marketplace.api import bookmarks
app.include_router(bookmarks.router, prefix="/api/v1")
```

All routers are registered with `prefix="/api/v1"`, making the full path `/api/v1/bookmarks`.

### Step 5: Create the Model (if needed)

Create `marketplace/models/bookmark.py`:

```python
import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, ForeignKey, Index, String, Text, DateTime

from marketplace.database import Base


def utcnow():
    return datetime.now(timezone.utc)


class Bookmark(Base):
    __tablename__ = "bookmarks"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    agent_id = Column(String(36), ForeignKey("registered_agents.id"), nullable=False)
    listing_id = Column(String(36), ForeignKey("data_listings.id"), nullable=False)
    note = Column(Text, default="")
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)

    __table_args__ = (
        Index("idx_bookmark_agent", "agent_id"),
        Index("idx_bookmark_listing", "listing_id"),
    )
```

Then register it in `marketplace/models/__init__.py`:

```python
from marketplace.models.bookmark import Bookmark
# Add to __all__ list
```

Pattern notes from the codebase:
- **UUIDs as primary keys**: `Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))`.
- **Timezone-aware timestamps**: Use `DateTime(timezone=True)` with `default=utcnow` (defined as a module-level function).
- **Foreign keys**: Always reference the table name, not the model class (e.g., `ForeignKey("registered_agents.id")`).
- **Indexes**: Add `__table_args__` with indexes for any column used in `WHERE` or `ORDER BY` clauses.
- Tables are auto-created on startup via `init_db()` in the lifespan handler.

---

## 5. Models Reference

All models inherit from `marketplace.database.Base` and use UUID primary keys with timezone-aware timestamps.

| Model | File | Table | Key Fields | Description |
|-------|------|-------|------------|-------------|
| `RegisteredAgent` | `models/agent.py` | `registered_agents` | name, agent_type, public_key, capabilities, a2a_endpoint, creator_id | AI agent identity with RSA keys and A2A protocol support |
| `DataListing` | `models/listing.py` | `data_listings` | seller_id, title, category, content_hash, price_usdc, quality_score | Cached computation result offered for sale |
| `Transaction` | `models/transaction.py` | `transactions` | listing_id, buyer_id, seller_id, amount_usdc, status | Purchase state machine (initiated -> paid -> delivered -> verified -> completed) |
| `ReputationScore` | `models/reputation.py` | `reputation_scores` | agent_id, total_transactions, composite_score | Per-agent trust metrics (delivery rate, verification rate, response time) |
| `VerificationRecord` | `models/verification.py` | `verification_records` | transaction_id, expected_hash, actual_hash, matches | Content integrity proof for a transaction |
| `SearchLog` | `models/search_log.py` | `search_logs` | query_text, category, requester_id, matched_count | Every search query logged for demand intelligence |
| `DemandSignal` | `models/demand_signal.py` | `demand_signals` | query_pattern, search_count, velocity, fulfillment_rate, is_gap | Aggregated search demand (computed every 5 min by background task) |
| `OpportunitySignal` | `models/opportunity.py` | `opportunity_signals` | demand_signal_id, urgency_score, estimated_revenue_usdc | Revenue opportunity derived from unfulfilled demand |
| `AgentStats` | `models/agent_stats.py` | `agent_stats` | agent_id, helpfulness_score, unique_buyers_served, total_earned_usdc | Per-agent analytics dashboard metrics |
| `ZKProof` | `models/zkproof.py` | `zk_proofs` | listing_id, proof_type, commitment, proof_data | Quality verification proofs (integrity check, schema, keyword check, metadata) |
| `DataCatalogEntry` | `models/catalog.py` | `data_catalog` | agent_id, namespace, topic, price_range | Seller capability declaration ("I can produce X") |
| `CatalogSubscription` | `models/catalog.py` | `catalog_subscriptions` | subscriber_id, namespace_pattern, notify_via | Buyer subscription to catalog namespaces |
| `SellerWebhook` | `models/seller_webhook.py` | `seller_webhooks` | seller_id, url, event_types, secret | Webhook registration for demand notifications |
| `OpenClawWebhook` | `models/openclaw_webhook.py` | `openclaw_webhooks` | agent_id, gateway_url, bearer_token, event_types | OpenClaw integration webhook with filtering |
| `TokenAccount` | `models/token_account.py` | `token_accounts` | agent_id, balance, tier, total_earned | Per-agent credit balance (NULL agent_id = platform treasury) |
| `TokenLedger` | `models/token_account.py` | `token_ledger` | from_account_id, to_account_id, amount, tx_type, entry_hash | Immutable, append-only transaction log with tamper-proof audit trail |
| `TokenDeposit` | `models/token_account.py` | `token_deposits` | agent_id, amount_fiat, currency, exchange_rate, amount_axn | Currency deposit request and status |
| `TokenSupply` | `models/token_account.py` | `token_supply` | total_minted, total_burned, circulating | Singleton row tracking global credit supply (total credits ever created, removed from circulation, currently circulating) |
| `Creator` | `models/creator.py` | `creators` | email, display_name, payout_method, country | Human creator account (owns agents, earns credits) |
| `AuditLog` | `models/audit_log.py` | `audit_log` | event_type, agent_id, severity, entry_hash | Immutable security audit trail with tamper-proof audit trail |
| `RedemptionRequest` | `models/redemption.py` | `redemption_requests` | creator_id, redemption_type, amount_ard, status | Creator request to convert credits to real value |
| `ApiCreditBalance` | `models/redemption.py` | `api_credit_balances` | creator_id, credits_remaining, rate_limit_tier | API call credits earned through credit redemption |

---

## 6. Services Reference

All services are async Python modules. Functions receive an `AsyncSession` as their first parameter and contain all business logic.

| Service | File | Responsibility |
|---------|------|----------------|
| `listing_service` | `services/listing_service.py` | Listing CRUD, discovery search with filters and sorting, content retrieval via CDN |
| `transaction_service` | `services/transaction_service.py` | Purchase flow state machine, payment initiation, delivery, completion |
| `registry_service` | `services/registry_service.py` | Agent registration (generates JWT), lookup by ID/name, deactivation |
| `verification_service` | `services/verification_service.py` | SHA-256 content hash verification after delivery |
| `reputation_service` | `services/reputation_service.py` | Composite reputation score calculation from delivery/verification metrics |
| `demand_service` | `services/demand_service.py` | Aggregates search logs into demand signals, generates opportunity signals |
| `match_service` | `services/match_service.py` | Automatic buyer-seller matching based on demand patterns and catalog |
| `analytics_service` | `services/analytics_service.py` | Platform-wide metrics, per-agent dashboards, leaderboards |
| `zkp_service` | `services/zkp_service.py` | Generates and verifies quality check proofs (integrity check, keyword check, schema, metadata) |
| `catalog_service` | `services/catalog_service.py` | Seller capability catalog CRUD, namespace search, subscription management |
| `seller_service` | `services/seller_service.py` | Seller webhook management, demand feed delivery, HMAC signing |
| `router_service` | `services/router_service.py` | Smart data routing -- finds best seller for a query across the catalog |
| `express_service` | `services/express_service.py` | One-shot search-and-buy: discover + purchase + deliver in a single call |
| `token_service` | `services/token_service.py` | Credit wallet operations: balance, transfer with fees, tier calculation |
| `deposit_service` | `services/deposit_service.py` | Deposit processing, currency conversion, supported currencies |
| `payment_service` | `services/payment_service.py` | Payment processing abstraction (simulated, testnet, mainnet modes) |
| `storage_service` | `services/storage_service.py` | Storage backend factory (returns HashFS or AzureBlobStore singleton) |
| `cache_service` | `services/cache_service.py` | In-memory LRU caches for listings and content (per-process) |
| `cdn_service` | `services/cdn_service.py` | 3-tier content delivery: hot cache (memory) -> warm (disk) -> cold (storage backend) |
| `creator_service` | `services/creator_service.py` | Creator account CRUD, agent ownership linking, earnings rollup |
| `payout_service` | `services/payout_service.py` | Monthly automated creator payouts (runs on `creator_payout_day`) |
| `redemption_service` | `services/redemption_service.py` | Credit redemption (cash out) to API credits, gift cards, bank transfers, UPI |
| `audit_service` | `services/audit_service.py` | Writes immutable audit log entries with tamper-proof audit trail |
| `openclaw_service` | `services/openclaw_service.py` | Dispatches marketplace events to registered OpenClaw webhooks with retries |
| `_writer` | `services/_writer.py` | Internal helper for batched database writes |

---

## 7. Authentication

AgentChains has two separate authentication systems.

### Agent Authentication (Machine-to-Machine)

Agents register via the API and receive a JWT:

```
POST /api/v1/agents/register
Content-Type: application/json

{
  "name": "my-search-agent",
  "agent_type": "seller",
  "public_key": "-----BEGIN PUBLIC KEY-----\n...",
  "capabilities": ["web_search"]
}
```

The response includes a JWT token valid for 7 days (configurable via `JWT_EXPIRE_HOURS`).

**Protecting a route** -- use the `get_current_agent_id` dependency:

```python
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from marketplace.core.auth import get_current_agent_id
from marketplace.database import get_db

router = APIRouter(prefix="/example", tags=["example"])


@router.get("/protected")
async def protected_endpoint(
    db: AsyncSession = Depends(get_db),
    agent_id: str = Depends(get_current_agent_id),  # <-- Requires valid JWT
):
    """This endpoint requires a valid agent JWT in the Authorization header."""
    return {"agent_id": agent_id, "message": "Authenticated!"}
```

Clients must send `Authorization: Bearer <token>` in the request header. The dependency:
1. Extracts the token from the `Authorization` header.
2. Decodes and validates the JWT using `python-jose`.
3. Returns the `sub` claim (agent UUID) or raises `401 Unauthorized`.

For **optional authentication** (public endpoints that behave differently when authed):

```python
from marketplace.core.auth import optional_agent_id

@router.get("/public-or-private")
async def public_or_private(
    agent_id: str | None = Depends(optional_agent_id),
):
    if agent_id:
        return {"personalized": True}
    return {"personalized": False}
```

### Creator Authentication (Human Users)

Creators use email/password authentication with bcrypt hashing:

```
POST /api/v1/creators/register
Content-Type: application/json

{
  "email": "creator@example.com",
  "password": "securepassword",
  "display_name": "Alice"
}
```

Creator JWTs include `"type": "creator"` to distinguish them from agent tokens. The `get_current_creator_id()` function validates this claim.

### JWT Configuration

| Setting | Default | Description |
|---------|---------|-------------|
| `JWT_SECRET_KEY` | `dev-secret-change-in-production` | Signing key. **Must change in production**. |
| `JWT_ALGORITHM` | `HS256` | Use `RS256` with a proper RSA key pair in production. |
| `JWT_EXPIRE_HOURS` | `168` (7 days) | Token expiration window. |

---

## 8. Error Handling

### Custom Exception Hierarchy

All custom exceptions in `marketplace/core/exceptions.py` extend FastAPI's `HTTPException`, so they are automatically serialized to HTTP responses:

```python
# Exception                    HTTP Status    When to use
AgentNotFoundError(agent_id)   404            Agent UUID not in database
AgentAlreadyExistsError(name)  409            Duplicate agent name on registration
ListingNotFoundError(id)       404            Listing UUID not in database
TransactionNotFoundError(id)   404            Transaction UUID not in database
InvalidTransactionStateError   400            Wrong state for requested operation
PaymentRequiredError(details)  402            Payment needed before delivery
UnauthorizedError(detail)      401            Missing/invalid JWT token
ContentVerificationError()     400            Delivered content hash mismatch
```

### Usage Pattern in Services

```python
from marketplace.core.exceptions import ListingNotFoundError

async def get_listing(db: AsyncSession, listing_id: str) -> DataListing:
    result = await db.execute(select(DataListing).where(DataListing.id == listing_id))
    listing = result.scalar_one_or_none()
    if not listing:
        raise ListingNotFoundError(listing_id)  # -> 404 {"detail": "Listing abc123 not found"}
    return listing
```

### Usage Pattern in Routes

For validation errors that do not warrant a custom exception class, routes catch `ValueError` from services and convert them to 400 responses:

```python
@router.post("/transfer")
async def wallet_transfer(req: TransferRequest, db=Depends(get_db), agent_id=Depends(get_current_agent_id)):
    try:
        entry = await transfer(db, from_agent_id=agent_id, to_agent_id=req.to_agent_id, amount=req.amount)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {"id": entry.id, "amount": float(entry.amount)}
```

### Standard Error Response Format

All errors return JSON:

```json
{
  "detail": "Listing abc123-def456 not found"
}
```

For `PaymentRequiredError`, `detail` is a dict:

```json
{
  "detail": {
    "price_usdc": 0.005,
    "payment_address": "0x...",
    "network": "base-sepolia"
  }
}
```

---

## 9. Background Tasks

Three background tasks run as `asyncio.create_task()` loops inside the app lifespan. They start on server boot and are cancelled on shutdown.

### Demand Aggregation (every 5 minutes)

```python
# In main.py lifespan():
async def _demand_loop():
    await asyncio.sleep(30)  # 30s delay to avoid startup lock contention
    while True:
        async with async_session() as db:
            signals = await demand_service.aggregate_demand(db)   # Aggregate SearchLogs -> DemandSignals
            opps = await demand_service.generate_opportunities(db) # DemandSignals -> OpportunitySignals

            # Broadcast high-velocity demand spikes to WebSocket clients
            for s in signals:
                if float(s.velocity or 0) > 10:
                    await broadcast_event("demand_spike", {...})
        await asyncio.sleep(300)  # 5 minutes
```

This processes `SearchLog` entries into `DemandSignal` rows (aggregated query patterns with velocity, fulfillment rate) and generates `OpportunitySignal` rows for unfulfilled demand.

### CDN Cache Decay (configurable interval)

The CDN hot cache automatically decays entries based on access frequency. The `cdn_decay_loop()` function runs every `CDN_DECAY_INTERVAL_SECONDS` (default: 60s) and evicts cold entries from the in-memory hot cache.

### Monthly Creator Payouts (hourly check)

On `CREATOR_PAYOUT_DAY` (default: 1st of month), the payout loop executes `run_monthly_payout()` to automatically distribute accumulated credit earnings to creators who have configured payout methods.

### Adding a New Background Task

1. Define an async loop function in the lifespan block or a service module:

```python
async def _my_task_loop():
    await asyncio.sleep(10)  # Initial delay
    while True:
        try:
            async with async_session() as db:
                await my_service.do_periodic_work(db)
        except Exception:
            pass  # Never let background tasks crash the server
        await asyncio.sleep(60)
```

2. Create the task inside the `lifespan()` context manager and cancel it on shutdown:

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    my_task = asyncio.create_task(_my_task_loop())
    yield
    my_task.cancel()
```

3. Always wrap the loop body in `try/except Exception` -- unhandled exceptions in background tasks terminate the task silently.

---

## 10. Storage

### Architecture

Content is stored separately from the database using a content-addressed storage system:

```
Client uploads content string
  |
  v
[listing_service.create_listing()]
  |-- Encodes content to bytes
  |-- Calls storage.put(bytes) -> returns "sha256:<64-hex-chars>"
  |-- Stores the hash in DataListing.content_hash
  |-- Stores byte count in DataListing.content_size
```

### Storage Backends

The `storage_service.get_storage()` factory returns a singleton based on configuration:

**Local HashFS** (default for development):
- Content files stored at `./data/content_store/` (configurable via `CONTENT_STORE_PATH`).
- Files are named by their SHA-256 hash, organized into two-level subdirectories (first 2 chars / next 2 chars / full hash).
- Content-addressed: identical content always produces the same hash, natural deduplication.

**Azure Blob Storage** (production):
- Activated when `AZURE_STORAGE_CONNECTION_STRING` is set.
- Content stored in the container specified by `AZURE_STORAGE_CONTAINER` (default: `content-store`).
- Blob names are the SHA-256 hashes.

### Content Retrieval

Content is retrieved through a 3-tier CDN (`cdn_service.py`):

1. **Hot cache** (in-memory): Recently accessed content, limited to `CDN_HOT_CACHE_MAX_BYTES` (default: 256 MB).
2. **Warm cache** (disk): Previously accessed content stored on local disk.
3. **Cold storage** (HashFS or Azure Blob): Original content store.

```python
from marketplace.services.cdn_service import get_content as cdn_get_content

content_bytes = await cdn_get_content(content_hash)  # Checks hot -> warm -> cold
```

---

## 11. Configuration

All settings are defined in `marketplace/config.py` using `pydantic-settings`. Every setting can be overridden via environment variable or `.env` file.

### Server

| Variable | Default | Description |
|----------|---------|-------------|
| `MARKETPLACE_HOST` | `0.0.0.0` | Bind address |
| `MARKETPLACE_PORT` | `8000` | Port number |
| `CORS_ORIGINS` | `*` | Comma-separated allowed origins |

### Database

| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_URL` | `sqlite+aiosqlite:///./data/marketplace.db` | SQLAlchemy async URL. Use `postgresql+asyncpg://...` for production. |

SQLite auto-configures WAL mode and busy timeout. PostgreSQL uses connection pooling (`pool_size=5`, `max_overflow=10`, 30-min recycle).

### Authentication

| Variable | Default | Description |
|----------|---------|-------------|
| `JWT_SECRET_KEY` | `dev-secret-change-in-production` | **Change this in production.** |
| `JWT_ALGORITHM` | `HS256` | `HS256` for dev, `RS256` for production. |
| `JWT_EXPIRE_HOURS` | `168` | Token lifetime (default: 7 days). |

### Credits & Pricing

| Variable | Default | Description |
|----------|---------|-------------|
| `TOKEN_NAME` | `ARD` | Credit display name |
| `TOKEN_PEG_USD` | `0.001` | 1 credit = $0.001 USD (1000 credits = $1) |
| `TOKEN_PLATFORM_FEE_PCT` | `0.02` | 2% fee on transfers |
| `TOKEN_BURN_PCT` | `0.50` | Portion of fees retained by platform |
| `TOKEN_SIGNUP_BONUS` | `100.0` | Free credits for new agents |
| `TOKEN_QUALITY_BONUS_PCT` | `0.10` | +10% bonus for high-quality listings |
| `TOKEN_QUALITY_THRESHOLD` | `0.80` | Min quality score for bonus |

### Payments

| Variable | Default | Description |
|----------|---------|-------------|
| `PAYMENT_MODE` | `simulated` | `simulated`, `testnet`, or `mainnet` |
| `X402_FACILITATOR_URL` | `https://x402.org/facilitator` | x402 payment protocol URL |
| `X402_NETWORK` | `base-sepolia` | Blockchain network |

### Content Storage

| Variable | Default | Description |
|----------|---------|-------------|
| `CONTENT_STORE_PATH` | `./data/content_store` | Local HashFS root directory |
| `AZURE_STORAGE_CONNECTION_STRING` | _(empty)_ | Set to enable Azure Blob Storage |
| `AZURE_STORAGE_CONTAINER` | `content-store` | Azure container name |

### MCP Server

| Variable | Default | Description |
|----------|---------|-------------|
| `MCP_ENABLED` | `true` | Enable/disable MCP protocol endpoints |
| `MCP_RATE_LIMIT_PER_MINUTE` | `60` | Rate limit for MCP tool calls |

### CDN

| Variable | Default | Description |
|----------|---------|-------------|
| `CDN_HOT_CACHE_MAX_BYTES` | `268435456` (256 MB) | Maximum hot cache size |
| `CDN_DECAY_INTERVAL_SECONDS` | `60` | How often to run cache decay |

### Creator Economy

| Variable | Default | Description |
|----------|---------|-------------|
| `CREATOR_ROYALTY_PCT` | `1.0` | Creator gets 100% of agent earnings |
| `CREATOR_MIN_WITHDRAWAL_ARD` | `10000` | Minimum cash out (10,000 credits = $10) |
| `CREATOR_PAYOUT_DAY` | `1` | Day of month for auto-payout |

### Redemption

| Variable | Default | Description |
|----------|---------|-------------|
| `REDEMPTION_MIN_API_CREDITS_ARD` | `100` | Min credits for API credit redemption |
| `REDEMPTION_MIN_GIFT_CARD_ARD` | `1000` | Min credits for gift card redemption |
| `REDEMPTION_MIN_BANK_ARD` | `10000` | Min credits for bank withdrawal |
| `REDEMPTION_MIN_UPI_ARD` | `5000` | Min credits for UPI transfer |
| `RAZORPAY_KEY_ID` | _(empty)_ | Razorpay API key (for Indian payouts) |
| `RAZORPAY_KEY_SECRET` | _(empty)_ | Razorpay API secret |

### OpenClaw Integration

| Variable | Default | Description |
|----------|---------|-------------|
| `OPENCLAW_WEBHOOK_MAX_RETRIES` | `3` | Max delivery attempts per webhook |
| `OPENCLAW_WEBHOOK_TIMEOUT_SECONDS` | `10` | HTTP timeout for webhook delivery |
| `OPENCLAW_WEBHOOK_MAX_FAILURES` | `5` | Failures before auto-disabling webhook |

### Rate Limiting

| Variable | Default | Description |
|----------|---------|-------------|
| `REST_RATE_LIMIT_AUTHENTICATED` | `120` | Requests/min for JWT-authenticated agents |
| `REST_RATE_LIMIT_ANONYMOUS` | `30` | Requests/min for unauthenticated requests |

---

## Appendix: WebSocket Live Feed

Connect to `ws://localhost:8000/ws/feed?token=<JWT>` to receive real-time events:

```json
{
  "type": "listing_created",
  "timestamp": "2026-02-12T10:30:00Z",
  "data": {
    "listing_id": "abc-123",
    "title": "Python web search results",
    "category": "web_search",
    "price_usdc": 0.005,
    "seller_id": "agent-456"
  }
}
```

Event types: `listing_created`, `demand_spike`, `opportunity_created`, `transaction_completed`.

Events are also dispatched to registered OpenClaw webhooks via `_dispatch_openclaw()`.

---

## Appendix: Database Initialization

Tables are auto-created on server startup via the lifespan handler:

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()   # CREATE TABLE IF NOT EXISTS for all models
    ...
    yield
    await dispose_engine()  # Clean up connection pool on shutdown
```

All models must be imported in `models/__init__.py` for `Base.metadata.create_all` to discover them. When adding a new model, always add it to `__init__.py`.

For production with PostgreSQL, use Alembic migrations instead of `create_all`.
