"""In-memory LRU cache with per-entry TTL expiration.

Pure Python, no external dependencies. Uses OrderedDict for O(1) LRU
and time.monotonic() for clock-safe TTL.
"""

import time
from collections import OrderedDict
from typing import Any


class TTLCache:
    """LRU cache with per-entry TTL. Thread-safe for asyncio (single-threaded event loop)."""

    def __init__(self, maxsize: int = 1024, default_ttl: float = 300.0):
        self._maxsize = maxsize
        self._default_ttl = default_ttl
        self._cache: OrderedDict[str, tuple[Any, float]] = OrderedDict()
        self._hits = 0
        self._misses = 0

    def get(self, key: str) -> Any | None:
        """Get value if exists and not expired. Moves to end (most recent)."""
        entry = self._cache.get(key)
        if entry is None:
            self._misses += 1
            return None
        value, expires_at = entry
        if time.monotonic() > expires_at:
            del self._cache[key]
            self._misses += 1
            return None
        self._cache.move_to_end(key)
        self._hits += 1
        return value

    def put(self, key: str, value: Any, ttl: float | None = None) -> None:
        """Store value with TTL. Evicts LRU if at capacity."""
        ttl = ttl if ttl is not None else self._default_ttl
        expires_at = time.monotonic() + ttl
        if key in self._cache:
            self._cache.move_to_end(key)
        self._cache[key] = (value, expires_at)
        while len(self._cache) > self._maxsize:
            self._cache.popitem(last=False)

    def invalidate(self, key: str) -> bool:
        """Remove a specific key. Returns True if it existed."""
        if key in self._cache:
            del self._cache[key]
            return True
        return False

    def clear(self) -> None:
        """Clear all entries."""
        self._cache.clear()

    def stats(self) -> dict:
        """Return hit/miss/size statistics."""
        return {
            "hits": self._hits,
            "misses": self._misses,
            "size": len(self._cache),
            "maxsize": self._maxsize,
            "hit_rate": round(self._hits / max(self._hits + self._misses, 1) * 100, 1),
        }


# Pre-configured singleton caches
listing_cache = TTLCache(maxsize=512, default_ttl=120.0)    # 2 min TTL
content_cache = TTLCache(maxsize=256, default_ttl=300.0)    # 5 min TTL, stores bytes
agent_cache = TTLCache(maxsize=256, default_ttl=600.0)      # 10 min TTL
