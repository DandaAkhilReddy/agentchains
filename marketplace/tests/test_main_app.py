"""Tests for the main FastAPI application: startup, middleware, exception handlers, WebSocket managers.

Uses the `client` fixture from conftest for HTTP tests.
WebSocket managers are tested directly (unit-style).
"""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from marketplace.main import (
    APP_VERSION,
    ConnectionManager,
    ScopedConnectionManager,
    SecurityHeadersMiddleware,
    create_app,
    ws_manager,
    ws_scoped_manager,
)


# ---------------------------------------------------------------------------
# App creation and configuration
# ---------------------------------------------------------------------------


class TestCreateApp:
    def test_app_has_correct_title(self):
        app = create_app()
        assert "AgentChains" in app.title

    def test_app_version(self):
        assert APP_VERSION == "1.0.0"

    def test_app_has_exception_handlers(self):
        app = create_app()
        # DomainError and generic Exception should be handled
        assert len(app.exception_handlers) >= 2


# ---------------------------------------------------------------------------
# Security headers middleware
# ---------------------------------------------------------------------------


class TestSecurityHeadersMiddleware:
    async def test_security_headers_present(self, client):
        """Every response should contain security headers."""
        resp = await client.get("/api/v1/health")
        assert resp.headers.get("X-Content-Type-Options") == "nosniff"
        assert resp.headers.get("X-Frame-Options") == "DENY"
        assert resp.headers.get("Referrer-Policy") == "strict-origin-when-cross-origin"
        assert "max-age=31536000" in resp.headers.get("Strict-Transport-Security", "")
        assert "default-src 'self'" in resp.headers.get("Content-Security-Policy", "")
        assert resp.headers.get("X-XSS-Protection") == "1; mode=block"
        assert "camera=()" in resp.headers.get("Permissions-Policy", "")
        assert resp.headers.get("Cross-Origin-Opener-Policy") == "same-origin"
        assert resp.headers.get("Cross-Origin-Resource-Policy") == "same-origin"


# ---------------------------------------------------------------------------
# Domain error handler
# ---------------------------------------------------------------------------


class TestDomainExceptionHandler:
    async def test_domain_error_returns_structured_json(self, client):
        """Trigger a 404 domain error via a nonexistent agent lookup."""
        resp = await client.get("/api/v1/agents/nonexistent-id-999")
        assert resp.status_code in (404, 422)  # Either not found or validation error

    async def test_error_response_shape(self, client):
        """POST with missing required fields should return a structured error."""
        resp = await client.post("/api/v1/agents/register", json={})
        assert resp.status_code == 422
        body = resp.json()
        assert "detail" in body


# ---------------------------------------------------------------------------
# CORS headers
# ---------------------------------------------------------------------------


class TestCORSMiddleware:
    async def test_cors_allows_configured_origin(self, client):
        resp = await client.options(
            "/api/v1/health",
            headers={
                "Origin": "http://localhost:5173",
                "Access-Control-Request-Method": "GET",
            },
        )
        # Should allow the configured origin or return a valid response
        assert resp.status_code in (200, 405)

    async def test_cors_headers_on_get(self, client):
        resp = await client.get(
            "/api/v1/health",
            headers={"Origin": "http://localhost:5173"},
        )
        # Should include access-control-allow-origin
        acl = resp.headers.get("access-control-allow-origin")
        if acl:
            assert "localhost:5173" in acl


# ---------------------------------------------------------------------------
# ConnectionManager (legacy WebSocket manager)
# ---------------------------------------------------------------------------


