"""Refresh token service — create token pairs, rotate refresh tokens."""

from __future__ import annotations

import hashlib
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import NamedTuple

from jose import jwt
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from marketplace.config import settings
from marketplace.core.exceptions import UnauthorizedError
from marketplace.models.refresh_token import RefreshToken


class TokenPair(NamedTuple):
    access_token: str
    refresh_token: str
    expires_in: int  # access token lifetime in seconds


def _hash_token(token: str) -> str:
    """SHA-256 hash of a refresh token for storage."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _create_access_token(
    actor_id: str,
    actor_type: str,
    email: str | None = None,
    name: str | None = None,
) -> tuple[str, str, datetime]:
    """Create an access JWT and return (token, jti, expires_at)."""
    jti = str(uuid.uuid4())
    expires_at = datetime.now(timezone.utc) + timedelta(hours=settings.jwt_expire_hours)
    payload: dict = {
        "sub": actor_id,
        "type": actor_type,
        "jti": jti,
        "aud": "agentchains-marketplace",
        "iss": "agentchains",
        "exp": expires_at,
        "iat": datetime.now(timezone.utc),
    }
    if email:
        payload["email"] = email
    if name:
        payload["name"] = name
    token = jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)
    return token, jti, expires_at


def create_token_pair(
    db_sync_not_needed: None = None,
    *,
    actor_id: str,
    actor_type: str,
    email: str | None = None,
    name: str | None = None,
) -> tuple[TokenPair, str, RefreshToken]:
    """Create an access + refresh token pair.

    Returns (TokenPair, refresh_token_plaintext, RefreshToken_row) so the
    caller can add the row to the session and commit.
    """
    access_token, jti, expires_at = _create_access_token(
        actor_id, actor_type, email=email, name=name,
    )
    expires_in = settings.jwt_expire_hours * 3600

    # Generate refresh token
    refresh_token_plain = f"rt_{secrets.token_urlsafe(48)}"
    refresh_token_hash = _hash_token(refresh_token_plain)
    refresh_expires = datetime.now(timezone.utc) + timedelta(
        days=settings.refresh_token_expire_days,
    )

    row = RefreshToken(
        id=str(uuid.uuid4()),
        token_hash=refresh_token_hash,
        actor_id=actor_id,
        actor_type=actor_type,
        expires_at=refresh_expires,
        revoked=False,
    )

    pair = TokenPair(
        access_token=access_token,
        refresh_token=refresh_token_plain,
        expires_in=expires_in,
    )
    return pair, refresh_token_plain, row


async def refresh_access_token(
    db: AsyncSession,
    refresh_token: str,
) -> TokenPair:
    """Exchange a refresh token for a new token pair (rotation).

    The old refresh token is revoked and a new one is issued.
    Raises UnauthorizedError if the token is invalid, expired, or already used.
    """
    token_hash = _hash_token(refresh_token)
    result = await db.execute(
        select(RefreshToken).where(RefreshToken.token_hash == token_hash)
    )
    row = result.scalar_one_or_none()

    if not row:
        raise UnauthorizedError("Invalid refresh token")
    if row.revoked:
        # Possible token reuse attack — revoke all tokens for this actor
        await db.execute(
            update(RefreshToken)
            .where(RefreshToken.actor_id == row.actor_id)
            .values(revoked=True)
        )
        await db.commit()
        raise UnauthorizedError("Refresh token already used — all tokens revoked")
    if row.expires_at.replace(tzinfo=timezone.utc) < datetime.now(timezone.utc):
        raise UnauthorizedError("Refresh token expired")

    # Revoke the old refresh token
    row.revoked = True

    # Create new pair
    pair, new_refresh_plain, new_row = create_token_pair(
        actor_id=row.actor_id,
        actor_type=row.actor_type,
    )
    db.add(new_row)
    await db.commit()

    return pair


async def revoke_refresh_tokens_for_actor(db: AsyncSession, actor_id: str) -> int:
    """Revoke all refresh tokens for an actor (e.g. on password change)."""
    result = await db.execute(
        update(RefreshToken)
        .where(RefreshToken.actor_id == actor_id)
        .where(RefreshToken.revoked == False)  # noqa: E712
        .values(revoked=True)
    )
    await db.commit()
    return result.rowcount or 0
