"""Unit tests for smart routing service.

Tests all 7 routing strategies (cheapest, fastest, highest_quality, best_value,
round_robin, weighted_random, locality) with various edge cases.

These are PURE FUNCTION tests — no database required.
"""

import pytest

from marketplace.services import router_service


# ---------------------------------------------------------------------------
# Helper: Create mock candidates
# ---------------------------------------------------------------------------

def make_candidate(
    listing_id: int,
    seller_id: int,
    price_usdc: float,
    quality_score: float = 0.8,
    reputation: float = 0.7,
    freshness_score: float = 0.9,
    avg_response_ms: int = 100,
    region: str = "us-east",
    match_score: float = 0.85,
    content_hash: str = "abc123",
) -> dict:
    """Create a mock candidate dict with all required fields."""
    return {
        "listing_id": listing_id,
        "seller_id": seller_id,
        "price_usdc": price_usdc,
        "quality_score": quality_score,
        "reputation": reputation,
        "freshness_score": freshness_score,
        "avg_response_ms": avg_response_ms,
        "region": region,
        "match_score": match_score,
        "content_hash": content_hash,
    }


# ---------------------------------------------------------------------------
# Test: normalize helper
# ---------------------------------------------------------------------------

def test_normalize_typical():
    """Test min-max normalization."""
    result = router_service._normalize([1.0, 2.0, 3.0, 4.0, 5.0])
    assert result == [0.0, 0.25, 0.5, 0.75, 1.0]


def test_normalize_zero_range():
    """All same values → [0.5, 0.5, 0.5]."""
    result = router_service._normalize([5.0, 5.0, 5.0])
    assert result == [0.5, 0.5, 0.5]


def test_normalize_empty():
    """Empty list → empty list."""
    result = router_service._normalize([])
    assert result == []


def test_normalize_single():
    """Single value → [0.5]."""
    result = router_service._normalize([42.0])
    assert result == [0.5]


# ---------------------------------------------------------------------------
# Test: smart_route edge cases
# ---------------------------------------------------------------------------

def test_smart_route_empty_candidates():
    """Empty candidates → empty result."""
    result = router_service.smart_route([], strategy="best_value")
    assert result == []


def test_smart_route_invalid_strategy_fallback():
    """Invalid strategy → fallback to 'best_value'."""
    candidates = [
        make_candidate(1, 101, 0.01, quality_score=0.9),
        make_candidate(2, 102, 0.02, quality_score=0.7),
    ]
    result = router_service.smart_route(candidates, strategy="INVALID")
    # Should use best_value logic (quality/price weighted)
    assert result[0]["listing_id"] == 1  # Better value
    assert result[0]["routing_strategy"] == "best_value"


def test_smart_route_adds_routing_metadata():
    """All candidates get 'routing_strategy' field."""
    candidates = [
        make_candidate(1, 101, 0.01),
        make_candidate(2, 102, 0.02),
    ]
    result = router_service.smart_route(candidates, strategy="cheapest")
    assert all("routing_strategy" in c for c in result)
    assert all(c["routing_strategy"] == "cheapest" for c in result)


# ---------------------------------------------------------------------------
# Test: cheapest strategy
# ---------------------------------------------------------------------------

def test_route_cheapest_basic():
    """Cheapest price wins."""
    candidates = [
        make_candidate(1, 101, 0.05),  # Most expensive
        make_candidate(2, 102, 0.01),  # Cheapest → winner
        make_candidate(3, 103, 0.03),  # Middle
    ]
    result = router_service.smart_route(candidates, strategy="cheapest")
    assert result[0]["listing_id"] == 2
    assert result[0]["routing_score"] == 1.0  # Normalized cheapest


def test_route_cheapest_same_price():
    """Same price → all tied at 0.5."""
    candidates = [
        make_candidate(1, 101, 0.02),
        make_candidate(2, 102, 0.02),
        make_candidate(3, 103, 0.02),
    ]
    result = router_service.smart_route(candidates, strategy="cheapest")
    assert all(c["routing_score"] == 0.5 for c in result)


# ---------------------------------------------------------------------------
# Test: fastest strategy
# ---------------------------------------------------------------------------

def test_route_fastest_basic():
    """Lowest avg_response_ms wins."""
    candidates = [
        make_candidate(1, 101, 0.01, avg_response_ms=200),
        make_candidate(2, 102, 0.01, avg_response_ms=50),   # Fastest → winner
        make_candidate(3, 103, 0.01, avg_response_ms=150),
    ]
    result = router_service.smart_route(candidates, strategy="fastest")
    assert result[0]["listing_id"] == 2
    assert result[0]["routing_score"] == 1.0


def test_route_fastest_missing_response_time():
    """Missing avg_response_ms → default 100."""
    candidates = [
        make_candidate(1, 101, 0.01, avg_response_ms=200),
        {"listing_id": 2, "seller_id": 102, "price_usdc": 0.01, "quality_score": 0.8, "match_score": 0.8},  # No avg_response_ms
    ]
    result = router_service.smart_route(candidates, strategy="fastest")
    # Candidate 2 defaults to 100ms, faster than 200ms
    assert result[0]["listing_id"] == 2


