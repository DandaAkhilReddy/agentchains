"""UT-7: CDN service tests -- HotCache + 3-tier CDN (30 tests)."""

import pytest

from marketplace.services.cdn_service import HotCache, get_content, get_cdn_stats, _hot_cache, _cdn_stats
from marketplace.services.cache_service import content_cache
from marketplace.services.storage_service import get_storage


# ═══════════════════════════════════════════════════════════════════
# HotCache Unit Tests (20 tests)
# ═══════════════════════════════════════════════════════════════════


class TestHotCache:
    """Tests for the HotCache LFU in-memory cache."""

    def test_hot_cache_put_and_get(self):
        cache = HotCache(max_bytes=1024)
        assert cache.put("k1", b"hello") is True
        assert cache.get("k1") == b"hello"

    def test_hot_cache_get_miss(self):
        cache = HotCache(max_bytes=1024)
        assert cache.get("nonexistent") is None

    def test_hot_cache_put_updates_bytes(self):
        cache = HotCache(max_bytes=1024)
        cache.put("k1", b"ABCDE")
        assert cache._current_bytes == 5
        cache.put("k2", b"XY")
        assert cache._current_bytes == 7

    def test_hot_cache_put_oversized_single(self):
        cache = HotCache(max_bytes=10)
        assert cache.put("big", b"X" * 20) is False
        assert cache._current_bytes == 0

    def test_hot_cache_eviction_lfu(self):
        cache = HotCache(max_bytes=30)
        cache.put("a", b"1234567890")  # 10 bytes, freq=1
        cache.put("b", b"1234567890")  # 10 bytes, freq=1
        cache.get("b")
        cache.get("b")
        # Evicts "a" (freq=1), keeps "b" (freq=3)
        cache.put("c", b"12345678901234567890")  # 20 bytes
        assert cache.get("a") is None
        assert cache.get("b") is not None

    def test_hot_cache_eviction_frees_bytes(self):
        cache = HotCache(max_bytes=20)
        cache.put("a", b"1234567890")
        cache.put("b", b"1234567890")
        cache.put("c", b"12345678901")  # triggers eviction
        assert cache._current_bytes <= 20

    def test_hot_cache_frequency_tracking(self):
        cache = HotCache(max_bytes=1024)
        cache.put("k1", b"data")
        assert cache._freq["k1"] == 1
        cache.get("k1")
        assert cache._freq["k1"] == 2
        cache.get("k1")
        assert cache._freq["k1"] == 3

    def test_hot_cache_hits_counter(self):
        cache = HotCache(max_bytes=1024)
        cache.put("k1", b"data")
        assert cache.hits == 0
        cache.get("k1")
        assert cache.hits == 1

    def test_hot_cache_misses_counter(self):
        cache = HotCache(max_bytes=1024)
        assert cache.misses == 0
        cache.get("missing")
        assert cache.misses == 1

    def test_hot_cache_promotions_counter(self):
        cache = HotCache(max_bytes=1024)
        assert cache.promotions == 0
        cache.put("k1", b"data")
        assert cache.promotions == 1
        cache.put("k2", b"data2")
        assert cache.promotions == 2

    def test_hot_cache_evictions_counter(self):
        cache = HotCache(max_bytes=15)
        cache.put("a", b"1234567890")  # 10 bytes
        assert cache.evictions == 0
        cache.put("b", b"1234567890")  # triggers eviction
        assert cache.evictions >= 1

    def test_hot_cache_should_promote_below_threshold(self):
        cache = HotCache(max_bytes=1024)
        for _ in range(5):
            cache.record_access("k1")
        assert cache.should_promote("k1") is False

    def test_hot_cache_should_promote_above_threshold(self):
        cache = HotCache(max_bytes=1024)
        for _ in range(11):
            cache.record_access("k1")
        assert cache.should_promote("k1") is True

    def test_hot_cache_should_promote_at_threshold(self):
        cache = HotCache(max_bytes=1024)
        for _ in range(10):
            cache.record_access("k1")
        assert cache.should_promote("k1") is False

    def test_hot_cache_decay_counters(self):
        cache = HotCache(max_bytes=1024)
        cache.put("k1", b"data")
        for _ in range(20):
            cache.record_access("k1")
        before = cache._access_count["k1"]
        cache.decay_counters()
        assert cache._access_count["k1"] == before // 2

    def test_hot_cache_decay_cleans_dead_keys(self):
        cache = HotCache(max_bytes=1024)
        cache.record_access("uncached_key")
        cache._access_count["uncached_key"] = 1
        cache.decay_counters()
        assert "uncached_key" not in cache._access_count

    def test_hot_cache_record_access(self):
        cache = HotCache(max_bytes=1024)
        cache.record_access("not_in_cache")
        assert cache._access_count["not_in_cache"] == 1

    def test_hot_cache_stats_format(self):
        cache = HotCache(max_bytes=1024)
        stats = cache.stats()
        expected_keys = {
            "tier", "entries", "bytes_used", "bytes_max",
            "utilization_pct", "hits", "misses", "promotions",
            "evictions", "hit_rate",
        }
        assert expected_keys.issubset(set(stats.keys()))

    def test_hot_cache_stats_hit_rate(self):
        cache = HotCache(max_bytes=1024)
        cache.put("k1", b"data")
        cache.get("k1")  # hit
        cache.get("k1")  # hit
        cache.get("missing")  # miss
        stats = cache.stats()
        assert stats["hit_rate"] == pytest.approx(66.7, abs=0.1)

    def test_hot_cache_small_budget(self):
        cache = HotCache(max_bytes=100)
        for i in range(20):
            cache.put(f"k{i}", b"X" * 10)
        assert cache._current_bytes <= 100
        assert len(cache._store) <= 10


