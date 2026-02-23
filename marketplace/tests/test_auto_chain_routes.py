"""API integration tests for the Phase 2 auto-chaining endpoints."""

import json

import pytest


# ---------------------------------------------------------------------------
# POST /chains/compose
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_compose_success(client, make_agent, db):
    agent, token = await make_agent()
    agent.capabilities = json.dumps(["web-search", "data"])
    agent.a2a_endpoint = "http://test:9000"
    await db.commit()

    resp = await client.post(
        "/api/v5/chains/compose",
        json={"task_description": "Search the web for Python data"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "draft"
    assert "data" in data["capabilities"]
    assert len(data["assignments"]) >= 1


@pytest.mark.asyncio
async def test_compose_no_auth(client):
    resp = await client.post(
        "/api/v5/chains/compose",
        json={"task_description": "Search the web for data"},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_compose_no_capabilities(client, make_agent):
    _, token = await make_agent()

    resp = await client.post(
        "/api/v5/chains/compose",
        json={"task_description": "hello world random text"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 400
    assert "Could not identify" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_compose_no_matching_agents(client, make_agent):
    _, token = await make_agent()

    resp = await client.post(
        "/api/v5/chains/compose",
        json={"task_description": "Search the web for data"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 400
    assert "No active agents" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_compose_with_filters(client, make_agent, db):
    agent, token = await make_agent()
    agent.capabilities = json.dumps(["web-search", "data"])
    agent.a2a_endpoint = "http://test:9000"
    await db.commit()

    resp = await client.post(
        "/api/v5/chains/compose",
        json={
            "task_description": "Search the web for data",
            "max_price": 10.0,
            "min_quality": 0.1,
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "draft"


# ---------------------------------------------------------------------------
# POST /chains/suggest-agents
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_suggest_agents_success(client, make_agent, db):
    agent, token = await make_agent()
    agent.capabilities = json.dumps(["web-search", "data", "scraping"])
    agent.a2a_endpoint = "http://test:9000"
    await db.commit()

    resp = await client.post(
        "/api/v5/chains/suggest-agents",
        json={"capability": "data"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["capability"] == "data"
    assert data["total"] >= 1
    assert len(data["agents"]) >= 1


@pytest.mark.asyncio
async def test_suggest_agents_no_auth(client):
    resp = await client.post(
        "/api/v5/chains/suggest-agents",
        json={"capability": "data"},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_suggest_agents_empty(client, make_agent):
    _, token = await make_agent()

    resp = await client.post(
        "/api/v5/chains/suggest-agents",
        json={"capability": "data"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 0
    assert data["agents"] == []


@pytest.mark.asyncio
async def test_suggest_agents_with_filters(client, make_agent, db):
    agent, token = await make_agent()
    agent.capabilities = json.dumps(["web-search", "data"])
    await db.commit()

    resp = await client.post(
        "/api/v5/chains/suggest-agents",
        json={"capability": "data", "max_results": 5, "max_price": 10.0},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200


# ---------------------------------------------------------------------------
# POST /chains/{chain_template_id}/validate
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_validate_chain_success(client, make_agent, db):
    agent, token = await make_agent()
    agent.a2a_endpoint = "http://test:9000"
    await db.commit()

    # Create a chain template first
    graph = json.dumps({
        "nodes": {"n1": {"type": "agent_call", "config": {"agent_id": agent.id}}},
        "edges": [],
    })
    create_resp = await client.post(
        "/api/v5/chain-templates",
        json={"name": "ValidateMe", "graph_json": graph},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert create_resp.status_code == 201
    template_id = create_resp.json()["id"]

    resp = await client.post(
        f"/api/v5/chains/{template_id}/validate",
        json={},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["valid"] is True
    assert data["template_id"] == template_id
    assert len(data["agents"]) == 1


@pytest.mark.asyncio
async def test_validate_chain_not_found(client, make_agent):
    _, token = await make_agent()

    resp = await client.post(
        "/api/v5/chains/nonexistent-id/validate",
        json={},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_validate_chain_inactive_agent(client, make_agent, db):
    agent, token = await make_agent()
    agent.a2a_endpoint = "http://test:9000"
    await db.commit()

    graph = json.dumps({
        "nodes": {"n1": {"type": "agent_call", "config": {"agent_id": agent.id}}},
        "edges": [],
    })
    create_resp = await client.post(
        "/api/v5/chain-templates",
        json={"name": "WillBreak", "graph_json": graph},
        headers={"Authorization": f"Bearer {token}"},
    )
    template_id = create_resp.json()["id"]

    # Deactivate agent
    agent.status = "suspended"
    await db.commit()

    resp = await client.post(
        f"/api/v5/chains/{template_id}/validate",
        json={},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["valid"] is False
    assert len(data["errors"]) > 0


@pytest.mark.asyncio
async def test_validate_no_auth(client):
    resp = await client.post(
        "/api/v5/chains/some-id/validate",
        json={},
    )
    assert resp.status_code == 401
