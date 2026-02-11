"""Comprehensive tests for the A2A auto-match service.

Tests the keyword matching, quality scoring, freshness scoring, category filtering,
price filtering, specialization bonuses, and savings calculations.
"""

import pytest
from datetime import datetime, timezone, timedelta
from decimal import Decimal

from marketplace.services.match_service import auto_match, _compute_match_score
from marketplace.models.listing import DataListing
from marketplace.models.agent_stats import AgentStats


# ---------------------------------------------------------------------------
# Basic matching tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_auto_match_basic_keyword_overlap(db, make_agent, make_listing):
    """Test that listings with keyword overlap score higher."""
    seller, _ = await make_agent(name="seller1")

    # Create listings with varying keyword overlap
    await make_listing(
        seller.id,
        title="Python web scraping tutorial",
        description="Learn to scrape websites with Python",
        category="web_search",
        price_usdc=0.005,
        quality_score=0.8,
    )
    await make_listing(
        seller.id,
        title="JavaScript guide",
        description="Frontend development with JS",
        category="web_search",
        price_usdc=0.005,
        quality_score=0.8,
    )

    result = await auto_match(db, "python scraping tutorial")

    assert len(result["matches"]) == 2
    # First match should have higher score (more keyword overlap)
    assert "python" in result["matches"][0]["title"].lower()
    assert result["matches"][0]["match_score"] > result["matches"][1]["match_score"]


@pytest.mark.asyncio
async def test_auto_match_quality_score_affects_ranking(db, make_agent, make_listing):
    """Test that higher quality scores result in better match scores."""
    seller, _ = await make_agent(name="seller1")

    # Same keywords, different quality
    await make_listing(
        seller.id,
        title="Python tutorial",
        description="Learn Python basics",
        category="web_search",
        price_usdc=0.005,
        quality_score=0.9,
    )
    await make_listing(
        seller.id,
        title="Python tutorial",
        description="Learn Python basics",
        category="web_search",
        price_usdc=0.005,
        quality_score=0.3,
    )

    result = await auto_match(db, "python tutorial")

    assert len(result["matches"]) == 2
    # Higher quality should rank first
    assert result["matches"][0]["quality_score"] == 0.9
    assert result["matches"][1]["quality_score"] == 0.3
    assert result["matches"][0]["match_score"] > result["matches"][1]["match_score"]


@pytest.mark.asyncio
async def test_auto_match_freshness_affects_ranking(db, make_agent, make_listing):
    """Test that fresher listings score higher."""
    seller, _ = await make_agent(name="seller1")

    # Create a fresh listing
    fresh = await make_listing(
        seller.id,
        title="Python tutorial",
        description="Learn Python basics",
        category="web_search",
        price_usdc=0.005,
        quality_score=0.8,
    )
    fresh.freshness_at = datetime.now(timezone.utc)

    # Create an old listing (25 hours old - beyond 24h freshness window)
    old = await make_listing(
        seller.id,
        title="Python tutorial",
        description="Learn Python basics",
        category="web_search",
        price_usdc=0.005,
        quality_score=0.8,
    )
    old.freshness_at = datetime.now(timezone.utc) - timedelta(hours=25)

    await db.commit()

    result = await auto_match(db, "python tutorial")

    assert len(result["matches"]) == 2
    # Fresh listing should rank higher
    assert result["matches"][0]["match_score"] > result["matches"][1]["match_score"]


@pytest.mark.asyncio
async def test_auto_match_category_filter(db, make_agent, make_listing):
    """Test that category filter excludes non-matching listings."""
    seller, _ = await make_agent(name="seller1")

    await make_listing(
        seller.id,
        title="Web search results",
        description="Python tutorial search",
        category="web_search",
        price_usdc=0.005,
    )
    await make_listing(
        seller.id,
        title="Code analysis",
        description="Python code review",
        category="code_analysis",
        price_usdc=0.005,
    )

    result = await auto_match(db, "python tutorial", category="web_search")

    assert len(result["matches"]) == 1
    assert result["matches"][0]["category"] == "web_search"
    assert result["category_filter"] == "web_search"


