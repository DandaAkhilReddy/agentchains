"""MCP Federation load balancer — 4 strategies for routing tool calls.

When multiple MCP servers provide the same tool in a namespace,
selects the best server based on the chosen strategy.
"""

import logging
import random
from enum import Enum

logger = logging.getLogger(__name__)


class LoadBalanceStrategy(str, Enum):
    ROUND_ROBIN = "round_robin"
    LEAST_LOADED = "least_loaded"
    WEIGHTED = "weighted"
    HEALTH_FIRST = "health_first"


class MCPLoadBalancer:
    """Load balancer for federated MCP server selection."""

    def __init__(self):
        self._round_robin_counters: dict[str, int] = {}
        self._request_counts: dict[str, int] = {}

    def select_server(
        self,
        servers: list,
        namespace: str,
        strategy: LoadBalanceStrategy = LoadBalanceStrategy.HEALTH_FIRST,
    ):
        """Select the best server from a list of candidates.

        Args:
            servers: List of MCPServerEntry objects
            namespace: Tool namespace for round-robin tracking
            strategy: Load balancing strategy

        Returns:
            Selected MCPServerEntry or None if no servers available
        """
        if not servers:
            return None

        active = [s for s in servers if s.status == "active"]
        if not active:
            # Fall back to degraded servers if no active ones
            active = [s for s in servers if s.status == "degraded"]
        if not active:
            return None

        if strategy == LoadBalanceStrategy.ROUND_ROBIN:
            return self._round_robin(active, namespace)
        elif strategy == LoadBalanceStrategy.LEAST_LOADED:
            return self._least_loaded(active)
        elif strategy == LoadBalanceStrategy.WEIGHTED:
            return self._weighted(active)
        elif strategy == LoadBalanceStrategy.HEALTH_FIRST:
            return self._health_first(active)
        else:
            return active[0]

    def record_request(self, server_id: str) -> None:
        """Track request count for least-loaded strategy."""
        self._request_counts[server_id] = self._request_counts.get(server_id, 0) + 1

    def record_completion(self, server_id: str) -> None:
        """Decrement active request count on completion."""
        count = self._request_counts.get(server_id, 1)
        self._request_counts[server_id] = max(0, count - 1)

    def _round_robin(self, servers: list, namespace: str):
        """Simple round-robin selection."""
        idx = self._round_robin_counters.get(namespace, 0)
        selected = servers[idx % len(servers)]
        self._round_robin_counters[namespace] = idx + 1
        return selected

    def _least_loaded(self, servers: list):
        """Select server with fewest active requests."""
        return min(servers, key=lambda s: self._request_counts.get(s.id, 0))

    def _weighted(self, servers: list):
        """Select server weighted by health score."""
        weights = [max(1, s.health_score or 1) for s in servers]
        return random.choices(servers, weights=weights, k=1)[0]

    def _health_first(self, servers: list):
        """Select the healthiest server, break ties by least requests."""
        return max(
            servers,
            key=lambda s: (
                s.health_score or 0,
                -(self._request_counts.get(s.id, 0)),
            ),
        )

    def reset(self) -> None:
        """Reset all counters."""
        self._round_robin_counters.clear()
        self._request_counts.clear()


# Singleton
mcp_load_balancer = MCPLoadBalancer()
