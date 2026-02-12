"""Database lifecycle tests for the AgentChains marketplace.

Each test creates its own isolated in-memory SQLite engine so there is no
interference with the conftest's shared test database or other tests.
All 20 tests validate schema creation, teardown, session behaviour,
and Base metadata integrity.
"""

import uuid
from decimal import Decimal

import pytest
from sqlalchemy import inspect
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

# Import Base (carries all table metadata once models are loaded)
from marketplace.database import Base

# Ensure every model is registered on Base.metadata before tests run
from marketplace.models import *  # noqa: F401, F403


# ---------------------------------------------------------------------------
# Helper: build a fresh in-memory engine + session factory per test
# ---------------------------------------------------------------------------

async def _make_test_engine():
    """Return a brand-new in-memory SQLite async engine."""
    engine = create_async_engine("sqlite+aiosqlite://", echo=False)
    return engine


async def _create_all(engine):
    """Run Base.metadata.create_all on the given engine."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def _drop_all(engine):
    """Run Base.metadata.drop_all on the given engine."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


async def _get_table_names(engine) -> list[str]:
    """Return the list of table names present in the database."""
    async with engine.begin() as conn:
        names = await conn.run_sync(
            lambda sync_conn: inspect(sync_conn).get_table_names()
        )
    return names


# ===================================================================
# 1. init_db equivalent — create_all creates all tables
# ===================================================================

@pytest.mark.asyncio
async def test_create_all_creates_tables():
    engine = await _make_test_engine()
    try:
        await _create_all(engine)
        names = await _get_table_names(engine)
        # Must have at least the core tables
        assert len(names) > 0, "create_all should produce at least one table"
        assert "registered_agents" in names
        assert "data_listings" in names
        assert "transactions" in names
    finally:
        await engine.dispose()


# ===================================================================
# 2. init_db is idempotent — calling create_all twice doesn't error
# ===================================================================

@pytest.mark.asyncio
async def test_create_all_idempotent():
    engine = await _make_test_engine()
    try:
        await _create_all(engine)
        # Second call must not raise
        await _create_all(engine)
        names = await _get_table_names(engine)
        assert len(names) > 0
    finally:
        await engine.dispose()


# ===================================================================
# 3. drop_db equivalent — drop_all removes all tables
# ===================================================================

@pytest.mark.asyncio
async def test_drop_all_removes_tables():
    engine = await _make_test_engine()
    try:
        await _create_all(engine)
        assert len(await _get_table_names(engine)) > 0

        await _drop_all(engine)
        names = await _get_table_names(engine)
        assert len(names) == 0, "drop_all should leave zero tables"
    finally:
        await engine.dispose()


# ===================================================================
# 4. drop then create recreates tables
# ===================================================================

@pytest.mark.asyncio
async def test_drop_then_create_recreates():
    engine = await _make_test_engine()
    try:
        await _create_all(engine)
        original = set(await _get_table_names(engine))

        await _drop_all(engine)
        assert len(await _get_table_names(engine)) == 0

        await _create_all(engine)
        restored = set(await _get_table_names(engine))
        assert restored == original, "Recreated tables must match original set"
    finally:
        await engine.dispose()


# ===================================================================
# 5. Session yields AsyncSession type
# ===================================================================

@pytest.mark.asyncio
async def test_session_is_async_session():
    engine = await _make_test_engine()
    try:
        await _create_all(engine)
        factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        async with factory() as session:
            assert isinstance(session, AsyncSession)
    finally:
        await engine.dispose()


# ===================================================================
# 6. Session supports commit (insert + commit doesn't raise)
# ===================================================================

@pytest.mark.asyncio
async def test_session_commit():
    from marketplace.models.agent import RegisteredAgent

    engine = await _make_test_engine()
    try:
        await _create_all(engine)
        factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        async with factory() as session:
            agent = RegisteredAgent(
                id=str(uuid.uuid4()),
                name="commit-test-agent",
                agent_type="buyer",
                public_key="ssh-rsa AAAA_test",
                status="active",
            )
            session.add(agent)
            await session.commit()  # Must not raise
    finally:
        await engine.dispose()


# ===================================================================
# 7. Session supports rollback (insert + rollback = no row)
# ===================================================================

