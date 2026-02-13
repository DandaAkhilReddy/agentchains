"""Unit tests for the OpenClaw webhook integration service.

Tests use in-memory SQLite via conftest fixtures.
HTTP delivery calls are mocked via httpx mock.
"""

import json
from unittest.mock import AsyncMock, patch, MagicMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from marketplace.services import openclaw_service
from marketplace.models.openclaw_webhook import OpenClawWebhook


# ---------------------------------------------------------------------------
# Webhook CRUD
# ---------------------------------------------------------------------------

async def test_register_webhook_creates_record(db: AsyncSession, make_agent, seed_platform):
    agent, _ = await make_agent("oc_reg")
    webhook = await openclaw_service.register_webhook(
        db, agent.id,
        gateway_url="https://example.com/hooks/agent",
        bearer_token="test-bearer-token-123",
    )

    assert webhook.agent_id == agent.id
    assert webhook.gateway_url == "https://example.com/hooks/agent"
    assert webhook.status == "active"
    assert webhook.failure_count == 0


async def test_register_webhook_default_event_types(db: AsyncSession, make_agent, seed_platform):
    agent, _ = await make_agent("oc_default_events")
    webhook = await openclaw_service.register_webhook(
        db, agent.id,
        gateway_url="https://example.com/hooks/agent",
        bearer_token="tok",
    )
    event_types = json.loads(webhook.event_types)
    assert "opportunity" in event_types
    assert "demand_spike" in event_types
    assert "transaction" in event_types


async def test_register_webhook_custom_event_types(db: AsyncSession, make_agent, seed_platform):
    agent, _ = await make_agent("oc_custom_events")
    webhook = await openclaw_service.register_webhook(
        db, agent.id,
        gateway_url="https://example.com/hooks/agent",
        bearer_token="tok",
        event_types=["listing_created"],
    )
    event_types = json.loads(webhook.event_types)
    assert event_types == ["listing_created"]


async def test_register_webhook_upsert_existing(db: AsyncSession, make_agent, seed_platform):
    """Second registration updates existing webhook instead of creating duplicate."""
    agent, _ = await make_agent("oc_upsert")
    w1 = await openclaw_service.register_webhook(
        db, agent.id, "https://old.com/hooks", "old-token",
    )
    w2 = await openclaw_service.register_webhook(
        db, agent.id, "https://new.com/hooks", "new-token",
    )

    assert w1.id == w2.id  # Same row updated
    assert w2.gateway_url == "https://new.com/hooks"
    assert w2.bearer_token == "new-token"


async def test_register_webhook_with_filters(db: AsyncSession, make_agent, seed_platform):
    agent, _ = await make_agent("oc_filters")
    webhook = await openclaw_service.register_webhook(
        db, agent.id, "https://example.com/hooks", "tok",
        filters={"categories": ["web_search"], "min_urgency": 0.5},
    )
    filters = json.loads(webhook.filters)
    assert filters["categories"] == ["web_search"]
    assert filters["min_urgency"] == 0.5


async def test_list_webhooks_empty(db: AsyncSession, make_agent, seed_platform):
    agent, _ = await make_agent("oc_list_empty")
    result = await openclaw_service.list_webhooks(db, agent.id)
    assert result == []


async def test_list_webhooks_returns_all(db: AsyncSession, make_agent, seed_platform):
    agent, _ = await make_agent("oc_list_all")
    await openclaw_service.register_webhook(
        db, agent.id, "https://gw1.com/hooks", "tok1",
    )
    # Force create a second one by making the first one non-active
    from sqlalchemy import select
    result = await db.execute(
        select(OpenClawWebhook).where(OpenClawWebhook.agent_id == agent.id)
    )
    w = result.scalar_one()
    w.status = "paused"
    await db.commit()

    # Now register another active one
    await openclaw_service.register_webhook(
        db, agent.id, "https://gw2.com/hooks", "tok2",
    )

    webhooks = await openclaw_service.list_webhooks(db, agent.id)
    assert len(webhooks) == 2


