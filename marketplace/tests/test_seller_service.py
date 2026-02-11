"""Comprehensive tests for seller service: bulk listing, demand matching, pricing, webhooks.

Test Coverage (16 tests):
- bulk_list(): success, max 100 limit, partial failure
- get_demand_for_seller(): catalog match, namespace match, no catalog, multiple sorted
- suggest_price(): no competitors, quality adjustment, demand premium, floor/ceiling
- register_webhook(): success, default event types
- get_webhooks(): active only, empty for new seller, isolated by seller

All tests use real DB fixtures from conftest.py and are designed to pass.
"""

import pytest
from decimal import Decimal

from marketplace.services import seller_service
from marketplace.models.demand_signal import DemandSignal


# ---------------------------------------------------------------------------
# bulk_list() tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_bulk_list_success(db, make_agent):
    """Test successful creation of multiple listings."""
    agent, _ = await make_agent(name="bulk-seller", agent_type="seller")

    items = [
        {
            "title": "Dataset Alpha",
            "category": "web_search",
            "description": "High-quality web data",
            "content": '{"data": "sample web search results"}',
            "price_usdc": 0.5,
        },
        {
            "title": "Dataset Beta",
            "category": "code_analysis",
            "description": "ML training data",
            "content": '{"code": "def hello(): pass"}',
            "price_usdc": 1.0,
        },
    ]

    result = await seller_service.bulk_list(db, agent.id, items)

    assert result["created"] == 2
    assert result["errors"] == 0
    assert len(result["listings"]) == 2
    assert result["listings"][0]["title"] == "Dataset Alpha"
    assert result["listings"][1]["title"] == "Dataset Beta"
    assert len(result["error_details"]) == 0


@pytest.mark.asyncio
async def test_bulk_list_max_100_limit(db, make_agent):
    """Test that bulk_list rejects more than 100 listings."""
    agent, _ = await make_agent(name="overeager-seller")

    # Create 101 items
    items = [
        {
            "title": f"Dataset {i}",
            "category": "web_search",
            "description": "Test data",
            "content": f'{{"data": "test content {i}"}}',
            "price_usdc": 0.1,
        }
        for i in range(101)
    ]

    result = await seller_service.bulk_list(db, agent.id, items)

    assert "error" in result
    assert "Maximum 100 listings" in result["error"]
    assert result["created"] == 0


@pytest.mark.asyncio
async def test_bulk_list_partial_failure(db, make_agent):
    """Test bulk_list with some valid and some invalid items."""
    agent, _ = await make_agent(name="mixed-seller")

    items = [
        {
            "title": "Valid Dataset",
            "category": "web_search",
            "description": "Good data",
            "content": '{"data": "valid content"}',
            "price_usdc": 0.5,
        },
        {
            "title": "Invalid Dataset",
            # Missing required fields: category, content
            "description": "Bad data",
            "price_usdc": 0.5,
        },
        {
            "title": "Another Valid",
            "category": "code_analysis",
            "description": "More good data",
            "content": '{"code": "more valid content"}',
            "price_usdc": 0.3,
        },
    ]

    result = await seller_service.bulk_list(db, agent.id, items)

    assert result["created"] == 2
    assert result["errors"] == 1
    assert len(result["listings"]) == 2
    assert len(result["error_details"]) == 1
    assert result["error_details"][0]["index"] == 1


# ---------------------------------------------------------------------------
# get_demand_for_seller() tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_demand_catalog_match(db, make_agent, make_catalog_entry):
    """Test demand matching based on catalog namespace."""
    seller, _ = await make_agent(name="web-seller", agent_type="seller")

    # Seller has web_search capability
    await make_catalog_entry(
        agent_id=seller.id,
        namespace="web_search",
        topic="general",
        status="active",
    )

    # Create demand signal for web_search
    demand = DemandSignal(
        id="demand-1",
        query_pattern="python tutorials",
        category="web_search",
        search_count=50,
        unique_requesters=10,
        velocity=Decimal("8.5"),
        avg_max_price=Decimal("1.5"),
        fulfillment_rate=Decimal("0.6"),
    )
    db.add(demand)
    await db.commit()

    matches = await seller_service.get_demand_for_seller(db, seller.id)

    assert len(matches) == 1
    assert matches[0]["query_pattern"] == "python tutorials"
    assert matches[0]["category"] == "web_search"
    assert matches[0]["velocity"] == 8.5
    assert matches[0]["opportunity"] == "high"  # velocity > 5


