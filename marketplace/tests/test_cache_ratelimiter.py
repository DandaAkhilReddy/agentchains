"""Tests for TTLCache and SlidingWindowRateLimiter — 30 tests total.

TTLCache: 15 tests covering put/get, expiry, LRU eviction, stats, singletons.
SlidingWindowRateLimiter: 15 tests covering limits, headers, cleanup, key isolation.
"""

import time

import pytest

from marketplace.services.cache_service import (
    TTLCache,
    listing_cache,
    content_cache,
    agent_cache,
)
from marketplace.core.rate_limiter import SlidingWindowRateLimiter


# ═══════════════════════════════════════════════════════════════════════════
# TTLCache — 15 tests
# ═══════════════════════════════════════════════════════════════════════════


class TestTTLCache:
    """Pure unit tests — each test creates its own TTLCache instance."""

    # 1
    def test_put_and_get_roundtrip(self):
        """put() stores a value and get() retrieves it."""
        cache = TTLCache(maxsize=5, default_ttl=10.0)
        cache.put("k1", "hello")
        assert cache.get("k1") == "hello"

    # 2
    def test_get_missing_key_returns_none(self):
        """get() on a key that was never stored returns None."""
        cache = TTLCache(maxsize=5, default_ttl=10.0)
        assert cache.get("nonexistent") is None

    # 3
    def test_get_expired_key_returns_none(self):
        """Expired entries are evicted on access and return None."""
        cache = TTLCache(maxsize=5, default_ttl=10.0)
        cache.put("k1", "value", ttl=0.01)
        time.sleep(0.02)
        assert cache.get("k1") is None

    # 4
    def test_lru_eviction_when_over_maxsize(self):
        """When maxsize=2 and a 3rd item is inserted, the LRU (first) is evicted."""
        cache = TTLCache(maxsize=2, default_ttl=10.0)
        cache.put("a", 1)
        cache.put("b", 2)
        cache.put("c", 3)  # evicts "a"
        assert cache.get("a") is None
        assert cache.get("b") == 2
        assert cache.get("c") == 3

    # 5
    def test_put_updates_existing_key(self):
        """Putting the same key twice overwrites and moves it to end."""
        cache = TTLCache(maxsize=2, default_ttl=10.0)
        cache.put("a", 1)
        cache.put("b", 2)
        cache.put("a", 10)  # update "a" — moves to end, "b" is now LRU
        cache.put("c", 3)   # evicts "b" (the LRU)
        assert cache.get("a") == 10
        assert cache.get("b") is None
        assert cache.get("c") == 3

    # 6
    def test_invalidate_existing_returns_true(self):
        """invalidate() on a present key removes it and returns True."""
        cache = TTLCache(maxsize=5, default_ttl=10.0)
        cache.put("k1", "value")
        assert cache.invalidate("k1") is True
        assert cache.get("k1") is None

    # 7
    def test_invalidate_missing_returns_false(self):
        """invalidate() on a missing key returns False."""
        cache = TTLCache(maxsize=5, default_ttl=10.0)
        assert cache.invalidate("nope") is False

    # 8
    def test_clear_removes_all_entries(self):
        """clear() wipes every entry."""
        cache = TTLCache(maxsize=5, default_ttl=10.0)
        cache.put("a", 1)
        cache.put("b", 2)
        cache.put("c", 3)
        cache.clear()
        assert cache.get("a") is None
        assert cache.get("b") is None
        assert cache.get("c") is None
        assert cache.stats()["size"] == 0

    # 9
    def test_stats_initial(self):
        """A fresh cache has hits=0, misses=0, size=0."""
        cache = TTLCache(maxsize=5, default_ttl=10.0)
        s = cache.stats()
        assert s["hits"] == 0
        assert s["misses"] == 0
        assert s["size"] == 0

    # 10
    def test_stats_after_operations(self):
        """Stats track hits, misses, and current size correctly."""
        cache = TTLCache(maxsize=5, default_ttl=10.0)
        cache.put("a", 1)
        cache.put("b", 2)
        cache.get("a")        # hit
        cache.get("b")        # hit
        cache.get("missing")  # miss
        s = cache.stats()
        assert s["hits"] == 2
        assert s["misses"] == 1
        assert s["size"] == 2

    # 11
    def test_hit_rate_calculation(self):
        """hit_rate is rounded percentage: hits / (hits + misses) * 100."""
        cache = TTLCache(maxsize=5, default_ttl=10.0)
        cache.put("a", 1)
        cache.get("a")      # hit
        cache.get("a")      # hit
        cache.get("a")      # hit
        cache.get("miss")   # miss
        s = cache.stats()
        # 3 hits, 1 miss => 75.0%
        assert s["hit_rate"] == 75.0

    # 12
    def test_get_moves_to_end_changes_eviction_order(self):
        """Accessing a key via get() promotes it; the un-accessed key becomes LRU."""
        cache = TTLCache(maxsize=2, default_ttl=10.0)
        cache.put("a", 1)
        cache.put("b", 2)
        cache.get("a")      # "a" promoted to end; "b" is now LRU
        cache.put("c", 3)   # evicts "b"
        assert cache.get("a") == 1
        assert cache.get("b") is None
        assert cache.get("c") == 3

    # 13
    def test_maxsize_boundary_exactly_fits(self):
        """Exactly maxsize entries fit without eviction."""
        cache = TTLCache(maxsize=3, default_ttl=10.0)
        cache.put("a", 1)
        cache.put("b", 2)
        cache.put("c", 3)
        assert cache.stats()["size"] == 3
        assert cache.get("a") == 1
        assert cache.get("b") == 2
        assert cache.get("c") == 3

    # 14
    def test_expired_key_counted_as_miss(self):
        """An expired-then-accessed key increments misses, not hits."""
        cache = TTLCache(maxsize=5, default_ttl=10.0)
        cache.put("x", 42, ttl=0.01)
        time.sleep(0.02)
        cache.get("x")  # miss (expired)
        s = cache.stats()
        assert s["misses"] == 1
        assert s["hits"] == 0

    # 15
    def test_singleton_configs(self):
        """Pre-configured singletons have the documented maxsize and TTL."""
        assert listing_cache._maxsize == 512
        assert listing_cache._default_ttl == 120.0

        assert content_cache._maxsize == 256
        assert content_cache._default_ttl == 300.0

        assert agent_cache._maxsize == 256
        assert agent_cache._default_ttl == 600.0


