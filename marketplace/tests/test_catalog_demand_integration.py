"""Integration tests for catalog service and demand intelligence.

IT-8: 20 integration tests covering the full lifecycle of catalog entries
(register, search, update, delete, subscribe/unsubscribe, agent catalog)
and demand intelligence (log_search, normalize_query, aggregate_demand,
trending, gaps, opportunities).
"""

import pytest
from decimal import Decimal

from marketplace.services.catalog_service import (
    register_catalog_entry,
    search_catalog,
    get_catalog_entry,
    update_catalog_entry,
    delete_catalog_entry,
    subscribe,
    unsubscribe,
    get_subscriptions,
    get_agent_catalog,
)
from marketplace.services.demand_service import (
    normalize_query,
    log_search,
    aggregate_demand,
    get_trending,
    get_demand_gaps,
    generate_opportunities,
    get_opportunities,
)


# =====================================================================
# CATALOG INTEGRATION TESTS (1-10)
# =====================================================================


@pytest.mark.asyncio
async def test_register_catalog_entry(db, make_agent):
    """1. Creates entry with agent_id, namespace, topic."""
    agent, _ = await make_agent(name="catalog-seller")

    entry = await register_catalog_entry(
        db=db,
        agent_id=agent.id,
        namespace="web_search",
        topic="test",
        description="Integration test entry",
    )

    assert entry.id is not None
    assert entry.agent_id == agent.id
    assert entry.namespace == "web_search"
    assert entry.topic == "test"
    assert entry.description == "Integration test entry"
    assert entry.status == "active"
    assert float(entry.price_range_min) == 0.001
    assert float(entry.price_range_max) == 0.01


@pytest.mark.asyncio
async def test_search_catalog_by_query(db, make_agent, make_catalog_entry):
    """2. Search with q= finds matching entries."""
    agent, _ = await make_agent()

    await make_catalog_entry(agent.id, namespace="web_search", topic="python basics")
    await make_catalog_entry(agent.id, namespace="api_data", topic="weather api")
    await make_catalog_entry(agent.id, namespace="web_search", topic="java tutorial")

    entries, total = await search_catalog(db, q="python")

    assert total == 1
    assert len(entries) == 1
    assert entries[0].topic == "python basics"


@pytest.mark.asyncio
async def test_search_catalog_by_namespace(db, make_agent, make_catalog_entry):
    """3. Filter by namespace returns only matching entries."""
    agent, _ = await make_agent()

    await make_catalog_entry(agent.id, namespace="web_search", topic="topic A")
    await make_catalog_entry(agent.id, namespace="api_data", topic="topic B")
    await make_catalog_entry(agent.id, namespace="web_search", topic="topic C")

    entries, total = await search_catalog(db, namespace="web_search")

    assert total == 2
    assert len(entries) == 2
    assert all(e.namespace == "web_search" for e in entries)


@pytest.mark.asyncio
async def test_search_catalog_pagination(db, make_agent, make_catalog_entry):
    """4. page and page_size work correctly for catalog search."""
    agent, _ = await make_agent()

    for i in range(15):
        await make_catalog_entry(agent.id, namespace="web_search", topic=f"item-{i}")

    # Page 1 with page_size=5
    entries_p1, total = await search_catalog(db, page=1, page_size=5)
    assert total == 15
    assert len(entries_p1) == 5

    # Page 2 with page_size=5
    entries_p2, total = await search_catalog(db, page=2, page_size=5)
    assert total == 15
    assert len(entries_p2) == 5

    # Page 3 with page_size=5
    entries_p3, total = await search_catalog(db, page=3, page_size=5)
    assert total == 15
    assert len(entries_p3) == 5

    # No overlap between pages
    ids_p1 = {e.id for e in entries_p1}
    ids_p2 = {e.id for e in entries_p2}
    ids_p3 = {e.id for e in entries_p3}
    assert ids_p1.isdisjoint(ids_p2)
    assert ids_p2.isdisjoint(ids_p3)
    assert ids_p1.isdisjoint(ids_p3)


@pytest.mark.asyncio
async def test_get_catalog_entry(db, make_agent, make_catalog_entry):
    """5. Get by ID returns the correct entry."""
    agent, _ = await make_agent()
    entry = await make_catalog_entry(agent.id, namespace="web_search", topic="test")

    fetched = await get_catalog_entry(db, entry.id)

    assert fetched is not None
    assert fetched.id == entry.id
    assert fetched.namespace == "web_search"
    assert fetched.topic == "test"
    assert fetched.agent_id == agent.id


@pytest.mark.asyncio
async def test_update_catalog_entry(db, make_agent, make_catalog_entry):
    """6. Update description works when agent owns the entry."""
    agent, _ = await make_agent()
    entry = await make_catalog_entry(agent.id, namespace="web_search", topic="test")

    updated = await update_catalog_entry(
        db=db,
        entry_id=entry.id,
        agent_id=agent.id,
        description="Updated description via integration test",
    )

    assert updated is not None
    assert updated.description == "Updated description via integration test"
    assert updated.id == entry.id


