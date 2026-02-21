"""Deep tests for MCP Federation service, handler, health monitor, and load balancer.

67 async/sync tests across 4 test classes:
  1. TestMCPFederationService (22 tests) — register/unregister servers, discover tools,
     namespace prefixing, route tool calls, health score tracking, auth header building
  2. TestMCPFederationHandler (15 tests) — get_federated_tools, handle_federated_tool_call,
     local vs federated routing, fallback on errors, unknown tool names
  3. TestMCPHealthMonitor (15 tests) — _check_server health pings, _run_health_checks loop,
     health score updates, degraded/inactive demotion, recovery detection, interval config
  4. TestMCPLoadBalancer (15 tests) — round_robin, least_loaded, weighted, health_first,
     no healthy server, single server, reset counters, record_request/completion
"""

import asyncio
import json
import time
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch, PropertyMock

import pytest

from marketplace.models.mcp_server import MCPServerEntry
from marketplace.services.mcp_load_balancer import (
    LoadBalanceStrategy,
    MCPLoadBalancer,
    mcp_load_balancer,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_server(
    name="test-server",
    namespace="test",
    base_url="http://remote:8000",
    status="active",
    health_score=100,
    tools_json="[]",
    auth_type="none",
    auth_credential_ref="",
    server_id=None,
):
    """Create a mock MCPServerEntry with sensible defaults."""
    server = MagicMock(spec=MCPServerEntry)
    server.id = server_id or str(uuid.uuid4())
    server.name = name
    server.base_url = base_url
    server.namespace = namespace
    server.status = status
    server.health_score = health_score
    server.tools_json = tools_json
    server.auth_type = auth_type
    server.auth_credential_ref = auth_credential_ref
    server.description = ""
    server.registered_by = None
    server.created_at = datetime.now(timezone.utc)
    server.updated_at = datetime.now(timezone.utc)
    server.last_health_check = None
    return server


def _mock_db_result(items):
    """Build a mock DB result whose .scalars().all() returns items."""
    result = MagicMock()
    scalars = MagicMock()
    scalars.all.return_value = items
    result.scalars.return_value = scalars
    result.scalar_one_or_none.return_value = items[0] if items else None
    return result


# ===========================================================================
# 1. TestMCPFederationService  (22 tests)
# ===========================================================================

class TestMCPFederationService:
    """Tests for marketplace.services.mcp_federation_service."""

    # -- register_server --

    @pytest.mark.asyncio
    async def test_register_server_creates_entry(self):
        """register_server should add an MCPServerEntry to the session."""
        from marketplace.services.mcp_federation_service import register_server

        db = AsyncMock()
        db.commit = AsyncMock()
        db.refresh = AsyncMock()
        db.add = MagicMock()

        result = await register_server(
            db, name="srv1", base_url="http://a.com/", namespace="ns1"
        )
        assert isinstance(result, MCPServerEntry)
        db.add.assert_called_once()
        db.commit.assert_awaited_once()
        db.refresh.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_register_server_strips_trailing_slash(self):
        """base_url trailing slash should be stripped."""
        from marketplace.services.mcp_federation_service import register_server

        db = AsyncMock()
        db.commit = AsyncMock()
        db.refresh = AsyncMock()
        db.add = MagicMock()

        result = await register_server(
            db, name="srv2", base_url="http://b.com///", namespace="ns2"
        )
        assert result.base_url == "http://b.com"

    @pytest.mark.asyncio
    async def test_register_server_with_bearer_auth(self):
        """Auth type and credential ref should be stored."""
        from marketplace.services.mcp_federation_service import register_server

        db = AsyncMock()
        db.commit = AsyncMock()
        db.refresh = AsyncMock()
        db.add = MagicMock()

        result = await register_server(
            db,
            name="authed",
            base_url="http://c.com",
            namespace="secure",
            auth_type="bearer",
            auth_credential_ref="tok123",
        )
        assert result.auth_type == "bearer"
        assert result.auth_credential_ref == "tok123"

    @pytest.mark.asyncio
    async def test_register_server_stores_registered_by(self):
        """registered_by field should be stored."""
        from marketplace.services.mcp_federation_service import register_server

        db = AsyncMock()
        db.commit = AsyncMock()
        db.refresh = AsyncMock()
        db.add = MagicMock()

        result = await register_server(
            db, name="s", base_url="http://d.com", namespace="n", registered_by="user1"
        )
        assert result.registered_by == "user1"

    # -- unregister_server --

    @pytest.mark.asyncio
    async def test_unregister_server_found(self):
        """unregister_server returns True if server exists and is deleted."""
        from marketplace.services.mcp_federation_service import unregister_server

        server = _make_server()
        db = AsyncMock()
        db.execute = AsyncMock(return_value=_mock_db_result([server]))
        db.delete = AsyncMock()
        db.commit = AsyncMock()

        assert await unregister_server(db, server.id) is True
        db.delete.assert_awaited_once_with(server)
        db.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_unregister_server_not_found(self):
        """unregister_server returns False if server does not exist."""
        from marketplace.services.mcp_federation_service import unregister_server

        db = AsyncMock()
        db.execute = AsyncMock(return_value=_mock_db_result([]))
        result = await unregister_server(db, "missing-id")
        assert result is False

    # -- list_servers --

    @pytest.mark.asyncio
    async def test_list_servers_all(self):
        """list_servers returns all servers when no filters."""
        from marketplace.services.mcp_federation_service import list_servers

        servers = [_make_server(name=f"s{i}") for i in range(3)]
        db = AsyncMock()
        db.execute = AsyncMock(return_value=_mock_db_result(servers))

        result = await list_servers(db)
        assert len(result) == 3

    @pytest.mark.asyncio
    async def test_list_servers_with_namespace_filter(self):
        """list_servers passes namespace filter to query."""
        from marketplace.services.mcp_federation_service import list_servers

        db = AsyncMock()
        db.execute = AsyncMock(return_value=_mock_db_result([]))
        await list_servers(db, namespace="weather")
        db.execute.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_list_servers_with_status_filter(self):
        """list_servers passes status filter."""
        from marketplace.services.mcp_federation_service import list_servers

        db = AsyncMock()
        db.execute = AsyncMock(return_value=_mock_db_result([]))
        await list_servers(db, status="degraded")
        db.execute.assert_awaited_once()

    # -- get_server --

    @pytest.mark.asyncio
    async def test_get_server_found(self):
        """get_server returns the entry if it exists."""
        from marketplace.services.mcp_federation_service import get_server

        server = _make_server()
        db = AsyncMock()
        db.execute = AsyncMock(return_value=_mock_db_result([server]))
        result = await get_server(db, server.id)
        assert result is server

    @pytest.mark.asyncio
    async def test_get_server_not_found(self):
        """get_server returns None for missing ID."""
        from marketplace.services.mcp_federation_service import get_server

        db = AsyncMock()
        db.execute = AsyncMock(return_value=_mock_db_result([]))
        assert await get_server(db, "nope") is None

    # -- discover_tools --

    @pytest.mark.asyncio
    async def test_discover_tools_namespaces_tool_names(self):
        """Each tool name should be prefixed with server namespace."""
        from marketplace.services.mcp_federation_service import discover_tools

        server = _make_server(
            namespace="weather",
            tools_json=json.dumps([{"name": "forecast", "description": "Get weather"}]),
        )
        db = AsyncMock()
        db.execute = AsyncMock(return_value=_mock_db_result([server]))

        tools = await discover_tools(db)
        assert len(tools) == 1
        assert tools[0]["name"] == "weather.forecast"

    @pytest.mark.asyncio
    async def test_discover_tools_attaches_server_id(self):
        """Discovered tools carry _server_id metadata."""
        from marketplace.services.mcp_federation_service import discover_tools

        server = _make_server(
            tools_json=json.dumps([{"name": "t1", "description": "d"}]),
        )
        db = AsyncMock()
        db.execute = AsyncMock(return_value=_mock_db_result([server]))

        tools = await discover_tools(db)
        assert tools[0]["_server_id"] == server.id

    @pytest.mark.asyncio
    async def test_discover_tools_invalid_json(self):
        """Invalid tools_json should be treated as empty list."""
        from marketplace.services.mcp_federation_service import discover_tools

        server = _make_server(tools_json="NOT JSON{")
        db = AsyncMock()
        db.execute = AsyncMock(return_value=_mock_db_result([server]))

        tools = await discover_tools(db)
        assert tools == []

    @pytest.mark.asyncio
    async def test_discover_tools_empty_tools_json(self):
        """None tools_json should be treated as empty list."""
        from marketplace.services.mcp_federation_service import discover_tools

        server = _make_server(tools_json=None)
        db = AsyncMock()
        db.execute = AsyncMock(return_value=_mock_db_result([server]))

        tools = await discover_tools(db)
        assert tools == []

    @pytest.mark.asyncio
    async def test_discover_tools_multiple_servers(self):
        """Tools from multiple servers are aggregated."""
        from marketplace.services.mcp_federation_service import discover_tools

        s1 = _make_server(namespace="a", tools_json=json.dumps([{"name": "x", "description": ""}]))
        s2 = _make_server(namespace="b", tools_json=json.dumps([{"name": "y", "description": ""}]))
        db = AsyncMock()
        db.execute = AsyncMock(return_value=_mock_db_result([s1, s2]))

        tools = await discover_tools(db)
        assert len(tools) == 2
        names = {t["name"] for t in tools}
        assert names == {"a.x", "b.y"}

    # -- _build_auth_headers --

    def test_build_auth_headers_bearer(self):
        """Bearer auth returns Authorization header."""
        from marketplace.services.mcp_federation_service import _build_auth_headers

        server = _make_server(auth_type="bearer", auth_credential_ref="mytoken")
        headers = _build_auth_headers(server)
        assert headers == {"Authorization": "Bearer mytoken"}

    def test_build_auth_headers_api_key(self):
        """api_key auth returns X-API-Key header."""
        from marketplace.services.mcp_federation_service import _build_auth_headers

        server = _make_server(auth_type="api_key", auth_credential_ref="key123")
        headers = _build_auth_headers(server)
        assert headers == {"X-API-Key": "key123"}

    def test_build_auth_headers_none(self):
        """No auth returns empty headers."""
        from marketplace.services.mcp_federation_service import _build_auth_headers

        server = _make_server(auth_type="none")
        assert _build_auth_headers(server) == {}

    # -- route_tool_call --

    @pytest.mark.asyncio
    async def test_route_tool_call_no_dot_returns_error(self):
        """Tool names without a dot are invalid for routing."""
        from marketplace.services.mcp_federation_service import route_tool_call

        db = AsyncMock()
        result = await route_tool_call(db, "nodot", {}, "agent1")
        assert "error" in result
        assert "Invalid" in result["error"]

    @pytest.mark.asyncio
    async def test_route_tool_call_no_active_server(self):
        """Returns error when no active server in the namespace."""
        from marketplace.services.mcp_federation_service import route_tool_call

        db = AsyncMock()
        db.execute = AsyncMock(return_value=_mock_db_result([]))

        result = await route_tool_call(db, "missing.tool", {}, "agent1")
        assert "error" in result
        assert "No active server" in result["error"]

    @pytest.mark.asyncio
    async def test_route_tool_call_picks_highest_health(self):
        """Server with highest health_score should be selected."""
        from marketplace.services.mcp_federation_service import route_tool_call

        s1 = _make_server(name="low", health_score=50)
        s2 = _make_server(name="high", health_score=90)

        db = AsyncMock()
        db.execute = AsyncMock(return_value=_mock_db_result([s1, s2]))

        with patch("marketplace.services.mcp_federation_service.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            mock_resp = MagicMock()
            mock_resp.json.return_value = {"result": "ok"}
            mock_resp.raise_for_status = MagicMock()
            mock_client.post = AsyncMock(return_value=mock_resp)

            result = await route_tool_call(db, "test.action", {"a": 1}, "agent1")
            assert result == {"result": "ok"}
            call_url = mock_client.post.call_args[0][0]
            assert s2.base_url in call_url

    # -- update_health_score --

    @pytest.mark.asyncio
    async def test_update_health_score_clamps_to_zero(self):
        """Score should never go below 0."""
        from marketplace.services.mcp_federation_service import update_health_score

        server = _make_server(health_score=10)
        db = AsyncMock()
        db.execute = AsyncMock(return_value=_mock_db_result([server]))
        db.commit = AsyncMock()

        await update_health_score(db, server.id, -50)
        assert server.health_score == 0
        assert server.status == "inactive"


# ===========================================================================
# 2. TestMCPFederationHandler  (15 tests)
# ===========================================================================

class TestMCPFederationHandler:
    """Tests for marketplace.mcp.federation_handler."""

    @pytest.mark.asyncio
    async def test_get_federated_tools_returns_local_tools(self):
        """Local TOOL_DEFINITIONS should always be included."""
        from marketplace.mcp.federation_handler import get_federated_tools

        db = AsyncMock()
        with patch(
            "marketplace.mcp.federation_handler.discover_tools",
            new_callable=AsyncMock,
            return_value=[],
        ):
            tools = await get_federated_tools(db)
            from marketplace.mcp.tools import TOOL_DEFINITIONS
            assert len(tools) >= len(TOOL_DEFINITIONS)

    @pytest.mark.asyncio
    async def test_get_federated_tools_includes_federated(self):
        """Federated tools from remote servers are appended."""
        from marketplace.mcp.federation_handler import get_federated_tools

        remote_tool = {"name": "remote.calc", "description": "calc"}
        db = AsyncMock()
        with patch(
            "marketplace.mcp.federation_handler.discover_tools",
            new_callable=AsyncMock,
            return_value=[remote_tool],
        ):
            tools = await get_federated_tools(db)
            names = [t["name"] for t in tools]
            assert "remote.calc" in names

    @pytest.mark.asyncio
    async def test_get_federated_tools_fallback_on_error(self):
        """If discover_tools raises, only local tools are returned."""
        from marketplace.mcp.federation_handler import get_federated_tools

        db = AsyncMock()
        with patch(
            "marketplace.mcp.federation_handler.discover_tools",
            new_callable=AsyncMock,
            side_effect=Exception("db down"),
        ):
            tools = await get_federated_tools(db)
            from marketplace.mcp.tools import TOOL_DEFINITIONS
            assert len(tools) == len(TOOL_DEFINITIONS)

    @pytest.mark.asyncio
    async def test_get_federated_tools_empty_remote(self):
        """Empty remote list means only local tools."""
        from marketplace.mcp.federation_handler import get_federated_tools

        db = AsyncMock()
        with patch(
            "marketplace.mcp.federation_handler.discover_tools",
            new_callable=AsyncMock,
            return_value=[],
        ):
            tools = await get_federated_tools(db)
            from marketplace.mcp.tools import TOOL_DEFINITIONS
            assert len(tools) == len(TOOL_DEFINITIONS)

    @pytest.mark.asyncio
    async def test_get_federated_tools_deduplication_not_needed(self):
        """Remote tools have namespace prefix so no collision with local names."""
        from marketplace.mcp.federation_handler import get_federated_tools

        remote_tool = {"name": "ns.marketplace_discover", "description": "dup?"}
        db = AsyncMock()
        with patch(
            "marketplace.mcp.federation_handler.discover_tools",
            new_callable=AsyncMock,
            return_value=[remote_tool],
        ):
            tools = await get_federated_tools(db)
            names = [t["name"] for t in tools]
            assert "marketplace_discover" in names
            assert "ns.marketplace_discover" in names

    # -- handle_federated_tool_call --

    @pytest.mark.asyncio
    async def test_handle_federated_call_routes_dotted_name(self):
        """Dotted tool name triggers federated routing."""
        from marketplace.mcp.federation_handler import handle_federated_tool_call

        db = AsyncMock()
        with patch(
            "marketplace.mcp.federation_handler.route_tool_call",
            new_callable=AsyncMock,
            return_value={"ok": True},
        ) as mock_route:
            result = await handle_federated_tool_call(
                db, "weather.forecast", {"city": "NYC"}, "agent1"
            )
            assert result == {"ok": True}
            mock_route.assert_awaited_once_with(
                db, "weather.forecast", {"city": "NYC"}, "agent1"
            )

    @pytest.mark.asyncio
    async def test_handle_federated_call_local_no_dot(self):
        """Non-dotted tool name goes to local execute_tool."""
        from marketplace.mcp.federation_handler import handle_federated_tool_call

        db = AsyncMock()
        with patch(
            "marketplace.mcp.federation_handler.execute_tool",
            new_callable=AsyncMock,
            return_value={"data": "local"},
        ) as mock_exec:
            result = await handle_federated_tool_call(
                db, "marketplace_discover", {"q": "test"}, "agent1"
            )
            assert result == {"data": "local"}
            mock_exec.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_handle_federated_call_deep_dotted_name(self):
        """Names with multiple dots should still route as federated."""
        from marketplace.mcp.federation_handler import handle_federated_tool_call

        db = AsyncMock()
        with patch(
            "marketplace.mcp.federation_handler.route_tool_call",
            new_callable=AsyncMock,
            return_value={"routed": True},
        ):
            result = await handle_federated_tool_call(
                db, "org.sub.tool_name", {}, "a"
            )
            assert result == {"routed": True}

    @pytest.mark.asyncio
    async def test_handle_federated_call_empty_args(self):
        """Empty arguments dict is valid."""
        from marketplace.mcp.federation_handler import handle_federated_tool_call

        db = AsyncMock()
        with patch(
            "marketplace.mcp.federation_handler.route_tool_call",
            new_callable=AsyncMock,
            return_value={"empty": True},
        ):
            result = await handle_federated_tool_call(db, "ns.tool", {}, "a")
            assert result == {"empty": True}

    @pytest.mark.asyncio
    async def test_handle_federated_call_returns_error_from_remote(self):
        """Error dict from route_tool_call is passed through."""
        from marketplace.mcp.federation_handler import handle_federated_tool_call

        db = AsyncMock()
        with patch(
            "marketplace.mcp.federation_handler.route_tool_call",
            new_callable=AsyncMock,
            return_value={"error": "timeout"},
        ):
            result = await handle_federated_tool_call(db, "ns.fail", {}, "a")
            assert result["error"] == "timeout"

    @pytest.mark.asyncio
    async def test_handle_local_tool_passes_db(self):
        """Local execute_tool should receive the db session."""
        from marketplace.mcp.federation_handler import handle_federated_tool_call

        db = AsyncMock()
        with patch(
            "marketplace.mcp.federation_handler.execute_tool",
            new_callable=AsyncMock,
            return_value={},
        ) as mock_exec:
            await handle_federated_tool_call(db, "some_local_tool", {}, "a")
            _, kwargs = mock_exec.call_args
            assert kwargs.get("db") is db

    @pytest.mark.asyncio
    async def test_handle_federated_agent_id_forwarded(self):
        """Agent ID is forwarded to route_tool_call."""
        from marketplace.mcp.federation_handler import handle_federated_tool_call

        db = AsyncMock()
        with patch(
            "marketplace.mcp.federation_handler.route_tool_call",
            new_callable=AsyncMock,
            return_value={},
        ) as mock_route:
            await handle_federated_tool_call(db, "ns.t", {}, "agent-xyz")
            mock_route.assert_awaited_once_with(db, "ns.t", {}, "agent-xyz")

    @pytest.mark.asyncio
    async def test_handle_local_tool_agent_id_forwarded(self):
        """Agent ID is forwarded to execute_tool."""
        from marketplace.mcp.federation_handler import handle_federated_tool_call

        db = AsyncMock()
        with patch(
            "marketplace.mcp.federation_handler.execute_tool",
            new_callable=AsyncMock,
            return_value={},
        ) as mock_exec:
            await handle_federated_tool_call(db, "local_tool", {}, "agent-abc")
            mock_exec.assert_awaited_once_with("local_tool", {}, "agent-abc", db=db)

    @pytest.mark.asyncio
    async def test_handle_federated_tool_arguments_passed(self):
        """Arguments dict is forwarded to route_tool_call intact."""
        from marketplace.mcp.federation_handler import handle_federated_tool_call

        db = AsyncMock()
        args = {"lat": 40.7, "lon": -74.0, "units": "metric"}
        with patch(
            "marketplace.mcp.federation_handler.route_tool_call",
            new_callable=AsyncMock,
            return_value={"temp": 22},
        ) as mock_route:
            result = await handle_federated_tool_call(db, "weather.temp", args, "a")
            assert result == {"temp": 22}
            passed_args = mock_route.call_args[0][2]
            assert passed_args == args

    @pytest.mark.asyncio
    async def test_handle_federated_tool_name_with_leading_dot(self):
        """A name starting with a dot is still treated as federated."""
        from marketplace.mcp.federation_handler import handle_federated_tool_call

        db = AsyncMock()
        with patch(
            "marketplace.mcp.federation_handler.route_tool_call",
            new_callable=AsyncMock,
            return_value={"odd": True},
        ):
            result = await handle_federated_tool_call(db, ".weird", {}, "a")
            assert result == {"odd": True}


# ===========================================================================
# 3. TestMCPHealthMonitor  (15 tests)
# ===========================================================================

class TestMCPHealthMonitor:
    """Tests for marketplace.services.mcp_health_monitor."""

    @pytest.mark.asyncio
    async def test_check_server_healthy_200(self):
        """_check_server returns (latency, True) for 200 with status=ok."""
        from marketplace.services.mcp_health_monitor import _check_server

        server = _make_server(base_url="http://srv:9000")
        mock_client = AsyncMock()
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"status": "ok"}
        mock_client.get = AsyncMock(return_value=mock_resp)

        latency, healthy = await _check_server(mock_client, server)
        assert healthy is True
        assert latency >= 0

    @pytest.mark.asyncio
    async def test_check_server_unhealthy_status_not_ok(self):
        """_check_server returns False when status != ok."""
        from marketplace.services.mcp_health_monitor import _check_server

        server = _make_server()
        mock_client = AsyncMock()
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"status": "error"}
        mock_client.get = AsyncMock(return_value=mock_resp)

        _, healthy = await _check_server(mock_client, server)
        assert healthy is False

    @pytest.mark.asyncio
    async def test_check_server_non_200_status(self):
        """Non-200 HTTP response means unhealthy."""
        from marketplace.services.mcp_health_monitor import _check_server

        server = _make_server()
        mock_client = AsyncMock()
        mock_resp = MagicMock()
        mock_resp.status_code = 503
        mock_client.get = AsyncMock(return_value=mock_resp)

        _, healthy = await _check_server(mock_client, server)
        assert healthy is False

    @pytest.mark.asyncio
    async def test_check_server_timeout_raises(self):
        """Timeout should raise an exception."""
        import httpx
        from marketplace.services.mcp_health_monitor import _check_server

        server = _make_server()
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=httpx.TimeoutException("timeout"))

        with pytest.raises(Exception, match="Timeout"):
            await _check_server(mock_client, server)

    @pytest.mark.asyncio
    async def test_check_server_connect_error_raises(self):
        """Connection failure should raise."""
        import httpx
        from marketplace.services.mcp_health_monitor import _check_server

        server = _make_server()
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(
            side_effect=httpx.ConnectError("refused")
        )

        with pytest.raises(Exception, match="Connection failed"):
            await _check_server(mock_client, server)

    @pytest.mark.asyncio
    async def test_check_server_uses_correct_url(self):
        """Health check URL should be {base_url}/mcp/health."""
        from marketplace.services.mcp_health_monitor import _check_server

        server = _make_server(base_url="http://my-host:5000/")
        mock_client = AsyncMock()
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"status": "ok"}
        mock_client.get = AsyncMock(return_value=mock_resp)

        await _check_server(mock_client, server)
        call_url = mock_client.get.call_args[0][0]
        assert call_url == "http://my-host:5000/mcp/health"

    @pytest.mark.asyncio
    async def test_check_server_latency_positive(self):
        """Latency measurement should be a positive number."""
        from marketplace.services.mcp_health_monitor import _check_server

        server = _make_server()
        mock_client = AsyncMock()
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"status": "ok"}
        mock_client.get = AsyncMock(return_value=mock_resp)

        latency, _ = await _check_server(mock_client, server)
        assert isinstance(latency, float)
        assert latency >= 0

    @pytest.mark.asyncio
    async def test_run_health_checks_no_servers(self):
        """_run_health_checks is a no-op when no servers exist."""
        from marketplace.services.mcp_health_monitor import _run_health_checks

        mock_session_ctx = AsyncMock()
        mock_db = AsyncMock()
        mock_session_ctx.__aenter__ = AsyncMock(return_value=mock_db)
        mock_session_ctx.__aexit__ = AsyncMock(return_value=False)
        empty_result = MagicMock()
        empty_scalars = MagicMock()
        empty_scalars.all.return_value = []
        empty_result.scalars.return_value = empty_scalars
        mock_db.execute = AsyncMock(return_value=empty_result)

        mock_session_factory = MagicMock(return_value=mock_session_ctx)

        with patch(
            "marketplace.database.async_session",
            mock_session_factory,
        ):
            await _run_health_checks()

    @pytest.mark.asyncio
    async def test_run_health_checks_healthy_server_score_increases(self):
        """Healthy server score should increase by 10 (capped at 100)."""
        from marketplace.services.mcp_health_monitor import _run_health_checks

        server = _make_server(health_score=80, status="active")

        mock_session_ctx = AsyncMock()
        mock_db = AsyncMock()
        mock_session_ctx.__aenter__ = AsyncMock(return_value=mock_db)
        mock_session_ctx.__aexit__ = AsyncMock(return_value=False)

        result_obj = MagicMock()
        scalars_obj = MagicMock()
        scalars_obj.all.return_value = [server]
        result_obj.scalars.return_value = scalars_obj
        mock_db.execute = AsyncMock(return_value=result_obj)
        mock_db.commit = AsyncMock()
        mock_db.add = MagicMock()

        mock_session_factory = MagicMock(return_value=mock_session_ctx)

        with patch(
            "marketplace.database.async_session",
            mock_session_factory,
        ), patch(
            "marketplace.services.mcp_health_monitor._check_server",
            new_callable=AsyncMock,
            return_value=(5.0, True),
        ):
            await _run_health_checks()
            assert server.health_score == 90
            assert server.status == "active"

    @pytest.mark.asyncio
    async def test_run_health_checks_unhealthy_server_score_decreases(self):
        """Unhealthy server score drops by 15."""
        from marketplace.services.mcp_health_monitor import _run_health_checks

        server = _make_server(health_score=60, status="active")

        mock_session_ctx = AsyncMock()
        mock_db = AsyncMock()
        mock_session_ctx.__aenter__ = AsyncMock(return_value=mock_db)
        mock_session_ctx.__aexit__ = AsyncMock(return_value=False)
        result_obj = MagicMock()
        scalars_obj = MagicMock()
        scalars_obj.all.return_value = [server]
        result_obj.scalars.return_value = scalars_obj
        mock_db.execute = AsyncMock(return_value=result_obj)
        mock_db.commit = AsyncMock()
        mock_db.add = MagicMock()

        mock_session_factory = MagicMock(return_value=mock_session_ctx)

        with patch(
            "marketplace.database.async_session",
            mock_session_factory,
        ), patch(
            "marketplace.services.mcp_health_monitor._check_server",
            new_callable=AsyncMock,
            return_value=(100.0, False),
        ):
            await _run_health_checks()
            assert server.health_score == 45
            assert server.status == "degraded"

    @pytest.mark.asyncio
    async def test_run_health_checks_exception_degrades_server(self):
        """Exception result reduces score by 20."""
        from marketplace.services.mcp_health_monitor import _run_health_checks

        server = _make_server(health_score=30, status="active")

        mock_session_ctx = AsyncMock()
        mock_db = AsyncMock()
        mock_session_ctx.__aenter__ = AsyncMock(return_value=mock_db)
        mock_session_ctx.__aexit__ = AsyncMock(return_value=False)
        result_obj = MagicMock()
        scalars_obj = MagicMock()
        scalars_obj.all.return_value = [server]
        result_obj.scalars.return_value = scalars_obj
        mock_db.execute = AsyncMock(return_value=result_obj)
        mock_db.commit = AsyncMock()
        mock_db.add = MagicMock()

        mock_session_factory = MagicMock(return_value=mock_session_ctx)

        with patch(
            "marketplace.database.async_session",
            mock_session_factory,
        ), patch(
            "marketplace.services.mcp_health_monitor._check_server",
            new_callable=AsyncMock,
            side_effect=Exception("connection refused"),
        ):
            await _run_health_checks()
            assert server.health_score == 10
            assert server.status == "degraded"

    @pytest.mark.asyncio
    async def test_run_health_checks_score_zero_goes_inactive(self):
        """Score dropping to 0 sets server inactive."""
        from marketplace.services.mcp_health_monitor import _run_health_checks

        server = _make_server(health_score=10, status="degraded")

        mock_session_ctx = AsyncMock()
        mock_db = AsyncMock()
        mock_session_ctx.__aenter__ = AsyncMock(return_value=mock_db)
        mock_session_ctx.__aexit__ = AsyncMock(return_value=False)
        result_obj = MagicMock()
        scalars_obj = MagicMock()
        scalars_obj.all.return_value = [server]
        result_obj.scalars.return_value = scalars_obj
        mock_db.execute = AsyncMock(return_value=result_obj)
        mock_db.commit = AsyncMock()
        mock_db.add = MagicMock()

        mock_session_factory = MagicMock(return_value=mock_session_ctx)

        with patch(
            "marketplace.database.async_session",
            mock_session_factory,
        ), patch(
            "marketplace.services.mcp_health_monitor._check_server",
            new_callable=AsyncMock,
            side_effect=Exception("timeout"),
        ):
            await _run_health_checks()
            assert server.health_score == 0
            assert server.status == "inactive"

    @pytest.mark.asyncio
    async def test_run_health_checks_recovery_from_degraded(self):
        """Degraded server recovers to active when healthy."""
        from marketplace.services.mcp_health_monitor import _run_health_checks

        server = _make_server(health_score=40, status="degraded")

        mock_session_ctx = AsyncMock()
        mock_db = AsyncMock()
        mock_session_ctx.__aenter__ = AsyncMock(return_value=mock_db)
        mock_session_ctx.__aexit__ = AsyncMock(return_value=False)
        result_obj = MagicMock()
        scalars_obj = MagicMock()
        scalars_obj.all.return_value = [server]
        result_obj.scalars.return_value = scalars_obj
        mock_db.execute = AsyncMock(return_value=result_obj)
        mock_db.commit = AsyncMock()
        mock_db.add = MagicMock()

        mock_session_factory = MagicMock(return_value=mock_session_ctx)

        with patch(
            "marketplace.database.async_session",
            mock_session_factory,
        ), patch(
            "marketplace.services.mcp_health_monitor._check_server",
            new_callable=AsyncMock,
            return_value=(3.0, True),
        ):
            await _run_health_checks()
            assert server.health_score == 50
            assert server.status == "active"

    def test_health_interval_default(self):
        """Default health interval is 30 seconds."""
        from marketplace.services.mcp_health_monitor import _HEALTH_INTERVAL_SECONDS
        assert _HEALTH_INTERVAL_SECONDS == 30

    def test_health_timeout_default(self):
        """Default health timeout is 5 seconds."""
        from marketplace.services.mcp_health_monitor import _HEALTH_TIMEOUT_SECONDS
        assert _HEALTH_TIMEOUT_SECONDS == 5


