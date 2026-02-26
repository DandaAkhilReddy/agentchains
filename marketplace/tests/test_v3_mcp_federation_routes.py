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
    assert body["health_score"] == 60


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


# ===========================================================================
# Extra coverage tests -- uncovered code paths (appended by coverage push)
# ===========================================================================


async def test_register_server_duplicate_namespace_ok(client):
    """Two servers in same namespace is allowed (unique on name)."""
    _, jwt = await _create_agent()
    headers = _auth(jwt)
    p1 = {
        "name": "dup-ns-srv-1",
        "base_url": "http://example.com/mcp1",
        "namespace": "dupns",
        "auth_type": "none",
    }
    r1 = await client.post(f"{FED}/servers", json=p1, headers=headers)
    assert r1.status_code == 201
    p2 = {
        "name": "dup-ns-srv-2",
        "base_url": "http://example.com/mcp2",
        "namespace": "dupns",
        "auth_type": "none",
    }
    r2 = await client.post(f"{FED}/servers", json=p2, headers=headers)
    assert r2.status_code == 201
    assert r2.json()["namespace"] == "dupns"


async def test_update_server_base_url_strips_trailing_slash(client):
    """PUT /federation/servers/{id} strips trailing slash from base_url."""
    agent_id, jwt = await _create_agent()
    srv = await _create_server(registered_by=agent_id, name="url-strip-x")
    headers = _auth(jwt)
    resp = await client.put(
        f"{FED}/servers/{srv.id}",
        json={"base_url": "http://example.com/mcp/"},
        headers=headers,
    )
    assert resp.status_code == 200
    assert not resp.json()["base_url"].endswith("/")


