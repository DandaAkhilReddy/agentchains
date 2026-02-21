"""MCP Federation load balancer.

Provides 4 routing strategies for distributing tool calls across
federated MCP servers that expose the same namespace:

1. round_robin — Cycle through servers sequentially
2. least_loaded — Route to server with fewest in-flight requests
3. weighted — Route proportional to health score
4. health_first — Always pick the healthiest server
"""

from __future__ import annotations

import logging
import random
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


class LoadBalanceStrategy(str, Enum):
    ROUND_ROBIN = "round_robin"
    LEAST_LOADED = "least_loaded"
    WEIGHTED = "weighted"
    HEALTH_FIRST = "health_first"


@dataclass
class ServerInfo:
    """Lightweight representation of an MCP server for load balancing."""

    server_id: str
    base_url: str
    health_score: int = 100
    in_flight: int = 0


class MCPLoadBalancer:
    """Load balancer for distributing calls across federated MCP servers."""

    def __init__(self, strategy: LoadBalanceStrategy = LoadBalanceStrategy.HEALTH_FIRST):
        self.strategy = strategy
        # namespace -> list of ServerInfo
        self._pools: dict[str, list[ServerInfo]] = {}
        # Round-robin counters per namespace
        self._rr_counters: dict[str, int] = {}

    def register_server(self, namespace: str, server: ServerInfo) -> None:
        """Add a server to the namespace pool."""
        if namespace not in self._pools:
            self._pools[namespace] = []
        # Avoid duplicates
        existing_ids = {s.server_id for s in self._pools[namespace]}
        if server.server_id not in existing_ids:
            self._pools[namespace].append(server)

    def remove_server(self, namespace: str, server_id: str) -> None:
        """Remove a server from the namespace pool."""
        if namespace in self._pools:
            self._pools[namespace] = [
                s for s in self._pools[namespace] if s.server_id != server_id
            ]

    def update_health(self, namespace: str, server_id: str, score: int) -> None:
        """Update a server's health score."""
        if namespace in self._pools:
            for server in self._pools[namespace]:
                if server.server_id == server_id:
                    server.health_score = score
                    break

    def select_server(self, namespace: str) -> ServerInfo | None:
        """Select the best server for a namespace based on the current strategy."""
        pool = self._pools.get(namespace, [])
        # Filter to healthy servers (score > 0)
        candidates = [s for s in pool if s.health_score > 0]
        if not candidates:
            return None

        if self.strategy == LoadBalanceStrategy.ROUND_ROBIN:
            return self._round_robin(namespace, candidates)
        elif self.strategy == LoadBalanceStrategy.LEAST_LOADED:
            return self._least_loaded(candidates)
        elif self.strategy == LoadBalanceStrategy.WEIGHTED:
            return self._weighted(candidates)
        elif self.strategy == LoadBalanceStrategy.HEALTH_FIRST:
            return self._health_first(candidates)

        return candidates[0]

    def record_request_start(self, namespace: str, server_id: str) -> None:
        """Increment in-flight count for a server."""
        if namespace in self._pools:
            for server in self._pools[namespace]:
                if server.server_id == server_id:
                    server.in_flight += 1
                    break

    def record_request_end(self, namespace: str, server_id: str) -> None:
        """Decrement in-flight count for a server."""
        if namespace in self._pools:
            for server in self._pools[namespace]:
                if server.server_id == server_id:
                    server.in_flight = max(0, server.in_flight - 1)
                    break

    def get_pool(self, namespace: str) -> list[ServerInfo]:
        """Get all servers in a namespace pool."""
        return list(self._pools.get(namespace, []))

    def _round_robin(self, namespace: str, candidates: list[ServerInfo]) -> ServerInfo:
        idx = self._rr_counters.get(namespace, 0) % len(candidates)
        self._rr_counters[namespace] = idx + 1
        return candidates[idx]

    def _least_loaded(self, candidates: list[ServerInfo]) -> ServerInfo:
        return min(candidates, key=lambda s: s.in_flight)

    def _weighted(self, candidates: list[ServerInfo]) -> ServerInfo:
        weights = [max(1, s.health_score) for s in candidates]
        return random.choices(candidates, weights=weights, k=1)[0]

    def _health_first(self, candidates: list[ServerInfo]) -> ServerInfo:
        return max(candidates, key=lambda s: s.health_score)

    def reset(self) -> None:
        """Clear all pools."""
        self._pools.clear()
        self._rr_counters.clear()


# Singleton
mcp_load_balancer = MCPLoadBalancer()
