"""Route-level tests for POST /api/v1/agents/auto-match (25 tests).

Covers: basic matching, validation errors, category/price filters,
buyer-exclusion, routing strategies, auto-buy with express purchase,
response schema, keyword overlap, quality ranking, inactive listings.

Uses the shared conftest fixtures (client, make_agent, make_listing,
make_token_account, seed_platform) and the in-memory SQLite test engine.
"""

from decimal import Decimal
from unittest.mock import AsyncMock, patch

import pytest

from marketplace.core.auth import create_access_token
from marketplace.models.token_account import TokenAccount, TokenSupply
from marketplace.models.transaction import Transaction
from marketplace.tests.conftest import TestSession, _new_id

from sqlalchemy import select


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

URL = "/api/v1/agents/auto-match"
CDN_PATCH = "marketplace.services.express_service.cdn_get_content"
SAMPLE_CONTENT = b'{"data": "auto-match integration test payload"}'


async def _seed_platform():
    """Ensure platform treasury account and TokenSupply singleton exist."""
    async with TestSession() as db:
        result = await db.execute(
            select(TokenAccount).where(TokenAccount.agent_id.is_(None))
        )
        if result.scalar_one_or_none() is None:
            db.add(TokenAccount(
                id=_new_id(), agent_id=None,
                balance=Decimal("0"), tier="platform",
            ))
            db.add(TokenSupply(id=1))
            await db.commit()


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


# ---------------------------------------------------------------------------
# 1. test_automatch_basic_success
# ---------------------------------------------------------------------------

async def test_automatch_basic_success(client, make_agent, make_listing):
    """Search with a matching description returns matches."""
    seller, _ = await make_agent(name="seller-basic")
    await make_listing(
        seller.id, price_usdc=0.005, category="web_search",
        title="Python web scraping tutorial",
    )
    await make_listing(
        seller.id, price_usdc=0.008, category="web_search",
        title="JavaScript React guide",
    )

    buyer, buyer_jwt = await make_agent(name="buyer-basic")

    resp = await client.post(URL, json={
        "description": "python scraping tutorial",
    }, headers=_auth(buyer_jwt))

    assert resp.status_code == 200
    body = resp.json()
    assert "matches" in body
    assert len(body["matches"]) >= 1
    assert body["query"] == "python scraping tutorial"


# ---------------------------------------------------------------------------
# 2. test_automatch_no_matches
# ---------------------------------------------------------------------------

async def test_automatch_no_matches(client, make_agent, make_listing):
    """Search with an unrelated description returns zero matches when
    all listings belong to the buyer (excluded) or there simply are none."""
    buyer, buyer_jwt = await make_agent(name="buyer-no-match")

    resp = await client.post(URL, json={
        "description": "quantum physics simulation",
    }, headers=_auth(buyer_jwt))

    assert resp.status_code == 200
    body = resp.json()
    # No listings at all in the database for another seller
    assert body["matches"] == [] or body["total_candidates"] == 0


# ---------------------------------------------------------------------------
# 3. test_automatch_category_filter
# ---------------------------------------------------------------------------

async def test_automatch_category_filter(client, make_agent, make_listing):
    """Filter by category excludes non-matching categories."""
    seller, _ = await make_agent(name="seller-cat")
    await make_listing(seller.id, category="web_search", title="Python web results")
    await make_listing(seller.id, category="code_analysis", title="Python code review")

    buyer, buyer_jwt = await make_agent(name="buyer-cat")

    resp = await client.post(URL, json={
        "description": "python",
        "category": "web_search",
    }, headers=_auth(buyer_jwt))

    assert resp.status_code == 200
    body = resp.json()
    assert body["category_filter"] == "web_search"
    for m in body["matches"]:
        assert m["category"] == "web_search"


# ---------------------------------------------------------------------------
# 4. test_automatch_max_price_filter
# ---------------------------------------------------------------------------

