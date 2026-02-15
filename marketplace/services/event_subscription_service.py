"""Generic trust/event webhook subscriptions and signed event delivery."""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import uuid
from datetime import datetime, timezone
from itertools import count
from typing import Any

import httpx
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from marketplace.config import settings
from marketplace.models.agent_trust import EventSubscription, WebhookDelivery

_EVENT_SEQ = count(1)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _json_load(value: Any, fallback: Any) -> Any:
    if value is None:
        return fallback
    if isinstance(value, (dict, list)):
        return value
    if isinstance(value, str):
        try:
            return json.loads(value)
        except Exception:
            return fallback
    return fallback


def _canonical_payload(payload: dict[str, Any]) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))


def _sign(secret: str, payload: dict[str, Any]) -> str:
    data = _canonical_payload(payload).encode("utf-8")
    digest = hmac.new(secret.encode("utf-8"), data, hashlib.sha256).hexdigest()
    return f"sha256={digest}"


def _base_event_payload(event: dict[str, Any]) -> dict[str, Any]:
    return {
        "event_id": event["event_id"],
        "seq": event["seq"],
        "event_type": event["event_type"],
        "occurred_at": event["occurred_at"],
        "agent_id": event.get("agent_id"),
        "payload": event.get("payload", {}),
        "delivery_attempt": event.get("delivery_attempt", 1),
    }


def build_event_envelope(
    event_type: str,
    payload: dict[str, Any],
    *,
    agent_id: str | None = None,
    delivery_attempt: int = 1,
) -> dict[str, Any]:
    """Build a signed event envelope shared by WebSocket and webhook delivery."""
    event = {
        "event_id": str(uuid.uuid4()),
        "seq": next(_EVENT_SEQ),
        "event_type": event_type,
        "occurred_at": _utcnow().isoformat(),
        "agent_id": agent_id,
        "payload": payload,
        "delivery_attempt": delivery_attempt,
    }
    secret = settings.event_signing_secret or settings.jwt_secret_key
    event["signature"] = _sign(secret, _base_event_payload(event))

    # Backward-compatible aliases for existing feed consumers.
    event["type"] = event_type
    event["timestamp"] = event["occurred_at"]
    event["data"] = payload
    return event


def _event_matches(subscription: EventSubscription, event: dict[str, Any]) -> bool:
    event_agent_id = event.get("agent_id")
    if event_agent_id and subscription.agent_id != event_agent_id:
        return False
    allowed_types = _json_load(subscription.event_types_json, ["*"])
    if not isinstance(allowed_types, list):
        return False
    return "*" in allowed_types or event["event_type"] in allowed_types


def _serialize_subscription(subscription: EventSubscription) -> dict[str, Any]:
    return {
        "id": subscription.id,
        "agent_id": subscription.agent_id,
        "callback_url": subscription.callback_url,
        "event_types": _json_load(subscription.event_types_json, ["*"]),
        "status": subscription.status,
        "failure_count": int(subscription.failure_count or 0),
        "last_delivery_at": (
            subscription.last_delivery_at.isoformat()
            if subscription.last_delivery_at
            else None
        ),
        "created_at": (
            subscription.created_at.isoformat() if subscription.created_at else None
        ),
    }


async def register_subscription(
    db: AsyncSession,
    *,
    agent_id: str,
    callback_url: str,
    event_types: list[str] | None = None,
) -> dict[str, Any]:
    result = await db.execute(
        select(EventSubscription).where(
            EventSubscription.agent_id == agent_id,
            EventSubscription.callback_url == callback_url,
        )
    )
    existing = result.scalar_one_or_none()
    secret = f"whsec_{uuid.uuid4().hex}"
    if existing is None:
        existing = EventSubscription(
            id=str(uuid.uuid4()),
            agent_id=agent_id,
            callback_url=callback_url,
            event_types_json=json.dumps(event_types or ["*"]),
            secret=secret,
            status="active",
        )
        db.add(existing)
    else:
        existing.event_types_json = json.dumps(event_types or ["*"])
        existing.status = "active"
        existing.failure_count = 0
        existing.secret = secret
    await db.commit()
    await db.refresh(existing)
    data = _serialize_subscription(existing)
    data["secret"] = secret
    return data


async def list_subscriptions(db: AsyncSession, *, agent_id: str) -> list[dict[str, Any]]:
    result = await db.execute(
        select(EventSubscription).where(EventSubscription.agent_id == agent_id)
    )
    rows = result.scalars().all()
    return [_serialize_subscription(row) for row in rows]


async def delete_subscription(
    db: AsyncSession, *, agent_id: str, subscription_id: str
) -> bool:
    result = await db.execute(
        select(EventSubscription).where(
            EventSubscription.id == subscription_id,
            EventSubscription.agent_id == agent_id,
        )
    )
    row = result.scalar_one_or_none()
    if row is None:
        return False
    await db.delete(row)
    await db.commit()
    return True


async def _deliver_to_subscription(
    db: AsyncSession,
    *,
    subscription: EventSubscription,
    event: dict[str, Any],
) -> None:
    payload = _base_event_payload(event)
    max_retries = max(1, settings.trust_webhook_max_retries)
    timeout = max(1, settings.trust_webhook_timeout_seconds)
    delivered = False

    for attempt in range(1, max_retries + 1):
        payload["delivery_attempt"] = attempt
        signature = _sign(subscription.secret, payload)
        signed_event = {
            **payload,
            "signature": signature,
            "type": payload["event_type"],
            "timestamp": payload["occurred_at"],
            "data": payload["payload"],
        }

        response_code: int | None = None
        response_body = ""
        status = "failed"
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    subscription.callback_url,
                    json=signed_event,
                    timeout=timeout,
                    headers={
                        "X-AgentChains-Signature": signature,
                        "X-AgentChains-Event-Id": payload["event_id"],
                        "X-AgentChains-Delivery-Attempt": str(attempt),
                    },
                )
            response_code = response.status_code
            response_body = (response.text or "")[:1200]
            if 200 <= response.status_code < 300:
                status = "delivered"
                delivered = True
        except Exception as exc:
            response_body = str(exc)[:1200]

        db.add(
            WebhookDelivery(
                id=str(uuid.uuid4()),
                subscription_id=subscription.id,
                event_id=payload["event_id"],
                event_type=payload["event_type"],
                payload_json=json.dumps(payload),
                signature=signature,
                status=status,
                response_code=response_code,
                response_body=response_body,
                delivery_attempt=attempt,
            )
        )
        await db.flush()

        if delivered:
            subscription.failure_count = 0
            subscription.last_delivery_at = _utcnow()
            break

        subscription.failure_count = int(subscription.failure_count or 0) + 1
        if subscription.failure_count >= settings.trust_webhook_max_failures:
            subscription.status = "paused"
            break
        await asyncio.sleep(2 ** (attempt - 1))

    await db.commit()


async def dispatch_event_to_subscriptions(
    db: AsyncSession,
    *,
    event: dict[str, Any],
) -> None:
    """Fan out a signed event to all matching active subscriptions."""
    query = select(EventSubscription).where(EventSubscription.status == "active")
    event_agent_id = event.get("agent_id")
    if event_agent_id:
        query = query.where(EventSubscription.agent_id == event_agent_id)
    try:
        result = await db.execute(query)
    except SQLAlchemyError:
        return
    subscriptions = result.scalars().all()
    for subscription in subscriptions:
        if _event_matches(subscription, event):
            await _deliver_to_subscription(db, subscription=subscription, event=event)
