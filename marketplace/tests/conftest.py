"""Shared test fixtures for the ARD token economy test suite.

Uses an in-memory SQLite database with StaticPool so all sessions share the
same connection (committed data is visible across sessions).
"""

import uuid
from decimal import Decimal

import pytest
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from marketplace.database import Base, get_db
from marketplace.main import app
from marketplace.models import *  # noqa: ensure all models are loaded for create_all


# ---------------------------------------------------------------------------
# In-memory SQLite test engine (shared via StaticPool)
# ---------------------------------------------------------------------------

test_engine = create_async_engine(
    "sqlite+aiosqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
    echo=False,
)
TestSession = async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)


@event.listens_for(test_engine.sync_engine, "connect")
def _set_sqlite_pragma(dbapi_conn, connection_record):
    cursor = dbapi_conn.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA busy_timeout=5000")
    cursor.close()


# ---------------------------------------------------------------------------
# Auto-use: create/drop tables for every test
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
async def _setup_db():
    """Create all tables before each test, drop after. Also clear global state."""
    # Clear all singleton caches before test
    from marketplace.services.cache_service import listing_cache, content_cache, agent_cache
    listing_cache.clear()
    content_cache.clear()
    agent_cache.clear()

    # Clear rate limiter buckets
    from marketplace.core.rate_limiter import rate_limiter
    rate_limiter._buckets.clear()

    # Clear CDN hot cache and stats
    from marketplace.services import cdn_service
    cdn_service._hot_cache._store.clear()
    cdn_service._hot_cache._freq.clear()
    cdn_service._hot_cache._access_count.clear()
    cdn_service._hot_cache._current_bytes = 0
    cdn_service._hot_cache.hits = 0
    cdn_service._hot_cache.misses = 0
    cdn_service._hot_cache.promotions = 0
    cdn_service._hot_cache.evictions = 0
    cdn_service._cdn_stats.update({
        "tier1_hits": 0,
        "tier2_hits": 0,
        "tier3_hits": 0,
        "total_misses": 0,
        "total_requests": 0,
    })

    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


# ---------------------------------------------------------------------------
# Core fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
async def db():
    """Yield a fresh AsyncSession for direct service-layer tests."""
    async with TestSession() as session:
        yield session


@pytest.fixture
async def client():
    """httpx AsyncClient wired to the FastAPI app with test DB override."""
    import httpx

    async def _override_get_db():
        async with TestSession() as session:
            yield session

    app.dependency_overrides[get_db] = _override_get_db

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
    ) as c:
        yield c

    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Seeding helpers
# ---------------------------------------------------------------------------

def _new_id() -> str:
    return str(uuid.uuid4())


@pytest.fixture
def auth_header():
    """Return a callable that builds an Authorization header from a JWT."""
    def _build(token: str) -> dict:
        return {"Authorization": f"Bearer {token}"}
    return _build


@pytest.fixture
async def seed_platform(db: AsyncSession):
    """Create platform treasury account + TokenSupply singleton. Returns the platform account."""
    from marketplace.services.token_service import ensure_platform_account
    return await ensure_platform_account(db)


@pytest.fixture
def make_agent(db: AsyncSession):
    """Factory fixture: create a RegisteredAgent and return (agent, jwt_token)."""
    from marketplace.core.auth import create_access_token
    from marketplace.models.agent import RegisteredAgent

    async def _make(name: str = None, agent_type: str = "both"):
        name = name or f"test-agent-{_new_id()[:8]}"
        agent = RegisteredAgent(
            id=_new_id(),
            name=name,
            agent_type=agent_type,
            public_key="ssh-rsa AAAA_test_key_placeholder",
            status="active",
        )
        db.add(agent)
        await db.commit()
        await db.refresh(agent)
        token = create_access_token(agent.id, agent.name)
        return agent, token

    return _make


@pytest.fixture
def make_token_account(db: AsyncSession):
    """Factory fixture: create a TokenAccount for an agent with given balance."""
    from marketplace.models.token_account import TokenAccount

    async def _make(agent_id: str, balance: float = 0):
        account = TokenAccount(
            id=_new_id(),
            agent_id=agent_id,
            balance=Decimal(str(balance)),
        )
        db.add(account)
        await db.commit()
        await db.refresh(account)
        return account

    return _make


@pytest.fixture
def make_listing(db: AsyncSession):
    """Factory fixture: create a DataListing with content stored in storage."""
    from marketplace.models.listing import DataListing
    from marketplace.services.storage_service import get_storage

    async def _make(seller_id: str, price_usdc: float = 1.0, content_hash: str = None, **kwargs):
        # Generate or use provided content
        content = kwargs.get("content", f"Test content for listing {_new_id()[:6]}")
        if isinstance(content, str):
            content = content.encode("utf-8")

        # Store content in storage and get hash
        storage = get_storage()
        stored_hash = storage.put(content)
        # Use caller-provided content_hash only if explicitly set, else use the stored hash
        final_hash = content_hash if content_hash is not None else stored_hash

        listing = DataListing(
            id=_new_id(),
            seller_id=seller_id,
            title=kwargs.get("title", f"Test Listing {_new_id()[:6]}"),
            category=kwargs.get("category", "web_search"),
            content_hash=final_hash,
            content_size=kwargs.get("content_size", len(content)),
            price_usdc=Decimal(str(price_usdc)),
            price_axn=Decimal(str(price_usdc / 0.001)),
            quality_score=Decimal(str(kwargs.get("quality_score", 0.85))),
            status=kwargs.get("status", "active"),
        )
        db.add(listing)
        await db.commit()
        await db.refresh(listing)
        return listing

    return _make


