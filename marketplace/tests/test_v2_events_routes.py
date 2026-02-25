"""Tests for v2 event stream bootstrap endpoints.

Covers: marketplace/api/v2_events.py
  - GET /api/v2/events/stream-token
"""

from __future__ import annotations

import pytest

from marketplace.config import settings
from marketplace.core.auth import decode_stream_token


# ===========================================================================
# GET /api/v2/events/stream-token
# ===========================================================================

class TestStreamToken:
    """Tests for the stream token issuance endpoint."""

    async def test_stream_token_happy_path(self, client, make_agent):
        agent, token = await make_agent()

        resp = await client.get(
            "/api/v2/events/stream-token",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["agent_id"] == agent.id
        assert "stream_token" in body
        assert "expires_in_seconds" in body
        assert "expires_at" in body
        assert body["ws_url"] == "/ws/v2/events"
        assert body["allowed_topics"] == ["public.market", "private.agent"]

    async def test_stream_token_is_valid_jwt(self, client, make_agent):
        """The returned stream_token should be decodable."""
        agent, token = await make_agent()

        resp = await client.get(
            "/api/v2/events/stream-token",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        stream_token = resp.json()["stream_token"]

        payload = decode_stream_token(stream_token)
        assert payload["sub"] == agent.id
        assert payload["type"] == "stream_agent"
        assert "public.market" in payload["allowed_topics"]
        assert "private.agent" in payload["allowed_topics"]

    async def test_stream_token_expires_in_matches_settings(self, client, make_agent):
        _, token = await make_agent()

        resp = await client.get(
            "/api/v2/events/stream-token",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        body = resp.json()
        expected_seconds = int(settings.stream_token_expire_minutes * 60)
        assert body["expires_in_seconds"] == expected_seconds

    async def test_stream_token_rejects_missing_auth(self, client):
        resp = await client.get("/api/v2/events/stream-token")
        assert resp.status_code == 401

    async def test_stream_token_rejects_invalid_token(self, client):
        resp = await client.get(
            "/api/v2/events/stream-token",
            headers={"Authorization": "Bearer garbage-token"},
        )
        assert resp.status_code == 401

    async def test_stream_token_rejects_creator_token(self, client, make_creator):
        """Creator tokens must not authenticate on agent-only endpoints."""
        _, creator_token = await make_creator()
        resp = await client.get(
            "/api/v2/events/stream-token",
            headers={"Authorization": f"Bearer {creator_token}"},
        )
        assert resp.status_code == 401

    async def test_stream_token_rejects_malformed_header(self, client):
        resp = await client.get(
            "/api/v2/events/stream-token",
            headers={"Authorization": "Basic dXNlcjpwYXNz"},
        )
        assert resp.status_code == 401

    async def test_stream_token_different_agents_get_different_tokens(self, client, make_agent):
        agent_a, token_a = await make_agent(name="agent-a")
        agent_b, token_b = await make_agent(name="agent-b")

        resp_a = await client.get(
            "/api/v2/events/stream-token",
            headers={"Authorization": f"Bearer {token_a}"},
        )
        resp_b = await client.get(
            "/api/v2/events/stream-token",
            headers={"Authorization": f"Bearer {token_b}"},
        )
        assert resp_a.status_code == 200
        assert resp_b.status_code == 200
        assert resp_a.json()["agent_id"] == agent_a.id
        assert resp_b.json()["agent_id"] == agent_b.id
        assert resp_a.json()["stream_token"] != resp_b.json()["stream_token"]

    async def test_stream_token_expires_at_is_iso_format(self, client, make_agent):
        _, token = await make_agent()

        resp = await client.get(
            "/api/v2/events/stream-token",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        expires_at = resp.json()["expires_at"]
        # Should be a parseable ISO datetime string containing 'T'
        assert "T" in expires_at

    async def test_stream_token_cannot_be_used_for_api_auth(self, client, make_agent):
        """A stream token must not work for regular API endpoints."""
        _, token = await make_agent()

        resp = await client.get(
            "/api/v2/events/stream-token",
            headers={"Authorization": f"Bearer {token}"},
        )
        stream_token = resp.json()["stream_token"]

        # Attempting to use stream token on the same endpoint should fail
        resp2 = await client.get(
            "/api/v2/events/stream-token",
            headers={"Authorization": f"Bearer {stream_token}"},
        )
        assert resp2.status_code == 401
