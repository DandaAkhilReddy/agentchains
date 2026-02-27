"""Trust tier enforcement gate — FastAPI dependency for trust-gated endpoints."""

from __future__ import annotations

from typing import Callable

from fastapi import Depends

from marketplace.core.auth_context import AuthContext
from marketplace.core.auth_dependencies import require_auth
from marketplace.core.exceptions import AuthorizationError


TIER_ORDER = {"T0": 0, "T1": 1, "T2": 2, "T3": 3, "T4": 4, "T5": 5}


def require_trust_tier(min_tier: str) -> Callable:
    """FastAPI dependency factory that checks agent's trust tier.

    Returns 403 if the agent's trust tier is below the required minimum.
    Non-agent actors are rejected since trust tiers only apply to agents.
    """
    if min_tier not in TIER_ORDER:
        raise ValueError(f"Invalid trust tier: {min_tier}")

    async def _check(ctx: AuthContext = Depends(require_auth)) -> AuthContext:
        if not ctx.is_agent:
            raise AuthorizationError("Trust tier check requires agent authentication")
        if not ctx.meets_trust_tier(min_tier):
            raise AuthorizationError(
                f"Agent trust tier {ctx.trust_tier} below required {min_tier}"
            )
        return ctx

    return _check
