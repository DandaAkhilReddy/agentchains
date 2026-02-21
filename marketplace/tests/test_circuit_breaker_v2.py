"""Tests for the circuit breaker pattern implementation."""

import time
from unittest.mock import patch
import pytest

from marketplace.services.circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerRegistry,
    CircuitState,
    circuit_breaker_registry,
)


class TestCircuitState:
    def test_closed_value(self):
        assert CircuitState.CLOSED.value == "closed"

    def test_open_value(self):
        assert CircuitState.OPEN.value == "open"

    def test_half_open_value(self):
        assert CircuitState.HALF_OPEN.value == "half_open"

    def test_states_are_unique(self):
        values = [s.value for s in CircuitState]
        assert len(values) == len(set(values))


class TestCircuitBreakerDefaults:
    def test_initial_state_is_closed(self):
        cb = CircuitBreaker()
        assert cb.state == CircuitState.CLOSED

    def test_default_failure_threshold(self):
        cb = CircuitBreaker()
        assert cb._failure_threshold == 5

    def test_default_recovery_timeout(self):
        cb = CircuitBreaker()
        assert cb._recovery_timeout == 60.0

    def test_default_half_open_max_calls(self):
        cb = CircuitBreaker()
        assert cb._half_open_max_calls == 3

    def test_custom_failure_threshold(self):
        cb = CircuitBreaker(failure_threshold=10)
        assert cb._failure_threshold == 10

    def test_custom_recovery_timeout(self):
        cb = CircuitBreaker(recovery_timeout=30.0)
        assert cb._recovery_timeout == 30.0

    def test_custom_half_open_max_calls(self):
        cb = CircuitBreaker(half_open_max_calls=1)
        assert cb._half_open_max_calls == 1


class TestCircuitBreakerClosedState:
    def test_allows_requests_when_closed(self):
        cb = CircuitBreaker()
        assert cb.allow_request() is True

    def test_stays_closed_after_single_failure(self):
        cb = CircuitBreaker(failure_threshold=5)
        cb.record_failure()
        assert cb.state == CircuitState.CLOSED

    def test_stays_closed_below_threshold(self):
        cb = CircuitBreaker(failure_threshold=5)
        for _ in range(4):
            cb.record_failure()
        assert cb.state == CircuitState.CLOSED

    def test_success_resets_failure_count(self):
        cb = CircuitBreaker(failure_threshold=5)
        for _ in range(3):
            cb.record_failure()
        cb.record_success()
        assert cb._failure_count == 0

    def test_allows_many_requests_when_closed(self):
        cb = CircuitBreaker()
        for _ in range(100):
            assert cb.allow_request() is True


class TestCircuitBreakerOpenState:
    def test_opens_at_failure_threshold(self):
        cb = CircuitBreaker(failure_threshold=3)
        for _ in range(3):
            cb.record_failure()
        assert cb.state == CircuitState.OPEN

    def test_blocks_requests_when_open(self):
        cb = CircuitBreaker(failure_threshold=2)
        cb.record_failure()
        cb.record_failure()
        assert cb.allow_request() is False

    def test_stays_open_before_timeout(self):
        cb = CircuitBreaker(failure_threshold=1, recovery_timeout=60.0)
        cb.record_failure()
        assert cb.state == CircuitState.OPEN

    def test_transitions_to_half_open_after_timeout(self):
        cb = CircuitBreaker(failure_threshold=1, recovery_timeout=0.01)
        cb.record_failure()
        assert cb.state == CircuitState.OPEN
        time.sleep(0.02)
        assert cb.state == CircuitState.HALF_OPEN

    def test_opens_after_exact_threshold(self):
        cb = CircuitBreaker(failure_threshold=5)
        for _ in range(5):
            cb.record_failure()
        assert cb.state == CircuitState.OPEN

    def test_records_last_failure_time(self):
        cb = CircuitBreaker(failure_threshold=1)
        cb.record_failure()
        assert cb._last_failure_time > 0


class TestCircuitBreakerHalfOpenState:
    def test_allows_limited_requests_in_half_open(self):
        cb = CircuitBreaker(failure_threshold=1, recovery_timeout=0.01, half_open_max_calls=2)
        cb.record_failure()
        time.sleep(0.02)
        assert cb.allow_request() is True
        assert cb.allow_request() is True
        assert cb.allow_request() is False

    def test_failure_in_half_open_reopens(self):
        cb = CircuitBreaker(failure_threshold=1, recovery_timeout=0.01)
        cb.record_failure()
        time.sleep(0.02)
        assert cb.state == CircuitState.HALF_OPEN
        cb.record_failure()
        assert cb.state == CircuitState.OPEN

    def test_success_in_half_open_tracks_count(self):
        cb = CircuitBreaker(failure_threshold=1, recovery_timeout=0.01, half_open_max_calls=3)
        cb.record_failure()
        time.sleep(0.02)
        cb.record_success()
        assert cb._success_count == 1

    def test_enough_successes_close_circuit(self):
        cb = CircuitBreaker(failure_threshold=1, recovery_timeout=0.01, half_open_max_calls=2)
        cb.record_failure()
        time.sleep(0.02)
        cb.state  # trigger transition to half-open
        cb.record_success()
        cb.record_success()
        assert cb.state == CircuitState.CLOSED

    def test_closed_after_recovery_resets_counts(self):
        cb = CircuitBreaker(failure_threshold=1, recovery_timeout=0.01, half_open_max_calls=1)
        cb.record_failure()
        time.sleep(0.02)
        cb.state  # half-open
        cb.record_success()
        assert cb._failure_count == 0
        assert cb._success_count == 0

    def test_half_open_resets_half_open_calls(self):
        cb = CircuitBreaker(failure_threshold=1, recovery_timeout=0.01, half_open_max_calls=3)
        cb.record_failure()
        time.sleep(0.02)
        cb.state  # trigger half-open
        assert cb._half_open_calls == 0