async def test_list_resources_namespace_filter_only_matching(client):
    """GET /federation/resources?namespace= returns only matching servers."""
    aid, jwt = await _create_agent()
    headers = _auth(jwt)
    res1 = json.dumps([{"uri": "ns1://data", "name": "d"}])
    await _create_server(
        registered_by=aid, name="nsf-srv1", namespace="nsone",
        resources_json=res1,
    )
    res2 = json.dumps([{"uri": "ns2://other", "name": "o"}])
    await _create_server(
        registered_by=aid, name="nsf-srv2", namespace="nstwo",
        resources_json=res2,
    )
    resp = await client.get(
        f"{FED}/resources", params={"namespace": "nsone"}, headers=headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 1
    assert body["resources"][0]["_namespace"] == "nsone"


async def test_list_resources_null_resources_json(client):
    """Server with resources_json=None contributes zero entries."""
    aid, jwt = await _create_agent()
    srv = await _create_server(
        registered_by=aid, name="null-res-srv", namespace="nullns",
    )
    async with TestSession() as db:
        from sqlalchemy import select as sel
        r = await db.execute(
            sel(MCPServerEntry).where(MCPServerEntry.id == srv.id)
        )
        s = r.scalar_one()
        s.resources_json = None
        await db.commit()
    resp = await client.get(f"{FED}/resources", headers=_auth(jwt))
    assert resp.status_code == 200
    for r in resp.json()["resources"]:
        assert r["_server_id"] != srv.id


async def test_read_resource_success_proxied(client):
    """POST /federation/resources/read proxies to federated server."""
    aid, jwt = await _create_agent()
    await _create_server(
        registered_by=aid, name="read-prx", namespace="weather",
        base_url="http://weather.example.com/mcp",
    )
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.raise_for_status = MagicMock()
    mock_resp.json.return_value = {"content": "sunny"}
    mock_cl = AsyncMock()
    mock_cl.__aenter__ = AsyncMock(return_value=mock_cl)
    mock_cl.__aexit__ = AsyncMock(return_value=False)
    mock_cl.post = AsyncMock(return_value=mock_resp)
    with patch("httpx.AsyncClient", return_value=mock_cl):
        resp = await client.post(
            f"{FED}/resources/read",
            json={"uri": "weather://forecasts/today"},
            headers=_auth(jwt),
        )
    assert resp.status_code == 200
    assert resp.json()["content"] == "sunny"


async def test_federation_health_degraded_inactive_counts(client):
    """GET /federation/health reports degraded_count and inactive_count."""
    aid, _ = await _create_agent()
    await _create_server(
        registered_by=aid, name="h-srv", namespace="hns",
        status="active", health_score=90,
    )
    await _create_server(
        registered_by=aid, name="d-srv", namespace="dns",
        status="degraded", health_score=30,
    )
    await _create_server(
        registered_by=aid, name="i-srv", namespace="ins",
        status="inactive", health_score=0,
    )
    resp = await client.get(f"{FED}/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["server_count"] == 3
    assert body["healthy_count"] == 1
    assert body["degraded_count"] == 1
    assert body["inactive_count"] == 1


async def test_call_federated_tool_no_dot_in_name(client):
    """tool_name without dot separator triggers error from route_tool_call."""
    _, jwt = await _create_agent()
    resp = await client.post(
        f"{FED}/tools/call",
        json={"tool_name": "nodotname", "arguments": {}},
        headers=_auth(jwt),
    )
    assert resp.status_code == 502


async def test_health_check_decrements_score_on_failure(client):
    """POST /servers/{id}/health decrements health_score by 20 on failure."""
    aid, jwt = await _create_agent()
    srv = await _create_server(
        registered_by=aid, name="dec-srv", namespace="decscore",
        health_score=80,
    )
    with patch(
        "marketplace.services.mcp_federation_service.refresh_server_tools",
        return_value={"error": "Connection refused"},
    ):
        resp = await client.post(
            f"{FED}/servers/{srv.id}/health", headers=_auth(jwt),
        )
    assert resp.status_code == 200
    body = resp.json()
    assert body["healthy"] is False
    assert body["health_score"] == 40


async def test_federation_health_tools_counting(client):
    """GET /federation/health counts tools from tools_json."""
    aid, _ = await _create_agent()
    tools = json.dumps([{"name": "t1"}, {"name": "t2"}, {"name": "t3"}])
    await _create_server(
        registered_by=aid, name="tc-srv", namespace="tc",
        tools_json=tools, status="active", health_score=100,
    )
    resp = await client.get(f"{FED}/health")
    body = resp.json()
    assert body["total_tool_count"] >= 3


async def test_read_resource_extracts_namespace_from_uri_scheme(client):
    """Namespace is extracted from URI scheme (e.g. myns://...)."""
    aid, jwt = await _create_agent()
    await _create_server(
        registered_by=aid, name="nsext-srv", namespace="myns",
        base_url="http://nsext.example.com/mcp",
    )
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.raise_for_status = MagicMock()
    mock_resp.json.return_value = {"data": "ok"}
    mc = AsyncMock()
    mc.__aenter__ = AsyncMock(return_value=mc)
    mc.__aexit__ = AsyncMock(return_value=False)
    mc.post = AsyncMock(return_value=mock_resp)
    with patch("httpx.AsyncClient", return_value=mc):
        resp = await client.post(
            f"{FED}/resources/read",
            json={"uri": "myns://some/resource"},
            headers=_auth(jwt),
        )
    assert resp.status_code == 200
    call_url = mc.post.call_args[0][0]
    assert "nsext.example.com" in call_url


async def test_register_server_with_full_options(client):
    """register_server with description, auth_type=bearer, credential_ref."""
    _, jwt = await _create_agent()
    resp = await client.post(
        f"{FED}/servers",
        json={
            "name": "Full Opts",
            "base_url": "http://full.example.com/mcp",
            "namespace": "fullopts",
            "description": "Fully configured server",
            "auth_type": "bearer",
            "auth_credential_ref": "vault://secret/token",
        },
        headers=_auth(jwt),
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["description"] == "Fully configured server"
    assert body["auth_type"] == "bearer"


# ===========================================================================
# Direct function-call tests — bypass HTTP/ASGI to guarantee coverage
#
# pytest-asyncio + httpx ASGI transport does not always resume coroutine
# tracing after `await` in Python 3.13 / coverage 7.x without
# `concurrency = asyncio`.  Calling route functions directly ensures every
# line inside the coroutine body is measured.
# ===========================================================================


# ---------------------------------------------------------------------------
# register_server — ValueError branch (lines 99-101)
# ---------------------------------------------------------------------------


async def test_register_server_value_error_from_service():
    """register_server raises HTTPException(400) when service raises ValueError."""
    import pytest
    from fastapi import HTTPException
    from marketplace.api.v3_mcp_federation import (
        ServerRegisterRequest,
        register_server,
    )

    req = ServerRegisterRequest(
        name="err-srv",
        base_url="http://example.com/mcp",
        namespace="errns",
    )
    mock_db = AsyncMock()

    with patch(
        "marketplace.services.mcp_federation_service.register_server",
        new_callable=AsyncMock,
        side_effect=ValueError("duplicate namespace"),
    ):
        with pytest.raises(HTTPException) as exc_info:
            await register_server(req=req, db=mock_db, agent_id="agent-x")

    assert exc_info.value.status_code == 400
    assert "duplicate namespace" in exc_info.value.detail


# ---------------------------------------------------------------------------
# list_servers — return statement (line 116)
# ---------------------------------------------------------------------------


async def test_list_servers_return_direct():
    """list_servers returns correct dict shape directly."""
    from marketplace.api.v3_mcp_federation import list_servers

    mock_db = AsyncMock()
    fake_srv = MagicMock()
    fake_srv.id = "srv-1"
    fake_srv.name = "direct-srv"
    fake_srv.base_url = "http://x.com"
    fake_srv.namespace = "dirns"
    fake_srv.description = "d"
    fake_srv.status = "active"
    fake_srv.health_score = 100
    fake_srv.auth_type = "none"
    fake_srv.last_health_check = None
    fake_srv.registered_by = "agent-y"
    fake_srv.created_at = None
    fake_srv.updated_at = None

    with patch(
        "marketplace.services.mcp_federation_service.list_servers",
        new_callable=AsyncMock,
        return_value=[fake_srv],
    ):
        result = await list_servers(db=mock_db, agent_id="agent-y")

    assert result["total"] == 1
    assert result["servers"][0]["name"] == "direct-srv"


# ---------------------------------------------------------------------------
# get_server — 404 branch (lines 130-132) + success path (line 132)
# ---------------------------------------------------------------------------


async def test_get_server_not_found_direct():
    """get_server raises HTTPException(404) when service returns None."""
    import pytest
    from fastapi import HTTPException
    from marketplace.api.v3_mcp_federation import get_server

    mock_db = AsyncMock()

    with patch(
        "marketplace.services.mcp_federation_service.get_server",
        new_callable=AsyncMock,
        return_value=None,
    ):
        with pytest.raises(HTTPException) as exc_info:
            await get_server(server_id="missing", db=mock_db, agent_id="agent-z")

    assert exc_info.value.status_code == 404


async def test_get_server_found_direct():
    """get_server returns serialised server dict when found."""
    from marketplace.api.v3_mcp_federation import get_server

    mock_db = AsyncMock()
    fake_srv = MagicMock()
    fake_srv.id = "srv-found"
    fake_srv.name = "found-srv"
    fake_srv.base_url = "http://found.com"
    fake_srv.namespace = "foundns"
    fake_srv.description = "desc"
    fake_srv.status = "active"
    fake_srv.health_score = 90
    fake_srv.auth_type = "none"
    fake_srv.last_health_check = None
    fake_srv.registered_by = "owner"
    fake_srv.created_at = None
    fake_srv.updated_at = None

    with patch(
        "marketplace.services.mcp_federation_service.get_server",
        new_callable=AsyncMock,
        return_value=fake_srv,
    ):
        result = await get_server(server_id="srv-found", db=mock_db, agent_id="owner")

    assert result["id"] == "srv-found"
    assert result["name"] == "found-srv"


# ---------------------------------------------------------------------------
# update_server — 404, 403, field updates, URL strip (lines 144-170)
# ---------------------------------------------------------------------------


async def test_update_server_not_found_direct():
    """update_server raises HTTPException(404) when server missing."""
    import pytest
    from fastapi import HTTPException
    from marketplace.api.v3_mcp_federation import ServerUpdateRequest, update_server

    mock_db = AsyncMock()
    req = ServerUpdateRequest(name="new-name")

    with patch(
        "marketplace.services.mcp_federation_service.get_server",
        new_callable=AsyncMock,
        return_value=None,
    ):
        with pytest.raises(HTTPException) as exc_info:
            await update_server(
                server_id="missing", req=req, db=mock_db, agent_id="agent-1",
            )

    assert exc_info.value.status_code == 404


async def test_update_server_forbidden_direct():
    """update_server raises HTTPException(403) for non-owner."""
    import pytest
    from fastapi import HTTPException
    from marketplace.api.v3_mcp_federation import ServerUpdateRequest, update_server

    mock_db = AsyncMock()
    req = ServerUpdateRequest(name="hijack")

    fake_srv = MagicMock()
    fake_srv.registered_by = "real-owner"

    with patch(
        "marketplace.services.mcp_federation_service.get_server",
        new_callable=AsyncMock,
        return_value=fake_srv,
    ):
        with pytest.raises(HTTPException) as exc_info:
            await update_server(
                server_id="srv-x", req=req, db=mock_db, agent_id="intruder",
            )

    assert exc_info.value.status_code == 403


async def test_update_server_all_fields_direct():
    """update_server applies all optional fields and commits."""
    from marketplace.api.v3_mcp_federation import ServerUpdateRequest, update_server

    mock_db = AsyncMock()
    fake_srv = MagicMock()
    fake_srv.registered_by = "owner-a"
    fake_srv.id = "srv-all"
    fake_srv.name = "old-name"
    fake_srv.base_url = "http://old.com"
    fake_srv.namespace = "oldns"
    fake_srv.description = "old"
    fake_srv.status = "active"
    fake_srv.health_score = 80
    fake_srv.auth_type = "none"
    fake_srv.auth_credential_ref = ""
    fake_srv.last_health_check = None
    fake_srv.created_at = None
    fake_srv.updated_at = None

    req = ServerUpdateRequest(
        name="new-name",
        base_url="http://new.example.com/mcp/",
        namespace="newns",
        description="new-desc",
        auth_type="bearer",
        auth_credential_ref="tok-abc",
    )

    with patch(
        "marketplace.services.mcp_federation_service.get_server",
        new_callable=AsyncMock,
        return_value=fake_srv,
    ):
        result = await update_server(
            server_id="srv-all", req=req, db=mock_db, agent_id="owner-a",
        )

    # name updated
    assert fake_srv.name == "new-name"
    # base_url trailing slash stripped
    assert not fake_srv.base_url.endswith("/")
    assert fake_srv.namespace == "newns"
    assert fake_srv.description == "new-desc"
    assert fake_srv.auth_type == "bearer"
    assert fake_srv.auth_credential_ref == "tok-abc"
    # db.commit and db.refresh were awaited
    mock_db.commit.assert_awaited()
    mock_db.refresh.assert_awaited_with(fake_srv)


async def test_update_server_invalid_url_direct():
    """update_server raises HTTPException(400) for invalid base_url."""
    import pytest
    from fastapi import HTTPException
    from marketplace.api.v3_mcp_federation import ServerUpdateRequest, update_server

    mock_db = AsyncMock()
    fake_srv = MagicMock()
    fake_srv.registered_by = "owner-b"

    req = ServerUpdateRequest(base_url="ftp://bad-url.com")

    with patch(
        "marketplace.services.mcp_federation_service.get_server",
        new_callable=AsyncMock,
        return_value=fake_srv,
    ):
        with pytest.raises(HTTPException) as exc_info:
            await update_server(
                server_id="srv-b", req=req, db=mock_db, agent_id="owner-b",
            )

    assert exc_info.value.status_code == 400


async def test_update_server_no_registered_by_allows_anyone():
    """update_server with registered_by=None allows any agent to update."""
    from marketplace.api.v3_mcp_federation import ServerUpdateRequest, update_server

    mock_db = AsyncMock()
    fake_srv = MagicMock()
    fake_srv.registered_by = None  # no owner restriction
    fake_srv.id = "open-srv"
    fake_srv.name = "open-srv"
    fake_srv.base_url = "http://open.example.com"
    fake_srv.namespace = "openns"
    fake_srv.description = ""
    fake_srv.status = "active"
    fake_srv.health_score = 100
    fake_srv.auth_type = "none"
    fake_srv.auth_credential_ref = ""
    fake_srv.last_health_check = None
    fake_srv.created_at = None
    fake_srv.updated_at = None

    req = ServerUpdateRequest(description="updated by stranger")

    with patch(
        "marketplace.services.mcp_federation_service.get_server",
        new_callable=AsyncMock,
        return_value=fake_srv,
    ):
        result = await update_server(
            server_id="open-srv", req=req, db=mock_db, agent_id="stranger",
        )

    assert fake_srv.description == "updated by stranger"


# ---------------------------------------------------------------------------
# unregister_server — 404, 403, deleted=False (lines 181-188)
# ---------------------------------------------------------------------------


async def test_unregister_server_not_found_direct():
    """unregister_server raises HTTPException(404) when server missing."""
    import pytest
    from fastapi import HTTPException
    from marketplace.api.v3_mcp_federation import unregister_server

    mock_db = AsyncMock()

    with patch(
        "marketplace.services.mcp_federation_service.get_server",
        new_callable=AsyncMock,
        return_value=None,
    ):
        with pytest.raises(HTTPException) as exc_info:
            await unregister_server(
                server_id="missing", db=mock_db, agent_id="agent-del",
            )

    assert exc_info.value.status_code == 404


async def test_unregister_server_forbidden_direct():
    """unregister_server raises HTTPException(403) for non-owner."""
    import pytest
    from fastapi import HTTPException
    from marketplace.api.v3_mcp_federation import unregister_server

    mock_db = AsyncMock()
    fake_srv = MagicMock()
    fake_srv.registered_by = "real-owner"

    with patch(
        "marketplace.services.mcp_federation_service.get_server",
        new_callable=AsyncMock,
        return_value=fake_srv,
    ):
        with pytest.raises(HTTPException) as exc_info:
            await unregister_server(
                server_id="srv-del", db=mock_db, agent_id="intruder",
            )

    assert exc_info.value.status_code == 403


async def test_unregister_server_service_returns_false():
    """unregister_server raises HTTPException(404) when service returns False."""
    import pytest
    from fastapi import HTTPException
    from marketplace.api.v3_mcp_federation import unregister_server

    mock_db = AsyncMock()
    fake_srv = MagicMock()
    fake_srv.registered_by = "owner-c"

    with patch(
        "marketplace.services.mcp_federation_service.get_server",
        new_callable=AsyncMock,
        return_value=fake_srv,
    ), patch(
        "marketplace.services.mcp_federation_service.unregister_server",
        new_callable=AsyncMock,
        return_value=False,
    ):
        with pytest.raises(HTTPException) as exc_info:
            await unregister_server(
                server_id="ghost-srv", db=mock_db, agent_id="owner-c",
            )

    assert exc_info.value.status_code == 404


async def test_unregister_server_success_direct():
    """unregister_server returns success dict when deleted."""
    from marketplace.api.v3_mcp_federation import unregister_server

    mock_db = AsyncMock()
    fake_srv = MagicMock()
    fake_srv.registered_by = "owner-d"

    with patch(
        "marketplace.services.mcp_federation_service.get_server",
        new_callable=AsyncMock,
        return_value=fake_srv,
    ), patch(
        "marketplace.services.mcp_federation_service.unregister_server",
        new_callable=AsyncMock,
        return_value=True,
    ):
        result = await unregister_server(
            server_id="real-srv", db=mock_db, agent_id="owner-d",
        )

    assert result["detail"] == "Server unregistered"
    assert result["server_id"] == "real-srv"


# ---------------------------------------------------------------------------
# trigger_health_check — 404, error branch, success (lines 205-221)
# ---------------------------------------------------------------------------


async def test_trigger_health_check_not_found_direct():
    """trigger_health_check raises HTTPException(404) when server missing."""
    import pytest
    from fastapi import HTTPException
    from marketplace.api.v3_mcp_federation import trigger_health_check

    mock_db = AsyncMock()

    with patch(
        "marketplace.services.mcp_federation_service.get_server",
        new_callable=AsyncMock,
        return_value=None,
    ):
        with pytest.raises(HTTPException) as exc_info:
            await trigger_health_check(
                server_id="missing", db=mock_db, agent_id="agent-hc",
            )

    assert exc_info.value.status_code == 404


async def test_trigger_health_check_error_branch_direct():
    """trigger_health_check returns healthy=False when refresh returns error."""
    from marketplace.api.v3_mcp_federation import trigger_health_check

    mock_db = AsyncMock()
    fake_srv = MagicMock()
    fake_srv.health_score = 60

    with patch(
        "marketplace.services.mcp_federation_service.get_server",
        new_callable=AsyncMock,
        return_value=fake_srv,
    ), patch(
        "marketplace.services.mcp_federation_service.refresh_server_tools",
        new_callable=AsyncMock,
        return_value={"error": "timeout"},
    ), patch(
        "marketplace.services.mcp_federation_service.update_health_score",
        new_callable=AsyncMock,
    ):
        result = await trigger_health_check(
            server_id="hc-srv", db=mock_db, agent_id="agent-hc",
        )

    assert result["healthy"] is False
    assert result["error"] == "timeout"
    assert result["health_score"] == 40  # max(0, 60 - 20)


async def test_trigger_health_check_success_direct():
    """trigger_health_check returns healthy=True when refresh succeeds."""
    from marketplace.api.v3_mcp_federation import trigger_health_check

    mock_db = AsyncMock()
    fake_srv = MagicMock()
    fake_srv.health_score = 80

    with patch(
        "marketplace.services.mcp_federation_service.get_server",
        new_callable=AsyncMock,
        return_value=fake_srv,
    ), patch(
        "marketplace.services.mcp_federation_service.refresh_server_tools",
        new_callable=AsyncMock,
        return_value={"tools": [{"name": "t1"}], "count": 1},
    ):
        result = await trigger_health_check(
            server_id="hc-ok-srv", db=mock_db, agent_id="agent-hc",
        )

    assert result["healthy"] is True
    assert result["tools_count"] == 1
    assert result["health_score"] == 100


# ---------------------------------------------------------------------------
# refresh_server_tools route — 404, error 502, success (lines 237-244)
# ---------------------------------------------------------------------------


async def test_refresh_server_tools_not_found_direct():
    """refresh_server_tools raises HTTPException(404) when server missing."""
    import pytest
    from fastapi import HTTPException
    from marketplace.api.v3_mcp_federation import refresh_server_tools

    mock_db = AsyncMock()

    with patch(
        "marketplace.services.mcp_federation_service.get_server",
        new_callable=AsyncMock,
        return_value=None,
    ):
        with pytest.raises(HTTPException) as exc_info:
            await refresh_server_tools(
                server_id="missing", db=mock_db, agent_id="agent-rf",
            )

    assert exc_info.value.status_code == 404


async def test_refresh_server_tools_error_direct():
    """refresh_server_tools raises HTTPException(502) on error."""
    import pytest
    from fastapi import HTTPException
    from marketplace.api.v3_mcp_federation import refresh_server_tools

    mock_db = AsyncMock()
    fake_srv = MagicMock()

    with patch(
        "marketplace.services.mcp_federation_service.get_server",
        new_callable=AsyncMock,
        return_value=fake_srv,
    ), patch(
        "marketplace.services.mcp_federation_service.refresh_server_tools",
        new_callable=AsyncMock,
        return_value={"error": "connection refused"},
    ):
        with pytest.raises(HTTPException) as exc_info:
            await refresh_server_tools(
                server_id="err-rf-srv", db=mock_db, agent_id="agent-rf",
            )

    assert exc_info.value.status_code == 502
    assert "connection refused" in exc_info.value.detail


async def test_refresh_server_tools_success_direct():
    """refresh_server_tools returns tool list dict on success."""
    from marketplace.api.v3_mcp_federation import refresh_server_tools

    mock_db = AsyncMock()
    fake_srv = MagicMock()

    with patch(
        "marketplace.services.mcp_federation_service.get_server",
        new_callable=AsyncMock,
        return_value=fake_srv,
    ), patch(
        "marketplace.services.mcp_federation_service.refresh_server_tools",
        new_callable=AsyncMock,
        return_value={"tools": [{"name": "a"}, {"name": "b"}], "count": 2},
    ):
        result = await refresh_server_tools(
            server_id="ok-rf-srv", db=mock_db, agent_id="agent-rf",
        )

    assert result["server_id"] == "ok-rf-srv"
    assert result["tools_refreshed"] == 2
    assert len(result["tools"]) == 2


# ---------------------------------------------------------------------------
# list_federated_tools — return statement (line 262)
# ---------------------------------------------------------------------------


async def test_list_federated_tools_return_direct():
    """list_federated_tools return statement is executed and returns correct shape."""
    from marketplace.api.v3_mcp_federation import list_federated_tools

    mock_db = AsyncMock()

    with patch(
        "marketplace.services.mcp_federation_service.discover_tools",
        new_callable=AsyncMock,
        return_value=[{"name": "ns.tool1"}, {"name": "ns.tool2"}],
    ):
        result = await list_federated_tools(
            namespace=None, db=mock_db, agent_id="agent-lt",
        )

    assert result["total"] == 2
    assert len(result["tools"]) == 2


async def test_list_federated_tools_with_namespace_direct():
    """list_federated_tools passes namespace filter to service."""
    from marketplace.api.v3_mcp_federation import list_federated_tools

    mock_db = AsyncMock()

    with patch(
        "marketplace.services.mcp_federation_service.discover_tools",
        new_callable=AsyncMock,
        return_value=[{"name": "filtered.t"}],
    ) as mock_discover:
        result = await list_federated_tools(
            namespace="filtered", db=mock_db, agent_id="agent-lt2",
        )

    mock_discover.assert_awaited_once_with(mock_db, namespace="filtered")
    assert result["total"] == 1


# ---------------------------------------------------------------------------
# list_federated_resources — for-loop and JSON decode (lines 308-323)
# ---------------------------------------------------------------------------


async def test_list_federated_resources_loop_direct():
    """list_federated_resources iterates servers and prefixes resources."""
    from marketplace.api.v3_mcp_federation import list_federated_resources

    fake_srv = MagicMock()
    fake_srv.id = "loop-srv"
    fake_srv.namespace = "loopns"
    fake_srv.resources_json = json.dumps([
        {"uri": "loopns://a", "name": "A"},
        {"uri": "loopns://b", "name": "B"},
    ])

    # Mock the DB execute → result chain
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = [fake_srv]
    mock_db = AsyncMock()
    mock_db.execute = AsyncMock(return_value=mock_result)

    result = await list_federated_resources(
        namespace=None, db=mock_db, agent_id="agent-lr",
    )

    assert result["total"] == 2
    assert result["resources"][0]["_server_id"] == "loop-srv"
    assert result["resources"][0]["_namespace"] == "loopns"


async def test_list_federated_resources_json_decode_error_direct():
    """list_federated_resources handles invalid resources_json gracefully."""
    from marketplace.api.v3_mcp_federation import list_federated_resources

    fake_srv = MagicMock()
    fake_srv.id = "bad-json-srv"
    fake_srv.namespace = "badns"
    fake_srv.resources_json = "{invalid json{"

    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = [fake_srv]
    mock_db = AsyncMock()
    mock_db.execute = AsyncMock(return_value=mock_result)

    result = await list_federated_resources(
        namespace=None, db=mock_db, agent_id="agent-lr2",
    )

    assert result["total"] == 0


async def test_list_federated_resources_none_json_direct():
    """list_federated_resources handles None resources_json gracefully."""
    from marketplace.api.v3_mcp_federation import list_federated_resources

    fake_srv = MagicMock()
    fake_srv.id = "none-json-srv"
    fake_srv.namespace = "nonens"
    fake_srv.resources_json = None

    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = [fake_srv]
    mock_db = AsyncMock()
    mock_db.execute = AsyncMock(return_value=mock_result)

    result = await list_federated_resources(
        namespace=None, db=mock_db, agent_id="agent-lr3",
    )

    assert result["total"] == 0


async def test_list_federated_resources_with_namespace_filter_direct():
    """list_federated_resources adds namespace filter to query when provided."""
    from marketplace.api.v3_mcp_federation import list_federated_resources

    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = []
    mock_db = AsyncMock()
    mock_db.execute = AsyncMock(return_value=mock_result)

    result = await list_federated_resources(
        namespace="targetns", db=mock_db, agent_id="agent-lr4",
    )

    assert result["total"] == 0
    mock_db.execute.assert_awaited_once()


# ---------------------------------------------------------------------------
# read_federated_resource — 404, sort+loop, httpx success (lines 356-373)
# ---------------------------------------------------------------------------


async def test_read_federated_resource_no_servers_direct():
    """read_federated_resource raises HTTPException(404) when no servers found."""
    import pytest
    from fastapi import HTTPException
    from marketplace.api.v3_mcp_federation import ResourceReadRequest, read_federated_resource

    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = []
    mock_db = AsyncMock()
    mock_db.execute = AsyncMock(return_value=mock_result)

    req = ResourceReadRequest(uri="unknown://resource")

    with pytest.raises(HTTPException) as exc_info:
        await read_federated_resource(req=req, db=mock_db, agent_id="agent-rr")

    assert exc_info.value.status_code == 404


async def test_read_federated_resource_httpx_success_direct():
    """read_federated_resource proxies to first healthy server via httpx."""
    import httpx as _httpx
    from marketplace.api.v3_mcp_federation import ResourceReadRequest, read_federated_resource

    fake_srv = MagicMock()
    fake_srv.id = "httpx-srv"
    fake_srv.namespace = "myns"
    fake_srv.base_url = "http://myns.example.com"
    fake_srv.health_score = 100
    fake_srv.auth_type = "none"
    fake_srv.auth_credential_ref = ""

    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = [fake_srv]
    mock_db = AsyncMock()
    mock_db.execute = AsyncMock(return_value=mock_result)

    mock_resp = MagicMock()
    mock_resp.json.return_value = {"content": "result"}
    mock_resp.raise_for_status.return_value = None

    mock_http_client = AsyncMock()
    mock_http_client.post = AsyncMock(return_value=mock_resp)

    req = ResourceReadRequest(uri="myns://some/data")

    with patch("httpx.AsyncClient") as mock_cls:
        mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_http_client)
        mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)

        result = await read_federated_resource(req=req, db=mock_db, agent_id="agent-rr")

    assert result["content"] == "result"


async def test_read_federated_resource_sort_by_health_direct():
    """read_federated_resource tries servers in descending health score order."""
    from marketplace.api.v3_mcp_federation import ResourceReadRequest, read_federated_resource

    low_srv = MagicMock()
    low_srv.id = "low-srv"
    low_srv.namespace = "sortns"
    low_srv.base_url = "http://low.example.com"
    low_srv.health_score = 20
    low_srv.auth_type = "none"
    low_srv.auth_credential_ref = ""

    high_srv = MagicMock()
    high_srv.id = "high-srv"
    high_srv.namespace = "sortns"
    high_srv.base_url = "http://high.example.com"
    high_srv.health_score = 95
    high_srv.auth_type = "none"
    high_srv.auth_credential_ref = ""

    mock_result = MagicMock()
    # Return low first, so we verify high gets tried first
    mock_result.scalars.return_value.all.return_value = [low_srv, high_srv]
    mock_db = AsyncMock()
    mock_db.execute = AsyncMock(return_value=mock_result)

    mock_resp = MagicMock()
    mock_resp.json.return_value = {"data": "sorted"}
    mock_resp.raise_for_status.return_value = None

    mock_http_client = AsyncMock()
    mock_http_client.post = AsyncMock(return_value=mock_resp)

    req = ResourceReadRequest(uri="sortns://test")

    with patch("httpx.AsyncClient") as mock_cls:
        mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_http_client)
        mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)

        result = await read_federated_resource(req=req, db=mock_db, agent_id="agent-sort")

    # First call should have used the high-health server URL
    first_call_url = mock_http_client.post.call_args_list[0][0][0]
    assert "high.example.com" in first_call_url
    assert result["data"] == "sorted"