async def test_automatch_max_price_filter(client, make_agent, make_listing):
    """Filter by max_price excludes expensive listings."""
    seller, _ = await make_agent(name="seller-price")
    await make_listing(seller.id, price_usdc=0.003, title="Cheap Python tutorial")
    await make_listing(seller.id, price_usdc=0.015, title="Premium Python tutorial")

    buyer, buyer_jwt = await make_agent(name="buyer-price")

    resp = await client.post(URL, json={
        "description": "python tutorial",
        "max_price": 0.01,
    }, headers=_auth(buyer_jwt))

    assert resp.status_code == 200
    body = resp.json()
    assert len(body["matches"]) == 1
    assert body["matches"][0]["price_usdc"] <= 0.01


# ---------------------------------------------------------------------------
# 5. test_automatch_excludes_buyer_own_listings
# ---------------------------------------------------------------------------

async def test_automatch_excludes_buyer_own_listings(client, make_agent, make_listing):
    """Buyer's own listings are excluded from results."""
    buyer, buyer_jwt = await make_agent(name="buyer-own")
    seller, _ = await make_agent(name="seller-other")

    await make_listing(buyer.id, title="My Python tutorial", category="web_search")
    await make_listing(seller.id, title="Python tutorial for sale", category="web_search")

    resp = await client.post(URL, json={
        "description": "python tutorial",
    }, headers=_auth(buyer_jwt))

    assert resp.status_code == 200
    body = resp.json()
    for m in body["matches"]:
        assert m["seller_id"] != buyer.id


# ---------------------------------------------------------------------------
# 6. test_automatch_unauthenticated
# ---------------------------------------------------------------------------

async def test_automatch_unauthenticated(client):
    """Request without token returns 401."""
    resp = await client.post(URL, json={
        "description": "python tutorial",
    })

    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# 7. test_automatch_empty_description
# ---------------------------------------------------------------------------

async def test_automatch_empty_description(client, make_agent):
    """Empty description violates min_length=1, returns 422."""
    _, token = await make_agent(name="buyer-empty")

    resp = await client.post(URL, json={
        "description": "",
    }, headers=_auth(token))

    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# 8. test_automatch_description_too_long
# ---------------------------------------------------------------------------

async def test_automatch_description_too_long(client, make_agent):
    """Description over 500 chars violates max_length, returns 422."""
    _, token = await make_agent(name="buyer-long")

    resp = await client.post(URL, json={
        "description": "x" * 501,
    }, headers=_auth(token))

    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# 9. test_automatch_negative_max_price
# ---------------------------------------------------------------------------

async def test_automatch_negative_max_price(client, make_agent):
    """Negative max_price violates ge=0, returns 422."""
    _, token = await make_agent(name="buyer-neg")

    resp = await client.post(URL, json={
        "description": "python tutorial",
        "max_price": -1.0,
    }, headers=_auth(token))

    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# 10. test_automatch_returns_top_5
# ---------------------------------------------------------------------------

async def test_automatch_returns_top_5(client, make_agent, make_listing):
    """At most 5 matches are returned even when more candidates exist."""
    seller, _ = await make_agent(name="seller-top5")
    for i in range(10):
        await make_listing(
            seller.id, title=f"Python tutorial {i}",
            price_usdc=0.005, quality_score=0.5 + i * 0.04,
        )

    buyer, buyer_jwt = await make_agent(name="buyer-top5")

    resp = await client.post(URL, json={
        "description": "python tutorial",
    }, headers=_auth(buyer_jwt))

    assert resp.status_code == 200
    body = resp.json()
    assert len(body["matches"]) == 5
    assert body["total_candidates"] == 10


# ---------------------------------------------------------------------------
# 11. test_automatch_match_score_ordering
# ---------------------------------------------------------------------------

async def test_automatch_match_score_ordering(client, make_agent, make_listing):
    """Results are sorted by match_score descending."""
    seller, _ = await make_agent(name="seller-order")
    await make_listing(seller.id, title="Python tutorial basics", quality_score=0.9)
    await make_listing(seller.id, title="JavaScript React guide", quality_score=0.3)

    buyer, buyer_jwt = await make_agent(name="buyer-order")

    resp = await client.post(URL, json={
        "description": "python tutorial",
    }, headers=_auth(buyer_jwt))

    assert resp.status_code == 200
    matches = resp.json()["matches"]
    scores = [m["match_score"] for m in matches]
    assert scores == sorted(scores, reverse=True)


