"""Comprehensive tests for marketplace/services/demand_service.py."""

import pytest
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from marketplace.services import demand_service
from marketplace.models.search_log import SearchLog
from marketplace.models.demand_signal import DemandSignal
from marketplace.models.opportunity import OpportunitySignal


# ---------------------------------------------------------------------------
# Tests for log_search()
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_log_search_creates_search_log(db, make_agent):
    """Test log_search creates a SearchLog with correct fields."""
    agent, _ = await make_agent(name="search-agent")

    log = await demand_service.log_search(
        db=db,
        query_text="machine learning datasets",
        category="web_search",
        source="discover",
        requester_id=agent.id,
        matched_count=5,
        led_to_purchase=1,
        max_price=10.0,
    )

    assert log.id is not None
    assert log.query_text == "machine learning datasets"
    assert log.category == "web_search"
    assert log.source == "discover"
    assert log.requester_id == agent.id
    assert log.matched_count == 5
    assert log.led_to_purchase == 1
    assert float(log.max_price) == 10.0
    assert log.created_at is not None


@pytest.mark.asyncio
async def test_log_search_defaults(db):
    """Test log_search with default parameters."""
    log = await demand_service.log_search(
        db=db,
        query_text="test query",
    )

    assert log.query_text == "test query"
    assert log.category is None
    assert log.source == "discover"
    assert log.requester_id is None
    assert log.matched_count == 0
    assert log.led_to_purchase == 0
    assert log.max_price is None


@pytest.mark.asyncio
async def test_log_search_persisted_to_db(db):
    """Test that log_search commits the log to database."""
    await demand_service.log_search(db, "test query")

    from sqlalchemy import select
    result = await db.execute(select(SearchLog))
    logs = list(result.scalars().all())

    assert len(logs) == 1
    assert logs[0].query_text == "test query"


# ---------------------------------------------------------------------------
# Tests for normalize_query()
# ---------------------------------------------------------------------------

def test_normalize_query_lowercase_and_sort():
    """Test normalize_query lowercases and sorts words."""
    result = demand_service.normalize_query("Machine Learning Python")
    assert result == "learning machine python"


def test_normalize_query_deduplicates():
    """Test normalize_query removes duplicate words."""
    result = demand_service.normalize_query("python python tutorial")
    assert result == "python tutorial"


def test_normalize_query_strips_whitespace():
    """Test normalize_query handles extra whitespace."""
    result = demand_service.normalize_query("  python   tutorial  ")
    assert result == "python tutorial"


# ---------------------------------------------------------------------------
# Tests for aggregate_demand()
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_aggregate_demand_groups_by_normalized_query(db, make_agent):
    """Test aggregate_demand groups searches by normalized query."""
    agent, _ = await make_agent()

    # Create 3 searches with same normalized pattern
    await demand_service.log_search(db, "Python Tutorial", category="web_search", requester_id=agent.id)
    await demand_service.log_search(db, "tutorial python", category="web_search", requester_id=agent.id)
    await demand_service.log_search(db, "Python Tutorial", category="web_search", requester_id=agent.id)

    signals = await demand_service.aggregate_demand(db, time_window_hours=24)

    assert len(signals) == 1
    assert signals[0].query_pattern == "python tutorial"
    assert signals[0].search_count == 3


@pytest.mark.asyncio
async def test_aggregate_demand_calculates_velocity(db):
    """Test aggregate_demand calculates searches per hour."""
    # Create 10 searches
    for _ in range(10):
        await demand_service.log_search(db, "python tutorial", category="web_search")

    signals = await demand_service.aggregate_demand(db, time_window_hours=5)

    assert len(signals) == 1
    # 10 searches / 5 hours = 2.0 per hour
    assert float(signals[0].velocity) == 2.0


@pytest.mark.asyncio
async def test_aggregate_demand_calculates_fulfillment_rate(db, make_agent):
    """Test aggregate_demand calculates fulfillment rate correctly."""
    agent, _ = await make_agent()

    # 2 with results, 8 without
    await demand_service.log_search(db, "python tutorial", matched_count=5, requester_id=agent.id)
    await demand_service.log_search(db, "Python Tutorial", matched_count=3, requester_id=agent.id)
    for _ in range(8):
        await demand_service.log_search(db, "tutorial python", matched_count=0, requester_id=agent.id)

    signals = await demand_service.aggregate_demand(db, time_window_hours=24)

    assert len(signals) == 1
    # 2/10 = 0.2
    assert float(signals[0].fulfillment_rate) == 0.2


