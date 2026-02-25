"""Addendum tests for redis_rate_limiter.py: Redis success path with mocked pipeline."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from marketplace.core.redis_rate_limiter import RedisRateLimiter


def _make_limiter_with_pipe(count: int):
    """Create a limiter with a mocked Redis that returns count from pipeline."""
    limiter = RedisRateLimiter("redis://localhost:6379")
    mock_pipe = MagicMock()
    mock_pipe.zremrangebyscore.return_value = mock_pipe
    mock_pipe.zadd.return_value = mock_pipe
    mock_pipe.zcard.return_value = mock_pipe
    mock_pipe.expire.return_value = mock_pipe
    mock_pipe.execute = AsyncMock(return_value=[0, 1, count, True])
    mock_redis = MagicMock()
    mock_redis.pipeline.return_value = mock_pipe
    mock_redis.ping = AsyncMock()
    limiter._redis = mock_redis
    return limiter


class TestRedisSuccess:
    async def test_allowed(self):
        limiter = _make_limiter_with_pipe(5)
        allowed, headers = await limiter.check("test-key")
        assert allowed is True
        assert "X-RateLimit-Limit" in headers
        assert "X-RateLimit-Remaining" in headers
        assert int(headers["X-RateLimit-Remaining"]) > 0

    async def test_blocked(self):
        limiter = _make_limiter_with_pipe(99999)
        allowed, headers = await limiter.check("test-key")
        assert allowed is False
        assert "Retry-After" in headers

    async def test_authenticated_higher_limit(self):
        limiter1 = _make_limiter_with_pipe(50)
        _, h_anon = await limiter1.check("k", authenticated=False)
        limiter2 = _make_limiter_with_pipe(50)
        _, h_auth = await limiter2.check("k", authenticated=True)
        anon_limit = int(h_anon["X-RateLimit-Limit"])
        auth_limit = int(h_auth["X-RateLimit-Limit"])
        assert auth_limit >= anon_limit

    async def test_pipeline_exception_fallback(self):
        limiter = RedisRateLimiter("redis://localhost:6379")
        mock_pipe = MagicMock()
        mock_pipe.zremrangebyscore.return_value = mock_pipe
        mock_pipe.zadd.return_value = mock_pipe
        mock_pipe.zcard.return_value = mock_pipe
        mock_pipe.expire.return_value = mock_pipe
        mock_pipe.execute = AsyncMock(side_effect=Exception("connection lost"))
        mock_redis = MagicMock()
        mock_redis.pipeline.return_value = mock_pipe
        mock_redis.ping = AsyncMock()
        limiter._redis = mock_redis
        allowed, headers = await limiter.check("k")
        assert isinstance(allowed, bool)


class TestTLS:
    async def test_rediss_url(self):
        limiter = RedisRateLimiter("rediss://myhost:6380")
        assert limiter._redis_url.startswith("rediss://")