# ---------------------------------------------------------------------------
# 12. test_automatch_routing_strategy_cheapest
# ---------------------------------------------------------------------------

async def test_automatch_routing_strategy_cheapest(client, make_agent, make_listing):
    """routing_strategy='cheapest' re-ranks results by price ascending."""
    seller, _ = await make_agent(name="seller-cheap")
    await make_listing(seller.id, title="Expensive tutorial", price_usdc=0.009)
    await make_listing(seller.id, title="Cheap tutorial", price_usdc=0.002)

    buyer, buyer_jwt = await make_agent(name="buyer-cheap")

    resp = await client.post(URL, json={
        "description": "tutorial",
        "routing_strategy": "cheapest",
    }, headers=_auth(buyer_jwt))

    assert resp.status_code == 200
    body = resp.json()
    assert body["routing_strategy"] == "cheapest"
    if len(body["matches"]) >= 2:
        assert body["matches"][0]["price_usdc"] <= body["matches"][1]["price_usdc"]


# ---------------------------------------------------------------------------
# 13. test_automatch_routing_strategy_highest_quality
# ---------------------------------------------------------------------------

async def test_automatch_routing_strategy_highest_quality(client, make_agent, make_listing):
    """routing_strategy='highest_quality' re-ranks by quality."""
    seller, _ = await make_agent(name="seller-hq")
    await make_listing(seller.id, title="Low quality guide", quality_score=0.3)
    await make_listing(seller.id, title="High quality guide", quality_score=0.95)

    buyer, buyer_jwt = await make_agent(name="buyer-hq")

    resp = await client.post(URL, json={
        "description": "guide",
        "routing_strategy": "highest_quality",
    }, headers=_auth(buyer_jwt))

    assert resp.status_code == 200
    body = resp.json()
    assert body["routing_strategy"] == "highest_quality"
    if len(body["matches"]) >= 2:
        assert body["matches"][0]["quality_score"] >= body["matches"][1]["quality_score"]


# ---------------------------------------------------------------------------
# 14. test_automatch_routing_strategy_locality
# ---------------------------------------------------------------------------

async def test_automatch_routing_strategy_locality(client, make_agent, make_listing):
    """routing_strategy='locality' with buyer_region runs without error."""
    seller, _ = await make_agent(name="seller-loc")
    await make_listing(seller.id, title="Regional data guide", price_usdc=0.005)

    buyer, buyer_jwt = await make_agent(name="buyer-loc")

    resp = await client.post(URL, json={
        "description": "regional data",
        "routing_strategy": "locality",
        "buyer_region": "us-east",
    }, headers=_auth(buyer_jwt))

    assert resp.status_code == 200
    body = resp.json()
    assert body["routing_strategy"] == "locality"
    assert len(body["matches"]) >= 1


# ---------------------------------------------------------------------------
# 15. test_automatch_auto_buy_false
# ---------------------------------------------------------------------------

async def test_automatch_auto_buy_false(client, make_agent, make_listing):
    """auto_buy=False (default) does not trigger a purchase."""
    seller, _ = await make_agent(name="seller-noauto")
    await make_listing(seller.id, title="Python tutorial", price_usdc=0.005)

    buyer, buyer_jwt = await make_agent(name="buyer-noauto")

    resp = await client.post(URL, json={
        "description": "python tutorial",
        "auto_buy": False,
    }, headers=_auth(buyer_jwt))

    assert resp.status_code == 200
    body = resp.json()
    assert "auto_purchased" not in body
    assert "purchase_result" not in body


# ---------------------------------------------------------------------------
# 16. test_automatch_auto_buy_true_executes_purchase
# ---------------------------------------------------------------------------

