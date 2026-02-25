"""Tests for marketplace.core.rate_limiter — sliding window rate limiting.

Covers:
- SlidingWindowRateLimiter.check: authenticated/anonymous limits, window reset,
  header generation, Retry-After on exceeded limits
- _maybe_cleanup: stale bucket removal
- Key isolation: different keys have independent windows
"""

from __future__ import annotations

import time
from unittest.mock import patch

import pytest

from marketplace.core.rate_limiter import SlidingWindowRateLimiter, _Window


# ---------------------------------------------------------------------------
# _Window dataclass
# ---------------------------------------------------------------------------


class TestWindow:
    """Defaults for the internal _Window dataclass."""

    def test_default_count_is_zero(self) -> None:
        w = _Window()
        assert w.count == 0

    def test_default_window_start_is_monotonic(self) -> None:
        before = time.monotonic()
        w = _Window()
        after = time.monotonic()
        assert before <= w.window_start <= after


# ---------------------------------------------------------------------------
# SlidingWindowRateLimiter.check — basic behavior
# ---------------------------------------------------------------------------


class TestRateLimiterCheck:
    """Core rate limit check logic."""

    def test_first_request_is_allowed(self) -> None:
        limiter = SlidingWindowRateLimiter()
        allowed, headers = limiter.check("test-key")
        assert allowed is True
        assert "X-RateLimit-Limit" in headers
        assert "X-RateLimit-Remaining" in headers
        assert "X-RateLimit-Reset" in headers

    def test_anonymous_limit_applied(self) -> None:
        limiter = SlidingWindowRateLimiter()
        allowed, headers = limiter.check("anon-key", authenticated=False)
        assert allowed is True
        # The limit header should match the anonymous setting
        from marketplace.config import settings

        assert headers["X-RateLimit-Limit"] == str(settings.rest_rate_limit_anonymous)

    def test_authenticated_limit_applied(self) -> None:
        limiter = SlidingWindowRateLimiter()
        allowed, headers = limiter.check("auth-key", authenticated=True)
        assert allowed is True
        from marketplace.config import settings

        assert headers["X-RateLimit-Limit"] == str(settings.rest_rate_limit_authenticated)

    def test_remaining_decreases_with_each_request(self) -> None:
        limiter = SlidingWindowRateLimiter()
        _, h1 = limiter.check("dec-key")
        _, h2 = limiter.check("dec-key")
        r1 = int(h1["X-RateLimit-Remaining"])
        r2 = int(h2["X-RateLimit-Remaining"])
        assert r2 < r1

    def test_exceeding_limit_returns_false_and_retry_after(self) -> None:
        limiter = SlidingWindowRateLimiter()
        from marketplace.config import settings

        limit = settings.rest_rate_limit_anonymous
        # Exhaust the limit
        for _ in range(limit):
            limiter.check("exhaust-key", authenticated=False)

        # Next request should be denied
        allowed, headers = limiter.check("exhaust-key", authenticated=False)
        assert allowed is False
        assert "Retry-After" in headers
        assert int(headers["Retry-After"]) >= 0

    def test_remaining_never_goes_negative(self) -> None:
        limiter = SlidingWindowRateLimiter()
        from marketplace.config import settings

        limit = settings.rest_rate_limit_anonymous
        for _ in range(limit + 5):
            _, headers = limiter.check("neg-key", authenticated=False)

        assert int(headers["X-RateLimit-Remaining"]) == 0


# ---------------------------------------------------------------------------
# Window reset
# ---------------------------------------------------------------------------


class TestRateLimiterWindowReset:
    """Window resets after 60 seconds."""

    def test_window_resets_after_60_seconds(self) -> None:
        limiter = SlidingWindowRateLimiter()
        from marketplace.config import settings

        limit = settings.rest_rate_limit_anonymous

        # Exhaust the limit
        for _ in range(limit + 1):
            limiter.check("reset-key", authenticated=False)

        allowed_before, _ = limiter.check("reset-key", authenticated=False)
        assert allowed_before is False

        # Simulate time passing by manipulating the bucket's window_start
        bucket = limiter._buckets["reset-key"]
        bucket.window_start = time.monotonic() - 61  # 61 seconds ago

        allowed_after, headers = limiter.check("reset-key", authenticated=False)
        assert allowed_after is True
        # Count should have been reset to 1
        assert int(headers["X-RateLimit-Remaining"]) == limit - 1


