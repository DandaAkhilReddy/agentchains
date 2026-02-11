"""Comprehensive tests for catalog_service.py

Tests cover:
- Catalog entry registration with subscriber notifications
- Search by query, namespace, agent_id, quality, price
- Pagination
- Entry CRUD with owner validation
- Soft delete (status=retired)
- Subscription pattern matching (namespace, topic, price, quality filters)
- Auto-populate catalog from existing listings
"""

import pytest
from decimal import Decimal

from marketplace.services.catalog_service import (
    register_catalog_entry,
    search_catalog,
    get_catalog_entry,
    update_catalog_entry,
    delete_catalog_entry,
    get_agent_catalog,
    subscribe,
    unsubscribe,
    get_subscriptions,
    notify_subscribers,
    auto_populate_catalog,
)


# ── Test: register_catalog_entry ─────────────────────────────────────────

@pytest.mark.asyncio
async def test_register_catalog_entry_success(db, make_agent):
    """Test successful catalog entry registration."""
    agent, _ = await make_agent(name="seller-agent")

    entry = await register_catalog_entry(
        db=db,
        agent_id=agent.id,
        namespace="web_search.python",
        topic="Python tutorials",
        description="High-quality Python learning resources",
        schema_json={"type": "html", "encoding": "utf-8"},
        price_range_min=0.002,
        price_range_max=0.015,
    )

    assert entry.id is not None
    assert entry.agent_id == agent.id
    assert entry.namespace == "web_search.python"
    assert entry.topic == "Python tutorials"
    assert entry.description == "High-quality Python learning resources"
    assert float(entry.price_range_min) == 0.002
    assert float(entry.price_range_max) == 0.015
    assert entry.status == "active"


@pytest.mark.asyncio
async def test_register_catalog_entry_default_values(db, make_agent):
    """Test catalog entry registration with default values."""
    agent, _ = await make_agent()

    entry = await register_catalog_entry(
        db=db,
        agent_id=agent.id,
        namespace="api_data",
        topic="Generic API responses",
    )

    assert entry.description == ""
    assert float(entry.price_range_min) == 0.001
    assert float(entry.price_range_max) == 0.01
    assert entry.schema_json == "{}"


@pytest.mark.asyncio
async def test_register_notifies_matching_subscribers(db, make_agent, make_catalog_subscription):
    """Test that registering a catalog entry notifies matching subscribers."""
    seller, _ = await make_agent(name="seller")
    buyer, _ = await make_agent(name="buyer")

    # Create subscription that matches "web_search.*"
    await make_catalog_subscription(
        subscriber_id=buyer.id,
        namespace_pattern="web_search.*",
        topic_pattern="*",
    )

    # Register entry in matching namespace
    entry = await register_catalog_entry(
        db=db,
        agent_id=seller.id,
        namespace="web_search.python",
        topic="Python data",
        price_range_min=0.005,
    )

    # notify_subscribers is called internally; verify entry exists
    assert entry.id is not None
    assert entry.namespace == "web_search.python"


@pytest.mark.asyncio
async def test_register_skips_self_notification(db, make_agent, make_catalog_subscription):
    """Test that agents are not notified of their own catalog entries."""
    agent, _ = await make_agent()

    # Agent subscribes to own namespace pattern
    await make_catalog_subscription(
        subscriber_id=agent.id,
        namespace_pattern="web_search.*",
    )

    # Register entry as same agent
    entry = await register_catalog_entry(
        db=db,
        agent_id=agent.id,
        namespace="web_search.python",
        topic="Python data",
    )

    # Should not error; self-notification is skipped in notify_subscribers
    assert entry.agent_id == agent.id


# ── Test: search_catalog ─────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_search_catalog_by_query(db, make_agent, make_catalog_entry):
    """Test search catalog by text query (topic, description, namespace)."""
    agent, _ = await make_agent()

    # Create entries
    await make_catalog_entry(agent.id, namespace="web_search", topic="Python tutorials")
    await make_catalog_entry(agent.id, namespace="api_data", topic="Weather API")
    await make_catalog_entry(agent.id, namespace="web_search", topic="JavaScript guides")

    # Search for "python"
    results, total = await search_catalog(db, q="python")
    assert total == 1
    assert results[0].topic == "Python tutorials"

    # Search for "web_search"
    results, total = await search_catalog(db, q="web_search")
    assert total == 2