@patch(CDN_PATCH, new_callable=AsyncMock)
async def test_automatch_auto_buy_true_executes_purchase(
    mock_cdn, client, make_agent, make_listing, make_token_account,
):
    """auto_buy=True with a matching listing under price triggers express_buy."""
    mock_cdn.return_value = SAMPLE_CONTENT
    await _seed_platform()

    seller, _ = await make_agent(name="seller-autobuy")
    await make_token_account(seller.id, balance=0)
    listing = await make_listing(
        seller.id, title="Python tutorial guide",
        price_usdc=0.005, quality_score=0.85,
    )

    buyer, buyer_jwt = await make_agent(name="buyer-autobuy")
    await make_token_account(buyer.id, balance=50000)

    resp = await client.post(URL, json={
        "description": "python tutorial guide",
        "auto_buy": True,
        "auto_buy_max_price": 0.01,
    }, headers=_auth(buyer_jwt))

    assert resp.status_code == 200
    body = resp.json()
    # The top match must have score >= 0.3 and price <= auto_buy_max_price
    if body["matches"] and body["matches"][0]["match_score"] >= 0.3:
        assert body.get("auto_purchased") is True
        assert "purchase_result" in body
        assert body["purchase_result"]["listing_id"] == listing.id


# ---------------------------------------------------------------------------
# 17. test_automatch_auto_buy_score_below_threshold
# ---------------------------------------------------------------------------

@patch(CDN_PATCH, new_callable=AsyncMock)
async def test_automatch_auto_buy_score_below_threshold(
    mock_cdn, client, make_agent, make_listing, make_token_account,
):
    """auto_buy does NOT fire if the top match_score < 0.3."""
    mock_cdn.return_value = SAMPLE_CONTENT
    await _seed_platform()

    seller, _ = await make_agent(name="seller-lowscore")
    await make_token_account(seller.id, balance=0)
    # Title has zero keyword overlap with description; quality is low
    await make_listing(
        seller.id, title="JavaScript React guide",
        price_usdc=0.001, quality_score=0.1,
    )

    buyer, buyer_jwt = await make_agent(name="buyer-lowscore")
    await make_token_account(buyer.id, balance=50000)

    resp = await client.post(URL, json={
        "description": "quantum physics deep learning",
        "auto_buy": True,
        "auto_buy_max_price": 1.0,
    }, headers=_auth(buyer_jwt))

    assert resp.status_code == 200
    body = resp.json()
    # Score should be below 0.3 with zero keyword overlap and low quality
    if body["matches"] and body["matches"][0]["match_score"] < 0.3:
        assert body.get("auto_purchased") is not True


# ---------------------------------------------------------------------------
# 18. test_automatch_auto_buy_price_above_max
# ---------------------------------------------------------------------------

@patch(CDN_PATCH, new_callable=AsyncMock)
async def test_automatch_auto_buy_price_above_max(
    mock_cdn, client, make_agent, make_listing, make_token_account,
):
    """auto_buy does NOT fire if the top match price > auto_buy_max_price."""
    mock_cdn.return_value = SAMPLE_CONTENT
    await _seed_platform()

    seller, _ = await make_agent(name="seller-expensiveab")
    await make_token_account(seller.id, balance=0)
    await make_listing(
        seller.id, title="Python tutorial guide",
        price_usdc=0.05, quality_score=0.9,
    )

    buyer, buyer_jwt = await make_agent(name="buyer-expensiveab")
    await make_token_account(buyer.id, balance=50000)

    resp = await client.post(URL, json={
        "description": "python tutorial guide",
        "auto_buy": True,
        "auto_buy_max_price": 0.001,  # way below listing price
        "max_price": 0.1,  # allow listing through price filter
    }, headers=_auth(buyer_jwt))

    assert resp.status_code == 200
    body = resp.json()
    assert len(body["matches"]) >= 1
    # Price is above auto_buy_max_price so no purchase
    assert body.get("auto_purchased") is not True


# ---------------------------------------------------------------------------
# 19. test_automatch_response_schema
# ---------------------------------------------------------------------------

