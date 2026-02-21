"""Unit tests for marketplace/core/redis_rate_limiter.py.

Strategy:
- No real Redis instance is needed.  All tests mock redis.asyncio.from_url so
  that the connection attempt always raises an Exception, which drives the
  code into its in-memory fallback paths.
- The get_rate_limiter() factory is tested by patching settings.redis_url at
  the module level where the factory reads it.
- The singleton global (_instance) is reset between tests via the module-level
  patch of the module's own namespace to avoid cross-test contamination.
"""

import pytest
from unittest.mock import patch, AsyncMock, MagicMock

import marketplace.core.redis_rate_limiter as rrm_module
from marketplace.core.redis_rate_limiter import RedisRateLimiter, get_rate_limiter


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _reset_singleton():
    """Reset the module-level singleton so each test gets a clean slate."""
    rrm_module._instance = None


# ---------------------------------------------------------------------------
# TestGetRateLimiter — 3 tests
# ---------------------------------------------------------------------------


class TestGetRateLimiter:
    """Tests for the get_rate_limiter() singleton factory."""

    def setup_method(self):
        _reset_singleton()

    def teardown_method(self):
        _reset_singleton()

    # 1
    def test_returns_none_when_redis_url_is_empty(self):
        """Factory returns None when settings.redis_url is an empty string."""
        with patch("marketplace.core.redis_rate_limiter.settings") as mock_settings:
            mock_settings.redis_url = ""
            result = get_rate_limiter()
        assert result is None

    # 2
    def test_returns_instance_when_redis_url_is_set(self):
        """Factory returns a RedisRateLimiter when settings.redis_url is non-empty."""
        with patch("marketplace.core.redis_rate_limiter.settings") as mock_settings:
            mock_settings.redis_url = "redis://localhost:6379/0"
            result = get_rate_limiter()
        assert isinstance(result, RedisRateLimiter)

    # 3
    def test_singleton_returns_same_instance_on_repeated_calls(self):
        """Calling get_rate_limiter() twice with the same URL returns the exact same object."""
        with patch("marketplace.core.redis_rate_limiter.settings") as mock_settings:
            mock_settings.redis_url = "redis://localhost:6379/0"
            first = get_rate_limiter()
            second = get_rate_limiter()
        assert first is second


# ---------------------------------------------------------------------------
# TestRedisRateLimiterInit — 2 tests
# ---------------------------------------------------------------------------


class TestRedisRateLimiterInit:
    """Tests for RedisRateLimiter.__init__()."""

    # 4
    def test_stores_redis_url(self):
        """Constructor stores the supplied URL in _redis_url."""
        url = "redis://example.com:6380/1"
        limiter = RedisRateLimiter(url)
        assert limiter._redis_url == url

    # 5
    def test_redis_connection_starts_as_none(self):
        """Constructor initialises _redis to None (lazy connection)."""
        limiter = RedisRateLimiter("redis://localhost:6379")
        assert limiter._redis is None


# ---------------------------------------------------------------------------
# TestRedisRateLimiterFallback — 6 tests
# ---------------------------------------------------------------------------


