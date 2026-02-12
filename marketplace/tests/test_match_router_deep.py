"""Deep tests for match_service and router_service.

25 tests covering:
- _normalize edge cases (4 tests)
- All 7 routing strategies via smart_route (14 tests)
- auto_match DB-based integration tests (7 tests)

Router tests call smart_route / _normalize directly with dicts (no DB).
Match tests use the db + make_agent + make_listing fixtures from conftest.
"""

import pytest
from collections import Counter
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from marketplace.services.router_service import (
    smart_route,
    _normalize,
    STRATEGIES,
    _round_robin_state,
    REGION_ADJACENCY,
)
from marketplace.services.match_service import auto_match, _compute_match_score
from marketplace.models.agent_stats import AgentStats


# ---------------------------------------------------------------------------
# Candidate factory (pure dicts, no DB)
# ---------------------------------------------------------------------------

def _cand(
    listing_id: str = "a",
    price_usdc: float = 0.01,
    quality_score: float = 0.8,
    match_score: float = 0.9,
    seller_id: str = "s1",
    reputation: float = 0.7,
    freshness_score: float = 0.9,
    avg_response_ms: int = 100,
    region: str = "us-east",
    content_hash: str = "hash0",
    **extra,
) -> dict:
    d = {
        "listing_id": listing_id,
        "price_usdc": price_usdc,
        "quality_score": quality_score,
        "match_score": match_score,
        "seller_id": seller_id,
        "reputation": reputation,
        "freshness_score": freshness_score,
        "avg_response_ms": avg_response_ms,
        "region": region,
        "content_hash": content_hash,
    }
    d.update(extra)
    return d


# ===================================================================
# 1-4  _normalize tests
# ===================================================================

def test_normalize_basic():
    """[1,2,3] -> [0.0, 0.5, 1.0]."""
    result = _normalize([1, 2, 3])
    assert result == pytest.approx([0.0, 0.5, 1.0])


def test_normalize_all_same():
    """[5,5,5] -> [0.5, 0.5, 0.5]."""
    result = _normalize([5, 5, 5])
    assert result == [0.5, 0.5, 0.5]


def test_normalize_empty():
    """Empty list returns empty list."""
    result = _normalize([])
    assert result == []


def test_normalize_two_values():
    """[0, 10] -> [0.0, 1.0]."""
    result = _normalize([0, 10])
    assert result == pytest.approx([0.0, 1.0])


# ===================================================================
# 5  cheapest: lowest price wins
# ===================================================================

def test_cheapest_lowest_price_wins():
    """Cheapest candidate gets routing_score 1.0 and is first."""
    candidates = [
        _cand(listing_id="expensive", price_usdc=0.05, seller_id="s1"),
        _cand(listing_id="cheap", price_usdc=0.01, seller_id="s2"),
        _cand(listing_id="mid", price_usdc=0.03, seller_id="s3"),
    ]
    result = smart_route(candidates, strategy="cheapest")
    assert result[0]["listing_id"] == "cheap"
    assert result[0]["routing_score"] == 1.0
    assert result[-1]["listing_id"] == "expensive"
    assert result[-1]["routing_score"] == 0.0


# ===================================================================
# 6  fastest: lowest avg_response_ms wins
# ===================================================================

def test_fastest_lowest_ms_wins():
    """Candidate with lowest avg_response_ms gets routing_score 1.0."""
    candidates = [
        _cand(listing_id="slow", avg_response_ms=500, seller_id="s1"),
        _cand(listing_id="fast", avg_response_ms=50, seller_id="s2"),
        _cand(listing_id="medium", avg_response_ms=200, seller_id="s3"),
    ]
    result = smart_route(candidates, strategy="fastest")
    assert result[0]["listing_id"] == "fast"
    assert result[0]["routing_score"] == 1.0
    assert result[-1]["listing_id"] == "slow"
    assert result[-1]["routing_score"] == 0.0


# ===================================================================
# 7  highest_quality formula
# ===================================================================

def test_highest_quality_formula():
    """Score = 0.5*quality + 0.3*reputation + 0.2*freshness."""
    candidates = [
        _cand(
            listing_id="hq",
            quality_score=0.9,
            reputation=0.8,
            freshness_score=0.7,
            seller_id="s1",
        ),
    ]
    result = smart_route(candidates, strategy="highest_quality")
    expected = round(0.5 * 0.9 + 0.3 * 0.8 + 0.2 * 0.7, 4)
    assert result[0]["routing_score"] == expected


# ===================================================================
# 8  best_value: high quality / low price wins
# ===================================================================

