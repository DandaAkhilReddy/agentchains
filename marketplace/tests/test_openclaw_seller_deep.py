"""Deep tests for OpenClaw webhook CRUD, seller bulk listing, price suggestion, demand matching.

20 tests covering:
  1. register_webhook creates active webhook
  2. register_webhook upsert resets failure_count
  3. delete_webhook hard deletes row
  4. delete_webhook wrong agent returns False
  5. get_status connected=True with active webhook
  6. get_status connected=False without webhook
  7. format_event_message demand_spike format
  8. format_event_message unknown event fallback
  9. format_event_message missing keys fallback
 10. dispatch filters by event_type
 11. dispatch filters by category
 12. dispatch filters by min_urgency
 13. bulk_list all items created
 14. bulk_list exceeding limit rejected
 15. bulk_list partial failure handling
 16. suggest_price no competitors default
 17. suggest_price quality-adjusted median
 18. suggest_price demand premium
 19. get_demand_for_seller matches catalog categories
 20. get_demand_for_seller no catalog returns empty
"""

import json
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from marketplace.models.demand_signal import DemandSignal
from marketplace.models.openclaw_webhook import OpenClawWebhook
from marketplace.services import openclaw_service, seller_service
from marketplace.services.openclaw_service import (
    format_event_message,
    register_webhook as oc_register,
    list_webhooks as oc_list,
    delete_webhook as oc_delete,
    get_status as oc_status,
)


# =========================================================================
# 1. register_webhook creates active webhook
# =========================================================================

@pytest.mark.asyncio
async def test_register_webhook_creates_active(db: AsyncSession, make_agent):
    """register_webhook creates a new OpenClawWebhook with status='active'."""
    agent, _ = await make_agent(name="deep-oc-reg")

    webhook = await oc_register(
        db,
        agent_id=agent.id,
        gateway_url="https://gw.deep.test/hooks/agent",
        bearer_token="deep-bearer-123",
        event_types=["demand_spike", "transaction"],
        filters={"categories": ["web_search"]},
    )

    assert webhook.id is not None
    assert webhook.agent_id == agent.id
    assert webhook.gateway_url == "https://gw.deep.test/hooks/agent"
    assert webhook.bearer_token == "deep-bearer-123"
    assert webhook.status == "active"
    assert webhook.failure_count == 0
    types = json.loads(webhook.event_types)
    assert types == ["demand_spike", "transaction"]
    filters = json.loads(webhook.filters)
    assert filters == {"categories": ["web_search"]}


# =========================================================================
# 2. register_webhook upsert resets failure_count
# =========================================================================

@pytest.mark.asyncio
async def test_upsert_webhook_resets_failure_count(db: AsyncSession, make_agent):
    """Re-registering an active webhook resets failure_count to 0 and updates fields."""
    agent, _ = await make_agent(name="deep-oc-upsert")

    first = await oc_register(
        db, agent.id,
        gateway_url="https://old-gw.test/hooks",
        bearer_token="old-tok",
    )
    # Simulate failures
    first.failure_count = 4
    await db.commit()

    second = await oc_register(
        db, agent.id,
        gateway_url="https://new-gw.test/hooks",
        bearer_token="new-tok",
        event_types=["listing_created"],
    )

    assert first.id == second.id  # same row updated
    assert second.failure_count == 0
    assert second.gateway_url == "https://new-gw.test/hooks"
    assert second.bearer_token == "new-tok"
    assert second.status == "active"


# =========================================================================
# 3. delete_webhook hard deletes the row
# =========================================================================

@pytest.mark.asyncio
async def test_delete_webhook_hard_delete(db: AsyncSession, make_agent):
    """delete_webhook removes the row from the database entirely."""
    agent, _ = await make_agent(name="deep-oc-del")

    webhook = await oc_register(db, agent.id, "https://gw.test/hooks", "tok")
    webhook_id = webhook.id

    result = await oc_delete(db, webhook_id, agent.id)
    assert result is True

    # Verify row is gone from database
    row = await db.execute(
        select(OpenClawWebhook).where(OpenClawWebhook.id == webhook_id)
    )
    assert row.scalar_one_or_none() is None


# =========================================================================
# 4. delete_webhook wrong agent returns False
# =========================================================================

@pytest.mark.asyncio
async def test_delete_webhook_wrong_agent_returns_false(db: AsyncSession, make_agent):
    """delete_webhook returns False when a different agent tries to delete."""
    owner, _ = await make_agent(name="deep-oc-owner")
    stranger, _ = await make_agent(name="deep-oc-stranger")

    webhook = await oc_register(db, owner.id, "https://gw.test/hooks", "tok")

    result = await oc_delete(db, webhook.id, stranger.id)
    assert result is False

    # Webhook still exists
    webhooks = await oc_list(db, owner.id)
    assert len(webhooks) == 1


