"""OpenClaw webhook integration — push marketplace events to OpenClaw agents."""

import asyncio
import json
import logging
from datetime import datetime, timezone

import httpx
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from marketplace.config import settings
from marketplace.models.openclaw_webhook import OpenClawWebhook

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Webhook CRUD
# ---------------------------------------------------------------------------

async def register_webhook(
    db: AsyncSession,
    agent_id: str,
    gateway_url: str,
    bearer_token: str,
    event_types: list[str] | None = None,
    filters: dict | None = None,
) -> OpenClawWebhook:
    """Register an OpenClaw gateway to receive marketplace events."""
    # Check for existing active webhook for this agent
    result = await db.execute(
        select(OpenClawWebhook).where(
            OpenClawWebhook.agent_id == agent_id,
            OpenClawWebhook.status == "active",
        )
    )
    existing = result.scalar_one_or_none()
    if existing:
        # Update existing webhook
        existing.gateway_url = gateway_url
        existing.bearer_token = bearer_token
        existing.event_types = json.dumps(event_types or ["opportunity", "demand_spike", "transaction"])
        existing.filters = json.dumps(filters or {})
        existing.failure_count = 0
        existing.status = "active"
        await db.commit()
        await db.refresh(existing)
        return existing

    webhook = OpenClawWebhook(
        agent_id=agent_id,
        gateway_url=gateway_url,
        bearer_token=bearer_token,
        event_types=json.dumps(event_types or ["opportunity", "demand_spike", "transaction"]),
        filters=json.dumps(filters or {}),
    )
    db.add(webhook)
    await db.commit()
    await db.refresh(webhook)
    return webhook


async def list_webhooks(db: AsyncSession, agent_id: str) -> list[dict]:
    """List all webhooks for an agent."""
    result = await db.execute(
        select(OpenClawWebhook).where(OpenClawWebhook.agent_id == agent_id)
    )
    webhooks = result.scalars().all()
    return [_webhook_to_dict(w) for w in webhooks]


async def delete_webhook(db: AsyncSession, webhook_id: str, agent_id: str) -> bool:
    """Delete a webhook (must belong to agent)."""
    result = await db.execute(
        select(OpenClawWebhook).where(
            OpenClawWebhook.id == webhook_id,
            OpenClawWebhook.agent_id == agent_id,
        )
    )
    webhook = result.scalar_one_or_none()
    if not webhook:
        return False
    await db.delete(webhook)
    await db.commit()
    return True


async def get_status(db: AsyncSession, agent_id: str) -> dict:
    """Return connection status summary for an agent."""
    result = await db.execute(
        select(OpenClawWebhook).where(OpenClawWebhook.agent_id == agent_id)
    )
    webhooks = result.scalars().all()
    active = [w for w in webhooks if w.status == "active"]
    return {
        "connected": len(active) > 0,
        "webhooks_count": len(webhooks),
        "active_count": len(active),
        "last_delivery": max(
            (w.last_delivered_at.isoformat() for w in webhooks if w.last_delivered_at),
            default=None,
        ),
    }


# ---------------------------------------------------------------------------
# Event delivery
# ---------------------------------------------------------------------------

EVENT_MESSAGES = {
    "demand_spike": "📈 Demand spike on AgentChains: '{query_pattern}' in {category} (velocity: {velocity}). Consider creating a listing to earn AXN!",
    "opportunity_created": "💰 Revenue opportunity: '{query_pattern}' — estimated ${estimated_revenue_usdc:.2f} with urgency {urgency_score:.0%}. Use the marketplace to sell this data.",
    "listing_created": "🆕 New listing on marketplace: '{title}' in {category} at ${price_usdc} USDC.",
    "transaction_completed": "✅ Transaction completed: {amount_axn:.0f} AXN earned from selling '{listing_title}'.",
    "transaction_initiated": "🛒 New purchase initiated for '{listing_title}' — delivery pending.",
}