class TestRedisRateLimiterFallback:
    """Tests for RedisRateLimiter.check() falling back to the in-memory limiter.

    In every test, redis.asyncio.from_url is patched to raise an Exception so
    that _get_redis() returns None and check() delegates to rate_limiter.check().
    """

    def setup_method(self):
        # Clear the in-memory rate limiter's buckets so previous tests don't
        # bleed over.
        from marketplace.core.rate_limiter import rate_limiter
        rate_limiter._buckets.clear()

    # 6
    @pytest.mark.asyncio
    async def test_check_falls_back_to_in_memory_when_redis_unavailable(self, monkeypatch):
        """When Redis raises on connect, check() returns a result from the in-memory limiter."""
        monkeypatch.setattr(
            "marketplace.core.rate_limiter.settings.rest_rate_limit_anonymous", 30
        )
        with patch("redis.asyncio.from_url", side_effect=Exception("Redis down")):
            limiter = RedisRateLimiter("redis://localhost:6379")
            allowed, headers = await limiter.check("test-key", authenticated=False)

        assert isinstance(allowed, bool)
        assert isinstance(headers, dict)

    # 7
    @pytest.mark.asyncio
    async def test_fallback_returns_valid_rate_limit_headers(self, monkeypatch):
        """Fallback response contains the three required X-RateLimit-* headers."""
        monkeypatch.setattr(
            "marketplace.core.rate_limiter.settings.rest_rate_limit_anonymous", 30
        )
        with patch("redis.asyncio.from_url", side_effect=Exception("Redis down")):
            limiter = RedisRateLimiter("redis://localhost:6379")
            _, headers = await limiter.check("test-key", authenticated=False)

        assert "X-RateLimit-Limit" in headers
        assert "X-RateLimit-Remaining" in headers
        assert "X-RateLimit-Reset" in headers

    # 8
    @pytest.mark.asyncio
    async def test_fallback_anonymous_limit_applied(self, monkeypatch):
        """Fallback uses the anonymous limit when authenticated=False."""
        monkeypatch.setattr(
            "marketplace.core.rate_limiter.settings.rest_rate_limit_anonymous", 10
        )
        monkeypatch.setattr(
            "marketplace.core.rate_limiter.settings.rest_rate_limit_authenticated", 50
        )
        with patch("redis.asyncio.from_url", side_effect=Exception("Redis down")):
            limiter = RedisRateLimiter("redis://localhost:6379")
            _, headers = await limiter.check("anon-key", authenticated=False)

        assert headers["X-RateLimit-Limit"] == "10"

    # 9
    @pytest.mark.asyncio
    async def test_fallback_authenticated_limit_applied(self, monkeypatch):
        """Fallback uses the authenticated limit when authenticated=True."""
        monkeypatch.setattr(
            "marketplace.core.rate_limiter.settings.rest_rate_limit_anonymous", 10
        )
        monkeypatch.setattr(
            "marketplace.core.rate_limiter.settings.rest_rate_limit_authenticated", 50
        )
        with patch("redis.asyncio.from_url", side_effect=Exception("Redis down")):
            limiter = RedisRateLimiter("redis://localhost:6379")
            _, headers = await limiter.check("auth-key", authenticated=True)

        assert headers["X-RateLimit-Limit"] == "50"

    # 10
    @pytest.mark.asyncio
    async def test_fallback_allows_request_within_limit(self, monkeypatch):
        """Within the configured limit the fallback path returns allowed=True."""
        monkeypatch.setattr(
            "marketplace.core.rate_limiter.settings.rest_rate_limit_anonymous", 30
        )
        with patch("redis.asyncio.from_url", side_effect=Exception("Redis down")):
            limiter = RedisRateLimiter("redis://localhost:6379")
            allowed, _ = await limiter.check("within-limit-key", authenticated=False)

        assert allowed is True

    # 11
    @pytest.mark.asyncio
    async def test_fallback_blocks_when_over_limit(self, monkeypatch):
        """When the in-memory bucket is exhausted, the fallback returns allowed=False."""
        monkeypatch.setattr(
            "marketplace.core.rate_limiter.settings.rest_rate_limit_anonymous", 2
        )
        with patch("redis.asyncio.from_url", side_effect=Exception("Redis down")):
            limiter = RedisRateLimiter("redis://localhost:6379")
            # Exhaust the limit using the shared in-memory limiter directly
            from marketplace.core.rate_limiter import rate_limiter
            rate_limiter.check("block-key", authenticated=False)  # count=1
            rate_limiter.check("block-key", authenticated=False)  # count=2 — at limit

            # The next call via RedisRateLimiter should be blocked (count=3 > 2)
            allowed, headers = await limiter.check("block-key", authenticated=False)

        assert allowed is False
        assert "Retry-After" in headers