# =========================================================================
# 5. get_status connected=True with active webhook
# =========================================================================

@pytest.mark.asyncio
async def test_status_connected_true_with_active_webhook(db: AsyncSession, make_agent):
    """get_status returns connected=True when agent has an active webhook."""
    agent, _ = await make_agent(name="deep-oc-status-on")

    await oc_register(db, agent.id, "https://gw.test/hooks", "tok")

    status = await oc_status(db, agent.id)
    assert status["connected"] is True
    assert status["active_count"] == 1
    assert status["webhooks_count"] == 1


# =========================================================================
# 6. get_status connected=False without webhook
# =========================================================================

@pytest.mark.asyncio
async def test_status_connected_false_without_webhook(db: AsyncSession, make_agent):
    """get_status returns connected=False when agent has no webhooks."""
    agent, _ = await make_agent(name="deep-oc-status-off")

    status = await oc_status(db, agent.id)
    assert status["connected"] is False
    assert status["active_count"] == 0
    assert status["webhooks_count"] == 0
    assert status["last_delivery"] is None


# =========================================================================
# 7. format_event_message demand_spike format
# =========================================================================

@pytest.mark.asyncio
async def test_format_demand_spike_message():
    """format_event_message produces readable demand_spike text with all data fields."""
    msg = format_event_message("demand_spike", {
        "query_pattern": "neural networks",
        "category": "ai_training",
        "velocity": 55.0,
    })

    assert "neural networks" in msg
    assert "ai_training" in msg
    assert "55" in msg
    assert "Demand spike" in msg


# =========================================================================
# 8. format_event_message unknown event fallback
# =========================================================================

@pytest.mark.asyncio
async def test_format_unknown_event_fallback():
    """Unknown event_type falls back to JSON dump string."""
    msg = format_event_message("brand_new_event", {"foo": "bar", "count": 99})

    assert "brand_new_event" in msg
    assert "bar" in msg
    assert "99" in msg


# =========================================================================
# 9. format_event_message missing keys fallback
# =========================================================================

@pytest.mark.asyncio
async def test_format_missing_keys_fallback():
    """Known event type with missing template keys falls back to JSON dump."""
    # demand_spike template requires query_pattern, category, velocity
    # We only supply query_pattern — KeyError triggers fallback
    msg = format_event_message("demand_spike", {"query_pattern": "partial data"})

    assert "demand_spike" in msg
    assert "partial data" in msg


# =========================================================================
# 10. dispatch filters by event_type
# =========================================================================

@pytest.mark.asyncio
@patch("marketplace.services.openclaw_service.deliver_event", new_callable=AsyncMock)
async def test_dispatch_filters_by_event_type(mock_deliver, db: AsyncSession, make_agent):
    """dispatch_to_openclaw_webhooks only delivers to webhooks subscribing to the event type."""
    mock_deliver.return_value = True

    agent, _ = await make_agent(name="deep-dispatch-evt")
    await oc_register(
        db, agent.id, "https://gw.test/hooks", "tok",
        event_types=["listing_created"],
    )

    # Dispatch a demand_spike — agent only subscribes to listing_created
    await openclaw_service.dispatch_to_openclaw_webhooks(db, "demand_spike", {
        "query_pattern": "test", "category": "web_search", "velocity": 5,
    })
    assert mock_deliver.call_count == 0

    # Dispatch a listing_created — should match
    mock_deliver.reset_mock()
    await openclaw_service.dispatch_to_openclaw_webhooks(db, "listing_created", {
        "title": "New Data", "category": "web_search", "price_usdc": 0.01,
    })
    assert mock_deliver.call_count == 1


# =========================================================================
# 11. dispatch filters by category
# =========================================================================

@pytest.mark.asyncio
@patch("marketplace.services.openclaw_service.deliver_event", new_callable=AsyncMock)
async def test_dispatch_filters_by_category(mock_deliver, db: AsyncSession, make_agent):
    """dispatch skips webhooks whose category filter does not match the event category."""
    mock_deliver.return_value = True

    agent, _ = await make_agent(name="deep-dispatch-cat")
    await oc_register(
        db, agent.id, "https://gw.test/hooks", "tok",
        event_types=["demand_spike"],
        filters={"categories": ["science"]},
    )

    # Dispatch with category=finance — does NOT match filter
    await openclaw_service.dispatch_to_openclaw_webhooks(db, "demand_spike", {
        "query_pattern": "stocks", "category": "finance", "velocity": 10,
    })
    assert mock_deliver.call_count == 0

    # Dispatch with category=science — matches filter
    mock_deliver.reset_mock()
    await openclaw_service.dispatch_to_openclaw_webhooks(db, "demand_spike", {
        "query_pattern": "physics", "category": "science", "velocity": 10,
    })
    assert mock_deliver.call_count == 1


