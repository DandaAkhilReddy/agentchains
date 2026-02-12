"""Integration tests for seller service and OpenClaw webhook service.

Test Coverage (20 tests):
  SELLER SERVICE (10):
    1. test_bulk_list_success — create multiple listings at once
    2. test_bulk_list_max_100 — more than 100 returns error
    3. test_bulk_list_partial_errors — some items fail, others succeed
    4. test_get_demand_for_seller — cross-references demand signals with seller catalog
    5. test_get_demand_no_catalog — returns empty if seller has no catalog entries
    6. test_suggest_price_no_competitors — returns default $0.005
    7. test_suggest_price_with_competitors — returns quality-adjusted median
    8. test_register_webhook — creates SellerWebhook record
    9. test_get_webhooks — returns active webhooks for seller
   10. test_suggest_price_demand_premium — high demand (>100 searches) adds 15% premium

  OPENCLAW SERVICE (10):
   11. test_openclaw_register_webhook — creates OpenClawWebhook
   12. test_openclaw_register_webhook_update_existing — second registration updates existing
   13. test_openclaw_list_webhooks — lists webhooks for agent
   14. test_openclaw_delete_webhook — deletes webhook
   15. test_openclaw_delete_webhook_wrong_agent — returns False if not owner
   16. test_openclaw_get_status — returns connected/active counts
   17. test_openclaw_format_event_message — formats known event types
   18. test_openclaw_format_event_unknown — unknown event returns JSON fallback
   19. test_openclaw_deliver_event_mock — mock httpx to test deliver_event
   20. test_openclaw_dispatch_filters — dispatch respects event_type and category filters

All tests use fixtures from conftest.py and are designed to pass.
"""

import json
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from marketplace.models.demand_signal import DemandSignal
from marketplace.models.openclaw_webhook import OpenClawWebhook
from marketplace.schemas.listing import ListingCreateRequest
from marketplace.services import seller_service, openclaw_service
from marketplace.services.openclaw_service import (
    format_event_message,
    deliver_event,
    register_webhook as oc_register,
    list_webhooks as oc_list,
    delete_webhook as oc_delete,
    get_status as oc_status,
)


# ===========================================================================
# SELLER SERVICE — 10 tests
# ===========================================================================


# ---------------------------------------------------------------------------
# 1. test_bulk_list_success
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_bulk_list_success(db: AsyncSession, make_agent):
    """Create multiple listings at once — all items valid."""
    agent, _ = await make_agent(name="int-bulk-seller", agent_type="seller")

    items = [
        {
            "title": "Web Scraping Results Q1",
            "category": "web_search",
            "content": '{"results": ["page1", "page2"]}',
            "price_usdc": 0.01,
        },
        {
            "title": "Code Review Dataset",
            "category": "code_analysis",
            "content": '{"code": "def fib(n): ..."}',
            "price_usdc": 0.05,
        },
        {
            "title": "API Response Cache",
            "category": "api_response",
            "content": '{"status": 200, "body": "ok"}',
            "price_usdc": 0.02,
        },
    ]

    result = await seller_service.bulk_list(db, agent.id, items)

    assert result["created"] == 3
    assert result["errors"] == 0
    assert len(result["listings"]) == 3
    assert len(result["error_details"]) == 0
    # Verify each listing title was persisted in order
    titles = [l["title"] for l in result["listings"]]
    assert titles == [
        "Web Scraping Results Q1",
        "Code Review Dataset",
        "API Response Cache",
    ]


# ---------------------------------------------------------------------------
# 2. test_bulk_list_max_100
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_bulk_list_max_100(db: AsyncSession, make_agent):
    """More than 100 items returns an error immediately."""
    agent, _ = await make_agent(name="int-over-seller")

    items = [
        {
            "title": f"Item {i}",
            "category": "web_search",
            "content": f'{{"data": "{i}"}}',
            "price_usdc": 0.01,
        }
        for i in range(101)
    ]

    result = await seller_service.bulk_list(db, agent.id, items)

    assert "error" in result
    assert "Maximum 100" in result["error"]
    assert result["created"] == 0


