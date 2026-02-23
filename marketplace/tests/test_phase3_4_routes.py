"""API integration tests for Phase 3 (analytics, provenance-entries) and Phase 4 (policy, settlement) endpoints."""

import json
import uuid
from decimal import Decimal

import pytest

from marketplace.models.chain_provenance import ChainProvenanceEntry
from marketplace.models.chain_template import ChainExecution, ChainTemplate
from marketplace.models.workflow import WorkflowDefinition


def _new_id() -> str:
    return str(uuid.uuid4())


def _make_graph_json(agent_ids: list[str]) -> str:
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


async def _seed_template_and_execution(db, agent_id, status="completed"):
    """Seed a template + execution directly in the DB for read-only tests."""
    wf = WorkflowDefinition(
        id=_new_id(),
        name="test-wf",
        graph_json=_make_graph_json([agent_id]),
        owner_id=agent_id,
    )
    db.add(wf)
    await db.commit()

    tmpl = ChainTemplate(
        id=_new_id(),
        name="test-chain",
        workflow_id=wf.id,
        graph_json=wf.graph_json,
        author_id=agent_id,
        status="active",
        execution_count=5,
    )
    db.add(tmpl)
    await db.commit()

    ex = ChainExecution(
        id=_new_id(),
        chain_template_id=tmpl.id,
        initiated_by=agent_id,
        status=status,
        total_cost_usd=Decimal("0.50"),
        participant_agents_json=json.dumps([agent_id]),
    )
    db.add(ex)
    await db.commit()
    await db.refresh(tmpl)
    await db.refresh(ex)
    return tmpl, ex