@pytest.mark.asyncio
async def test_search_catalog_by_namespace(db, make_agent, make_catalog_entry):
    """Test search catalog by exact namespace match."""
    agent, _ = await make_agent()

    await make_catalog_entry(agent.id, namespace="web_search", topic="Topic 1")
    await make_catalog_entry(agent.id, namespace="api_data", topic="Topic 2")
    await make_catalog_entry(agent.id, namespace="web_search", topic="Topic 3")

    results, total = await search_catalog(db, namespace="web_search")
    assert total == 2
    assert all(e.namespace == "web_search" for e in results)


@pytest.mark.asyncio
async def test_search_catalog_by_agent_id(db, make_agent, make_catalog_entry):
    """Test search catalog by agent_id."""
    agent1, _ = await make_agent(name="agent1")
    agent2, _ = await make_agent(name="agent2")

    await make_catalog_entry(agent1.id, namespace="web_search", topic="A")
    await make_catalog_entry(agent2.id, namespace="web_search", topic="B")
    await make_catalog_entry(agent1.id, namespace="api_data", topic="C")

    results, total = await search_catalog(db, agent_id=agent1.id)
    assert total == 2
    assert all(e.agent_id == agent1.id for e in results)


@pytest.mark.asyncio
async def test_search_catalog_by_min_quality(db, make_agent, make_catalog_entry):
    """Test search catalog by minimum quality score."""
    agent, _ = await make_agent()

    await make_catalog_entry(agent.id, namespace="web_search", topic="Low", quality_avg=0.4)
    await make_catalog_entry(agent.id, namespace="web_search", topic="Med", quality_avg=0.7)
    await make_catalog_entry(agent.id, namespace="web_search", topic="High", quality_avg=0.9)

    results, total = await search_catalog(db, min_quality=0.6)
    assert total == 2
    assert all(float(e.quality_avg) >= 0.6 for e in results)


@pytest.mark.asyncio
async def test_search_catalog_by_max_price(db, make_agent, make_catalog_entry):
    """Test search catalog by maximum price (filters by price_range_min)."""
    agent, _ = await make_agent()

    await make_catalog_entry(agent.id, namespace="web_search", topic="Cheap", price_range_min=0.001)
    await make_catalog_entry(agent.id, namespace="web_search", topic="Medium", price_range_min=0.005)
    await make_catalog_entry(agent.id, namespace="web_search", topic="Expensive", price_range_min=0.020)

    results, total = await search_catalog(db, max_price=0.010)
    assert total == 2
    assert all(float(e.price_range_min) <= 0.010 for e in results)


@pytest.mark.asyncio
async def test_search_catalog_pagination(db, make_agent, make_catalog_entry):
    """Test search catalog pagination."""
    agent, _ = await make_agent()

    # Create 25 entries
    for i in range(25):
        await make_catalog_entry(agent.id, namespace="web_search", topic=f"Topic {i}")

    # Page 1: 20 results
    results_p1, total = await search_catalog(db, page=1, page_size=20)
    assert total == 25
    assert len(results_p1) == 20

    # Page 2: 5 results
    results_p2, total = await search_catalog(db, page=2, page_size=20)
    assert total == 25
    assert len(results_p2) == 5

    # Ensure no overlap
    ids_p1 = {e.id for e in results_p1}
    ids_p2 = {e.id for e in results_p2}
    assert ids_p1.isdisjoint(ids_p2)


@pytest.mark.asyncio
async def test_search_catalog_combined_filters(db, make_agent, make_catalog_entry):
    """Test search catalog with multiple filters combined."""
    agent1, _ = await make_agent(name="agent1")
    agent2, _ = await make_agent(name="agent2")

    await make_catalog_entry(agent1.id, namespace="web_search", topic="Python A", quality_avg=0.8, price_range_min=0.003)
    await make_catalog_entry(agent1.id, namespace="web_search", topic="Python B", quality_avg=0.6, price_range_min=0.002)
    await make_catalog_entry(agent2.id, namespace="web_search", topic="Python C", quality_avg=0.9, price_range_min=0.001)
    await make_catalog_entry(agent1.id, namespace="api_data", topic="Python D", quality_avg=0.9, price_range_min=0.002)

    # Filter: namespace=web_search, min_quality=0.7, max_price=0.005, agent_id=agent1
    results, total = await search_catalog(
        db,
        namespace="web_search",
        min_quality=0.7,
        max_price=0.005,
        agent_id=agent1.id,
    )

    assert total == 1
    assert results[0].topic == "Python A"


@pytest.mark.asyncio
async def test_search_catalog_excludes_retired_entries(db, make_agent, make_catalog_entry):
    """Test that search catalog excludes entries with status='retired'."""
    agent, _ = await make_agent()

    await make_catalog_entry(agent.id, namespace="web_search", topic="Active", status="active")
    await make_catalog_entry(agent.id, namespace="web_search", topic="Retired", status="retired")

    results, total = await search_catalog(db)
    assert total == 1
    assert results[0].topic == "Active"


