"""Tests for MCP Federation v3 API routes (marketplace/api/v3_mcp_federation.py).

Covers server registration CRUD, health checks, tool refresh, aggregated tool
and resource discovery, federated tool/resource calls, and the federation
health overview endpoint.
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, patch

import pytest

from marketplace.core.auth import create_access_token
from marketplace.models.agent import RegisteredAgent
from marketplace.models.mcp_server import MCPServerEntry
from marketplace.tests.conftest import TestSession, _new_id

V3 = "/api/v3"
FED = f"{V3}/federation"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _create_agent(name: str | None = None) -> tuple[str, str]:
    """Create an active agent and return (agent_id, jwt)."""
    async with TestSession() as db:
        agent_id = _new_id()
        agent = RegisteredAgent(
            id=agent_id,
            name=name or f"mcp-agent-{agent_id[:8]}",
            agent_type="both",
            public_key="ssh-rsa AAAA_test",
            status="active",
        )
        db.add(agent)
        await db.commit()
        return agent_id, create_access_token(agent_id, agent.name)


async def _create_server(
    registered_by: str,
    name: str | None = None,
    namespace: str = "testns",
    base_url: str = "http://example.com/mcp",
    status: str = "active",
    health_score: int = 100,
    tools_json: str | None = None,
    resources_json: str | None = None,
) -> MCPServerEntry:
    """Directly insert an MCPServerEntry."""
    async with TestSession() as db:
        srv = MCPServerEntry(
            id=_new_id(),
            name=name or f"srv-{_new_id()[:8]}",
            base_url=base_url.rstrip("/"),
            namespace=namespace,
            description="test server",
            status=status,
            health_score=health_score,
            auth_type="none",
            registered_by=registered_by,
            tools_json=tools_json or "[]",
            resources_json=resources_json or "[]",
        )
        db.add(srv)
        await db.commit()
        await db.refresh(srv)
        return srv


def _auth(jwt: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {jwt}"}


# ═══════════════════════════════════════════════════════════════════
# POST /federation/servers — register server
# ═══════════════════════════════════════════════════════════════════


async def test_register_server_201(client):
    _, jwt = await _create_agent()

    resp = await client.post(
        f"{FED}/servers",
        json={
            "name": "Weather MCP",
            "base_url": "http://weather.example.com/mcp",
            "namespace": "weather",
            "description": "Weather data provider",
            "auth_type": "none",
        },
        headers=_auth(jwt),
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["name"] == "Weather MCP"
    assert body["namespace"] == "weather"
    assert body["status"] == "active"


async def test_register_server_bearer_auth(client):
    _, jwt = await _create_agent()

    resp = await client.post(
        f"{FED}/servers",
        json={
            "name": "Secure MCP",
            "base_url": "http://secure.example.com/mcp",
            "namespace": "secure",
            "auth_type": "bearer",
            "auth_credential_ref": "my-secret-token",
        },
        headers=_auth(jwt),
    )
    assert resp.status_code == 201
    assert resp.json()["auth_type"] == "bearer"


async def test_register_server_invalid_url(client):
    _, jwt = await _create_agent()

    resp = await client.post(
        f"{FED}/servers",
        json={
            "name": "Bad URL",
            "base_url": "ftp://not-http.com",
            "namespace": "bad",
        },
        headers=_auth(jwt),
    )
    assert resp.status_code == 400


async def test_register_server_no_auth(client):
    resp = await client.post(
        f"{FED}/servers",
        json={
            "name": "NoAuth",
            "base_url": "http://a.com",
            "namespace": "ns",
        },
    )
    assert resp.status_code in (401, 403)


async def test_register_server_invalid_namespace(client):
    _, jwt = await _create_agent()

    resp = await client.post(
        f"{FED}/servers",
        json={
            "name": "Bad NS",
            "base_url": "http://example.com",
            "namespace": "123-bad",  # must start with letter
        },
        headers=_auth(jwt),
    )
    assert resp.status_code == 422


async def test_register_server_invalid_auth_type(client):
    _, jwt = await _create_agent()

    resp = await client.post(
        f"{FED}/servers",
        json={
            "name": "Bad Auth",
            "base_url": "http://example.com",
            "namespace": "validns",
            "auth_type": "oauth2",  # not valid
        },
        headers=_auth(jwt),
    )
    assert resp.status_code == 422


# ═══════════════════════════════════════════════════════════════════
# GET /federation/servers — list servers
# ═══════════════════════════════════════════════════════════════════


async def test_list_servers_empty(client):
    _, jwt = await _create_agent()
    resp = await client.get(f"{FED}/servers", headers=_auth(jwt))
    assert resp.status_code == 200
    body = resp.json()
    assert body["servers"] == []
    assert body["total"] == 0


async def test_list_servers_with_data(client):
    agent_id, jwt = await _create_agent()
    await _create_server(agent_id, name="srv-a", namespace="ns1")
    await _create_server(agent_id, name="srv-b", namespace="ns2")

    resp = await client.get(f"{FED}/servers", headers=_auth(jwt))
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 2


async def test_list_servers_filter_namespace(client):
    agent_id, jwt = await _create_agent()
    await _create_server(agent_id, name="ns-a", namespace="weather")
    await _create_server(agent_id, name="ns-b", namespace="finance")

    resp = await client.get(
        f"{FED}/servers",
        params={"namespace": "weather"},
        headers=_auth(jwt),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 1
    assert body["servers"][0]["namespace"] == "weather"


async def test_list_servers_filter_status(client):
    agent_id, jwt = await _create_agent()
    await _create_server(agent_id, name="active-s", status="active")
    await _create_server(agent_id, name="inactive-s", status="inactive")

    resp = await client.get(
        f"{FED}/servers",
        params={"status": "inactive"},
        headers=_auth(jwt),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 1
    assert body["servers"][0]["status"] == "inactive"


# ═══════════════════════════════════════════════════════════════════
# GET /federation/servers/{id} — get single server
# ═══════════════════════════════════════════════════════════════════


async def test_get_server_200(client):
    agent_id, jwt = await _create_agent()
    srv = await _create_server(agent_id, name="get-srv")

    resp = await client.get(
        f"{FED}/servers/{srv.id}", headers=_auth(jwt),
    )
    assert resp.status_code == 200
    assert resp.json()["name"] == "get-srv"


async def test_get_server_404(client):
    _, jwt = await _create_agent()
    resp = await client.get(
        f"{FED}/servers/nonexistent-id", headers=_auth(jwt),
    )
    assert resp.status_code == 404


# ═══════════════════════════════════════════════════════════════════
# PUT /federation/servers/{id} — update server
# ═══════════════════════════════════════════════════════════════════


async def test_update_server_200(client):
    agent_id, jwt = await _create_agent()
    srv = await _create_server(agent_id, name="upd-srv")

    resp = await client.put(
        f"{FED}/servers/{srv.id}",
        json={"name": "Updated MCP", "description": "Updated desc"},
        headers=_auth(jwt),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["name"] == "Updated MCP"
    assert body["description"] == "Updated desc"


async def test_update_server_change_namespace(client):
    agent_id, jwt = await _create_agent()
    srv = await _create_server(agent_id, name="ns-change")

    resp = await client.put(
        f"{FED}/servers/{srv.id}",
        json={"namespace": "newns"},
        headers=_auth(jwt),
    )
    assert resp.status_code == 200
    assert resp.json()["namespace"] == "newns"


async def test_update_server_change_url(client):
    agent_id, jwt = await _create_agent()
    srv = await _create_server(agent_id, name="url-change")

    resp = await client.put(
        f"{FED}/servers/{srv.id}",
        json={"base_url": "http://new-host.example.com/mcp"},
        headers=_auth(jwt),
    )
    assert resp.status_code == 200


async def test_update_server_invalid_url(client):
    agent_id, jwt = await _create_agent()
    srv = await _create_server(agent_id, name="bad-url-upd")

    resp = await client.put(
        f"{FED}/servers/{srv.id}",
        json={"base_url": "ftp://invalid"},
        headers=_auth(jwt),
    )
    assert resp.status_code == 400


async def test_update_server_404(client):
    _, jwt = await _create_agent()
    resp = await client.put(
        f"{FED}/servers/missing",
        json={"name": "X"},
        headers=_auth(jwt),
    )
    assert resp.status_code == 404


async def test_update_server_403_non_registrant(client):
    owner_id, _ = await _create_agent(name="upd-owner")
    _, other_jwt = await _create_agent(name="upd-intruder")

    srv = await _create_server(owner_id, name="forbidden-upd")

    resp = await client.put(
        f"{FED}/servers/{srv.id}",
        json={"name": "Hijacked"},
        headers=_auth(other_jwt),
    )
    assert resp.status_code == 403


async def test_update_server_change_auth(client):
    agent_id, jwt = await _create_agent()
    srv = await _create_server(agent_id, name="auth-change")

    resp = await client.put(
        f"{FED}/servers/{srv.id}",
        json={"auth_type": "api_key", "auth_credential_ref": "key-123"},
        headers=_auth(jwt),
    )
    assert resp.status_code == 200
    assert resp.json()["auth_type"] == "api_key"


# ═══════════════════════════════════════════════════════════════════
# DELETE /federation/servers/{id} — unregister
# ═══════════════════════════════════════════════════════════════════


async def test_unregister_server_200(client):
    agent_id, jwt = await _create_agent()
    srv = await _create_server(agent_id, name="del-srv")

    resp = await client.delete(
        f"{FED}/servers/{srv.id}", headers=_auth(jwt),
    )
    assert resp.status_code == 200
    assert resp.json()["detail"] == "Server unregistered"

    # Verify it's gone
    get_resp = await client.get(
        f"{FED}/servers/{srv.id}", headers=_auth(jwt),
    )
    assert get_resp.status_code == 404


async def test_unregister_server_404(client):
    _, jwt = await _create_agent()
    resp = await client.delete(
        f"{FED}/servers/missing", headers=_auth(jwt),
    )
    assert resp.status_code == 404


async def test_unregister_server_403_non_registrant(client):
    owner_id, _ = await _create_agent(name="del-owner")
    _, other_jwt = await _create_agent(name="del-intruder")

    srv = await _create_server(owner_id, name="no-del")

    resp = await client.delete(
        f"{FED}/servers/{srv.id}", headers=_auth(other_jwt),
    )
    assert resp.status_code == 403


# ═══════════════════════════════════════════════════════════════════
# POST /federation/servers/{id}/health — trigger health check
# ═══════════════════════════════════════════════════════════════════


async def test_trigger_health_check_success(client):
    agent_id, jwt = await _create_agent()
    srv = await _create_server(agent_id, name="health-ok")

    with patch(
        "marketplace.services.mcp_federation_service.refresh_server_tools",
        new_callable=AsyncMock,
        return_value={"tools": [{"name": "get_temp"}], "count": 1},
    ):
        resp = await client.post(
            f"{FED}/servers/{srv.id}/health", headers=_auth(jwt),
        )
    assert resp.status_code == 200
    body = resp.json()
    assert body["healthy"] is True
    assert body["tools_count"] == 1
    assert body["health_score"] == 100


async def test_trigger_health_check_failure(client):
    agent_id, jwt = await _create_agent()
    srv = await _create_server(agent_id, name="health-fail", health_score=80)

    with patch(
        "marketplace.services.mcp_federation_service.refresh_server_tools",
        new_callable=AsyncMock,
        return_value={"error": "Connection refused"},
    ), patch(
        "marketplace.services.mcp_federation_service.update_health_score",
        new_callable=AsyncMock,
    ):
        resp = await client.post(
            f"{FED}/servers/{srv.id}/health", headers=_auth(jwt),
        )
    assert resp.status_code == 200
    body = resp.json()
    assert body["healthy"] is False
    assert "error" in body


async def test_trigger_health_check_404(client):
    _, jwt = await _create_agent()
    resp = await client.post(
        f"{FED}/servers/missing/health", headers=_auth(jwt),
    )
    assert resp.status_code == 404


# ═══════════════════════════════════════════════════════════════════
# POST /federation/servers/{id}/refresh — refresh tools
# ═══════════════════════════════════════════════════════════════════


async def test_refresh_server_tools_success(client):
    agent_id, jwt = await _create_agent()
    srv = await _create_server(agent_id, name="refresh-ok")

    tools_data = [{"name": "forecast"}, {"name": "current_temp"}]
    with patch(
        "marketplace.services.mcp_federation_service.refresh_server_tools",
        new_callable=AsyncMock,
        return_value={"tools": tools_data, "count": 2},
    ):
        resp = await client.post(
            f"{FED}/servers/{srv.id}/refresh", headers=_auth(jwt),
        )
    assert resp.status_code == 200
    body = resp.json()
    assert body["tools_refreshed"] == 2
    assert len(body["tools"]) == 2


async def test_refresh_server_tools_error(client):
    agent_id, jwt = await _create_agent()
    srv = await _create_server(agent_id, name="refresh-err")

    with patch(
        "marketplace.services.mcp_federation_service.refresh_server_tools",
        new_callable=AsyncMock,
        return_value={"error": "HTTP 500"},
    ):
        resp = await client.post(
            f"{FED}/servers/{srv.id}/refresh", headers=_auth(jwt),
        )
    assert resp.status_code == 502


async def test_refresh_server_tools_404(client):
    _, jwt = await _create_agent()
    resp = await client.post(
        f"{FED}/servers/missing/refresh", headers=_auth(jwt),
    )
    assert resp.status_code == 404


# ═══════════════════════════════════════════════════════════════════
# GET /federation/tools — list aggregated tools
# ═══════════════════════════════════════════════════════════════════


async def test_list_federated_tools_empty(client):
    _, jwt = await _create_agent()
    resp = await client.get(f"{FED}/tools", headers=_auth(jwt))
    assert resp.status_code == 200
    body = resp.json()
    assert body["tools"] == []
    assert body["total"] == 0


async def test_list_federated_tools_with_data(client):
    agent_id, jwt = await _create_agent()
    tools = [{"name": "get_temp", "description": "Get temperature"}]
    await _create_server(
        agent_id,
        name="tool-srv",
        namespace="weather",
        tools_json=json.dumps(tools),
    )

    resp = await client.get(f"{FED}/tools", headers=_auth(jwt))
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 1
    # Tool name should be namespaced
    assert body["tools"][0]["name"] == "weather.get_temp"
    assert body["tools"][0]["_namespace"] == "weather"


async def test_list_federated_tools_filter_namespace(client):
    agent_id, jwt = await _create_agent()
    await _create_server(
        agent_id,
        name="ns-filter-1",
        namespace="weather",
        tools_json=json.dumps([{"name": "t1"}]),
    )
    await _create_server(
        agent_id,
        name="ns-filter-2",
        namespace="finance",
        tools_json=json.dumps([{"name": "t2"}]),
    )

    resp = await client.get(
        f"{FED}/tools",
        params={"namespace": "finance"},
        headers=_auth(jwt),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 1
    assert body["tools"][0]["name"] == "finance.t2"


async def test_list_federated_tools_inactive_server_excluded(client):
    agent_id, jwt = await _create_agent()
    await _create_server(
        agent_id,
        name="inactive-tools",
        status="inactive",
        tools_json=json.dumps([{"name": "hidden"}]),
    )

    resp = await client.get(f"{FED}/tools", headers=_auth(jwt))
    assert resp.status_code == 200
    assert resp.json()["total"] == 0


# ═══════════════════════════════════════════════════════════════════
# POST /federation/tools/call — call a federated tool
# ═══════════════════════════════════════════════════════════════════


async def test_call_federated_tool_success(client):
    agent_id, jwt = await _create_agent()
    await _create_server(
        agent_id,
        name="callable-srv",
        namespace="weather",
    )

    mock_result = {"temperature": 22, "unit": "celsius"}
    with patch(
        "marketplace.services.mcp_federation_service.route_tool_call",
        new_callable=AsyncMock,
        return_value=mock_result,
    ):
        resp = await client.post(
            f"{FED}/tools/call",
            json={
                "tool_name": "weather.get_forecast",
                "arguments": {"city": "Zurich"},
            },
            headers=_auth(jwt),
        )
    assert resp.status_code == 200
    body = resp.json()
    assert body["temperature"] == 22


async def test_call_federated_tool_error(client):
    _, jwt = await _create_agent()

    with patch(
        "marketplace.services.mcp_federation_service.route_tool_call",
        new_callable=AsyncMock,
        return_value={"error": "No active server found for namespace 'missing'"},
    ):
        resp = await client.post(
            f"{FED}/tools/call",
            json={"tool_name": "missing.tool", "arguments": {}},
            headers=_auth(jwt),
        )
    assert resp.status_code == 502


async def test_call_federated_tool_no_auth(client):
    resp = await client.post(
        f"{FED}/tools/call",
        json={"tool_name": "ns.tool", "arguments": {}},
    )
    assert resp.status_code in (401, 403)


# ═══════════════════════════════════════════════════════════════════
# GET /federation/resources — list aggregated resources
# ═══════════════════════════════════════════════════════════════════


async def test_list_federated_resources_empty(client):
    _, jwt = await _create_agent()
    resp = await client.get(f"{FED}/resources", headers=_auth(jwt))
    assert resp.status_code == 200
    body = resp.json()
    assert body["resources"] == []
    assert body["total"] == 0


async def test_list_federated_resources_with_data(client):
    agent_id, jwt = await _create_agent()
    resources = [
        {"uri": "weather://forecasts/today", "name": "Today Forecast"},
    ]
    await _create_server(
        agent_id,
        name="res-srv",
        namespace="weather",
        resources_json=json.dumps(resources),
    )

    resp = await client.get(f"{FED}/resources", headers=_auth(jwt))
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 1
    assert body["resources"][0]["uri"] == "weather://forecasts/today"
    assert body["resources"][0]["_namespace"] == "weather"


async def test_list_federated_resources_filter_namespace(client):
    agent_id, jwt = await _create_agent()
    await _create_server(
        agent_id,
        name="res-w",
        namespace="weather",
        resources_json=json.dumps([{"uri": "weather://x"}]),
    )
    await _create_server(
        agent_id,
        name="res-f",
        namespace="finance",
        resources_json=json.dumps([{"uri": "finance://y"}]),
    )

    resp = await client.get(
        f"{FED}/resources",
        params={"namespace": "finance"},
        headers=_auth(jwt),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 1
    assert body["resources"][0]["_namespace"] == "finance"


async def test_list_resources_inactive_server_excluded(client):
    agent_id, jwt = await _create_agent()
    await _create_server(
        agent_id,
        name="inactive-res",
        status="inactive",
        resources_json=json.dumps([{"uri": "test://hidden"}]),
    )

    resp = await client.get(f"{FED}/resources", headers=_auth(jwt))
    assert resp.status_code == 200
    assert resp.json()["total"] == 0


async def test_list_resources_malformed_json_ignored(client):
    agent_id, jwt = await _create_agent()
    await _create_server(
        agent_id,
        name="bad-res-json",
        resources_json="not-valid-json{",
    )

    resp = await client.get(f"{FED}/resources", headers=_auth(jwt))
    assert resp.status_code == 200
    assert resp.json()["total"] == 0


# ═══════════════════════════════════════════════════════════════════
# POST /federation/resources/read — read a federated resource
# ═══════════════════════════════════════════════════════════════════


async def test_read_federated_resource_no_server_404(client):
    _, jwt = await _create_agent()

    resp = await client.post(
        f"{FED}/resources/read",
        json={"uri": "unknown://resource/path"},
        headers=_auth(jwt),
    )
    assert resp.status_code == 404


async def test_read_federated_resource_all_fail_502(client):
    agent_id, jwt = await _create_agent()
    await _create_server(
        agent_id,
        name="fail-res-srv",
        namespace="broken",
        base_url="http://unreachable.example.com",
    )

    # The endpoint makes real httpx calls to the server base_url, which will fail
    resp = await client.post(
        f"{FED}/resources/read",
        json={"uri": "broken://some/resource"},
        headers=_auth(jwt),
    )
    assert resp.status_code == 502


async def test_read_federated_resource_success(client):
    agent_id, jwt = await _create_agent()
    await _create_server(
        agent_id,
        name="read-srv",
        namespace="data",
        base_url="http://data.example.com/mcp",
    )

    from unittest.mock import MagicMock

    # httpx Response methods (json, raise_for_status) are sync, not async
    mock_response = MagicMock()
    mock_response.json.return_value = {"contents": [{"text": "hello"}]}
    mock_response.raise_for_status.return_value = None
    mock_response.status_code = 200

    # post() is awaited, so it must be an AsyncMock
    mock_http_client = AsyncMock()
    mock_http_client.post = AsyncMock(return_value=mock_response)

    # The route imports httpx locally; patch at package level
    with patch("httpx.AsyncClient") as mock_cls:
        mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_http_client)
        mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)

        resp = await client.post(
            f"{FED}/resources/read",
            json={"uri": "data://some/resource"},
            headers=_auth(jwt),
        )
    assert resp.status_code == 200
    body = resp.json()
    assert body["contents"][0]["text"] == "hello"


# ═══════════════════════════════════════════════════════════════════
# GET /federation/health — public health overview
# ═══════════════════════════════════════════════════════════════════


async def test_federation_health_no_auth(client):
    """Health overview does not require authentication."""
    resp = await client.get(f"{FED}/health")
    assert resp.status_code == 200
    body = resp.json()
    assert "server_count" in body
    assert "healthy_count" in body
    assert "total_tool_count" in body


async def test_federation_health_empty(client):
    resp = await client.get(f"{FED}/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["server_count"] == 0
    assert body["healthy_count"] == 0
    assert body["total_tool_count"] == 0


async def test_federation_health_with_servers(client):
    agent_id, _ = await _create_agent()

    tools = [{"name": "a"}, {"name": "b"}]
    await _create_server(
        agent_id,
        name="health-active",
        status="active",
        health_score=80,
        tools_json=json.dumps(tools),
    )
    await _create_server(
        agent_id,
        name="health-degraded",
        status="degraded",
        health_score=30,
    )
    await _create_server(
        agent_id,
        name="health-inactive",
        status="inactive",
        health_score=0,
    )

    resp = await client.get(f"{FED}/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["server_count"] == 3
    assert body["healthy_count"] == 1  # active with score >= 50
    assert body["degraded_count"] == 1
    assert body["inactive_count"] == 1
    assert body["total_tool_count"] == 2


async def test_federation_health_malformed_tools_json(client):
    agent_id, _ = await _create_agent()
    await _create_server(
        agent_id,
        name="health-bad-json",
        tools_json="not-json{",
    )

    resp = await client.get(f"{FED}/health")
    assert resp.status_code == 200
    body = resp.json()
    # Malformed JSON should not crash, just skip the tool count
    assert body["server_count"] == 1
    assert body["total_tool_count"] == 0


# ═══════════════════════════════════════════════════════════════════
# Edge cases
# ═══════════════════════════════════════════════════════════════════


async def test_register_server_missing_required_fields(client):
    _, jwt = await _create_agent()

    # Missing base_url and namespace
    resp = await client.post(
        f"{FED}/servers",
        json={"name": "Incomplete"},
        headers=_auth(jwt),
    )
    assert resp.status_code == 422


async def test_register_and_list_roundtrip(client):
    """Verify a registered server shows up in the list endpoint."""
    agent_id, jwt = await _create_agent()
    headers = _auth(jwt)

    reg_resp = await client.post(
        f"{FED}/servers",
        json={
            "name": "Roundtrip Server",
            "base_url": "http://roundtrip.example.com/mcp",
            "namespace": "roundtrip",
        },
        headers=headers,
    )
    assert reg_resp.status_code == 201
    server_id = reg_resp.json()["id"]

    list_resp = await client.get(f"{FED}/servers", headers=headers)
    assert list_resp.status_code == 200
    ids = [s["id"] for s in list_resp.json()["servers"]]
    assert server_id in ids


async def test_update_and_get_roundtrip(client):
    agent_id, jwt = await _create_agent()
    headers = _auth(jwt)

    srv = await _create_server(agent_id, name="rt-update")

    await client.put(
        f"{FED}/servers/{srv.id}",
        json={"description": "New description"},
        headers=headers,
    )

    get_resp = await client.get(
        f"{FED}/servers/{srv.id}", headers=headers,
    )
    assert get_resp.status_code == 200
    assert get_resp.json()["description"] == "New description"


async def test_delete_then_list(client):
    agent_id, jwt = await _create_agent()
    headers = _auth(jwt)

    srv = await _create_server(agent_id, name="del-then-list")

    del_resp = await client.delete(
        f"{FED}/servers/{srv.id}", headers=headers,
    )
    assert del_resp.status_code == 200

    list_resp = await client.get(f"{FED}/servers", headers=headers)
    ids = [s["id"] for s in list_resp.json()["servers"]]
    assert srv.id not in ids


async def test_tools_from_multiple_servers_aggregated(client):
    agent_id, jwt = await _create_agent()
    await _create_server(
        agent_id,
        name="multi-1",
        namespace="alpha",
        tools_json=json.dumps([{"name": "tool_a"}]),
    )
    await _create_server(
        agent_id,
        name="multi-2",
        namespace="beta",
        tools_json=json.dumps([{"name": "tool_b"}, {"name": "tool_c"}]),
    )

    resp = await client.get(f"{FED}/tools", headers=_auth(jwt))
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 3
    names = {t["name"] for t in body["tools"]}
    assert "alpha.tool_a" in names
    assert "beta.tool_b" in names
    assert "beta.tool_c" in names
