"""Token revocation via Redis with DB fallback.

Maintains a JTI blacklist. Redis is the hot path; the ``revoked_tokens``
DB table is the durable fallback for when Redis is unavailable.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from marketplace.models.revoked_token import RevokedToken

logger = logging.getLogger(__name__)

# In-process fallback set for environments without Redis.
_LOCAL_BLACKLIST: set[str] = set()


def _get_redis():
    """Return an async Redis client or None if unavailable."""
    try:
        from marketplace.config import settings
        if not settings.redis_url:
            return None
        import redis.asyncio as aioredis
        return aioredis.from_url(settings.redis_url, decode_responses=True)
    except Exception:
        return None


async def revoke_token(
    db: AsyncSession,
    jti: str,
    actor_id: str,
    expires_at: datetime,
) -> None:
    """Add a JTI to the blacklist (Redis + DB)."""
    now = datetime.now(timezone.utc)
    ttl_seconds = max(int((expires_at - now).total_seconds()), 1)

    # Redis path
    redis = _get_redis()
    if redis:
        try:
            async with redis as r:
                await r.setex(f"revoked:{jti}", ttl_seconds, "1")
        except Exception:
            logger.warning("Redis revoke failed for jti=%s, falling back to DB", jti)

    # Local in-process fallback
    _LOCAL_BLACKLIST.add(jti)

    # DB durable record
    row = RevokedToken(
        jti=jti,
        actor_id=actor_id,
        revoked_at=now,
        expires_at=expires_at,
    )
    db.add(row)
    await db.commit()


async def is_token_revoked(db: AsyncSession, jti: str) -> bool:
    """Check if a JTI has been revoked. Checks Redis -> local set -> DB."""
    # Redis hot path
    redis = _get_redis()
    if redis:
        try:
            async with redis as r:
                if await r.exists(f"revoked:{jti}"):
                    return True
        except Exception:
            logger.debug("Redis check failed for jti=%s", jti)

    # Local in-process fallback
    if jti in _LOCAL_BLACKLIST:
        return True

    # DB fallback
    result = await db.execute(
        select(RevokedToken.jti).where(RevokedToken.jti == jti)
    )
    return result.scalar_one_or_none() is not None


async def revoke_all_for_actor(db: AsyncSession, actor_id: str) -> int:
    """Revoke all tokens for an actor. Returns count of newly revoked tokens.

    Since we don't track all active JTIs, this adds a sentinel record and
    relies on the unified decoder checking the ``revoked_at`` timestamp
    against the token's ``iat``.
    """
    now = datetime.now(timezone.utc)
    # Store a sentinel with a special JTI format
    sentinel_jti = f"all:{actor_id}:{int(now.timestamp())}"
    row = RevokedToken(
        jti=sentinel_jti,
        actor_id=actor_id,
        revoked_at=now,
        # Sentinel expires far in the future (30 days)
        expires_at=datetime(2099, 12, 31, tzinfo=timezone.utc),
    )
    db.add(row)
    await db.commit()

    # Also set in Redis
    redis = _get_redis()
    if redis:
        try:
            async with redis as r:
                await r.setex(f"revoke_all:{actor_id}", 86400 * 30, str(int(now.timestamp())))
        except Exception:
            logger.warning("Redis revoke_all failed for actor_id=%s", actor_id)

    return 1  # Sentinel count


async def is_actor_tokens_revoked_after(
    db: AsyncSession, actor_id: str, issued_at: datetime
) -> bool:
    """Check if all tokens for an actor were bulk-revoked after ``issued_at``."""
    # Redis hot path
    redis = _get_redis()
    if redis:
        try:
            async with redis as r:
                ts = await r.get(f"revoke_all:{actor_id}")
                if ts and int(ts) > int(issued_at.timestamp()):
                    return True
        except Exception:
            pass

    # DB fallback — check for sentinel records
    result = await db.execute(
        select(RevokedToken.revoked_at)
        .where(RevokedToken.actor_id == actor_id)
        .where(RevokedToken.jti.startswith("all:"))
        .where(RevokedToken.revoked_at > issued_at)
        .limit(1)
    )
    return result.scalar_one_or_none() is not None


async def cleanup_expired(db: AsyncSession) -> int:
    """Delete revoked token records that have expired (housekeeping)."""
    now = datetime.now(timezone.utc)
    result = await db.execute(
        delete(RevokedToken).where(RevokedToken.expires_at < now)
    )
    await db.commit()
    return result.rowcount or 0