class TestCircuitBreakerReset:
    def test_reset_returns_to_closed(self):
        cb = CircuitBreaker(failure_threshold=1)
        cb.record_failure()
        assert cb.state == CircuitState.OPEN
        cb.reset()
        assert cb.state == CircuitState.CLOSED

    def test_reset_clears_failure_count(self):
        cb = CircuitBreaker()
        for _ in range(3):
            cb.record_failure()
        cb.reset()
        assert cb._failure_count == 0

    def test_reset_clears_success_count(self):
        cb = CircuitBreaker()
        cb.reset()
        assert cb._success_count == 0

    def test_reset_allows_requests_again(self):
        cb = CircuitBreaker(failure_threshold=1)
        cb.record_failure()
        assert cb.allow_request() is False
        cb.reset()
        assert cb.allow_request() is True


class TestCircuitBreakerRegistry:
    def test_creates_breaker_for_new_agent(self):
        reg = CircuitBreakerRegistry()
        breaker = reg.get_breaker("agent-1")
        assert isinstance(breaker, CircuitBreaker)

    def test_returns_same_breaker_for_same_agent(self):
        reg = CircuitBreakerRegistry()
        b1 = reg.get_breaker("agent-1")
        b2 = reg.get_breaker("agent-1")
        assert b1 is b2

    def test_returns_different_breakers_for_different_agents(self):
        reg = CircuitBreakerRegistry()
        b1 = reg.get_breaker("agent-1")
        b2 = reg.get_breaker("agent-2")
        assert b1 is not b2

    def test_reset_all_resets_every_breaker(self):
        reg = CircuitBreakerRegistry()
        b1 = reg.get_breaker("agent-1")
        b2 = reg.get_breaker("agent-2")
        b1._state = CircuitState.OPEN
        b2._state = CircuitState.OPEN
        reg.reset_all()
        assert b1.state == CircuitState.CLOSED
        assert b2.state == CircuitState.CLOSED

    def test_singleton_registry_exists(self):
        assert isinstance(circuit_breaker_registry, CircuitBreakerRegistry)

    def test_registry_handles_many_agents(self):
        reg = CircuitBreakerRegistry()
        for i in range(50):
            breaker = reg.get_breaker(f"agent-{i}")
            assert breaker.state == CircuitState.CLOSED
        assert len(reg._breakers) == 50


class TestCircuitBreakerFullCycle:
    def test_full_lifecycle(self):
        """Test complete circuit breaker lifecycle: closed -> open -> half-open -> closed."""
        cb = CircuitBreaker(failure_threshold=2, recovery_timeout=0.01, half_open_max_calls=1)

        # Start closed
        assert cb.state == CircuitState.CLOSED
        assert cb.allow_request() is True

        # Record failures to open
        cb.record_failure()
        cb.record_failure()
        assert cb.state == CircuitState.OPEN
        assert cb.allow_request() is False

        # Wait for recovery timeout
        time.sleep(0.02)
        assert cb.state == CircuitState.HALF_OPEN
        assert cb.allow_request() is True

        # Success closes the circuit
        cb.record_success()
        assert cb.state == CircuitState.CLOSED
        assert cb.allow_request() is True

    def test_repeated_open_close_cycles(self):
        cb = CircuitBreaker(failure_threshold=1, recovery_timeout=0.01, half_open_max_calls=1)
        for _ in range(3):
            cb.record_failure()
            assert cb.state == CircuitState.OPEN
            time.sleep(0.02)
            cb.state  # half-open
            cb.record_success()
            assert cb.state == CircuitState.CLOSED

    def test_half_open_failure_reopen_then_recover(self):
        cb = CircuitBreaker(failure_threshold=1, recovery_timeout=0.01, half_open_max_calls=1)
        cb.record_failure()
        time.sleep(0.02)
        cb.state  # half-open
        cb.record_failure()  # re-open
        assert cb.state == CircuitState.OPEN
        time.sleep(0.02)
        cb.state  # half-open again
        cb.record_success()
        assert cb.state == CircuitState.CLOSED