# =========================================================================
# 12. dispatch filters by min_urgency
# =========================================================================

@pytest.mark.asyncio
@patch("marketplace.services.openclaw_service.deliver_event", new_callable=AsyncMock)
async def test_dispatch_filters_by_min_urgency(mock_deliver, db: AsyncSession, make_agent):
    """dispatch skips events whose urgency_score is below the webhook min_urgency filter."""
    mock_deliver.return_value = True

    agent, _ = await make_agent(name="deep-dispatch-urg")
    await oc_register(
        db, agent.id, "https://gw.test/hooks", "tok",
        event_types=["demand_spike"],
        filters={"min_urgency": 0.7},
    )

    # Low urgency — should be skipped
    await openclaw_service.dispatch_to_openclaw_webhooks(db, "demand_spike", {
        "query_pattern": "low", "category": "web_search", "velocity": 1,
        "urgency_score": 0.3,
    })
    assert mock_deliver.call_count == 0

    # High urgency — should be delivered
    mock_deliver.reset_mock()
    await openclaw_service.dispatch_to_openclaw_webhooks(db, "demand_spike", {
        "query_pattern": "high", "category": "web_search", "velocity": 20,
        "urgency_score": 0.9,
    })
    assert mock_deliver.call_count == 1


# =========================================================================
# 13. bulk_list all items created
# =========================================================================

@pytest.mark.asyncio
async def test_bulk_list_all_items_created(db: AsyncSession, make_agent):
    """bulk_list successfully creates all valid items."""
    agent, _ = await make_agent(name="deep-bulk-all", agent_type="seller")

    items = [
        {
            "title": f"Deep Listing {i}",
            "category": "web_search",
            "content": f'{{"data": "item-{i}"}}',
            "price_usdc": 0.01,
        }
        for i in range(5)
    ]

    result = await seller_service.bulk_list(db, agent.id, items)

    assert result["created"] == 5
    assert result["errors"] == 0
    assert len(result["listings"]) == 5
    titles = [l["title"] for l in result["listings"]]
    assert titles == [f"Deep Listing {i}" for i in range(5)]


# =========================================================================
# 14. bulk_list exceeding limit rejected
# =========================================================================

@pytest.mark.asyncio
async def test_bulk_list_exceeding_limit_rejected(db: AsyncSession, make_agent):
    """bulk_list with more than 100 items returns error immediately."""
    agent, _ = await make_agent(name="deep-bulk-over", agent_type="seller")

    items = [
        {
            "title": f"Item {i}",
            "category": "web_search",
            "content": f'{{"i": {i}}}',
            "price_usdc": 0.01,
        }
        for i in range(101)
    ]

    result = await seller_service.bulk_list(db, agent.id, items)

    assert "error" in result
    assert "Maximum 100" in result["error"]
    assert result["created"] == 0


# =========================================================================
# 15. bulk_list partial failure handling
# =========================================================================

@pytest.mark.asyncio
async def test_bulk_list_partial_failure(db: AsyncSession, make_agent):
    """bulk_list reports partial success when some items fail validation."""
    agent, _ = await make_agent(name="deep-bulk-partial", agent_type="seller")

    items = [
        # Valid
        {
            "title": "Valid Alpha",
            "category": "web_search",
            "content": '{"valid": true}',
            "price_usdc": 0.01,
        },
        # Invalid: missing content and category
        {
            "title": "Bad Beta",
            "price_usdc": 0.01,
        },
        # Valid
        {
            "title": "Valid Gamma",
            "category": "code_analysis",
            "content": '{"code": "x = 1"}',
            "price_usdc": 0.05,
        },
    ]

    result = await seller_service.bulk_list(db, agent.id, items)

    assert result["created"] == 2
    assert result["errors"] == 1
    assert len(result["error_details"]) == 1
    assert result["error_details"][0]["index"] == 1


# =========================================================================
# 16. suggest_price no competitors default
# =========================================================================

@pytest.mark.asyncio
async def test_suggest_price_no_competitors_default(db: AsyncSession, make_agent):
    """suggest_price returns $0.005 default when no competitors exist."""
    seller, _ = await make_agent(name="deep-price-none")

    result = await seller_service.suggest_price(
        db, seller.id, category="computation", quality_score=0.8,
    )

    assert result["suggested_price"] == 0.005
    assert result["competitors"] == 0
    assert result["category"] == "computation"
    assert "No competitors" in result["strategy"]


# =========================================================================
# 17. suggest_price quality-adjusted median
# =========================================================================