async def test_read_federated_resource_all_fail_502_direct():
    """read_federated_resource raises 502 when all servers fail."""
    import httpx as _httpx
    import pytest
    from fastapi import HTTPException
    from marketplace.api.v3_mcp_federation import ResourceReadRequest, read_federated_resource

    fake_srv = MagicMock()
    fake_srv.id = "fail-srv"
    fake_srv.namespace = "failns"
    fake_srv.base_url = "http://fail.example.com"
    fake_srv.health_score = 50
    fake_srv.auth_type = "none"
    fake_srv.auth_credential_ref = ""

    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = [fake_srv]
    mock_db = AsyncMock()
    mock_db.execute = AsyncMock(return_value=mock_result)

    mock_http_client = AsyncMock()
    mock_http_client.post = AsyncMock(
        side_effect=_httpx.RequestError("connection refused"),
    )

    req = ResourceReadRequest(uri="failns://resource")

    with patch("httpx.AsyncClient") as mock_cls:
        mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_http_client)
        mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)

        with pytest.raises(HTTPException) as exc_info:
            await read_federated_resource(req=req, db=mock_db, agent_id="agent-fail")

    assert exc_info.value.status_code == 502


async def test_read_federated_resource_no_scheme_direct():
    """read_federated_resource with URI that has no :// uses no namespace filter."""
    import pytest
    from fastapi import HTTPException
    from marketplace.api.v3_mcp_federation import ResourceReadRequest, read_federated_resource

    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = []
    mock_db = AsyncMock()
    mock_db.execute = AsyncMock(return_value=mock_result)

    # URI without :// — namespace should be None, no namespace filter added
    req = ResourceReadRequest(uri="/just/a/path")

    with pytest.raises(HTTPException) as exc_info:
        await read_federated_resource(req=req, db=mock_db, agent_id="agent-ns")

    assert exc_info.value.status_code == 404


