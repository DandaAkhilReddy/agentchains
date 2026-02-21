"""Abuse detection service — anomaly rules and rate-based detection.

Monitors agent behavior for suspicious patterns and enforces
rate-based abuse rules to protect the marketplace.
"""

import logging
import time
from collections import defaultdict
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class AbuseEvent:
    agent_id: str
    event_type: str
    severity: str  # low, medium, high, critical
    description: str
    timestamp: float = field(default_factory=time.time)
    metadata: dict = field(default_factory=dict)


class AbuseDetectionService:
    """Rule-based abuse detection for marketplace agents."""

    def __init__(self):
        self._event_windows: dict[str, list[float]] = defaultdict(list)
        self._violation_counts: dict[str, int] = defaultdict(int)
        self._blocked_agents: set[str] = set()

        # Configurable thresholds
        self.max_transactions_per_minute = 30
        self.max_failed_auths_per_minute = 10
        self.max_listings_per_hour = 50
        self.max_api_calls_per_minute = 200
        self.violation_threshold_for_block = 10

    async def check_transaction_rate(self, agent_id: str) -> AbuseEvent | None:
        """Check if agent is creating transactions too fast."""
        key = f"tx:{agent_id}"
        if self._is_rate_exceeded(key, self.max_transactions_per_minute, 60):
            event = AbuseEvent(
                agent_id=agent_id,
                event_type="excessive_transactions",
                severity="high",
                description=f"Agent exceeded {self.max_transactions_per_minute} transactions/minute",
            )
            await self._record_violation(agent_id, event)
            return event
        return None

    async def check_auth_failures(self, agent_id: str) -> AbuseEvent | None:
        """Check for brute-force authentication attempts."""
        key = f"auth_fail:{agent_id}"
        if self._is_rate_exceeded(key, self.max_failed_auths_per_minute, 60):
            event = AbuseEvent(
                agent_id=agent_id,
                event_type="brute_force_auth",
                severity="critical",
                description=f"Agent exceeded {self.max_failed_auths_per_minute} failed auths/minute",
            )
            await self._record_violation(agent_id, event)
            return event
        return None

    async def check_listing_spam(self, agent_id: str) -> AbuseEvent | None:
        """Check for listing spam (too many listings created too fast)."""
        key = f"listing:{agent_id}"
        if self._is_rate_exceeded(key, self.max_listings_per_hour, 3600):
            event = AbuseEvent(
                agent_id=agent_id,
                event_type="listing_spam",
                severity="medium",
                description=f"Agent exceeded {self.max_listings_per_hour} listings/hour",
            )
            await self._record_violation(agent_id, event)
            return event
        return None

    async def check_api_abuse(self, agent_id: str) -> AbuseEvent | None:
        """Check for excessive API calls."""
        key = f"api:{agent_id}"
        if self._is_rate_exceeded(key, self.max_api_calls_per_minute, 60):
            event = AbuseEvent(
                agent_id=agent_id,
                event_type="api_abuse",
                severity="medium",
                description=f"Agent exceeded {self.max_api_calls_per_minute} API calls/minute",
            )
            await self._record_violation(agent_id, event)
            return event
        return None

    def record_event(self, key: str) -> None:
        """Record a timestamped event for rate checking."""
        self._event_windows[key].append(time.time())

    def is_blocked(self, agent_id: str) -> bool:
        """Check if an agent is currently blocked."""
        return agent_id in self._blocked_agents

    def unblock_agent(self, agent_id: str) -> bool:
        """Manually unblock an agent."""
        if agent_id in self._blocked_agents:
            self._blocked_agents.discard(agent_id)
            self._violation_counts[agent_id] = 0
            logger.info("Agent unblocked: %s", agent_id)
            return True
        return False

    def get_violation_count(self, agent_id: str) -> int:
        """Get the total violation count for an agent."""
        return self._violation_counts.get(agent_id, 0)

    def get_blocked_agents(self) -> list[str]:
        """List all currently blocked agents."""
        return list(self._blocked_agents)

    def _is_rate_exceeded(self, key: str, limit: int, window_seconds: int) -> bool:
        """Check if events exceed the rate limit within the window."""
        now = time.time()
        cutoff = now - window_seconds

        # Clean old events
        events = self._event_windows[key]
        self._event_windows[key] = [t for t in events if t > cutoff]

        # Record this event
        self._event_windows[key].append(now)

        return len(self._event_windows[key]) > limit

    async def _record_violation(self, agent_id: str, event: AbuseEvent) -> None:
        """Record a violation and potentially block the agent."""
        self._violation_counts[agent_id] = self._violation_counts.get(agent_id, 0) + 1
        count = self._violation_counts[agent_id]

        logger.warning(
            "Abuse detected: agent=%s type=%s severity=%s violations=%d",
            agent_id, event.event_type, event.severity, count,
        )

        if count >= self.violation_threshold_for_block:
            self._blocked_agents.add(agent_id)
            logger.critical(
                "Agent auto-blocked due to %d violations: %s",
                count, agent_id,
            )

    def cleanup_old_events(self, max_age_seconds: int = 7200) -> int:
        """Remove events older than max_age_seconds. Returns count removed."""
        cutoff = time.time() - max_age_seconds
        removed = 0
        for key in list(self._event_windows.keys()):
            before = len(self._event_windows[key])
            self._event_windows[key] = [t for t in self._event_windows[key] if t > cutoff]
            removed += before - len(self._event_windows[key])
            if not self._event_windows[key]:
                del self._event_windows[key]
        return removed


# Singleton
abuse_detection_service = AbuseDetectionService()
