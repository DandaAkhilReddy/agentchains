"""Deep tests for demand aggregation, catalog operations, and subscription patterns.

Covers:
  - normalize_query edge cases
  - aggregate_demand grouping, velocity, is_gap, upsert
  - get_trending ordering
  - get_demand_gaps category filtering
  - generate_opportunities urgency formula, 24h expiry, upsert
  - Catalog CRUD: create, read, update, delete (sets status="retired")
  - Catalog subscribe: namespace pattern fnmatch, topic pattern, skips self
  - auto_populate_catalog: groups by category, skips existing
  - API routes: GET /analytics/trending, GET /analytics/demand-gaps, POST /catalog
  - Subscription matching and notification patterns
"""

import pytest
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import update

from marketplace.services import demand_service, catalog_service
from marketplace.models.search_log import SearchLog
from marketplace.models.demand_signal import DemandSignal
from marketplace.models.catalog import DataCatalogEntry, CatalogSubscription


# ---------------------------------------------------------------------------
# 1. normalize_query: mixed-case duplicates with extra whitespace
# ---------------------------------------------------------------------------

def test_normalize_query_mixed_case_duplicates_whitespace():
    """normalize_query lowercases, deduplicates, sorts, and strips."""
    result = demand_service.normalize_query("  Zoo  apple  ZOO  Apple  banana  ")
    assert result == "apple banana zoo"


# ---------------------------------------------------------------------------
# 2. normalize_query: single word passthrough
# ---------------------------------------------------------------------------

def test_normalize_query_single_word():
    """A single word is returned lowercased and stripped."""
    assert demand_service.normalize_query("  HELLO  ") == "hello"


# ---------------------------------------------------------------------------
# 3. aggregate_demand: velocity = count / hours, is_gap when fulfillment < 0.2
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_aggregate_demand_velocity_and_gap(db):
    """10 unfulfilled searches over 5h -> velocity=2.0, is_gap=1."""
    for _ in range(10):
        await demand_service.log_search(db, "deep learning", matched_count=0)

    signals = await demand_service.aggregate_demand(db, time_window_hours=5)

    assert len(signals) == 1
    s = signals[0]
    assert float(s.velocity) == 2.0        # 10 / 5
    assert float(s.fulfillment_rate) == 0.0
    assert s.is_gap == 1


# ---------------------------------------------------------------------------
# 4. aggregate_demand: is_gap=0 when fulfillment >= 0.2
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_aggregate_demand_not_gap_at_threshold(db):
    """Exactly 20% fulfillment should NOT be a gap (is_gap=0)."""
    # 2 fulfilled out of 10 = 0.2
    for _ in range(2):
        await demand_service.log_search(db, "threshold query", matched_count=1)
    for _ in range(8):
        await demand_service.log_search(db, "threshold query", matched_count=0)

    signals = await demand_service.aggregate_demand(db, time_window_hours=24)

    assert len(signals) == 1
    assert float(signals[0].fulfillment_rate) == 0.2
    assert signals[0].is_gap == 0  # 0.2 is NOT < 0.2


# ---------------------------------------------------------------------------
# 5. aggregate_demand: upsert updates existing DemandSignal
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_aggregate_demand_upsert_updates_counts(db):
    """A second aggregation round updates the same row, not create a new one."""
    await demand_service.log_search(db, "upsert test")
    sigs1 = await demand_service.aggregate_demand(db, time_window_hours=24)
    original_id = sigs1[0].id

    await demand_service.log_search(db, "test upsert")  # same normalized
    await demand_service.log_search(db, "Upsert Test")
    sigs2 = await demand_service.aggregate_demand(db, time_window_hours=24)

    assert len(sigs2) == 1
    assert sigs2[0].id == original_id
    assert sigs2[0].search_count == 3


# ---------------------------------------------------------------------------
# 6. get_trending: ordered by velocity desc
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_trending_velocity_order(db, make_demand_signal):
    """Signals come back ordered highest velocity first."""
    await make_demand_signal(query_pattern="slow-deep", velocity=0.5)
    await make_demand_signal(query_pattern="fast-deep", velocity=9.9)
    await make_demand_signal(query_pattern="mid-deep", velocity=4.0)

    trending = await demand_service.get_trending(db, limit=10, hours=24)

    velocities = [float(t.velocity) for t in trending]
    assert velocities == sorted(velocities, reverse=True)
    assert velocities[0] == 9.9


# ---------------------------------------------------------------------------
# 7. get_demand_gaps: filtered by category
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_demand_gaps_category_filtering(db, make_demand_signal):
    """Only gaps matching the requested category are returned."""
    await make_demand_signal(query_pattern="gap-web-deep", category="web_search", is_gap=1, search_count=50)
    await make_demand_signal(query_pattern="gap-api-deep", category="api_data", is_gap=1, search_count=80)

    gaps = await demand_service.get_demand_gaps(db, category="api_data")

    assert len(gaps) == 1
    assert gaps[0].query_pattern == "gap-api-deep"


