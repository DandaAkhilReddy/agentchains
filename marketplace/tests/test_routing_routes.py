"""Test suite for Routing API routes.

Tests cover:
- POST /api/v1/route/select — route selection with all 7 strategies
- GET /api/v1/route/strategies — list available strategies

No auth required for these endpoints.
"""

import pytest

from marketplace.services.router_service import _round_robin_state


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _candidate(
    listing_id: int,
    price_usdc: float,
    quality_score: float = 0.8,
    seller_id: int = None,
    match_score: float = 0.85,
    avg_response_ms: int = 100,
    region: str = "us-east",
    reputation: float = 0.7,
    freshness_score: float = 0.9,
    content_hash: str = "hash-abc",
) -> dict:
    """Build a candidate dict with all typical fields."""
    return {
        "listing_id": listing_id,
        "seller_id": seller_id or (1000 + listing_id),
        "price_usdc": price_usdc,
        "quality_score": quality_score,
        "match_score": match_score,
        "avg_response_ms": avg_response_ms,
        "region": region,
        "reputation": reputation,
        "freshness_score": freshness_score,
        "content_hash": content_hash,
    }


# ---------------------------------------------------------------------------
# 1. test_route_select_cheapest
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_route_select_cheapest(client):
    """Cheapest candidate is ranked first when using 'cheapest' strategy."""
    candidates = [
        _candidate(1, price_usdc=0.05),
        _candidate(2, price_usdc=0.01),  # cheapest
        _candidate(3, price_usdc=0.03),
    ]
    resp = await client.post(
        "/api/v1/route/select",
        json={"candidates": candidates, "strategy": "cheapest"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["ranked"][0]["listing_id"] == 2


# ---------------------------------------------------------------------------
# 2. test_route_select_fastest
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_route_select_fastest(client):
    """Fastest (lowest avg_response_ms) candidate ranked first."""
    candidates = [
        _candidate(1, price_usdc=0.01, avg_response_ms=300),
        _candidate(2, price_usdc=0.01, avg_response_ms=50),   # fastest
        _candidate(3, price_usdc=0.01, avg_response_ms=200),
    ]
    resp = await client.post(
        "/api/v1/route/select",
        json={"candidates": candidates, "strategy": "fastest"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["ranked"][0]["listing_id"] == 2


# ---------------------------------------------------------------------------
# 3. test_route_select_highest_quality
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_route_select_highest_quality(client):
    """Highest quality + reputation + freshness scoring wins."""
    candidates = [
        _candidate(1, price_usdc=0.01, quality_score=0.9, reputation=0.8, freshness_score=0.9),
        _candidate(2, price_usdc=0.01, quality_score=0.5, reputation=0.4, freshness_score=0.4),
        _candidate(3, price_usdc=0.01, quality_score=0.7, reputation=0.6, freshness_score=0.6),
    ]
    resp = await client.post(
        "/api/v1/route/select",
        json={"candidates": candidates, "strategy": "highest_quality"},
    )
    assert resp.status_code == 200
    ranked = resp.json()["ranked"]
    assert ranked[0]["listing_id"] == 1
    # 0.5*0.9 + 0.3*0.8 + 0.2*0.9 = 0.87
    assert ranked[0]["routing_score"] == 0.87


# ---------------------------------------------------------------------------
# 4. test_route_select_best_value
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_route_select_best_value(client):
    """Best value = quality/price ratio weighted scoring."""
    candidates = [
        _candidate(1, price_usdc=0.05, quality_score=0.6, reputation=0.5, freshness_score=0.5),
        _candidate(2, price_usdc=0.01, quality_score=0.9, reputation=0.8, freshness_score=0.9),  # best value
    ]
    resp = await client.post(
        "/api/v1/route/select",
        json={"candidates": candidates, "strategy": "best_value"},
    )
    assert resp.status_code == 200
    ranked = resp.json()["ranked"]
    # Candidate 2 has much better quality/price ratio
    assert ranked[0]["listing_id"] == 2


# ---------------------------------------------------------------------------
# 5. test_route_select_round_robin
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_route_select_round_robin(client):
    """Round robin: fair rotation among sellers."""
    _round_robin_state.clear()

    candidates = [
        _candidate(1, price_usdc=0.01, seller_id=201, content_hash="rr-test-1"),
        _candidate(2, price_usdc=0.01, seller_id=202, content_hash="rr-test-1"),
    ]

    # First call — both start at count=0, so first in list wins
    resp1 = await client.post(
        "/api/v1/route/select",
        json={"candidates": candidates, "strategy": "round_robin"},
    )
    assert resp1.status_code == 200
    winner1 = resp1.json()["ranked"][0]["seller_id"]

    # Second call — previous winner incremented, other seller should win
    resp2 = await client.post(
        "/api/v1/route/select",
        json={"candidates": candidates, "strategy": "round_robin"},
    )
    assert resp2.status_code == 200
    winner2 = resp2.json()["ranked"][0]["seller_id"]

    assert winner1 != winner2


# ---------------------------------------------------------------------------
# 6. test_route_select_weighted_random
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_route_select_weighted_random(client):
    """Weighted random: all candidates present in result."""
    candidates = [
        _candidate(1, price_usdc=0.01, quality_score=0.9, reputation=0.9),
        _candidate(2, price_usdc=0.02, quality_score=0.7, reputation=0.7),
        _candidate(3, price_usdc=0.03, quality_score=0.5, reputation=0.5),
    ]
    resp = await client.post(
        "/api/v1/route/select",
        json={"candidates": candidates, "strategy": "weighted_random"},
    )
    assert resp.status_code == 200
    ranked = resp.json()["ranked"]
    returned_ids = {c["listing_id"] for c in ranked}
    assert returned_ids == {1, 2, 3}


# ---------------------------------------------------------------------------
# 7. test_route_select_locality_same_region
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_route_select_locality_same_region(client):
    """Same region gets locality=1.0, ranked first."""
    candidates = [
        _candidate(1, price_usdc=0.02, region="us-east", quality_score=0.7),
        _candidate(2, price_usdc=0.01, region="asia-south", quality_score=0.9),
    ]
    resp = await client.post(
        "/api/v1/route/select",
        json={
            "candidates": candidates,
            "strategy": "locality",
            "buyer_region": "us-east",
        },
    )
    assert resp.status_code == 200
    ranked = resp.json()["ranked"]
    # us-east same region locality=1.0 should beat asia-south locality=0.2
    assert ranked[0]["listing_id"] == 1


# ---------------------------------------------------------------------------
# 8. test_route_select_locality_adjacent
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_route_select_locality_adjacent(client):
    """Adjacent region gets locality=0.5."""
    candidates = [
        _candidate(1, price_usdc=0.01, region="us-west", quality_score=0.7),   # adjacent to us-east
        _candidate(2, price_usdc=0.01, region="asia-south", quality_score=0.7),  # not adjacent
    ]
    resp = await client.post(
        "/api/v1/route/select",
        json={
            "candidates": candidates,
            "strategy": "locality",
            "buyer_region": "us-east",
        },
    )
    assert resp.status_code == 200
    ranked = resp.json()["ranked"]
    # us-west adjacent (0.5) beats asia-south other (0.2) with equal quality/price
    assert ranked[0]["listing_id"] == 1


# ---------------------------------------------------------------------------
# 9. test_route_select_locality_other
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_route_select_locality_other(client):
    """Non-adjacent region gets locality=0.2."""
    candidates = [
        _candidate(1, price_usdc=0.01, region="us-east", quality_score=0.5),    # same → 1.0
        _candidate(2, price_usdc=0.01, region="us-west", quality_score=0.5),    # adjacent → 0.5
        _candidate(3, price_usdc=0.01, region="asia-south", quality_score=0.5),  # other → 0.2
    ]
    resp = await client.post(
        "/api/v1/route/select",
        json={
            "candidates": candidates,
            "strategy": "locality",
            "buyer_region": "us-east",
        },
    )
    assert resp.status_code == 200
    ranked = resp.json()["ranked"]
    assert ranked[0]["listing_id"] == 1  # same region
    assert ranked[1]["listing_id"] == 2  # adjacent
    assert ranked[2]["listing_id"] == 3  # other


# ---------------------------------------------------------------------------
# 10. test_route_select_locality_no_region
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_route_select_locality_no_region(client):
    """Locality with no buyer_region falls back to best_value."""
    candidates = [
        _candidate(1, price_usdc=0.05, quality_score=0.5, reputation=0.5, freshness_score=0.5),
        _candidate(2, price_usdc=0.01, quality_score=0.9, reputation=0.9, freshness_score=0.9),
    ]
    resp = await client.post(
        "/api/v1/route/select",
        json={
            "candidates": candidates,
            "strategy": "locality",
            "buyer_region": None,
        },
    )
    assert resp.status_code == 200
    ranked = resp.json()["ranked"]
    # Falls back to best_value: candidate 2 has higher quality/price ratio
    assert ranked[0]["listing_id"] == 2
    # Strategy label is still "locality" per the API
    assert resp.json()["strategy"] == "locality"


# ---------------------------------------------------------------------------
# 11. test_route_select_invalid_strategy
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_route_select_invalid_strategy(client):
    """Invalid strategy falls back to best_value scoring."""
    candidates = [
        _candidate(1, price_usdc=0.05, quality_score=0.5, reputation=0.5, freshness_score=0.5),
        _candidate(2, price_usdc=0.01, quality_score=0.9, reputation=0.8, freshness_score=0.9),
    ]
    resp = await client.post(
        "/api/v1/route/select",
        json={"candidates": candidates, "strategy": "NONEXISTENT_STRATEGY"},
    )
    assert resp.status_code == 200
    ranked = resp.json()["ranked"]
    # Falls back to best_value: candidate 2 wins
    assert ranked[0]["listing_id"] == 2
    assert ranked[0]["routing_strategy"] == "best_value"


# ---------------------------------------------------------------------------
# 12. test_route_select_single_candidate
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_route_select_single_candidate(client):
    """Single candidate is returned as-is with routing metadata."""
    candidates = [_candidate(1, price_usdc=0.01)]
    resp = await client.post(
        "/api/v1/route/select",
        json={"candidates": candidates, "strategy": "cheapest"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["count"] == 1
    assert data["ranked"][0]["listing_id"] == 1
    assert "routing_score" in data["ranked"][0]


# ---------------------------------------------------------------------------
# 13. test_route_select_empty_candidates
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_route_select_empty_candidates(client):
    """Empty candidates list triggers 422 validation error (min_length=1)."""
    resp = await client.post(
        "/api/v1/route/select",
        json={"candidates": [], "strategy": "cheapest"},
    )
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# 14. test_route_select_default_strategy
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_route_select_default_strategy(client):
    """Omitting strategy defaults to 'best_value'."""
    candidates = [
        _candidate(1, price_usdc=0.05, quality_score=0.5, reputation=0.5, freshness_score=0.5),
        _candidate(2, price_usdc=0.01, quality_score=0.9, reputation=0.8, freshness_score=0.9),
    ]
    resp = await client.post(
        "/api/v1/route/select",
        json={"candidates": candidates},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["strategy"] == "best_value"
    # best_value: candidate 2 wins with high quality and low price
    assert data["ranked"][0]["listing_id"] == 2


# ---------------------------------------------------------------------------
# 15. test_route_select_response_has_routing_score
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_route_select_response_has_routing_score(client):
    """Every result item has a routing_score field."""
    candidates = [
        _candidate(1, price_usdc=0.01),
        _candidate(2, price_usdc=0.02),
        _candidate(3, price_usdc=0.03),
    ]
    resp = await client.post(
        "/api/v1/route/select",
        json={"candidates": candidates, "strategy": "cheapest"},
    )
    assert resp.status_code == 200
    ranked = resp.json()["ranked"]
    for item in ranked:
        assert "routing_score" in item, f"Missing routing_score on listing {item['listing_id']}"
        assert isinstance(item["routing_score"], (int, float))


# ---------------------------------------------------------------------------
# 16. test_route_select_response_has_routing_strategy
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_route_select_response_has_routing_strategy(client):
    """Every result item has a routing_strategy field matching the request."""
    candidates = [
        _candidate(1, price_usdc=0.01),
        _candidate(2, price_usdc=0.02),
    ]
    resp = await client.post(
        "/api/v1/route/select",
        json={"candidates": candidates, "strategy": "fastest"},
    )
    assert resp.status_code == 200
    ranked = resp.json()["ranked"]
    for item in ranked:
        assert item["routing_strategy"] == "fastest"


# ---------------------------------------------------------------------------
# 17. test_route_select_count_matches
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_route_select_count_matches(client):
    """The 'count' field matches the length of 'ranked'."""
    candidates = [
        _candidate(i, price_usdc=0.01 * (i + 1)) for i in range(1, 6)
    ]
    resp = await client.post(
        "/api/v1/route/select",
        json={"candidates": candidates, "strategy": "cheapest"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["count"] == len(data["ranked"])
    assert data["count"] == 5


# ---------------------------------------------------------------------------
# 18. test_route_select_tied_prices_cheapest
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_route_select_tied_prices_cheapest(client):
    """Tied prices produce equal routing_scores (0.5 for all)."""
    candidates = [
        _candidate(1, price_usdc=0.02, seller_id=101),
        _candidate(2, price_usdc=0.02, seller_id=102),
        _candidate(3, price_usdc=0.02, seller_id=103),
    ]
    resp = await client.post(
        "/api/v1/route/select",
        json={"candidates": candidates, "strategy": "cheapest"},
    )
    assert resp.status_code == 200
    ranked = resp.json()["ranked"]
    scores = [c["routing_score"] for c in ranked]
    # All tied at 0.5 (normalized same values)
    assert all(s == 0.5 for s in scores)
    # All 3 candidates present
    assert len(ranked) == 3


# ---------------------------------------------------------------------------
# 19. test_route_select_high_quality_low_price_best_value
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_route_select_high_quality_low_price_best_value(client):
    """High quality + low price wins best_value over low quality + high price."""
    candidates = [
        _candidate(1, price_usdc=0.08, quality_score=0.3, reputation=0.3, freshness_score=0.3),
        _candidate(2, price_usdc=0.01, quality_score=0.95, reputation=0.9, freshness_score=0.95),
    ]
    resp = await client.post(
        "/api/v1/route/select",
        json={"candidates": candidates, "strategy": "best_value"},
    )
    assert resp.status_code == 200
    ranked = resp.json()["ranked"]
    assert ranked[0]["listing_id"] == 2
    # Winner should have a higher score than loser
    assert ranked[0]["routing_score"] > ranked[1]["routing_score"]


# ---------------------------------------------------------------------------
# 20. test_route_select_many_candidates
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_route_select_many_candidates(client):
    """20 candidates are all returned and ranked."""
    candidates = [
        _candidate(i, price_usdc=round(0.01 + i * 0.002, 4), quality_score=round(0.5 + i * 0.02, 2))
        for i in range(1, 21)
    ]
    resp = await client.post(
        "/api/v1/route/select",
        json={"candidates": candidates, "strategy": "best_value"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["count"] == 20
    assert len(data["ranked"]) == 20
    # All original listing IDs are present
    returned_ids = {c["listing_id"] for c in data["ranked"]}
    expected_ids = set(range(1, 21))
    assert returned_ids == expected_ids


# ---------------------------------------------------------------------------
# 21. test_route_select_missing_optional_fields
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_route_select_missing_optional_fields(client):
    """Candidates without optional fields (avg_response_ms, reputation, etc.) still work."""
    candidates = [
        {
            "listing_id": 1,
            "seller_id": 101,
            "price_usdc": 0.01,
            "quality_score": 0.8,
            "match_score": 0.85,
        },
        {
            "listing_id": 2,
            "seller_id": 102,
            "price_usdc": 0.02,
            "quality_score": 0.7,
            "match_score": 0.75,
        },
    ]
    # Test with several strategies that use optional fields
    for strategy in ["fastest", "highest_quality", "best_value"]:
        resp = await client.post(
            "/api/v1/route/select",
            json={"candidates": candidates, "strategy": strategy},
        )
        assert resp.status_code == 200, f"Failed for strategy '{strategy}'"
        ranked = resp.json()["ranked"]
        assert len(ranked) == 2
        for item in ranked:
            assert "routing_score" in item


# ---------------------------------------------------------------------------
# 22. test_strategies_endpoint
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_strategies_endpoint(client):
    """GET /route/strategies returns all 7 strategies."""
    resp = await client.get("/api/v1/route/strategies")
    assert resp.status_code == 200
    data = resp.json()
    expected = [
        "cheapest", "fastest", "highest_quality", "best_value",
        "round_robin", "weighted_random", "locality",
    ]
    assert data["strategies"] == expected
    assert len(data["strategies"]) == 7


# ---------------------------------------------------------------------------
# 23. test_strategies_has_default
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_strategies_has_default(client):
    """GET /route/strategies reports 'best_value' as the default."""
    resp = await client.get("/api/v1/route/strategies")
    assert resp.status_code == 200
    assert resp.json()["default"] == "best_value"


# ---------------------------------------------------------------------------
# 24. test_strategies_has_descriptions
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_strategies_has_descriptions(client):
    """GET /route/strategies returns a description for every strategy."""
    resp = await client.get("/api/v1/route/strategies")
    assert resp.status_code == 200
    data = resp.json()
    descriptions = data["descriptions"]
    expected_keys = {
        "cheapest", "fastest", "highest_quality", "best_value",
        "round_robin", "weighted_random", "locality",
    }
    assert set(descriptions.keys()) == expected_keys
    # Each description is a non-empty string
    for key, desc in descriptions.items():
        assert isinstance(desc, str) and len(desc) > 0, f"Empty description for {key}"


# ---------------------------------------------------------------------------
# 25. test_route_select_cheapest_multiple
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_route_select_cheapest_multiple(client):
    """Verify full ranking order for cheapest strategy (5 candidates)."""
    candidates = [
        _candidate(1, price_usdc=0.05),  # most expensive → lowest score
        _candidate(2, price_usdc=0.01),  # cheapest → highest score (1.0)
        _candidate(3, price_usdc=0.03),  # middle
        _candidate(4, price_usdc=0.04),  # 2nd most expensive
        _candidate(5, price_usdc=0.02),  # 2nd cheapest
    ]
    resp = await client.post(
        "/api/v1/route/select",
        json={"candidates": candidates, "strategy": "cheapest"},
    )
    assert resp.status_code == 200
    ranked = resp.json()["ranked"]
    ranked_ids = [c["listing_id"] for c in ranked]
    # Expected order: 2 (0.01), 5 (0.02), 3 (0.03), 4 (0.04), 1 (0.05)
    assert ranked_ids == [2, 5, 3, 4, 1]
    # Verify scores are descending
    scores = [c["routing_score"] for c in ranked]
    assert scores == sorted(scores, reverse=True)
    # Cheapest gets 1.0, most expensive gets 0.0
    assert scores[0] == 1.0
    assert scores[-1] == 0.0
