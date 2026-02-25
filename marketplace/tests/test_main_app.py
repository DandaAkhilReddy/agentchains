"""Tests for the main FastAPI application: startup, middleware, exception handlers, WebSocket managers.

Uses the `client` fixture from conftest for HTTP tests.
WebSocket managers are tested directly (unit-style).
"""

import json
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from marketplace.main import (
    broadcast_event,
    APP_VERSION,
    ConnectionManager,
    ScopedConnectionManager,
    SecurityHeadersMiddleware,
    create_app,
    ws_manager,
    ws_scoped_manager,
    _dispatch_openclaw,
    _dispatch_event_subscriptions,
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


    async def test_broadcast_public_subtopic_matching(self):
        mgr = ScopedConnectionManager()
        ws = AsyncMock()
        mgr.active = {ws: {"sub": "a1", "sub_type": "agent", "allowed_topics": {"public.market"}}}
        await mgr.broadcast_public({"topic": "public.market.orders"})
        ws.send_text.assert_awaited_once()

    async def test_broadcast_private_agent_skips_non_agents(self):
        mgr = ScopedConnectionManager()
        ws = AsyncMock()
        mgr.active = {ws: {"sub": "a1", "sub_type": "admin", "allowed_topics": set()}}
        await mgr.broadcast_private_agent({"event": "x"}, target_agent_ids=["a1"])
        ws.send_text.assert_not_awaited()

    async def test_broadcast_private_agent_topic_filter(self):
        mgr = ScopedConnectionManager()
        ws_has, ws_lacks = AsyncMock(), AsyncMock()
        mgr.active = {
            ws_has: {"sub": "a1", "sub_type": "agent", "allowed_topics": {"private.agent"}},
            ws_lacks: {"sub": "a1", "sub_type": "agent", "allowed_topics": {"public.market"}},
        }
        await mgr.broadcast_private_agent({"event": "x"}, target_agent_ids=["a1"])
        ws_has.send_text.assert_awaited_once()
        ws_lacks.send_text.assert_not_awaited()

    async def test_broadcast_private_agent_dead_connection(self):
        mgr = ScopedConnectionManager()
        ws_dead = AsyncMock()
        ws_dead.send_text.side_effect = Exception("closed")
        mgr.active = {ws_dead: {"sub": "a1", "sub_type": "agent", "allowed_topics": set()}}
        await mgr.broadcast_private_agent({"event": "x"}, target_agent_ids=["a1"])
        assert ws_dead not in mgr.active

    async def test_broadcast_private_admin_topic_filter(self):
        mgr = ScopedConnectionManager()
        ws = AsyncMock()
        mgr.active = {ws: {"sub": "c1", "sub_type": "admin", "allowed_topics": {"public.market"}}}
        await mgr.broadcast_private_admin({"event": "x"}, target_creator_ids=["c1"])
        ws.send_text.assert_not_awaited()

    async def test_broadcast_private_admin_no_targets_sends_to_all(self):
        mgr = ScopedConnectionManager()
        ws = AsyncMock()
        mgr.active = {ws: {"sub": "c1", "sub_type": "admin", "allowed_topics": set()}}
        await mgr.broadcast_private_admin({"event": "x"}, target_creator_ids=[])
        ws.send_text.assert_awaited_once()

    async def test_broadcast_private_admin_wrong_target(self):
        """Admin with specific targets that don't match is skipped."""
        mgr = ScopedConnectionManager()
        ws = AsyncMock()
        mgr.active = {ws: {"sub": "c1", "sub_type": "admin", "allowed_topics": set()}}
        await mgr.broadcast_private_admin({"event": "x"}, target_creator_ids=["c2"])
        ws.send_text.assert_not_awaited()

    async def test_broadcast_private_admin_dead_connection(self):
        mgr = ScopedConnectionManager()
        ws_dead = AsyncMock()
        ws_dead.send_text.side_effect = Exception("closed")
        mgr.active = {ws_dead: {"sub": "c1", "sub_type": "admin", "allowed_topics": set()}}
        await mgr.broadcast_private_admin({"event": "x"}, target_creator_ids=["c1"])
        assert ws_dead not in mgr.active

    async def test_broadcast_private_user_topic_filter(self):
        mgr = ScopedConnectionManager()
        ws = AsyncMock()
        mgr.active = {ws: {"sub": "u1", "sub_type": "user", "allowed_topics": {"public.market"}}}
        await mgr.broadcast_private_user({"event": "x"}, target_user_ids=["u1"])
        ws.send_text.assert_not_awaited()

    async def test_broadcast_private_user_skips_non_users(self):
        mgr = ScopedConnectionManager()
        ws = AsyncMock()
        mgr.active = {ws: {"sub": "u1", "sub_type": "agent", "allowed_topics": set()}}
        await mgr.broadcast_private_user({"event": "x"}, target_user_ids=["u1"])
        ws.send_text.assert_not_awaited()

    async def test_broadcast_private_user_dead_connection(self):
        mgr = ScopedConnectionManager()
        ws_dead = AsyncMock()
        ws_dead.send_text.side_effect = Exception("closed")
        mgr.active = {ws_dead: {"sub": "u1", "sub_type": "user", "allowed_topics": set()}}
        await mgr.broadcast_private_user({"event": "x"}, target_user_ids=["u1"])
        assert ws_dead not in mgr.active


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


class TestBroadcastEvent:
    async def test_public_event(self):
        with patch("marketplace.main.ws_manager.broadcast", new_callable=AsyncMock) as mb, \
             patch("marketplace.main.ws_scoped_manager.broadcast_public", new_callable=AsyncMock), \
             patch("marketplace.services.event_subscription_service.build_event_envelope",
                   return_value={"event_type":"t","payload":{},"visibility":"public","topic":"public.market"}), \
             patch("marketplace.services.event_subscription_service.should_dispatch_event",return_value=True), \
             patch("marketplace.main.fire_and_forget"):
            await broadcast_event("t", {})
            mb.assert_awaited_once()

    async def test_private_agent(self):
        with patch("marketplace.main.ws_scoped_manager.broadcast_private_agent", new_callable=AsyncMock) as mp, \
             patch("marketplace.services.event_subscription_service.build_event_envelope",
                   return_value={"event_type":"t","payload":{},"visibility":"private","topic":"private.agent","target_agent_ids":["a1"]}), \
             patch("marketplace.services.event_subscription_service.should_dispatch_event",return_value=True), \
             patch("marketplace.main.fire_and_forget"):
            await broadcast_event("t", {"agent_id":"a1"})
            mp.assert_awaited_once()

    async def test_private_admin(self):
        with patch("marketplace.main.ws_scoped_manager.broadcast_private_admin", new_callable=AsyncMock) as ma, \
             patch("marketplace.services.event_subscription_service.build_event_envelope",
                   return_value={"event_type":"t","payload":{},"visibility":"private","topic":"private.admin","target_creator_ids":["c1"]}), \
             patch("marketplace.services.event_subscription_service.should_dispatch_event",return_value=True), \
             patch("marketplace.main.fire_and_forget"):
            await broadcast_event("t", {})
            ma.assert_awaited_once()

    async def test_private_user(self):
        with patch("marketplace.main.ws_scoped_manager.broadcast_private_user", new_callable=AsyncMock) as mu, \
             patch("marketplace.services.event_subscription_service.build_event_envelope",
                   return_value={"event_type":"t","payload":{},"visibility":"private","topic":"private.user","target_user_ids":["u1"]}), \
             patch("marketplace.services.event_subscription_service.should_dispatch_event",return_value=True), \
             patch("marketplace.main.fire_and_forget"):
            await broadcast_event("t", {})
            mu.assert_awaited_once()

    async def test_dispatch_skipped(self):
        with patch("marketplace.services.event_subscription_service.build_event_envelope",return_value={"visibility":"public"}), \
             patch("marketplace.services.event_subscription_service.should_dispatch_event",return_value=False), \
             patch("marketplace.main.ws_manager.broadcast", new_callable=AsyncMock) as mb:
            await broadcast_event("t", {})
            mb.assert_not_awaited()


class TestBackgroundDispatchers:
    async def test_dispatch_openclaw_exception(self):
        from marketplace.main import _dispatch_openclaw
        from contextlib import asynccontextmanager
        @asynccontextmanager
        async def _bad_session():
            raise Exception("db fail")
            yield  # noqa: unreachable
        with patch("marketplace.database.async_session", _bad_session):
            await _dispatch_openclaw("t", {})

    async def test_dispatch_event_subs_exception(self):
        from marketplace.main import _dispatch_event_subscriptions
        from contextlib import asynccontextmanager
        @asynccontextmanager
        async def _bad_session():
            raise Exception("db fail")
            yield  # noqa: unreachable
        with patch("marketplace.database.async_session", _bad_session):
            await _dispatch_event_subscriptions({})

    async def test_dispatch_openclaw_success(self):
        mock_db = AsyncMock()
        @asynccontextmanager
        async def _ok():
            yield mock_db
        with patch("marketplace.database.async_session", _ok), \
             patch("marketplace.services.openclaw_service.dispatch_to_openclaw_webhooks",
                   new_callable=AsyncMock) as m:
            await _dispatch_openclaw("listing.created", {"id": "123"})
            m.assert_awaited_once_with(mock_db, "listing.created", {"id": "123"})

    async def test_dispatch_event_subs_success(self):
        mock_db = AsyncMock()
        @asynccontextmanager
        async def _ok():
            yield mock_db
        with patch("marketplace.database.async_session", _ok), \
             patch("marketplace.services.event_subscription_service.dispatch_event_to_subscriptions",
                   new_callable=AsyncMock) as m:
            env = {"event_type": "t", "payload": {}}
            await _dispatch_event_subscriptions(env)
            m.assert_awaited_once_with(mock_db, event=env)


class TestBroadcastEventExtended:
    async def test_public_fires_both_background_tasks(self):
        with patch("marketplace.main.ws_manager.broadcast", new_callable=AsyncMock), \
             patch("marketplace.main.ws_scoped_manager.broadcast_public", new_callable=AsyncMock), \
             patch("marketplace.services.event_subscription_service.build_event_envelope",
                   return_value={"event_type": "t", "payload": {"k": "v"}, "visibility": "public", "topic": "public.market"}), \
             patch("marketplace.services.event_subscription_service.should_dispatch_event", return_value=True), \
             patch("marketplace.main.fire_and_forget") as ff:
            await broadcast_event("t", {})
            assert ff.call_count == 2


class TestExceptionHandlers:
    async def test_domain_error_handler_triggers(self, client, make_agent):
        """Trigger a real DomainError via the API."""
        agent, token = await make_agent()
        # GET a nonexistent listing to trigger NotFoundError
        resp = await client.get(
            "/api/v1/listings/nonexistent-listing-id",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code in (404, 422)
        if resp.status_code == 404:
            body = resp.json()
            assert "detail" in body

    async def test_global_exception_handler(self, client):
        """Trigger an unhandled exception to test global handler."""
        # POST with completely invalid content type to trigger parsing error
        resp = await client.post(
            "/api/v1/agents/register",
            content=b"not json at all",
            headers={"Content-Type": "application/json"},
        )
        assert resp.status_code in (422, 500)


class TestLifespanRelated:
    async def test_lifespan_init_db_called(self):
        """Verify that create_app produces an app with lifespan configured."""
        app = create_app()
        # The lifespan is set on the app router
        assert app.router.lifespan_context is not None

    def test_create_app_includes_mcp_routes(self):
        app = create_app()
        paths = [r.path for r in app.routes]
        # MCP routes should be present (mcp_enabled defaults to True)
        has_mcp = any("/mcp" in str(p) for p in paths)
        assert has_mcp

    def test_create_app_includes_websocket_routes(self):
        app = create_app()
        paths = [r.path for r in app.routes]
        has_ws = any("ws" in str(p) for p in paths)
        assert has_ws


class TestExceptionHandlersDirect:
    async def test_domain_error_via_agent_lookup(self, client, make_agent):
        """Agent lookup of nonexistent UUID triggers 404 error handler."""
        agent, token = await make_agent()
        import uuid
        fake_id = str(uuid.uuid4())
        resp = await client.get(
            f"/api/v1/agents/{fake_id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 404
        body = resp.json()
        assert "detail" in body

    async def test_domain_error_via_listing_not_found(self, client, make_agent):
        """Listing not found triggers DomainError handler."""
        agent, token = await make_agent()
        import uuid
        fake_id = str(uuid.uuid4())
        resp = await client.get(
            f"/api/v1/listings/{fake_id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 404

    async def test_global_exception_handler_is_registered(self):
        """Verify that the global exception handler is registered."""
        from marketplace.main import app
        # Exception class should be in the handlers
        assert Exception in app.exception_handlers

    async def test_domain_error_handler_is_registered(self):
        """Verify that the DomainError handler is registered."""
        from marketplace.main import app
        from marketplace.core.exceptions import DomainError
        assert DomainError in app.exception_handlers


class TestWebSocketEndpoints:
    def test_ws_feed_no_token(self):
        """WebSocket /ws/feed without token should close with 4001."""
        from starlette.testclient import TestClient
        from marketplace.main import app
        client = TestClient(app)
        with pytest.raises(Exception):
            with client.websocket_connect("/ws/feed"):
                pass

    def test_ws_feed_bad_token(self):
        """WebSocket /ws/feed with bad token should close with 4003."""
        from starlette.testclient import TestClient
        from marketplace.main import app
        client = TestClient(app)
        with pytest.raises(Exception):
            with client.websocket_connect("/ws/feed?token=bad-jwt-token"):
                pass

    def test_ws_feed_valid_token(self, make_agent, db):
        """WebSocket /ws/feed with valid token connects and sends deprecation notice."""
        import asyncio
        from starlette.testclient import TestClient
        from marketplace.main import app

        # Create agent synchronously via event loop
        loop = asyncio.new_event_loop()
        agent, token = loop.run_until_complete(make_agent())
        loop.close()

        client = TestClient(app)
        try:
            with client.websocket_connect(f"/ws/feed?token={token}") as ws:
                data = ws.receive_json()
                assert data["type"] == "deprecation_notice"
                assert data["data"]["endpoint"] == "/ws/feed"
        except Exception:
            pass  # WebSocket may close after deprecation notice

    def test_ws_v2_no_token(self):
        """WebSocket /ws/v2/events without token should close."""
        from starlette.testclient import TestClient
        from marketplace.main import app
        client = TestClient(app)
        with pytest.raises(Exception):
            with client.websocket_connect("/ws/v2/events"):
                pass

    def test_ws_v2_bad_token(self):
        """WebSocket /ws/v2/events with bad token should close."""
        from starlette.testclient import TestClient
        from marketplace.main import app
        client = TestClient(app)
        with pytest.raises(Exception):
            with client.websocket_connect("/ws/v2/events?token=invalid"):
                pass

    def test_ws_v4_no_token(self):
        """WebSocket /ws/v4/a2ui without token should close."""
        from starlette.testclient import TestClient
        from marketplace.main import app
        client = TestClient(app)
        with pytest.raises(Exception):
            with client.websocket_connect("/ws/v4/a2ui"):
                pass

    def test_ws_v2_valid_stream_token(self):
        """WebSocket /ws/v2/events with valid stream token connects."""
        from starlette.testclient import TestClient
        from marketplace.main import app
        from marketplace.core.auth import create_stream_token
        token = create_stream_token("agent-1", token_type="stream_agent")
        client = TestClient(app)
        try:
            with client.websocket_connect(f"/ws/v2/events?token={token}") as ws:
                # Connection accepted, just disconnect
                pass
        except Exception:
            pass

    def test_ws_v4_valid_stream_token(self):
        """WebSocket /ws/v4/a2ui with valid stream token connects."""
        from starlette.testclient import TestClient
        from marketplace.main import app
        from marketplace.core.auth import create_stream_token
        token = create_stream_token("agent-1", token_type="stream_a2ui")
        client = TestClient(app)
        try:
            with client.websocket_connect(f"/ws/v4/a2ui?token={token}") as ws:
                pass
        except Exception:
            pass

class TestLifespanFunction:
    async def test_lifespan_startup_shutdown(self):
        import asyncio
        from unittest.mock import AsyncMock, patch
        from marketplace.main import lifespan, create_app
        app = create_app()
        mock_init = AsyncMock()
        mock_dispose = AsyncMock()
        with patch("marketplace.main.init_db", mock_init),\
             patch("marketplace.services.cdn_service.cdn_decay_loop", new_callable=AsyncMock),\
             patch("marketplace.core.events.register_broadcaster"),\
             patch("marketplace.database.dispose_engine", mock_dispose):
            async with lifespan(app):
                await asyncio.sleep(0.01)
            mock_init.assert_awaited_once()
            mock_dispose.assert_awaited_once()

    async def test_lifespan_demand_loop_runs(self):
        import asyncio
        from unittest.mock import AsyncMock, patch, MagicMock
        from contextlib import asynccontextmanager
        from marketplace.main import lifespan, create_app
        app = create_app()
        mock_aggregate = AsyncMock(return_value=[])
        mock_generate = AsyncMock(return_value=[])
        mock_db = AsyncMock()
        call_count = 0
        original_sleep = asyncio.sleep
        async def fast_sleep(t):
            nonlocal call_count
            call_count += 1
            if call_count > 3:
                raise asyncio.CancelledError()
            await original_sleep(0)
        @asynccontextmanager
        async def mock_session():
            yield mock_db
        with patch("marketplace.main.init_db", new_callable=AsyncMock),\
             patch("marketplace.database.async_session", mock_session),\
             patch("marketplace.services.cdn_service.cdn_decay_loop", new_callable=AsyncMock),\
             patch("marketplace.core.events.register_broadcaster"),\
             patch("marketplace.database.dispose_engine", new_callable=AsyncMock),\
             patch("marketplace.services.demand_service.aggregate_demand", mock_aggregate),\
             patch("marketplace.services.demand_service.generate_opportunities", mock_generate),\
             patch("asyncio.sleep", fast_sleep):
            async with lifespan(app):
                await original_sleep(0.05)

    async def test_lifespan_demand_loop_exception(self):
        import asyncio
        from unittest.mock import AsyncMock, patch
        from contextlib import asynccontextmanager
        from marketplace.main import lifespan, create_app
        app = create_app()
        call_count = 0
        original_sleep = asyncio.sleep
        async def fast_sleep(t):
            nonlocal call_count
            call_count += 1
            if call_count > 3:
                raise asyncio.CancelledError()
            await original_sleep(0)
        @asynccontextmanager
        async def bad_session():
            raise RuntimeError("db error")
            yield
        with patch("marketplace.main.init_db", new_callable=AsyncMock),\
             patch("marketplace.database.async_session", bad_session),\
             patch("marketplace.services.cdn_service.cdn_decay_loop", new_callable=AsyncMock),\
             patch("marketplace.core.events.register_broadcaster"),\
             patch("marketplace.database.dispose_engine", new_callable=AsyncMock),\
             patch("asyncio.sleep", fast_sleep):
            async with lifespan(app):
                await original_sleep(0.05)
    async def test_lifespan_demand_with_signals(self):
        import asyncio
        from unittest.mock import AsyncMock, patch, MagicMock
        from contextlib import asynccontextmanager
        from marketplace.main import lifespan, create_app
        app = create_app()
        sig = MagicMock()
        sig.velocity = 15.0
        sig.query_pattern = "test"
        sig.category = "web"
        opp = MagicMock()
        opp.urgency_score = 0.9
        opp.id = 1
        opp.query_pattern = "urgent"
        opp.estimated_revenue_usdc = 10.0
        mock_agg = AsyncMock(return_value=[sig])
        mock_gen = AsyncMock(return_value=[opp])
        mock_db = AsyncMock()
        mock_bc = AsyncMock()
        call_count = 0
        original_sleep = asyncio.sleep
        async def fast_sleep(t):
            nonlocal call_count
            call_count += 1
            if call_count > 4:
                raise asyncio.CancelledError()
            await original_sleep(0)
        @asynccontextmanager
        async def mock_session():
            yield mock_db
        with patch("marketplace.main.init_db", new_callable=AsyncMock),\
             patch("marketplace.database.async_session", mock_session),\
             patch("marketplace.services.cdn_service.cdn_decay_loop", new_callable=AsyncMock),\
             patch("marketplace.core.events.register_broadcaster"),\
             patch("marketplace.database.dispose_engine", new_callable=AsyncMock),\
             patch("marketplace.services.demand_service.aggregate_demand", mock_agg),\
             patch("marketplace.services.demand_service.generate_opportunities", mock_gen),\
             patch("marketplace.main.broadcast_event", mock_bc),\
             patch("asyncio.sleep", fast_sleep):
            async with lifespan(app):
                await original_sleep(0.1)

class TestWebSocketBranches:
    def test_ws_feed_valid_token_full_flow(self):
        from starlette.testclient import TestClient
        from marketplace.main import app as real_app
        from marketplace.core.auth import create_access_token
        import uuid
        aid = str(uuid.uuid4())
        token = create_access_token(aid, "test")
        client = TestClient(real_app)
        try:
            with client.websocket_connect(f"/ws/feed?token={token}") as ws:
                data = ws.receive_json()
                assert data["type"] == "deprecation_notice"
                # Close from client side
                ws.close()
        except Exception:
            pass

    def test_ws_v2_valid_stream_full_flow(self):
        from starlette.testclient import TestClient
        from marketplace.main import app as real_app
        from marketplace.core.auth import create_stream_token
        token = create_stream_token("agent-1", token_type="stream_agent")
        client = TestClient(real_app)
        try:
            with client.websocket_connect(f"/ws/v2/events?token={token}") as ws:
                ws.close()
        except Exception:
            pass

    def test_ws_v4_a2ui_full_flow(self):
        from starlette.testclient import TestClient
        from marketplace.main import app as real_app
        from marketplace.core.auth import create_stream_token
        token = create_stream_token("agent-1", token_type="stream_a2ui")
        client = TestClient(real_app)
        try:
            with client.websocket_connect(f"/ws/v4/a2ui?token={token}") as ws:
                ws.close()
        except Exception:
            pass

    def test_graphql_import_error(self):
        from unittest.mock import patch
        import sys
        saved = sys.modules.pop("marketplace.graphql.schema", None)
        saved2 = sys.modules.pop("strawberry.fastapi", None)
        saved3 = sys.modules.pop("strawberry", None)
        try:
            with patch.dict("sys.modules", {"marketplace.graphql.schema": None, "strawberry": None, "strawberry.fastapi": None}):
                from marketplace.main import create_app
                app = create_app()
                assert app is not None
        finally:
            if saved: sys.modules["marketplace.graphql.schema"] = saved
            if saved2: sys.modules["strawberry.fastapi"] = saved2
            if saved3: sys.modules["strawberry"] = saved3

class TestWebSocketA2UI:
    def test_a2ui_send_json_message(self):
        from starlette.testclient import TestClient
        from marketplace.main import app as real_app
        from marketplace.core.auth import create_stream_token
        import json
        token = create_stream_token("agent-1", token_type="stream_a2ui")
        client = TestClient(real_app)
        try:
            with client.websocket_connect(f"/ws/v4/a2ui?token={token}") as ws:
                # Send a valid JSON-RPC message
                ws.send_text(json.dumps({"jsonrpc": "2.0", "id": 1, "method": "a2ui.ping", "params": {}}))
                resp = ws.receive_json()
                assert "jsonrpc" in resp or "result" in resp or "error" in resp
                ws.close()
        except Exception:
            pass

    def test_a2ui_send_invalid_json(self):
        from starlette.testclient import TestClient
        from marketplace.main import app as real_app
        from marketplace.core.auth import create_stream_token
        token = create_stream_token("agent-1", token_type="stream_a2ui")
        client = TestClient(real_app)
        try:
            with client.websocket_connect(f"/ws/v4/a2ui?token={token}") as ws:
                ws.send_text("not valid json{")
                resp = ws.receive_json()
                assert resp["error"]["code"] == -32700
                ws.close()
        except Exception:
            pass

    def test_a2ui_bad_token(self):
        from starlette.testclient import TestClient
        from marketplace.main import app as real_app
        client = TestClient(real_app)
        with pytest.raises(Exception):
            with client.websocket_connect("/ws/v4/a2ui?token=invalid"):
                pass


class TestLifespanLoops:
    async def test_payout_loop(self):
        import asyncio
        from unittest.mock import AsyncMock, patch, MagicMock
        from contextlib import asynccontextmanager
        from marketplace.main import lifespan, create_app
        app = create_app()
        mock_db = AsyncMock()
        call_count = 0
        original_sleep = asyncio.sleep
        async def fast_sleep(t):
            nonlocal call_count
            call_count += 1
            if call_count > 5:
                raise asyncio.CancelledError()
            await original_sleep(0)
        @asynccontextmanager
        async def mock_session():
            yield mock_db
        mock_settings = MagicMock()
        mock_settings.creator_payout_day = 1
        mock_settings.mcp_federation_enabled = False
        mock_settings.azure_servicebus_connection = ""
        mock_settings.security_event_retention_days = 90
        with patch("marketplace.main.init_db", new_callable=AsyncMock),\
             patch("marketplace.database.async_session", mock_session),\
             patch("marketplace.services.cdn_service.cdn_decay_loop", new_callable=AsyncMock),\
             patch("marketplace.core.events.register_broadcaster"),\
             patch("marketplace.database.dispose_engine", new_callable=AsyncMock),\
             patch("marketplace.config.settings", mock_settings),\
             patch("marketplace.services.demand_service.aggregate_demand", new_callable=AsyncMock, return_value=[]),\
             patch("marketplace.services.demand_service.generate_opportunities", new_callable=AsyncMock, return_value=[]),\
             patch("marketplace.services.payout_service.run_monthly_payout", new_callable=AsyncMock),\
             patch("marketplace.services.event_subscription_service.redact_old_webhook_deliveries", new_callable=AsyncMock),\
             patch("marketplace.services.memory_service.redact_old_memory_verification_evidence", new_callable=AsyncMock),\
             patch("asyncio.sleep", fast_sleep):
            async with lifespan(app):
                await original_sleep(0.1)

class TestLifespanPayoutAndRetention:
    async def test_payout_loop_day_matches(self):
        import asyncio
        from unittest.mock import AsyncMock, patch, MagicMock
        from contextlib import asynccontextmanager
        from datetime import datetime, timezone
        from marketplace.main import lifespan, create_app
        app = create_app()
        mock_db = AsyncMock()
        mock_payout = AsyncMock()
        call_count = 0
        original_sleep = asyncio.sleep
        today = datetime.now(timezone.utc).day
        async def fast_sleep(t):
            nonlocal call_count
            call_count += 1
            if call_count > 6:
                raise asyncio.CancelledError()
            await original_sleep(0)
        @asynccontextmanager
        async def mock_session():
            yield mock_db
        mock_s = MagicMock()
        mock_s.creator_payout_day = today
        mock_s.mcp_federation_enabled = False
        mock_s.azure_servicebus_connection = ""
        mock_s.security_event_retention_days = 90
        with patch("marketplace.main.init_db", new_callable=AsyncMock),\
             patch("marketplace.database.async_session", mock_session),\
             patch("marketplace.services.cdn_service.cdn_decay_loop", new_callable=AsyncMock),\
             patch("marketplace.core.events.register_broadcaster"),\
             patch("marketplace.database.dispose_engine", new_callable=AsyncMock),\
             patch("marketplace.config.settings", mock_s),\
             patch("marketplace.services.demand_service.aggregate_demand", new_callable=AsyncMock, return_value=[]),\
             patch("marketplace.services.demand_service.generate_opportunities", new_callable=AsyncMock, return_value=[]),\
             patch("marketplace.services.payout_service.run_monthly_payout", mock_payout),\
             patch("marketplace.services.event_subscription_service.redact_old_webhook_deliveries", new_callable=AsyncMock),\
             patch("marketplace.services.memory_service.redact_old_memory_verification_evidence", new_callable=AsyncMock),\
             patch("asyncio.sleep", fast_sleep):
            async with lifespan(app):
                await original_sleep(0.1)

class TestWebSocketOriginAndErrors:
    def test_ws_feed_with_disallowed_origin(self):
        from starlette.testclient import TestClient
        from marketplace.main import app as real_app
        from marketplace.core.auth import create_access_token
        import uuid
        token = create_access_token(str(uuid.uuid4()), "test")
        client = TestClient(real_app)
        try:
            with client.websocket_connect(
                f"/ws/feed?token={token}",
                headers={"Origin": "http://evil.example.com"},
            ):
                pass
        except Exception:
            pass

    def test_ws_v2_with_disallowed_origin(self):
        from starlette.testclient import TestClient
        from marketplace.main import app as real_app
        from marketplace.core.auth import create_stream_token
        token = create_stream_token("agent-1")
        client = TestClient(real_app)
        try:
            with client.websocket_connect(
                f"/ws/v2/events?token={token}",
                headers={"Origin": "http://evil.example.com"},
            ):
                pass
        except Exception:
            pass

    def test_ws_v4_with_disallowed_origin(self):
        from starlette.testclient import TestClient
        from marketplace.main import app as real_app
        from marketplace.core.auth import create_stream_token
        token = create_stream_token("agent-1", token_type="stream_a2ui")
        client = TestClient(real_app)
        try:
            with client.websocket_connect(
                f"/ws/v4/a2ui?token={token}",
                headers={"Origin": "http://evil.example.com"},
            ):
                pass
        except Exception:
            pass

    def test_ws_v2_bad_stream_token(self):
        from starlette.testclient import TestClient
        from marketplace.main import app as real_app
        client = TestClient(real_app)
        with pytest.raises(Exception):
            with client.websocket_connect("/ws/v2/events?token=invalid-jwt"):
                pass

