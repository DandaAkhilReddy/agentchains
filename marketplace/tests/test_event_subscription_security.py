"""Security tests for webhook validation and event signatures."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select

from marketplace.config import settings
from marketplace.models.agent_trust import WebhookDelivery
from marketplace.services.event_subscription_service import (
    _base_event_payload,
    build_event_envelope,
    dispatch_event_to_subscriptions,
    redact_old_webhook_deliveries,
    register_subscription,
    validate_callback_url,
    verify_event_signature,
)


def test_validate_callback_url_rejects_http_in_production(monkeypatch):
    monkeypatch.setattr(settings, "environment", "production")
    try:
        try:
            validate_callback_url("http://example.com/hook")
            assert False, "Expected ValueError for non-https callback URL in production"
        except ValueError as exc:
            assert "HTTPS" in str(exc)
    finally:
        monkeypatch.setattr(settings, "environment", "development")


def test_validate_callback_url_rejects_private_ip_in_production(monkeypatch):
    monkeypatch.setattr(settings, "environment", "production")
    try:
        try:
            validate_callback_url("https://127.0.0.1/hook")
            assert False, "Expected ValueError for localhost callback URL in production"
        except ValueError:
            pass
    finally:
        monkeypatch.setattr(settings, "environment", "development")


def test_validate_callback_url_allows_dev_localhost(monkeypatch):
    monkeypatch.setattr(settings, "environment", "development")
    normalized = validate_callback_url("http://127.0.0.1:8080/hook")
    assert normalized == "http://127.0.0.1:8080/hook"


def test_event_signature_verification_accepts_current_key(monkeypatch):
    monkeypatch.setattr(settings, "event_signing_secret", "current-secret")
    event = build_event_envelope("test_event", {"hello": "world"})
    payload = _base_event_payload(event)
    assert verify_event_signature(
        payload=payload,
        signature=event["signature"],
        current_secret="current-secret",
    )


def test_event_signature_verification_accepts_previous_key(monkeypatch):
    monkeypatch.setattr(settings, "event_signing_secret", "old-secret")
    event = build_event_envelope("test_event", {"hello": "rotation"})
    payload = _base_event_payload(event)
    assert verify_event_signature(
        payload=payload,
        signature=event["signature"],
        current_secret="new-secret",
        previous_secret="old-secret",
    )


@pytest.mark.asyncio
async def test_old_webhook_delivery_payloads_are_redacted(db, monkeypatch):
    monkeypatch.setattr(settings, "environment", "development")
    agent_id = str(uuid.uuid4())
    await register_subscription(
        db,
        agent_id=agent_id,
        callback_url="http://127.0.0.1:8080/hook",
        event_types=["test_event"],
    )

    class _DummyResponse:
        status_code = 200
        text = "ok"

    class _DummyClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def post(self, *args, **kwargs):
            return _DummyResponse()

    monkeypatch.setattr(
        "marketplace.services.event_subscription_service.httpx.AsyncClient",
        _DummyClient,
    )

    event = build_event_envelope("test_event", {"agent_id": agent_id}, agent_id=agent_id)
    await dispatch_event_to_subscriptions(db, event=event)

    result = await db.execute(select(WebhookDelivery))
    delivery = result.scalars().first()
    assert delivery is not None
    delivery.created_at = datetime.now(timezone.utc) - timedelta(days=45)
    delivery.payload_json = '{"sensitive":"yes"}'
    delivery.response_body = "full response body"
    await db.commit()

    redacted = await redact_old_webhook_deliveries(db, retention_days=30)
    assert redacted >= 1

    result = await db.execute(select(WebhookDelivery))
    delivery = result.scalars().first()
    assert delivery is not None
    assert delivery.payload_json == "{}"
    assert delivery.response_body == "[redacted]"