@pytest.mark.asyncio
async def test_aggregate_demand_identifies_gaps(db):
    """Test aggregate_demand sets is_gap=1 when fulfillment_rate < 0.2."""
    # Create 10 searches, only 1 with results (10% fulfillment)
    await demand_service.log_search(db, "rare dataset", matched_count=1)
    for _ in range(9):
        await demand_service.log_search(db, "rare dataset", matched_count=0)

    signals = await demand_service.aggregate_demand(db, time_window_hours=24)

    assert len(signals) == 1
    assert float(signals[0].fulfillment_rate) == 0.1
    assert signals[0].is_gap == 1


@pytest.mark.asyncio
async def test_aggregate_demand_upserts_existing_signal(db):
    """Test aggregate_demand updates existing DemandSignal instead of creating duplicate."""
    # First aggregation
    await demand_service.log_search(db, "python tutorial")
    signals1 = await demand_service.aggregate_demand(db, time_window_hours=24)
    signal_id = signals1[0].id

    # Add more searches and re-aggregate
    await demand_service.log_search(db, "tutorial python")
    await demand_service.log_search(db, "Python Tutorial")
    signals2 = await demand_service.aggregate_demand(db, time_window_hours=24)

    # Should update same signal, not create new one
    assert len(signals2) == 1
    assert signals2[0].id == signal_id
    assert signals2[0].search_count == 3


@pytest.mark.asyncio
async def test_aggregate_demand_counts_unique_requesters(db, make_agent):
    """Test aggregate_demand counts unique requester IDs."""
    agent1, _ = await make_agent(name="agent1")
    agent2, _ = await make_agent(name="agent2")
    agent3, _ = await make_agent(name="agent3")

    # 5 searches from 3 different agents
    await demand_service.log_search(db, "python tutorial", requester_id=agent1.id)
    await demand_service.log_search(db, "python tutorial", requester_id=agent1.id)
    await demand_service.log_search(db, "python tutorial", requester_id=agent2.id)
    await demand_service.log_search(db, "python tutorial", requester_id=agent3.id)
    await demand_service.log_search(db, "python tutorial", requester_id=agent2.id)

    signals = await demand_service.aggregate_demand(db, time_window_hours=24)

    assert len(signals) == 1
    assert signals[0].unique_requesters == 3


@pytest.mark.asyncio
async def test_aggregate_demand_calculates_avg_max_price(db):
    """Test aggregate_demand calculates average max_price."""
    await demand_service.log_search(db, "python tutorial", max_price=10.0)
    await demand_service.log_search(db, "tutorial python", max_price=20.0)
    await demand_service.log_search(db, "Python Tutorial", max_price=15.0)

    signals = await demand_service.aggregate_demand(db, time_window_hours=24)

    assert len(signals) == 1
    # (10 + 20 + 15) / 3 = 15.0
    assert float(signals[0].avg_max_price) == 15.0


@pytest.mark.asyncio
async def test_aggregate_demand_most_common_category(db):
    """Test aggregate_demand uses most common category in group."""
    await demand_service.log_search(db, "python tutorial", category="web_search")
    await demand_service.log_search(db, "tutorial python", category="web_search")
    await demand_service.log_search(db, "Python Tutorial", category="api_data")

    signals = await demand_service.aggregate_demand(db, time_window_hours=24)

    assert len(signals) == 1
    # web_search appears 2 times, api_data 1 time
    assert signals[0].category == "web_search"


@pytest.mark.asyncio
async def test_aggregate_demand_time_window_filter(db):
    """Test aggregate_demand respects time window."""
    from sqlalchemy import select, update

    # Create recent search
    log1 = await demand_service.log_search(db, "recent query")

    # Create old search (manually backdate it)
    log2 = await demand_service.log_search(db, "old query")
    old_time = datetime.now(timezone.utc) - timedelta(hours=50)
    await db.execute(
        update(SearchLog)
        .where(SearchLog.id == log2.id)
        .values(created_at=old_time)
    )
    await db.commit()

    # Aggregate with 24-hour window
    signals = await demand_service.aggregate_demand(db, time_window_hours=24)

    # Should only include recent query
    assert len(signals) == 1
    assert signals[0].query_pattern == "query recent"