# ---------------------------------------------------------------------------
# 3. test_bulk_list_partial_errors
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_bulk_list_partial_errors(db: AsyncSession, make_agent):
    """Some items fail validation, others succeed."""
    agent, _ = await make_agent(name="int-partial-seller")

    items = [
        # Valid
        {
            "title": "Good Listing A",
            "category": "web_search",
            "content": '{"good": true}',
            "price_usdc": 0.01,
        },
        # Invalid — missing 'category' and 'content'
        {
            "title": "Bad Listing B",
            "price_usdc": 0.01,
        },
        # Invalid — price is negative (violates gt=0)
        {
            "title": "Bad Listing C",
            "category": "web_search",
            "content": '{"bad": true}',
            "price_usdc": -5,
        },
        # Valid
        {
            "title": "Good Listing D",
            "category": "document_summary",
            "content": '{"summary": "hello"}',
            "price_usdc": 0.03,
        },
    ]

    result = await seller_service.bulk_list(db, agent.id, items)

    assert result["created"] == 2
    assert result["errors"] == 2
    assert len(result["listings"]) == 2
    assert len(result["error_details"]) == 2
    # Errors should be at indices 1 and 3 (0-based)
    error_indices = {e["index"] for e in result["error_details"]}
    assert error_indices == {1, 2}


# ---------------------------------------------------------------------------
# 4. test_get_demand_for_seller
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_demand_for_seller(
    db: AsyncSession, make_agent, make_catalog_entry, make_demand_signal,
):
    """Cross-references demand signals with seller catalog entries."""
    seller, _ = await make_agent(name="int-demand-seller", agent_type="seller")

    # Seller's catalog: web_search namespace
    await make_catalog_entry(
        agent_id=seller.id, namespace="web_search", topic="general",
    )

    # Matching demand signal — same category as seller's namespace
    signal = DemandSignal(
        id="int-demand-1",
        query_pattern="trending search results",
        category="web_search",
        search_count=42,
        unique_requesters=12,
        velocity=Decimal("7.5"),
        avg_max_price=Decimal("1.0"),
        fulfillment_rate=Decimal("0.4"),
    )
    db.add(signal)

    # Non-matching demand signal — seller has no capability here
    non_match = DemandSignal(
        id="int-demand-2",
        query_pattern="financial data",
        category="finance",
        search_count=20,
        unique_requesters=8,
        velocity=Decimal("3.0"),
        avg_max_price=Decimal("2.0"),
        fulfillment_rate=Decimal("0.2"),
    )
    db.add(non_match)
    await db.commit()

    matches = await seller_service.get_demand_for_seller(db, seller.id)

    assert len(matches) == 1
    assert matches[0]["query_pattern"] == "trending search results"
    assert matches[0]["category"] == "web_search"
    assert matches[0]["velocity"] == 7.5
    assert matches[0]["total_searches"] == 42
    assert matches[0]["opportunity"] == "high"  # velocity > 5


# ---------------------------------------------------------------------------
# 5. test_get_demand_no_catalog
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_demand_no_catalog(db: AsyncSession, make_agent, make_demand_signal):
    """Seller with no catalog entries gets empty demand list."""
    seller, _ = await make_agent(name="int-no-catalog-seller", agent_type="seller")

    # There IS demand in the system, but seller has no catalog
    await make_demand_signal(
        query_pattern="machine learning data", category="ai_training",
        search_count=200, velocity=15.0,
    )

    matches = await seller_service.get_demand_for_seller(db, seller.id)

    assert matches == []


# ---------------------------------------------------------------------------
# 6. test_suggest_price_no_competitors
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_suggest_price_no_competitors(db: AsyncSession, make_agent):
    """No competitors in the category — returns default $0.005."""
    seller, _ = await make_agent(name="int-pioneer-seller")

    result = await seller_service.suggest_price(
        db=db,
        seller_id=seller.id,
        category="computation",
        quality_score=0.7,
    )

    assert result["suggested_price"] == 0.005
    assert result["competitors"] == 0
    assert result["category"] == "computation"
    assert "No competitors" in result["strategy"]


# ---------------------------------------------------------------------------
# 7. test_suggest_price_with_competitors
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_suggest_price_with_competitors(db: AsyncSession, make_agent, make_listing):
    """Returns quality-adjusted median when competitors exist."""
    s1, _ = await make_agent(name="int-comp-1")
    s2, _ = await make_agent(name="int-comp-2")
    s3, _ = await make_agent(name="int-comp-3")

    # Create competing listings in "web_search"
    await make_listing(s1.id, price_usdc=0.50, category="web_search", quality_score=0.4)
    await make_listing(s2.id, price_usdc=1.00, category="web_search", quality_score=0.6)
    await make_listing(s3.id, price_usdc=1.50, category="web_search", quality_score=0.8)

    # New seller asks for pricing with quality_score=0.8
    new_seller, _ = await make_agent(name="int-new-quality-seller")
    result = await seller_service.suggest_price(
        db=db,
        seller_id=new_seller.id,
        category="web_search",
        quality_score=0.8,
    )

    assert result["competitors"] == 3
    assert result["median_price"] == 1.0  # median of [0.5, 1.0, 1.5]
    assert result["quality_score"] == 0.8
    # avg_quality = mean(0.4, 0.6, 0.8) = 0.6
    # quality_multiplier = 0.8 / 0.6 = 1.333...
    # suggested = 1.0 * 1.333 = 1.333
    assert 1.2 < result["suggested_price"] < 1.5
    assert "Quality-adjusted median" in result["strategy"]