# ===========================================================================
# 4. TestMCPLoadBalancer  (15 tests)
# ===========================================================================

class TestMCPLoadBalancer:
    """Tests for marketplace.services.mcp_load_balancer."""

    def setup_method(self):
        """Fresh balancer for each test."""
        self.lb = MCPLoadBalancer()

    # -- round_robin --

    def test_round_robin_cycles_through_servers(self):
        """Round-robin should cycle through servers in order."""
        s1 = _make_server(name="a", server_id="1")
        s2 = _make_server(name="b", server_id="2")
        s3 = _make_server(name="c", server_id="3")
        servers = [s1, s2, s3]

        picks = [
            self.lb.select_server(servers, "ns", LoadBalanceStrategy.ROUND_ROBIN)
            for _ in range(6)
        ]
        assert picks[0] is s1
        assert picks[1] is s2
        assert picks[2] is s3
        assert picks[3] is s1  # wraps

    def test_round_robin_separate_namespaces(self):
        """Different namespaces maintain separate counters."""
        s1 = _make_server(name="a", server_id="1")
        s2 = _make_server(name="b", server_id="2")
        servers = [s1, s2]

        r1 = self.lb.select_server(servers, "nsA", LoadBalanceStrategy.ROUND_ROBIN)
        r2 = self.lb.select_server(servers, "nsB", LoadBalanceStrategy.ROUND_ROBIN)
        assert r1 is s1
        assert r2 is s1  # nsB starts at 0

    def test_round_robin_single_server(self):
        """Single server always selected."""
        s = _make_server()
        result = self.lb.select_server([s], "ns", LoadBalanceStrategy.ROUND_ROBIN)
        assert result is s

    # -- least_loaded --

    def test_least_loaded_picks_fewest_requests(self):
        """Server with least active requests is chosen."""
        s1 = _make_server(name="busy", server_id="1")
        s2 = _make_server(name="idle", server_id="2")

        self.lb.record_request("1")
        self.lb.record_request("1")
        self.lb.record_request("1")
        self.lb.record_request("2")

        result = self.lb.select_server([s1, s2], "ns", LoadBalanceStrategy.LEAST_LOADED)
        assert result is s2

    def test_least_loaded_no_requests(self):
        """With no recorded requests, picks first server (all equal)."""
        s1 = _make_server(name="a", server_id="1")
        s2 = _make_server(name="b", server_id="2")
        result = self.lb.select_server([s1, s2], "ns", LoadBalanceStrategy.LEAST_LOADED)
        # Both have 0 requests, min picks first
        assert result is s1

    # -- weighted --

    def test_weighted_returns_a_server(self):
        """Weighted strategy returns one of the provided servers."""
        s1 = _make_server(name="a", health_score=90)
        s2 = _make_server(name="b", health_score=10)
        result = self.lb.select_server([s1, s2], "ns", LoadBalanceStrategy.WEIGHTED)
        assert result in (s1, s2)

    def test_weighted_single_server(self):
        """Single server always returned for weighted."""
        s = _make_server(health_score=50)
        result = self.lb.select_server([s], "ns", LoadBalanceStrategy.WEIGHTED)
        assert result is s

    # -- health_first --

    def test_health_first_picks_highest_health(self):
        """Healthiest server is selected."""
        s1 = _make_server(name="sick", server_id="1", health_score=30)
        s2 = _make_server(name="healthy", server_id="2", health_score=100)
        result = self.lb.select_server([s1, s2], "ns", LoadBalanceStrategy.HEALTH_FIRST)
        assert result is s2

    def test_health_first_breaks_ties_by_least_requests(self):
        """Equal health picks server with fewer requests."""
        s1 = _make_server(name="a", server_id="1", health_score=100)
        s2 = _make_server(name="b", server_id="2", health_score=100)
        self.lb.record_request("1")
        self.lb.record_request("1")
        result = self.lb.select_server([s1, s2], "ns", LoadBalanceStrategy.HEALTH_FIRST)
        assert result is s2

    # -- no servers / inactive --

    def test_select_server_empty_list(self):
        """Empty server list returns None."""
        assert self.lb.select_server([], "ns") is None

    def test_select_server_all_inactive(self):
        """All inactive servers returns None."""
        s1 = _make_server(status="inactive")
        s2 = _make_server(status="inactive")
        assert self.lb.select_server([s1, s2], "ns") is None

    def test_select_server_falls_back_to_degraded(self):
        """If no active servers, degraded ones are used."""
        s = _make_server(status="degraded")
        result = self.lb.select_server([s], "ns", LoadBalanceStrategy.HEALTH_FIRST)
        assert result is s

    # -- record_request / record_completion / reset --

    def test_record_request_increments(self):
        """record_request increments counter for server."""
        self.lb.record_request("srv1")
        self.lb.record_request("srv1")
        assert self.lb._request_counts["srv1"] == 2

    def test_record_completion_decrements(self):
        """record_completion decrements counter."""
        self.lb.record_request("srv1")
        self.lb.record_request("srv1")
        self.lb.record_completion("srv1")
        assert self.lb._request_counts["srv1"] == 1

    def test_record_completion_clamps_at_zero(self):
        """Counter never goes negative."""
        self.lb.record_completion("unknown")
        assert self.lb._request_counts["unknown"] == 0

    def test_reset_clears_all_counters(self):
        """reset() clears round-robin and request counts."""
        self.lb.record_request("a")
        self.lb._round_robin_counters["ns"] = 5
        self.lb.reset()
        assert len(self.lb._request_counts) == 0
        assert len(self.lb._round_robin_counters) == 0

    def test_singleton_instance_exists(self):
        """Module-level singleton should be an MCPLoadBalancer."""
        assert isinstance(mcp_load_balancer, MCPLoadBalancer)

    def test_load_balance_strategy_enum_values(self):
        """Enum has all four strategy values."""
        assert LoadBalanceStrategy.ROUND_ROBIN == "round_robin"
        assert LoadBalanceStrategy.LEAST_LOADED == "least_loaded"
        assert LoadBalanceStrategy.WEIGHTED == "weighted"
        assert LoadBalanceStrategy.HEALTH_FIRST == "health_first"
