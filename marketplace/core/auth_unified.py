"""Unified token decoder — single entry point for all auth flows.

Decodes JWT tokens (agent/creator/user), API keys, and returns an
``AuthContext`` regardless of actor type.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone

from jose import JWTError, jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from marketplace.config import settings
from marketplace.core.auth_context import AuthContext
from marketplace.core.exceptions import UnauthorizedError
from marketplace.core.token_revocation import is_actor_tokens_revoked_after, is_token_revoked
from marketplace.models.agent_trust import AgentTrustProfile

logger = logging.getLogger(__name__)

# API key prefix for detection
_API_KEY_PREFIX = "ac_live_"


async def decode_authorization(
    db: AsyncSession,
    authorization: str | None,
) -> AuthContext:
    """Decode an Authorization header value into an AuthContext.

    Supports:
    - ``Bearer <jwt>`` — decodes JWT for agent/creator/user tokens
    - ``Bearer ac_live_...`` — validates API key

    Raises UnauthorizedError on any failure.
    """
    if not authorization:
        raise UnauthorizedError("Missing Authorization header")

    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise UnauthorizedError("Authorization header must be: Bearer <token>")

    raw_token = parts[1]

    # Route API keys to the API key service
    if raw_token.startswith(_API_KEY_PREFIX):
        return await _decode_api_key(db, raw_token)

    return await _decode_jwt(db, raw_token)


async def _decode_jwt(db: AsyncSession, token: str) -> AuthContext:
    """Decode a JWT and build an AuthContext."""
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
            audience="agentchains-marketplace",
            issuer="agentchains",
        )
    except JWTError as exc:
        raise UnauthorizedError(f"Invalid or expired token: {exc}") from exc

    sub = payload.get("sub")
    if not sub:
        raise UnauthorizedError("Token missing subject")

    token_type = payload.get("type")

    # Reject stream tokens
    if token_type in {"stream", "stream_agent", "stream_admin", "stream_user", "stream_a2ui"}:
        raise UnauthorizedError("Stream tokens cannot be used for API endpoints")

    # Determine actor type
    if token_type == "creator":
        actor_type = "creator"
    elif token_type == "user":
        actor_type = "user"
    else:
        actor_type = "agent"

    jti = payload.get("jti", "")
    iat_ts = payload.get("iat")
    iat = datetime.fromtimestamp(iat_ts, tz=timezone.utc) if iat_ts else None

    # Check single-token revocation
    if jti:
        if await is_token_revoked(db, jti):
            raise UnauthorizedError("Token has been revoked")

    # Check bulk revocation
    if iat:
        if await is_actor_tokens_revoked_after(db, sub, iat):
            raise UnauthorizedError("All tokens for this account have been revoked")

    # Load roles from DB
    roles = await _load_roles(db, sub)

    # Load trust tier for agents
    trust_tier: str | None = None
    if actor_type == "agent":
        trust_tier = await _load_trust_tier(db, sub)

    return AuthContext(
        actor_id=sub,
        actor_type=actor_type,
        roles=frozenset(roles),
        trust_tier=trust_tier,
        token_jti=jti,
        scopes=frozenset(["*"]),  # JWT tokens get full scope
    )


async def _decode_api_key(db: AsyncSession, key: str) -> AuthContext:
    """Validate an API key and return an AuthContext."""
    from marketplace.services.api_key_service import validate_api_key
    return await validate_api_key(db, key)


async def _load_roles(db: AsyncSession, actor_id: str) -> list[str]:
    """Load role names for an actor from the actor_roles + roles tables."""
    from marketplace.models.role import ActorRole, Role

    result = await db.execute(
        select(Role.name)
        .join(ActorRole, ActorRole.role_id == Role.id)
        .where(ActorRole.actor_id == actor_id)
    )
    return [row[0] for row in result.all()]


async def _load_trust_tier(db: AsyncSession, agent_id: str) -> str | None:
    """Load the trust tier for an agent."""
    result = await db.execute(
        select(AgentTrustProfile.trust_tier)
        .where(AgentTrustProfile.agent_id == agent_id)
    )
    row = result.scalar_one_or_none()
    return row if row else "T0"