@pytest.mark.asyncio
async def test_update_catalog_entry_wrong_agent(db, make_agent, make_catalog_entry):
    """7. Returns None if agent does not own the entry."""
    owner, _ = await make_agent(name="owner-agent")
    other, _ = await make_agent(name="other-agent")
    entry = await make_catalog_entry(owner.id, namespace="web_search", topic="test")

    result = await update_catalog_entry(
        db=db,
        entry_id=entry.id,
        agent_id=other.id,
        description="Should not work",
    )

    assert result is None

    # Verify original entry is unchanged
    original = await get_catalog_entry(db, entry.id)
    assert original.description == "Test catalog entry"


@pytest.mark.asyncio
async def test_delete_catalog_entry(db, make_agent, make_catalog_entry):
    """8. Delete sets status to 'retired'."""
    agent, _ = await make_agent()
    entry = await make_catalog_entry(agent.id, namespace="web_search", topic="test")

    result = await delete_catalog_entry(db, entry.id, agent.id)
    assert result is True

    # Verify soft delete
    deleted = await get_catalog_entry(db, entry.id)
    assert deleted is not None
    assert deleted.status == "retired"

    # Verify excluded from search
    entries, total = await search_catalog(db)
    assert total == 0


@pytest.mark.asyncio
async def test_subscribe_and_unsubscribe(db, make_agent):
    """9. Subscribe creates CatalogSubscription, unsubscribe pauses it."""
    agent, _ = await make_agent()

    # Subscribe
    sub = await subscribe(
        db=db,
        subscriber_id=agent.id,
        namespace_pattern="web_search.*",
        topic_pattern="python*",
    )

    assert sub.id is not None
    assert sub.subscriber_id == agent.id
    assert sub.namespace_pattern == "web_search.*"
    assert sub.status == "active"

    # Verify it appears in active subscriptions
    subs = await get_subscriptions(db, agent.id)
    assert len(subs) == 1
    assert subs[0].id == sub.id

    # Unsubscribe
    result = await unsubscribe(db, sub.id, agent.id)
    assert result is True

    # Verify status is now paused and no longer in active list
    subs_after = await get_subscriptions(db, agent.id)
    assert len(subs_after) == 0


@pytest.mark.asyncio
async def test_get_agent_catalog(db, make_agent, make_catalog_entry):
    """10. Returns only active entries for the specified agent."""
    agent, _ = await make_agent()
    other_agent, _ = await make_agent(name="other")

    await make_catalog_entry(agent.id, namespace="web_search", topic="active-1", status="active")
    await make_catalog_entry(agent.id, namespace="api_data", topic="active-2", status="active")
    await make_catalog_entry(agent.id, namespace="ml_data", topic="retired-1", status="retired")
    await make_catalog_entry(other_agent.id, namespace="web_search", topic="other-agent-entry", status="active")

    entries = await get_agent_catalog(db, agent.id)

    assert len(entries) == 2
    assert all(e.agent_id == agent.id for e in entries)
    assert all(e.status == "active" for e in entries)
    topics = {e.topic for e in entries}
    assert topics == {"active-1", "active-2"}


# =====================================================================
# DEMAND INTELLIGENCE INTEGRATION TESTS (11-20)
# =====================================================================


@pytest.mark.asyncio
async def test_log_search(db):
    """11. Creates SearchLog entry with correct fields."""
    log = await log_search(
        db=db,
        query_text="python tutorial",
        category="web_search",
        source="discover",
        matched_count=3,
        led_to_purchase=1,
    )

    assert log.id is not None
    assert log.query_text == "python tutorial"
    assert log.category == "web_search"
    assert log.source == "discover"
    assert log.matched_count == 3
    assert log.led_to_purchase == 1
    assert log.created_at is not None


def test_normalize_query():
    """12. 'Python Tutorial' becomes 'python tutorial' (lowercase sorted unique words)."""
    result = normalize_query("Python Tutorial")
    assert result == "python tutorial"

    # Also verify sorting and deduplication
    result2 = normalize_query("Tutorial Python Python")
    assert result2 == "python tutorial"

    # Whitespace handling
    result3 = normalize_query("  Python   Tutorial  ")
    assert result3 == "python tutorial"


@pytest.mark.asyncio
async def test_aggregate_demand_basic(db):
    """13. Aggregates search logs into DemandSignal."""
    # Create multiple search logs with the same normalized query
    await log_search(db, query_text="python tutorial", category="web_search")
    await log_search(db, query_text="Tutorial Python", category="web_search")
    await log_search(db, query_text="python tutorial", category="web_search")

    signals = await aggregate_demand(db, time_window_hours=24)

    assert len(signals) == 1
    assert signals[0].query_pattern == "python tutorial"
    assert signals[0].search_count == 3
    assert signals[0].category == "web_search"