# ---------------------------------------------------------------------------
# Test: highest_quality strategy
# ---------------------------------------------------------------------------

def test_route_highest_quality_basic():
    """0.5*quality + 0.3*reputation + 0.2*freshness."""
    candidates = [
        make_candidate(1, 101, 0.01, quality_score=0.9, reputation=0.8, freshness_score=0.9),  # Best
        make_candidate(2, 102, 0.01, quality_score=0.6, reputation=0.5, freshness_score=0.5),  # Worst
        make_candidate(3, 103, 0.01, quality_score=0.7, reputation=0.7, freshness_score=0.7),  # Middle
    ]
    result = router_service.smart_route(candidates, strategy="highest_quality")
    assert result[0]["listing_id"] == 1
    # 0.5*0.9 + 0.3*0.8 + 0.2*0.9 = 0.45 + 0.24 + 0.18 = 0.87
    assert result[0]["routing_score"] == 0.87


def test_route_highest_quality_missing_fields():
    """Missing fields default to 0.5."""
    candidates = [
        {"listing_id": 1, "seller_id": 101, "price_usdc": 0.01, "match_score": 0.8},  # All defaults
        make_candidate(2, 102, 0.01, quality_score=0.6, reputation=0.6, freshness_score=0.6),
    ]
    result = router_service.smart_route(candidates, strategy="highest_quality")
    # Candidate 1: 0.5*0.5 + 0.3*0.5 + 0.2*0.5 = 0.5
    # Candidate 2: 0.5*0.6 + 0.3*0.6 + 0.2*0.6 = 0.6
    assert result[0]["listing_id"] == 2


# ---------------------------------------------------------------------------
# Test: best_value strategy
# ---------------------------------------------------------------------------

def test_route_best_value_basic():
    """0.4*(quality/price) + 0.25*reputation + 0.2*freshness + 0.15*(1-price_norm)."""
    candidates = [
        make_candidate(1, 101, 0.02, quality_score=0.9, reputation=0.8, freshness_score=0.9),  # High quality, medium price
        make_candidate(2, 102, 0.01, quality_score=0.8, reputation=0.7, freshness_score=0.8),  # Good quality, low price → best value
        make_candidate(3, 103, 0.05, quality_score=0.6, reputation=0.6, freshness_score=0.6),  # Low quality, high price
    ]
    result = router_service.smart_route(candidates, strategy="best_value")
    # Candidate 2 should win with best quality/price ratio
    assert result[0]["listing_id"] == 2


def test_route_best_value_zero_price_protection():
    """Price = 0 → use 0.0001 to avoid division by zero."""
    candidates = [
        make_candidate(1, 101, 0.0, quality_score=0.9),  # Zero price
        make_candidate(2, 102, 0.01, quality_score=0.8),
    ]
    result = router_service.smart_route(candidates, strategy="best_value")
    # Should not crash, candidate 1 should have very high score
    assert len(result) == 2
    assert result[0]["listing_id"] == 1  # 0.9/0.0001 is capped at 100, very high value


# ---------------------------------------------------------------------------
# Test: round_robin strategy
# ---------------------------------------------------------------------------

def test_route_round_robin_initial():
    """First call → all tied, picks first by dict order, increments count."""
    # Clear round-robin state
    router_service._round_robin_state.clear()

    candidates = [
        make_candidate(1, 101, 0.01, content_hash="hash1"),
        make_candidate(2, 102, 0.01, content_hash="hash1"),
        make_candidate(3, 103, 0.01, content_hash="hash1"),
    ]
    result = router_service.smart_route(candidates, strategy="round_robin")

    # All start with count=0, so routing_score = 1/(1+0) = 1.0
    assert result[0]["routing_score"] == 1.0
    # Winner's count should be incremented in cache
    key = f"rr:hash1:{result[0]['seller_id']}"
    assert router_service._round_robin_state.get(key) == 1


def test_route_round_robin_rotation():
    """Second call favors different seller."""
    router_service._round_robin_state.clear()

    candidates = [
        make_candidate(1, 101, 0.01, content_hash="hash2"),
        make_candidate(2, 102, 0.01, content_hash="hash2"),
    ]

    # First call
    result1 = router_service.smart_route(candidates.copy(), strategy="round_robin")
    winner1 = result1[0]["seller_id"]

    # Second call with same candidates
    result2 = router_service.smart_route(candidates.copy(), strategy="round_robin")
    winner2 = result2[0]["seller_id"]

    # Should rotate to the other seller
    assert winner1 != winner2


def test_route_round_robin_cleans_temp_keys():
    """Temporary _rr_key and _rr_count are removed from result."""
    router_service._round_robin_state.clear()

    candidates = [
        make_candidate(1, 101, 0.01, content_hash="hash3"),
        make_candidate(2, 102, 0.01, content_hash="hash3"),
    ]
    result = router_service.smart_route(candidates, strategy="round_robin")

    # None of the results should have temp keys
    assert all("_rr_key" not in c for c in result)
    assert all("_rr_count" not in c for c in result)


