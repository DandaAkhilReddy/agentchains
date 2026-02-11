"""Comprehensive tests for the analytics service."""

import pytest
from decimal import Decimal
from datetime import datetime, timedelta, timezone

from marketplace.services.analytics_service import (
    get_earnings_breakdown,
    get_agent_stats,
    get_multi_leaderboard,
)


# =============================================================================
# get_earnings_breakdown() Tests
# =============================================================================


@pytest.mark.asyncio
async def test_earnings_breakdown_seller_only(
    db, make_agent, make_listing, make_transaction
):
    """Test earnings breakdown for an agent with only seller transactions."""
    seller, _ = await make_agent(name="seller-agent")

    # Create listings
    listing1 = await make_listing(
        seller.id, price_usdc=10.0, category="web_search", content_size=1000
    )
    listing2 = await make_listing(
        seller.id, price_usdc=5.0, category="ml_models", content_size=2000
    )

    # Create buyer and transactions
    buyer, _ = await make_agent(name="buyer-agent")
    await make_transaction(
        buyer.id, seller.id, listing1.id, amount_usdc=10.0, status="completed"
    )
    await make_transaction(
        buyer.id, seller.id, listing2.id, amount_usdc=5.0, status="completed"
    )

    result = await get_earnings_breakdown(db, seller.id)

    assert result["agent_id"] == seller.id
    assert result["total_earned_usdc"] == 15.0
    assert result["total_spent_usdc"] == 0.0
    assert result["net_revenue_usdc"] == 15.0
    assert result["earnings_by_category"]["web_search"] == 10.0
    assert result["earnings_by_category"]["ml_models"] == 5.0
    assert len(result["earnings_timeline"]) > 0


@pytest.mark.asyncio
async def test_earnings_breakdown_buyer_only(
    db, make_agent, make_listing, make_transaction
):
    """Test earnings breakdown for an agent with only buyer transactions."""
    seller, _ = await make_agent(name="seller-agent")
    buyer, _ = await make_agent(name="buyer-agent")

    # Create listings
    listing1 = await make_listing(seller.id, price_usdc=8.0, category="web_search")
    listing2 = await make_listing(seller.id, price_usdc=12.0, category="ml_models")

    # Create transactions as buyer
    await make_transaction(
        buyer.id, seller.id, listing1.id, amount_usdc=8.0, status="completed"
    )
    await make_transaction(
        buyer.id, seller.id, listing2.id, amount_usdc=12.0, status="completed"
    )

    result = await get_earnings_breakdown(db, buyer.id)

    assert result["agent_id"] == buyer.id
    assert result["total_earned_usdc"] == 0.0
    assert result["total_spent_usdc"] == 20.0
    assert result["net_revenue_usdc"] == -20.0
    assert result["earnings_by_category"] == {}
    assert len(result["earnings_timeline"]) > 0
    # Timeline should only have 'spent' data
    for entry in result["earnings_timeline"]:
        assert entry["earned"] == 0.0
        assert entry["spent"] > 0.0


@pytest.mark.asyncio
async def test_earnings_breakdown_mixed_transactions(
    db, make_agent, make_listing, make_transaction
):
    """Test earnings breakdown for an agent that both sells and buys."""
    agent1, _ = await make_agent(name="agent-1")
    agent2, _ = await make_agent(name="agent-2")

    # Agent1 sells to agent2
    listing1 = await make_listing(agent1.id, price_usdc=20.0, category="web_search")
    await make_transaction(
        agent2.id, agent1.id, listing1.id, amount_usdc=20.0, status="completed"
    )

    # Agent1 buys from agent2
    listing2 = await make_listing(agent2.id, price_usdc=7.0, category="ml_models")
    await make_transaction(
        agent1.id, agent2.id, listing2.id, amount_usdc=7.0, status="completed"
    )

    result = await get_earnings_breakdown(db, agent1.id)

    assert result["agent_id"] == agent1.id
    assert result["total_earned_usdc"] == 20.0
    assert result["total_spent_usdc"] == 7.0
    assert result["net_revenue_usdc"] == 13.0
    assert result["earnings_by_category"]["web_search"] == 20.0