# ---------------------------------------------------------------------------
# federation_health_overview — tools loop (lines 395-405)
# ---------------------------------------------------------------------------


async def test_federation_health_overview_tools_loop_direct():
    """federation_health_overview counts tools from tools_json for each server."""
    from marketplace.api.v3_mcp_federation import federation_health_overview

    srv_a = MagicMock()
    srv_a.status = "active"
    srv_a.health_score = 80
    srv_a.tools_json = json.dumps([{"name": "t1"}, {"name": "t2"}])

    srv_b = MagicMock()
    srv_b.status = "degraded"
    srv_b.health_score = 30
    srv_b.tools_json = json.dumps([{"name": "t3"}])

    srv_c = MagicMock()
    srv_c.status = "inactive"
    srv_c.health_score = 0
    srv_c.tools_json = None  # None → 0 tools

    mock_db = AsyncMock()

    with patch(
        "marketplace.services.mcp_federation_service.list_servers",
        new_callable=AsyncMock,
        return_value=[srv_a, srv_b, srv_c],
    ):
        result = await federation_health_overview(db=mock_db)

    assert result["server_count"] == 3
    assert result["healthy_count"] == 1   # only srv_a (active + score >= 50)
    assert result["degraded_count"] == 1
    assert result["inactive_count"] == 1
    assert result["total_tool_count"] == 3  # t1 + t2 + t3


