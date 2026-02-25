"""Tests for cache_service.TTLCache — 25 tests covering all public methods and edge cases.

Covers put/get roundtrips, TTL expiration, LRU eviction, invalidate, clear,
stats tracking, hit-rate computation, custom TTL, overwrite semantics, and
boundary conditions.
"""

from __future__ import annotations

import time

import pytest

from marketplace.services.cache_service import (
    TTLCache,
    agent_cache,
    content_cache,
    listing_cache,
)


# ---------------------------------------------------------------------------
# Basic put/get operations
# ---------------------------------------------------------------------------


class TestTTLCacheBasicOps:

    def test_put_and_get_returns_stored_value(self):
        cache = TTLCache(maxsize=10, default_ttl=60.0)
        cache.put("key1", {"data": 42})
        assert cache.get("key1") == {"data": 42}

    def test_get_nonexistent_key_returns_none(self):
        cache = TTLCache(maxsize=10, default_ttl=60.0)
        assert cache.get("does-not-exist") is None

    def test_put_overwrites_existing_value(self):
        cache = TTLCache(maxsize=10, default_ttl=60.0)
        cache.put("k", "old")
        cache.put("k", "new")
        assert cache.get("k") == "new"

    def test_stores_none_value_explicitly(self):
        """None as a stored value should be distinguishable from a miss."""
        cache = TTLCache(maxsize=10, default_ttl=60.0)
        cache.put("k", None)
        # get() returns None for both miss and stored-None, but the entry exists
        # We verify by checking the stats — a hit means the entry exists
        cache.get("k")
        assert cache.stats()["hits"] == 1

    def test_stores_various_types(self):
        cache = TTLCache(maxsize=10, default_ttl=60.0)
        cache.put("str", "hello")
        cache.put("int", 123)
        cache.put("list", [1, 2, 3])
        cache.put("bytes", b"\x00\x01")
        assert cache.get("str") == "hello"
        assert cache.get("int") == 123
        assert cache.get("list") == [1, 2, 3]
        assert cache.get("bytes") == b"\x00\x01"


# ---------------------------------------------------------------------------
# TTL expiration
# ---------------------------------------------------------------------------


class TestTTLCacheExpiration:

    def test_entry_expires_after_ttl(self):
        cache = TTLCache(maxsize=10, default_ttl=60.0)
        cache.put("k", "value", ttl=0.01)
        time.sleep(0.02)
        assert cache.get("k") is None

    def test_entry_survives_before_ttl(self):
        cache = TTLCache(maxsize=10, default_ttl=60.0)
        cache.put("k", "value", ttl=10.0)
        assert cache.get("k") == "value"

    def test_custom_ttl_overrides_default(self):
        cache = TTLCache(maxsize=10, default_ttl=0.01)
        cache.put("short", "gone", ttl=0.01)
        cache.put("long", "here", ttl=10.0)
        time.sleep(0.02)
        assert cache.get("short") is None
        assert cache.get("long") == "here"

    def test_expired_entry_is_removed_from_cache(self):
        cache = TTLCache(maxsize=10, default_ttl=60.0)
        cache.put("k", "value", ttl=0.01)
        time.sleep(0.02)
        cache.get("k")
        assert cache.stats()["size"] == 0

    def test_zero_ttl_expires_immediately(self):
        cache = TTLCache(maxsize=10, default_ttl=60.0)
        cache.put("k", "gone", ttl=0)
        # time.monotonic() precision means 0 TTL expires on next get
        time.sleep(0.001)
        assert cache.get("k") is None


# ---------------------------------------------------------------------------
# LRU eviction
# ---------------------------------------------------------------------------


