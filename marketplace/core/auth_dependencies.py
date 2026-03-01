"""FastAPI dependency factories for authentication and authorization.

Each dependency returns an ``AuthContext`` (or raises ``UnauthorizedError``/
``AuthorizationError``).  Use these in route signatures via ``Depends()``.
"""

from __future__ import annotations

from typing import Callable

from fastapi import Depends, Header
from sqlalchemy.ext.asyncio import AsyncSession

from marketplace.core.auth_context import AuthContext
from marketplace.core.auth_unified import decode_authorization
from marketplace.core.exceptions import AuthorizationError, UnauthorizedError
from marketplace.database import get_db


async def require_auth(
    authorization: str | None = Header(default=None),
    db: AsyncSession = Depends(get_db),
) -> AuthContext:
    """Require any authenticated actor (agent, creator, or user)."""
    return await decode_authorization(db, authorization)


async def require_agent(
    ctx: AuthContext = Depends(require_auth),
) -> AuthContext:
    """Require an authenticated agent."""
    if not ctx.is_agent:
        raise AuthorizationError("Agent authentication required")
    return ctx


async def require_creator(
    ctx: AuthContext = Depends(require_auth),
) -> AuthContext:
    """Require an authenticated creator."""
    if not ctx.is_creator:
        raise AuthorizationError("Creator authentication required")
    return ctx


async def require_user(
    ctx: AuthContext = Depends(require_auth),
) -> AuthContext:
    """Require an authenticated end-user."""
    if not ctx.is_user:
        raise AuthorizationError("User authentication required")
    return ctx


def require_role(role: str) -> Callable:
    """Dependency factory: require the actor to have a specific role."""

    async def _check(ctx: AuthContext = Depends(require_auth)) -> AuthContext:
        if not ctx.has_role(role):
            raise AuthorizationError(f"Role '{role}' required")
        return ctx

    return _check


def require_any_role(*roles: str) -> Callable:
    """Dependency factory: require the actor to have at least one of the given roles."""

    async def _check(ctx: AuthContext = Depends(require_auth)) -> AuthContext:
        if not ctx.has_any_role(*roles):
            raise AuthorizationError(f"One of roles {roles!r} required")
        return ctx

    return _check


def require_trust_tier(min_tier: str) -> Callable:
    """Dependency factory: require the agent to have a minimum trust tier."""

    async def _check(ctx: AuthContext = Depends(require_auth)) -> AuthContext:
        if not ctx.is_agent:
            raise AuthorizationError("Trust tier check requires agent authentication")
        if not ctx.meets_trust_tier(min_tier):
            raise AuthorizationError(
                f"Agent trust tier {ctx.trust_tier} below required {min_tier}"
            )
        return ctx

    return _check


async def optional_auth(
    authorization: str | None = Header(default=None),
    db: AsyncSession = Depends(get_db),
) -> AuthContext | None:
    """Optionally authenticate — returns None if no token provided."""
    if not authorization:
        return None
    try:
        return await decode_authorization(db, authorization)
    except UnauthorizedError:
        return None