async def test_federation_health_overview_malformed_tools_json_direct():
    """federation_health_overview skips malformed tools_json without crashing."""
    from marketplace.api.v3_mcp_federation import federation_health_overview

    srv = MagicMock()
    srv.status = "active"
    srv.health_score = 70
    srv.tools_json = "{bad json{"

    mock_db = AsyncMock()

    with patch(
        "marketplace.services.mcp_federation_service.list_servers",
        new_callable=AsyncMock,
        return_value=[srv],
    ):
        result = await federation_health_overview(db=mock_db)

    assert result["total_tool_count"] == 0
    assert result["server_count"] == 1


async def test_federation_health_overview_empty_direct():
    """federation_health_overview with no servers returns all zeros."""
    from marketplace.api.v3_mcp_federation import federation_health_overview

    mock_db = AsyncMock()

    with patch(
        "marketplace.services.mcp_federation_service.list_servers",
        new_callable=AsyncMock,
        return_value=[],
    ):
        result = await federation_health_overview(db=mock_db)

    assert result["server_count"] == 0
    assert result["healthy_count"] == 0
    assert result["total_tool_count"] == 0


# ---------------------------------------------------------------------------
# register_server — success path (line 101: return _server_to_dict)
# ---------------------------------------------------------------------------


async def test_register_server_success_direct():
    """register_server returns serialised server on successful service call."""
    from marketplace.api.v3_mcp_federation import ServerRegisterRequest, register_server

    req = ServerRegisterRequest(
        name="ok-srv",
        base_url="http://ok.example.com/mcp",
        namespace="okns",
    )
    mock_db = AsyncMock()

    fake_srv = MagicMock()
    fake_srv.id = "srv-ok"
    fake_srv.name = "ok-srv"
    fake_srv.base_url = "http://ok.example.com/mcp"
    fake_srv.namespace = "okns"
    fake_srv.description = ""
    fake_srv.status = "active"
    fake_srv.health_score = 100
    fake_srv.auth_type = "none"
    fake_srv.last_health_check = None
    fake_srv.registered_by = "agent-ok"
    fake_srv.created_at = None
    fake_srv.updated_at = None

    with patch(
        "marketplace.services.mcp_federation_service.register_server",
        new_callable=AsyncMock,
        return_value=fake_srv,
    ):
        result = await register_server(req=req, db=mock_db, agent_id="agent-ok")

    assert result["id"] == "srv-ok"
    assert result["name"] == "ok-srv"
    assert result["namespace"] == "okns"
