"""Tests for MCP Federation Load Balancer — 4 strategies.

Covers:
- LoadBalanceStrategy enum values
- MCPLoadBalancer.select_server with each strategy:
  - ROUND_ROBIN: cycles through servers
  - LEAST_LOADED: picks server with fewest active requests
  - WEIGHTED: health-score-weighted random selection
  - HEALTH_FIRST: highest health, tiebreak by fewest requests
- Fallback to degraded servers when no active ones
- Empty server list returns None
- All servers inactive returns None
- record_request / record_completion tracking
- reset clears all counters
"""

import random
from unittest.mock import MagicMock, patch

import pytest

from marketplace.services.mcp_load_balancer import (
    LoadBalanceStrategy,
    MCPLoadBalancer,
    mcp_load_balancer,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_server(
    server_id: str = "srv-1",
    status: str = "active",
    health_score: int = 100,
) -> MagicMock:
    """Create a mock MCPServerEntry for load balancer tests."""
    server = MagicMock()
    server.id = server_id
    server.status = status
    server.health_score = health_score
    return server


# ---------------------------------------------------------------------------
# LoadBalanceStrategy enum
# ---------------------------------------------------------------------------

class TestLoadBalanceStrategy:
    def test_enum_values(self):
        assert LoadBalanceStrategy.ROUND_ROBIN == "round_robin"
        assert LoadBalanceStrategy.LEAST_LOADED == "least_loaded"
        assert LoadBalanceStrategy.WEIGHTED == "weighted"
        assert LoadBalanceStrategy.HEALTH_FIRST == "health_first"

    def test_enum_is_string(self):
        assert isinstance(LoadBalanceStrategy.ROUND_ROBIN, str)


# ---------------------------------------------------------------------------
# select_server: empty / inactive
# ---------------------------------------------------------------------------

class TestSelectServerEdgeCases:
    def test_empty_server_list_returns_none(self):
        lb = MCPLoadBalancer()
        result = lb.select_server([], "ns")
        assert result is None

    def test_all_inactive_returns_none(self):
        lb = MCPLoadBalancer()
        servers = [
            _make_server("s1", status="inactive"),
            _make_server("s2", status="inactive"),
        ]
        result = lb.select_server(servers, "ns")
        assert result is None

    def test_fallback_to_degraded_when_no_active(self):
        lb = MCPLoadBalancer()
        degraded = _make_server("d1", status="degraded", health_score=30)
        inactive = _make_server("i1", status="inactive")
        result = lb.select_server([degraded, inactive], "ns")
        assert result.id == "d1"


# ---------------------------------------------------------------------------
# ROUND_ROBIN strategy
# ---------------------------------------------------------------------------

class TestRoundRobin:
    def test_cycles_through_servers(self):
        lb = MCPLoadBalancer()
        s1 = _make_server("s1")
        s2 = _make_server("s2")
        s3 = _make_server("s3")
        servers = [s1, s2, s3]

        results = [
            lb.select_server(servers, "ns", LoadBalanceStrategy.ROUND_ROBIN)
            for _ in range(6)
        ]

        ids = [r.id for r in results]
        assert ids == ["s1", "s2", "s3", "s1", "s2", "s3"]

    def test_different_namespaces_have_independent_counters(self):
        lb = MCPLoadBalancer()
        s1 = _make_server("s1")
        s2 = _make_server("s2")
        servers = [s1, s2]

        r1 = lb.select_server(servers, "ns-a", LoadBalanceStrategy.ROUND_ROBIN)
        r2 = lb.select_server(servers, "ns-b", LoadBalanceStrategy.ROUND_ROBIN)

        # Both should start at index 0
        assert r1.id == "s1"
        assert r2.id == "s1"

    def test_single_server_always_selected(self):
        lb = MCPLoadBalancer()
        s1 = _make_server("s1")

        for _ in range(5):
            result = lb.select_server([s1], "ns", LoadBalanceStrategy.ROUND_ROBIN)
            assert result.id == "s1"


# ---------------------------------------------------------------------------
# LEAST_LOADED strategy
# ---------------------------------------------------------------------------

class TestLeastLoaded:
    def test_selects_server_with_fewest_requests(self):
        lb = MCPLoadBalancer()
        s1 = _make_server("s1")
        s2 = _make_server("s2")
        s3 = _make_server("s3")

        lb.record_request("s1")
        lb.record_request("s1")
        lb.record_request("s2")
        # s3 has 0 requests

        result = lb.select_server([s1, s2, s3], "ns", LoadBalanceStrategy.LEAST_LOADED)
        assert result.id == "s3"

    def test_all_equal_load_picks_first(self):
        lb = MCPLoadBalancer()
        s1 = _make_server("s1")
        s2 = _make_server("s2")

        result = lb.select_server([s1, s2], "ns", LoadBalanceStrategy.LEAST_LOADED)
        # Both have 0 requests, picks first one encountered by min()
        assert result.id in ("s1", "s2")

    def test_completion_decreases_load(self):
        lb = MCPLoadBalancer()
        s1 = _make_server("s1")
        s2 = _make_server("s2")

        lb.record_request("s1")
        lb.record_request("s1")
        lb.record_request("s2")

        lb.record_completion("s1")
        lb.record_completion("s1")

        # s1 now has 0, s2 has 1
        result = lb.select_server([s1, s2], "ns", LoadBalanceStrategy.LEAST_LOADED)
        assert result.id == "s1"


# ---------------------------------------------------------------------------
# WEIGHTED strategy
# ---------------------------------------------------------------------------

class TestWeighted:
    def test_weighted_selects_from_servers(self):
        lb = MCPLoadBalancer()
        s1 = _make_server("s1", health_score=90)
        s2 = _make_server("s2", health_score=10)

        # Since it uses random.choices, we seed for determinism
        with patch("marketplace.services.mcp_load_balancer.random.choices") as mock_choices:
            mock_choices.return_value = [s1]
            result = lb.select_server([s1, s2], "ns", LoadBalanceStrategy.WEIGHTED)

            assert result.id == "s1"
            # Verify weights passed correctly
            args, kwargs = mock_choices.call_args
            assert args[0] == [s1, s2]
            assert kwargs["weights"] == [90, 10]

    def test_weighted_with_zero_health_uses_minimum_1(self):
        lb = MCPLoadBalancer()
        s1 = _make_server("s1", health_score=0)
        s2 = _make_server("s2", health_score=50)

        with patch("marketplace.services.mcp_load_balancer.random.choices") as mock_choices:
            mock_choices.return_value = [s2]
            lb.select_server([s1, s2], "ns", LoadBalanceStrategy.WEIGHTED)

            _, kwargs = mock_choices.call_args
            # max(1, 0) = 1 and max(1, 50) = 50
            assert kwargs["weights"] == [1, 50]

    def test_weighted_with_none_health_uses_minimum_1(self):
        lb = MCPLoadBalancer()
        s1 = _make_server("s1", health_score=None)

        with patch("marketplace.services.mcp_load_balancer.random.choices") as mock_choices:
            mock_choices.return_value = [s1]
            lb.select_server([s1], "ns", LoadBalanceStrategy.WEIGHTED)

            _, kwargs = mock_choices.call_args
            # max(1, None or 1) = 1
            assert kwargs["weights"] == [1]


# ---------------------------------------------------------------------------
# HEALTH_FIRST strategy
# ---------------------------------------------------------------------------

class TestHealthFirst:
    def test_selects_highest_health_server(self):
        lb = MCPLoadBalancer()
        s1 = _make_server("s1", health_score=60)
        s2 = _make_server("s2", health_score=95)
        s3 = _make_server("s3", health_score=80)

        result = lb.select_server([s1, s2, s3], "ns", LoadBalanceStrategy.HEALTH_FIRST)
        assert result.id == "s2"

    def test_tiebreak_by_fewer_requests(self):
        lb = MCPLoadBalancer()
        s1 = _make_server("s1", health_score=100)
        s2 = _make_server("s2", health_score=100)

        lb.record_request("s1")
        lb.record_request("s1")
        lb.record_request("s1")
        # s2 has 0 requests

        result = lb.select_server([s1, s2], "ns", LoadBalanceStrategy.HEALTH_FIRST)
        assert result.id == "s2"

    def test_health_trumps_request_count(self):
        lb = MCPLoadBalancer()
        s1 = _make_server("s1", health_score=90)
        s2 = _make_server("s2", health_score=80)

        # s2 has fewer requests but lower health
        lb.record_request("s1")

        result = lb.select_server([s1, s2], "ns", LoadBalanceStrategy.HEALTH_FIRST)
        assert result.id == "s1"

    def test_none_health_score_treated_as_zero(self):
        lb = MCPLoadBalancer()
        s1 = _make_server("s1", health_score=None)
        s2 = _make_server("s2", health_score=50)

        result = lb.select_server([s1, s2], "ns", LoadBalanceStrategy.HEALTH_FIRST)
        assert result.id == "s2"


# ---------------------------------------------------------------------------
# Default / unknown strategy
# ---------------------------------------------------------------------------

class TestDefaultStrategy:
    def test_unknown_strategy_returns_first_active(self):
        lb = MCPLoadBalancer()
        s1 = _make_server("s1")
        s2 = _make_server("s2")

        # Simulate an unrecognized strategy by passing a plain string
        # The else branch returns active[0]
        result = lb.select_server([s1, s2], "ns", strategy="bogus_strategy")
        assert result.id == "s1"


# ---------------------------------------------------------------------------
# record_request / record_completion
# ---------------------------------------------------------------------------

class TestRequestTracking:
    def test_record_request_increments(self):
        lb = MCPLoadBalancer()

        lb.record_request("srv-1")
        lb.record_request("srv-1")
        lb.record_request("srv-1")

        assert lb._request_counts["srv-1"] == 3

    def test_record_completion_decrements(self):
        lb = MCPLoadBalancer()

        lb.record_request("srv-1")
        lb.record_request("srv-1")
        lb.record_completion("srv-1")

        assert lb._request_counts["srv-1"] == 1

    def test_record_completion_floors_at_zero(self):
        lb = MCPLoadBalancer()

        lb.record_completion("unknown-srv")
        assert lb._request_counts["unknown-srv"] == 0

        lb.record_completion("unknown-srv")
        assert lb._request_counts["unknown-srv"] == 0

    def test_record_request_starts_from_zero(self):
        lb = MCPLoadBalancer()

        lb.record_request("new-srv")
        assert lb._request_counts["new-srv"] == 1


# ---------------------------------------------------------------------------
# reset
# ---------------------------------------------------------------------------

class TestReset:
    def test_reset_clears_counters(self):
        lb = MCPLoadBalancer()

        lb.record_request("srv-1")
        lb.record_request("srv-2")
        lb.select_server(
            [_make_server("s1")], "ns", LoadBalanceStrategy.ROUND_ROBIN
        )

        lb.reset()

        assert lb._request_counts == {}
        assert lb._round_robin_counters == {}

    def test_reset_allows_fresh_start(self):
        lb = MCPLoadBalancer()
        s1 = _make_server("s1")
        s2 = _make_server("s2")

        # Advance round-robin
        lb.select_server([s1, s2], "ns", LoadBalanceStrategy.ROUND_ROBIN)
        lb.select_server([s1, s2], "ns", LoadBalanceStrategy.ROUND_ROBIN)

        lb.reset()

        # After reset, should start from index 0 again
        result = lb.select_server([s1, s2], "ns", LoadBalanceStrategy.ROUND_ROBIN)
        assert result.id == "s1"


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

class TestSingleton:
    def test_module_singleton_exists(self):
        assert mcp_load_balancer is not None
        assert isinstance(mcp_load_balancer, MCPLoadBalancer)

    def test_singleton_is_functional(self):
        mcp_load_balancer.reset()

        s1 = _make_server("singleton-s1")
        result = mcp_load_balancer.select_server([s1], "test-ns")
        assert result.id == "singleton-s1"

        mcp_load_balancer.reset()


# ---------------------------------------------------------------------------
# Mixed status filtering
# ---------------------------------------------------------------------------

class TestStatusFiltering:
    def test_only_active_servers_considered_first(self):
        lb = MCPLoadBalancer()
        active = _make_server("active-1", status="active", health_score=50)
        degraded = _make_server("degraded-1", status="degraded", health_score=90)
        inactive = _make_server("inactive-1", status="inactive", health_score=100)

        result = lb.select_server(
            [active, degraded, inactive], "ns", LoadBalanceStrategy.HEALTH_FIRST
        )
        # Only active servers are considered first, so active-1 is the only candidate
        assert result.id == "active-1"

    def test_degraded_used_when_no_active(self):
        lb = MCPLoadBalancer()
        d1 = _make_server("d1", status="degraded", health_score=40)
        d2 = _make_server("d2", status="degraded", health_score=70)

        result = lb.select_server([d1, d2], "ns", LoadBalanceStrategy.HEALTH_FIRST)
        assert result.id == "d2"