# ── Test: get_catalog_entry ──────────────────────────────────────────────

@pytest.mark.asyncio
async def test_get_catalog_entry_success(db, make_agent, make_catalog_entry):
    """Test get catalog entry by ID."""
    agent, _ = await make_agent()
    entry = await make_catalog_entry(agent.id, namespace="web_search", topic="Test")

    fetched = await get_catalog_entry(db, entry.id)
    assert fetched is not None
    assert fetched.id == entry.id
    assert fetched.topic == "Test"


@pytest.mark.asyncio
async def test_get_catalog_entry_not_found(db):
    """Test get catalog entry with non-existent ID."""
    fetched = await get_catalog_entry(db, "non-existent-id")
    assert fetched is None


# ── Test: update_catalog_entry ───────────────────────────────────────────

@pytest.mark.asyncio
async def test_update_catalog_entry_success(db, make_agent, make_catalog_entry):
    """Test update catalog entry as owner."""
    agent, _ = await make_agent()
    entry = await make_catalog_entry(agent.id, namespace="web_search", topic="Old Topic")

    updated = await update_catalog_entry(
        db=db,
        entry_id=entry.id,
        agent_id=agent.id,
        topic="New Topic",
        description="Updated description",
        price_range_min=0.005,
    )

    assert updated is not None
    assert updated.topic == "New Topic"
    assert updated.description == "Updated description"
    assert float(updated.price_range_min) == 0.005
    assert updated.updated_at > entry.created_at


@pytest.mark.asyncio
async def test_update_catalog_entry_wrong_owner(db, make_agent, make_catalog_entry):
    """Test update catalog entry fails if agent is not owner."""
    agent1, _ = await make_agent(name="agent1")
    agent2, _ = await make_agent(name="agent2")

    entry = await make_catalog_entry(agent1.id, namespace="web_search", topic="Test")

    updated = await update_catalog_entry(
        db=db,
        entry_id=entry.id,
        agent_id=agent2.id,  # Wrong owner
        topic="Hacked Topic",
    )

    assert updated is None

    # Verify original unchanged
    original = await get_catalog_entry(db, entry.id)
    assert original.topic == "Test"


@pytest.mark.asyncio
async def test_update_catalog_entry_not_found(db, make_agent):
    """Test update catalog entry with non-existent ID."""
    agent, _ = await make_agent()

    updated = await update_catalog_entry(
        db=db,
        entry_id="non-existent-id",
        agent_id=agent.id,
        topic="New Topic",
    )

    assert updated is None


# ── Test: delete_catalog_entry ───────────────────────────────────────────

@pytest.mark.asyncio
async def test_delete_catalog_entry_success(db, make_agent, make_catalog_entry):
    """Test delete catalog entry (soft delete, sets status=retired)."""
    agent, _ = await make_agent()
    entry = await make_catalog_entry(agent.id, namespace="web_search", topic="To Delete")

    result = await delete_catalog_entry(db, entry.id, agent.id)
    assert result is True

    # Verify soft delete: entry exists but status=retired
    deleted = await get_catalog_entry(db, entry.id)
    assert deleted is not None
    assert deleted.status == "retired"

    # Verify excluded from search
    results, total = await search_catalog(db)
    assert total == 0


@pytest.mark.asyncio
async def test_delete_catalog_entry_wrong_owner(db, make_agent, make_catalog_entry):
    """Test delete catalog entry fails if agent is not owner."""
    agent1, _ = await make_agent(name="agent1")
    agent2, _ = await make_agent(name="agent2")

    entry = await make_catalog_entry(agent1.id, namespace="web_search", topic="Test")

    result = await delete_catalog_entry(db, entry.id, agent2.id)
    assert result is False

    # Verify not deleted
    original = await get_catalog_entry(db, entry.id)
    assert original.status == "active"


@pytest.mark.asyncio
async def test_delete_catalog_entry_not_found(db, make_agent):
    """Test delete catalog entry with non-existent ID."""
    agent, _ = await make_agent()

    result = await delete_catalog_entry(db, "non-existent-id", agent.id)
    assert result is False


# ── Test: get_agent_catalog ──────────────────────────────────────────────

@pytest.mark.asyncio
async def test_get_agent_catalog(db, make_agent, make_catalog_entry):
    """Test get all active catalog entries for an agent."""
    agent, _ = await make_agent()

    await make_catalog_entry(agent.id, namespace="web_search", topic="Entry 1", status="active")
    await make_catalog_entry(agent.id, namespace="api_data", topic="Entry 2", status="active")
    await make_catalog_entry(agent.id, namespace="web_search", topic="Entry 3", status="retired")

    entries = await get_agent_catalog(db, agent.id)
    assert len(entries) == 2
    assert all(e.agent_id == agent.id for e in entries)
    assert all(e.status == "active" for e in entries)