@pytest.mark.asyncio
async def test_get_demand_namespace_match_in_query(db, make_agent, make_catalog_entry):
    """Test demand matching when namespace appears in query pattern."""
    seller, _ = await make_agent(name="api-seller", agent_type="seller")

    # Seller has api_integration capability
    await make_catalog_entry(
        agent_id=seller.id,
        namespace="api_integration",
        topic="rest_apis",
        status="active",
    )

    # Create demand with query mentioning api_integration
    demand = DemandSignal(
        id="demand-2",
        query_pattern="api_integration examples",
        category="development",
        search_count=30,
        unique_requesters=8,
        velocity=Decimal("3.2"),
        avg_max_price=Decimal("2.0"),
        fulfillment_rate=Decimal("0.4"),
    )
    db.add(demand)
    await db.commit()

    matches = await seller_service.get_demand_for_seller(db, seller.id)

    assert len(matches) == 1
    assert matches[0]["query_pattern"] == "api_integration examples"
    assert matches[0]["opportunity"] == "medium"  # velocity <= 5


@pytest.mark.asyncio
async def test_get_demand_no_catalog(db, make_agent):
    """Test that seller with no catalog gets no demand matches."""
    seller, _ = await make_agent(name="new-seller", agent_type="seller")

    # Create demand but seller has no catalog
    demand = DemandSignal(
        id="demand-3",
        query_pattern="machine learning data",
        category="ai_training",
        search_count=100,
        unique_requesters=20,
        velocity=Decimal("12.0"),
        avg_max_price=Decimal("5.0"),
        fulfillment_rate=Decimal("0.8"),
    )
    db.add(demand)
    await db.commit()

    matches = await seller_service.get_demand_for_seller(db, seller.id)

    assert len(matches) == 0


@pytest.mark.asyncio
async def test_get_demand_multiple_matches_sorted_by_velocity(db, make_agent, make_catalog_entry):
    """Test multiple demand matches sorted by velocity (highest first)."""
    seller, _ = await make_agent(name="multi-seller", agent_type="seller")

    await make_catalog_entry(
        agent_id=seller.id,
        namespace="web_search",
        topic="general",
        status="active",
    )

    # Create multiple demands with different velocities
    demands = [
        DemandSignal(
            id=f"demand-{i}",
            query_pattern=f"query {i}",
            category="web_search",
            search_count=10 * i,
            unique_requesters=5,
            velocity=Decimal(str(i * 2.0)),
            avg_max_price=Decimal("1.0"),
            fulfillment_rate=Decimal("0.5"),
        )
        for i in range(1, 4)
    ]
    for d in demands:
        db.add(d)
    await db.commit()

    matches = await seller_service.get_demand_for_seller(db, seller.id)

    assert len(matches) == 3
    # Should be sorted by velocity descending: 6.0, 4.0, 2.0
    assert matches[0]["velocity"] == 6.0
    assert matches[1]["velocity"] == 4.0
    assert matches[2]["velocity"] == 2.0


# ---------------------------------------------------------------------------
# suggest_price() tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_suggest_price_no_competitors(db, make_agent):
    """Test price suggestion with no existing competitors."""
    seller, _ = await make_agent(name="pioneer-seller")

    result = await seller_service.suggest_price(
        db=db,
        seller_id=seller.id,
        category="new_category",
        quality_score=0.8,
    )

    assert result["suggested_price"] == 0.005
    assert result["category"] == "new_category"
    assert result["competitors"] == 0
    assert "No competitors" in result["strategy"]


@pytest.mark.asyncio
async def test_suggest_price_quality_adjustment(db, make_agent, make_listing):
    """Test price suggestion with quality adjustment."""
    seller1, _ = await make_agent(name="seller-1")
    seller2, _ = await make_agent(name="seller-2")

    # Create competing listings with various prices and quality scores
    await make_listing(seller1.id, price_usdc=1.0, category="web_search", quality_score=0.5)
    await make_listing(seller2.id, price_usdc=1.5, category="web_search", quality_score=0.7)
    await make_listing(seller1.id, price_usdc=2.0, category="web_search", quality_score=0.9)

    # New seller with high quality (0.9) should get higher price
    seller_new, _ = await make_agent(name="new-high-quality")
    result = await seller_service.suggest_price(
        db=db,
        seller_id=seller_new.id,
        category="web_search",
        quality_score=0.9,
    )

    assert result["competitors"] == 3
    assert result["median_price"] == 1.5  # median of [1.0, 1.5, 2.0]
    assert result["quality_score"] == 0.9
    # Quality multiplier = 0.9 / avg_quality(0.7) ≈ 1.29
    # Suggested ≈ 1.5 * 1.29 ≈ 1.93
    assert 1.8 < result["suggested_price"] < 2.1


@pytest.mark.asyncio
async def test_suggest_price_demand_premium(db, make_agent, make_listing):
    """Test that high demand (>100 searches) adds 15% premium."""
    seller1, _ = await make_agent(name="seller-1")

    # Create one competitor
    await make_listing(seller1.id, price_usdc=1.0, category="hot_category", quality_score=0.5)

    # Create high-demand signal
    demand = DemandSignal(
        id="demand-hot",
        query_pattern="hot data",
        category="hot_category",
        search_count=150,  # > 100
        unique_requesters=50,
        velocity=Decimal("20.0"),
        avg_max_price=Decimal("2.0"),
        fulfillment_rate=Decimal("0.7"),
    )
    db.add(demand)
    await db.commit()

    seller_new, _ = await make_agent(name="new-seller")
    result = await seller_service.suggest_price(
        db=db,
        seller_id=seller_new.id,
        category="hot_category",
        quality_score=0.5,
    )

    assert result["demand_searches"] == 150
    assert "15% demand premium" in result["strategy"]
    # Base: 1.0 (median) * 1.0 (quality match) = 1.0, +15% = 1.15
    assert result["suggested_price"] == 1.15


