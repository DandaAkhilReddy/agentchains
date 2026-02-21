"""Redis-backed sliding window rate limiter for multi-instance deployments.

Falls back to the in-memory rate limiter if Redis is unavailable.
Enable by setting REDIS_URL in environment variables.

Usage:
    from marketplace.core.redis_rate_limiter import get_rate_limiter
    limiter = get_rate_limiter()
    allowed, headers = await limiter.check("agent:abc123", authenticated=True)
"""

import logging
import time

from marketplace.config import settings

logger = logging.getLogger(__name__)


class RedisRateLimiter:
    """Sliding window rate limiter backed by Redis sorted sets."""

    def __init__(self, redis_url: str):
        self._redis_url = redis_url
        self._redis = None

    async def _get_redis(self):
        if self._redis is None:
            try:
                from redis.asyncio import from_url

                # Azure Cache for Redis uses TLS on port 6380 (rediss:// scheme)
                connect_kwargs = {
                    "decode_responses": True,
                    "socket_connect_timeout": 2,
                }
                # Azure Redis requires SSL; detect from URL scheme
                if self._redis_url.startswith("rediss://"):
                    connect_kwargs["ssl_cert_reqs"] = "required"

                self._redis = from_url(self._redis_url, **connect_kwargs)
                await self._redis.ping()
                logger.info("Redis rate limiter connected: %s", self._redis_url)
            except Exception:
                logger.warning(
                    "Redis unavailable at %s — falling back to in-memory rate limiter",
                    self._redis_url,
                )
                self._redis = None
        return self._redis

    async def check(self, key: str, authenticated: bool = False) -> tuple[bool, dict]:
        """Check if request is within rate limits using Redis sorted sets."""
        limit = (
            settings.rest_rate_limit_authenticated
            if authenticated
            else settings.rest_rate_limit_anonymous
        )
        window_seconds = 60
        redis = await self._get_redis()

        if redis is None:
            # Fallback to in-memory
            from marketplace.core.rate_limiter import rate_limiter

            return rate_limiter.check(key, authenticated)

        try:
            now = time.time()
            window_start = now - window_seconds
            redis_key = f"ratelimit:{key}"

            pipe = redis.pipeline()
            # Remove expired entries
            pipe.zremrangebyscore(redis_key, 0, window_start)
            # Add current request
            pipe.zadd(redis_key, {f"{now}": now})
            # Count requests in window
            pipe.zcard(redis_key)
            # Set TTL on key
            pipe.expire(redis_key, window_seconds + 1)
            results = await pipe.execute()

            count = results[2]
            remaining = max(0, limit - count)
            reset_at = int(window_seconds - (now - window_start))

            headers = {
                "X-RateLimit-Limit": str(limit),
                "X-RateLimit-Remaining": str(remaining),
                "X-RateLimit-Reset": str(max(0, reset_at)),
            }

            if count > limit:
                headers["Retry-After"] = str(max(1, reset_at))
                return False, headers
            return True, headers

        except Exception:
            logger.warning("Redis rate limit check failed, falling back to in-memory")
            from marketplace.core.rate_limiter import rate_limiter

            return rate_limiter.check(key, authenticated)

    async def close(self):
        """Close Redis connection."""
        if self._redis:
            await self._redis.close()
            self._redis = None


_instance: RedisRateLimiter | None = None


def get_rate_limiter() -> RedisRateLimiter | None:
    """Get the Redis rate limiter singleton (None if REDIS_URL not configured)."""
    global _instance
    redis_url = getattr(settings, "redis_url", "")
    if not redis_url:
        return None
    if _instance is None:
        _instance = RedisRateLimiter(redis_url)
    return _instance