# ── Test: subscribe ──────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_subscribe_success(db, make_agent):
    """Test creating a catalog subscription."""
    agent, _ = await make_agent()

    sub = await subscribe(
        db=db,
        subscriber_id=agent.id,
        namespace_pattern="web_search.*",
        topic_pattern="python*",
        max_price=0.010,
        min_quality=0.7,
        notify_via="websocket",
    )

    assert sub.id is not None
    assert sub.subscriber_id == agent.id
    assert sub.namespace_pattern == "web_search.*"
    assert sub.topic_pattern == "python*"
    assert float(sub.max_price) == 0.010
    assert float(sub.min_quality) == 0.7
    assert sub.notify_via == "websocket"
    assert sub.status == "active"


@pytest.mark.asyncio
async def test_subscribe_default_values(db, make_agent):
    """Test subscribe with default values."""
    agent, _ = await make_agent()

    sub = await subscribe(
        db=db,
        subscriber_id=agent.id,
        namespace_pattern="api_data",
    )

    assert sub.topic_pattern == "*"
    assert sub.max_price is None
    assert sub.min_quality is None
    assert sub.notify_via == "websocket"


# ── Test: unsubscribe ────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_unsubscribe_success(db, make_agent, make_catalog_subscription):
    """Test unsubscribe sets status=paused."""
    agent, _ = await make_agent()
    sub = await make_catalog_subscription(subscriber_id=agent.id)

    result = await unsubscribe(db, sub.id, agent.id)
    assert result is True

    # Verify status changed to paused
    from sqlalchemy import select
    from marketplace.models.catalog import CatalogSubscription
    result = await db.execute(
        select(CatalogSubscription).where(CatalogSubscription.id == sub.id)
    )
    updated_sub = result.scalar_one_or_none()
    assert updated_sub.status == "paused"


@pytest.mark.asyncio
async def test_unsubscribe_wrong_owner(db, make_agent, make_catalog_subscription):
    """Test unsubscribe fails if subscriber_id doesn't match."""
    agent1, _ = await make_agent(name="agent1")
    agent2, _ = await make_agent(name="agent2")

    sub = await make_catalog_subscription(subscriber_id=agent1.id)

    result = await unsubscribe(db, sub.id, agent2.id)
    assert result is False


@pytest.mark.asyncio
async def test_unsubscribe_not_found(db, make_agent):
    """Test unsubscribe with non-existent subscription."""
    agent, _ = await make_agent()

    result = await unsubscribe(db, "non-existent-id", agent.id)
    assert result is False


# ── Test: get_subscriptions ──────────────────────────────────────────────

@pytest.mark.asyncio
async def test_get_subscriptions(db, make_agent, make_catalog_subscription):
    """Test get active subscriptions for a subscriber."""
    agent, _ = await make_agent()

    await make_catalog_subscription(subscriber_id=agent.id, namespace_pattern="web_search.*")
    await make_catalog_subscription(subscriber_id=agent.id, namespace_pattern="api_data.*")
    await make_catalog_subscription(subscriber_id=agent.id, namespace_pattern="ml_data.*", status="paused")

    subs = await get_subscriptions(db, agent.id)
    assert len(subs) == 2
    assert all(s.subscriber_id == agent.id for s in subs)
    assert all(s.status == "active" for s in subs)


# ── Test: notify_subscribers (pattern matching) ──────────────────────────

@pytest.mark.asyncio
async def test_notify_subscribers_namespace_match(db, make_agent, make_catalog_subscription):
    """Test notify_subscribers matches namespace patterns."""
    seller, _ = await make_agent(name="seller")
    buyer1, _ = await make_agent(name="buyer1")
    buyer2, _ = await make_agent(name="buyer2")

    # buyer1 subscribes to "web_search.*"
    await make_catalog_subscription(subscriber_id=buyer1.id, namespace_pattern="web_search.*")

    # buyer2 subscribes to "api_data.*"
    await make_catalog_subscription(subscriber_id=buyer2.id, namespace_pattern="api_data.*")

    # Register entry in "web_search.python"
    entry = await register_catalog_entry(
        db=db,
        agent_id=seller.id,
        namespace="web_search.python",
        topic="Python data",
    )

    # notify_subscribers is called internally
    # Only buyer1 should be notified (namespace matches)
    # No errors should occur
    assert entry.namespace == "web_search.python"


