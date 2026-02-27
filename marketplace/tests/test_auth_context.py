"""Unit tests for marketplace.core.auth_context.AuthContext."""

from __future__ import annotations

import pytest

from marketplace.core.auth_context import AuthContext


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_context(
    actor_id: str = "actor-1",
    actor_type: str = "agent",
    roles: frozenset[str] | None = None,
    trust_tier: str | None = "T2",
    token_jti: str = "jti-abc",
    scopes: frozenset[str] | None = None,
) -> AuthContext:
    return AuthContext(
        actor_id=actor_id,
        actor_type=actor_type,
        roles=roles if roles is not None else frozenset(),
        trust_tier=trust_tier,
        token_jti=token_jti,
        scopes=scopes if scopes is not None else frozenset(["read"]),
    )


# ---------------------------------------------------------------------------
# Construction
# ---------------------------------------------------------------------------

class TestAuthContextConstruction:
    def test_creation_with_all_fields_stores_values(self) -> None:
        ctx = AuthContext(
            actor_id="user-99",
            actor_type="user",
            roles=frozenset(["viewer", "editor"]),
            trust_tier=None,
            token_jti="jti-xyz",
            scopes=frozenset(["read", "write"]),
        )
        assert ctx.actor_id == "user-99"
        assert ctx.actor_type == "user"
        assert ctx.roles == frozenset(["viewer", "editor"])
        assert ctx.trust_tier is None
        assert ctx.token_jti == "jti-xyz"
        assert ctx.scopes == frozenset(["read", "write"])

    def test_creation_with_empty_roles_and_scopes(self) -> None:
        ctx = _make_context(roles=frozenset(), scopes=frozenset())
        assert ctx.roles == frozenset()
        assert ctx.scopes == frozenset()

    def test_frozen_dataclass_raises_on_field_assignment(self) -> None:
        ctx = _make_context()
        with pytest.raises((AttributeError, TypeError)):
            ctx.actor_id = "new-id"  # type: ignore[misc]

    def test_frozen_dataclass_raises_on_trust_tier_assignment(self) -> None:
        ctx = _make_context()
        with pytest.raises((AttributeError, TypeError)):
            ctx.trust_tier = "T5"  # type: ignore[misc]

    def test_frozen_dataclass_raises_on_roles_assignment(self) -> None:
        ctx = _make_context()
        with pytest.raises((AttributeError, TypeError)):
            ctx.roles = frozenset(["admin"])  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Actor-type properties
# ---------------------------------------------------------------------------

class TestActorTypeProperties:
    def test_is_agent_returns_true_for_agent_type(self) -> None:
        assert _make_context(actor_type="agent").is_agent is True

    def test_is_agent_returns_false_for_user_type(self) -> None:
        assert _make_context(actor_type="user").is_agent is False

    def test_is_agent_returns_false_for_creator_type(self) -> None:
        assert _make_context(actor_type="creator").is_agent is False

    def test_is_creator_returns_true_for_creator_type(self) -> None:
        assert _make_context(actor_type="creator").is_creator is True

    def test_is_creator_returns_false_for_agent_type(self) -> None:
        assert _make_context(actor_type="agent").is_creator is False

    def test_is_creator_returns_false_for_user_type(self) -> None:
        assert _make_context(actor_type="user").is_creator is False

    def test_is_user_returns_true_for_user_type(self) -> None:
        assert _make_context(actor_type="user").is_user is True

    def test_is_user_returns_false_for_agent_type(self) -> None:
        assert _make_context(actor_type="agent").is_user is False

    def test_is_user_returns_false_for_creator_type(self) -> None:
        assert _make_context(actor_type="creator").is_user is False

    def test_all_three_actor_type_flags_are_mutually_exclusive(self) -> None:
        for actor_type in ("agent", "creator", "user"):
            ctx = _make_context(actor_type=actor_type)
            flags = [ctx.is_agent, ctx.is_creator, ctx.is_user]
            assert flags.count(True) == 1


# ---------------------------------------------------------------------------
# has_role / has_any_role
# ---------------------------------------------------------------------------

class TestRoleChecks:
    def test_has_role_returns_true_when_role_present(self) -> None:
        ctx = _make_context(roles=frozenset(["admin", "viewer"]))
        assert ctx.has_role("admin") is True

    def test_has_role_returns_false_when_role_absent(self) -> None:
        ctx = _make_context(roles=frozenset(["viewer"]))
        assert ctx.has_role("admin") is False

    def test_has_role_returns_false_for_empty_roles(self) -> None:
        ctx = _make_context(roles=frozenset())
        assert ctx.has_role("any") is False

    def test_has_any_role_returns_true_when_one_matches(self) -> None:
        ctx = _make_context(roles=frozenset(["editor"]))
        assert ctx.has_any_role("admin", "editor") is True

    def test_has_any_role_returns_true_when_multiple_match(self) -> None:
        ctx = _make_context(roles=frozenset(["admin", "editor"]))
        assert ctx.has_any_role("admin", "editor") is True

    def test_has_any_role_returns_false_when_none_match(self) -> None:
        ctx = _make_context(roles=frozenset(["viewer"]))
        assert ctx.has_any_role("admin", "editor") is False

    def test_has_any_role_returns_false_for_empty_roles(self) -> None:
        ctx = _make_context(roles=frozenset())
        assert ctx.has_any_role("admin") is False

    def test_has_any_role_with_single_matching_arg(self) -> None:
        ctx = _make_context(roles=frozenset(["moderator"]))
        assert ctx.has_any_role("moderator") is True