async def test_automatch_response_schema(client, make_agent, make_listing):
    """Verify all expected fields are present in the response."""
    seller, _ = await make_agent(name="seller-schema")
    await make_listing(seller.id, title="Python tutorial", price_usdc=0.005)

    buyer, buyer_jwt = await make_agent(name="buyer-schema")

    resp = await client.post(URL, json={
        "description": "python tutorial",
    }, headers=_auth(buyer_jwt))

    assert resp.status_code == 200
    body = resp.json()

    # Top-level response fields
    assert "query" in body
    assert "category_filter" in body
    assert "routing_strategy" in body
    assert "matches" in body
    assert "total_candidates" in body

    assert isinstance(body["matches"], list)
    assert isinstance(body["total_candidates"], int)

    # Per-match fields
    if body["matches"]:
        match = body["matches"][0]
        expected_keys = {
            "listing_id", "title", "category", "price_usdc",
            "quality_score", "match_score", "estimated_fresh_cost",
            "savings_usdc", "savings_percent", "seller_id",
        }
        assert expected_keys.issubset(set(match.keys()))

        # Type checks
        assert isinstance(match["listing_id"], str)
        assert isinstance(match["title"], str)
        assert isinstance(match["price_usdc"], (int, float))
        assert isinstance(match["match_score"], (int, float))
        assert 0 <= match["match_score"] <= 1.0


# ---------------------------------------------------------------------------
# 20. test_automatch_quality_score_affects_ranking
# ---------------------------------------------------------------------------

async def test_automatch_quality_score_affects_ranking(client, make_agent, make_listing):
    """Higher quality score leads to a higher match_score for identical titles."""
    seller, _ = await make_agent(name="seller-quality")
    await make_listing(
        seller.id, title="Python tutorial", quality_score=0.95, price_usdc=0.005,
    )
    await make_listing(
        seller.id, title="Python tutorial", quality_score=0.2, price_usdc=0.005,
    )

    buyer, buyer_jwt = await make_agent(name="buyer-quality")

    resp = await client.post(URL, json={
        "description": "python tutorial",
    }, headers=_auth(buyer_jwt))

    assert resp.status_code == 200
    matches = resp.json()["matches"]
    assert len(matches) == 2
    # Higher quality listing should rank first
    assert matches[0]["quality_score"] > matches[1]["quality_score"]
    assert matches[0]["match_score"] >= matches[1]["match_score"]


# ---------------------------------------------------------------------------
# 21. test_automatch_keyword_overlap
# ---------------------------------------------------------------------------

async def test_automatch_keyword_overlap(client, make_agent, make_listing):
    """Listing with higher keyword overlap in title scores higher."""
    seller, _ = await make_agent(name="seller-kw")
    # This title has 3 overlapping keywords with the query
    await make_listing(
        seller.id, title="Python web scraping tutorial",
        quality_score=0.5, price_usdc=0.005,
    )
    # This title has 0 overlapping keywords
    await make_listing(
        seller.id, title="JavaScript React guide",
        quality_score=0.5, price_usdc=0.005,
    )

    buyer, buyer_jwt = await make_agent(name="buyer-kw")

    resp = await client.post(URL, json={
        "description": "python scraping tutorial",
    }, headers=_auth(buyer_jwt))

    assert resp.status_code == 200
    matches = resp.json()["matches"]
    assert len(matches) == 2
    # First match should have higher score due to keyword overlap
    assert matches[0]["match_score"] > matches[1]["match_score"]
    assert "python" in matches[0]["title"].lower() or "scraping" in matches[0]["title"].lower()


# ---------------------------------------------------------------------------
# 22. test_automatch_multiple_categories
# ---------------------------------------------------------------------------

async def test_automatch_multiple_categories(client, make_agent, make_listing):
    """Listings in multiple categories, filter narrows correctly."""
    seller, _ = await make_agent(name="seller-multicat")
    await make_listing(seller.id, title="Python data analysis", category="web_search")
    await make_listing(seller.id, title="Python code review", category="code_analysis")
    await make_listing(seller.id, title="Python summary", category="document_summary")

    buyer, buyer_jwt = await make_agent(name="buyer-multicat")

    # Without filter: all categories returned
    resp_all = await client.post(URL, json={
        "description": "python",
    }, headers=_auth(buyer_jwt))
    assert resp_all.status_code == 200
    all_categories = {m["category"] for m in resp_all.json()["matches"]}
    assert len(all_categories) >= 2

    # With filter: only code_analysis
    resp_filtered = await client.post(URL, json={
        "description": "python",
        "category": "code_analysis",
    }, headers=_auth(buyer_jwt))
    assert resp_filtered.status_code == 200
    for m in resp_filtered.json()["matches"]:
        assert m["category"] == "code_analysis"


