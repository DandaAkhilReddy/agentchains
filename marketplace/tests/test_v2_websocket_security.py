"""Security-focused tests for v2 websocket routing and event envelopes."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock

import pytest

from marketplace.core.auth import create_access_token, create_stream_token, decode_stream_token
from marketplace.core.exceptions import UnauthorizedError
from marketplace.main import ScopedConnectionManager
from marketplace.services.event_subscription_service import build_event_envelope


def _mock_ws():
    ws = AsyncMock()
    ws.accept = AsyncMock()
    ws.send_text = AsyncMock()
    ws.close = AsyncMock()
    return ws


@pytest.mark.asyncio
async def test_scoped_manager_private_event_only_reaches_target_agent():
    manager = ScopedConnectionManager()
    ws_a = _mock_ws()
    ws_b = _mock_ws()
    await manager.connect(
        ws_a,
        stream_payload={
            "sub": "agent-a",
            "sub_type": "agent",
            "allowed_topics": ["private.agent"],
        },
    )
    await manager.connect(
        ws_b,
        stream_payload={
            "sub": "agent-b",
            "sub_type": "agent",
            "allowed_topics": ["private.agent"],
        },
    )

    payload = {"type": "private", "data": {"secret": "only-a"}}
    await manager.broadcast_private_agent(payload, target_agent_ids=["agent-a"])

    ws_a.send_text.assert_awaited_once_with(json.dumps(payload))
    ws_b.send_text.assert_not_awaited()


@pytest.mark.asyncio
async def test_scoped_manager_private_admin_event_only_reaches_target_creator():
    manager = ScopedConnectionManager()
    ws_admin_target = _mock_ws()
    ws_admin_other = _mock_ws()
    ws_agent = _mock_ws()
    await manager.connect(
        ws_admin_target,
        stream_payload={
            "sub": "creator-a",
            "sub_type": "admin",
            "allowed_topics": ["private.admin", "public.market"],
        },
    )
    await manager.connect(
        ws_admin_other,
        stream_payload={
            "sub": "creator-b",
            "sub_type": "admin",
            "allowed_topics": ["private.admin", "public.market"],
        },
    )
    await manager.connect(
        ws_agent,
        stream_payload={
            "sub": "agent-a",
            "sub_type": "agent",
            "allowed_topics": ["private.agent", "public.market"],
        },
    )

    payload = {"type": "private_admin", "data": {"request_id": "req-1"}}
    await manager.broadcast_private_admin(payload, target_creator_ids=["creator-a"])

    ws_admin_target.send_text.assert_awaited_once_with(json.dumps(payload))
    ws_admin_other.send_text.assert_not_awaited()
    ws_agent.send_text.assert_not_awaited()


def test_decode_stream_token_rejects_non_stream_token():
    token = create_access_token("agent-a", "agent-a")
    with pytest.raises(UnauthorizedError):
        decode_stream_token(token)


def test_decode_stream_token_accepts_stream_token():
    token = create_stream_token("agent-a")
    payload = decode_stream_token(token)
    assert payload["sub"] == "agent-a"
    assert payload["type"] == "stream_agent"


def test_decode_stream_token_accepts_admin_stream_token():
    token = create_stream_token(
        "creator-admin",
        token_type="stream_admin",
        allowed_topics=["public.market", "private.admin"],
    )
    payload = decode_stream_token(token)
    assert payload["sub"] == "creator-admin"
    assert payload["type"] == "stream_admin"
    assert payload["sub_type"] == "admin"


def test_unclassified_event_is_private_and_blocked_without_targets():
    event = build_event_envelope("unclassified.security.event", {"foo": "bar"})
    assert event["visibility"] == "private"
    assert event["blocked"] is True
    assert event["target_agent_ids"] == []


def test_public_listing_event_is_sanitized_for_legacy_feed():
    event = build_event_envelope(
        "listing_created",
        {
            "listing_id": "listing-1",
            "title": "Title",
            "category": "web_search",
            "price_usd": 1.5,
            "seller_id": "sensitive-seller",
        },
    )
    assert event["visibility"] == "public"
    assert "seller_id" not in event["payload"]
    assert event["payload"]["listing_id"] == "listing-1"