@pytest.mark.asyncio
async def test_earnings_breakdown_by_category(
    db, make_agent, make_listing, make_transaction
):
    """Test that earnings are correctly grouped by category."""
    seller, _ = await make_agent(name="seller-agent")
    buyer, _ = await make_agent(name="buyer-agent")

    # Create listings in different categories
    listing1 = await make_listing(
        seller.id, price_usdc=10.0, category="web_search"
    )
    listing2 = await make_listing(
        seller.id, price_usdc=15.0, category="web_search"
    )
    listing3 = await make_listing(
        seller.id, price_usdc=8.0, category="ml_models"
    )
    listing4 = await make_listing(
        seller.id, price_usdc=5.0, category="datasets"
    )

    # Create transactions
    await make_transaction(
        buyer.id, seller.id, listing1.id, amount_usdc=10.0, status="completed"
    )
    await make_transaction(
        buyer.id, seller.id, listing2.id, amount_usdc=15.0, status="completed"
    )
    await make_transaction(
        buyer.id, seller.id, listing3.id, amount_usdc=8.0, status="completed"
    )
    await make_transaction(
        buyer.id, seller.id, listing4.id, amount_usdc=5.0, status="completed"
    )

    result = await get_earnings_breakdown(db, seller.id)

    assert result["earnings_by_category"]["web_search"] == 25.0
    assert result["earnings_by_category"]["ml_models"] == 8.0
    assert result["earnings_by_category"]["datasets"] == 5.0


@pytest.mark.asyncio
async def test_earnings_breakdown_timeline(
    db, make_agent, make_listing, make_transaction
):
    """Test that timeline correctly groups transactions by date."""
    seller, _ = await make_agent(name="seller-agent")
    buyer, _ = await make_agent(name="buyer-agent")

    listing = await make_listing(seller.id, price_usdc=10.0)

    # Create multiple transactions (they'll have the same date in this test)
    await make_transaction(
        buyer.id, seller.id, listing.id, amount_usdc=10.0, status="completed"
    )
    await make_transaction(
        buyer.id, seller.id, listing.id, amount_usdc=5.0, status="completed"
    )

    result = await get_earnings_breakdown(db, seller.id)

    assert len(result["earnings_timeline"]) > 0
    # Timeline should be sorted by date
    dates = [entry["date"] for entry in result["earnings_timeline"]]
    assert dates == sorted(dates)
    # Should have aggregated earnings for the same day
    total_timeline_earned = sum(
        entry["earned"] for entry in result["earnings_timeline"]
    )
    assert total_timeline_earned == 15.0


@pytest.mark.asyncio
async def test_earnings_breakdown_empty_state(db, make_agent):
    """Test earnings breakdown for an agent with no transactions."""
    agent, _ = await make_agent(name="empty-agent")

    result = await get_earnings_breakdown(db, agent.id)

    assert result["agent_id"] == agent.id
    assert result["total_earned_usdc"] == 0.0
    assert result["total_spent_usdc"] == 0.0
    assert result["net_revenue_usdc"] == 0.0
    assert result["earnings_by_category"] == {}
    assert result["earnings_timeline"] == []


@pytest.mark.asyncio
async def test_earnings_breakdown_only_counts_completed(
    db, make_agent, make_listing, make_transaction
):
    """Test that only completed transactions are counted."""
    seller, _ = await make_agent(name="seller-agent")
    buyer, _ = await make_agent(name="buyer-agent")

    listing = await make_listing(seller.id, price_usdc=10.0)

    # Create completed transaction
    await make_transaction(
        buyer.id, seller.id, listing.id, amount_usdc=10.0, status="completed"
    )

    # Create pending transaction (should be ignored)
    await make_transaction(
        buyer.id, seller.id, listing.id, amount_usdc=50.0, status="pending"
    )

    result = await get_earnings_breakdown(db, seller.id)

    # Only the completed transaction should count
    assert result["total_earned_usdc"] == 10.0


# =============================================================================
# get_agent_stats() Tests
# =============================================================================


@pytest.mark.asyncio
async def test_agent_stats_creation(db, make_agent):
    """Test that agent stats are created if they don't exist."""
    agent, _ = await make_agent(name="new-agent")

    stats = await get_agent_stats(db, agent.id)

    assert stats.agent_id == agent.id
    assert stats.total_listings_created == 0
    assert stats.total_data_bytes_contributed == 0
    assert stats.avg_listing_quality == 0.5  # default when no listings
    assert stats.category_count == 0
    assert stats.primary_specialization is None


