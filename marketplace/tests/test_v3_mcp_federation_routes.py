"""Tests for MCP Federation v3 API routes (marketplace/api/v3_mcp_federation.py).

Covers server registration CRUD, health checks, tool refresh, aggregated tool
and resource discovery, federated tool/resource calls, and the federation
health overview endpoint.

All tests make real HTTP requests via the client fixture. External httpx calls
to federated servers are mocked (genuine external dependency).
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

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
    auth_type: str = "none",
    auth_credential_ref: str = "",
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
            auth_type=auth_type,
            auth_credential_ref=auth_credential_ref,
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


# ===================================================================
# POST /federation/servers -- register server
# ===================================================================


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


async def test_register_server_api_key_auth(client):
    _, jwt = await _create_agent()

    resp = await client.post(
        f"{FED}/servers",
        json={
            "name": "API Key MCP",
            "base_url": "http://apikey.example.com/mcp",
            "namespace": "apikey",
            "auth_type": "api_key",
            "auth_credential_ref": "key-abc123",
        },
        headers=_auth(jwt),
    )
    assert resp.status_code == 201
    assert resp.json()["auth_type"] == "api_key"


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


async def test_register_server_missing_required_fields(client):
    _, jwt = await _create_agent()

    # Missing base_url and namespace
    resp = await client.post(
        f"{FED}/servers",
        json={"name": "Incomplete"},
        headers=_auth(jwt),
    )
    assert resp.status_code == 422


async def test_register_server_response_fields(client):
    """Verify all expected fields in the registration response."""
    _, jwt = await _create_agent()

    resp = await client.post(
        f"{FED}/servers",
        json={
            "name": "Full Fields",
            "base_url": "http://full.example.com/mcp",
            "namespace": "fullns",
            "description": "Full description",
        },
        headers=_auth(jwt),
    )
    assert resp.status_code == 201
    body = resp.json()
    assert "id" in body
    assert body["description"] == "Full description"
    assert "registered_by" in body
    assert "health_score" in body
    assert "created_at" in body
    assert "updated_at" in body


async def test_register_server_with_description(client):
    _, jwt = await _create_agent()

    resp = await client.post(
        f"{FED}/servers",
        json={
            "name": "Desc Server",
            "base_url": "http://desc.example.com/mcp",
            "namespace": "descns",
            "description": "A server with a description",
        },
        headers=_auth(jwt),
    )
    assert resp.status_code == 201
    assert resp.json()["description"] == "A server with a description"


# ===================================================================
# GET /federation/servers -- list servers
# ===================================================================


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


async def test_list_servers_with_limit(client):
    agent_id, jwt = await _create_agent()
    for i in range(5):
        await _create_server(agent_id, name=f"srv-lim-{i}", namespace=f"ns{i}")

    resp = await client.get(
        f"{FED}/servers",
        params={"limit": 2},
        headers=_auth(jwt),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 2


async def test_list_servers_response_shape(client):
    _, jwt = await _create_agent()
    resp = await client.get(f"{FED}/servers", headers=_auth(jwt))
    assert resp.status_code == 200
    body = resp.json()
    assert "servers" in body
    assert "total" in body


# ===================================================================
# GET /federation/servers/{id} -- get single server
# ===================================================================


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


async def test_get_server_response_fields(client):
    """Verify all fields in the server detail response."""
    agent_id, jwt = await _create_agent()
    srv = await _create_server(agent_id, name="detail-srv", namespace="detailns")

    resp = await client.get(
        f"{FED}/servers/{srv.id}", headers=_auth(jwt),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["id"] == srv.id
    assert body["base_url"] is not None
    assert body["namespace"] == "detailns"
    assert "health_score" in body
    assert "auth_type" in body
    assert "registered_by" in body


# ===================================================================
# PUT /federation/servers/{id} -- update server
# ===================================================================


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


async def test_update_server_only_description(client):
    """Partial update with just description."""
    agent_id, jwt = await _create_agent()
    srv = await _create_server(agent_id, name="partial-upd")

    resp = await client.put(
        f"{FED}/servers/{srv.id}",
        json={"description": "Only desc changed"},
        headers=_auth(jwt),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["name"] == "partial-upd"
    assert body["description"] == "Only desc changed"


async def test_update_server_empty_body(client):
    """Update with no fields should succeed (no-op)."""
    agent_id, jwt = await _create_agent()
    srv = await _create_server(agent_id, name="noop-upd")

    resp = await client.put(
        f"{FED}/servers/{srv.id}",
        json={},
        headers=_auth(jwt),
    )
    assert resp.status_code == 200
    assert resp.json()["name"] == "noop-upd"


async def test_update_server_url_trailing_slash_stripped(client):
    """base_url should have trailing slash stripped."""
    agent_id, jwt = await _create_agent()
    srv = await _create_server(agent_id, name="slash-upd")

    resp = await client.put(
        f"{FED}/servers/{srv.id}",
        json={"base_url": "http://new-host.example.com/mcp/"},
        headers=_auth(jwt),
    )
    assert resp.status_code == 200
    assert not resp.json()["base_url"].endswith("/")


async def test_update_server_multiple_fields(client):
    """Update multiple fields at once."""
    agent_id, jwt = await _create_agent()
    srv = await _create_server(agent_id, name="multi-upd")

    resp = await client.put(
        f"{FED}/servers/{srv.id}",
        json={
            "name": "Multi Updated",
            "namespace": "multins",
            "description": "Multi desc",
            "auth_type": "bearer",
            "auth_credential_ref": "tok-456",
        },
        headers=_auth(jwt),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["name"] == "Multi Updated"
    assert body["namespace"] == "multins"
    assert body["description"] == "Multi desc"
    assert body["auth_type"] == "bearer"


# ===================================================================
# DELETE /federation/servers/{id} -- unregister
# ===================================================================


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


async def test_unregister_server_response_includes_id(client):
    agent_id, jwt = await _create_agent()
    srv = await _create_server(agent_id, name="del-id")

    resp = await client.delete(
        f"{FED}/servers/{srv.id}", headers=_auth(jwt),
    )
    assert resp.status_code == 200
    assert resp.json()["server_id"] == srv.id


# ===================================================================
# POST /federation/servers/{id}/health -- trigger health check
# ===================================================================


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
    assert body["health_score"] == 60  # 80 - 20


async def test_trigger_health_check_404(client):
    _, jwt = await _create_agent()
    resp = await client.post(
        f"{FED}/servers/missing/health", headers=_auth(jwt),
    )
    assert resp.status_code == 404


async def test_trigger_health_check_failure_low_score(client):
    """Health check failure with already low score clamps at 0."""
    agent_id, jwt = await _create_agent()
    srv = await _create_server(agent_id, name="health-low", health_score=10)

    with patch(
        "marketplace.services.mcp_federation_service.refresh_server_tools",
        new_callable=AsyncMock,
        return_value={"error": "timeout"},
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
    assert body["health_score"] == 0  # max(0, 10 - 20) = 0


# ===================================================================
# POST /federation/servers/{id}/refresh -- refresh tools
# ===================================================================


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


async def test_refresh_server_tools_response_shape(client):
    """Verify the refresh response includes server_id, tools_refreshed, tools."""
    agent_id, jwt = await _create_agent()
    srv = await _create_server(agent_id, name="refresh-shape")

    with patch(
        "marketplace.services.mcp_federation_service.refresh_server_tools",
        new_callable=AsyncMock,
        return_value={"tools": [], "count": 0},
    ):
        resp = await client.post(
            f"{FED}/servers/{srv.id}/refresh", headers=_auth(jwt),
        )
    assert resp.status_code == 200
    body = resp.json()
    assert body["server_id"] == srv.id
    assert body["tools_refreshed"] == 0
    assert body["tools"] == []


# ===================================================================
# GET /federation/tools -- list aggregated tools
# ===================================================================


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


async def test_list_federated_tools_from_multiple_servers(client):
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


async def test_list_federated_tools_degraded_server_excluded(client):
    """Degraded servers are not 'active' so their tools should be excluded."""
    agent_id, jwt = await _create_agent()
    await _create_server(
        agent_id,
        name="degraded-tools",
        status="degraded",
        tools_json=json.dumps([{"name": "hidden"}]),
    )

    resp = await client.get(f"{FED}/tools", headers=_auth(jwt))
    assert resp.status_code == 200
    assert resp.json()["total"] == 0


# ===================================================================
# POST /federation/tools/call -- call a federated tool
# ===================================================================


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


async def test_call_federated_tool_with_arguments(client):
    _, jwt = await _create_agent()

    with patch(
        "marketplace.services.mcp_federation_service.route_tool_call",
        new_callable=AsyncMock,
        return_value={"result": "computed"},
    ):
        resp = await client.post(
            f"{FED}/tools/call",
            json={
                "tool_name": "compute.calculate",
                "arguments": {"x": 10, "y": 20, "op": "add"},
            },
            headers=_auth(jwt),
        )
    assert resp.status_code == 200
    assert resp.json()["result"] == "computed"


# ===================================================================
# GET /federation/resources -- list aggregated resources
# ===================================================================


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


async def test_list_resources_includes_server_id(client):
    """Each resource should include _server_id metadata."""
    agent_id, jwt = await _create_agent()
    srv = await _create_server(
        agent_id,
        name="res-sid",
        namespace="sidns",
        resources_json=json.dumps([{"uri": "sidns://test"}]),
    )

    resp = await client.get(f"{FED}/resources", headers=_auth(jwt))
    assert resp.status_code == 200
    resource = resp.json()["resources"][0]
    assert resource["_server_id"] == srv.id


async def test_list_resources_multiple_from_one_server(client):
    """Server with multiple resources should list them all."""
    agent_id, jwt = await _create_agent()
    resources = [
        {"uri": "multi://a", "name": "A"},
        {"uri": "multi://b", "name": "B"},
        {"uri": "multi://c", "name": "C"},
    ]
    await _create_server(
        agent_id,
        name="multi-res",
        namespace="multi",
        resources_json=json.dumps(resources),
    )

    resp = await client.get(f"{FED}/resources", headers=_auth(jwt))
    assert resp.status_code == 200
    assert resp.json()["total"] == 3


async def test_list_resources_empty_json_array(client):
    """Server with empty resources_json should contribute 0 resources."""
    agent_id, jwt = await _create_agent()
    await _create_server(
        agent_id,
        name="empty-res",
        resources_json="[]",
    )

    resp = await client.get(f"{FED}/resources", headers=_auth(jwt))
    assert resp.status_code == 200
    assert resp.json()["total"] == 0


# ===================================================================
# POST /federation/resources/read -- read a federated resource
# ===================================================================


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


async def test_read_federated_resource_no_auth(client):
    resp = await client.post(
        f"{FED}/resources/read",
        json={"uri": "test://resource"},
    )
    assert resp.status_code in (401, 403)


async def test_read_federated_resource_servers_sorted_by_health(client):
    """Servers are tried in order of health score (highest first)."""
    agent_id, jwt = await _create_agent()
    # Create two servers with different health scores
    await _create_server(
        agent_id,
        name="low-health",
        namespace="sort",
        base_url="http://low.example.com/mcp",
        health_score=30,
    )
    await _create_server(
        agent_id,
        name="high-health",
        namespace="sort",
        base_url="http://high.example.com/mcp",
        health_score=90,
    )

    mock_response = MagicMock()
    mock_response.json.return_value = {"data": "from-high"}
    mock_response.raise_for_status.return_value = None
    mock_response.status_code = 200

    mock_http_client = AsyncMock()
    mock_http_client.post = AsyncMock(return_value=mock_response)

    with patch("httpx.AsyncClient") as mock_cls:
        mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_http_client)
        mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)

        resp = await client.post(
            f"{FED}/resources/read",
            json={"uri": "sort://test"},
            headers=_auth(jwt),
        )
    assert resp.status_code == 200
    # Should get data from the first server tried (highest health)
    assert resp.json()["data"] == "from-high"


# ===================================================================
# GET /federation/health -- public health overview
# ===================================================================


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


async def test_federation_health_active_low_score_not_healthy(client):
    """Active server with health_score < 50 is not counted as healthy."""
    agent_id, _ = await _create_agent()
    await _create_server(
        agent_id,
        name="health-low-active",
        status="active",
        health_score=40,
    )

    resp = await client.get(f"{FED}/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["server_count"] == 1
    assert body["healthy_count"] == 0


async def test_federation_health_multiple_active_servers(client):
    """Multiple active servers with different scores."""
    agent_id, _ = await _create_agent()
    tools_a = [{"name": "t1"}, {"name": "t2"}]
    tools_b = [{"name": "t3"}]

    await _create_server(
        agent_id, name="ha1", status="active", health_score=90,
        tools_json=json.dumps(tools_a),
    )
    await _create_server(
        agent_id, name="ha2", status="active", health_score=60,
        tools_json=json.dumps(tools_b),
    )
    await _create_server(
        agent_id, name="ha3", status="active", health_score=20,
    )

    resp = await client.get(f"{FED}/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["server_count"] == 3
    assert body["healthy_count"] == 2  # score >= 50: ha1 (90), ha2 (60)
    assert body["total_tool_count"] == 3  # t1, t2, t3


async def test_federation_health_null_tools_json(client):
    """Server with None/null tools_json should contribute 0 tools."""
    agent_id, _ = await _create_agent()
    await _create_server(
        agent_id,
        name="health-null-tools",
        tools_json=None,
    )

    resp = await client.get(f"{FED}/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total_tool_count"] == 0


# ===================================================================
# Edge cases and roundtrips
# ===================================================================


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