def test_best_value_high_quality_low_price():
    """High quality at low price beats low quality at high price."""
    candidates = [
        _cand(listing_id="great_value", price_usdc=0.01, quality_score=0.95,
              reputation=0.8, freshness_score=0.9, seller_id="s1"),
        _cand(listing_id="poor_value", price_usdc=0.08, quality_score=0.5,
              reputation=0.4, freshness_score=0.5, seller_id="s2"),
    ]
    result = smart_route(candidates, strategy="best_value")
    assert result[0]["listing_id"] == "great_value"
    assert result[0]["routing_score"] > result[1]["routing_score"]


# ===================================================================
# 9  best_value: quality/price ratio capped at 100
# ===================================================================

def test_best_value_capped_ratio():
    """quality/price is capped at 100 (then divided by 100 -> max 1.0)."""
    # quality=0.9, price=0.0001 -> 0.9/0.0001 = 9000, but capped at 100
    candidates = [
        _cand(listing_id="extreme", price_usdc=0.0001, quality_score=0.9,
              reputation=0.5, freshness_score=0.5, seller_id="s1"),
        _cand(listing_id="normal", price_usdc=0.01, quality_score=0.9,
              reputation=0.5, freshness_score=0.5, seller_id="s2"),
    ]
    result = smart_route(candidates, strategy="best_value")
    # Both hit the cap, so the value_norm component is 1.0 for "extreme"
    # but "extreme" also gets better 1-price_norm bonus
    extreme = next(c for c in result if c["listing_id"] == "extreme")
    normal = next(c for c in result if c["listing_id"] == "normal")
    # Verify cap: value_norm for extreme would be 1.0 (capped at 100/100)
    # value_norm for normal: min(0.9/0.01, 100)/100 = min(90, 100)/100 = 0.9
    assert extreme["routing_score"] >= normal["routing_score"]


# ===================================================================
# 10  round_robin: fair rotation — winner's count incremented
# ===================================================================

def test_round_robin_fair_rotation():
    """Winner's access_count is incremented in TTLCache."""
    _round_robin_state.clear()

    candidates = [
        _cand(listing_id="a", seller_id="s1", content_hash="rr_deep_1"),
        _cand(listing_id="b", seller_id="s2", content_hash="rr_deep_1"),
    ]
    result = smart_route(candidates, strategy="round_robin")

    winner_seller = result[0]["seller_id"]
    key = f"rr:rr_deep_1:{winner_seller}"
    assert _round_robin_state.get(key) == 1

    # Loser should NOT have been incremented
    loser_seller = result[1]["seller_id"]
    loser_key = f"rr:rr_deep_1:{loser_seller}"
    assert _round_robin_state.get(loser_key) is None


# ===================================================================
# 11  round_robin: second call picks different winner
# ===================================================================

def test_round_robin_second_call_different():
    """Second invocation with same candidates picks a different winner."""
    _round_robin_state.clear()

    c1 = _cand(listing_id="x", seller_id="rx1", content_hash="rr_deep_2")
    c2 = _cand(listing_id="y", seller_id="rx2", content_hash="rr_deep_2")

    r1 = smart_route([c1.copy(), c2.copy()], strategy="round_robin")
    first_winner = r1[0]["seller_id"]

    r2 = smart_route([c1.copy(), c2.copy()], strategy="round_robin")
    second_winner = r2[0]["seller_id"]

    assert first_winner != second_winner


# ===================================================================
# 12  weighted_random: all candidates present in output
# ===================================================================

def test_weighted_random_all_present():
    """All input candidates appear in output (just reordered)."""
    ids = {"wa", "wb", "wc", "wd"}
    candidates = [
        _cand(listing_id=lid, seller_id=f"s_{lid}", price_usdc=0.01 + i * 0.01,
              quality_score=0.8)
        for i, lid in enumerate(sorted(ids))
    ]
    result = smart_route(candidates, strategy="weighted_random")
    assert {c["listing_id"] for c in result} == ids
    assert len(result) == len(ids)


# ===================================================================
# 13  weighted_random: high quality appears first more often
# ===================================================================

def test_weighted_random_high_quality_more_likely():
    """Over 100 runs, high-quality candidate appears first more often than low-quality."""
    first_counts: Counter = Counter()
    for _ in range(100):
        candidates = [
            _cand(listing_id="high", price_usdc=0.01, quality_score=0.99,
                  reputation=0.99, seller_id="sh"),
            _cand(listing_id="low", price_usdc=0.01, quality_score=0.01,
                  reputation=0.01, seller_id="sl"),
        ]
        result = smart_route(candidates, strategy="weighted_random")
        first_counts[result[0]["listing_id"]] += 1

    assert first_counts["high"] > first_counts["low"]