# ---------------------------------------------------------------------------
# Extended factory fixtures (Wave 0)
# ---------------------------------------------------------------------------

@pytest.fixture
def make_transaction(db: AsyncSession):
    """Factory fixture: create a Transaction."""
    from marketplace.models.transaction import Transaction

    async def _make(buyer_id: str, seller_id: str, listing_id: str,
                    amount_usdc: float = 1.0, status: str = "completed"):
        from datetime import datetime, timezone
        tx = Transaction(
            id=_new_id(),
            listing_id=listing_id,
            buyer_id=buyer_id,
            seller_id=seller_id,
            amount_usdc=Decimal(str(amount_usdc)),
            status=status,
            content_hash=f"sha256:{_new_id().replace('-', '')[:64]}",
        )
        if status == "completed":
            tx.completed_at = datetime.now(timezone.utc)
        db.add(tx)
        await db.commit()
        await db.refresh(tx)
        return tx

    return _make


@pytest.fixture
def make_creator(db: AsyncSession):
    """Factory fixture: register a Creator and return (creator, jwt_token)."""
    from marketplace.core.creator_auth import hash_password, create_creator_token
    from marketplace.models.creator import Creator

    async def _make(email: str = None, password: str = "testpass123",
                    display_name: str = "Test Creator"):
        email = email or f"creator-{_new_id()[:8]}@test.com"
        creator = Creator(
            id=_new_id(),
            email=email,
            password_hash=hash_password(password),
            display_name=display_name,
            status="active",
        )
        db.add(creator)
        await db.commit()
        await db.refresh(creator)
        token = create_creator_token(creator.id, creator.email)
        return creator, token

    return _make


@pytest.fixture
def make_catalog_entry(db: AsyncSession):
    """Factory fixture: create a DataCatalogEntry."""
    from marketplace.models.catalog import DataCatalogEntry

    async def _make(agent_id: str, namespace: str = "web_search",
                    topic: str = "test-topic", **kwargs):
        entry = DataCatalogEntry(
            id=_new_id(),
            agent_id=agent_id,
            namespace=namespace,
            topic=topic,
            description=kwargs.get("description", "Test catalog entry"),
            price_range_min=Decimal(str(kwargs.get("price_range_min", 0.001))),
            price_range_max=Decimal(str(kwargs.get("price_range_max", 0.01))),
            quality_avg=Decimal(str(kwargs.get("quality_avg", 0.8))),
            status=kwargs.get("status", "active"),
        )
        db.add(entry)
        await db.commit()
        await db.refresh(entry)
        return entry

    return _make


@pytest.fixture
def make_catalog_subscription(db: AsyncSession):
    """Factory fixture: create a CatalogSubscription."""
    from marketplace.models.catalog import CatalogSubscription

    async def _make(subscriber_id: str, namespace_pattern: str = "web_search.*", **kwargs):
        sub = CatalogSubscription(
            id=_new_id(),
            subscriber_id=subscriber_id,
            namespace_pattern=namespace_pattern,
            topic_pattern=kwargs.get("topic_pattern", "*"),
            max_price=Decimal(str(kwargs["max_price"])) if kwargs.get("max_price") else None,
            min_quality=Decimal(str(kwargs["min_quality"])) if kwargs.get("min_quality") else None,
            status=kwargs.get("status", "active"),
        )
        db.add(sub)
        await db.commit()
        await db.refresh(sub)
        return sub

    return _make


@pytest.fixture
def make_search_log(db: AsyncSession):
    """Factory fixture: create a SearchLog."""
    from marketplace.models.search_log import SearchLog

    async def _make(query_text: str = "python tutorial",
                    category: str = "web_search", **kwargs):
        log = SearchLog(
            id=_new_id(),
            query_text=query_text,
            category=category,
            source=kwargs.get("source", "discover"),
            requester_id=kwargs.get("requester_id"),
            matched_count=kwargs.get("matched_count", 0),
            led_to_purchase=kwargs.get("led_to_purchase", 0),
        )
        db.add(log)
        await db.commit()
        await db.refresh(log)
        return log

    return _make


@pytest.fixture
def make_demand_signal(db: AsyncSession):
    """Factory fixture: create a DemandSignal."""
    from marketplace.models.demand_signal import DemandSignal

    async def _make(query_pattern: str = "python tutorial",
                    category: str = "web_search", **kwargs):
        signal = DemandSignal(
            id=_new_id(),
            query_pattern=query_pattern,
            category=category,
            search_count=kwargs.get("search_count", 10),
            unique_requesters=kwargs.get("unique_requesters", 5),
            velocity=Decimal(str(kwargs.get("velocity", 2.0))),
            fulfillment_rate=Decimal(str(kwargs.get("fulfillment_rate", 0.5))),
            is_gap=kwargs.get("is_gap", 0),
        )
        db.add(signal)
        await db.commit()
        await db.refresh(signal)
        return signal

    return _make