@pytest.mark.asyncio
async def test_aggregate_demand_empty_returns_empty_list(db):
    """Test aggregate_demand returns empty list when no logs exist."""
    signals = await demand_service.aggregate_demand(db, time_window_hours=24)
    assert signals == []


# ---------------------------------------------------------------------------
# Tests for get_trending()
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_trending_returns_by_velocity(db, make_demand_signal):
    """Test get_trending returns signals ordered by velocity desc."""
    signal1 = await make_demand_signal(query_pattern="slow query", velocity=1.0)
    signal2 = await make_demand_signal(query_pattern="fast query", velocity=10.0)
    signal3 = await make_demand_signal(query_pattern="medium query", velocity=5.0)

    trending = await demand_service.get_trending(db, limit=10, hours=24)

    assert len(trending) == 3
    assert trending[0].id == signal2.id  # highest velocity first
    assert trending[1].id == signal3.id
    assert trending[2].id == signal1.id


@pytest.mark.asyncio
async def test_get_trending_respects_time_window(db, make_demand_signal):
    """Test get_trending filters by last_searched_at within time window."""
    from sqlalchemy import update

    # Recent signal
    signal1 = await make_demand_signal(query_pattern="recent", velocity=5.0)

    # Old signal (backdate last_searched_at)
    signal2 = await make_demand_signal(query_pattern="old", velocity=10.0)
    old_time = datetime.now(timezone.utc) - timedelta(hours=10)
    await db.execute(
        update(DemandSignal)
        .where(DemandSignal.id == signal2.id)
        .values(last_searched_at=old_time)
    )
    await db.commit()

    # Get trending within 6 hours
    trending = await demand_service.get_trending(db, limit=10, hours=6)

    # Should only include recent signal
    assert len(trending) == 1
    assert trending[0].id == signal1.id


@pytest.mark.asyncio
async def test_get_trending_respects_limit(db, make_demand_signal):
    """Test get_trending respects limit parameter."""
    for i in range(10):
        await make_demand_signal(query_pattern=f"query-{i}", velocity=float(i))

    trending = await demand_service.get_trending(db, limit=3, hours=24)

    assert len(trending) == 3


# ---------------------------------------------------------------------------
# Tests for get_demand_gaps()
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_demand_gaps_filters_by_is_gap(db, make_demand_signal):
    """Test get_demand_gaps returns only signals with is_gap=1."""
    gap1 = await make_demand_signal(query_pattern="gap1", is_gap=1, search_count=100)
    gap2 = await make_demand_signal(query_pattern="gap2", is_gap=1, search_count=50)
    not_gap = await make_demand_signal(query_pattern="fulfilled", is_gap=0, search_count=200)

    gaps = await demand_service.get_demand_gaps(db, limit=10)

    assert len(gaps) == 2
    gap_ids = {g.id for g in gaps}
    assert gap1.id in gap_ids
    assert gap2.id in gap_ids
    assert not_gap.id not in gap_ids


@pytest.mark.asyncio
async def test_get_demand_gaps_orders_by_search_count(db, make_demand_signal):
    """Test get_demand_gaps returns gaps ordered by search_count desc."""
    gap1 = await make_demand_signal(query_pattern="low", is_gap=1, search_count=10)
    gap2 = await make_demand_signal(query_pattern="high", is_gap=1, search_count=100)
    gap3 = await make_demand_signal(query_pattern="medium", is_gap=1, search_count=50)

    gaps = await demand_service.get_demand_gaps(db, limit=10)

    assert len(gaps) == 3
    assert gaps[0].id == gap2.id  # highest search_count first
    assert gaps[1].id == gap3.id
    assert gaps[2].id == gap1.id


@pytest.mark.asyncio
async def test_get_demand_gaps_category_filter(db, make_demand_signal):
    """Test get_demand_gaps filters by category when provided."""
    gap_web = await make_demand_signal(
        query_pattern="web gap",
        category="web_search",
        is_gap=1,
        search_count=100
    )
    gap_api = await make_demand_signal(
        query_pattern="api gap",
        category="api_data",
        is_gap=1,
        search_count=90
    )

    gaps = await demand_service.get_demand_gaps(db, limit=10, category="web_search")

    assert len(gaps) == 1
    assert gaps[0].id == gap_web.id


