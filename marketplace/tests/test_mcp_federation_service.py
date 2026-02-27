"""Tests for MCP Federation Service — register, discover, route, health scoring.

Covers:
- Server registration with SSRF-safe URL validation
- Server unregistration
- Listing servers with namespace/status filters
- Tool discovery across federated servers (namespacing, JSON parse)
- Tool refresh with httpx mocking (success, HTTP error, connection error)
- Tool routing with namespace parsing and health-based selection
- Health score updates with status degradation thresholds
- Auth header construction (bearer, api_key, none)
- MCPFederationService class wrapper
"""

import json
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from marketplace.models.mcp_server import MCPServerEntry
from marketplace.services.mcp_federation_service import (
    MCPFederationService,
    _build_auth_headers,
    discover_tools,
    get_server,
    list_servers,
    refresh_server_tools,
    register_server,
    route_tool_call,
    unregister_server,
    update_health_score,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _create_server(
    db: AsyncSession,
    name: str = "test-server",
    base_url: str = "https://mcp.example.com",
    namespace: str = "weather",
    status: str = "active",
    health_score: int = 100,
    tools_json: str = "[]",
    auth_type: str = "none",
    auth_credential_ref: str = "",
) -> MCPServerEntry:
    """Insert an MCPServerEntry directly for test setup."""
    import uuid

    server = MCPServerEntry(
        id=str(uuid.uuid4()),
        name=name,
        base_url=base_url,
        namespace=namespace,
        status=status,
        health_score=health_score,
        tools_json=tools_json,
        auth_type=auth_type,
        auth_credential_ref=auth_credential_ref,
    )
    db.add(server)
    await db.commit()
    await db.refresh(server)
    return server


# ---------------------------------------------------------------------------
# register_server
# ---------------------------------------------------------------------------

class TestRegisterServer:
    async def test_register_server_success(self, db: AsyncSession):
        server = await register_server(
            db,
            name="weather-v1",
            base_url="https://weather.example.com/mcp",
            namespace="weather",
            description="Weather data provider",
        )

        assert server.id is not None
        assert server.name == "weather-v1"
        assert server.namespace == "weather"
        assert server.status == "active"
        assert server.health_score == 100

    async def test_register_server_with_bearer_auth(self, db: AsyncSession):
        server = await register_server(
            db,
            name="secure-srv",
            base_url="https://secure.example.com",
            namespace="secure",
            auth_type="bearer",
            auth_credential_ref="tok-abc-123",
        )

        assert server.auth_type == "bearer"
        assert server.auth_credential_ref == "tok-abc-123"

    async def test_register_server_strips_trailing_slash(self, db: AsyncSession):
        server = await register_server(
            db,
            name="slash-test",
            base_url="https://mcp.example.com/",
            namespace="tools",
        )
        assert not server.base_url.endswith("/")

    async def test_register_server_rejects_private_ip(self, db: AsyncSession):
        with pytest.raises(ValueError, match="private|reserved"):
            await register_server(
                db,
                name="bad-srv",
                base_url="http://192.168.1.1/mcp",
                namespace="hack",
            )

    async def test_register_server_rejects_invalid_scheme(self, db: AsyncSession):
        with pytest.raises(ValueError, match="http or https"):
            await register_server(
                db,
                name="ftp-srv",
                base_url="ftp://files.example.com",
                namespace="files",
            )

    async def test_register_server_stores_registered_by(self, db: AsyncSession):
        server = await register_server(
            db,
            name="owner-test",
            base_url="https://owned.example.com",
            namespace="owned",
            registered_by="agent-xyz-123",
        )
        assert server.registered_by == "agent-xyz-123"


# ---------------------------------------------------------------------------
# unregister_server
# ---------------------------------------------------------------------------

class TestUnregisterServer:
    async def test_unregister_existing_server(self, db: AsyncSession):
        server = await _create_server(db, name="to-remove")
        result = await unregister_server(db, server.id)
        assert result is True

        # Verify it's gone
        fetched = await get_server(db, server.id)
        assert fetched is None

    async def test_unregister_nonexistent_returns_false(self, db: AsyncSession):
        result = await unregister_server(db, "nonexistent-id")
        assert result is False


# ---------------------------------------------------------------------------
# list_servers
# ---------------------------------------------------------------------------

class TestListServers:
    async def test_list_all_servers(self, db: AsyncSession):
        await _create_server(db, name="srv-a", namespace="ns1")
        await _create_server(db, name="srv-b", namespace="ns2")

        servers = await list_servers(db)
        assert len(servers) == 2

    async def test_list_servers_filter_by_namespace(self, db: AsyncSession):
        await _create_server(db, name="srv-ns1", namespace="weather")
        await _create_server(db, name="srv-ns2", namespace="search")

        servers = await list_servers(db, namespace="weather")
        assert len(servers) == 1
        assert servers[0].namespace == "weather"

    async def test_list_servers_filter_by_status(self, db: AsyncSession):
        await _create_server(db, name="active-srv", status="active")
        await _create_server(db, name="inactive-srv", status="inactive")

        servers = await list_servers(db, status="active")
        assert len(servers) == 1
        assert servers[0].status == "active"

    async def test_list_servers_respects_limit(self, db: AsyncSession):
        for i in range(5):
            await _create_server(db, name=f"srv-{i}", namespace=f"ns-{i}")

        servers = await list_servers(db, limit=3)
        assert len(servers) == 3

    async def test_list_servers_empty(self, db: AsyncSession):
        servers = await list_servers(db)
        assert servers == []


# ---------------------------------------------------------------------------
# get_server
# ---------------------------------------------------------------------------

class TestGetServer:
    async def test_get_existing_server(self, db: AsyncSession):
        server = await _create_server(db, name="fetch-me")
        fetched = await get_server(db, server.id)

        assert fetched is not None
        assert fetched.name == "fetch-me"

    async def test_get_nonexistent_returns_none(self, db: AsyncSession):
        result = await get_server(db, "no-such-id")
        assert result is None


# ---------------------------------------------------------------------------
# discover_tools
# ---------------------------------------------------------------------------

class TestDiscoverTools:
    async def test_discover_tools_aggregates_namespaced(self, db: AsyncSession):
        tools_a = json.dumps([{"name": "get_forecast", "description": "Weather forecast"}])
        tools_b = json.dumps([{"name": "web_search", "description": "Search the web"}])

        await _create_server(db, name="weather-srv", namespace="weather", tools_json=tools_a)
        await _create_server(db, name="search-srv", namespace="search", tools_json=tools_b)

        tools = await discover_tools(db)
        assert len(tools) == 2

        names = {t["name"] for t in tools}
        assert "weather.get_forecast" in names
        assert "search.web_search" in names

    async def test_discover_tools_adds_server_metadata(self, db: AsyncSession):
        tools_data = json.dumps([{"name": "ping", "description": "Ping tool"}])
        server = await _create_server(db, name="meta-srv", namespace="sys", tools_json=tools_data)

        tools = await discover_tools(db)
        assert len(tools) == 1
        assert tools[0]["_server_id"] == server.id
        assert tools[0]["_namespace"] == "sys"

    async def test_discover_tools_filters_by_namespace(self, db: AsyncSession):
        tools_a = json.dumps([{"name": "tool_a"}])
        tools_b = json.dumps([{"name": "tool_b"}])

        await _create_server(db, name="srv-a", namespace="alpha", tools_json=tools_a)
        await _create_server(db, name="srv-b", namespace="beta", tools_json=tools_b)

        tools = await discover_tools(db, namespace="alpha")
        assert len(tools) == 1
        assert tools[0]["name"] == "alpha.tool_a"

    async def test_discover_tools_skips_inactive_servers(self, db: AsyncSession):
        tools_data = json.dumps([{"name": "hidden"}])
        await _create_server(db, name="inactive-srv", status="inactive", tools_json=tools_data)

        tools = await discover_tools(db)
        assert len(tools) == 0

    async def test_discover_tools_handles_invalid_json(self, db: AsyncSession):
        await _create_server(db, name="bad-json-srv", tools_json="not-valid-json")

        tools = await discover_tools(db)
        assert len(tools) == 0

    async def test_discover_tools_handles_empty_tools_json(self, db: AsyncSession):
        await _create_server(db, name="empty-srv", tools_json="")

        tools = await discover_tools(db)
        assert len(tools) == 0

    async def test_discover_tools_handles_null_tools_json(self, db: AsyncSession):
        await _create_server(db, name="null-srv", tools_json=None)

        tools = await discover_tools(db)
        assert len(tools) == 0


# ---------------------------------------------------------------------------
# _build_auth_headers
# ---------------------------------------------------------------------------

class TestBuildAuthHeaders:
    def test_bearer_auth(self):
        server = MagicMock()
        server.auth_type = "bearer"
        server.auth_credential_ref = "my-token-123"

        headers = _build_auth_headers(server)
        assert headers == {"Authorization": "Bearer my-token-123"}

    def test_api_key_auth(self):
        server = MagicMock()
        server.auth_type = "api_key"
        server.auth_credential_ref = "key-abc-456"

        headers = _build_auth_headers(server)
        assert headers == {"X-API-Key": "key-abc-456"}

    def test_no_auth(self):
        server = MagicMock()
        server.auth_type = "none"
        server.auth_credential_ref = ""

        headers = _build_auth_headers(server)
        assert headers == {}

    def test_bearer_without_credential(self):
        server = MagicMock()
        server.auth_type = "bearer"
        server.auth_credential_ref = ""

        headers = _build_auth_headers(server)
        assert headers == {}


# ---------------------------------------------------------------------------
# refresh_server_tools
# ---------------------------------------------------------------------------

class TestRefreshServerTools:
    async def test_refresh_success(self, db: AsyncSession):
        server = await _create_server(db, name="refresh-target", health_score=80)

        mock_tools = [{"name": "tool_1"}, {"name": "tool_2"}]
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"tools": mock_tools}
        mock_response.raise_for_status = MagicMock()

        with patch("marketplace.services.mcp_federation_service.httpx.AsyncClient") as MockClient:
            mock_client = AsyncMock()
            mock_client.post.return_value = mock_response
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value = mock_client

            result = await refresh_server_tools(db, server.id)

        assert result["count"] == 2
        assert len(result["tools"]) == 2

        # Verify DB was updated
        updated = await get_server(db, server.id)
        assert updated.health_score == 100
        assert updated.status == "active"
        stored_tools = json.loads(updated.tools_json)
        assert len(stored_tools) == 2

    async def test_refresh_nonexistent_server(self, db: AsyncSession):
        result = await refresh_server_tools(db, "no-such-id")
        assert "error" in result
        assert result["error"] == "Server not found"

    async def test_refresh_http_error_degrades_health(self, db: AsyncSession):
        server = await _create_server(db, name="http-err-srv", health_score=60)

        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Server error", request=MagicMock(), response=mock_response
        )

        with patch("marketplace.services.mcp_federation_service.httpx.AsyncClient") as MockClient:
            mock_client = AsyncMock()
            mock_client.post.return_value = mock_response
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value = mock_client

            result = await refresh_server_tools(db, server.id)

        assert "error" in result
        # Health should drop by 20 (60 -> 40)
        updated = await get_server(db, server.id)
        assert updated.health_score == 40

    async def test_refresh_connection_error_degrades_health(self, db: AsyncSession):
        server = await _create_server(db, name="conn-err-srv", health_score=50)

        with patch("marketplace.services.mcp_federation_service.httpx.AsyncClient") as MockClient:
            mock_client = AsyncMock()
            mock_client.post.side_effect = httpx.ConnectError("Connection refused")
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value = mock_client

            result = await refresh_server_tools(db, server.id)

        assert "error" in result
        # Health should drop by 30 (50 -> 20)
        updated = await get_server(db, server.id)
        assert updated.health_score == 20

    async def test_refresh_response_with_flat_tools_list(self, db: AsyncSession):
        """When API returns a flat list instead of {"tools": [...]}."""
        server = await _create_server(db, name="flat-resp-srv")

        mock_tools = [{"name": "flat_tool"}]
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_tools
        mock_response.raise_for_status = MagicMock()

        with patch("marketplace.services.mcp_federation_service.httpx.AsyncClient") as MockClient:
            mock_client = AsyncMock()
            mock_client.post.return_value = mock_response
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value = mock_client

            result = await refresh_server_tools(db, server.id)

        # When data is a list (not dict), the code uses `data` directly
        assert result["count"] == 1