# ---------------------------------------------------------------------------
# has_scope
# ---------------------------------------------------------------------------

class TestScopeChecks:
    def test_has_scope_returns_true_for_explicit_scope(self) -> None:
        ctx = _make_context(scopes=frozenset(["read", "write"]))
        assert ctx.has_scope("read") is True

    def test_has_scope_returns_false_for_absent_scope(self) -> None:
        ctx = _make_context(scopes=frozenset(["read"]))
        assert ctx.has_scope("write") is False

    def test_has_scope_returns_true_for_wildcard_regardless_of_requested(self) -> None:
        ctx = _make_context(scopes=frozenset(["*"]))
        assert ctx.has_scope("any_arbitrary_scope") is True

    def test_has_scope_wildcard_grants_write(self) -> None:
        ctx = _make_context(scopes=frozenset(["*"]))
        assert ctx.has_scope("write") is True

    def test_has_scope_wildcard_grants_admin(self) -> None:
        ctx = _make_context(scopes=frozenset(["*"]))
        assert ctx.has_scope("admin") is True

    def test_has_scope_returns_false_for_empty_scopes(self) -> None:
        ctx = _make_context(scopes=frozenset())
        assert ctx.has_scope("read") is False

    def test_has_scope_wildcard_mixed_with_explicit_scopes(self) -> None:
        ctx = _make_context(scopes=frozenset(["read", "*"]))
        assert ctx.has_scope("delete") is True


# ---------------------------------------------------------------------------
# meets_trust_tier
# ---------------------------------------------------------------------------

class TestTrustTierChecks:
    def test_meets_trust_tier_returns_false_when_trust_tier_is_none(self) -> None:
        ctx = _make_context(trust_tier=None)
        assert ctx.meets_trust_tier("T0") is False

    def test_meets_trust_tier_returns_false_when_trust_tier_none_for_higher_tier(self) -> None:
        ctx = _make_context(trust_tier=None)
        assert ctx.meets_trust_tier("T5") is False

    def test_meets_trust_tier_returns_true_when_exact_match(self) -> None:
        for tier in ("T0", "T1", "T2", "T3", "T4", "T5"):
            ctx = _make_context(trust_tier=tier)
            assert ctx.meets_trust_tier(tier) is True, f"Expected {tier} >= {tier}"

    def test_meets_trust_tier_returns_true_when_above_minimum(self) -> None:
        ctx = _make_context(trust_tier="T3")
        assert ctx.meets_trust_tier("T1") is True
        assert ctx.meets_trust_tier("T2") is True

    def test_meets_trust_tier_returns_false_when_below_minimum(self) -> None:
        ctx = _make_context(trust_tier="T2")
        assert ctx.meets_trust_tier("T3") is False
        assert ctx.meets_trust_tier("T5") is False

    def test_meets_trust_tier_t0_meets_t0_only(self) -> None:
        ctx = _make_context(trust_tier="T0")
        assert ctx.meets_trust_tier("T0") is True
        assert ctx.meets_trust_tier("T1") is False

    def test_meets_trust_tier_t5_meets_all_tiers(self) -> None:
        ctx = _make_context(trust_tier="T5")
        for tier in ("T0", "T1", "T2", "T3", "T4", "T5"):
            assert ctx.meets_trust_tier(tier) is True, f"T5 should meet {tier}"

    def test_meets_trust_tier_ordering_t1_less_than_t2(self) -> None:
        t1_ctx = _make_context(trust_tier="T1")
        t2_ctx = _make_context(trust_tier="T2")
        assert t1_ctx.meets_trust_tier("T2") is False
        assert t2_ctx.meets_trust_tier("T1") is True

    def test_meets_trust_tier_ordering_full_sequence(self) -> None:
        tiers = ["T0", "T1", "T2", "T3", "T4", "T5"]
        for i, current in enumerate(tiers):
            ctx = _make_context(trust_tier=current)
            # Should meet all tiers at or below current level
            for j, required in enumerate(tiers):
                expected = i >= j
                result = ctx.meets_trust_tier(required)
                assert result == expected, (
                    f"meets_trust_tier: current={current}, required={required}, "
                    f"expected={expected}, got={result}"
                )