# ═══════════════════════════════════════════════════════════════════════════
# SlidingWindowRateLimiter — 15 tests
# ═══════════════════════════════════════════════════════════════════════════


class TestSlidingWindowRateLimiter:
    """Pure unit tests — each test creates its own SlidingWindowRateLimiter."""

    # 16
    def test_allows_within_limit(self, monkeypatch):
        """Requests within the anonymous limit are allowed."""
        monkeypatch.setattr("marketplace.core.rate_limiter.settings.rest_rate_limit_anonymous", 30)
        limiter = SlidingWindowRateLimiter()
        allowed, _ = limiter.check("ip-1", authenticated=False)
        assert allowed is True

    # 17
    def test_blocks_over_limit(self, monkeypatch):
        """Exceeding the limit causes the request to be blocked."""
        monkeypatch.setattr("marketplace.core.rate_limiter.settings.rest_rate_limit_anonymous", 3)
        limiter = SlidingWindowRateLimiter()
        for _ in range(3):
            limiter.check("ip-1", authenticated=False)
        allowed, _ = limiter.check("ip-1", authenticated=False)
        assert allowed is False

    # 18
    def test_anonymous_vs_authenticated_different_limits(self, monkeypatch):
        """Anonymous limit (30) is lower than authenticated limit (120)."""
        monkeypatch.setattr("marketplace.core.rate_limiter.settings.rest_rate_limit_anonymous", 5)
        monkeypatch.setattr("marketplace.core.rate_limiter.settings.rest_rate_limit_authenticated", 10)
        limiter = SlidingWindowRateLimiter()
        # Exhaust anonymous limit
        for _ in range(5):
            limiter.check("anon-key", authenticated=False)
        anon_allowed, _ = limiter.check("anon-key", authenticated=False)
        assert anon_allowed is False

        # Authenticated user at same count is still allowed
        for _ in range(5):
            limiter.check("auth-key", authenticated=True)
        auth_allowed, _ = limiter.check("auth-key", authenticated=True)
        assert auth_allowed is True

    # 19
    def test_window_resets_after_60s(self, monkeypatch):
        """After 60 seconds the window resets and requests are allowed again."""
        monkeypatch.setattr("marketplace.core.rate_limiter.settings.rest_rate_limit_anonymous", 2)
        limiter = SlidingWindowRateLimiter()
        limiter.check("ip-1")
        limiter.check("ip-1")
        allowed, _ = limiter.check("ip-1")
        assert allowed is False

        # Simulate 60s passing by rewinding the window_start
        limiter._buckets["ip-1"].window_start -= 61
        allowed, _ = limiter.check("ip-1")
        assert allowed is True

    # 20
    def test_headers_contain_x_ratelimit_limit(self, monkeypatch):
        """Response headers include X-RateLimit-Limit equal to the configured limit."""
        monkeypatch.setattr("marketplace.core.rate_limiter.settings.rest_rate_limit_anonymous", 30)
        limiter = SlidingWindowRateLimiter()
        _, headers = limiter.check("ip-1", authenticated=False)
        assert "X-RateLimit-Limit" in headers
        assert headers["X-RateLimit-Limit"] == "30"

    # 21
    def test_headers_remaining_decrements(self, monkeypatch):
        """X-RateLimit-Remaining decrements with each request."""
        monkeypatch.setattr("marketplace.core.rate_limiter.settings.rest_rate_limit_anonymous", 5)
        limiter = SlidingWindowRateLimiter()
        _, h1 = limiter.check("ip-1")
        _, h2 = limiter.check("ip-1")
        _, h3 = limiter.check("ip-1")
        assert int(h1["X-RateLimit-Remaining"]) == 4
        assert int(h2["X-RateLimit-Remaining"]) == 3
        assert int(h3["X-RateLimit-Remaining"]) == 2

    # 22
    def test_headers_contain_x_ratelimit_reset(self, monkeypatch):
        """Response headers include X-RateLimit-Reset (seconds until window resets)."""
        monkeypatch.setattr("marketplace.core.rate_limiter.settings.rest_rate_limit_anonymous", 30)
        limiter = SlidingWindowRateLimiter()
        _, headers = limiter.check("ip-1")
        assert "X-RateLimit-Reset" in headers
        reset = int(headers["X-RateLimit-Reset"])
        assert 0 <= reset <= 60

    # 23
    def test_separate_keys_independent_counters(self, monkeypatch):
        """Different keys (IPs / agent IDs) have independent rate counters."""
        monkeypatch.setattr("marketplace.core.rate_limiter.settings.rest_rate_limit_anonymous", 2)
        limiter = SlidingWindowRateLimiter()
        limiter.check("ip-a")
        limiter.check("ip-a")
        # ip-a is at limit
        allowed_a, _ = limiter.check("ip-a")
        assert allowed_a is False

        # ip-b is fresh
        allowed_b, _ = limiter.check("ip-b")
        assert allowed_b is True

    # 24
    def test_retry_after_header_when_blocked(self, monkeypatch):
        """Blocked responses include a Retry-After header."""
        monkeypatch.setattr("marketplace.core.rate_limiter.settings.rest_rate_limit_anonymous", 1)
        limiter = SlidingWindowRateLimiter()
        limiter.check("ip-1")
        allowed, headers = limiter.check("ip-1")
        assert allowed is False
        assert "Retry-After" in headers
        assert int(headers["Retry-After"]) >= 1

    # 25
    def test_remaining_never_negative(self, monkeypatch):
        """X-RateLimit-Remaining is clamped to 0, never goes negative."""
        monkeypatch.setattr("marketplace.core.rate_limiter.settings.rest_rate_limit_anonymous", 1)
        limiter = SlidingWindowRateLimiter()
        limiter.check("ip-1")  # count=1, remaining=0
        _, headers = limiter.check("ip-1")  # count=2, remaining=max(0, 1-2)=0
        assert int(headers["X-RateLimit-Remaining"]) == 0

    # 26
    def test_cleanup_stale_buckets(self, monkeypatch):
        """Buckets older than 600s are removed during cleanup."""
        monkeypatch.setattr("marketplace.core.rate_limiter.settings.rest_rate_limit_anonymous", 100)
        limiter = SlidingWindowRateLimiter()
        limiter.check("stale-ip")
        # Make the bucket stale (window started > 600s ago)
        limiter._buckets["stale-ip"].window_start -= 700
        # Force cleanup by making _last_cleanup old enough
        limiter._last_cleanup -= 301
        now = time.monotonic()
        limiter._maybe_cleanup(now)
        assert "stale-ip" not in limiter._buckets

    # 27
    def test_cleanup_not_triggered_too_early(self, monkeypatch):
        """Cleanup is skipped when less than 300s have elapsed since last cleanup."""
        monkeypatch.setattr("marketplace.core.rate_limiter.settings.rest_rate_limit_anonymous", 100)
        limiter = SlidingWindowRateLimiter()
        limiter.check("stale-ip")
        limiter._buckets["stale-ip"].window_start -= 700  # stale bucket
        # Do NOT move _last_cleanup back — it is recent
        now = time.monotonic()
        limiter._maybe_cleanup(now)
        # Bucket should still exist because cleanup was not triggered
        assert "stale-ip" in limiter._buckets

    # 28
    def test_blocked_returns_false_tuple(self, monkeypatch):
        """When blocked, check() returns (False, headers)."""
        monkeypatch.setattr("marketplace.core.rate_limiter.settings.rest_rate_limit_anonymous", 1)
        limiter = SlidingWindowRateLimiter()
        limiter.check("ip-1")
        result = limiter.check("ip-1")
        assert isinstance(result, tuple)
        assert result[0] is False
        assert isinstance(result[1], dict)

    # 29
    def test_allowed_returns_true_tuple(self, monkeypatch):
        """When allowed, check() returns (True, headers)."""
        monkeypatch.setattr("marketplace.core.rate_limiter.settings.rest_rate_limit_anonymous", 30)
        limiter = SlidingWindowRateLimiter()
        result = limiter.check("ip-1")
        assert isinstance(result, tuple)
        assert result[0] is True
        assert isinstance(result[1], dict)

    # 30
    def test_authenticated_limit_applied(self, monkeypatch):
        """Authenticated flag picks up the authenticated limit, not anonymous."""
        monkeypatch.setattr("marketplace.core.rate_limiter.settings.rest_rate_limit_authenticated", 50)
        limiter = SlidingWindowRateLimiter()
        _, headers = limiter.check("agent-1", authenticated=True)
        assert headers["X-RateLimit-Limit"] == "50"