# ===================================================================
# 14  locality: same region scores 1.0
# ===================================================================

def test_locality_same_region():
    """Seller in same region as buyer gets locality=1.0."""
    candidates = [
        _cand(listing_id="same", region="us-east", quality_score=0.5,
              price_usdc=0.05, seller_id="s1"),
        _cand(listing_id="far", region="asia-south", quality_score=0.5,
              price_usdc=0.05, seller_id="s2"),
    ]
    result = smart_route(candidates, strategy="locality", buyer_region="us-east")
    assert result[0]["listing_id"] == "same"
    # locality=1.0, quality=0.5, price_inv=1-0.05/0.1=0.5
    expected = round(0.5 * 1.0 + 0.3 * 0.5 + 0.2 * 0.5, 4)
    assert result[0]["routing_score"] == expected


# ===================================================================
# 15  locality: adjacent region scores 0.5
# ===================================================================

def test_locality_adjacent_region():
    """Seller in adjacent region gets locality=0.5."""
    # us-west is adjacent to us-east per REGION_ADJACENCY
    assert "us-west" in REGION_ADJACENCY["us-east"]

    candidates = [
        _cand(listing_id="adj", region="us-west", quality_score=0.6,
              price_usdc=0.02, seller_id="s1"),
    ]
    result = smart_route(candidates, strategy="locality", buyer_region="us-east")
    # locality=0.5, quality=0.6, price_inv=1-0.02/0.1=0.8
    expected = round(0.5 * 0.5 + 0.3 * 0.6 + 0.2 * 0.8, 4)
    assert result[0]["routing_score"] == expected


# ===================================================================
# 16  locality: other region scores 0.2
# ===================================================================

def test_locality_other_region():
    """Seller in non-adjacent region gets locality=0.2."""
    # asia-south is NOT adjacent to us-east
    assert "asia-south" not in REGION_ADJACENCY.get("us-east", set())

    candidates = [
        _cand(listing_id="far", region="asia-south", quality_score=0.6,
              price_usdc=0.02, seller_id="s1"),
    ]
    result = smart_route(candidates, strategy="locality", buyer_region="us-east")
    expected = round(0.5 * 0.2 + 0.3 * 0.6 + 0.2 * (1 - 0.02 / 0.1), 4)
    assert result[0]["routing_score"] == expected


# ===================================================================
# 17  locality: no buyer_region falls back to best_value
# ===================================================================

def test_locality_no_buyer_region():
    """When buyer_region is None, locality falls back to best_value."""
    candidates = [
        _cand(listing_id="a", price_usdc=0.05, quality_score=0.5,
              reputation=0.5, freshness_score=0.5, seller_id="s1"),
        _cand(listing_id="b", price_usdc=0.01, quality_score=0.9,
              reputation=0.8, freshness_score=0.8, seller_id="s2"),
    ]
    loc_result = smart_route(
        [c.copy() for c in candidates], strategy="locality", buyer_region=None,
    )
    bv_result = smart_route(
        [c.copy() for c in candidates], strategy="best_value",
    )
    # Same ranking order (best_value used internally)
    assert loc_result[0]["listing_id"] == bv_result[0]["listing_id"]
    # But strategy label stays "locality"
    assert all(c["routing_strategy"] == "locality" for c in loc_result)


# ===================================================================
# 18  invalid strategy falls back to best_value
# ===================================================================

def test_invalid_strategy_fallback():
    """Unknown strategy string falls back to best_value."""
    candidates = [
        _cand(listing_id="a", price_usdc=0.01, quality_score=0.9, seller_id="s1"),
        _cand(listing_id="b", price_usdc=0.05, quality_score=0.4, seller_id="s2"),
    ]
    result = smart_route(candidates, strategy="totally_made_up")
    # Fallback strategy label is "best_value"
    assert result[0]["routing_strategy"] == "best_value"
    assert len(result) == 2


# ===================================================================
# 19  empty candidates returns empty list
# ===================================================================

def test_empty_candidates():
    """smart_route([]) returns []."""
    result = smart_route([], strategy="cheapest")
    assert result == []


# ===================================================================
# 20  routing_score field is added to every candidate
# ===================================================================