@pytest.mark.asyncio
async def test_auto_match_max_price_filter(db, make_agent, make_listing):
    """Test that max_price filter excludes expensive listings."""
    seller, _ = await make_agent(name="seller1")

    await make_listing(
        seller.id,
        title="Cheap Python tutorial",
        description="Basic Python guide",
        category="web_search",
        price_usdc=0.003,
    )
    await make_listing(
        seller.id,
        title="Premium Python tutorial",
        description="Advanced Python guide",
        category="web_search",
        price_usdc=0.015,
    )

    result = await auto_match(db, "python tutorial", max_price=0.01)

    assert len(result["matches"]) == 1
    assert result["matches"][0]["price_usdc"] <= 0.01


@pytest.mark.asyncio
async def test_auto_match_excludes_buyer_own_listings(db, make_agent, make_listing):
    """Test that buyer's own listings are excluded from results."""
    buyer, _ = await make_agent(name="buyer1")
    seller, _ = await make_agent(name="seller1")

    # Buyer's own listing
    await make_listing(
        buyer.id,
        title="My Python tutorial",
        description="Python guide I created",
        category="web_search",
        price_usdc=0.005,
    )
    # Another seller's listing
    await make_listing(
        seller.id,
        title="Python tutorial",
        description="Python guide for sale",
        category="web_search",
        price_usdc=0.005,
    )

    result = await auto_match(db, "python tutorial", buyer_id=buyer.id)

    assert len(result["matches"]) == 1
    assert result["matches"][0]["seller_id"] == seller.id


@pytest.mark.asyncio
async def test_auto_match_specialization_bonus(db, make_agent, make_listing):
    """Test that sellers with matching specialization get a bonus."""
    seller1, _ = await make_agent(name="seller1")
    seller2, _ = await make_agent(name="seller2")

    # Give seller1 a specialization in web_search
    stats1 = AgentStats(
        agent_id=seller1.id,
        primary_specialization="web_search",
    )
    db.add(stats1)
    await db.commit()

    # Create identical listings
    await make_listing(
        seller1.id,
        title="Python tutorial",
        description="Learn Python",
        category="web_search",
        price_usdc=0.005,
        quality_score=0.8,
    )
    await make_listing(
        seller2.id,
        title="Python tutorial",
        description="Learn Python",
        category="web_search",
        price_usdc=0.005,
        quality_score=0.8,
    )

    result = await auto_match(db, "python tutorial", category="web_search")

    assert len(result["matches"]) == 2
    # Seller with specialization should rank higher (gets +0.1 bonus)
    assert result["matches"][0]["seller_id"] == seller1.id
    assert result["matches"][0]["match_score"] > result["matches"][1]["match_score"]


@pytest.mark.asyncio
async def test_auto_match_savings_calculation(db, make_agent, make_listing):
    """Test that savings are calculated correctly."""
    seller, _ = await make_agent(name="seller1")

    # web_search fresh cost is $0.01, listing at $0.005
    await make_listing(
        seller.id,
        title="Web search results",
        description="Python tutorial search",
        category="web_search",
        price_usdc=0.005,
    )

    result = await auto_match(db, "python tutorial")

    assert len(result["matches"]) == 1
    match = result["matches"][0]

    assert match["estimated_fresh_cost"] == 0.01
    assert match["price_usdc"] == 0.005
    assert match["savings_usdc"] == 0.005  # 0.01 - 0.005
    assert match["savings_percent"] == 50.0  # (0.005 / 0.01) * 100


@pytest.mark.asyncio
async def test_auto_match_top_5_limit(db, make_agent, make_listing):
    """Test that only top 5 matches are returned."""
    seller, _ = await make_agent(name="seller1")

    # Create 10 listings
    for i in range(10):
        await make_listing(
            seller.id,
            title=f"Python tutorial {i}",
            description="Learn Python basics",
            category="web_search",
            price_usdc=0.005,
            quality_score=0.5 + (i * 0.05),  # Varying quality
        )

    result = await auto_match(db, "python tutorial")

    assert len(result["matches"]) == 5
    assert result["total_candidates"] == 10
    # Verify they're sorted by score descending
    scores = [m["match_score"] for m in result["matches"]]
    assert scores == sorted(scores, reverse=True)


# ---------------------------------------------------------------------------
# Edge case tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_auto_match_empty_listings(db):
    """Test auto_match with no listings in database."""
    result = await auto_match(db, "python tutorial")

    assert result["matches"] == []
    assert result["total_candidates"] == 0
    assert result["query"] == "python tutorial"