async def test_delete_webhook_success(db: AsyncSession, make_agent, seed_platform):
    agent, _ = await make_agent("oc_delete")
    webhook = await openclaw_service.register_webhook(
        db, agent.id, "https://gw.com/hooks", "tok",
    )
    deleted = await openclaw_service.delete_webhook(db, webhook.id, agent.id)
    assert deleted is True

    result = await openclaw_service.list_webhooks(db, agent.id)
    assert len(result) == 0


async def test_delete_webhook_wrong_agent(db: AsyncSession, make_agent, seed_platform):
    agent1, _ = await make_agent("oc_del_owner")
    agent2, _ = await make_agent("oc_del_other")
    webhook = await openclaw_service.register_webhook(
        db, agent1.id, "https://gw.com/hooks", "tok",
    )
    deleted = await openclaw_service.delete_webhook(db, webhook.id, agent2.id)
    assert deleted is False


async def test_delete_webhook_nonexistent(db: AsyncSession, make_agent, seed_platform):
    agent, _ = await make_agent("oc_del_none")
    deleted = await openclaw_service.delete_webhook(db, "nonexistent-id", agent.id)
    assert deleted is False


async def test_get_status_not_connected(db: AsyncSession, make_agent, seed_platform):
    agent, _ = await make_agent("oc_status_none")
    status = await openclaw_service.get_status(db, agent.id)
    assert status["connected"] is False
    assert status["webhooks_count"] == 0
    assert status["active_count"] == 0


async def test_get_status_connected(db: AsyncSession, make_agent, seed_platform):
    agent, _ = await make_agent("oc_status_yes")
    await openclaw_service.register_webhook(
        db, agent.id, "https://gw.com/hooks", "tok",
    )
    status = await openclaw_service.get_status(db, agent.id)
    assert status["connected"] is True
    assert status["active_count"] == 1


# ---------------------------------------------------------------------------
# Event message formatting
# ---------------------------------------------------------------------------

def test_format_event_message_demand_spike():
    msg = openclaw_service.format_event_message("demand_spike", {
        "query_pattern": "climate data",
        "category": "science",
        "velocity": 25.5,
    })
    assert "climate data" in msg
    assert "science" in msg


def test_format_event_message_opportunity():
    msg = openclaw_service.format_event_message("opportunity_created", {
        "query_pattern": "stock prices",
        "estimated_revenue_usdc": 12.50,
        "urgency_score": 0.85,
    })
    assert "stock prices" in msg
    assert "12.50" in msg


def test_format_event_message_listing_created():
    msg = openclaw_service.format_event_message("listing_created", {
        "title": "Weather Report",
        "category": "environment",
        "price_usdc": 2.5,
    })
    assert "Weather Report" in msg


def test_format_event_message_transaction():
    msg = openclaw_service.format_event_message("transaction_completed", {
        "amount_usd": 5.0,
        "listing_title": "API Results",
    })
    assert "5.0" in msg
    assert "API Results" in msg


def test_format_event_message_unknown_type():
    msg = openclaw_service.format_event_message("unknown_event", {"foo": "bar"})
    assert "unknown_event" in msg
    assert "bar" in msg


def test_format_event_message_missing_keys():
    """Template with missing keys falls back to JSON dump."""
    msg = openclaw_service.format_event_message("demand_spike", {"query_pattern": "test"})
    # Missing 'category' and 'velocity' → fallback
    assert "demand_spike" in msg


# ---------------------------------------------------------------------------
# Event delivery (mocked HTTP)
# ---------------------------------------------------------------------------

@patch("marketplace.services.openclaw_service.httpx.AsyncClient")
async def test_deliver_event_success(mock_client_cls):
    mock_resp = MagicMock()
    mock_resp.status_code = 202
    mock_client = AsyncMock()
    mock_client.post = AsyncMock(return_value=mock_resp)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client_cls.return_value = mock_client

    webhook = MagicMock(spec=OpenClawWebhook)
    webhook.gateway_url = "https://gw.com/hooks/agent"
    webhook.bearer_token = "test-token"
    webhook.id = "wh-123"

    result = await openclaw_service.deliver_event(webhook, "test", {"msg": "hello"})
    assert result is True
    mock_client.post.assert_called_once()