# ---------------------------------------------------------------------------
# Key isolation
# ---------------------------------------------------------------------------


class TestRateLimiterKeyIsolation:
    """Different keys maintain independent rate limits."""

    def test_different_keys_have_independent_counters(self) -> None:
        limiter = SlidingWindowRateLimiter()
        from marketplace.config import settings

        limit = settings.rest_rate_limit_anonymous

        # Exhaust key-a
        for _ in range(limit + 1):
            limiter.check("key-a", authenticated=False)

        # key-b should still be allowed
        allowed, _ = limiter.check("key-b", authenticated=False)
        assert allowed is True

    def test_authenticated_and_anonymous_same_key_use_same_bucket(self) -> None:
        """Same key string shares one bucket regardless of auth flag."""
        limiter = SlidingWindowRateLimiter()
        limiter.check("shared-key", authenticated=True)
        limiter.check("shared-key", authenticated=False)
        # Both should have incremented the same bucket
        assert limiter._buckets["shared-key"].count == 2


# ---------------------------------------------------------------------------
# _maybe_cleanup
# ---------------------------------------------------------------------------


class TestRateLimiterCleanup:
    """Stale bucket cleanup."""

    def test_stale_buckets_removed(self) -> None:
        limiter = SlidingWindowRateLimiter()
        # Create a bucket
        limiter.check("stale-key")
        assert "stale-key" in limiter._buckets

        # Make the bucket stale (window_start > 600s ago)
        limiter._buckets["stale-key"].window_start = time.monotonic() - 700

        # Force cleanup to run by advancing _last_cleanup
        limiter._last_cleanup = time.monotonic() - 301

        # Trigger cleanup via check on another key
        limiter.check("trigger-key")
        assert "stale-key" not in limiter._buckets

    def test_fresh_buckets_not_removed(self) -> None:
        limiter = SlidingWindowRateLimiter()
        limiter.check("fresh-key")

        # Force cleanup timing
        limiter._last_cleanup = time.monotonic() - 301
        limiter.check("trigger-key")

        # Fresh bucket should survive
        assert "fresh-key" in limiter._buckets

    def test_cleanup_skipped_if_too_recent(self) -> None:
        limiter = SlidingWindowRateLimiter()
        limiter.check("some-key")
        limiter._buckets["some-key"].window_start = time.monotonic() - 700

        # _last_cleanup is recent, so cleanup should be skipped
        limiter._last_cleanup = time.monotonic()
        limiter._maybe_cleanup(time.monotonic())

        # Stale bucket should still exist because cleanup was skipped
        assert "some-key" in limiter._buckets


# ---------------------------------------------------------------------------
# Header format
# ---------------------------------------------------------------------------


class TestRateLimiterHeaders:
    """Response header correctness."""

    def test_reset_is_non_negative(self) -> None:
        limiter = SlidingWindowRateLimiter()
        _, headers = limiter.check("hdr-key")
        assert int(headers["X-RateLimit-Reset"]) >= 0

    def test_limit_header_is_string_integer(self) -> None:
        limiter = SlidingWindowRateLimiter()
        _, headers = limiter.check("hdr-key")
        int(headers["X-RateLimit-Limit"])  # should not raise

    def test_retry_after_at_least_one_second(self) -> None:
        limiter = SlidingWindowRateLimiter()
        from marketplace.config import settings

        limit = settings.rest_rate_limit_anonymous
        for _ in range(limit + 1):
            limiter.check("retry-key")

        _, headers = limiter.check("retry-key")
        assert int(headers["Retry-After"]) >= 1