# ---------------------------------------------------------------------------
# 8. test_register_webhook
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_register_webhook(db: AsyncSession, make_agent):
    """Creates a SellerWebhook record with correct fields."""
    seller, _ = await make_agent(name="int-webhook-seller")

    webhook = await seller_service.register_webhook(
        db=db,
        seller_id=seller.id,
        url="https://my-seller-app.com/hooks/demand",
        event_types=["demand_match", "listing_sold"],
        secret="s3cr3t_hmac_key",
    )

    assert webhook.id is not None
    assert webhook.seller_id == seller.id
    assert webhook.url == "https://my-seller-app.com/hooks/demand"
    assert webhook.status == "active"
    assert webhook.secret == "s3cr3t_hmac_key"
    event_types = json.loads(webhook.event_types)
    assert "demand_match" in event_types
    assert "listing_sold" in event_types


# ---------------------------------------------------------------------------
# 9. test_get_webhooks
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_webhooks(db: AsyncSession, make_agent):
    """Returns active webhooks for a seller."""
    seller, _ = await make_agent(name="int-wh-list-seller")

    # Create two webhooks, then pause one
    wh1 = await seller_service.register_webhook(
        db=db, seller_id=seller.id,
        url="https://example.com/wh1",
    )
    wh2 = await seller_service.register_webhook(
        db=db, seller_id=seller.id,
        url="https://example.com/wh2",
    )
    # Pause the second
    wh2.status = "paused"
    await db.commit()

    webhooks = await seller_service.get_webhooks(db, seller.id)

    assert len(webhooks) == 1
    assert webhooks[0].id == wh1.id
    assert webhooks[0].url == "https://example.com/wh1"
    assert webhooks[0].status == "active"


# ---------------------------------------------------------------------------
# 10. test_suggest_price_demand_premium
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_suggest_price_demand_premium(db: AsyncSession, make_agent, make_listing):
    """High demand (>100 searches) adds 15% premium to suggested price."""
    comp, _ = await make_agent(name="int-comp-demand")

    # One competitor at $2.00 with quality 0.5
    await make_listing(comp.id, price_usdc=2.0, category="web_search", quality_score=0.5)

    # Demand signal with search_count > 100
    demand = DemandSignal(
        id="int-demand-premium",
        query_pattern="high volume query",
        category="web_search",
        search_count=150,
        unique_requesters=60,
        velocity=Decimal("25.0"),
        avg_max_price=Decimal("3.0"),
        fulfillment_rate=Decimal("0.6"),
    )
    db.add(demand)
    await db.commit()

    seller, _ = await make_agent(name="int-premium-seller")
    result = await seller_service.suggest_price(
        db=db,
        seller_id=seller.id,
        category="web_search",
        quality_score=0.5,
    )

    assert result["demand_searches"] == 150
    assert "15% demand premium" in result["strategy"]
    # median_price=2.0, quality_multiplier=0.5/0.5=1.0 => base=2.0, +15% => 2.30
    assert result["suggested_price"] == 2.3


# ===========================================================================
# OPENCLAW SERVICE — 10 tests
# ===========================================================================


# ---------------------------------------------------------------------------
# 11. test_openclaw_register_webhook
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_openclaw_register_webhook(db: AsyncSession, make_agent):
    """Creates an OpenClawWebhook via oc_register."""
    agent, _ = await make_agent(name="int-oc-register")

    webhook = await oc_register(
        db,
        agent_id=agent.id,
        gateway_url="https://openclaw.example.com/hooks/agent",
        bearer_token="oc-bearer-tok-abc",
        event_types=["demand_spike", "listing_created"],
    )

    assert webhook.id is not None
    assert webhook.agent_id == agent.id
    assert webhook.gateway_url == "https://openclaw.example.com/hooks/agent"
    assert webhook.bearer_token == "oc-bearer-tok-abc"
    assert webhook.status == "active"
    assert webhook.failure_count == 0
    event_types = json.loads(webhook.event_types)
    assert event_types == ["demand_spike", "listing_created"]