@patch("marketplace.services.openclaw_service.httpx.AsyncClient")
async def test_deliver_event_failure(mock_client_cls):
    mock_resp = MagicMock()
    mock_resp.status_code = 500
    mock_client = AsyncMock()
    mock_client.post = AsyncMock(return_value=mock_resp)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client_cls.return_value = mock_client

    webhook = MagicMock(spec=OpenClawWebhook)
    webhook.gateway_url = "https://gw.com/hooks/agent"
    webhook.bearer_token = "test-token"
    webhook.id = "wh-123"

    result = await openclaw_service.deliver_event(webhook, "test", {"msg": "hello"})
    assert result is False


@patch("marketplace.services.openclaw_service.httpx.AsyncClient")
async def test_deliver_event_exception(mock_client_cls):
    """Network exception → returns False, doesn't raise."""
    mock_client = AsyncMock()
    mock_client.post = AsyncMock(side_effect=Exception("Connection refused"))
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client_cls.return_value = mock_client

    webhook = MagicMock(spec=OpenClawWebhook)
    webhook.gateway_url = "https://gw.com/hooks/agent"
    webhook.bearer_token = "test-token"
    webhook.id = "wh-123"

    result = await openclaw_service.deliver_event(webhook, "test", {})
    assert result is False


# ---------------------------------------------------------------------------
# Test webhook endpoint
# ---------------------------------------------------------------------------

@patch("marketplace.services.openclaw_service.deliver_event", new_callable=AsyncMock)
async def test_test_webhook_success(mock_deliver, db: AsyncSession, make_agent, seed_platform):
    mock_deliver.return_value = True
    agent, _ = await make_agent("oc_test_wh")
    webhook = await openclaw_service.register_webhook(
        db, agent.id, "https://gw.com/hooks", "tok",
    )
    result = await openclaw_service.test_webhook(db, webhook.id, agent.id)
    assert result["success"] is True
    assert result["message"] == "Delivered"


@patch("marketplace.services.openclaw_service.deliver_event", new_callable=AsyncMock)
async def test_test_webhook_failure(mock_deliver, db: AsyncSession, make_agent, seed_platform):
    mock_deliver.return_value = False
    agent, _ = await make_agent("oc_test_fail")
    webhook = await openclaw_service.register_webhook(
        db, agent.id, "https://gw.com/hooks", "tok",
    )
    result = await openclaw_service.test_webhook(db, webhook.id, agent.id)
    assert result["success"] is False


async def test_test_webhook_not_found(db: AsyncSession, make_agent, seed_platform):
    agent, _ = await make_agent("oc_test_nf")
    result = await openclaw_service.test_webhook(db, "nonexistent-id", agent.id)
    assert result["success"] is False
    assert "not found" in result["message"].lower()


# ---------------------------------------------------------------------------
# Dispatch fan-out (mocked delivery)
# ---------------------------------------------------------------------------

@patch("marketplace.services.openclaw_service.deliver_event", new_callable=AsyncMock)
async def test_dispatch_filters_by_event_type(mock_deliver, db: AsyncSession, make_agent, seed_platform):
    """Webhook subscribed to 'demand_spike' doesn't receive 'listing_created'."""
    mock_deliver.return_value = True
    agent, _ = await make_agent("oc_dispatch_filter")
    await openclaw_service.register_webhook(
        db, agent.id, "https://gw.com/hooks", "tok",
        event_types=["demand_spike"],
    )

    await openclaw_service.dispatch_to_openclaw_webhooks(db, "listing_created", {"title": "test"})
    mock_deliver.assert_not_called()


@patch("marketplace.services.openclaw_service.deliver_event", new_callable=AsyncMock)
async def test_dispatch_delivers_matching_event(mock_deliver, db: AsyncSession, make_agent, seed_platform):
    mock_deliver.return_value = True
    agent, _ = await make_agent("oc_dispatch_match")
    await openclaw_service.register_webhook(
        db, agent.id, "https://gw.com/hooks", "tok",
        event_types=["demand_spike"],
    )

    await openclaw_service.dispatch_to_openclaw_webhooks(db, "demand_spike", {
        "query_pattern": "test", "category": "web_search", "velocity": 20,
    })
    mock_deliver.assert_called_once()


