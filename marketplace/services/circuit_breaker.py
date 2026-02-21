"""Per-agent circuit breaker to prevent cascading failures in agent-to-agent calls.

States:
  CLOSED   — normal operation, requests flow through
  OPEN     — failures exceeded threshold, all requests rejected
  HALF_OPEN — recovery window, limited requests allowed to test recovery
"""

import enum
import logging
import time
import threading

logger = logging.getLogger(__name__)


class CircuitState(enum.Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitBreaker:
    """Circuit breaker for a single agent/service endpoint."""

    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: float = 60.0,
        half_open_max_calls: int = 3,
    ) -> None:
        self._failure_threshold = failure_threshold
        self._recovery_timeout = recovery_timeout
        self._half_open_max_calls = half_open_max_calls

        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._half_open_calls = 0
        self._last_failure_time: float = 0.0
        self._lock = threading.Lock()

    @property
    def state(self) -> CircuitState:
        """Return the current circuit state, transitioning OPEN -> HALF_OPEN if recovery_timeout has passed."""
        with self._lock:
            if self._state == CircuitState.OPEN:
                elapsed = time.monotonic() - self._last_failure_time
                if elapsed >= self._recovery_timeout:
                    self._state = CircuitState.HALF_OPEN
                    self._half_open_calls = 0
                    logger.info("Circuit breaker transitioning OPEN -> HALF_OPEN")
            return self._state

    def record_success(self) -> None:
        """Record a successful call. Resets the breaker to CLOSED if in HALF_OPEN."""
        # Access property to trigger OPEN -> HALF_OPEN if recovery timeout elapsed
        _ = self.state
        with self._lock:
            if self._state == CircuitState.HALF_OPEN:
                self._success_count += 1
                if self._success_count >= self._half_open_max_calls:
                    self._state = CircuitState.CLOSED
                    self._failure_count = 0
                    self._success_count = 0
                    self._half_open_calls = 0
                    logger.info("Circuit breaker recovered -> CLOSED")
            elif self._state == CircuitState.CLOSED:
                # Reset failure count on success in closed state
                self._failure_count = 0

    def record_failure(self) -> None:
        """Record a failed call. Opens the circuit if threshold is exceeded."""
        with self._lock:
            self._failure_count += 1
            self._last_failure_time = time.monotonic()

            if self._state == CircuitState.HALF_OPEN:
                # Any failure in half-open immediately re-opens
                self._state = CircuitState.OPEN
                self._success_count = 0
                self._half_open_calls = 0
                logger.warning("Circuit breaker failure in HALF_OPEN -> OPEN")
            elif self._state == CircuitState.CLOSED:
                if self._failure_count >= self._failure_threshold:
                    self._state = CircuitState.OPEN
                    logger.warning(
                        "Circuit breaker tripped after %d failures -> OPEN",
                        self._failure_count,
                    )

    def allow_request(self) -> bool:
        """Check whether a request should be allowed through.

        CLOSED:    always allow
        OPEN:      block unless recovery_timeout has passed (then transition to HALF_OPEN)
        HALF_OPEN: allow up to half_open_max_calls
        """
        current_state = self.state  # may trigger OPEN -> HALF_OPEN transition

        with self._lock:
            if current_state == CircuitState.CLOSED:
                return True

            if current_state == CircuitState.OPEN:
                return False

            # HALF_OPEN
            if self._half_open_calls < self._half_open_max_calls:
                self._half_open_calls += 1
                return True
            return False

    def reset(self) -> None:
        """Fully reset the circuit breaker to CLOSED state."""
        with self._lock:
            self._state = CircuitState.CLOSED
            self._failure_count = 0
            self._success_count = 0
            self._half_open_calls = 0
            self._last_failure_time = 0.0
            logger.info("Circuit breaker manually reset -> CLOSED")


class CircuitBreakerRegistry:
    """Registry that manages per-agent circuit breakers."""

    def __init__(self) -> None:
        self._breakers: dict[str, CircuitBreaker] = {}
        self._lock = threading.Lock()

    def get_breaker(self, agent_id: str) -> CircuitBreaker:
        """Get or create a circuit breaker for the given agent_id."""
        with self._lock:
            if agent_id not in self._breakers:
                self._breakers[agent_id] = CircuitBreaker()
                logger.debug("Created circuit breaker for agent '%s'", agent_id)
            return self._breakers[agent_id]

    def reset_all(self) -> None:
        """Reset all circuit breakers to CLOSED."""
        with self._lock:
            for agent_id, breaker in self._breakers.items():
                breaker.reset()
            logger.info("Reset all %d circuit breakers", len(self._breakers))


# Singleton registry instance
circuit_breaker_registry = CircuitBreakerRegistry()