@pytest.mark.asyncio
async def test_suggest_price_quality_adjusted_median(db: AsyncSession, make_agent, make_listing):
    """suggest_price returns quality-adjusted median price when competitors exist."""
    s1, _ = await make_agent(name="deep-comp-1")
    s2, _ = await make_agent(name="deep-comp-2")

    # Two competitors at $1.00 and $3.00, both quality 0.5
    await make_listing(s1.id, price_usdc=1.00, category="web_search", quality_score=0.5)
    await make_listing(s2.id, price_usdc=3.00, category="web_search", quality_score=0.5)

    seller, _ = await make_agent(name="deep-price-adj")

    # quality_score=1.0, avg_quality=0.5 => multiplier=2.0
    # median of [1.0, 3.0] = 2.0
    # suggested = 2.0 * 2.0 = 4.0, but capped at max(prices)*1.5 = 4.5
    result = await seller_service.suggest_price(
        db, seller.id, category="web_search", quality_score=1.0,
    )

    assert result["competitors"] == 2
    assert result["median_price"] == 2.0
    assert "Quality-adjusted median" in result["strategy"]
    # The price should be 4.0 (2.0 * 2.0x multiplier), capped at 4.5
    assert result["suggested_price"] == 4.0


# =========================================================================
# 18. suggest_price demand premium
# =========================================================================

@pytest.mark.asyncio
async def test_suggest_price_demand_premium(db: AsyncSession, make_agent, make_listing):
    """High demand (>100 total searches) adds 15% premium."""
    comp, _ = await make_agent(name="deep-comp-demand")
    await make_listing(comp.id, price_usdc=2.0, category="web_search", quality_score=0.5)

    # Demand signal with search_count > 100
    demand = DemandSignal(
        id="deep-demand-premium",
        query_pattern="high demand deep query",
        category="web_search",
        search_count=200,
        unique_requesters=80,
        velocity=Decimal("30.0"),
        fulfillment_rate=Decimal("0.5"),
    )
    db.add(demand)
    await db.commit()

    seller, _ = await make_agent(name="deep-premium-seller")
    result = await seller_service.suggest_price(
        db, seller.id, category="web_search", quality_score=0.5,
    )

    assert result["demand_searches"] == 200
    assert "15% demand premium" in result["strategy"]
    # median=2.0, multiplier=0.5/0.5=1.0, base=2.0, +15% => 2.3
    assert result["suggested_price"] == 2.3


# =========================================================================
# 19. get_demand_for_seller matches catalog categories
# =========================================================================

@pytest.mark.asyncio
async def test_get_demand_matches_catalog_categories(
    db: AsyncSession, make_agent, make_catalog_entry,
):
    """get_demand_for_seller returns demands matching seller's catalog categories."""
    seller, _ = await make_agent(name="deep-demand-match", agent_type="seller")

    await make_catalog_entry(agent_id=seller.id, namespace="web_search", topic="tutorials")

    # Matching demand — same category
    matching = DemandSignal(
        id="deep-ds-match",
        query_pattern="python web scraping",
        category="web_search",
        search_count=30,
        unique_requesters=10,
        velocity=Decimal("8.0"),
        avg_max_price=Decimal("0.5"),
        fulfillment_rate=Decimal("0.3"),
    )
    # Non-matching demand — different category
    non_matching = DemandSignal(
        id="deep-ds-nomatch",
        query_pattern="financial reports data",
        category="finance",
        search_count=20,
        unique_requesters=5,
        velocity=Decimal("3.0"),
        fulfillment_rate=Decimal("0.5"),
    )
    db.add_all([matching, non_matching])
    await db.commit()

    matches = await seller_service.get_demand_for_seller(db, seller.id)

    assert len(matches) == 1
    assert matches[0]["query_pattern"] == "python web scraping"
    assert matches[0]["category"] == "web_search"
    assert matches[0]["velocity"] == 8.0
    assert matches[0]["opportunity"] == "high"  # velocity > 5


# =========================================================================
# 20. get_demand_for_seller no catalog returns empty
# =========================================================================

@pytest.mark.asyncio
async def test_get_demand_no_catalog_returns_empty(db: AsyncSession, make_agent):
    """Seller with no catalog entries gets an empty demand list."""
    seller, _ = await make_agent(name="deep-demand-empty", agent_type="seller")

    # Create demand signals in the system
    demand = DemandSignal(
        id="deep-ds-orphan",
        query_pattern="machine learning datasets",
        category="ai_training",
        search_count=100,
        unique_requesters=40,
        velocity=Decimal("12.0"),
        fulfillment_rate=Decimal("0.2"),
    )
    db.add(demand)
    await db.commit()

    matches = await seller_service.get_demand_for_seller(db, seller.id)
    assert matches == []