# ---------------------------------------------------------------------------
# Phase 3: Analytics endpoints
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_chain_analytics(client, make_agent, db):
    agent, token = await make_agent()
    tmpl, ex = await _seed_template_and_execution(db, agent.id)

    resp = await client.get(
        f"/api/v5/chain-templates/{tmpl.id}/analytics",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["template_id"] == tmpl.id
    assert data["execution_count"] >= 1


@pytest.mark.asyncio
async def test_get_chain_analytics_not_found(client, make_agent, db):
    _, token = await make_agent()
    resp = await client.get(
        f"/api/v5/chain-templates/{_new_id()}/analytics",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_get_popular_chains(client, make_agent, db):
    agent, token = await make_agent()
    await _seed_template_and_execution(db, agent.id)

    resp = await client.get(
        "/api/v5/chains/popular",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "chains" in data
    assert isinstance(data["chains"], list)


@pytest.mark.asyncio
async def test_get_agent_chain_stats(client, make_agent, db):
    agent, token = await make_agent()
    await _seed_template_and_execution(db, agent.id)

    resp = await client.get(
        f"/api/v5/chains/agents/{agent.id}/stats",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["agent_id"] == agent.id
    assert "chains_authored" in data


# ---------------------------------------------------------------------------
# Phase 3: Provenance-entries endpoint
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_provenance_entries_success(client, make_agent, db):
    agent, token = await make_agent()
    tmpl, ex = await _seed_template_and_execution(db, agent.id)

    # Add a provenance entry
    entry = ChainProvenanceEntry(
        chain_execution_id=ex.id,
        node_id="n0",
        event_type="node_completed",
        node_type="agent_call",
        agent_id=agent.id,
        cost_usd=Decimal("0.05"),
        status="completed",
    )
    db.add(entry)
    await db.commit()

    resp = await client.get(
        f"/api/v5/chain-executions/{ex.id}/provenance-entries",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "entries" in data
    assert data["total"] >= 1


@pytest.mark.asyncio
async def test_provenance_entries_forbidden(client, make_agent, db):
    agent1, token1 = await make_agent()
    agent2, token2 = await make_agent()
    tmpl, ex = await _seed_template_and_execution(db, agent1.id)

    resp = await client.get(
        f"/api/v5/chain-executions/{ex.id}/provenance-entries",
        headers={"Authorization": f"Bearer {token2}"},
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_provenance_entries_not_found(client, make_agent, db):
    _, token = await make_agent()
    resp = await client.get(
        f"/api/v5/chain-executions/{_new_id()}/provenance-entries",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Phase 4: Policy endpoints
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_policy_success(client, make_agent, db):
    _, token = await make_agent()
    resp = await client.post(
        "/api/v5/chains/policies",
        json={
            "name": "Swiss Data Residency",
            "policy_type": "jurisdiction",
            "rules_json": json.dumps({"allowed_jurisdictions": ["CH", "EU"]}),
            "enforcement": "block",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "Swiss Data Residency"
    assert data["policy_type"] == "jurisdiction"
    assert data["enforcement"] == "block"
    assert data["status"] == "active"


@pytest.mark.asyncio
async def test_create_policy_invalid_type(client, make_agent, db):
    _, token = await make_agent()
    resp = await client.post(
        "/api/v5/chains/policies",
        json={
            "name": "Bad Policy",
            "policy_type": "invalid_type",
            "rules_json": "{}",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_create_policy_no_auth(client):
    resp = await client.post(
        "/api/v5/chains/policies",
        json={
            "name": "Test",
            "policy_type": "cost_limit",
            "rules_json": "{}",
        },
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_list_policies(client, make_agent, db):
    _, token = await make_agent()
    # Create a policy first
    await client.post(
        "/api/v5/chains/policies",
        json={
            "name": "Cost Cap",
            "policy_type": "cost_limit",
            "rules_json": json.dumps({"max_cost_usd": 10.0}),
        },
        headers={"Authorization": f"Bearer {token}"},
    )

    resp = await client.get(
        "/api/v5/chains/policies",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "policies" in data
    assert data["total"] >= 1


@pytest.mark.asyncio
async def test_evaluate_policies(client, make_agent, db):
    agent, token = await make_agent()
    agent.a2a_endpoint = "http://test:9000"
    await db.commit()

    # Create template
    graph_json = _make_graph_json([agent.id])
    tmpl_resp = await client.post(
        "/api/v5/chain-templates",
        json={
            "name": "Policy Test Chain",
            "graph_json": graph_json,
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert tmpl_resp.status_code == 201
    template_id = tmpl_resp.json()["id"]

    # Create a policy
    policy_resp = await client.post(
        "/api/v5/chains/policies",
        json={
            "name": "Cost Cap",
            "policy_type": "cost_limit",
            "rules_json": json.dumps({"max_cost_usd": 100.0}),
            "enforcement": "block",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert policy_resp.status_code == 201
    policy_id = policy_resp.json()["id"]

    # Evaluate
    resp = await client.post(
        f"/api/v5/chains/{template_id}/evaluate-policies",
        json={"policy_ids": [policy_id]},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["chain_template_id"] == template_id
    assert "overall_passed" in data
    assert "policy_results" in data


@pytest.mark.asyncio
async def test_evaluate_policies_template_not_found(client, make_agent, db):
    _, token = await make_agent()
    resp = await client.post(
        f"/api/v5/chains/{_new_id()}/evaluate-policies",
        json={"policy_ids": [_new_id()]},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Phase 4: Settlement endpoints
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_settlement_report(client, make_agent, db):
    agent, token = await make_agent()
    tmpl, ex = await _seed_template_and_execution(db, agent.id)

    resp = await client.get(
        f"/api/v5/chain-executions/{ex.id}/settlement",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["chain_execution_id"] == ex.id
    assert "total_paid_usd" in data
    assert "payments" in data


@pytest.mark.asyncio
async def test_get_settlement_report_not_found(client, make_agent, db):
    _, token = await make_agent()
    resp = await client.get(
        f"/api/v5/chain-executions/{_new_id()}/settlement",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_get_cost_estimate(client, make_agent, db):
    agent, token = await make_agent()
    agent.a2a_endpoint = "http://test:9000"
    await db.commit()

    # Create template via API
    graph_json = _make_graph_json([agent.id])
    tmpl_resp = await client.post(
        "/api/v5/chain-templates",
        json={"name": "Cost Test", "graph_json": graph_json},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert tmpl_resp.status_code == 201
    template_id = tmpl_resp.json()["id"]

    resp = await client.get(
        f"/api/v5/chain-templates/{template_id}/cost-estimate",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["chain_template_id"] == template_id
    assert "estimated_total_usd" in data
    assert "agent_costs" in data


@pytest.mark.asyncio
async def test_get_cost_estimate_not_found(client, make_agent, db):
    _, token = await make_agent()
    resp = await client.get(
        f"/api/v5/chain-templates/{_new_id()}/cost-estimate",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 404
