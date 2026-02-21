"""Rate limit plugin — per-agent sliding window rate limiter."""

from __future__ import annotations

import logging
import time
from collections import defaultdict
from typing import Any

logger = logging.getLogger(__name__)

PLUGIN_JSON = {
    "name": "rate_limit_plugin",
    "version": "0.1.0",
    "author": "AgentChains Team",
    "description": "Per-agent rate limiting using a simple sliding window counter.",
    "entry_point": "marketplace.plugins.examples.rate_limit_plugin:RateLimitPlugin",
}

# Defaults
DEFAULT_WINDOW_SECONDS = 60
DEFAULT_MAX_REQUESTS = 30


class RateLimitPlugin:
    """Enforces per-agent rate limits via a sliding window counter.

    When an ``agent_registered`` event fires, the plugin records
    the timestamp.  Subsequent calls to :meth:`is_allowed` check
    whether the agent has exceeded *max_requests* within the
    current *window_seconds* window.
    """

    meta = PLUGIN_JSON

    def __init__(
        self,
        window_seconds: int = DEFAULT_WINDOW_SECONDS,
        max_requests: int = DEFAULT_MAX_REQUESTS,
    ) -> None:
        self.window_seconds = window_seconds
        self.max_requests = max_requests
        # agent_id -> list of timestamps
        self._requests: dict[str, list[float]] = defaultdict(list)

    async def on_load(self) -> None:
        """Called when the plugin is loaded by the PluginLoader."""
        logger.info(
            "[RateLimitPlugin] Loaded — window=%ds, max=%d requests",
            self.window_seconds,
            self.max_requests,
        )

    async def on_unload(self) -> None:
        """Called when the plugin is unloaded."""
        logger.info("[RateLimitPlugin] Unloaded — clearing rate limit state.")
        self._requests.clear()

    # ------------------------------------------------------------------
    # Hook handler
    # ------------------------------------------------------------------

    async def on_agent_registered(self, data: Any) -> None:
        """Hook: ``agent_registered`` — record activity timestamp.

        *data* is expected to contain at least an ``agent_id`` key.
        """
        agent_id = data.get("agent_id", "unknown") if isinstance(data, dict) else str(data)
        self._record(agent_id)
        allowed = self.is_allowed(agent_id)
        if not allowed:
            logger.warning(
                "[RateLimitPlugin] Agent %s exceeded rate limit (%d/%ds)",
                agent_id,
                self.max_requests,
                self.window_seconds,
            )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def is_allowed(self, agent_id: str) -> bool:
        """Return ``True`` if *agent_id* has not exceeded the rate limit."""
        self._prune(agent_id)
        return len(self._requests[agent_id]) <= self.max_requests

    def get_remaining(self, agent_id: str) -> int:
        """Return the number of remaining requests for *agent_id*."""
        self._prune(agent_id)
        return max(0, self.max_requests - len(self._requests[agent_id]))

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _record(self, agent_id: str) -> None:
        """Record a new request timestamp for *agent_id*."""
        self._requests[agent_id].append(time.monotonic())

    def _prune(self, agent_id: str) -> None:
        """Remove timestamps outside the current sliding window."""
        cutoff = time.monotonic() - self.window_seconds
        self._requests[agent_id] = [
            ts for ts in self._requests[agent_id] if ts > cutoff
        ]
