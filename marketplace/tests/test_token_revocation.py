"""Unit tests for marketplace.core.token_revocation."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from marketplace.core.token_revocation import (
    cleanup_expired,
    is_actor_tokens_revoked_after,
    is_token_revoked,
    revoke_all_for_actor,
    revoke_token,
)
from marketplace.database import Base
from marketplace.models.revoked_token import RevokedToken


# ---------------------------------------------------------------------------
# In-memory DB fixture — isolated per test
# ---------------------------------------------------------------------------

@pytest.fixture
async def db():
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as session:
        yield session
    await engine.dispose()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _jti() -> str:
    return str(uuid.uuid4())


def _actor_id() -> str:
    return f"actor-{uuid.uuid4().hex[:8]}"


def _future(hours: int = 2) -> datetime:
    return datetime.now(timezone.utc) + timedelta(hours=hours)


def _past(seconds: int = 10) -> datetime:
    return datetime.now(timezone.utc) - timedelta(seconds=seconds)


# Disable Redis for all tests in this module — token_revocation will fall back
# to DB/local-blacklist only.
pytestmark = pytest.mark.usefixtures()


@pytest.fixture(autouse=True)
def _no_redis():
    """Patch _get_redis to return None so all tests use the DB path."""
    with patch("marketplace.core.token_revocation._get_redis", return_value=None):
        yield


# Also clear the module-level in-process blacklist before each test so tests
# are isolated even when running in the same process.
@pytest.fixture(autouse=True)
def _clear_local_blacklist():
    import marketplace.core.token_revocation as _mod
    _mod._LOCAL_BLACKLIST.clear()
    yield
    _mod._LOCAL_BLACKLIST.clear()


# ---------------------------------------------------------------------------
# revoke_token
# ---------------------------------------------------------------------------

class TestRevokeToken:
    async def test_revoke_token_creates_db_record(self, db: AsyncSession) -> None:
        jti = _jti()
        actor = _actor_id()
        await revoke_token(db, jti, actor, _future())

        result = await db.execute(select(RevokedToken).where(RevokedToken.jti == jti))
        row = result.scalar_one_or_none()
        assert row is not None
        assert row.jti == jti
        assert row.actor_id == actor

    async def test_revoke_token_stores_correct_actor_id(self, db: AsyncSession) -> None:
        jti = _jti()
        actor = _actor_id()
        await revoke_token(db, jti, actor, _future())

        result = await db.execute(select(RevokedToken).where(RevokedToken.jti == jti))
        row = result.scalar_one()
        assert row.actor_id == actor

    async def test_revoke_token_stores_expires_at(self, db: AsyncSession) -> None:
        jti = _jti()
        expires = _future(hours=3)
        await revoke_token(db, jti, _actor_id(), expires)

        result = await db.execute(select(RevokedToken).where(RevokedToken.jti == jti))
        row = result.scalar_one()
        # Allow 2-second tolerance for timezone-naive DB storage
        assert abs((row.expires_at.replace(tzinfo=timezone.utc) - expires).total_seconds()) < 2

    async def test_revoke_token_adds_to_local_blacklist(self, db: AsyncSession) -> None:
        import marketplace.core.token_revocation as _mod

        jti = _jti()
        await revoke_token(db, jti, _actor_id(), _future())
        assert jti in _mod._LOCAL_BLACKLIST

    async def test_revoke_token_multiple_jtis_are_each_stored(self, db: AsyncSession) -> None:
        actor = _actor_id()
        jtis = [_jti() for _ in range(3)]
        for j in jtis:
            await revoke_token(db, j, actor, _future())

        for j in jtis:
            result = await db.execute(select(RevokedToken).where(RevokedToken.jti == j))
            assert result.scalar_one_or_none() is not None


# ---------------------------------------------------------------------------
# is_token_revoked
# ---------------------------------------------------------------------------

class TestIsTokenRevoked:
    async def test_is_token_revoked_returns_true_for_revoked_jti(
        self, db: AsyncSession
    ) -> None:
        jti = _jti()
        await revoke_token(db, jti, _actor_id(), _future())
        assert await is_token_revoked(db, jti) is True

    async def test_is_token_revoked_returns_false_for_unknown_jti(
        self, db: AsyncSession
    ) -> None:
        unknown_jti = _jti()
        assert await is_token_revoked(db, unknown_jti) is False

    async def test_is_token_revoked_returns_true_from_local_blacklist(
        self, db: AsyncSession
    ) -> None:
        import marketplace.core.token_revocation as _mod

        jti = _jti()
        _mod._LOCAL_BLACKLIST.add(jti)
        # Should find it in local set without touching DB
        assert await is_token_revoked(db, jti) is True

    async def test_is_token_revoked_returns_false_for_empty_db(
        self, db: AsyncSession
    ) -> None:
        assert await is_token_revoked(db, _jti()) is False

    async def test_is_token_revoked_returns_true_after_multiple_revocations(
        self, db: AsyncSession
    ) -> None:
        jti1 = _jti()
        jti2 = _jti()
        actor = _actor_id()
        await revoke_token(db, jti1, actor, _future())
        await revoke_token(db, jti2, actor, _future())
        assert await is_token_revoked(db, jti1) is True
        assert await is_token_revoked(db, jti2) is True


# ---------------------------------------------------------------------------
# revoke_all_for_actor
# ---------------------------------------------------------------------------

class TestRevokeAllForActor:
    async def test_revoke_all_creates_sentinel_record_in_db(
        self, db: AsyncSession
    ) -> None:
        actor = _actor_id()
        await revoke_all_for_actor(db, actor)

        result = await db.execute(
            select(RevokedToken).where(RevokedToken.actor_id == actor)
        )
        rows = result.scalars().all()
        assert len(rows) == 1

    async def test_revoke_all_sentinel_jti_starts_with_all_prefix(
        self, db: AsyncSession
    ) -> None:
        actor = _actor_id()
        await revoke_all_for_actor(db, actor)

        result = await db.execute(
            select(RevokedToken).where(RevokedToken.actor_id == actor)
        )
        row = result.scalar_one()
        assert row.jti.startswith("all:")

    async def test_revoke_all_sentinel_jti_contains_actor_id(
        self, db: AsyncSession
    ) -> None:
        actor = _actor_id()
        await revoke_all_for_actor(db, actor)

        result = await db.execute(
            select(RevokedToken).where(RevokedToken.actor_id == actor)
        )
        row = result.scalar_one()
        assert actor in row.jti

    async def test_revoke_all_returns_one(self, db: AsyncSession) -> None:
        count = await revoke_all_for_actor(db, _actor_id())
        assert count == 1

    async def test_revoke_all_sentinel_expires_far_in_future(
        self, db: AsyncSession
    ) -> None:
        actor = _actor_id()
        await revoke_all_for_actor(db, actor)

        result = await db.execute(
            select(RevokedToken).where(RevokedToken.actor_id == actor)
        )
        row = result.scalar_one()
        far_future = datetime(2090, 1, 1, tzinfo=timezone.utc)
        assert row.expires_at.replace(tzinfo=timezone.utc) > far_future

    async def test_revoke_all_for_different_actors_creates_separate_sentinels(
        self, db: AsyncSession
    ) -> None:
        actor1 = _actor_id()
        actor2 = _actor_id()
        await revoke_all_for_actor(db, actor1)
        await revoke_all_for_actor(db, actor2)

        for actor in (actor1, actor2):
            result = await db.execute(
                select(RevokedToken).where(RevokedToken.actor_id == actor)
            )
            assert result.scalar_one_or_none() is not None


# ---------------------------------------------------------------------------
# is_actor_tokens_revoked_after
# ---------------------------------------------------------------------------

class TestIsActorTokensRevokedAfter:
    async def test_returns_false_when_no_sentinel_exists(
        self, db: AsyncSession
    ) -> None:
        issued_at = datetime.now(timezone.utc) - timedelta(minutes=10)
        assert await is_actor_tokens_revoked_after(db, _actor_id(), issued_at) is False

    async def test_returns_true_when_sentinel_revoked_after_issued_at(
        self, db: AsyncSession
    ) -> None:
        actor = _actor_id()
        issued_at = datetime.now(timezone.utc) - timedelta(minutes=30)
        # Revoke now — after issued_at
        await revoke_all_for_actor(db, actor)
        assert await is_actor_tokens_revoked_after(db, actor, issued_at) is True

    async def test_returns_false_when_sentinel_revoked_before_issued_at(
        self, db: AsyncSession
    ) -> None:
        actor = _actor_id()
        # Insert a sentinel with revoked_at in the past
        past_time = datetime.now(timezone.utc) - timedelta(hours=2)
        sentinel_jti = f"all:{actor}:manual"
        row = RevokedToken(
            jti=sentinel_jti,
            actor_id=actor,
            revoked_at=past_time,
            expires_at=datetime(2099, 12, 31, tzinfo=timezone.utc),
        )
        db.add(row)
        await db.commit()

        # Token was issued after the bulk revocation — should NOT be flagged
        issued_at = datetime.now(timezone.utc) - timedelta(hours=1)
        assert await is_actor_tokens_revoked_after(db, actor, issued_at) is False

    async def test_returns_false_for_different_actor_sentinel(
        self, db: AsyncSession
    ) -> None:
        other_actor = _actor_id()
        my_actor = _actor_id()
        issued_at = datetime.now(timezone.utc) - timedelta(minutes=10)

        # Revoke all for a DIFFERENT actor
        await revoke_all_for_actor(db, other_actor)

        # My actor's tokens should still be valid
        assert await is_actor_tokens_revoked_after(db, my_actor, issued_at) is False

    async def test_returns_true_only_for_sentinel_jti_starting_with_all(
        self, db: AsyncSession
    ) -> None:
        actor = _actor_id()
        issued_at = datetime.now(timezone.utc) - timedelta(minutes=10)

        # Insert a normal revoked token (not a sentinel) for the actor
        normal_jti = _jti()
        await revoke_token(db, normal_jti, actor, _future())

        # Normal single-token revocation should NOT trigger bulk revocation check
        assert await is_actor_tokens_revoked_after(db, actor, issued_at) is False


# ---------------------------------------------------------------------------
# cleanup_expired
# ---------------------------------------------------------------------------

class TestCleanupExpired:
    async def test_cleanup_removes_expired_records(self, db: AsyncSession) -> None:
        actor = _actor_id()
        jti = _jti()
        expired_row = RevokedToken(
            jti=jti,
            actor_id=actor,
            revoked_at=_past(seconds=3600),
            expires_at=_past(seconds=10),  # expired
        )
        db.add(expired_row)
        await db.commit()

        deleted = await cleanup_expired(db)
        assert deleted >= 1

        result = await db.execute(select(RevokedToken).where(RevokedToken.jti == jti))
        assert result.scalar_one_or_none() is None

    async def test_cleanup_does_not_remove_non_expired_records(
        self, db: AsyncSession
    ) -> None:
        actor = _actor_id()
        jti = _jti()
        valid_row = RevokedToken(
            jti=jti,
            actor_id=actor,
            revoked_at=datetime.now(timezone.utc),
            expires_at=_future(hours=1),  # not expired
        )
        db.add(valid_row)
        await db.commit()

        await cleanup_expired(db)

        result = await db.execute(select(RevokedToken).where(RevokedToken.jti == jti))
        assert result.scalar_one_or_none() is not None

    async def test_cleanup_returns_zero_when_nothing_expired(
        self, db: AsyncSession
    ) -> None:
        actor = _actor_id()
        jti = _jti()
        db.add(RevokedToken(
            jti=jti,
            actor_id=actor,
            revoked_at=datetime.now(timezone.utc),
            expires_at=_future(),
        ))
        await db.commit()

        deleted = await cleanup_expired(db)
        assert deleted == 0

    async def test_cleanup_returns_zero_on_empty_table(self, db: AsyncSession) -> None:
        deleted = await cleanup_expired(db)
        assert deleted == 0

    async def test_cleanup_removes_multiple_expired_records(
        self, db: AsyncSession
    ) -> None:
        actor = _actor_id()
        jtis = [_jti() for _ in range(3)]
        for j in jtis:
            db.add(RevokedToken(
                jti=j,
                actor_id=actor,
                revoked_at=_past(seconds=3600),
                expires_at=_past(seconds=60),
            ))
        await db.commit()

        deleted = await cleanup_expired(db)
        assert deleted == 3

    async def test_cleanup_mixed_records_removes_only_expired(
        self, db: AsyncSession
    ) -> None:
        actor = _actor_id()
        expired_jti = _jti()
        valid_jti = _jti()

        db.add(RevokedToken(
            jti=expired_jti,
            actor_id=actor,
            revoked_at=_past(3600),
            expires_at=_past(10),
        ))
        db.add(RevokedToken(
            jti=valid_jti,
            actor_id=actor,
            revoked_at=datetime.now(timezone.utc),
            expires_at=_future(),
        ))
        await db.commit()

        deleted = await cleanup_expired(db)
        assert deleted == 1

        result = await db.execute(select(RevokedToken).where(RevokedToken.jti == valid_jti))
        assert result.scalar_one_or_none() is not None