@pytest.mark.asyncio
async def test_agent_stats_recalculation(
    db, make_agent, make_listing, make_transaction
):
    """Test that agent stats are recalculated from live data."""
    seller, _ = await make_agent(name="seller-agent")
    buyer, _ = await make_agent(name="buyer-agent")

    # Create listings with different sizes and quality scores
    listing1 = await make_listing(
        seller.id, price_usdc=10.0, content_size=1000, quality_score=0.9
    )
    listing2 = await make_listing(
        seller.id, price_usdc=5.0, content_size=2000, quality_score=0.7
    )

    # Create transaction
    await make_transaction(
        buyer.id, seller.id, listing1.id, amount_usdc=10.0, status="completed"
    )

    stats = await get_agent_stats(db, seller.id)

    assert stats.total_listings_created == 2
    assert stats.total_data_bytes_contributed == 3000
    assert float(stats.avg_listing_quality) == 0.8  # average of 0.9 and 0.7
    assert float(stats.total_earned_usdc) == 10.0


@pytest.mark.asyncio
async def test_agent_stats_categories(db, make_agent, make_listing):
    """Test that categories are correctly tracked."""
    agent, _ = await make_agent(name="agent")

    # Create listings in multiple categories
    await make_listing(agent.id, category="web_search")
    await make_listing(agent.id, category="ml_models")
    await make_listing(agent.id, category="web_search")  # duplicate category
    await make_listing(agent.id, category="datasets")

    stats = await get_agent_stats(db, agent.id)

    assert stats.category_count == 3
    # Primary specialization should be the first category
    assert stats.primary_specialization in ["web_search", "ml_models", "datasets"]

    # Check that categories_json contains all unique categories
    import json
    categories = json.loads(stats.categories_json)
    assert len(categories) == 3
    assert set(categories) == {"web_search", "ml_models", "datasets"}


@pytest.mark.asyncio
async def test_agent_stats_unique_buyers(
    db, make_agent, make_listing, make_transaction
):
    """Test that unique buyers served is correctly calculated."""
    seller, _ = await make_agent(name="seller-agent")
    buyer1, _ = await make_agent(name="buyer-1")
    buyer2, _ = await make_agent(name="buyer-2")
    buyer3, _ = await make_agent(name="buyer-3")

    listing = await make_listing(seller.id, price_usdc=10.0)

    # Multiple transactions from same buyers
    await make_transaction(
        buyer1.id, seller.id, listing.id, amount_usdc=10.0, status="completed"
    )
    await make_transaction(
        buyer1.id, seller.id, listing.id, amount_usdc=5.0, status="completed"
    )
    await make_transaction(
        buyer2.id, seller.id, listing.id, amount_usdc=10.0, status="completed"
    )
    await make_transaction(
        buyer3.id, seller.id, listing.id, amount_usdc=10.0, status="completed"
    )

    stats = await get_agent_stats(db, seller.id)

    # Should count unique buyers, not total transactions
    assert stats.unique_buyers_served == 3


@pytest.mark.asyncio
async def test_agent_stats_helpfulness_formula(
    db, make_agent, make_listing, make_transaction
):
    """Test the helpfulness score calculation formula."""
    seller, _ = await make_agent(name="seller-agent")

    # Create listings to get some quality score
    listing1 = await make_listing(
        seller.id, price_usdc=1.0, quality_score=0.9, content_size=1000
    )
    listing2 = await make_listing(
        seller.id, price_usdc=1.0, quality_score=0.8, content_size=1000
    )

    # Create transactions with multiple buyers
    buyers = []
    for i in range(5):
        buyer, _ = await make_agent(name=f"buyer-{i}")
        buyers.append(buyer)
        await make_transaction(
            buyer.id, seller.id, listing1.id, amount_usdc=1.0, status="completed"
        )

    # Manually increase access count to test cache hits component
    listing1.access_count = 20
    db.add(listing1)
    await db.commit()

    stats = await get_agent_stats(db, seller.id)

    # Helpfulness formula:
    # 0.3 * min(unique_buyers / 10, 1.0)
    # + 0.3 * min(listings / 20, 1.0)
    # + 0.2 * avg_quality
    # + 0.2 * min(cache_hits / 50, 1.0)
    # capped at 1.0

    expected = min(
        0.3 * min(5 / 10, 1.0)  # 0.15
        + 0.3 * min(2 / 20, 1.0)  # 0.03
        + 0.2 * 0.85  # 0.17 (avg quality)
        + 0.2 * min(20 / 50, 1.0),  # 0.08
        1.0,
    )

    assert abs(float(stats.helpfulness_score) - expected) < 0.01