# ═══════════════════════════════════════════════════════════════════
# CDN Integration (10 tests)
# ═══════════════════════════════════════════════════════════════════


class TestCDNIntegration:
    """Tests for 3-tier CDN get_content() function."""

    async def test_cdn_get_content_tier1_hit(self):
        _hot_cache._store.clear()
        _hot_cache._freq.clear()
        _hot_cache._access_count.clear()
        _hot_cache._current_bytes = 0
        _hot_cache.hits = 0
        _hot_cache.misses = 0
        _hot_cache.put("hash-t1", b"tier1-content")
        initial = _cdn_stats["tier1_hits"]
        data = await get_content("hash-t1")
        assert data == b"tier1-content"
        assert _cdn_stats["tier1_hits"] == initial + 1

    async def test_cdn_get_content_tier2_hit(self):
        _hot_cache._store.clear()
        _hot_cache._freq.clear()
        _hot_cache._access_count.clear()
        _hot_cache._current_bytes = 0
        content_cache.put("content:hash-t2", b"tier2-content")
        initial = _cdn_stats["tier2_hits"]
        data = await get_content("hash-t2")
        assert data == b"tier2-content"
        assert _cdn_stats["tier2_hits"] == initial + 1

    async def test_cdn_get_content_tier3_hit(self):
        _hot_cache._store.clear()
        _hot_cache._freq.clear()
        _hot_cache._access_count.clear()
        _hot_cache._current_bytes = 0
        content_cache.clear()
        storage = get_storage()
        content = b"disk-only-content"
        content_hash = storage.put(content)
        initial = _cdn_stats["tier3_hits"]
        data = await get_content(content_hash)
        assert data == content
        assert _cdn_stats["tier3_hits"] == initial + 1

    async def test_cdn_get_content_total_miss(self):
        _hot_cache._store.clear()
        _hot_cache._freq.clear()
        _hot_cache._access_count.clear()
        _hot_cache._current_bytes = 0
        content_cache.clear()
        initial = _cdn_stats["total_misses"]
        data = await get_content("sha256:nonexistent_hash_abc")
        assert data is None
        assert _cdn_stats["total_misses"] == initial + 1

    async def test_cdn_get_content_promotion(self):
        _hot_cache._store.clear()
        _hot_cache._freq.clear()
        _hot_cache._access_count.clear()
        _hot_cache._current_bytes = 0
        content_cache.put("content:hash-promo", b"promo-content")
        for _ in range(12):
            await get_content("hash-promo")
        assert _hot_cache.get("hash-promo") == b"promo-content"

    async def test_cdn_stats_format(self):
        stats = get_cdn_stats()
        assert "overview" in stats
        assert "hot_cache" in stats
        assert "warm_cache" in stats
        assert "total_requests" in stats["overview"]

    async def test_cdn_stats_request_counting(self):
        before = _cdn_stats["total_requests"]
        await get_content("sha256:counting_test")
        assert _cdn_stats["total_requests"] == before + 1

    async def test_cdn_stats_tier_counting(self):
        _hot_cache._store.clear()
        _hot_cache._freq.clear()
        _hot_cache._access_count.clear()
        _hot_cache._current_bytes = 0
        _hot_cache.put("tier-count-test", b"data")
        before = _cdn_stats["tier1_hits"]
        await get_content("tier-count-test")
        assert _cdn_stats["tier1_hits"] == before + 1

    def test_cdn_decay_counters_called(self):
        _hot_cache._access_count.clear()
        _hot_cache.record_access("dk1")
        _hot_cache.record_access("dk1")
        _hot_cache.record_access("dk1")
        _hot_cache.record_access("dk1")
        assert _hot_cache._access_count["dk1"] == 4
        _hot_cache.decay_counters()
        assert _hot_cache._access_count["dk1"] == 2

    async def test_cdn_get_content_empty_hash(self):
        """Empty string hash — tier1 miss, tier2 miss, tier3 miss → None."""
        _hot_cache._store.clear()
        _hot_cache._freq.clear()
        _hot_cache._access_count.clear()
        _hot_cache._current_bytes = 0
        content_cache.clear()
        initial = _cdn_stats["total_misses"]
        data = await get_content("sha256:empty_test_nonexistent")
        assert data is None
        assert _cdn_stats["total_misses"] == initial + 1