@patch("marketplace.services.openclaw_service.deliver_event", new_callable=AsyncMock)
async def test_dispatch_filters_by_category(mock_deliver, db: AsyncSession, make_agent, seed_platform):
    """Webhook with category filter only receives matching categories."""
    mock_deliver.return_value = True
    agent, _ = await make_agent("oc_dispatch_cat")
    await openclaw_service.register_webhook(
        db, agent.id, "https://gw.com/hooks", "tok",
        event_types=["demand_spike"],
        filters={"categories": ["science"]},
    )

    # Non-matching category → no delivery
    await openclaw_service.dispatch_to_openclaw_webhooks(db, "demand_spike", {
        "query_pattern": "test", "category": "web_search", "velocity": 10,
    })
    mock_deliver.assert_not_called()


@patch("marketplace.services.openclaw_service.deliver_event", new_callable=AsyncMock)
async def test_dispatch_category_match_delivers(mock_deliver, db: AsyncSession, make_agent, seed_platform):
    mock_deliver.return_value = True
    agent, _ = await make_agent("oc_dispatch_cat_ok")
    await openclaw_service.register_webhook(
        db, agent.id, "https://gw.com/hooks", "tok",
        event_types=["demand_spike"],
        filters={"categories": ["science"]},
    )

    await openclaw_service.dispatch_to_openclaw_webhooks(db, "demand_spike", {
        "query_pattern": "test", "category": "science", "velocity": 10,
    })
    mock_deliver.assert_called_once()


@patch("marketplace.services.openclaw_service.deliver_event", new_callable=AsyncMock)
async def test_dispatch_pauses_after_max_failures(mock_deliver, db: AsyncSession, make_agent, seed_platform):
    """Webhook is paused after reaching max failure count."""
    mock_deliver.return_value = False  # All deliveries fail
    agent, _ = await make_agent("oc_dispatch_pause")

    # Set failure_count to just below threshold
    from marketplace.config import settings
    webhook = await openclaw_service.register_webhook(
        db, agent.id, "https://gw.com/hooks", "tok",
        event_types=["demand_spike"],
    )
    webhook.failure_count = settings.openclaw_webhook_max_failures - 1
    await db.commit()

    await openclaw_service.dispatch_to_openclaw_webhooks(db, "demand_spike", {
        "query_pattern": "test", "category": "web_search", "velocity": 10,
    })

    # Refresh webhook state
    await db.refresh(webhook)
    assert webhook.status == "paused"


@patch("marketplace.services.openclaw_service.deliver_event", new_callable=AsyncMock)
async def test_dispatch_skips_paused_webhooks(mock_deliver, db: AsyncSession, make_agent, seed_platform):
    """Paused webhooks are not dispatched to."""
    mock_deliver.return_value = True
    agent, _ = await make_agent("oc_skip_paused")
    webhook = await openclaw_service.register_webhook(
        db, agent.id, "https://gw.com/hooks", "tok",
        event_types=["demand_spike"],
    )
    webhook.status = "paused"
    await db.commit()

    await openclaw_service.dispatch_to_openclaw_webhooks(db, "demand_spike", {
        "query_pattern": "test", "category": "web_search", "velocity": 10,
    })
    mock_deliver.assert_not_called()


# ---------------------------------------------------------------------------
# _webhook_to_dict helper
# ---------------------------------------------------------------------------

def test_webhook_to_dict_serialization():
    """Verify dict output has correct keys and types."""
    webhook = MagicMock(spec=OpenClawWebhook)
    webhook.id = "wh-123"
    webhook.agent_id = "agent-456"
    webhook.gateway_url = "https://gw.com/hooks"
    webhook.event_types = '["demand_spike"]'
    webhook.filters = '{"categories": ["web_search"]}'
    webhook.status = "active"
    webhook.failure_count = 0
    webhook.last_delivered_at = None
    webhook.created_at = None

    result = openclaw_service._webhook_to_dict(webhook)
    assert result["id"] == "wh-123"
    assert result["event_types"] == ["demand_spike"]
    assert result["filters"]["categories"] == ["web_search"]
    assert result["status"] == "active"
    assert result["last_delivered_at"] is None