@pytest.mark.asyncio
async def test_session_rollback():
    from marketplace.models.agent import RegisteredAgent
    from sqlalchemy import select, func

    engine = await _make_test_engine()
    try:
        await _create_all(engine)
        factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

        async with factory() as session:
            agent = RegisteredAgent(
                id=str(uuid.uuid4()),
                name="rollback-test-agent",
                agent_type="seller",
                public_key="ssh-rsa AAAA_test",
                status="active",
            )
            session.add(agent)
            await session.flush()  # Write to DB within transaction
            await session.rollback()

        # Verify nothing was persisted
        async with factory() as session:
            count = await session.scalar(
                select(func.count()).select_from(RegisteredAgent)
            )
            assert count == 0, "Rolled-back insert must leave zero rows"
    finally:
        await engine.dispose()


# ===================================================================
# 8. expire_on_commit=False: attributes accessible after commit
# ===================================================================

@pytest.mark.asyncio
async def test_expire_on_commit_false():
    from marketplace.models.agent import RegisteredAgent

    engine = await _make_test_engine()
    try:
        await _create_all(engine)
        factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        async with factory() as session:
            agent = RegisteredAgent(
                id=str(uuid.uuid4()),
                name="expire-test-agent",
                agent_type="both",
                public_key="ssh-rsa AAAA_test",
                status="active",
            )
            session.add(agent)
            await session.commit()
            # With expire_on_commit=False, accessing .name should NOT raise
            # (no lazy-load / DetachedInstanceError)
            assert agent.name == "expire-test-agent"
            assert agent.agent_type == "both"
    finally:
        await engine.dispose()


# ===================================================================
# 9. Base is a DeclarativeBase subclass
# ===================================================================

@pytest.mark.asyncio
async def test_base_is_declarative_base():
    assert issubclass(Base, DeclarativeBase)


# ===================================================================
# 10. Base.metadata has tables after model imports (len > 0)
# ===================================================================

@pytest.mark.asyncio
async def test_base_metadata_has_tables():
    assert len(Base.metadata.tables) > 0, (
        "Base.metadata.tables must be populated after model imports"
    )


# ===================================================================
# 11. Table existence: "registered_agents" (agents table) in metadata
# ===================================================================

@pytest.mark.asyncio
async def test_agents_table_in_metadata():
    assert "registered_agents" in Base.metadata.tables


# ===================================================================
# 12. Table existence: "data_listings" table in metadata
# ===================================================================

@pytest.mark.asyncio
async def test_data_listings_table_in_metadata():
    assert "data_listings" in Base.metadata.tables


# ===================================================================
# 13. Table existence: "transactions" table in metadata
# ===================================================================

@pytest.mark.asyncio
async def test_transactions_table_in_metadata():
    assert "transactions" in Base.metadata.tables


# ===================================================================
# 14. Table existence: "token_accounts" table in metadata
# ===================================================================

@pytest.mark.asyncio
async def test_token_accounts_table_in_metadata():
    assert "token_accounts" in Base.metadata.tables


# ===================================================================
# 15. Table existence: "token_ledger" table in metadata
# ===================================================================

@pytest.mark.asyncio
async def test_token_ledger_table_in_metadata():
    assert "token_ledger" in Base.metadata.tables


# ===================================================================
# 16. Table existence: "token_supply" table in metadata
# ===================================================================

@pytest.mark.asyncio
async def test_token_supply_table_in_metadata():
    assert "token_supply" in Base.metadata.tables


# ===================================================================
# 17. Table existence: "creators" table in metadata
# ===================================================================

@pytest.mark.asyncio
async def test_creators_table_in_metadata():
    assert "creators" in Base.metadata.tables


# ===================================================================
# 18. Dispose engine completes without error
# ===================================================================

@pytest.mark.asyncio
async def test_dispose_engine():
    engine = await _make_test_engine()
    await _create_all(engine)
    # dispose must not raise
    await engine.dispose()


# ===================================================================
# 19. Dispose engine is idempotent (call twice)
# ===================================================================

@pytest.mark.asyncio
async def test_dispose_engine_idempotent():
    engine = await _make_test_engine()
    await _create_all(engine)
    await engine.dispose()
    # Second dispose must also succeed without error
    await engine.dispose()


# ===================================================================
# 20. Engine echo is False (verify from database module)
# ===================================================================

@pytest.mark.asyncio
async def test_engine_echo_is_false():
    from marketplace.database import engine as app_engine

    assert app_engine.echo is False, (
        "Production/app engine should have echo=False to avoid noisy SQL logs"
    )