# ---------------------------------------------------------------------------
# 12. test_openclaw_register_webhook_update_existing
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_openclaw_register_webhook_update_existing(db: AsyncSession, make_agent):
    """Second registration for same agent updates the existing webhook."""
    agent, _ = await make_agent(name="int-oc-upsert")

    first = await oc_register(
        db, agent.id,
        gateway_url="https://old-gw.com/hooks",
        bearer_token="old-token",
    )
    second = await oc_register(
        db, agent.id,
        gateway_url="https://new-gw.com/hooks",
        bearer_token="new-token",
        event_types=["listing_created"],
    )

    # Same row was updated, not a new row
    assert first.id == second.id
    assert second.gateway_url == "https://new-gw.com/hooks"
    assert second.bearer_token == "new-token"
    event_types = json.loads(second.event_types)
    assert event_types == ["listing_created"]


# ---------------------------------------------------------------------------
# 13. test_openclaw_list_webhooks
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_openclaw_list_webhooks(db: AsyncSession, make_agent):
    """Lists all webhooks (active and non-active) for an agent."""
    agent, _ = await make_agent(name="int-oc-list")

    # Create first webhook, then pause it so a second can be created
    w1 = await oc_register(db, agent.id, "https://gw1.com/hooks", "tok1")
    w1.status = "paused"
    await db.commit()

    # Now register a new active one (since previous is paused, no upsert)
    w2 = await oc_register(db, agent.id, "https://gw2.com/hooks", "tok2")

    webhooks = await oc_list(db, agent.id)

    assert len(webhooks) == 2
    urls = {w["gateway_url"] for w in webhooks}
    assert "https://gw1.com/hooks" in urls
    assert "https://gw2.com/hooks" in urls


# ---------------------------------------------------------------------------
# 14. test_openclaw_delete_webhook
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_openclaw_delete_webhook(db: AsyncSession, make_agent):
    """Deletes a webhook owned by the agent."""
    agent, _ = await make_agent(name="int-oc-delete")

    webhook = await oc_register(db, agent.id, "https://gw.com/hooks", "tok")
    webhook_id = webhook.id

    deleted = await oc_delete(db, webhook_id, agent.id)

    assert deleted is True
    # Verify it is gone
    remaining = await oc_list(db, agent.id)
    assert len(remaining) == 0


# ---------------------------------------------------------------------------
# 15. test_openclaw_delete_webhook_wrong_agent
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_openclaw_delete_webhook_wrong_agent(db: AsyncSession, make_agent):
    """Returns False when non-owner tries to delete."""
    owner, _ = await make_agent(name="int-oc-owner")
    intruder, _ = await make_agent(name="int-oc-intruder")

    webhook = await oc_register(db, owner.id, "https://gw.com/hooks", "tok")

    deleted = await oc_delete(db, webhook.id, intruder.id)

    assert deleted is False
    # Webhook still exists
    remaining = await oc_list(db, owner.id)
    assert len(remaining) == 1


# ---------------------------------------------------------------------------
# 16. test_openclaw_get_status
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_openclaw_get_status(db: AsyncSession, make_agent):
    """Returns connected flag and active/total counts."""
    agent, _ = await make_agent(name="int-oc-status")

    # No webhooks yet
    status_before = await oc_status(db, agent.id)
    assert status_before["connected"] is False
    assert status_before["webhooks_count"] == 0
    assert status_before["active_count"] == 0

    # Register a webhook
    await oc_register(db, agent.id, "https://gw.com/hooks", "tok")

    status_after = await oc_status(db, agent.id)
    assert status_after["connected"] is True
    assert status_after["webhooks_count"] == 1
    assert status_after["active_count"] == 1


# ---------------------------------------------------------------------------
# 17. test_openclaw_format_event_message
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_openclaw_format_event_message():
    """Known event types are formatted with their template."""
    # demand_spike
    msg_spike = format_event_message("demand_spike", {
        "query_pattern": "quantum computing",
        "category": "science",
        "velocity": 42.0,
    })
    assert "quantum computing" in msg_spike
    assert "science" in msg_spike
    assert "42" in msg_spike

    # opportunity_created
    msg_opp = format_event_message("opportunity_created", {
        "query_pattern": "stock prices",
        "estimated_revenue_usdc": 15.75,
        "urgency_score": 0.9,
    })
    assert "stock prices" in msg_opp
    assert "15.75" in msg_opp

    # transaction_completed
    msg_tx = format_event_message("transaction_completed", {
        "amount_axn": 1000.0,
        "listing_title": "Premium Data Feed",
    })
    assert "1000" in msg_tx
    assert "Premium Data Feed" in msg_tx


