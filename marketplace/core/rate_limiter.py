"""Sliding window rate limiter — in-memory, per agent_id or IP."""

import time
from collections import defaultdict
from dataclasses import dataclass, field

from marketplace.config import settings


@dataclass
class _Window:
    count: int = 0
    window_start: float = field(default_factory=time.monotonic)


class SlidingWindowRateLimiter:
    def __init__(self):
        self._buckets: dict[str, _Window] = defaultdict(_Window)
        self._last_cleanup = time.monotonic()

    def check(self, key: str, authenticated: bool = False) -> tuple[bool, dict]:
        limit = (
            settings.rest_rate_limit_authenticated
            if authenticated
            else settings.rest_rate_limit_anonymous
        )
        now = time.monotonic()
        self._maybe_cleanup(now)
        bucket = self._buckets[key]
        if now - bucket.window_start >= 60:
            bucket.count = 0
            bucket.window_start = now
        bucket.count += 1
        remaining = max(0, limit - bucket.count)
        reset_at = int(bucket.window_start + 60 - now)
        headers = {
            "X-RateLimit-Limit": str(limit),
            "X-RateLimit-Remaining": str(remaining),
            "X-RateLimit-Reset": str(max(0, reset_at)),
        }
        if bucket.count > limit:
            headers["Retry-After"] = str(max(1, reset_at))
            return False, headers
        return True, headers

    def _maybe_cleanup(self, now: float):
        if now - self._last_cleanup < 300:
            return
        self._last_cleanup = now
        stale = [k for k, v in self._buckets.items() if now - v.window_start > 600]
        for k in stale:
            del self._buckets[k]


rate_limiter = SlidingWindowRateLimiter()
