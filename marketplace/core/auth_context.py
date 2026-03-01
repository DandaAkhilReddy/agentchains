"""Unified authentication context shared across all auth flows."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AuthContext:
    """Immutable authentication context returned by all auth dependencies.

    Carries the authenticated actor's identity, roles, trust tier, token
    identifier (for revocation), and fine-grained scopes.
    """

    actor_id: str
    actor_type: str  # "agent" | "creator" | "user"
    roles: frozenset[str]
    trust_tier: str | None  # "T0"-"T5" for agents, None for humans
    token_jti: str
    scopes: frozenset[str]

    @property
    def is_agent(self) -> bool:
        return self.actor_type == "agent"

    @property
    def is_creator(self) -> bool:
        return self.actor_type == "creator"

    @property
    def is_user(self) -> bool:
        return self.actor_type == "user"

    def has_role(self, role: str) -> bool:
        return role in self.roles

    def has_any_role(self, *roles: str) -> bool:
        return bool(self.roles & frozenset(roles))

    def has_scope(self, scope: str) -> bool:
        return "*" in self.scopes or scope in self.scopes

    def meets_trust_tier(self, min_tier: str) -> bool:
        """Check if agent's trust tier meets or exceeds the minimum required tier."""
        if self.trust_tier is None:
            return False
        tier_order = {"T0": 0, "T1": 1, "T2": 2, "T3": 3, "T4": 4, "T5": 5}
        current = tier_order.get(self.trust_tier, 0)
        required = tier_order.get(min_tier, 0)
        return current >= required