# ---------------------------------------------------------------------------
# route_tool_call
# ---------------------------------------------------------------------------

class TestRouteToolCall:
    async def test_route_success(self, db: AsyncSession):
        await _create_server(
            db, name="router-srv", namespace="weather", health_score=100
        )

        expected_result = {"content": [{"type": "text", "text": "Sunny, 25C"}]}
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = expected_result
        mock_response.raise_for_status = MagicMock()

        with patch("marketplace.services.mcp_federation_service.httpx.AsyncClient") as MockClient:
            mock_client = AsyncMock()
            mock_client.post.return_value = mock_response
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value = mock_client

            result = await route_tool_call(
                db,
                namespaced_tool_name="weather.get_forecast",
                arguments={"city": "London"},
                agent_id="agent-001",
            )

        assert result == expected_result

    async def test_route_invalid_tool_name_no_dot(self, db: AsyncSession):
        result = await route_tool_call(
            db,
            namespaced_tool_name="no_namespace",
            arguments={},
            agent_id="agent-001",
        )
        assert "error" in result
        assert "Invalid namespaced tool name" in result["error"]

    async def test_route_no_active_server_for_namespace(self, db: AsyncSession):
        result = await route_tool_call(
            db,
            namespaced_tool_name="unknown.some_tool",
            arguments={},
            agent_id="agent-001",
        )
        assert "error" in result
        assert "No active server" in result["error"]

    async def test_route_selects_highest_health_server(self, db: AsyncSession):
        await _create_server(
            db, name="low-health", namespace="tools",
            base_url="https://low.example.com", health_score=30,
        )
        await _create_server(
            db, name="high-health", namespace="tools",
            base_url="https://high.example.com", health_score=90,
        )

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"ok": True}
        mock_response.raise_for_status = MagicMock()

        with patch("marketplace.services.mcp_federation_service.httpx.AsyncClient") as MockClient:
            mock_client = AsyncMock()
            mock_client.post.return_value = mock_response
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value = mock_client

            await route_tool_call(
                db,
                namespaced_tool_name="tools.do_thing",
                arguments={},
                agent_id="agent-001",
            )

            # The URL should target the high-health server
            call_args = mock_client.post.call_args
            assert "high.example.com" in call_args[0][0]

    async def test_route_http_error_degrades_health(self, db: AsyncSession):
        server = await _create_server(
            db, name="fail-route-srv", namespace="failing", health_score=50,
        )

        mock_response = MagicMock()
        mock_response.status_code = 503
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Service unavailable", request=MagicMock(), response=mock_response
        )

        with patch("marketplace.services.mcp_federation_service.httpx.AsyncClient") as MockClient:
            mock_client = AsyncMock()
            mock_client.post.return_value = mock_response
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value = mock_client

            result = await route_tool_call(
                db,
                namespaced_tool_name="failing.some_tool",
                arguments={},
                agent_id="agent-001",
            )

        assert "error" in result
        # Health drops by 10 (50 -> 40)
        updated = await get_server(db, server.id)
        assert updated.health_score == 40

    async def test_route_connection_error_degrades_health(self, db: AsyncSession):
        server = await _create_server(
            db, name="connfail-srv", namespace="dead", health_score=40,
        )

        with patch("marketplace.services.mcp_federation_service.httpx.AsyncClient") as MockClient:
            mock_client = AsyncMock()
            mock_client.post.side_effect = httpx.ConnectError("Refused")
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value = mock_client

            result = await route_tool_call(
                db,
                namespaced_tool_name="dead.some_tool",
                arguments={},
                agent_id="agent-001",
            )

        assert "error" in result
        # Health drops by 20 (40 -> 20)
        updated = await get_server(db, server.id)
        assert updated.health_score == 20