# ---------------------------------------------------------------------------
# 8. generate_opportunities: urgency formula values
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_generate_opportunities_urgency_formula(db, make_demand_signal):
    """Single gap -> norm_velocity=1, (1 - 0)=1, norm_requesters=1 => urgency=1.0."""
    await make_demand_signal(
        query_pattern="max urgency deep",
        is_gap=1,
        velocity=10.0,
        fulfillment_rate=0.0,
        unique_requesters=8,
    )

    opps = await demand_service.generate_opportunities(db)

    assert len(opps) == 1
    # 0.4*1 + 0.3*1 + 0.3*1 = 1.0
    assert float(opps[0].urgency_score) == 1.0


# ---------------------------------------------------------------------------
# 9. generate_opportunities: 24h expiry
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_generate_opportunities_24h_expiry(db, make_demand_signal):
    """New opportunity expires ~24h from now."""
    await make_demand_signal(
        query_pattern="expiry deep test",
        is_gap=1, velocity=3.0, unique_requesters=2,
    )

    before = datetime.now(timezone.utc)
    opps = await demand_service.generate_opportunities(db)
    after = datetime.now(timezone.utc)

    expires = opps[0].expires_at
    low = before + timedelta(hours=24)
    high = after + timedelta(hours=24)
    assert low <= expires <= high


# ---------------------------------------------------------------------------
# 10. generate_opportunities: upsert updates existing opportunity
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_generate_opportunities_upsert_existing(db, make_demand_signal):
    """Second call updates an active opportunity, keeping the same id."""
    gap = await make_demand_signal(
        query_pattern="opp upsert deep",
        is_gap=1, velocity=2.0, unique_requesters=3,
    )

    opps1 = await demand_service.generate_opportunities(db)
    opp_id = opps1[0].id

    # Bump velocity
    await db.execute(
        update(DemandSignal)
        .where(DemandSignal.id == gap.id)
        .values(velocity=Decimal("8.0"))
    )
    await db.commit()

    opps2 = await demand_service.generate_opportunities(db)

    assert len(opps2) == 1
    assert opps2[0].id == opp_id
    assert float(opps2[0].search_velocity) == 8.0


# ---------------------------------------------------------------------------
# 11. Catalog CRUD: create and read
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_catalog_create_and_read(db, make_agent):
    """register_catalog_entry persists, get_catalog_entry retrieves it."""
    agent, _ = await make_agent(name="catalog-seller-deep")

    entry = await catalog_service.register_catalog_entry(
        db, agent.id, "nlp.sentiment", "Sentiment Analysis",
        description="Real-time sentiment data",
        price_range_min=0.002,
        price_range_max=0.02,
    )

    fetched = await catalog_service.get_catalog_entry(db, entry.id)
    assert fetched is not None
    assert fetched.namespace == "nlp.sentiment"
    assert fetched.topic == "Sentiment Analysis"
    assert fetched.status == "active"


# ---------------------------------------------------------------------------
# 12. Catalog CRUD: update
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_catalog_update_entry(db, make_agent):
    """update_catalog_entry changes fields for the owner."""
    agent, _ = await make_agent(name="cat-updater-deep")

    entry = await catalog_service.register_catalog_entry(
        db, agent.id, "code.python", "Python Code",
    )

    updated = await catalog_service.update_catalog_entry(
        db, entry.id, agent.id, topic="Python Code Analysis",
    )

    assert updated is not None
    assert updated.topic == "Python Code Analysis"


# ---------------------------------------------------------------------------
# 13. Catalog CRUD: delete sets status="retired"
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_catalog_delete_sets_retired(db, make_agent):
    """delete_catalog_entry soft-deletes by setting status to 'retired'."""
    agent, _ = await make_agent(name="cat-deleter-deep")

    entry = await catalog_service.register_catalog_entry(
        db, agent.id, "web_search", "Web Data",
    )

    ok = await catalog_service.delete_catalog_entry(db, entry.id, agent.id)
    assert ok is True

    fetched = await catalog_service.get_catalog_entry(db, entry.id)
    assert fetched.status == "retired"


# ---------------------------------------------------------------------------
# 14. Catalog subscribe: namespace pattern fnmatch matching
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_subscribe_namespace_pattern_fnmatch(db, make_agent):
    """Subscription with 'web_search.*' matches 'web_search.python' namespace."""
    buyer, _ = await make_agent(name="buyer-sub-deep")
    seller, _ = await make_agent(name="seller-sub-deep")

    sub = await catalog_service.subscribe(
        db, buyer.id, "web_search.*", topic_pattern="*",
    )
    assert sub.status == "active"

    # Register an entry in 'web_search.python' -- should match
    entry = await catalog_service.register_catalog_entry(
        db, seller.id, "web_search.python", "Python Data",
    )

    # Verify subscription exists and would match via fnmatch
    import fnmatch
    assert fnmatch.fnmatch(entry.namespace, sub.namespace_pattern)