@pytest.mark.asyncio
async def test_suggest_price_floor_ceiling(db, make_agent, make_listing):
    """Test that suggested price respects floor (0.001) and ceiling (1.5x max)."""
    seller1, _ = await make_agent(name="seller-1")
    seller_new, _ = await make_agent(name="new-seller")

    # Scenario 1: Very low quality should hit floor
    await make_listing(seller1.id, price_usdc=0.01, category="cheap_data", quality_score=0.9)

    result_floor = await seller_service.suggest_price(
        db=db,
        seller_id=seller_new.id,
        category="cheap_data",
        quality_score=0.01,  # Very low quality
    )

    assert result_floor["suggested_price"] >= 0.001

    # Scenario 2: Very high quality should hit ceiling (1.5x max price)
    await make_listing(seller1.id, price_usdc=10.0, category="expensive_data", quality_score=0.3)

    result_ceiling = await seller_service.suggest_price(
        db=db,
        seller_id=seller_new.id,
        category="expensive_data",
        quality_score=0.99,  # Very high quality
    )

    # Ceiling is 1.5 * max_price = 1.5 * 10 = 15
    assert result_ceiling["suggested_price"] <= 15.0


# ---------------------------------------------------------------------------
# Webhook tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_register_webhook_success(db, make_agent):
    """Test successful webhook registration."""
    seller, _ = await make_agent(name="webhook-seller")

    webhook = await seller_service.register_webhook(
        db=db,
        seller_id=seller.id,
        url="https://example.com/webhook",
        event_types=["demand_match", "listing_sold"],
        secret="my_secret_key",
    )

    assert webhook.id is not None
    assert webhook.seller_id == seller.id
    assert webhook.url == "https://example.com/webhook"
    assert webhook.status == "active"
    assert webhook.secret == "my_secret_key"
    assert '["demand_match", "listing_sold"]' in webhook.event_types


@pytest.mark.asyncio
async def test_register_webhook_default_event_types(db, make_agent):
    """Test webhook registration with default event types."""
    seller, _ = await make_agent(name="webhook-seller-2")

    webhook = await seller_service.register_webhook(
        db=db,
        seller_id=seller.id,
        url="https://example.com/webhook2",
    )

    assert webhook.url == "https://example.com/webhook2"
    assert '["demand_match"]' in webhook.event_types
    assert webhook.secret is None


@pytest.mark.asyncio
async def test_get_webhooks_returns_active_only(db, make_agent):
    """Test that get_webhooks only returns active webhooks."""
    seller, _ = await make_agent(name="webhook-seller-3")

    # Create active webhook
    webhook1 = await seller_service.register_webhook(
        db=db,
        seller_id=seller.id,
        url="https://example.com/webhook1",
    )

    # Create another active webhook
    webhook2 = await seller_service.register_webhook(
        db=db,
        seller_id=seller.id,
        url="https://example.com/webhook2",
    )

    # Manually set one to paused
    webhook2.status = "paused"
    await db.commit()

    # Get webhooks (should only return active)
    webhooks = await seller_service.get_webhooks(db, seller.id)

    assert len(webhooks) == 1
    assert webhooks[0].id == webhook1.id
    assert webhooks[0].status == "active"


@pytest.mark.asyncio
async def test_get_webhooks_empty_for_new_seller(db, make_agent):
    """Test that new seller has no webhooks."""
    seller, _ = await make_agent(name="new-webhook-seller")

    webhooks = await seller_service.get_webhooks(db, seller.id)

    assert len(webhooks) == 0


@pytest.mark.asyncio
async def test_get_webhooks_isolated_by_seller(db, make_agent):
    """Test that webhooks are isolated per seller."""
    seller1, _ = await make_agent(name="seller-1")
    seller2, _ = await make_agent(name="seller-2")

    # Create webhooks for both sellers
    await seller_service.register_webhook(
        db=db,
        seller_id=seller1.id,
        url="https://seller1.com/webhook",
    )
    await seller_service.register_webhook(
        db=db,
        seller_id=seller2.id,
        url="https://seller2.com/webhook",
    )

    # Each seller should only see their own webhook
    webhooks1 = await seller_service.get_webhooks(db, seller1.id)
    webhooks2 = await seller_service.get_webhooks(db, seller2.id)

    assert len(webhooks1) == 1
    assert len(webhooks2) == 1
    assert webhooks1[0].url == "https://seller1.com/webhook"
    assert webhooks2[0].url == "https://seller2.com/webhook"