@pytest.mark.asyncio
async def test_auto_match_no_keyword_overlap(db, make_agent, make_listing):
    """Test matching when there's no keyword overlap."""
    seller, _ = await make_agent(name="seller1")

    await make_listing(
        seller.id,
        title="JavaScript React tutorial",
        description="Learn React framework",
        category="web_search",
        price_usdc=0.005,
        quality_score=0.8,
    )

    result = await auto_match(db, "python django database")

    # Should still return the listing, but with lower text score (only quality + freshness)
    assert len(result["matches"]) == 1
    # Score should be low since no keyword overlap (only quality 0.3 * 0.8 + freshness)
    assert result["matches"][0]["match_score"] < 0.5


@pytest.mark.asyncio
async def test_auto_match_zero_keywords(db, make_agent, make_listing):
    """Test matching with empty or whitespace-only query."""
    seller, _ = await make_agent(name="seller1")

    await make_listing(
        seller.id,
        title="Python tutorial",
        description="Learn Python",
        category="web_search",
        price_usdc=0.005,
        quality_score=0.8,
    )

    result = await auto_match(db, "   ")

    # Should return listings but with zero text score
    assert len(result["matches"]) == 1
    # Score based only on quality and freshness (no keyword overlap)
    assert result["matches"][0]["match_score"] <= 0.5


@pytest.mark.asyncio
async def test_auto_match_inactive_listings_excluded(db, make_agent, make_listing):
    """Test that inactive listings are not returned."""
    seller, _ = await make_agent(name="seller1")

    await make_listing(
        seller.id,
        title="Active Python tutorial",
        description="Learn Python",
        category="web_search",
        price_usdc=0.005,
        status="active",
    )
    inactive = await make_listing(
        seller.id,
        title="Inactive Python tutorial",
        description="Learn Python",
        category="web_search",
        price_usdc=0.005,
        status="inactive",
    )

    result = await auto_match(db, "python tutorial")

    assert len(result["matches"]) == 1
    assert result["matches"][0]["listing_id"] != inactive.id


@pytest.mark.asyncio
async def test_auto_match_old_listing_zero_freshness(db, make_agent, make_listing):
    """Test that listings older than 24 hours get zero freshness score."""
    seller, _ = await make_agent(name="seller1")

    old_listing = await make_listing(
        seller.id,
        title="Python tutorial",
        description="Learn Python",
        category="web_search",
        price_usdc=0.005,
        quality_score=0.5,
    )
    # Set to 30 hours old
    old_listing.freshness_at = datetime.now(timezone.utc) - timedelta(hours=30)
    await db.commit()

    result = await auto_match(db, "python tutorial")

    assert len(result["matches"]) == 1
    # Score should be text + quality only (no freshness)
    # Max possible: 0.5 (full keyword overlap) + 0.3 * 0.5 (quality) = 0.65
    assert result["matches"][0]["match_score"] <= 0.65


@pytest.mark.asyncio
async def test_auto_match_full_keyword_overlap(db, make_agent, make_listing):
    """Test maximum possible text score with 100% keyword overlap."""
    seller, _ = await make_agent(name="seller1")

    listing = await make_listing(
        seller.id,
        title="python tutorial",
        description="python tutorial guide",
        category="web_search",
        price_usdc=0.005,
        quality_score=1.0,
    )
    listing.freshness_at = datetime.now(timezone.utc)
    await db.commit()

    result = await auto_match(db, "python tutorial")

    assert len(result["matches"]) == 1
    # Perfect score: 0.5 (text) + 0.3 (quality) + 0.2 (freshness) = 1.0
    assert result["matches"][0]["match_score"] >= 0.95


@pytest.mark.asyncio
async def test_auto_match_tags_contribute_to_score(db, make_agent, make_listing):
    """Test that tags are included in keyword matching."""
    seller, _ = await make_agent(name="seller1")

    listing = await make_listing(
        seller.id,
        title="Tutorial",
        description="Programming guide",
        category="web_search",
        price_usdc=0.005,
    )
    # Manually set tags
    listing.tags = '["python", "beginner", "tutorial"]'
    await db.commit()

    result = await auto_match(db, "python beginner")

    assert len(result["matches"]) == 1
    # Should have keyword overlap from tags
    assert result["matches"][0]["match_score"] > 0.3  # More than just quality