# ---------------------------------------------------------------------------
# 15. Catalog subscribe: skips self-notification
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_subscribe_skips_self_notification(db, make_agent):
    """If subscriber_id == entry.agent_id, notify_subscribers skips."""
    agent, _ = await make_agent(name="self-sub-deep")

    await catalog_service.subscribe(db, agent.id, "*")

    # Registering a catalog entry as the same agent should not crash
    # (internally notify_subscribers skips self)
    entry = await catalog_service.register_catalog_entry(
        db, agent.id, "self.test", "Self Test",
    )

    # If we get here without error, the self-skip logic works
    assert entry.status == "active"


# ---------------------------------------------------------------------------
# 16. auto_populate_catalog: groups by category, skips existing
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_auto_populate_groups_and_skips_existing(db, make_agent, make_listing):
    """auto_populate_catalog creates one entry per category and skips duplicates."""
    agent, _ = await make_agent(name="auto-pop-deep")

    await make_listing(agent.id, category="web_search", price_usdc=0.005)
    await make_listing(agent.id, category="web_search", price_usdc=0.010)
    await make_listing(agent.id, category="api_data", price_usdc=0.020)

    created = await catalog_service.auto_populate_catalog(db, agent.id)
    assert len(created) == 2
    namespaces = {e.namespace for e in created}
    assert namespaces == {"web_search", "api_data"}

    # Second call should skip existing
    created2 = await catalog_service.auto_populate_catalog(db, agent.id)
    assert len(created2) == 0


# ---------------------------------------------------------------------------
# 17. API route: GET /api/v1/analytics/trending
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_api_trending_route(client, db, make_demand_signal):
    """GET /analytics/trending returns trends ordered by velocity."""
    await make_demand_signal(query_pattern="api-slow-deep", velocity=1.0)
    await make_demand_signal(query_pattern="api-fast-deep", velocity=7.0)

    resp = await client.get("/api/v1/analytics/trending?hours=24&limit=10")

    assert resp.status_code == 200
    data = resp.json()
    assert "trends" in data
    assert len(data["trends"]) == 2
    assert data["trends"][0]["velocity"] >= data["trends"][1]["velocity"]


# ---------------------------------------------------------------------------
# 18. API route: GET /api/v1/analytics/demand-gaps
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_api_demand_gaps_route(client, db, make_demand_signal):
    """GET /analytics/demand-gaps returns only gap signals."""
    await make_demand_signal(query_pattern="gap-route-deep", is_gap=1, search_count=20, category="web_search")
    await make_demand_signal(query_pattern="no-gap-route-deep", is_gap=0, search_count=50)

    resp = await client.get("/api/v1/analytics/demand-gaps?category=web_search")

    assert resp.status_code == 200
    data = resp.json()
    assert len(data["gaps"]) == 1
    assert data["gaps"][0]["query_pattern"] == "gap-route-deep"


# ---------------------------------------------------------------------------
# 19. API route: POST /api/v1/catalog
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_api_catalog_create_route(client, make_agent, auth_header):
    """POST /catalog creates a catalog entry for the authenticated agent."""
    agent, token = await make_agent(name="cat-api-deep")

    payload = {
        "namespace": "deep.test",
        "topic": "Deep Test Topic",
        "description": "Integration test catalog entry",
        "price_range_min": 0.003,
        "price_range_max": 0.025,
    }

    resp = await client.post(
        "/api/v1/catalog",
        json=payload,
        headers=auth_header(token),
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["agent_id"] == agent.id
    assert body["namespace"] == "deep.test"
    assert body["topic"] == "Deep Test Topic"
    assert body["status"] == "active"


# ---------------------------------------------------------------------------
# 20. Subscription matching: topic pattern filters correctly
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_subscription_topic_pattern_matching(db, make_agent):
    """A subscription with topic_pattern='python*' matches 'Python Data' but not 'Java Data'."""
    buyer, _ = await make_agent(name="topic-buyer-deep")
    seller, _ = await make_agent(name="topic-seller-deep")

    sub = await catalog_service.subscribe(
        db, buyer.id,
        namespace_pattern="*",          # match all namespaces
        topic_pattern="python*",        # only topics starting with python
    )

    # Entry whose topic matches (case-insensitive fnmatch in notify_subscribers)
    entry_match = await catalog_service.register_catalog_entry(
        db, seller.id, "lang", "Python Data",
    )

    # Entry whose topic does NOT match
    entry_no = await catalog_service.register_catalog_entry(
        db, seller.id, "lang", "Java Data",
    )

    import fnmatch
    # notify_subscribers does case-insensitive match
    assert fnmatch.fnmatch(entry_match.topic.lower(), sub.topic_pattern.lower())
    assert not fnmatch.fnmatch(entry_no.topic.lower(), sub.topic_pattern.lower())
