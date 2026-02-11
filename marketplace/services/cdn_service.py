"""Three-tier CDN for content delivery.

Tier 1 (Hot):  In-memory LFU cache, 256MB budget, sub-0.1ms
Tier 2 (Warm): TTL cache from cache_service, ~0.5ms
Tier 3 (Cold): HashFS disk via asyncio.to_thread(), ~1-5ms

Auto-promotion: content accessed >10 times/minute → Tier 1.
Background decay: every 60s, halve access counters.
"""

import asyncio
import sys
import time
import threading
from typing import Any

from marketplace.services.cache_service import content_cache
from marketplace.services.storage_service import get_storage


class HotCache:
    """LFU in-memory cache with a byte-size budget."""

    def __init__(self, max_bytes: int = 256 * 1024 * 1024):
        self._max_bytes = max_bytes
        self._current_bytes = 0
        self._store: dict[str, bytes] = {}
        self._freq: dict[str, int] = {}
        self._access_count: dict[str, int] = {}  # per-minute access counter
        self._last_decay = time.monotonic()
        self._lock = threading.Lock()

        # Stats
        self.hits = 0
        self.misses = 0
        self.promotions = 0
        self.evictions = 0

    def get(self, key: str) -> bytes | None:
        with self._lock:
            data = self._store.get(key)
            if data is not None:
                self._freq[key] = self._freq.get(key, 0) + 1
                self._access_count[key] = self._access_count.get(key, 0) + 1
                self.hits += 1
                return data
            self.misses += 1
            return None

    def put(self, key: str, data: bytes) -> bool:
        """Store content if it fits. Returns True if stored."""
        size = len(data)
        if size > self._max_bytes:
            return False

        with self._lock:
            if key in self._store:
                return True  # already cached

            # Evict LFU entries until we have room
            while self._current_bytes + size > self._max_bytes and self._store:
                self._evict_lfu()

            self._store[key] = data
            self._freq[key] = 1
            self._access_count[key] = 1
            self._current_bytes += size
            self.promotions += 1
            return True

    def _evict_lfu(self):
        """Evict the least-frequently-used entry. Must hold lock."""
        if not self._freq:
            return
        min_key = min(self._freq, key=self._freq.get)
        data = self._store.pop(min_key, None)
        if data is not None:
            self._current_bytes -= len(data)
        self._freq.pop(min_key, None)
        self._access_count.pop(min_key, None)
        self.evictions += 1

    def should_promote(self, key: str) -> bool:
        """Check if content should be promoted to hot tier (>10 accesses/min)."""
        with self._lock:
            return self._access_count.get(key, 0) > 10

    def decay_counters(self):
        """Halve all per-minute access counters. Called by background task."""
        with self._lock:
            dead_keys = []
            for key in self._access_count:
                self._access_count[key] //= 2
                if self._access_count[key] == 0 and key not in self._store:
                    dead_keys.append(key)
            for key in dead_keys:
                self._access_count.pop(key, None)
            self._last_decay = time.monotonic()

    def record_access(self, key: str):
        """Record an access even if content isn't in hot cache (for promotion tracking)."""
        with self._lock:
            self._access_count[key] = self._access_count.get(key, 0) + 1

    def stats(self) -> dict:
        with self._lock:
            return {
                "tier": "hot",
                "entries": len(self._store),
                "bytes_used": self._current_bytes,
                "bytes_max": self._max_bytes,
                "utilization_pct": round(self._current_bytes / self._max_bytes * 100, 1),
                "hits": self.hits,
                "misses": self.misses,
                "promotions": self.promotions,
                "evictions": self.evictions,
                "hit_rate": round(self.hits / max(self.hits + self.misses, 1) * 100, 1),
            }


# Singleton
_hot_cache = HotCache()

# Global CDN stats
_cdn_stats = {
    "tier1_hits": 0,
    "tier2_hits": 0,
    "tier3_hits": 0,
    "total_misses": 0,
    "total_requests": 0,
}


async def get_content(content_hash: str) -> bytes | None:
    """Fetch content through the three-tier CDN.

    Returns bytes or None. Automatically promotes hot content to Tier 1.
    """
    _cdn_stats["total_requests"] += 1

    # Tier 1: Hot cache (in-memory LFU)
    data = _hot_cache.get(content_hash)
    if data is not None:
        _cdn_stats["tier1_hits"] += 1
        return data

    # Tier 2: Warm cache (TTL)
    data = content_cache.get(f"content:{content_hash}")
    if data is not None:
        _cdn_stats["tier2_hits"] += 1
        _hot_cache.record_access(content_hash)
        # Promote to Tier 1 if hot
        if _hot_cache.should_promote(content_hash):
            _hot_cache.put(content_hash, data)
        return data

    # Tier 3: Cold storage (HashFS on disk)
    storage = get_storage()
    data = await asyncio.to_thread(storage.get, content_hash)
    if data is not None:
        _cdn_stats["tier3_hits"] += 1
        # Always cache in Tier 2
        content_cache.put(f"content:{content_hash}", data)
        _hot_cache.record_access(content_hash)
        # Promote to Tier 1 if hot
        if _hot_cache.should_promote(content_hash):
            _hot_cache.put(content_hash, data)
        return data

    _cdn_stats["total_misses"] += 1
    return None


def get_cdn_stats() -> dict:
    """Return combined CDN statistics across all tiers."""
    return {
        "overview": {
            "total_requests": _cdn_stats["total_requests"],
            "tier1_hits": _cdn_stats["tier1_hits"],
            "tier2_hits": _cdn_stats["tier2_hits"],
            "tier3_hits": _cdn_stats["tier3_hits"],
            "total_misses": _cdn_stats["total_misses"],
        },
        "hot_cache": _hot_cache.stats(),
        "warm_cache": content_cache.stats(),
    }


async def cdn_decay_loop():
    """Background task: decay hot cache counters every 60s."""
    while True:
        await asyncio.sleep(60)
        _hot_cache.decay_counters()