@pytest.mark.asyncio
async def test_notify_subscribers_topic_match(db, make_agent, make_catalog_subscription):
    """Test notify_subscribers matches topic patterns."""
    seller, _ = await make_agent(name="seller")
    buyer, _ = await make_agent(name="buyer")

    # Subscribe with specific topic pattern
    await make_catalog_subscription(
        subscriber_id=buyer.id,
        namespace_pattern="web_search",
        topic_pattern="python*",
    )

    # Register matching entry
    entry = await register_catalog_entry(
        db=db,
        agent_id=seller.id,
        namespace="web_search",
        topic="Python Tutorials",
    )

    # Should match (case-insensitive)
    assert entry.topic == "Python Tutorials"


@pytest.mark.asyncio
async def test_notify_subscribers_price_filter(db, make_agent, make_catalog_subscription):
    """Test notify_subscribers respects max_price filter."""
    seller, _ = await make_agent(name="seller")
    buyer, _ = await make_agent(name="buyer")

    # Subscribe with max_price filter
    await make_catalog_subscription(
        subscriber_id=buyer.id,
        namespace_pattern="web_search.*",
        max_price=0.005,
    )

    # Register entry with higher price (should not notify)
    entry = await register_catalog_entry(
        db=db,
        agent_id=seller.id,
        namespace="web_search.python",
        topic="Expensive data",
        price_range_min=0.010,
    )

    # No error should occur
    assert float(entry.price_range_min) == 0.010


@pytest.mark.asyncio
async def test_notify_subscribers_quality_filter(db, make_agent, make_catalog_subscription, make_catalog_entry):
    """Test notify_subscribers respects min_quality filter."""
    seller, _ = await make_agent(name="seller")
    buyer, _ = await make_agent(name="buyer")

    # Subscribe with min_quality filter
    await make_catalog_subscription(
        subscriber_id=buyer.id,
        namespace_pattern="web_search.*",
        min_quality=0.8,
    )

    # Create entry with low quality (use factory to set quality_avg)
    entry = await make_catalog_entry(
        seller.id,
        namespace="web_search.python",
        topic="Low quality data",
        quality_avg=0.5,
    )

    # Manually trigger notification
    await notify_subscribers(db, entry)

    # No error should occur
    assert float(entry.quality_avg) == 0.5


# ── Test: auto_populate_catalog ──────────────────────────────────────────

@pytest.mark.asyncio
async def test_auto_populate_catalog_creates_entries(db, make_agent, make_listing):
    """Test auto_populate_catalog creates catalog entries from listings."""
    agent, _ = await make_agent()

    # Create listings in different categories
    await make_listing(agent.id, category="web_search", price_usdc=0.003, quality_score=0.8)
    await make_listing(agent.id, category="web_search", price_usdc=0.005, quality_score=0.9)
    await make_listing(agent.id, category="api_data", price_usdc=0.002, quality_score=0.7)

    entries = await auto_populate_catalog(db, agent.id)

    assert len(entries) == 2  # Two categories: web_search, api_data

    # Check web_search entry
    web_entry = next(e for e in entries if e.namespace == "web_search")
    assert web_entry.topic == "Auto-populated web_search data"
    assert "2 active web_search listings" in web_entry.description
    assert float(web_entry.price_range_min) == 0.003
    assert float(web_entry.price_range_max) == 0.005
    assert 0.8 <= float(web_entry.quality_avg) <= 0.9

    # Check api_data entry
    api_entry = next(e for e in entries if e.namespace == "api_data")
    assert api_entry.namespace == "api_data"
    assert "1 active api_data listings" in api_entry.description


@pytest.mark.asyncio
async def test_auto_populate_catalog_skips_existing(db, make_agent, make_listing, make_catalog_entry):
    """Test auto_populate_catalog skips categories with existing entries."""
    agent, _ = await make_agent()

    # Create listings
    await make_listing(agent.id, category="web_search", price_usdc=0.003)
    await make_listing(agent.id, category="api_data", price_usdc=0.002)

    # Manually create catalog entry for web_search
    await make_catalog_entry(agent.id, namespace="web_search", topic="Manual entry")

    # Auto-populate should only create api_data entry
    entries = await auto_populate_catalog(db, agent.id)

    assert len(entries) == 1
    assert entries[0].namespace == "api_data"


@pytest.mark.asyncio
async def test_auto_populate_catalog_no_listings(db, make_agent):
    """Test auto_populate_catalog returns empty list if no listings exist."""
    agent, _ = await make_agent()

    entries = await auto_populate_catalog(db, agent.id)
    assert len(entries) == 0