@pytest.mark.asyncio
async def test_get_demand_gaps_respects_limit(db, make_demand_signal):
    """Test get_demand_gaps respects limit parameter."""
    for i in range(10):
        await make_demand_signal(query_pattern=f"gap-{i}", is_gap=1, search_count=i)

    gaps = await demand_service.get_demand_gaps(db, limit=3)

    assert len(gaps) == 3


# ---------------------------------------------------------------------------
# Tests for generate_opportunities()
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_generate_opportunities_creates_from_gaps(db, make_demand_signal):
    """Test generate_opportunities creates OpportunitySignal from gaps."""
    gap = await make_demand_signal(
        query_pattern="ml datasets",
        category="web_search",
        is_gap=1,
        search_count=100,
        velocity=5.0,
        fulfillment_rate=0.1,
        unique_requesters=10,
    )

    opportunities = await demand_service.generate_opportunities(db)

    assert len(opportunities) == 1
    opp = opportunities[0]
    assert opp.demand_signal_id == gap.id
    assert opp.query_pattern == "ml datasets"
    assert opp.category == "web_search"
    assert opp.status == "active"


@pytest.mark.asyncio
async def test_generate_opportunities_calculates_estimated_revenue(db, make_demand_signal):
    """Test generate_opportunities calculates estimated_revenue_usdc = velocity * avg_price."""
    from decimal import Decimal

    gap = await make_demand_signal(
        query_pattern="test",
        is_gap=1,
        velocity=10.0,  # 10 searches/hour
        unique_requesters=5,
    )

    # Update avg_max_price manually
    from sqlalchemy import update
    await db.execute(
        update(DemandSignal)
        .where(DemandSignal.id == gap.id)
        .values(avg_max_price=Decimal("2.5"))
    )
    await db.commit()

    opportunities = await demand_service.generate_opportunities(db)

    assert len(opportunities) == 1
    # 10 * 2.5 = 25.0
    assert float(opportunities[0].estimated_revenue_usdc) == 25.0


@pytest.mark.asyncio
async def test_generate_opportunities_calculates_urgency_score(db, make_demand_signal):
    """Test generate_opportunities calculates urgency score correctly."""
    gap = await make_demand_signal(
        query_pattern="urgent query",
        is_gap=1,
        velocity=10.0,
        fulfillment_rate=0.0,  # 0% fulfillment
        unique_requesters=20,
    )

    opportunities = await demand_service.generate_opportunities(db)

    assert len(opportunities) == 1
    urgency = float(opportunities[0].urgency_score)

    # Urgency = 0.4 * norm_velocity + 0.3 * (1 - fulfillment) + 0.3 * norm_requesters
    # All values are max, so should be high
    assert urgency > 0.7


@pytest.mark.asyncio
async def test_generate_opportunities_upserts_existing(db, make_demand_signal):
    """Test generate_opportunities updates existing active opportunity."""
    gap = await make_demand_signal(
        query_pattern="test query",
        is_gap=1,
        velocity=5.0,
        unique_requesters=10,
    )

    # First generation
    opps1 = await demand_service.generate_opportunities(db)
    opp_id = opps1[0].id

    # Update gap velocity
    from sqlalchemy import update
    await db.execute(
        update(DemandSignal)
        .where(DemandSignal.id == gap.id)
        .values(velocity=Decimal("10.0"))
    )
    await db.commit()

    # Second generation
    opps2 = await demand_service.generate_opportunities(db)

    # Should update same opportunity, not create new one
    assert len(opps2) == 1
    assert opps2[0].id == opp_id
    assert float(opps2[0].search_velocity) == 10.0


@pytest.mark.asyncio
async def test_generate_opportunities_counts_competing_listings(db, make_demand_signal, make_agent, make_listing):
    """Test generate_opportunities counts active competing listings."""
    seller, _ = await make_agent(name="seller")

    gap = await make_demand_signal(
        query_pattern="web data",
        category="web_search",
        is_gap=1,
        velocity=5.0,
        unique_requesters=5,
    )

    # Create 3 active listings in same category
    await make_listing(seller.id, category="web_search", status="active")
    await make_listing(seller.id, category="web_search", status="active")
    await make_listing(seller.id, category="web_search", status="active")

    # Create 1 inactive listing (should not count)
    await make_listing(seller.id, category="web_search", status="sold")

    # Create 1 listing in different category (should not count)
    await make_listing(seller.id, category="api_data", status="active")

    opportunities = await demand_service.generate_opportunities(db)

    assert len(opportunities) == 1
    # Should only count the 3 active listings in web_search category
    assert opportunities[0].competing_listings == 3