@pytest.mark.asyncio
async def test_agent_stats_spending_tracked(
    db, make_agent, make_listing, make_transaction
):
    """Test that spending as a buyer is tracked."""
    seller, _ = await make_agent(name="seller-agent")
    buyer, _ = await make_agent(name="buyer-agent")

    listing = await make_listing(seller.id, price_usdc=25.0)

    await make_transaction(
        buyer.id, seller.id, listing.id, amount_usdc=25.0, status="completed"
    )

    stats = await get_agent_stats(db, buyer.id)

    assert stats.total_spent_usdc == 25.0
    assert stats.total_earned_usdc == 0.0


# =============================================================================
# get_multi_leaderboard() Tests
# =============================================================================


@pytest.mark.asyncio
async def test_leaderboard_helpfulness(
    db, make_agent, make_listing, make_transaction
):
    """Test helpfulness leaderboard ranking."""
    # Create agents with different helpfulness scores
    agent1, _ = await make_agent(name="agent-1")
    agent2, _ = await make_agent(name="agent-2")
    agent3, _ = await make_agent(name="agent-3")

    # Agent1: high quality, many listings
    for i in range(10):
        await make_listing(agent1.id, quality_score=0.95, content_size=1000)

    # Agent2: medium quality, fewer listings
    for i in range(5):
        await make_listing(agent2.id, quality_score=0.7, content_size=500)

    # Agent3: low quality, few listings
    for i in range(2):
        await make_listing(agent3.id, quality_score=0.5, content_size=100)

    # Calculate stats for all agents
    await get_agent_stats(db, agent1.id)
    await get_agent_stats(db, agent2.id)
    await get_agent_stats(db, agent3.id)

    # Get leaderboard
    leaderboard = await get_multi_leaderboard(db, "helpfulness", limit=10)

    assert len(leaderboard) == 3
    # Agent1 should be ranked first
    assert leaderboard[0]["rank"] == 1
    assert leaderboard[0]["agent_id"] == agent1.id
    assert leaderboard[0]["agent_name"] == "agent-1"
    assert "primary_score" in leaderboard[0]
    assert "helpfulness_score" in leaderboard[0]
    # Helpfulness scores should be in descending order
    assert (
        leaderboard[0]["helpfulness_score"]
        >= leaderboard[1]["helpfulness_score"]
        >= leaderboard[2]["helpfulness_score"]
    )


@pytest.mark.asyncio
async def test_leaderboard_earnings(
    db, make_agent, make_listing, make_transaction
):
    """Test earnings leaderboard ranking."""
    # Create agents with different earnings
    agent1, _ = await make_agent(name="high-earner")
    agent2, _ = await make_agent(name="medium-earner")
    agent3, _ = await make_agent(name="low-earner")
    buyer, _ = await make_agent(name="buyer")

    # Agent1: high earnings
    listing1 = await make_listing(agent1.id, price_usdc=100.0)
    await make_transaction(
        buyer.id, agent1.id, listing1.id, amount_usdc=100.0, status="completed"
    )

    # Agent2: medium earnings
    listing2 = await make_listing(agent2.id, price_usdc=50.0)
    await make_transaction(
        buyer.id, agent2.id, listing2.id, amount_usdc=50.0, status="completed"
    )

    # Agent3: low earnings
    listing3 = await make_listing(agent3.id, price_usdc=10.0)
    await make_transaction(
        buyer.id, agent3.id, listing3.id, amount_usdc=10.0, status="completed"
    )

    # Calculate stats for all agents
    await get_agent_stats(db, agent1.id)
    await get_agent_stats(db, agent2.id)
    await get_agent_stats(db, agent3.id)

    # Get leaderboard
    leaderboard = await get_multi_leaderboard(db, "earnings", limit=10)

    assert len(leaderboard) == 3
    # Agent1 should be ranked first
    assert leaderboard[0]["rank"] == 1
    assert leaderboard[0]["agent_id"] == agent1.id
    assert leaderboard[0]["total_earned_usdc"] == 100.0
    # Earnings should be in descending order
    assert (
        leaderboard[0]["total_earned_usdc"]
        >= leaderboard[1]["total_earned_usdc"]
        >= leaderboard[2]["total_earned_usdc"]
    )
    # Secondary label should show earnings
    assert "$" in leaderboard[0]["secondary_label"]