# ---------------------------------------------------------------------------
# update_health_score
# ---------------------------------------------------------------------------

class TestUpdateHealthScore:
    async def test_set_score_clamps_to_0_100(self, db: AsyncSession):
        server = await _create_server(db, name="clamp-srv", health_score=50)

        await update_health_score(db, server.id, 150)
        updated = await get_server(db, server.id)
        assert updated.health_score == 100

        await update_health_score(db, server.id, -10)
        updated = await get_server(db, server.id)
        assert updated.health_score == 0

    async def test_score_zero_sets_inactive(self, db: AsyncSession):
        server = await _create_server(db, name="zero-srv", health_score=10)

        await update_health_score(db, server.id, 0)
        updated = await get_server(db, server.id)
        assert updated.status == "inactive"

    async def test_score_below_50_sets_degraded(self, db: AsyncSession):
        server = await _create_server(db, name="degrade-srv", health_score=80)

        await update_health_score(db, server.id, 30)
        updated = await get_server(db, server.id)
        assert updated.status == "degraded"

    async def test_score_50_plus_sets_active(self, db: AsyncSession):
        server = await _create_server(db, name="active-srv", health_score=20, status="degraded")

        await update_health_score(db, server.id, 75)
        updated = await get_server(db, server.id)
        assert updated.status == "active"

    async def test_update_nonexistent_server_is_noop(self, db: AsyncSession):
        # Should not raise
        await update_health_score(db, "ghost-id", 50)

    async def test_last_health_check_updated(self, db: AsyncSession):
        server = await _create_server(db, name="time-srv")
        before = server.last_health_check

        await update_health_score(db, server.id, 80)
        updated = await get_server(db, server.id)
        assert updated.last_health_check is not None
        if before is not None:
            assert updated.last_health_check >= before


