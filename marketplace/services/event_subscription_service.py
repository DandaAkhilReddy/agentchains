"""Generic trust/event webhook subscriptions and signed event delivery."""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import ipaddress
import json
import socket
import uuid
from datetime import datetime, timedelta, timezone
from itertools import count
from typing import Any
from urllib.parse import urlsplit, urlunsplit

import httpx
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from marketplace.config import settings
from marketplace.models.agent_trust import EventSubscription, WebhookDelivery

_EVENT_SEQ = count(1)
_SCHEMA_VERSION = "2026-02-15"
_PROD_ENVS = {"production", "prod"}
_PUBLIC_TOPIC = "public.market"
_PRIVATE_TOPIC = "private.agent"
_PRIVATE_NETWORKS = (
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("169.254.0.0/16"),
    ipaddress.ip_network("::1/128"),
    ipaddress.ip_network("fc00::/7"),
    ipaddress.ip_network("fe80::/10"),
)

_EVENT_POLICY: dict[str, dict[str, Any]] = {
    "demand_spike": {
        "visibility": "public",
        "topic": _PUBLIC_TOPIC,
        "public_fields": ["query_pattern", "velocity", "category"],
        "target_keys": [],
    },
    "opportunity_created": {
        "visibility": "public",
        "topic": _PUBLIC_TOPIC,
        "public_fields": ["id", "query_pattern", "estimated_revenue_usd", "urgency_score"],
        "target_keys": [],
    },
    "listing_created": {
        "visibility": "public",
        "topic": _PUBLIC_TOPIC,
        "public_fields": ["listing_id", "title", "category", "price", "price_usd", "price_usdc"],
        "target_keys": [],
    },
    "test_event": {
        "visibility": "public",
        "topic": _PUBLIC_TOPIC,
        "public_fields": [],
        "target_keys": [],
    },
    "catalog_update": {
        "visibility": "private",
        "topic": _PRIVATE_TOPIC,
        "public_fields": [],
        "target_keys": ["subscriber_id", "agent_id"],
    },
    "transaction_initiated": {
        "visibility": "private",
        "topic": _PRIVATE_TOPIC,
        "public_fields": [],
        "target_keys": ["buyer_id", "seller_id"],
    },
    "payment_confirmed": {
        "visibility": "private",
        "topic": _PRIVATE_TOPIC,
        "public_fields": [],
        "target_keys": ["buyer_id", "seller_id"],
    },
    "content_delivered": {
        "visibility": "private",
        "topic": _PRIVATE_TOPIC,
        "public_fields": [],
        "target_keys": ["buyer_id", "seller_id"],
    },
    "transaction_completed": {
        "visibility": "private",
        "topic": _PRIVATE_TOPIC,
        "public_fields": [],
        "target_keys": ["buyer_id", "seller_id"],
    },
    "transaction_disputed": {
        "visibility": "private",
        "topic": _PRIVATE_TOPIC,
        "public_fields": [],
        "target_keys": ["buyer_id", "seller_id"],
    },
    "express_purchase": {
        "visibility": "private",
        "topic": _PRIVATE_TOPIC,
        "public_fields": [],
        "target_keys": ["buyer_id", "seller_id"],
    },
    "payment": {
        "visibility": "private",
        "topic": _PRIVATE_TOPIC,
        "public_fields": [],
        "target_keys": ["from_agent_id", "to_agent_id"],
    },
    "deposit": {
        "visibility": "private",
        "topic": _PRIVATE_TOPIC,
        "public_fields": [],
        "target_keys": ["agent_id"],
    },
    "agent.trust.updated": {
        "visibility": "private",
        "topic": _PRIVATE_TOPIC,
        "public_fields": [],
        "target_keys": ["agent_id"],
    },
    "challenge.failed": {
        "visibility": "private",
        "topic": _PRIVATE_TOPIC,
        "public_fields": [],
        "target_keys": ["agent_id"],
    },
    "challenge.passed": {
        "visibility": "private",
        "topic": _PRIVATE_TOPIC,
        "public_fields": [],
        "target_keys": ["agent_id"],
    },
    "memory.snapshot.imported": {
        "visibility": "private",
        "topic": _PRIVATE_TOPIC,
        "public_fields": [],
        "target_keys": ["agent_id"],
    },
    "memory.snapshot.verified": {
        "visibility": "private",
        "topic": _PRIVATE_TOPIC,
        "public_fields": [],
        "target_keys": ["agent_id"],
    },
}


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _is_prod() -> bool:
    return settings.environment.lower() in _PROD_ENVS


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


