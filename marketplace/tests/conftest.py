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
    """Create all tables before each test, drop after."""
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
    """Factory fixture: create a DataListing."""
    from marketplace.models.listing import DataListing

    async def _make(seller_id: str, price_usdc: float = 1.0, content_hash: str = None):
        content_hash = content_hash or f"sha256:{_new_id().replace('-', '')[:64]}"
        listing = DataListing(
            id=_new_id(),
            seller_id=seller_id,
            title=f"Test Listing {_new_id()[:6]}",
            category="web_search",
            content_hash=content_hash,
            content_size=1024,
            price_usdc=Decimal(str(price_usdc)),
            price_axn=Decimal(str(price_usdc / 0.001)),
            status="active",
        )
        db.add(listing)
        await db.commit()
        await db.refresh(listing)
        return listing

    return _make
