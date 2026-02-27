"""Unit tests for marketplace.core.refresh_tokens."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from marketplace.core.exceptions import UnauthorizedError
from marketplace.core.refresh_tokens import (
    TokenPair,
    _hash_token,
    create_token_pair,
    refresh_access_token,
    revoke_refresh_tokens_for_actor,
)
from marketplace.database import Base
from marketplace.models.refresh_token import RefreshToken


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

def _actor_id() -> str:
    return f"actor-{uuid.uuid4().hex[:8]}"


def _make_pair(
    actor_id: str | None = None,
    actor_type: str = "agent",
) -> tuple[TokenPair, str, RefreshToken]:
    return create_token_pair(
        actor_id=actor_id or _actor_id(),
        actor_type=actor_type,
    )


async def _persist_pair(
    db: AsyncSession,
    actor_id: str | None = None,
    actor_type: str = "agent",
    revoked: bool = False,
    expired: bool = False,
) -> tuple[TokenPair, str, RefreshToken]:
    aid = actor_id or _actor_id()
    pair, plain, row = create_token_pair(actor_id=aid, actor_type=actor_type)

    if expired:
        row.expires_at = datetime.now(timezone.utc) - timedelta(seconds=10)
    if revoked:
        row.revoked = True

    db.add(row)
    await db.commit()
    return pair, plain, row


# ---------------------------------------------------------------------------
# create_token_pair
# ---------------------------------------------------------------------------

class TestCreateTokenPair:
    def test_create_token_pair_returns_token_pair_named_tuple(self) -> None:
        pair, _, _ = _make_pair()
        assert isinstance(pair, TokenPair)

    def test_create_token_pair_access_token_is_non_empty_string(self) -> None:
        pair, _, _ = _make_pair()
        assert isinstance(pair.access_token, str)
        assert len(pair.access_token) > 20

    def test_create_token_pair_refresh_token_starts_with_rt_prefix(self) -> None:
        _, plain, _ = _make_pair()
        assert plain.startswith("rt_")

    def test_create_token_pair_refresh_token_is_url_safe_string(self) -> None:
        _, plain, _ = _make_pair()
        # rt_ + base64url characters (no +, /, or =)
        assert all(c not in plain for c in ("+", "/", "="))

    def test_create_token_pair_expires_in_is_positive_integer(self) -> None:
        pair, _, _ = _make_pair()
        assert isinstance(pair.expires_in, int)
        assert pair.expires_in > 0

    def test_create_token_pair_expires_in_matches_jwt_expire_hours(self) -> None:
        from marketplace.config import settings

        pair, _, _ = _make_pair()
        assert pair.expires_in == settings.jwt_expire_hours * 3600

    def test_create_token_pair_returns_refresh_token_row(self) -> None:
        _, _, row = _make_pair()
        assert isinstance(row, RefreshToken)

    def test_create_token_pair_row_actor_id_matches(self) -> None:
        aid = _actor_id()
        _, _, row = create_token_pair(actor_id=aid, actor_type="agent")
        assert row.actor_id == aid

    def test_create_token_pair_row_actor_type_matches(self) -> None:
        _, _, row = create_token_pair(actor_id=_actor_id(), actor_type="creator")
        assert row.actor_type == "creator"

    def test_create_token_pair_row_not_revoked_by_default(self) -> None:
        _, _, row = _make_pair()
        assert row.revoked is False

    def test_create_token_pair_row_token_hash_is_sha256_of_plain(self) -> None:
        _, plain, row = _make_pair()
        assert row.token_hash == _hash_token(plain)

    def test_create_token_pair_row_has_future_expires_at(self) -> None:
        _, _, row = _make_pair()
        assert row.expires_at > datetime.now(timezone.utc)

    def test_create_token_pair_with_email_and_name(self) -> None:
        pair, _, _ = create_token_pair(
            actor_id=_actor_id(),
            actor_type="user",
            email="user@example.com",
            name="Test User",
        )
        assert isinstance(pair.access_token, str)

    def test_create_token_pair_two_calls_produce_different_refresh_tokens(self) -> None:
        _, plain1, _ = _make_pair()
        _, plain2, _ = _make_pair()
        assert plain1 != plain2

    def test_create_token_pair_two_calls_produce_different_access_tokens(self) -> None:
        pair1, _, _ = _make_pair()
        pair2, _, _ = _make_pair()
        assert pair1.access_token != pair2.access_token


# ---------------------------------------------------------------------------
# refresh_access_token — happy path
# ---------------------------------------------------------------------------

class TestRefreshAccessTokenHappyPath:
    async def test_refresh_returns_new_token_pair(self, db: AsyncSession) -> None:
        _, plain, _ = await _persist_pair(db)
        new_pair = await refresh_access_token(db, plain)
        assert isinstance(new_pair, TokenPair)

    async def test_refresh_returns_non_empty_access_token(self, db: AsyncSession) -> None:
        _, plain, _ = await _persist_pair(db)
        new_pair = await refresh_access_token(db, plain)
        assert len(new_pair.access_token) > 20

    async def test_refresh_returns_non_empty_refresh_token(self, db: AsyncSession) -> None:
        _, plain, _ = await _persist_pair(db)
        new_pair = await refresh_access_token(db, plain)
        assert len(new_pair.refresh_token) > 10

    async def test_refresh_returns_new_refresh_token_different_from_old(
        self, db: AsyncSession
    ) -> None:
        _, plain, _ = await _persist_pair(db)
        new_pair = await refresh_access_token(db, plain)
        assert new_pair.refresh_token != plain

    async def test_refresh_returns_new_access_token_different_from_old(
        self, db: AsyncSession
    ) -> None:
        pair, plain, _ = await _persist_pair(db)
        new_pair = await refresh_access_token(db, plain)
        assert new_pair.access_token != pair.access_token

    async def test_refresh_revokes_old_refresh_token_in_db(
        self, db: AsyncSession
    ) -> None:
        _, plain, old_row = await _persist_pair(db)
        await refresh_access_token(db, plain)

        result = await db.execute(
            select(RefreshToken).where(RefreshToken.id == old_row.id)
        )
        updated_row = result.scalar_one()
        assert updated_row.revoked is True

    async def test_refresh_creates_new_refresh_token_row_in_db(
        self, db: AsyncSession
    ) -> None:
        _, plain, _ = await _persist_pair(db)
        new_pair = await refresh_access_token(db, plain)

        new_hash = _hash_token(new_pair.refresh_token)
        result = await db.execute(
            select(RefreshToken).where(RefreshToken.token_hash == new_hash)
        )
        new_row = result.scalar_one_or_none()
        assert new_row is not None
        assert new_row.revoked is False

    async def test_refresh_new_row_inherits_actor_id(self, db: AsyncSession) -> None:
        aid = _actor_id()
        _, plain, _ = await _persist_pair(db, actor_id=aid)
        new_pair = await refresh_access_token(db, plain)

        new_hash = _hash_token(new_pair.refresh_token)
        result = await db.execute(
            select(RefreshToken).where(RefreshToken.token_hash == new_hash)
        )
        new_row = result.scalar_one()
        assert new_row.actor_id == aid

    async def test_refresh_expires_in_is_positive(self, db: AsyncSession) -> None:
        _, plain, _ = await _persist_pair(db)
        new_pair = await refresh_access_token(db, plain)
        assert new_pair.expires_in > 0


# ---------------------------------------------------------------------------
# refresh_access_token — error cases
# ---------------------------------------------------------------------------

class TestRefreshAccessTokenErrors:
    async def test_invalid_refresh_token_raises_unauthorized_error(
        self, db: AsyncSession
    ) -> None:
        with pytest.raises(UnauthorizedError, match="Invalid refresh token"):
            await refresh_access_token(db, "rt_completely_invalid_token")

    async def test_random_string_raises_unauthorized_error(
        self, db: AsyncSession
    ) -> None:
        with pytest.raises(UnauthorizedError):
            await refresh_access_token(db, "not-a-token-at-all")

    async def test_empty_string_raises_unauthorized_error(
        self, db: AsyncSession
    ) -> None:
        with pytest.raises(UnauthorizedError):
            await refresh_access_token(db, "")

    async def test_already_revoked_token_raises_unauthorized_error(
        self, db: AsyncSession
    ) -> None:
        _, plain, _ = await _persist_pair(db, revoked=True)
        with pytest.raises(UnauthorizedError, match="already used"):
            await refresh_access_token(db, plain)

    async def test_revoked_token_triggers_revoke_all_for_actor(
        self, db: AsyncSession
    ) -> None:
        """Token reuse attack: using a revoked refresh token should revoke ALL tokens
        for that actor (reuse detection)."""
        actor_id = _actor_id()

        # Create two refresh tokens for the same actor
        _, plain1, row1 = await _persist_pair(db, actor_id=actor_id)
        _, plain2, _ = await _persist_pair(db, actor_id=actor_id)

        # Mark first token as already revoked (simulating reuse)
        row1.revoked = True
        await db.commit()

        with pytest.raises(UnauthorizedError, match="already used"):
            await refresh_access_token(db, plain1)

        # Both tokens for this actor should now be revoked
        result = await db.execute(
            select(RefreshToken).where(RefreshToken.actor_id == actor_id)
        )
        rows = result.scalars().all()
        assert all(r.revoked for r in rows), "All tokens for actor must be revoked on reuse"

    async def test_expired_refresh_token_raises_unauthorized_error(
        self, db: AsyncSession
    ) -> None:
        _, plain, _ = await _persist_pair(db, expired=True)
        with pytest.raises(UnauthorizedError, match="expired"):
            await refresh_access_token(db, plain)

    async def test_using_old_token_after_rotation_raises_unauthorized_error(
        self, db: AsyncSession
    ) -> None:
        """After a successful rotation, the old token must not be reusable."""
        _, plain, _ = await _persist_pair(db)
        # First rotation — valid
        await refresh_access_token(db, plain)
        # Second attempt with the old token — should fail
        with pytest.raises(UnauthorizedError):
            await refresh_access_token(db, plain)


# ---------------------------------------------------------------------------
# revoke_refresh_tokens_for_actor
# ---------------------------------------------------------------------------

class TestRevokeRefreshTokensForActor:
    async def test_revoke_marks_all_active_tokens_as_revoked(
        self, db: AsyncSession
    ) -> None:
        actor_id = _actor_id()
        for _ in range(3):
            await _persist_pair(db, actor_id=actor_id)

        count = await revoke_refresh_tokens_for_actor(db, actor_id)
        assert count == 3

        result = await db.execute(
            select(RefreshToken).where(RefreshToken.actor_id == actor_id)
        )
        rows = result.scalars().all()
        assert all(r.revoked for r in rows)

    async def test_revoke_returns_count_of_newly_revoked(
        self, db: AsyncSession
    ) -> None:
        actor_id = _actor_id()
        await _persist_pair(db, actor_id=actor_id)
        await _persist_pair(db, actor_id=actor_id)

        count = await revoke_refresh_tokens_for_actor(db, actor_id)
        assert count == 2

    async def test_revoke_returns_zero_for_unknown_actor(
        self, db: AsyncSession
    ) -> None:
        count = await revoke_refresh_tokens_for_actor(db, "nonexistent-actor")
        assert count == 0

    async def test_revoke_does_not_affect_already_revoked_tokens_count(
        self, db: AsyncSession
    ) -> None:
        actor_id = _actor_id()
        # One fresh, one already revoked
        await _persist_pair(db, actor_id=actor_id, revoked=False)
        await _persist_pair(db, actor_id=actor_id, revoked=True)

        count = await revoke_refresh_tokens_for_actor(db, actor_id)
        assert count == 1  # Only the active one counts

    async def test_revoke_does_not_affect_different_actor_tokens(
        self, db: AsyncSession
    ) -> None:
        actor1 = _actor_id()
        actor2 = _actor_id()

        await _persist_pair(db, actor_id=actor1)
        await _persist_pair(db, actor_id=actor2)

        await revoke_refresh_tokens_for_actor(db, actor1)

        # actor2's tokens should remain active
        result = await db.execute(
            select(RefreshToken).where(RefreshToken.actor_id == actor2)
        )
        rows = result.scalars().all()
        assert all(not r.revoked for r in rows)

    async def test_revoke_idempotent_on_second_call(self, db: AsyncSession) -> None:
        """Second call on already-revoked actor returns 0."""
        actor_id = _actor_id()
        await _persist_pair(db, actor_id=actor_id)

        count_first = await revoke_refresh_tokens_for_actor(db, actor_id)
        count_second = await revoke_refresh_tokens_for_actor(db, actor_id)

        assert count_first == 1
        assert count_second == 0

    async def test_revoke_single_token_for_actor(self, db: AsyncSession) -> None:
        actor_id = _actor_id()
        await _persist_pair(db, actor_id=actor_id)

        count = await revoke_refresh_tokens_for_actor(db, actor_id)
        assert count == 1

        result = await db.execute(
            select(RefreshToken).where(RefreshToken.actor_id == actor_id)
        )
        row = result.scalar_one()
        assert row.revoked is True


# ---------------------------------------------------------------------------
# _hash_token
# ---------------------------------------------------------------------------

class TestHashToken:
    def test_hash_token_returns_string(self) -> None:
        assert isinstance(_hash_token("rt_abc123"), str)

    def test_hash_token_is_deterministic(self) -> None:
        assert _hash_token("rt_abc123") == _hash_token("rt_abc123")

    def test_hash_token_different_inputs_produce_different_hashes(self) -> None:
        assert _hash_token("rt_token_a") != _hash_token("rt_token_b")

    def test_hash_token_produces_64_char_hex_digest(self) -> None:
        h = _hash_token("rt_test_value")
        assert len(h) == 64
        assert all(c in "0123456789abcdef" for c in h)

    def test_hash_token_empty_string(self) -> None:
        h = _hash_token("")
        assert len(h) == 64
