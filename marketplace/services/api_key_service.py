"""API key service — create, validate, revoke API keys for machine-to-machine auth."""

from __future__ import annotations

import hashlib
import json
import secrets
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from marketplace.core.auth_context import AuthContext
from marketplace.core.exceptions import UnauthorizedError
from marketplace.models.api_key import ApiKey
from marketplace.services import auth_event_service

_API_KEY_PREFIX = "ac_live_"


def _hash_key(key: str) -> str:
    return hashlib.sha256(key.encode("utf-8")).hexdigest()


async def create_api_key(
    db: AsyncSession,
    actor_id: str,
    actor_type: str,
    name: str,
    scopes: list[str] | None = None,
    expires_in_days: int | None = None,
) -> tuple[str, ApiKey]:
    """Create a new API key. Returns (plaintext_key, ApiKey row).

    The plaintext key is returned only once and must be saved by the caller.
    """
    random_part = secrets.token_urlsafe(32)
    key_plaintext = f"{_API_KEY_PREFIX}{random_part}"
    key_hash = _hash_key(key_plaintext)
    key_prefix = key_plaintext[:8]

    expires_at = None
    if expires_in_days:
        expires_at = datetime.now(timezone.utc) + timedelta(days=expires_in_days)

    row = ApiKey(
        id=str(uuid.uuid4()),
        actor_id=actor_id,
        actor_type=actor_type,
        key_prefix=key_prefix,
        key_hash=key_hash,
        name=name,
        scopes_json=json.dumps(scopes or ["*"]),
        expires_at=expires_at,
    )
    db.add(row)
    await db.commit()
    await db.refresh(row)
    await auth_event_service.log_auth_event(
        db,
        actor_id=actor_id,
        actor_type=actor_type,
        event_type="api_key_create",
        details={"key_id": row.id, "name": name, "key_prefix": key_prefix},
    )
    return key_plaintext, row


async def validate_api_key(db: AsyncSession, key: str) -> AuthContext:
    """Validate an API key and return an AuthContext."""
    key_hash = _hash_key(key)
    result = await db.execute(
        select(ApiKey).where(ApiKey.key_hash == key_hash)
    )
    row = result.scalar_one_or_none()

    if not row:
        raise UnauthorizedError("Invalid API key")
    if row.revoked:
        raise UnauthorizedError("API key has been revoked")
    if row.expires_at and row.expires_at.replace(tzinfo=timezone.utc) < datetime.now(timezone.utc):
        raise UnauthorizedError("API key has expired")

    # Update last_used_at
    row.last_used_at = datetime.now(timezone.utc)
    await db.commit()

    scopes = json.loads(row.scopes_json or '["*"]')

    # Load roles
    from marketplace.core.auth_unified import _load_roles, _load_trust_tier
    roles = await _load_roles(db, row.actor_id)
    trust_tier = None
    if row.actor_type == "agent":
        trust_tier = await _load_trust_tier(db, row.actor_id)

    return AuthContext(
        actor_id=row.actor_id,
        actor_type=row.actor_type,
        roles=frozenset(roles),
        trust_tier=trust_tier,
        token_jti=f"apikey:{row.id}",
        scopes=frozenset(scopes),
    )


async def revoke_api_key(db: AsyncSession, key_id: str, actor_id: str) -> None:
    """Revoke an API key. Only the owner can revoke."""
    row = await db.get(ApiKey, key_id)
    if not row:
        raise ValueError("API key not found")
    if row.actor_id != actor_id:
        raise ValueError("Not authorized to revoke this API key")
    row.revoked = True
    await db.commit()
    await auth_event_service.log_auth_event(
        db,
        actor_id=actor_id,
        actor_type=row.actor_type,
        event_type="api_key_revoke",
        details={"key_id": key_id, "key_prefix": row.key_prefix, "name": row.name},
    )


async def list_api_keys(db: AsyncSession, actor_id: str) -> list[ApiKey]:
    """List all API keys for an actor (never returns plaintext)."""
    result = await db.execute(
        select(ApiKey)
        .where(ApiKey.actor_id == actor_id)
        .order_by(ApiKey.created_at.desc())
    )
    return list(result.scalars().all())
