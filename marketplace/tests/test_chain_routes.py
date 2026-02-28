"""API integration tests for the v5 chain endpoints."""

import json
import uuid

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _set_trust_tier(db, agent_id: str, tier: str = "T2") -> None:
    """Seed a trust profile for an agent so trust-gated routes pass."""
    from marketplace.models.agent_trust import AgentTrustProfile
    profile = AgentTrustProfile(
        id=str(uuid.uuid4()),
        agent_id=agent_id,
        trust_tier=tier,
    )
    db.add(profile)
    await db.commit()


def _make_graph_json(agent_ids: list[str]) -> str:
    """Build a valid DAG JSON string with agent_call nodes."""
    nodes = {}
    prev_id = None
    for i, aid in enumerate(agent_ids):
        node_id = f"node_{i}"
        node_def = {
            "type": "agent_call",
            "config": {"agent_id": aid},
        }
        if prev_id:
            node_def["depends_on"] = [prev_id]
        nodes[node_id] = node_def
        prev_id = node_id
    return json.dumps({"nodes": nodes, "edges": []})


async def _create_template(client, token, agent_id, name="Test Chain"):
    """Helper to create a chain template via API and return the response JSON."""
    graph_json = _make_graph_json([agent_id])
    resp = await client.post(
        "/api/v5/chain-templates",
        json={
            "name": name,
            "description": "test",
            "category": "test",
            "graph_json": graph_json,
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    return resp


# ---------------------------------------------------------------------------
# CRUD tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_template_success(client, make_agent, db):
    agent, token = await make_agent()
    agent.a2a_endpoint = "http://test:9000"
    await db.commit()
    await _set_trust_tier(db, agent.id)

    resp = await _create_template(client, token, agent.id)
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "Test Chain"
    assert data["status"] == "active"
    assert data["author_id"] == agent.id


@pytest.mark.asyncio
async def test_create_template_no_auth(client):
    resp = await client.post(
        "/api/v5/chain-templates",
        json={"name": "X", "graph_json": "{}"},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_create_template_ssrf_rejected(client, make_agent, db):
    agent, token = await make_agent()
    agent.a2a_endpoint = "http://test:9000"
    await db.commit()
    await _set_trust_tier(db, agent.id)

    graph = {
        "nodes": {
            "n1": {
                "type": "agent_call",
                "config": {"agent_id": agent.id, "endpoint": "http://evil.com"},
            }
        },
        "edges": [],
    }
    resp = await client.post(
        "/api/v5/chain-templates",
        json={"name": "SSRF", "graph_json": json.dumps(graph)},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 400
    assert "raw endpoint" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_list_templates(client, make_agent, db):
    agent, token = await make_agent()
    agent.a2a_endpoint = "http://test:9000"
    await db.commit()
    await _set_trust_tier(db, agent.id)

    await _create_template(client, token, agent.id, "Chain A")
    await _create_template(client, token, agent.id, "Chain B")

    resp = await client.get(
        "/api/v5/chain-templates",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] >= 2
    assert len(data["templates"]) >= 2


@pytest.mark.asyncio
async def test_get_template(client, make_agent, db):
    agent, token = await make_agent()
    agent.a2a_endpoint = "http://test:9000"
    await db.commit()
    await _set_trust_tier(db, agent.id)

    create_resp = await _create_template(client, token, agent.id)
    template_id = create_resp.json()["id"]

    resp = await client.get(
        f"/api/v5/chain-templates/{template_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["id"] == template_id


@pytest.mark.asyncio
async def test_get_template_not_found(client, make_agent, db):
    agent, token = await make_agent()
    await _set_trust_tier(db, agent.id)
    resp = await client.get(
        "/api/v5/chain-templates/nonexistent-id",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Fork tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_fork_template(client, make_agent, db):
    author, author_token = await make_agent()
    forker, forker_token = await make_agent()
    author.a2a_endpoint = "http://test:9000"
    await db.commit()
    await _set_trust_tier(db, author.id)
    await _set_trust_tier(db, forker.id)

    create_resp = await _create_template(client, author_token, author.id)
    template_id = create_resp.json()["id"]

    resp = await client.post(
        f"/api/v5/chain-templates/{template_id}/fork",
        json={},
        headers={"Authorization": f"Bearer {forker_token}"},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["forked_from_id"] == template_id
    assert data["author_id"] == forker.id


# ---------------------------------------------------------------------------
# Execute tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_execute_chain(client, make_agent, db):
    agent, token = await make_agent()
    agent.a2a_endpoint = "http://test:9000"
    await db.commit()
    await _set_trust_tier(db, agent.id)

    create_resp = await _create_template(client, token, agent.id)
    template_id = create_resp.json()["id"]

    resp = await client.post(
        f"/api/v5/chain-templates/{template_id}/execute",
        json={"input_data": {"query": "test"}},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 202
    data = resp.json()
    assert data["chain_template_id"] == template_id
    assert data["status"] == "pending"


@pytest.mark.asyncio
async def test_execute_idempotency(client, make_agent, db):
    agent, token = await make_agent()
    agent.a2a_endpoint = "http://test:9000"
    await db.commit()
    await _set_trust_tier(db, agent.id)

    create_resp = await _create_template(client, token, agent.id)
    template_id = create_resp.json()["id"]

    body = {"input_data": {}, "idempotency_key": "idem-api-test-001"}

    resp1 = await client.post(
        f"/api/v5/chain-templates/{template_id}/execute",
        json=body,
        headers={"Authorization": f"Bearer {token}"},
    )
    resp2 = await client.post(
        f"/api/v5/chain-templates/{template_id}/execute",
        json=body,
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp1.status_code == 202
    assert resp2.status_code == 202
    assert resp1.json()["id"] == resp2.json()["id"]


@pytest.mark.asyncio
async def test_get_execution(client, make_agent, db):
    agent, token = await make_agent()
    agent.a2a_endpoint = "http://test:9000"
    await db.commit()
    await _set_trust_tier(db, agent.id)

    create_resp = await _create_template(client, token, agent.id)
    template_id = create_resp.json()["id"]

    exec_resp = await client.post(
        f"/api/v5/chain-templates/{template_id}/execute",
        json={},
        headers={"Authorization": f"Bearer {token}"},
    )
    exec_id = exec_resp.json()["id"]

    resp = await client.get(
        f"/api/v5/chain-executions/{exec_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["id"] == exec_id


# ---------------------------------------------------------------------------
# Provenance tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_provenance_forbidden(client, make_agent, db):
    author, author_token = await make_agent()
    outsider, outsider_token = await make_agent()
    author.a2a_endpoint = "http://test:9000"
    await db.commit()
    await _set_trust_tier(db, author.id)

    create_resp = await _create_template(client, author_token, author.id)
    template_id = create_resp.json()["id"]

    exec_resp = await client.post(
        f"/api/v5/chain-templates/{template_id}/execute",
        json={},
        headers={"Authorization": f"Bearer {author_token}"},
    )
    exec_id = exec_resp.json()["id"]

    resp = await client.get(
        f"/api/v5/chain-executions/{exec_id}/provenance",
        headers={"Authorization": f"Bearer {outsider_token}"},
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_provenance_success(client, make_agent, db):
    agent, token = await make_agent()
    agent.a2a_endpoint = "http://test:9000"
    await db.commit()
    await _set_trust_tier(db, agent.id)

    create_resp = await _create_template(client, token, agent.id)
    template_id = create_resp.json()["id"]

    exec_resp = await client.post(
        f"/api/v5/chain-templates/{template_id}/execute",
        json={},
        headers={"Authorization": f"Bearer {token}"},
    )
    exec_id = exec_resp.json()["id"]

    resp = await client.get(
        f"/api/v5/chain-executions/{exec_id}/provenance",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["chain_execution_id"] == exec_id
    assert "nodes" in data


# ---------------------------------------------------------------------------
# List executions and archive tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_template_executions(client, make_agent, db):
    agent, token = await make_agent()
    agent.a2a_endpoint = "http://test:9000"
    await db.commit()
    await _set_trust_tier(db, agent.id)

    create_resp = await _create_template(client, token, agent.id)
    template_id = create_resp.json()["id"]

    await client.post(
        f"/api/v5/chain-templates/{template_id}/execute",
        json={},
        headers={"Authorization": f"Bearer {token}"},
    )

    resp = await client.get(
        f"/api/v5/chain-templates/{template_id}/executions",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] >= 1


@pytest.mark.asyncio
async def test_archive_template(client, make_agent, db):
    agent, token = await make_agent()
    agent.a2a_endpoint = "http://test:9000"
    await db.commit()
    await _set_trust_tier(db, agent.id)

    create_resp = await _create_template(client, token, agent.id)
    template_id = create_resp.json()["id"]

    resp = await client.delete(
        f"/api/v5/chain-templates/{template_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert "archived" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_archive_non_author(client, make_agent, db):
    author, author_token = await make_agent()
    other, other_token = await make_agent()
    author.a2a_endpoint = "http://test:9000"
    await db.commit()
    await _set_trust_tier(db, author.id)

    create_resp = await _create_template(client, author_token, author.id)
    template_id = create_resp.json()["id"]

    resp = await client.delete(
        f"/api/v5/chain-templates/{template_id}",
        headers={"Authorization": f"Bearer {other_token}"},
    )
    assert resp.status_code == 403