# ---------------------------------------------------------------------------
# TestRedisRateLimiterClose — 2 tests
# ---------------------------------------------------------------------------


class TestRedisRateLimiterClose:
    """Tests for RedisRateLimiter.close()."""

    # 12
    @pytest.mark.asyncio
    async def test_close_with_no_connection_is_a_noop(self):
        """close() when _redis is None does not raise and leaves _redis as None."""
        limiter = RedisRateLimiter("redis://localhost:6379")
        assert limiter._redis is None  # pre-condition
        await limiter.close()          # must not raise
        assert limiter._redis is None

    # 13
    @pytest.mark.asyncio
    async def test_close_calls_redis_close_and_resets_to_none(self):
        """close() calls .close() on the live Redis client and sets _redis = None."""
        mock_redis = AsyncMock()
        mock_redis.close = AsyncMock()

        limiter = RedisRateLimiter("redis://localhost:6379")
        limiter._redis = mock_redis   # inject mock connection directly

        await limiter.close()

        mock_redis.close.assert_awaited_once()
        assert limiter._redis is None


# ---------------------------------------------------------------------------
# TestRedisRateLimiterGetRedis — additional coverage
# ---------------------------------------------------------------------------


class TestRedisRateLimiterGetRedis:
    """Tests for the _get_redis() connection / fallback logic."""

    # 14
    @pytest.mark.asyncio
    async def test_get_redis_returns_none_when_connection_fails(self):
        """_get_redis() returns None if the Redis connection or ping raises."""
        with patch("redis.asyncio.from_url", side_effect=Exception("connection refused")):
            limiter = RedisRateLimiter("redis://localhost:6379")
            result = await limiter._get_redis()

        assert result is None
        # Internal state must also be None after a failed attempt
        assert limiter._redis is None

    # 15
    @pytest.mark.asyncio
    async def test_get_redis_reuses_existing_connection(self):
        """_get_redis() skips re-connecting when _redis is already set."""
        mock_redis = AsyncMock()
        limiter = RedisRateLimiter("redis://localhost:6379")
        limiter._redis = mock_redis   # inject an already-live connection

        # Even if from_url would raise, _get_redis should return the cached object
        with patch("redis.asyncio.from_url", side_effect=Exception("should not be called")):
            result = await limiter._get_redis()

        assert result is mock_redis

    # 16 — extra: pipeline exception falls back to in-memory
    @pytest.mark.asyncio
    async def test_check_falls_back_when_redis_pipeline_raises(self, monkeypatch):
        """If the pipeline execute() raises, check() still returns a valid result via in-memory."""
        monkeypatch.setattr(
            "marketplace.core.rate_limiter.settings.rest_rate_limit_anonymous", 30
        )
        from marketplace.core.rate_limiter import rate_limiter
        rate_limiter._buckets.clear()

        # Build a mock Redis whose pipeline raises on execute()
        mock_pipe = AsyncMock()
        mock_pipe.zremrangebyscore = MagicMock(return_value=mock_pipe)
        mock_pipe.zadd = MagicMock(return_value=mock_pipe)
        mock_pipe.zcard = MagicMock(return_value=mock_pipe)
        mock_pipe.expire = MagicMock(return_value=mock_pipe)
        mock_pipe.execute = AsyncMock(side_effect=Exception("Redis pipeline error"))

        mock_redis = AsyncMock()
        mock_redis.ping = AsyncMock()
        mock_redis.pipeline = MagicMock(return_value=mock_pipe)

        limiter = RedisRateLimiter("redis://localhost:6379")
        limiter._redis = mock_redis   # bypass _get_redis connection path

        allowed, headers = await limiter.check("pipeline-fail-key", authenticated=False)

        assert isinstance(allowed, bool)
        assert "X-RateLimit-Limit" in headers
        assert "X-RateLimit-Remaining" in headers
        assert "X-RateLimit-Reset" in headers