@pytest.mark.asyncio
async def test_aggregate_demand_gap_detection(db):
    """14. fulfillment_rate < 0.2 sets is_gap=1."""
    # Create 10 searches, only 1 has matched results (10% fulfillment)
    await log_search(db, query_text="obscure data", category="web_search", matched_count=1)
    for _ in range(9):
        await log_search(db, query_text="obscure data", category="web_search", matched_count=0)

    signals = await aggregate_demand(db, time_window_hours=24)

    assert len(signals) == 1
    assert float(signals[0].fulfillment_rate) == 0.1
    assert signals[0].is_gap == 1


@pytest.mark.asyncio
async def test_aggregate_demand_velocity(db):
    """15. velocity = search_count / time_window_hours."""
    # Create 12 searches in a 6-hour window
    for _ in range(12):
        await log_search(db, query_text="trending topic", category="web_search")

    signals = await aggregate_demand(db, time_window_hours=6)

    assert len(signals) == 1
    # 12 searches / 6 hours = 2.0
    assert float(signals[0].velocity) == 2.0


@pytest.mark.asyncio
async def test_get_trending(db, make_demand_signal):
    """16. Returns signals ordered by velocity desc."""
    slow = await make_demand_signal(query_pattern="slow query", velocity=1.0)
    fast = await make_demand_signal(query_pattern="fast query", velocity=10.0)
    medium = await make_demand_signal(query_pattern="medium query", velocity=5.0)

    trending = await get_trending(db, limit=10, hours=24)

    assert len(trending) == 3
    assert trending[0].id == fast.id
    assert trending[1].id == medium.id
    assert trending[2].id == slow.id
    assert float(trending[0].velocity) >= float(trending[1].velocity)
    assert float(trending[1].velocity) >= float(trending[2].velocity)


@pytest.mark.asyncio
async def test_get_demand_gaps(db, make_demand_signal):
    """17. Returns only is_gap=1 signals."""
    gap1 = await make_demand_signal(query_pattern="gap one", is_gap=1, search_count=50)
    gap2 = await make_demand_signal(query_pattern="gap two", is_gap=1, search_count=100)
    non_gap = await make_demand_signal(query_pattern="fulfilled query", is_gap=0, search_count=200)

    gaps = await get_demand_gaps(db, limit=10)

    assert len(gaps) == 2
    gap_ids = {g.id for g in gaps}
    assert gap1.id in gap_ids
    assert gap2.id in gap_ids
    assert non_gap.id not in gap_ids


@pytest.mark.asyncio
async def test_generate_opportunities(db, make_demand_signal):
    """18. Creates OpportunitySignal from demand gaps."""
    gap = await make_demand_signal(
        query_pattern="unmet need",
        category="web_search",
        is_gap=1,
        velocity=8.0,
        fulfillment_rate=0.05,
        unique_requesters=15,
        search_count=80,
    )

    opportunities = await generate_opportunities(db)

    assert len(opportunities) == 1
    opp = opportunities[0]
    assert opp.demand_signal_id == gap.id
    assert opp.query_pattern == "unmet need"
    assert opp.category == "web_search"
    assert opp.status == "active"
    assert float(opp.urgency_score) > 0
    assert float(opp.search_velocity) == 8.0


@pytest.mark.asyncio
async def test_get_opportunities(db, make_demand_signal):
    """19. Returns active opportunities ordered by urgency desc."""
    # Create two gaps with different urgency profiles
    gap_low = await make_demand_signal(
        query_pattern="low priority",
        category="web_search",
        is_gap=1,
        velocity=1.0,
        fulfillment_rate=0.15,
        unique_requesters=2,
    )
    gap_high = await make_demand_signal(
        query_pattern="high priority",
        category="web_search",
        is_gap=1,
        velocity=20.0,
        fulfillment_rate=0.0,
        unique_requesters=50,
    )

    # Generate opportunities from gaps
    await generate_opportunities(db)

    # Retrieve opportunities
    opps = await get_opportunities(db, limit=10)

    assert len(opps) == 2
    # Higher urgency should come first
    assert float(opps[0].urgency_score) >= float(opps[1].urgency_score)
    assert opps[0].query_pattern == "high priority"
    assert opps[1].query_pattern == "low priority"


@pytest.mark.asyncio
async def test_aggregate_demand_upsert(db):
    """20. Calling aggregate twice updates existing signal rather than creating a duplicate."""
    # First round: 2 searches
    await log_search(db, query_text="python tutorial", category="web_search")
    await log_search(db, query_text="tutorial python", category="web_search")

    signals_1 = await aggregate_demand(db, time_window_hours=24)
    assert len(signals_1) == 1
    signal_id = signals_1[0].id
    assert signals_1[0].search_count == 2

    # Second round: add more searches and re-aggregate
    await log_search(db, query_text="Python Tutorial", category="web_search")
    await log_search(db, query_text="python tutorial", category="web_search")

    signals_2 = await aggregate_demand(db, time_window_hours=24)

    assert len(signals_2) == 1
    # Same signal ID -- upsert, not duplicate
    assert signals_2[0].id == signal_id
    # Count reflects all 4 searches
    assert signals_2[0].search_count == 4