@pytest.mark.asyncio
async def test_compute_match_score_no_freshness_field(db, make_agent, make_listing):
    """Test _compute_match_score when freshness_at is None."""
    seller, _ = await make_agent(name="seller1")

    listing = await make_listing(
        seller.id,
        title="Python tutorial",
        description="Learn Python",
        category="web_search",
        price_usdc=0.005,
        quality_score=0.5,
    )
    # Don't commit after setting to None - just test the function directly
    # Create a temporary listing object with freshness_at = None for scoring
    from marketplace.models.listing import DataListing
    temp_listing = DataListing(
        title="Python tutorial",
        description="Learn Python",
        quality_score=Decimal("0.5"),
        freshness_at=None,
        tags="[]",
    )

    keywords = {"python", "tutorial"}
    score = _compute_match_score(temp_listing, keywords)

    # Should calculate without freshness component (max 0.8)
    assert score <= 0.8


@pytest.mark.asyncio
async def test_auto_match_multiple_filters_combined(db, make_agent, make_listing):
    """Test that category and max_price filters work together."""
    seller, _ = await make_agent(name="seller1")

    await make_listing(
        seller.id,
        title="Web search Python",
        description="Python search results",
        category="web_search",
        price_usdc=0.005,
    )
    await make_listing(
        seller.id,
        title="Code analysis Python",
        description="Python code review",
        category="code_analysis",
        price_usdc=0.005,
    )
    await make_listing(
        seller.id,
        title="Web search expensive",
        description="Premium search results",
        category="web_search",
        price_usdc=0.02,
    )

    result = await auto_match(
        db,
        "python",
        category="web_search",
        max_price=0.01,
    )

    # Should only return the web_search listing under $0.01
    assert len(result["matches"]) == 1
    assert result["matches"][0]["category"] == "web_search"
    assert result["matches"][0]["price_usdc"] <= 0.01


@pytest.mark.asyncio
async def test_auto_match_specialization_case_insensitive(db, make_agent, make_listing):
    """Test that specialization bonus is case-insensitive."""
    seller, _ = await make_agent(name="seller1")

    stats = AgentStats(
        agent_id=seller.id,
        primary_specialization="WEB_SEARCH",  # Uppercase
    )
    db.add(stats)
    await db.commit()

    await make_listing(
        seller.id,
        title="Python tutorial",
        description="Learn Python",
        category="web_search",  # Lowercase
        price_usdc=0.005,
        quality_score=0.5,
    )

    result = await auto_match(db, "python", category="web_search")

    assert len(result["matches"]) == 1
    # Should get specialization bonus despite case mismatch
    # Base score would be ~0.5, with bonus should be higher
    assert result["matches"][0]["match_score"] > 0.5


@pytest.mark.asyncio
async def test_auto_match_score_capped_at_one(db, make_agent, make_listing):
    """Test that match scores are capped at 1.0 even with specialization bonus."""
    seller, _ = await make_agent(name="seller1")

    stats = AgentStats(
        agent_id=seller.id,
        primary_specialization="web_search",
    )
    db.add(stats)
    await db.commit()

    listing = await make_listing(
        seller.id,
        title="python tutorial python guide",
        description="python programming python basics",
        category="web_search",
        price_usdc=0.005,
        quality_score=1.0,
    )
    listing.freshness_at = datetime.now(timezone.utc)
    await db.commit()

    result = await auto_match(db, "python tutorial", category="web_search")

    assert len(result["matches"]) == 1
    # Even with perfect score + specialization bonus, should cap at 1.0
    assert result["matches"][0]["match_score"] <= 1.0


@pytest.mark.asyncio
async def test_auto_match_negative_savings_zeroed(db, make_agent, make_listing):
    """Test that negative savings (when listing costs more than fresh) is shown as 0."""
    seller, _ = await make_agent(name="seller1")

    # Create listing more expensive than estimated fresh cost
    await make_listing(
        seller.id,
        title="Expensive web search",
        description="Premium data",
        category="web_search",  # Fresh cost $0.01
        price_usdc=0.02,  # More expensive than fresh
    )

    result = await auto_match(db, "web search", max_price=0.05)

    assert len(result["matches"]) == 1
    match = result["matches"][0]

    # Savings should be 0 (not negative) - the code uses max(0, fresh_cost - price)
    assert match["savings_usdc"] == 0
    # Savings percent will also be 0 since savings_usdc is 0
    assert match["savings_percent"] == 0.0