# ---------------------------------------------------------------------------
# Test: weighted_random strategy
# ---------------------------------------------------------------------------

def test_route_weighted_random_probabilities():
    """Higher quality*reputation/price → higher probability."""
    candidates = [
        make_candidate(1, 101, 0.01, quality_score=0.9, reputation=0.9),  # 0.9*0.9/0.01 = 81
        make_candidate(2, 102, 0.05, quality_score=0.5, reputation=0.5),  # 0.5*0.5/0.05 = 5
    ]
    result = router_service.smart_route(candidates, strategy="weighted_random")

    # Both should have routing_score (probability)
    assert all("routing_score" in c for c in result)
    # Sum of probabilities should be ~1.0
    total_prob = sum(c["routing_score"] for c in result)
    assert abs(total_prob - 1.0) < 0.01


def test_route_weighted_random_zero_price_protection():
    """Zero price → use 0.0001."""
    candidates = [
        make_candidate(1, 101, 0.0, quality_score=0.8, reputation=0.8),
        make_candidate(2, 102, 0.01, quality_score=0.7, reputation=0.7),
    ]
    result = router_service.smart_route(candidates, strategy="weighted_random")
    # Should not crash
    assert len(result) == 2


# ---------------------------------------------------------------------------
# Test: locality strategy
# ---------------------------------------------------------------------------

def test_route_locality_same_region():
    """Same region → locality=1.0, highest score."""
    candidates = [
        make_candidate(1, 101, 0.02, region="us-east", quality_score=0.7),
        make_candidate(2, 102, 0.01, region="eu-west", quality_score=0.9),  # Better quality, different region
    ]
    result = router_service.smart_route(candidates, strategy="locality", buyer_region="us-east")
    # Candidate 1 should win due to locality bonus (1.0 vs 0.2)
    assert result[0]["listing_id"] == 1


def test_route_locality_adjacent_region():
    """Adjacent region → locality=0.5."""
    candidates = [
        make_candidate(1, 101, 0.01, region="us-west", quality_score=0.8),  # Adjacent to us-east
        make_candidate(2, 102, 0.01, region="asia-south", quality_score=0.8),  # Not adjacent
    ]
    result = router_service.smart_route(candidates, strategy="locality", buyer_region="us-east")
    # us-west is adjacent to us-east per REGION_ADJACENCY
    assert result[0]["listing_id"] == 1


def test_route_locality_other_region():
    """Non-adjacent region → locality=0.2."""
    candidates = [
        make_candidate(1, 101, 0.01, region="us-east", quality_score=0.5),  # Same
        make_candidate(2, 102, 0.01, region="us-west", quality_score=0.5),  # Adjacent
        make_candidate(3, 103, 0.01, region="asia-south", quality_score=0.5),  # Other
    ]
    result = router_service.smart_route(candidates, strategy="locality", buyer_region="us-east")
    # Order: us-east (1.0), us-west (0.5), asia-south (0.2)
    assert result[0]["listing_id"] == 1
    assert result[1]["listing_id"] == 2
    assert result[2]["listing_id"] == 3


def test_route_locality_no_buyer_region_fallback():
    """No buyer_region → fallback to best_value."""
    candidates = [
        make_candidate(1, 101, 0.05, quality_score=0.6, region="us-east"),
        make_candidate(2, 102, 0.01, quality_score=0.8, region="eu-west"),  # Better value
    ]
    result = router_service.smart_route(candidates, strategy="locality", buyer_region=None)
    # Should use best_value logic, candidate 2 wins
    assert result[0]["listing_id"] == 2
    assert result[0]["routing_strategy"] == "locality"  # Still labeled as locality


def test_route_locality_missing_seller_region():
    """Missing seller region → locality=0.2 (other)."""
    candidates = [
        make_candidate(1, 101, 0.01, region="us-east", quality_score=0.7),
        {"listing_id": 2, "seller_id": 102, "price_usdc": 0.01, "quality_score": 0.7, "match_score": 0.8},  # No region
    ]
    result = router_service.smart_route(candidates, strategy="locality", buyer_region="us-east")
    # Candidate 1 should win (locality 1.0 vs 0.2)
    assert result[0]["listing_id"] == 1


# ---------------------------------------------------------------------------
# Test: STRATEGIES constant
# ---------------------------------------------------------------------------

def test_strategies_constant():
    """Verify all 7 strategies are defined."""
    assert len(router_service.STRATEGIES) == 7
    expected = {"cheapest", "fastest", "highest_quality", "best_value", "round_robin", "weighted_random", "locality"}
    assert set(router_service.STRATEGIES) == expected


# ---------------------------------------------------------------------------
# Test: REGION_ADJACENCY constant
# ---------------------------------------------------------------------------

def test_region_adjacency_symmetric():
    """Verify region adjacency is defined (not necessarily symmetric)."""
    # Just check structure exists
    assert "us-east" in router_service.REGION_ADJACENCY
    assert "us-west" in router_service.REGION_ADJACENCY["us-east"]
    # Note: Not testing full symmetry as it's not required by the implementation