# ---------------------------------------------------------------------------
# 18. test_openclaw_format_event_unknown
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_openclaw_format_event_unknown():
    """Unknown event type returns JSON fallback string."""
    msg = format_event_message("totally_new_event", {"key": "value", "num": 123})

    assert "totally_new_event" in msg
    assert "value" in msg
    assert "123" in msg


# ---------------------------------------------------------------------------
# 19. test_openclaw_deliver_event_mock
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
@patch("marketplace.services.openclaw_service.httpx.AsyncClient")
async def test_openclaw_deliver_event_mock(mock_client_cls):
    """Mock httpx.AsyncClient to verify deliver_event sends correct payload."""
    mock_resp = MagicMock()
    mock_resp.status_code = 200

    mock_client = AsyncMock()
    mock_client.post = AsyncMock(return_value=mock_resp)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client_cls.return_value = mock_client

    webhook = MagicMock(spec=OpenClawWebhook)
    webhook.gateway_url = "https://openclaw-gw.example.com/hooks/agent"
    webhook.bearer_token = "test-bearer-token-xyz"
    webhook.id = "wh-int-test"

    result = await deliver_event(
        webhook, "demand_spike",
        {"query_pattern": "test query", "category": "web_search", "velocity": 10},
    )

    assert result is True
    mock_client.post.assert_called_once()
    # Verify the URL and headers
    call_args = mock_client.post.call_args
    assert call_args[0][0] == "https://openclaw-gw.example.com/hooks/agent"
    assert call_args[1]["headers"]["Authorization"] == "Bearer test-bearer-token-xyz"
    # Verify the body contains a message and sessionKey
    body = call_args[1]["json"]
    assert "message" in body
    assert "sessionKey" in body
    assert "agentchains-demand_spike" == body["sessionKey"]


# ---------------------------------------------------------------------------
# 20. test_openclaw_dispatch_filters
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
@patch("marketplace.services.openclaw_service.deliver_event", new_callable=AsyncMock)
async def test_openclaw_dispatch_filters(mock_deliver, db: AsyncSession, make_agent):
    """Dispatch respects event_type and category filters on webhooks."""
    mock_deliver.return_value = True

    agent_a, _ = await make_agent(name="int-dispatch-a")
    agent_b, _ = await make_agent(name="int-dispatch-b")

    # Agent A: subscribes to demand_spike only, category filter = ["science"]
    await oc_register(
        db, agent_a.id, "https://gw-a.com/hooks", "tok-a",
        event_types=["demand_spike"],
        filters={"categories": ["science"]},
    )

    # Agent B: subscribes to listing_created only, no category filter
    # Need to pause agent B's webhook first if exists, then create fresh
    wh_b = await oc_register(
        db, agent_b.id, "https://gw-b.com/hooks", "tok-b",
        event_types=["listing_created"],
    )

    # --- Dispatch a demand_spike in "science" category ---
    mock_deliver.reset_mock()
    await openclaw_service.dispatch_to_openclaw_webhooks(db, "demand_spike", {
        "query_pattern": "climate models",
        "category": "science",
        "velocity": 20,
    })
    # Only agent_a should receive it (matches event_type AND category)
    assert mock_deliver.call_count == 1

    # --- Dispatch a demand_spike in "finance" category ---
    mock_deliver.reset_mock()
    await openclaw_service.dispatch_to_openclaw_webhooks(db, "demand_spike", {
        "query_pattern": "stock data",
        "category": "finance",
        "velocity": 5,
    })
    # Agent A filters for "science" category, so no delivery
    # Agent B filters for "listing_created" event, so no delivery
    assert mock_deliver.call_count == 0

    # --- Dispatch a listing_created event (no category) ---
    mock_deliver.reset_mock()
    await openclaw_service.dispatch_to_openclaw_webhooks(db, "listing_created", {
        "title": "Fresh Dataset",
        "category": "web_search",
        "price_usdc": 0.5,
    })
    # Only agent_b subscribes to listing_created (no category filter)
    assert mock_deliver.call_count == 1
