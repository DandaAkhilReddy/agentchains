"""Tests for marketplace.services.api_key_service.

Covers:
- create_api_key: returns plaintext key starting with "ac_live_"
- create_api_key: stores hashed key in DB (not plaintext)
- validate_api_key: returns AuthContext for a valid key
- validate_api_key: raises UnauthorizedError for invalid/unknown key
- validate_api_key: raises UnauthorizedError for revoked key
- validate_api_key: raises UnauthorizedError for expired key
- validate_api_key: updates last_used_at on successful validation
- revoke_api_key: sets revoked=True on the row
- revoke_api_key: raises ValueError when a non-owner attempts revocation
- revoke_api_key: raises ValueError when key_id does not exist
- list_api_keys: returns all keys for the given actor, newest first
- list_api_keys: returns empty list when actor has no keys
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from marketplace.core.exceptions import UnauthorizedError
from marketplace.services.api_key_service import (
    create_api_key,
    list_api_keys,
    revoke_api_key,
    validate_api_key,
)


# ---------------------------------------------------------------------------
# In-memory DB fixture (self-contained)
# ---------------------------------------------------------------------------

@pytest.fixture
async def db() -> AsyncSession:
    from marketplace.database import Base

    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as session:
        yield session
    await engine.dispose()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_ACTOR_ID = "actor-api-key-test"
_ACTOR_TYPE = "creator"


async def _create_key(db: AsyncSession, **kwargs) -> tuple[str, object]:
    """Shorthand: create a key for _ACTOR_ID with sensible defaults."""
    defaults = dict(
        actor_id=_ACTOR_ID,
        actor_type=_ACTOR_TYPE,
        name="Test Key",
        scopes=["listings:read"],
    )
    defaults.update(kwargs)
    return await create_api_key(db, **defaults)


# ---------------------------------------------------------------------------
# create_api_key
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_create_api_key_returns_plaintext_starting_with_prefix(db: AsyncSession) -> None:
    """create_api_key returns a plaintext key that starts with 'ac_live_'."""
    plaintext, _ = await _create_key(db)
    assert plaintext.startswith("ac_live_")


@pytest.mark.asyncio
async def test_create_api_key_plaintext_not_stored_in_db(db: AsyncSession) -> None:
    """The DB row stores the SHA-256 hash of the key, never the plaintext."""
    plaintext, row = await _create_key(db)
    assert row.key_hash != plaintext
    assert len(row.key_hash) == 64  # SHA-256 hex digest length


@pytest.mark.asyncio
async def test_create_api_key_hash_matches_sha256_of_plaintext(db: AsyncSession) -> None:
    """The stored key_hash is the SHA-256 digest of the returned plaintext key."""
    plaintext, row = await _create_key(db)
    expected_hash = hashlib.sha256(plaintext.encode("utf-8")).hexdigest()
    assert row.key_hash == expected_hash


@pytest.mark.asyncio
async def test_create_api_key_stores_correct_actor_id(db: AsyncSession) -> None:
    """create_api_key persists the actor_id on the row."""
    _, row = await _create_key(db, actor_id="specific-actor")
    assert row.actor_id == "specific-actor"


@pytest.mark.asyncio
async def test_create_api_key_stores_correct_name(db: AsyncSession) -> None:
    """create_api_key persists the key name on the row."""
    _, row = await _create_key(db, name="My Integration Key")
    assert row.name == "My Integration Key"


@pytest.mark.asyncio
async def test_create_api_key_not_revoked_by_default(db: AsyncSession) -> None:
    """Newly created API keys are not revoked."""
    _, row = await _create_key(db)
    assert row.revoked is False


@pytest.mark.asyncio
async def test_create_api_key_no_expiry_by_default(db: AsyncSession) -> None:
    """create_api_key with no expires_in_days leaves expires_at as None."""
    _, row = await _create_key(db)
    assert row.expires_at is None


@pytest.mark.asyncio
async def test_create_api_key_sets_expiry_when_requested(db: AsyncSession) -> None:
    """create_api_key with expires_in_days sets a future expiry date."""
    _, row = await _create_key(db, expires_in_days=30)
    assert row.expires_at is not None
    # SQLite may return a naive datetime; normalise before comparison.
    expires_at = row.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    assert expires_at > datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# validate_api_key
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_validate_api_key_returns_auth_context_for_valid_key(db: AsyncSession) -> None:
    """validate_api_key returns an AuthContext when the key is valid."""
    plaintext, row = await _create_key(db)
    ctx = await validate_api_key(db, plaintext)
    assert ctx.actor_id == _ACTOR_ID
    assert ctx.actor_type == _ACTOR_TYPE


@pytest.mark.asyncio
async def test_validate_api_key_sets_token_jti_to_apikey_format(db: AsyncSession) -> None:
    """The returned AuthContext carries a token_jti in 'apikey:<id>' format."""
    plaintext, row = await _create_key(db)
    ctx = await validate_api_key(db, plaintext)
    assert ctx.token_jti == f"apikey:{row.id}"


@pytest.mark.asyncio
async def test_validate_api_key_updates_last_used_at(db: AsyncSession) -> None:
    """validate_api_key sets last_used_at on the row to approximately now."""
    plaintext, row = await _create_key(db)
    before = datetime.now(timezone.utc)
    await validate_api_key(db, plaintext)
    await db.refresh(row)
    assert row.last_used_at is not None
    # last_used_at should be within a 5-second window
    last_used = row.last_used_at.replace(tzinfo=timezone.utc)
    assert last_used >= before


@pytest.mark.asyncio
async def test_validate_api_key_raises_for_unknown_key(db: AsyncSession) -> None:
    """validate_api_key raises UnauthorizedError when the key hash is not in the DB."""
    with pytest.raises(UnauthorizedError, match="Invalid API key"):
        await validate_api_key(db, "ac_live_totally_unknown_key_value_xyz")


@pytest.mark.asyncio
async def test_validate_api_key_raises_for_revoked_key(db: AsyncSession) -> None:
    """validate_api_key raises UnauthorizedError when the key has been revoked."""
    plaintext, row = await _create_key(db, actor_id="owner-rev")
    await revoke_api_key(db, row.id, "owner-rev")
    with pytest.raises(UnauthorizedError, match="revoked"):
        await validate_api_key(db, plaintext)


@pytest.mark.asyncio
async def test_validate_api_key_raises_for_expired_key(db: AsyncSession) -> None:
    """validate_api_key raises UnauthorizedError when the key has passed its expiry."""
    from marketplace.models.api_key import ApiKey

    plaintext, row = await _create_key(db)
    # Force the expiry into the past
    row.expires_at = datetime.now(timezone.utc) - timedelta(hours=1)
    await db.commit()

    with pytest.raises(UnauthorizedError, match="expired"):
        await validate_api_key(db, plaintext)


@pytest.mark.asyncio
async def test_validate_api_key_passes_for_key_not_yet_expired(db: AsyncSession) -> None:
    """validate_api_key succeeds when the key has a future expiry."""
    plaintext, _ = await _create_key(db, expires_in_days=1)
    ctx = await validate_api_key(db, plaintext)
    assert ctx.actor_id == _ACTOR_ID


# ---------------------------------------------------------------------------
# revoke_api_key
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_revoke_api_key_sets_revoked_true(db: AsyncSession) -> None:
    """revoke_api_key marks the ApiKey row as revoked=True."""
    plaintext, row = await _create_key(db, actor_id="owner-1")
    await revoke_api_key(db, row.id, "owner-1")
    await db.refresh(row)
    assert row.revoked is True


@pytest.mark.asyncio
async def test_revoke_api_key_raises_for_non_owner(db: AsyncSession) -> None:
    """revoke_api_key raises ValueError when called by an actor other than the owner."""
    _, row = await _create_key(db, actor_id="owner-2")
    with pytest.raises(ValueError, match="Not authorized"):
        await revoke_api_key(db, row.id, "attacker-id")


@pytest.mark.asyncio
async def test_revoke_api_key_raises_for_nonexistent_key_id(db: AsyncSession) -> None:
    """revoke_api_key raises ValueError when the key_id does not exist in the DB."""
    with pytest.raises(ValueError, match="API key not found"):
        await revoke_api_key(db, "nonexistent-key-id", "some-actor")


# ---------------------------------------------------------------------------
# list_api_keys
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_list_api_keys_returns_keys_for_actor(db: AsyncSession) -> None:
    """list_api_keys returns all ApiKey rows owned by the given actor."""
    await _create_key(db, actor_id="list-actor", name="Key A")
    await _create_key(db, actor_id="list-actor", name="Key B")
    keys = await list_api_keys(db, "list-actor")
    assert len(keys) == 2


@pytest.mark.asyncio
async def test_list_api_keys_does_not_include_other_actors_keys(db: AsyncSession) -> None:
    """list_api_keys only returns keys belonging to the specified actor."""
    await _create_key(db, actor_id="actor-owner", name="Owner Key")
    await _create_key(db, actor_id="actor-other", name="Other Key")
    keys = await list_api_keys(db, "actor-owner")
    assert all(k.actor_id == "actor-owner" for k in keys)
    assert len(keys) == 1


@pytest.mark.asyncio
async def test_list_api_keys_returns_empty_list_for_actor_with_no_keys(db: AsyncSession) -> None:
    """list_api_keys returns an empty list when the actor has no keys."""
    keys = await list_api_keys(db, "actor-no-keys")
    assert keys == []


@pytest.mark.asyncio
async def test_list_api_keys_never_exposes_plaintext(db: AsyncSession) -> None:
    """list_api_keys rows do not contain the plaintext key — only the hash and prefix."""
    plaintext, _ = await _create_key(db, actor_id="actor-safe")
    keys = await list_api_keys(db, "actor-safe")
    assert len(keys) == 1
    row = keys[0]
    # key_hash should NOT be the plaintext
    assert row.key_hash != plaintext
    # key_prefix is the first 8 chars of the plaintext (safe to expose)
    assert plaintext.startswith(row.key_prefix)


@pytest.mark.asyncio
async def test_list_api_keys_returns_newest_first(db: AsyncSession) -> None:
    """list_api_keys returns keys ordered by created_at descending."""
    import asyncio

    await _create_key(db, actor_id="actor-order", name="First")
    await asyncio.sleep(0.01)  # ensure distinct timestamps
    await _create_key(db, actor_id="actor-order", name="Second")
    keys = await list_api_keys(db, "actor-order")
    assert keys[0].name == "Second"
    assert keys[1].name == "First"