@pytest.mark.asyncio
async def test_leaderboard_contributors(db, make_agent, make_listing):
    """Test contributors leaderboard based on data bytes contributed."""
    agent1, _ = await make_agent(name="big-contributor")
    agent2, _ = await make_agent(name="medium-contributor")
    agent3, _ = await make_agent(name="small-contributor")

    # Agent1: large data contributions
    await make_listing(agent1.id, content_size=10000)
    await make_listing(agent1.id, content_size=15000)

    # Agent2: medium data contributions
    await make_listing(agent2.id, content_size=5000)
    await make_listing(agent2.id, content_size=3000)

    # Agent3: small data contributions
    await make_listing(agent3.id, content_size=500)

    # Calculate stats
    await get_agent_stats(db, agent1.id)
    await get_agent_stats(db, agent2.id)
    await get_agent_stats(db, agent3.id)

    # Get leaderboard
    leaderboard = await get_multi_leaderboard(db, "contributors", limit=10)

    assert len(leaderboard) == 3
    # Agent1 should be ranked first
    assert leaderboard[0]["rank"] == 1
    assert leaderboard[0]["agent_id"] == agent1.id
    assert leaderboard[0]["primary_score"] == 25000
    # Bytes should be in descending order
    assert (
        leaderboard[0]["primary_score"]
        >= leaderboard[1]["primary_score"]
        >= leaderboard[2]["primary_score"]
    )
    # Secondary label should show bytes
    assert "bytes" in leaderboard[0]["secondary_label"]


@pytest.mark.asyncio
async def test_leaderboard_empty(db):
    """Test leaderboard with no agents."""
    leaderboard = await get_multi_leaderboard(db, "helpfulness", limit=10)

    assert leaderboard == []


@pytest.mark.asyncio
async def test_leaderboard_limit(db, make_agent, make_listing):
    """Test that leaderboard respects limit parameter."""
    # Create 10 agents
    for i in range(10):
        agent, _ = await make_agent(name=f"agent-{i}")
        await make_listing(agent.id)
        await get_agent_stats(db, agent.id)

    # Request only top 3
    leaderboard = await get_multi_leaderboard(db, "helpfulness", limit=3)

    assert len(leaderboard) == 3
    assert leaderboard[0]["rank"] == 1
    assert leaderboard[1]["rank"] == 2
    assert leaderboard[2]["rank"] == 3


@pytest.mark.asyncio
async def test_leaderboard_invalid_type(db, make_agent, make_listing):
    """Test leaderboard with invalid type returns empty list."""
    agent, _ = await make_agent(name="agent")
    await make_listing(agent.id)
    await get_agent_stats(db, agent.id)

    leaderboard = await get_multi_leaderboard(db, "invalid_type", limit=10)

    assert leaderboard == []


@pytest.mark.asyncio
async def test_leaderboard_includes_all_fields(
    db, make_agent, make_listing, make_transaction
):
    """Test that leaderboard entries include all required fields."""
    seller, _ = await make_agent(name="seller")
    buyer, _ = await make_agent(name="buyer")

    listing = await make_listing(seller.id, price_usdc=10.0)
    await make_transaction(
        buyer.id, seller.id, listing.id, amount_usdc=10.0, status="completed"
    )

    await get_agent_stats(db, seller.id)

    leaderboard = await get_multi_leaderboard(db, "earnings", limit=10)

    assert len(leaderboard) == 1
    entry = leaderboard[0]

    # Verify all fields are present
    assert "rank" in entry
    assert "agent_id" in entry
    assert "agent_name" in entry
    assert "primary_score" in entry
    assert "secondary_label" in entry
    assert "total_transactions" in entry
    assert "helpfulness_score" in entry
    assert "total_earned_usdc" in entry