# ---------------------------------------------------------------------------
# 23. test_automatch_with_inactive_listings
# ---------------------------------------------------------------------------

async def test_automatch_with_inactive_listings(client, make_agent, make_listing):
    """Inactive listings are excluded from results."""
    seller, _ = await make_agent(name="seller-inactive")
    active = await make_listing(
        seller.id, title="Active Python tutorial",
        status="active", price_usdc=0.005,
    )
    inactive = await make_listing(
        seller.id, title="Inactive Python tutorial",
        status="inactive", price_usdc=0.005,
    )

    buyer, buyer_jwt = await make_agent(name="buyer-inactive")

    resp = await client.post(URL, json={
        "description": "python tutorial",
    }, headers=_auth(buyer_jwt))

    assert resp.status_code == 200
    matches = resp.json()["matches"]
    listing_ids = [m["listing_id"] for m in matches]
    assert inactive.id not in listing_ids
    assert active.id in listing_ids


# ---------------------------------------------------------------------------
# 24. test_automatch_auto_buy_max_price_override
# ---------------------------------------------------------------------------

@patch(CDN_PATCH, new_callable=AsyncMock)
async def test_automatch_auto_buy_max_price_override(
    mock_cdn, client, make_agent, make_listing, make_token_account,
):
    """auto_buy_max_price overrides max_price for auto-buy threshold."""
    mock_cdn.return_value = SAMPLE_CONTENT
    await _seed_platform()

    seller, _ = await make_agent(name="seller-override")
    await make_token_account(seller.id, balance=0)
    listing = await make_listing(
        seller.id, title="Python tutorial guide",
        price_usdc=0.008, quality_score=0.9,
    )

    buyer, buyer_jwt = await make_agent(name="buyer-override")
    await make_token_account(buyer.id, balance=50000)

    # max_price=0.01 allows listing through filter
    # auto_buy_max_price=0.005 is BELOW listing price -> no auto buy
    resp = await client.post(URL, json={
        "description": "python tutorial guide",
        "auto_buy": True,
        "max_price": 0.01,
        "auto_buy_max_price": 0.005,
    }, headers=_auth(buyer_jwt))

    assert resp.status_code == 200
    body = resp.json()
    assert len(body["matches"]) >= 1
    # Price 0.008 > auto_buy_max_price 0.005 so no purchase
    assert body.get("auto_purchased") is not True

    # Now set auto_buy_max_price high enough
    resp2 = await client.post(URL, json={
        "description": "python tutorial guide",
        "auto_buy": True,
        "max_price": 0.01,
        "auto_buy_max_price": 0.01,
    }, headers=_auth(buyer_jwt))

    assert resp2.status_code == 200
    body2 = resp2.json()
    if body2["matches"] and body2["matches"][0]["match_score"] >= 0.3:
        assert body2.get("auto_purchased") is True


# ---------------------------------------------------------------------------
# 25. test_automatch_routing_strategy_ignored_when_no_matches
# ---------------------------------------------------------------------------

async def test_automatch_routing_strategy_ignored_when_no_matches(client, make_agent):
    """Routing strategy set with no matches does not cause an error."""
    buyer, buyer_jwt = await make_agent(name="buyer-no-strat")

    resp = await client.post(URL, json={
        "description": "nonexistent data topic",
        "routing_strategy": "cheapest",
        "buyer_region": "us-east",
    }, headers=_auth(buyer_jwt))

    assert resp.status_code == 200
    body = resp.json()
    assert body["matches"] == []
    assert body["routing_strategy"] == "cheapest"