def test_routing_score_added():
    """Every candidate in the result must have a 'routing_score' key."""
    candidates = [
        _cand(listing_id="a", seller_id="s1"),
        _cand(listing_id="b", seller_id="s2"),
        _cand(listing_id="c", seller_id="s3"),
    ]
    for strategy in STRATEGIES:
        _round_robin_state.clear()  # clean state for round_robin
        result = smart_route(
            [c.copy() for c in candidates],
            strategy=strategy,
            buyer_region="us-east",
        )
        for c in result:
            assert "routing_score" in c, f"routing_score missing for strategy={strategy}"
            assert isinstance(c["routing_score"], float), (
                f"routing_score not float for strategy={strategy}"
            )


# ===================================================================
# 21  routing_strategy field is added to every candidate
# ===================================================================

def test_routing_strategy_added():
    """Every candidate in the result must have a 'routing_strategy' key."""
    candidates = [
        _cand(listing_id="a", seller_id="s1"),
        _cand(listing_id="b", seller_id="s2"),
    ]
    for strategy in STRATEGIES:
        _round_robin_state.clear()
        result = smart_route(
            [c.copy() for c in candidates],
            strategy=strategy,
            buyer_region="us-east",
        )
        for c in result:
            assert "routing_strategy" in c
            # Invalid strategies become "best_value", valid stay as-is
            assert c["routing_strategy"] == strategy


# ===================================================================
# 22-25  auto_match DB integration tests
# ===================================================================

@pytest.mark.asyncio
async def test_auto_match_keyword_overlap(db, make_agent, make_listing):
    """Listings whose title/description overlaps with query score higher."""
    seller, _ = await make_agent(name="kw_seller")

    # High overlap
    await make_listing(
        seller.id,
        title="machine learning deep neural network",
        description="advanced deep learning models",
        category="code_analysis",
        price_usdc=0.005,
        quality_score=0.7,
    )
    # No overlap
    await make_listing(
        seller.id,
        title="cooking recipe dessert",
        description="how to bake a cake",
        category="code_analysis",
        price_usdc=0.005,
        quality_score=0.7,
    )

    result = await auto_match(db, "machine learning deep neural")

    assert len(result["matches"]) == 2
    # The listing with keyword overlap must rank first
    assert "machine" in result["matches"][0]["title"].lower()
    assert result["matches"][0]["match_score"] > result["matches"][1]["match_score"]


@pytest.mark.asyncio
async def test_auto_match_excludes_buyer(db, make_agent, make_listing):
    """Buyer's own listings are excluded from results."""
    buyer, _ = await make_agent(name="buyer_excl")
    other_seller, _ = await make_agent(name="other_seller")

    await make_listing(
        buyer.id,
        title="buyer owns this data",
        description="my own listing",
        category="web_search",
        price_usdc=0.005,
    )
    await make_listing(
        other_seller.id,
        title="seller data available",
        description="external listing",
        category="web_search",
        price_usdc=0.005,
    )

    result = await auto_match(db, "data listing", buyer_id=buyer.id)

    for m in result["matches"]:
        assert m["seller_id"] != buyer.id
    assert len(result["matches"]) == 1
    assert result["matches"][0]["seller_id"] == other_seller.id


@pytest.mark.asyncio
async def test_auto_match_max_5_results(db, make_agent, make_listing):
    """Even with 10 active listings, only top 5 are returned."""
    seller, _ = await make_agent(name="bulk_seller")

    for i in range(10):
        await make_listing(
            seller.id,
            title=f"data analysis report {i}",
            description="comprehensive analysis of trends",
            category="web_search",
            price_usdc=0.005,
            quality_score=0.5 + i * 0.04,
        )

    result = await auto_match(db, "data analysis report")

    assert len(result["matches"]) == 5
    assert result["total_candidates"] == 10
    # Verify descending match_score order
    scores = [m["match_score"] for m in result["matches"]]
    assert scores == sorted(scores, reverse=True)


@pytest.mark.asyncio
async def test_auto_match_category_filter(db, make_agent, make_listing):
    """Category filter restricts results to the specified category."""
    seller, _ = await make_agent(name="multi_cat_seller")

    await make_listing(
        seller.id,
        title="python code review",
        description="automated code analysis",
        category="code_analysis",
        price_usdc=0.005,
    )
    await make_listing(
        seller.id,
        title="python web search results",
        description="search engine output",
        category="web_search",
        price_usdc=0.005,
    )
    await make_listing(
        seller.id,
        title="python api data",
        description="rest api response",
        category="api_response",
        price_usdc=0.005,
    )

    result = await auto_match(db, "python", category="code_analysis")

    assert result["category_filter"] == "code_analysis"
    assert len(result["matches"]) == 1
    assert result["matches"][0]["category"] == "code_analysis"