def format_event_message(event_type: str, data: dict) -> str:
    """Convert a machine event into a natural-language message for OpenClaw agents."""
    template = EVENT_MESSAGES.get(event_type)
    if not template:
        return f"AgentChains event ({event_type}): {json.dumps(data, default=str)}"
    try:
        return template.format(**data)
    except (KeyError, ValueError):
        return f"AgentChains event ({event_type}): {json.dumps(data, default=str)}"


async def deliver_event(webhook: OpenClawWebhook, event_type: str, data: dict) -> bool:
    """Deliver a single event to an OpenClaw gateway. Returns True on success."""
    message = format_event_message(event_type, data)
    body = {
        "message": message,
        "sessionKey": f"agentchains-{event_type}",
    }

    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                webhook.gateway_url,
                json=body,
                headers={"Authorization": f"Bearer {webhook.bearer_token}"},
                timeout=settings.openclaw_webhook_timeout_seconds,
            )
        return resp.status_code in (200, 202)
    except Exception as exc:
        logger.warning("OpenClaw webhook delivery failed for %s: %s", webhook.id, exc)
        return False


async def test_webhook(db: AsyncSession, webhook_id: str, agent_id: str) -> dict:
    """Send a test event to verify webhook connectivity."""
    result = await db.execute(
        select(OpenClawWebhook).where(
            OpenClawWebhook.id == webhook_id,
            OpenClawWebhook.agent_id == agent_id,
        )
    )
    webhook = result.scalar_one_or_none()
    if not webhook:
        return {"success": False, "message": "Webhook not found"}

    success = await deliver_event(webhook, "test", {
        "message": "This is a test event from AgentChains Marketplace.",
    })
    if success:
        webhook.last_delivered_at = datetime.now(timezone.utc)
        webhook.failure_count = 0
        await db.commit()
    return {"success": success, "message": "Delivered" if success else "Delivery failed"}


async def dispatch_to_openclaw_webhooks(
    db: AsyncSession, event_type: str, data: dict
) -> None:
    """Fan-out an event to all matching OpenClaw webhooks with retry."""
    result = await db.execute(
        select(OpenClawWebhook).where(OpenClawWebhook.status == "active")
    )
    webhooks = result.scalars().all()

    for webhook in webhooks:
        # Check event type filter
        try:
            allowed_types = json.loads(webhook.event_types)
        except (json.JSONDecodeError, TypeError):
            allowed_types = []
        if event_type not in allowed_types and event_type != "test":
            continue

        # Check category filter
        try:
            filters = json.loads(webhook.filters)
        except (json.JSONDecodeError, TypeError):
            filters = {}
        if filters.get("categories"):
            event_category = data.get("category", "")
            if event_category and event_category not in filters["categories"]:
                continue
        if filters.get("min_urgency"):
            urgency = data.get("urgency_score", 1.0)
            if urgency < filters["min_urgency"]:
                continue

        # Deliver with retry
        success = False
        for attempt in range(settings.openclaw_webhook_max_retries):
            success = await deliver_event(webhook, event_type, data)
            if success:
                break
            await asyncio.sleep(2 ** attempt)  # Exponential backoff

        # Update webhook status
        if success:
            webhook.last_delivered_at = datetime.now(timezone.utc)
            webhook.failure_count = 0
        else:
            webhook.failure_count += 1
            if webhook.failure_count >= settings.openclaw_webhook_max_failures:
                webhook.status = "paused"
                logger.warning(
                    "OpenClaw webhook %s paused after %d failures",
                    webhook.id, webhook.failure_count,
                )
        await db.commit()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _webhook_to_dict(webhook: OpenClawWebhook) -> dict:
    return {
        "id": webhook.id,
        "agent_id": webhook.agent_id,
        "gateway_url": webhook.gateway_url,
        "event_types": json.loads(webhook.event_types) if webhook.event_types else [],
        "filters": json.loads(webhook.filters) if webhook.filters else {},
        "status": webhook.status,
        "failure_count": webhook.failure_count,
        "last_delivered_at": webhook.last_delivered_at.isoformat() if webhook.last_delivered_at else None,
        "created_at": webhook.created_at.isoformat() if webhook.created_at else None,
    }