# ---------------------------------------------------------------------------
# MCPFederationService class wrapper
# ---------------------------------------------------------------------------

class TestMCPFederationServiceClass:
    async def test_register_server_via_class(self, db: AsyncSession):
        svc = MCPFederationService()
        server = await svc.register_server(
            db,
            name="class-test-srv",
            base_url="https://class.example.com",
            namespace="class_ns",
        )
        assert server.name == "class-test-srv"

    async def test_discover_tools_via_class(self, db: AsyncSession):
        tools_data = json.dumps([{"name": "cls_tool"}])
        await _create_server(db, name="cls-srv", namespace="cls", tools_json=tools_data)

        svc = MCPFederationService()
        tools = await svc.discover_tools(db)
        assert len(tools) == 1

    async def test_route_tool_call_via_class(self, db: AsyncSession):
        await _create_server(db, name="cls-route-srv", namespace="cls")

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"result": "ok"}
        mock_response.raise_for_status = MagicMock()

        with patch("marketplace.services.mcp_federation_service.httpx.AsyncClient") as MockClient:
            mock_client = AsyncMock()
            mock_client.post.return_value = mock_response
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value = mock_client

            svc = MCPFederationService()
            result = await svc.route_tool_call(
                db,
                namespaced_tool_name="cls.some_tool",
                arguments={},
                agent_id="agent-x",
            )

        assert result == {"result": "ok"}