def _event_signing_secret() -> str:
    secret = (settings.event_signing_secret or "").strip()
    if not secret:
        raise RuntimeError("EVENT_SIGNING_SECRET must be configured")
    return secret


def _sign(secret: str, payload: dict[str, Any]) -> str:
    data = _canonical_payload(payload).encode("utf-8")
    digest = hmac.new(secret.encode("utf-8"), data, hashlib.sha256).hexdigest()
    return f"sha256={digest}"


def verify_event_signature(
    *,
    payload: dict[str, Any],
    signature: str,
    current_secret: str,
    previous_secret: str | None = None,
) -> bool:
    """Verify an event signature against current and optional previous key."""
    if not signature:
        return False
    expected = _sign(current_secret, payload)
    if hmac.compare_digest(signature, expected):
        return True
    if previous_secret:
        previous = _sign(previous_secret, payload)
        return hmac.compare_digest(signature, previous)
    return False


def _event_policy(event_type: str) -> dict[str, Any]:
    return _EVENT_POLICY.get(
        event_type,
        {
            "visibility": "private",
            "topic": _PRIVATE_TOPIC,
            "public_fields": [],
            "target_keys": [],
        },
    )


def _extract_target_agent_ids(
    payload: dict[str, Any], policy: dict[str, Any], explicit_targets: list[str] | None = None
) -> list[str]:
    values: set[str] = set()
    for item in explicit_targets or []:
        if isinstance(item, str) and item.strip():
            values.add(item.strip())

    keys = set(policy.get("target_keys", []))
    keys.update(
        {
            "agent_id",
            "buyer_id",
            "seller_id",
            "subscriber_id",
            "from_agent_id",
            "to_agent_id",
        }
    )
    for key in keys:
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            values.add(value.strip())
        if isinstance(value, list):
            for nested in value:
                if isinstance(nested, str) and nested.strip():
                    values.add(nested.strip())
    return sorted(values)


def _sanitize_payload(
    payload: dict[str, Any], policy: dict[str, Any], visibility: str
) -> dict[str, Any]:
    if visibility != "public":
        return dict(payload)

    fields = policy.get("public_fields", [])
    if not fields:
        return dict(payload)
    return {field: payload[field] for field in fields if field in payload}


def _base_event_payload(event: dict[str, Any]) -> dict[str, Any]:
    return {
        "event_id": event["event_id"],
        "seq": event["seq"],
        "event_type": event["event_type"],
        "occurred_at": event["occurred_at"],
        "agent_id": event.get("agent_id"),
        "payload": event.get("payload", {}),
        "visibility": event.get("visibility", "private"),
        "topic": event.get("topic", _PRIVATE_TOPIC),
        "target_agent_ids": event.get("target_agent_ids", []),
        "schema_version": event.get("schema_version", _SCHEMA_VERSION),
        "delivery_attempt": event.get("delivery_attempt", 1),
    }


def build_event_envelope(
    event_type: str,
    payload: dict[str, Any],
    *,
    agent_id: str | None = None,
    delivery_attempt: int = 1,
    target_agent_ids: list[str] | None = None,
) -> dict[str, Any]:
    """Build a signed event envelope shared by WebSocket and webhook delivery."""
    policy = _event_policy(event_type)
    visibility = policy["visibility"]
    topic = policy["topic"]
    targets = _extract_target_agent_ids(payload, policy, target_agent_ids)
    sanitized_payload = _sanitize_payload(payload, policy, visibility)
    blocked = visibility == "private" and not targets
    resolved_agent_id = agent_id or (targets[0] if targets else None)

    event = {
        "event_id": str(uuid.uuid4()),
        "seq": next(_EVENT_SEQ),
        "event_type": event_type,
        "occurred_at": _utcnow().isoformat(),
        "agent_id": resolved_agent_id,
        "payload": sanitized_payload,
        "visibility": visibility,
        "topic": topic,
        "target_agent_ids": targets,
        "schema_version": _SCHEMA_VERSION,
        "delivery_attempt": delivery_attempt,
        "blocked": blocked,
        "signature_key_id": settings.event_signing_key_id,
    }
    event["signature"] = _sign(_event_signing_secret(), _base_event_payload(event))

    # Backward-compatible aliases for existing feed consumers.
    event["type"] = event_type
    event["timestamp"] = event["occurred_at"]
    event["data"] = sanitized_payload
    return event


def should_dispatch_event(event: dict[str, Any]) -> bool:
    return not bool(event.get("blocked"))