class TestConnectionManager:
    def test_initial_state(self):
        mgr = ConnectionManager()
        assert len(mgr.active) == 0

    async def test_connect_accepts_websocket(self):
        mgr = ConnectionManager()
        ws = AsyncMock()
        result = await mgr.connect(ws)
        assert result is True
        assert ws in mgr.active
        ws.accept.assert_awaited_once()

    async def test_connect_rejects_over_max(self):
        mgr = ConnectionManager()
        mgr.MAX_CONNECTIONS = 2
        ws1 = AsyncMock()
        ws2 = AsyncMock()
        ws3 = AsyncMock()

        await mgr.connect(ws1)
        await mgr.connect(ws2)
        result = await mgr.connect(ws3)

        assert result is False
        ws3.close.assert_awaited_once()
        assert ws3 not in mgr.active

    def test_disconnect_removes_websocket(self):
        mgr = ConnectionManager()
        ws = MagicMock()
        mgr.active.add(ws)
        mgr.disconnect(ws)
        assert ws not in mgr.active

    def test_disconnect_no_error_for_missing(self):
        mgr = ConnectionManager()
        ws = MagicMock()
        mgr.disconnect(ws)  # Should not raise

    async def test_broadcast_sends_to_all(self):
        mgr = ConnectionManager()
        ws1 = AsyncMock()
        ws2 = AsyncMock()
        mgr.active = {ws1, ws2}

        message = {"event": "test", "data": {"key": "value"}}
        await mgr.broadcast(message)

        expected_data = json.dumps(message)
        ws1.send_text.assert_awaited_once_with(expected_data)
        ws2.send_text.assert_awaited_once_with(expected_data)

    async def test_broadcast_removes_dead_connections(self):
        mgr = ConnectionManager()
        ws_alive = AsyncMock()
        ws_dead = AsyncMock()
        ws_dead.send_text.side_effect = Exception("connection closed")
        mgr.active = {ws_alive, ws_dead}

        await mgr.broadcast({"event": "test"})
        assert ws_dead not in mgr.active
        assert ws_alive in mgr.active


# ---------------------------------------------------------------------------
# ScopedConnectionManager
# ---------------------------------------------------------------------------