@pytest.mark.asyncio
async def test_generate_opportunities_empty_when_no_gaps(db):
    """Test generate_opportunities returns empty list when no gaps exist."""
    opportunities = await demand_service.generate_opportunities(db)
    assert opportunities == []


@pytest.mark.asyncio
async def test_generate_opportunities_sets_expires_at(db, make_demand_signal):
    """Test generate_opportunities sets expires_at 24 hours from now."""
    gap = await make_demand_signal(
        query_pattern="test",
        is_gap=1,
        velocity=5.0,
        unique_requesters=5,
    )

    now = datetime.now(timezone.utc)
    opportunities = await demand_service.generate_opportunities(db)

    assert len(opportunities) == 1
    expires = opportunities[0].expires_at

    # Should be approximately 24 hours from now (allow 1 minute margin)
    expected = now + timedelta(hours=24)
    delta = abs((expires - expected).total_seconds())
    assert delta < 60


# ---------------------------------------------------------------------------
# Tests for get_opportunities()
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_opportunities_returns_active_only(db, make_demand_signal):
    """Test get_opportunities returns only active opportunities."""
    gap1 = await make_demand_signal(query_pattern="gap1", is_gap=1, velocity=5.0, unique_requesters=5)
    gap2 = await make_demand_signal(query_pattern="gap2", is_gap=1, velocity=3.0, unique_requesters=3)

    # Generate opportunities
    opps = await demand_service.generate_opportunities(db)
    assert len(opps) == 2

    # Mark one as expired
    from sqlalchemy import update
    await db.execute(
        update(OpportunitySignal)
        .where(OpportunitySignal.id == opps[0].id)
        .values(status="expired")
    )
    await db.commit()

    # Get opportunities
    active_opps = await demand_service.get_opportunities(db, limit=10)

    # Should only return active one
    assert len(active_opps) == 1
    assert active_opps[0].status == "active"


@pytest.mark.asyncio
async def test_get_opportunities_orders_by_urgency(db, make_demand_signal):
    """Test get_opportunities returns opportunities ordered by urgency_score desc."""
    gap1 = await make_demand_signal(
        query_pattern="low urgency",
        is_gap=1,
        velocity=1.0,
        fulfillment_rate=0.15,
        unique_requesters=2
    )
    gap2 = await make_demand_signal(
        query_pattern="high urgency",
        is_gap=1,
        velocity=20.0,
        fulfillment_rate=0.0,
        unique_requesters=50
    )

    opportunities = await demand_service.generate_opportunities(db)
    retrieved = await demand_service.get_opportunities(db, limit=10)

    assert len(retrieved) == 2
    # Higher urgency should be first
    assert retrieved[0].query_pattern == "high urgency"
    assert retrieved[1].query_pattern == "low urgency"


@pytest.mark.asyncio
async def test_get_opportunities_category_filter(db, make_demand_signal):
    """Test get_opportunities filters by category when provided."""
    gap_web = await make_demand_signal(
        query_pattern="web gap",
        category="web_search",
        is_gap=1,
        velocity=5.0,
        unique_requesters=5
    )
    gap_api = await make_demand_signal(
        query_pattern="api gap",
        category="api_data",
        is_gap=1,
        velocity=5.0,
        unique_requesters=5
    )

    await demand_service.generate_opportunities(db)
    opps = await demand_service.get_opportunities(db, category="web_search", limit=10)

    assert len(opps) == 1
    assert opps[0].category == "web_search"


@pytest.mark.asyncio
async def test_get_opportunities_respects_limit(db, make_demand_signal):
    """Test get_opportunities respects limit parameter."""
    for i in range(10):
        await make_demand_signal(
            query_pattern=f"gap-{i}",
            is_gap=1,
            velocity=float(i),
            unique_requesters=i+1
        )

    await demand_service.generate_opportunities(db)
    opps = await demand_service.get_opportunities(db, limit=3)

    assert len(opps) == 3