def _is_disallowed_ip(ip: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    return (
        ip.is_loopback
        or ip.is_link_local
        or ip.is_multicast
        or ip.is_reserved
        or ip.is_unspecified
        or any(ip in network for network in _PRIVATE_NETWORKS)
    )


def _resolve_host_ips(host: str) -> list[ipaddress.IPv4Address | ipaddress.IPv6Address]:
    try:
        infos = socket.getaddrinfo(host, None, type=socket.SOCK_STREAM)
    except socket.gaierror as exc:
        raise ValueError(f"Unable to resolve callback host: {host}") from exc

    addresses: list[ipaddress.IPv4Address | ipaddress.IPv6Address] = []
    for info in infos:
        raw = info[4][0]
        try:
            addresses.append(ipaddress.ip_address(raw))
        except ValueError:
            continue
    if not addresses:
        raise ValueError(f"No routable IP addresses found for callback host: {host}")
    return addresses


def validate_callback_url(callback_url: str) -> str:
    parts = urlsplit((callback_url or "").strip())
    if parts.scheme not in {"http", "https"}:
        raise ValueError("Callback URL must use http or https")
    if not parts.netloc or not parts.hostname:
        raise ValueError("Callback URL must include a valid host")

    if _is_prod() and parts.scheme != "https":
        raise ValueError("HTTPS callback URL is required in production")

    host = parts.hostname
    if _is_prod() and host in {"localhost", "127.0.0.1", "::1"}:
        raise ValueError("Localhost callback URLs are not allowed in production")

    try:
        literal_ip = ipaddress.ip_address(host)
    except ValueError:
        literal_ip = None

    if literal_ip is not None:
        addresses = [literal_ip]
    elif _is_prod():
        addresses = _resolve_host_ips(host)
    else:
        addresses = []
    for addr in addresses:
        if _is_disallowed_ip(addr):
            if _is_prod():
                raise ValueError("Callback URL resolves to a private or reserved address")
    normalized_path = parts.path or "/"
    normalized = urlunsplit((parts.scheme, parts.netloc, normalized_path, parts.query, ""))
    return normalized


def _event_matches(subscription: EventSubscription, event: dict[str, Any]) -> bool:
    visibility = event.get("visibility", "private")
    target_agent_ids = event.get("target_agent_ids") or []
    if visibility == "private":
        if not target_agent_ids or subscription.agent_id not in target_agent_ids:
            return False
    else:
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
    normalized_url = validate_callback_url(callback_url)
    result = await db.execute(
        select(EventSubscription).where(
            EventSubscription.agent_id == agent_id,
            EventSubscription.callback_url == normalized_url,
        )
    )
    existing = result.scalar_one_or_none()
    secret = f"whsec_{uuid.uuid4().hex}"
    if existing is None:
        existing = EventSubscription(
            id=str(uuid.uuid4()),
            agent_id=agent_id,
            callback_url=normalized_url,
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
    data["signature_key_id"] = settings.event_signing_key_id
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
        validate_callback_url(subscription.callback_url)
        signature = _sign(subscription.secret, payload)
        signed_event = {
            **payload,
            "signature": signature,
            "signature_key_id": settings.event_signing_key_id,
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
                        "X-AgentChains-Signature-Key-Id": settings.event_signing_key_id,
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
    if not should_dispatch_event(event):
        return

    query = select(EventSubscription).where(EventSubscription.status == "active")
    visibility = event.get("visibility", "private")
    if visibility == "private":
        targets = event.get("target_agent_ids") or []
        if not targets:
            return
        query = query.where(EventSubscription.agent_id.in_(targets))
    elif event.get("agent_id"):
        query = query.where(EventSubscription.agent_id == event["agent_id"])

    try:
        result = await db.execute(query)
    except SQLAlchemyError:
        return
    subscriptions = result.scalars().all()
    for subscription in subscriptions:
        if _event_matches(subscription, event):
            await _deliver_to_subscription(db, subscription=subscription, event=event)


async def redact_old_webhook_deliveries(
    db: AsyncSession,
    *,
    retention_days: int | None = None,
) -> int:
    """Redact raw payload/response bodies beyond retention window."""
    days = retention_days if retention_days is not None else settings.security_event_retention_days
    cutoff = _utcnow() - timedelta(days=max(1, days))
    result = await db.execute(
        select(WebhookDelivery).where(WebhookDelivery.created_at < cutoff)
    )
    rows = result.scalars().all()
    redacted = 0
    for row in rows:
        needs_update = False
        if row.payload_json not in ("{}", ""):
            row.payload_json = "{}"
            needs_update = True
        if row.response_body not in ("", "[redacted]"):
            row.response_body = "[redacted]"
            needs_update = True
        if needs_update:
            redacted += 1
    if redacted:
        await db.commit()
    return redacted