class TestTTLCacheLRU:

    def test_evicts_lru_when_over_maxsize(self):
        cache = TTLCache(maxsize=2, default_ttl=60.0)
        cache.put("a", 1)
        cache.put("b", 2)
        cache.put("c", 3)  # evicts "a"
        assert cache.get("a") is None
        assert cache.get("b") == 2
        assert cache.get("c") == 3

    def test_get_promotes_entry_preventing_eviction(self):
        cache = TTLCache(maxsize=2, default_ttl=60.0)
        cache.put("a", 1)
        cache.put("b", 2)
        cache.get("a")  # promote "a" — "b" becomes LRU
        cache.put("c", 3)  # evicts "b"
        assert cache.get("a") == 1
        assert cache.get("b") is None
        assert cache.get("c") == 3

    def test_put_existing_key_moves_to_end(self):
        cache = TTLCache(maxsize=2, default_ttl=60.0)
        cache.put("a", 1)
        cache.put("b", 2)
        cache.put("a", 10)  # update and move to end — "b" is LRU
        cache.put("c", 3)   # evicts "b"
        assert cache.get("a") == 10
        assert cache.get("b") is None

    def test_maxsize_one_always_replaces(self):
        cache = TTLCache(maxsize=1, default_ttl=60.0)
        cache.put("a", 1)
        cache.put("b", 2)
        assert cache.get("a") is None
        assert cache.get("b") == 2

    def test_exact_maxsize_no_eviction(self):
        cache = TTLCache(maxsize=3, default_ttl=60.0)
        cache.put("a", 1)
        cache.put("b", 2)
        cache.put("c", 3)
        assert cache.stats()["size"] == 3
        assert cache.get("a") == 1
        assert cache.get("b") == 2
        assert cache.get("c") == 3


# ---------------------------------------------------------------------------
# invalidate and clear
# ---------------------------------------------------------------------------


class TestTTLCacheInvalidation:

    def test_invalidate_existing_returns_true(self):
        cache = TTLCache(maxsize=10, default_ttl=60.0)
        cache.put("k", "val")
        assert cache.invalidate("k") is True
        assert cache.get("k") is None

    def test_invalidate_missing_returns_false(self):
        cache = TTLCache(maxsize=10, default_ttl=60.0)
        assert cache.invalidate("nope") is False

    def test_clear_removes_all(self):
        cache = TTLCache(maxsize=10, default_ttl=60.0)
        for i in range(5):
            cache.put(f"k{i}", i)
        cache.clear()
        assert cache.stats()["size"] == 0
        for i in range(5):
            assert cache.get(f"k{i}") is None


# ---------------------------------------------------------------------------
# Stats and hit-rate
# ---------------------------------------------------------------------------


class TestTTLCacheStats:

    def test_initial_stats_are_zero(self):
        cache = TTLCache(maxsize=10, default_ttl=60.0)
        s = cache.stats()
        assert s["hits"] == 0
        assert s["misses"] == 0
        assert s["size"] == 0
        assert s["maxsize"] == 10
        assert s["hit_rate"] == 0.0

    def test_hits_and_misses_tracked(self):
        cache = TTLCache(maxsize=10, default_ttl=60.0)
        cache.put("a", 1)
        cache.get("a")       # hit
        cache.get("a")       # hit
        cache.get("missing") # miss
        s = cache.stats()
        assert s["hits"] == 2
        assert s["misses"] == 1

    def test_expired_access_counts_as_miss(self):
        cache = TTLCache(maxsize=10, default_ttl=60.0)
        cache.put("k", "val", ttl=0.01)
        time.sleep(0.02)
        cache.get("k")  # miss (expired)
        assert cache.stats()["misses"] == 1
        assert cache.stats()["hits"] == 0

    def test_hit_rate_percentage(self):
        cache = TTLCache(maxsize=10, default_ttl=60.0)
        cache.put("a", 1)
        for _ in range(3):
            cache.get("a")      # 3 hits
        cache.get("missing")    # 1 miss
        # 3 / 4 = 75.0%
        assert cache.stats()["hit_rate"] == 75.0


# ---------------------------------------------------------------------------
# Singletons
# ---------------------------------------------------------------------------


class TestSingletonConfigs:

    def test_listing_cache_config(self):
        assert listing_cache._maxsize == 512
        assert listing_cache._default_ttl == 120.0

    def test_content_cache_config(self):
        assert content_cache._maxsize == 256
        assert content_cache._default_ttl == 300.0

    def test_agent_cache_config(self):
        assert agent_cache._maxsize == 256
        assert agent_cache._default_ttl == 600.0