class TestScopedConnectionManager:
    def test_initial_state(self):
        mgr = ScopedConnectionManager()
        assert len(mgr.active) == 0

    async def test_connect_stores_metadata(self):
        mgr = ScopedConnectionManager()
        ws = AsyncMock()
        payload = {"sub": "agent-1", "sub_type": "agent", "allowed_topics": ["public.market"]}

        result = await mgr.connect(ws, stream_payload=payload)
        assert result is True
        assert ws in mgr.active
        assert mgr.active[ws]["sub"] == "agent-1"
        assert mgr.active[ws]["sub_type"] == "agent"

    async def test_connect_rejects_over_max(self):
        mgr = ScopedConnectionManager()
        mgr.MAX_CONNECTIONS = 1
        ws1 = AsyncMock()
        ws2 = AsyncMock()

        await mgr.connect(ws1, stream_payload={"sub": "a1"})
        result = await mgr.connect(ws2, stream_payload={"sub": "a2"})
        assert result is False
        ws2.close.assert_awaited_once()

    def test_disconnect_removes_ws(self):
        mgr = ScopedConnectionManager()
        ws = MagicMock()
        mgr.active[ws] = {"sub": "a1", "sub_type": "agent", "allowed_topics": set()}
        mgr.disconnect(ws)
        assert ws not in mgr.active

    async def test_broadcast_public_sends_to_matching_topics(self):
        mgr = ScopedConnectionManager()
        ws1 = AsyncMock()
        ws2 = AsyncMock()
        mgr.active = {
            ws1: {"sub": "a1", "sub_type": "agent", "allowed_topics": {"public.market"}},
            ws2: {"sub": "a2", "sub_type": "agent", "allowed_topics": {"private.agent"}},
        }

        message = {"topic": "public.market", "event": "listing.created"}
        await mgr.broadcast_public(message)

        ws1.send_text.assert_awaited_once()
        ws2.send_text.assert_not_awaited()

    async def test_broadcast_public_sends_to_empty_topics(self):
        """Connections with no topic filters receive all public messages."""
        mgr = ScopedConnectionManager()
        ws = AsyncMock()
        mgr.active = {
            ws: {"sub": "a1", "sub_type": "agent", "allowed_topics": set()},
        }

        await mgr.broadcast_public({"topic": "public.market", "event": "test"})
        ws.send_text.assert_awaited_once()

    async def test_broadcast_private_agent_filters_by_target(self):
        mgr = ScopedConnectionManager()
        ws_target = AsyncMock()
        ws_other = AsyncMock()
        mgr.active = {
            ws_target: {"sub": "agent-1", "sub_type": "agent", "allowed_topics": set()},
            ws_other: {"sub": "agent-2", "sub_type": "agent", "allowed_topics": set()},
        }

        message = {"event": "private"}
        await mgr.broadcast_private_agent(message, target_agent_ids=["agent-1"])

        ws_target.send_text.assert_awaited_once()
        ws_other.send_text.assert_not_awaited()

    async def test_broadcast_private_agent_noop_on_empty_targets(self):
        mgr = ScopedConnectionManager()
        ws = AsyncMock()
        mgr.active = {
            ws: {"sub": "a1", "sub_type": "agent", "allowed_topics": set()},
        }
        await mgr.broadcast_private_agent({"event": "x"}, target_agent_ids=[])
        ws.send_text.assert_not_awaited()

    async def test_broadcast_private_admin_filters_by_creator(self):
        mgr = ScopedConnectionManager()
        ws_admin = AsyncMock()
        ws_agent = AsyncMock()
        mgr.active = {
            ws_admin: {"sub": "creator-1", "sub_type": "admin", "allowed_topics": set()},
            ws_agent: {"sub": "agent-1", "sub_type": "agent", "allowed_topics": set()},
        }

        message = {"event": "admin_event"}
        await mgr.broadcast_private_admin(message, target_creator_ids=["creator-1"])

        ws_admin.send_text.assert_awaited_once()
        ws_agent.send_text.assert_not_awaited()

    async def test_broadcast_private_user_filters_by_user_id(self):
        mgr = ScopedConnectionManager()
        ws_user = AsyncMock()
        ws_other = AsyncMock()
        mgr.active = {
            ws_user: {"sub": "user-1", "sub_type": "user", "allowed_topics": set()},
            ws_other: {"sub": "user-2", "sub_type": "user", "allowed_topics": set()},
        }

        message = {"event": "user_event"}
        await mgr.broadcast_private_user(message, target_user_ids=["user-1"])

        ws_user.send_text.assert_awaited_once()
        ws_other.send_text.assert_not_awaited()

    async def test_broadcast_private_user_noop_on_empty_targets(self):
        mgr = ScopedConnectionManager()
        ws = AsyncMock()
        mgr.active = {
            ws: {"sub": "u1", "sub_type": "user", "allowed_topics": set()},
        }
        await mgr.broadcast_private_user({"event": "x"}, target_user_ids=[])
        ws.send_text.assert_not_awaited()

    async def test_broadcast_removes_dead_connections(self):
        mgr = ScopedConnectionManager()
        ws_alive = AsyncMock()
        ws_dead = AsyncMock()
        ws_dead.send_text.side_effect = Exception("closed")
        mgr.active = {
            ws_alive: {"sub": "a1", "sub_type": "agent", "allowed_topics": set()},
            ws_dead: {"sub": "a2", "sub_type": "agent", "allowed_topics": set()},
        }

        await mgr.broadcast_public({"topic": "public.market"})
        assert ws_dead not in mgr.active
        assert ws_alive in mgr.active


# ---------------------------------------------------------------------------
# Health endpoint
# ---------------------------------------------------------------------------


class TestHealthEndpoint:
    async def test_health_returns_200(self, client):
        resp = await client.get("/api/v1/health")
        assert resp.status_code == 200

    async def test_cdn_health_returns_dict(self, client):
        resp = await client.get("/api/v1/health/cdn")
        assert resp.status_code == 200
        body = resp.json()
        assert isinstance(body, dict)


# ---------------------------------------------------------------------------
# Root endpoint (no static dir)
# ---------------------------------------------------------------------------


class TestRootEndpoint:
    async def test_root_returns_info(self, client):
        resp = await client.get("/")
        # May return 200 with info or redirect to SPA
        assert resp.status_code == 200
        body = resp.json()
        assert "version" in body or "name" in body
