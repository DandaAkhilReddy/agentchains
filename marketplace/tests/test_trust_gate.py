"""Tests for marketplace.core.trust_gate (trust tier enforcement).

Tests the inner _check dependency function returned by require_trust_tier,
using synthetic AuthContext instances (no DB required).

Covers:
- Agent meeting or exceeding the required tier is allowed through
- Agent below the required tier raises AuthorizationError
- Non-agent actor (creator) raises AuthorizationError
- Non-agent actor (user) raises AuthorizationError
- Invalid tier string in factory raises ValueError
- Tier ordering: T0 < T1 < T2 < T3 < T4 < T5
"""

from __future__ import annotations

import pytest

from marketplace.core.auth_context import AuthContext
from marketplace.core.exceptions import AuthorizationError
from marketplace.core.trust_gate import TIER_ORDER, require_trust_tier


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_agent_ctx(trust_tier: str) -> AuthContext:
    """Build a minimal agent AuthContext with the given trust tier."""
    return AuthContext(
        actor_id="agent-test",
        actor_type="agent",
        roles=frozenset(),
        trust_tier=trust_tier,
        token_jti="test-jti",
        scopes=frozenset(["*"]),
    )


def _make_creator_ctx() -> AuthContext:
    """Build a minimal creator AuthContext (no trust tier)."""
    return AuthContext(
        actor_id="creator-test",
        actor_type="creator",
        roles=frozenset(),
        trust_tier=None,
        token_jti="test-jti",
        scopes=frozenset(["*"]),
    )


def _make_user_ctx() -> AuthContext:
    """Build a minimal user AuthContext (no trust tier)."""
    return AuthContext(
        actor_id="user-test",
        actor_type="user",
        roles=frozenset(),
        trust_tier=None,
        token_jti="test-jti",
        scopes=frozenset(["*"]),
    )


async def _invoke_check(min_tier: str, ctx: AuthContext) -> AuthContext:
    """Extract and call the inner _check coroutine directly, bypassing FastAPI DI."""
    dep_factory = require_trust_tier(min_tier)
    # The inner function uses Depends(require_auth) as a default arg.
    # We call it directly by passing ctx as the positional argument.
    return await dep_factory(ctx)


# ---------------------------------------------------------------------------
# require_trust_tier factory validation
# ---------------------------------------------------------------------------

def test_require_trust_tier_raises_for_invalid_tier_string() -> None:
    """require_trust_tier raises ValueError immediately for an unrecognised tier like 'T9'."""
    with pytest.raises(ValueError, match="Invalid trust tier"):
        require_trust_tier("T9")


def test_require_trust_tier_raises_for_empty_tier_string() -> None:
    """require_trust_tier raises ValueError for an empty tier string."""
    with pytest.raises(ValueError, match="Invalid trust tier"):
        require_trust_tier("")


# ---------------------------------------------------------------------------
# Agent meeting or exceeding the required tier
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_agent_at_exact_required_tier_is_allowed() -> None:
    """An agent whose trust tier equals the minimum required tier passes the gate."""
    ctx = _make_agent_ctx("T2")
    result = await _invoke_check("T2", ctx)
    assert result is ctx


@pytest.mark.asyncio
async def test_agent_above_required_tier_is_allowed() -> None:
    """An agent whose trust tier exceeds the minimum required tier passes the gate."""
    ctx = _make_agent_ctx("T4")
    result = await _invoke_check("T2", ctx)
    assert result is ctx


@pytest.mark.asyncio
async def test_agent_at_t5_passes_all_tiers() -> None:
    """An agent at T5 (maximum tier) passes a gate requiring any tier from T0 through T5."""
    for tier in ("T0", "T1", "T2", "T3", "T4", "T5"):
        ctx = _make_agent_ctx("T5")
        result = await _invoke_check(tier, ctx)
        assert result is ctx


@pytest.mark.asyncio
async def test_agent_at_t0_passes_only_t0_gate() -> None:
    """An agent at T0 passes only a T0 gate and is blocked by T1 and above."""
    ctx_pass = _make_agent_ctx("T0")
    result = await _invoke_check("T0", ctx_pass)
    assert result is ctx_pass

    ctx_fail = _make_agent_ctx("T0")
    with pytest.raises(AuthorizationError):
        await _invoke_check("T1", ctx_fail)


# ---------------------------------------------------------------------------
# Agent below the required tier
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_agent_below_required_tier_raises_authorization_error() -> None:
    """An agent with trust tier T1 is rejected by a gate requiring T2."""
    ctx = _make_agent_ctx("T1")
    with pytest.raises(AuthorizationError):
        await _invoke_check("T2", ctx)


@pytest.mark.asyncio
async def test_agent_at_t0_blocked_by_t3_gate() -> None:
    """An agent at T0 is rejected by a gate requiring T3."""
    ctx = _make_agent_ctx("T0")
    with pytest.raises(AuthorizationError):
        await _invoke_check("T3", ctx)


@pytest.mark.asyncio
async def test_authorization_error_message_contains_tier_info() -> None:
    """The raised AuthorizationError message references the agent's tier and required tier."""
    ctx = _make_agent_ctx("T1")
    with pytest.raises(AuthorizationError, match="T1"):
        await _invoke_check("T3", ctx)


# ---------------------------------------------------------------------------
# Non-agent actors rejected
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_creator_actor_raises_authorization_error() -> None:
    """A creator auth context is rejected by the trust tier gate."""
    ctx = _make_creator_ctx()
    with pytest.raises(AuthorizationError, match="agent authentication"):
        await _invoke_check("T0", ctx)


@pytest.mark.asyncio
async def test_user_actor_raises_authorization_error() -> None:
    """A user auth context is rejected by the trust tier gate."""
    ctx = _make_user_ctx()
    with pytest.raises(AuthorizationError, match="agent authentication"):
        await _invoke_check("T0", ctx)


# ---------------------------------------------------------------------------
# Tier ordering sanity checks
# ---------------------------------------------------------------------------

def test_tier_order_values_are_strictly_ascending() -> None:
    """TIER_ORDER maps T0..T5 to strictly increasing integers."""
    tiers = ["T0", "T1", "T2", "T3", "T4", "T5"]
    values = [TIER_ORDER[t] for t in tiers]
    assert values == sorted(values)
    assert len(set(values)) == len(values)  # all unique


def test_tier_order_contains_exactly_six_tiers() -> None:
    """TIER_ORDER defines exactly T0 through T5 — no more, no less."""
    assert set(TIER_ORDER.keys()) == {"T0", "T1", "T2", "T3", "T4", "T5"}


@pytest.mark.asyncio
async def test_each_tier_only_passes_at_or_above_itself() -> None:
    """For every pair (agent_tier, required_tier): passes iff agent_tier >= required_tier."""
    tiers = ["T0", "T1", "T2", "T3", "T4", "T5"]
    for agent_tier in tiers:
        for required_tier in tiers:
            ctx = _make_agent_ctx(agent_tier)
            should_pass = TIER_ORDER[agent_tier] >= TIER_ORDER[required_tier]
            if should_pass:
                result = await _invoke_check(required_tier, ctx)
                assert result is ctx
            else:
                with pytest.raises(AuthorizationError):
                    await _invoke_check(required_tier, ctx)
