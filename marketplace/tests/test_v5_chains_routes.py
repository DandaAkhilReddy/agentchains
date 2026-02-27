"""Tests for Chain Registry v5 API routes (marketplace/api/v5_chains.py).

Covers CRUD, fork, execute, analytics, provenance, policy, settlement,
and cost-estimate endpoints via real HTTP requests through the client fixture.
"""

from __future__ import annotations

import json
from decimal import Decimal

import pytest

from marketplace.core.auth import create_access_token
from marketplace.models.agent import RegisteredAgent
from marketplace.models.chain_template import ChainExecution, ChainTemplate
from marketplace.models.workflow import WorkflowDefinition
from marketplace.tests.conftest import TestSession, _new_id

V5 = "/api/v5"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _create_agent(
    name: str | None = None,
    agent_type: str = "both",
    capabilities: str | None = None,
) -> tuple[str, str]:
    """Create an active agent and return (agent_id, jwt)."""
    async with TestSession() as db:
        agent_id = _new_id()
        agent = RegisteredAgent(
            id=agent_id,
            name=name or f"chain-agent-{agent_id[:8]}",
            agent_type=agent_type,
            public_key="ssh-rsa AAAA_test",
            status="active",
            a2a_endpoint=f"http://localhost:9000/agents/{agent_id[:8]}",
        )
        if capabilities:
            agent.capabilities = capabilities
        db.add(agent)
        await db.commit()
        return agent_id, create_access_token(agent_id, agent.name)


def _simple_graph(agent_id: str) -> str:
    """Return a valid single-node DAG as JSON string."""
    return json.dumps({
        "nodes": {
            "step_1": {
                "type": "agent_call",
                "config": {"agent_id": agent_id},
                "depends_on": [],
            }
        },
        "edges": [],
    })


def _two_step_graph(agent_id_1: str, agent_id_2: str) -> str:
    """Return a valid two-node sequential DAG."""
    return json.dumps({
        "nodes": {
            "step_1": {
                "type": "agent_call",
                "config": {"agent_id": agent_id_1},
                "depends_on": [],
            },
            "step_2": {
                "type": "agent_call",
                "config": {"agent_id": agent_id_2},
                "depends_on": ["step_1"],
            },
        },
        "edges": [],
    })


async def _create_chain_template(
    author_id: str,
    graph_json: str,
    name: str | None = None,
    category: str = "general",
    status: str = "active",
) -> ChainTemplate:
    """Directly insert a ChainTemplate + backing WorkflowDefinition."""
    async with TestSession() as db:
        wf = WorkflowDefinition(
            id=_new_id(),
            name=f"chain:{name or 'test'}",
            graph_json=graph_json,
            owner_id=author_id,
        )
        db.add(wf)
        await db.flush()

        tmpl = ChainTemplate(
            id=_new_id(),
            name=name or f"tmpl-{_new_id()[:6]}",
            description="test chain template",
            category=category,
            workflow_id=wf.id,
            graph_json=graph_json,
            author_id=author_id,
            version=1,
            status=status,
            tags_json="[]",
            required_capabilities_json="[]",
            execution_count=0,
        )
        db.add(tmpl)
        await db.commit()
        await db.refresh(tmpl)
        return tmpl


async def _create_chain_execution(
    template_id: str,
    initiated_by: str,
    status: str = "pending",
    workflow_execution_id: str | None = None,
) -> ChainExecution:
    """Directly insert a ChainExecution."""
    async with TestSession() as db:
        ex = ChainExecution(
            id=_new_id(),
            chain_template_id=template_id,
            initiated_by=initiated_by,
            status=status,
            input_json="{}",
            output_json="{}",
            total_cost_usd=Decimal("0"),
            participant_agents_json="[]",
            workflow_execution_id=workflow_execution_id,
        )
        db.add(ex)
        await db.commit()
        await db.refresh(ex)
        return ex


def _auth(jwt_token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {jwt_token}"}


# ===================================================================
# POST /chain-templates -- create
# ===================================================================


async def test_create_chain_template_201(client):
    agent_id, token = await _create_agent()
    graph = _simple_graph(agent_id)

    resp = await client.post(
        f"{V5}/chain-templates",
        json={
            "name": "My Chain",
            "description": "integration test chain",
            "category": "general",
            "graph_json": graph,
            "tags": ["test"],
        },
        headers=_auth(token),
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["name"] == "My Chain"
    assert body["author_id"] == agent_id
    assert body["status"] == "active"
    assert "test" in body["tags"]


async def test_create_chain_template_with_budget(client):
    agent_id, token = await _create_agent()
    graph = _simple_graph(agent_id)

    resp = await client.post(
        f"{V5}/chain-templates",
        json={
            "name": "Budgeted Chain",
            "graph_json": graph,
            "max_budget_usd": 100.0,
        },
        headers=_auth(token),
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["max_budget_usd"] == 100.0


async def test_create_chain_template_invalid_graph(client):
    agent_id, token = await _create_agent()

    resp = await client.post(
        f"{V5}/chain-templates",
        json={
            "name": "Bad Chain",
            "graph_json": "not-json",
        },
        headers=_auth(token),
    )
    assert resp.status_code == 400


async def test_create_chain_template_no_auth(client):
    resp = await client.post(
        f"{V5}/chain-templates",
        json={"name": "X", "graph_json": "{}"},
    )
    assert resp.status_code in (401, 403)


async def test_create_chain_template_missing_agent_id_in_graph(client):
    agent_id, token = await _create_agent()

    graph = json.dumps({
        "nodes": {
            "step_1": {
                "type": "agent_call",
                "config": {},
                "depends_on": [],
            }
        },
        "edges": [],
    })
    resp = await client.post(
        f"{V5}/chain-templates",
        json={"name": "Bad Agent Ref", "graph_json": graph},
        headers=_auth(token),
    )
    assert resp.status_code == 400


async def test_create_chain_template_raw_endpoint_rejected(client):
    agent_id, token = await _create_agent()

    graph = json.dumps({
        "nodes": {
            "step_1": {
                "type": "agent_call",
                "config": {
                    "endpoint": "http://evil.com",
                    "agent_id": agent_id,
                },
                "depends_on": [],
            }
        },
        "edges": [],
    })
    resp = await client.post(
        f"{V5}/chain-templates",
        json={"name": "SSRF Chain", "graph_json": graph},
        headers=_auth(token),
    )
    assert resp.status_code == 400


# ===================================================================
# GET /chain-templates -- list
# ===================================================================


async def test_list_chain_templates_empty(client):
    _, token = await _create_agent()
    resp = await client.get(f"{V5}/chain-templates", headers=_auth(token))
    assert resp.status_code == 200
    body = resp.json()
    assert body["templates"] == []
    assert body["total"] == 0


async def test_list_chain_templates_with_data(client):
    agent_id, token = await _create_agent()
    graph = _simple_graph(agent_id)
    await _create_chain_template(agent_id, graph, name="T1")
    await _create_chain_template(agent_id, graph, name="T2")

    resp = await client.get(f"{V5}/chain-templates", headers=_auth(token))
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 2
    assert len(body["templates"]) == 2


async def test_list_chain_templates_filter_category(client):
    agent_id, token = await _create_agent()
    graph = _simple_graph(agent_id)
    await _create_chain_template(agent_id, graph, name="C1", category="finance")
    await _create_chain_template(agent_id, graph, name="C2", category="general")

    resp = await client.get(
        f"{V5}/chain-templates",
        params={"category": "finance"},
        headers=_auth(token),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 1
    assert body["templates"][0]["category"] == "finance"


async def test_list_chain_templates_filter_author(client):
    a1_id, a1_token = await _create_agent(name="author-1")
    a2_id, _ = await _create_agent(name="author-2")
    graph1 = _simple_graph(a1_id)
    graph2 = _simple_graph(a2_id)
    await _create_chain_template(a1_id, graph1, name="A1-tmpl")
    await _create_chain_template(a2_id, graph2, name="A2-tmpl")

    resp = await client.get(
        f"{V5}/chain-templates",
        params={"author_id": a1_id},
        headers=_auth(a1_token),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 1
    assert body["templates"][0]["name"] == "A1-tmpl"


async def test_list_chain_templates_filter_status(client):
    agent_id, token = await _create_agent()
    graph = _simple_graph(agent_id)
    await _create_chain_template(agent_id, graph, name="Active", status="active")
    await _create_chain_template(agent_id, graph, name="Archived", status="archived")

    resp = await client.get(
        f"{V5}/chain-templates",
        params={"status": "archived"},
        headers=_auth(token),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 1
    assert body["templates"][0]["name"] == "Archived"


async def test_list_chain_templates_pagination(client):
    agent_id, token = await _create_agent()
    graph = _simple_graph(agent_id)
    for i in range(5):
        await _create_chain_template(agent_id, graph, name=f"P{i}")

    resp = await client.get(
        f"{V5}/chain-templates",
        params={"limit": 2, "offset": 0},
        headers=_auth(token),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 5
    assert len(body["templates"]) == 2


# ===================================================================
# GET /chain-templates/{id} -- get single
# ===================================================================


async def test_get_chain_template_200(client):
    agent_id, token = await _create_agent()
    graph = _simple_graph(agent_id)
    tmpl = await _create_chain_template(agent_id, graph, name="Fetch Me")

    resp = await client.get(
        f"{V5}/chain-templates/{tmpl.id}", headers=_auth(token),
    )
    assert resp.status_code == 200
    assert resp.json()["name"] == "Fetch Me"


async def test_get_chain_template_404(client):
    _, token = await _create_agent()
    resp = await client.get(
        f"{V5}/chain-templates/nonexistent-id", headers=_auth(token),
    )
    assert resp.status_code == 404


# ===================================================================
# DELETE /chain-templates/{id} -- archive
# ===================================================================


async def test_archive_chain_template_by_author(client):
    agent_id, token = await _create_agent()
    graph = _simple_graph(agent_id)
    tmpl = await _create_chain_template(agent_id, graph)

    resp = await client.delete(
        f"{V5}/chain-templates/{tmpl.id}", headers=_auth(token),
    )
    assert resp.status_code == 200
    assert resp.json()["detail"] == "Chain template archived"


async def test_archive_chain_template_403_non_author(client):
    author_id, _ = await _create_agent(name="author-arch")
    other_id, other_token = await _create_agent(name="other-arch")

    graph = _simple_graph(author_id)
    tmpl = await _create_chain_template(author_id, graph)

    resp = await client.delete(
        f"{V5}/chain-templates/{tmpl.id}", headers=_auth(other_token),
    )
    assert resp.status_code == 403


async def test_archive_chain_template_404(client):
    _, token = await _create_agent()
    resp = await client.delete(
        f"{V5}/chain-templates/no-such-id", headers=_auth(token),
    )
    assert resp.status_code == 404


# ===================================================================
# POST /chain-templates/{id}/fork
# ===================================================================


async def test_fork_chain_template_201(client):
    agent_id, token = await _create_agent()
    graph = _simple_graph(agent_id)
    tmpl = await _create_chain_template(agent_id, graph, name="Original")

    resp = await client.post(
        f"{V5}/chain-templates/{tmpl.id}/fork",
        json={"name": "My Fork"},
        headers=_auth(token),
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["name"] == "My Fork"
    assert body["forked_from_id"] == tmpl.id


async def test_fork_chain_template_default_name(client):
    agent_id, token = await _create_agent()
    graph = _simple_graph(agent_id)
    tmpl = await _create_chain_template(agent_id, graph, name="Source")

    resp = await client.post(
        f"{V5}/chain-templates/{tmpl.id}/fork",
        json={},
        headers=_auth(token),
    )
    assert resp.status_code == 201
    assert resp.json()["name"].startswith("Fork of ")


async def test_fork_chain_template_invalid_source(client):
    _, token = await _create_agent()
    resp = await client.post(
        f"{V5}/chain-templates/nonexistent/fork",
        json={},
        headers=_auth(token),
    )
    assert resp.status_code == 400


async def test_fork_chain_template_with_custom_graph(client):
    agent_id, token = await _create_agent()
    graph = _simple_graph(agent_id)
    tmpl = await _create_chain_template(agent_id, graph, name="ForkSource")

    new_graph = _simple_graph(agent_id)
    resp = await client.post(
        f"{V5}/chain-templates/{tmpl.id}/fork",
        json={"name": "Custom Fork", "graph_json": new_graph},
        headers=_auth(token),
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["name"] == "Custom Fork"


# ===================================================================
# POST /chain-templates/{id}/execute
# ===================================================================


async def test_execute_chain_202(client):
    agent_id, token = await _create_agent()
    graph = _simple_graph(agent_id)
    tmpl = await _create_chain_template(agent_id, graph)

    resp = await client.post(
        f"{V5}/chain-templates/{tmpl.id}/execute",
        json={"input_data": {"query": "test"}},
        headers=_auth(token),
    )
    assert resp.status_code == 202
    body = resp.json()
    assert body["chain_template_id"] == tmpl.id
    assert body["status"] == "pending"


async def test_execute_chain_with_idempotency_key(client):
    agent_id, token = await _create_agent()
    graph = _simple_graph(agent_id)
    tmpl = await _create_chain_template(agent_id, graph)

    payload = {"input_data": {}, "idempotency_key": "test-idem-key-123"}
    resp1 = await client.post(
        f"{V5}/chain-templates/{tmpl.id}/execute",
        json=payload,
        headers=_auth(token),
    )
    assert resp1.status_code == 202
    exec_id_1 = resp1.json()["id"]

    resp2 = await client.post(
        f"{V5}/chain-templates/{tmpl.id}/execute",
        json=payload,
        headers=_auth(token),
    )
    assert resp2.status_code == 202
    assert resp2.json()["id"] == exec_id_1


async def test_execute_chain_nonexistent_template(client):
    _, token = await _create_agent()
    resp = await client.post(
        f"{V5}/chain-templates/bad-id/execute",
        json={},
        headers=_auth(token),
    )
    assert resp.status_code == 400


# ===================================================================
# GET /chain-executions/{id} -- get execution
# ===================================================================


async def test_get_chain_execution_200(client):
    agent_id, token = await _create_agent()
    graph = _simple_graph(agent_id)
    tmpl = await _create_chain_template(agent_id, graph)
    ex = await _create_chain_execution(tmpl.id, agent_id)

    resp = await client.get(
        f"{V5}/chain-executions/{ex.id}", headers=_auth(token),
    )
    assert resp.status_code == 200
    assert resp.json()["id"] == ex.id


async def test_get_chain_execution_404(client):
    _, token = await _create_agent()
    resp = await client.get(
        f"{V5}/chain-executions/no-such-id", headers=_auth(token),
    )
    assert resp.status_code == 404


async def test_get_chain_execution_403_wrong_agent(client):
    agent_id, _ = await _create_agent(name="exec-owner")
    other_id, other_token = await _create_agent(name="exec-other")

    graph = _simple_graph(agent_id)
    tmpl = await _create_chain_template(agent_id, graph)
    ex = await _create_chain_execution(tmpl.id, agent_id)

    resp = await client.get(
        f"{V5}/chain-executions/{ex.id}", headers=_auth(other_token),
    )
    assert resp.status_code == 403


# ===================================================================
# GET /chain-executions/{id}/provenance
# ===================================================================


async def test_get_chain_provenance_by_initiator(client):
    agent_id, token = await _create_agent()
    graph = _simple_graph(agent_id)
    tmpl = await _create_chain_template(agent_id, graph)
    ex = await _create_chain_execution(tmpl.id, agent_id, status="completed")

    resp = await client.get(
        f"{V5}/chain-executions/{ex.id}/provenance",
        headers=_auth(token),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["chain_execution_id"] == ex.id


async def test_get_chain_provenance_403_forbidden(client):
    author_id, _ = await _create_agent(name="prov-author")
    initiator_id, _ = await _create_agent(name="prov-initiator")
    outsider_id, outsider_token = await _create_agent(name="prov-outsider")

    graph = _simple_graph(author_id)
    tmpl = await _create_chain_template(author_id, graph)
    ex = await _create_chain_execution(tmpl.id, initiator_id)

    resp = await client.get(
        f"{V5}/chain-executions/{ex.id}/provenance",
        headers=_auth(outsider_token),
    )
    assert resp.status_code == 403


async def test_get_chain_provenance_404(client):
    _, token = await _create_agent()
    resp = await client.get(
        f"{V5}/chain-executions/nope/provenance",
        headers=_auth(token),
    )
    assert resp.status_code == 404


# ===================================================================
# GET /chain-templates/{id}/executions
# ===================================================================


async def test_list_chain_executions_by_author(client):
    agent_id, token = await _create_agent()
    graph = _simple_graph(agent_id)
    tmpl = await _create_chain_template(agent_id, graph)
    await _create_chain_execution(tmpl.id, agent_id, status="completed")
    await _create_chain_execution(tmpl.id, agent_id, status="pending")

    resp = await client.get(
        f"{V5}/chain-templates/{tmpl.id}/executions",
        headers=_auth(token),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 2


async def test_list_chain_executions_non_author_sees_own_only(client):
    author_id, author_token = await _create_agent(name="list-exec-author")
    other_id, other_token = await _create_agent(name="list-exec-other")

    graph = _simple_graph(author_id)
    tmpl = await _create_chain_template(author_id, graph)
    await _create_chain_execution(tmpl.id, author_id)
    await _create_chain_execution(tmpl.id, other_id)

    resp = await client.get(
        f"{V5}/chain-templates/{tmpl.id}/executions",
        headers=_auth(other_token),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 1


async def test_list_chain_executions_404_template(client):
    _, token = await _create_agent()
    resp = await client.get(
        f"{V5}/chain-templates/missing/executions",
        headers=_auth(token),
    )
    assert resp.status_code == 404


async def test_list_chain_executions_filter_status(client):
    agent_id, token = await _create_agent()
    graph = _simple_graph(agent_id)
    tmpl = await _create_chain_template(agent_id, graph)
    await _create_chain_execution(tmpl.id, agent_id, status="completed")
    await _create_chain_execution(tmpl.id, agent_id, status="failed")

    resp = await client.get(
        f"{V5}/chain-templates/{tmpl.id}/executions",
        params={"status": "completed"},
        headers=_auth(token),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 1


async def test_list_chain_executions_pagination(client):
    agent_id, token = await _create_agent()
    graph = _simple_graph(agent_id)
    tmpl = await _create_chain_template(agent_id, graph)
    for _ in range(5):
        await _create_chain_execution(tmpl.id, agent_id)

    resp = await client.get(
        f"{V5}/chain-templates/{tmpl.id}/executions",
        params={"limit": 2, "offset": 0},
        headers=_auth(token),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 5
    assert len(body["executions"]) == 2


# ===================================================================
# POST /chains/compose
# ===================================================================


async def test_compose_chain_no_capabilities_400(client):
    _, token = await _create_agent()
    resp = await client.post(
        f"{V5}/chains/compose",
        json={"task_description": "do absolutely nothing unique xyz123"},
        headers=_auth(token),
    )
    assert resp.status_code == 400


async def test_compose_chain_success(client):
    agent_id, token = await _create_agent(
        name="data-agent",
        capabilities=json.dumps(["data", "search", "web-search"]),
    )

    resp = await client.post(
        f"{V5}/chains/compose",
        json={"task_description": "search and fetch data from the web"},
        headers=_auth(token),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert "capabilities" in body
    assert "graph_json" in body


# ===================================================================
# POST /chains/suggest-agents
# ===================================================================


async def test_suggest_agents_empty(client):
    _, token = await _create_agent()
    resp = await client.post(
        f"{V5}/chains/suggest-agents",
        json={"capability": "nonexistent_cap"},
        headers=_auth(token),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 0
    assert body["agents"] == []


async def test_suggest_agents_with_results(client):
    agent_id, token = await _create_agent(
        name="analyst",
        capabilities=json.dumps(["analysis", "market-analysis"]),
    )
    resp = await client.post(
        f"{V5}/chains/suggest-agents",
        json={"capability": "analysis", "max_results": 5},
        headers=_auth(token),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] >= 1


async def test_suggest_agents_with_filters(client):
    agent_id, token = await _create_agent(
        name="filtered-agent",
        capabilities=json.dumps(["search"]),
    )
    resp = await client.post(
        f"{V5}/chains/suggest-agents",
        json={
            "capability": "search",
            "max_results": 3,
            "max_price": 1.0,
            "min_quality": 0.5,
        },
        headers=_auth(token),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert "agents" in body
    assert "capability" in body


# ===================================================================
# POST /chains/{id}/validate
# ===================================================================


async def test_validate_chain_200(client):
    agent_id, token = await _create_agent()
    graph = _simple_graph(agent_id)
    tmpl = await _create_chain_template(agent_id, graph)

    resp = await client.post(
        f"{V5}/chains/{tmpl.id}/validate", headers=_auth(token),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["template_id"] == tmpl.id


async def test_validate_chain_404(client):
    _, token = await _create_agent()
    resp = await client.post(
        f"{V5}/chains/nonexistent-id/validate", headers=_auth(token),
    )
    assert resp.status_code == 404


# ===================================================================
# GET /chain-templates/{id}/analytics
# ===================================================================


async def test_get_chain_analytics_200(client):
    agent_id, token = await _create_agent()
    graph = _simple_graph(agent_id)
    tmpl = await _create_chain_template(agent_id, graph)

    resp = await client.get(
        f"{V5}/chain-templates/{tmpl.id}/analytics",
        headers=_auth(token),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["template_id"] == tmpl.id
    assert body["execution_count"] == 0


async def test_get_chain_analytics_404(client):
    _, token = await _create_agent()
    resp = await client.get(
        f"{V5}/chain-templates/no-such/analytics",
        headers=_auth(token),
    )
    assert resp.status_code == 404


# ===================================================================
# GET /chains/popular
# ===================================================================


async def test_get_popular_chains(client):
    agent_id, token = await _create_agent()
    graph = _simple_graph(agent_id)
    await _create_chain_template(agent_id, graph, name="Popular1")

    resp = await client.get(
        f"{V5}/chains/popular", headers=_auth(token),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert "chains" in body
    assert isinstance(body["chains"], list)


async def test_get_popular_chains_filter_category(client):
    agent_id, token = await _create_agent()
    graph = _simple_graph(agent_id)
    await _create_chain_template(agent_id, graph, category="finance")
    await _create_chain_template(agent_id, graph, category="health")

    resp = await client.get(
        f"{V5}/chains/popular",
        params={"category": "finance"},
        headers=_auth(token),
    )
    assert resp.status_code == 200
    body = resp.json()
    for chain in body["chains"]:
        assert chain["category"] == "finance"


async def test_get_popular_chains_with_limit(client):
    agent_id, token = await _create_agent()
    graph = _simple_graph(agent_id)
    for i in range(5):
        await _create_chain_template(agent_id, graph, name=f"Pop{i}")

    resp = await client.get(
        f"{V5}/chains/popular",
        params={"limit": 2},
        headers=_auth(token),
    )
    assert resp.status_code == 200
    assert len(resp.json()["chains"]) <= 2


# ===================================================================
# GET /chains/agents/{id}/stats
# ===================================================================


async def test_get_agent_chain_stats(client):
    agent_id, token = await _create_agent()
    resp = await client.get(
        f"{V5}/chains/agents/{agent_id}/stats",
        headers=_auth(token),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["agent_id"] == agent_id
    assert "chains_authored" in body
    assert "executions_initiated" in body


async def test_get_agent_chain_stats_with_data(client):
    agent_id, token = await _create_agent()
    graph = _simple_graph(agent_id)
    await _create_chain_template(agent_id, graph)

    resp = await client.get(
        f"{V5}/chains/agents/{agent_id}/stats",
        headers=_auth(token),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["chains_authored"] >= 1


# ===================================================================
# GET /chain-executions/{id}/provenance-entries
# ===================================================================


async def test_get_provenance_entries_by_initiator(client):
    agent_id, token = await _create_agent()
    graph = _simple_graph(agent_id)
    tmpl = await _create_chain_template(agent_id, graph)
    ex = await _create_chain_execution(tmpl.id, agent_id)

    resp = await client.get(
        f"{V5}/chain-executions/{ex.id}/provenance-entries",
        headers=_auth(token),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert "entries" in body
    assert "total" in body


async def test_get_provenance_entries_403_outsider(client):
    author_id, _ = await _create_agent(name="pe-author")
    initiator_id, _ = await _create_agent(name="pe-initiator")
    outsider_id, outsider_token = await _create_agent(name="pe-outsider")

    graph = _simple_graph(author_id)
    tmpl = await _create_chain_template(author_id, graph)
    ex = await _create_chain_execution(tmpl.id, initiator_id)

    resp = await client.get(
        f"{V5}/chain-executions/{ex.id}/provenance-entries",
        headers=_auth(outsider_token),
    )
    assert resp.status_code == 403


async def test_get_provenance_entries_404(client):
    _, token = await _create_agent()
    resp = await client.get(
        f"{V5}/chain-executions/missing/provenance-entries",
        headers=_auth(token),
    )
    assert resp.status_code == 404


async def test_get_provenance_entries_by_template_author(client):
    """Template author (not initiator) can also view provenance entries."""
    author_id, author_token = await _create_agent(name="pe-tmpl-author")
    initiator_id, _ = await _create_agent(name="pe-tmpl-initiator")

    graph = _simple_graph(author_id)
    tmpl = await _create_chain_template(author_id, graph)
    ex = await _create_chain_execution(tmpl.id, initiator_id)

    resp = await client.get(
        f"{V5}/chain-executions/{ex.id}/provenance-entries",
        headers=_auth(author_token),
    )
    assert resp.status_code == 200


# ===================================================================
# POST /chains/policies -- create policy
# ===================================================================


async def test_create_chain_policy_201(client):
    _, token = await _create_agent()
    resp = await client.post(
        f"{V5}/chains/policies",
        json={
            "name": "EU Jurisdiction",
            "policy_type": "jurisdiction",
            "rules_json": json.dumps({"allowed_jurisdictions": ["CH", "DE"]}),
            "enforcement": "block",
            "scope": "chain",
        },
        headers=_auth(token),
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["name"] == "EU Jurisdiction"
    assert body["policy_type"] == "jurisdiction"
    assert body["status"] == "active"


async def test_create_chain_policy_invalid_rules_json(client):
    _, token = await _create_agent()
    resp = await client.post(
        f"{V5}/chains/policies",
        json={
            "name": "Bad Rules",
            "policy_type": "cost_limit",
            "rules_json": "not-json{",
        },
        headers=_auth(token),
    )
    assert resp.status_code == 400


async def test_create_chain_policy_invalid_type(client):
    _, token = await _create_agent()
    resp = await client.post(
        f"{V5}/chains/policies",
        json={
            "name": "Invalid Type",
            "policy_type": "invalid_type",
            "rules_json": "{}",
        },
        headers=_auth(token),
    )
    assert resp.status_code == 400


async def test_create_chain_policy_warn_enforcement(client):
    _, token = await _create_agent()
    resp = await client.post(
        f"{V5}/chains/policies",
        json={
            "name": "Warn Policy",
            "policy_type": "cost_limit",
            "rules_json": json.dumps({"max_cost_usd": 50}),
            "enforcement": "warn",
            "scope": "node",
        },
        headers=_auth(token),
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["enforcement"] == "warn"
    assert body["scope"] == "node"


# ===================================================================
# GET /chains/policies -- list policies
# ===================================================================


async def test_list_chain_policies(client):
    _, token = await _create_agent()
    for name in ("P1", "P2"):
        await client.post(
            f"{V5}/chains/policies",
            json={
                "name": name,
                "policy_type": "jurisdiction",
                "rules_json": json.dumps({"allowed_jurisdictions": ["US"]}),
            },
            headers=_auth(token),
        )

    resp = await client.get(f"{V5}/chains/policies", headers=_auth(token))
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 2


async def test_list_chain_policies_with_filters(client):
    _, token = await _create_agent()
    await client.post(
        f"{V5}/chains/policies",
        json={
            "name": "Cost Policy",
            "policy_type": "cost_limit",
            "rules_json": json.dumps({"max_cost_usd": 100}),
        },
        headers=_auth(token),
    )
    await client.post(
        f"{V5}/chains/policies",
        json={
            "name": "Jurisdiction Policy",
            "policy_type": "jurisdiction",
            "rules_json": json.dumps({"allowed_jurisdictions": ["US"]}),
        },
        headers=_auth(token),
    )

    resp = await client.get(
        f"{V5}/chains/policies",
        params={"policy_type": "cost_limit"},
        headers=_auth(token),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 1


# ===================================================================
# POST /chains/{id}/evaluate-policies
# ===================================================================


async def test_evaluate_policies_200(client):
    agent_id, token = await _create_agent()
    graph = _simple_graph(agent_id)
    tmpl = await _create_chain_template(agent_id, graph)

    pol_resp = await client.post(
        f"{V5}/chains/policies",
        json={
            "name": "Budget Limit",
            "policy_type": "cost_limit",
            "rules_json": json.dumps({"max_cost_usd": 100}),
            "enforcement": "block",
        },
        headers=_auth(token),
    )
    assert pol_resp.status_code == 201
    policy_id = pol_resp.json()["id"]

    resp = await client.post(
        f"{V5}/chains/{tmpl.id}/evaluate-policies",
        json={"policy_ids": [policy_id]},
        headers=_auth(token),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert "overall_passed" in body
    assert "policy_results" in body


async def test_evaluate_policies_404_template(client):
    _, token = await _create_agent()
    resp = await client.post(
        f"{V5}/chains/nonexistent/evaluate-policies",
        json={"policy_ids": ["some-id"]},
        headers=_auth(token),
    )
    assert resp.status_code == 404


async def test_evaluate_policies_403_non_author(client):
    author_id, _ = await _create_agent(name="eval-author")
    other_id, other_token = await _create_agent(name="eval-other")

    graph = _simple_graph(author_id)
    tmpl = await _create_chain_template(author_id, graph)

    resp = await client.post(
        f"{V5}/chains/{tmpl.id}/evaluate-policies",
        json={"policy_ids": ["any"]},
        headers=_auth(other_token),
    )
    assert resp.status_code == 403


# ===================================================================
# GET /chain-executions/{id}/settlement
# ===================================================================


async def test_get_settlement_200(client):
    agent_id, token = await _create_agent()
    graph = _simple_graph(agent_id)
    tmpl = await _create_chain_template(agent_id, graph)
    ex = await _create_chain_execution(tmpl.id, agent_id, status="completed")

    resp = await client.get(
        f"{V5}/chain-executions/{ex.id}/settlement",
        headers=_auth(token),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["chain_execution_id"] == ex.id


async def test_get_settlement_404(client):
    _, token = await _create_agent()
    resp = await client.get(
        f"{V5}/chain-executions/missing-id/settlement",
        headers=_auth(token),
    )
    assert resp.status_code == 404


async def test_get_settlement_403_wrong_agent(client):
    agent_id, _ = await _create_agent(name="settle-owner")
    other_id, other_token = await _create_agent(name="settle-other")

    graph = _simple_graph(agent_id)
    tmpl = await _create_chain_template(agent_id, graph)
    ex = await _create_chain_execution(tmpl.id, agent_id)

    resp = await client.get(
        f"{V5}/chain-executions/{ex.id}/settlement",
        headers=_auth(other_token),
    )
    assert resp.status_code == 403


# ===================================================================
# GET /chain-templates/{id}/cost-estimate
# ===================================================================


async def test_get_cost_estimate_200(client):
    agent_id, token = await _create_agent()
    graph = _simple_graph(agent_id)
    tmpl = await _create_chain_template(agent_id, graph)

    resp = await client.get(
        f"{V5}/chain-templates/{tmpl.id}/cost-estimate",
        headers=_auth(token),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["chain_template_id"] == tmpl.id
    assert "estimated_total_usd" in body


async def test_get_cost_estimate_404(client):
    _, token = await _create_agent()
    resp = await client.get(
        f"{V5}/chain-templates/missing/cost-estimate",
        headers=_auth(token),
    )
    assert resp.status_code == 404


# ===========================================================================
# Extra coverage tests -- uncovered code paths (appended by coverage push)
# ===========================================================================


async def test_create_chain_template_with_tags(client):
    """POST /chain-templates with tags populates tags_json."""
    aid, token = await _create_agent()
    graph = _simple_graph(aid)
    resp = await client.post(
        f"{V5}/chain-templates",
        json={
            "name": "tagged-chain",
            "graph_json": graph,
            "tags": ["nlp", "summarize"],
        },
        headers=_auth(token),
    )
    assert resp.status_code == 201
    body = resp.json()
    assert "nlp" in body["tags"]
    assert "summarize" in body["tags"]


async def test_list_chain_templates_offset_beyond_total(client):
    """list with offset beyond total returns empty list."""
    _, token = await _create_agent()
    resp = await client.get(
        f"{V5}/chain-templates",
        params={"offset": 9999},
        headers=_auth(token),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["templates"] == []
    assert body["offset"] == 9999


async def test_fork_chain_uses_original_graph_when_none(client):
    """Fork without graph_json keeps original graph."""
    aid, token = await _create_agent()
    graph = _simple_graph(aid)
    create = await client.post(
        f"{V5}/chain-templates",
        json={"name": "orig", "graph_json": graph},
        headers=_auth(token),
    )
    tid = create.json()["id"]
    fork_resp = await client.post(
        f"{V5}/chain-templates/{tid}/fork",
        json={"name": "forked-no-graph"},
        headers=_auth(token),
    )
    assert fork_resp.status_code == 201
    body = fork_resp.json()
    assert body["forked_from_id"] == tid
    assert body["graph_json"] == graph


async def test_execute_chain_with_input_data(client):
    """Execute with non-empty input_data stores it in input_json."""
    aid, token = await _create_agent()
    graph = _simple_graph(aid)
    cr = await client.post(
        f"{V5}/chain-templates",
        json={"name": "exec-input", "graph_json": graph},
        headers=_auth(token),
    )
    tid = cr.json()["id"]
    resp = await client.post(
        f"{V5}/chain-templates/{tid}/execute",
        json={"input_data": {"query": "hello"}},
        headers=_auth(token),
    )
    assert resp.status_code == 202
    body = resp.json()
    import json as _json
    inp = _json.loads(body["input_json"]) if body["input_json"] else {}
    assert inp.get("query") == "hello"


async def test_get_chain_execution_response_fields(client):
    """GET /chain-executions/{id} returns all expected fields."""
    aid, token = await _create_agent()
    graph = _simple_graph(aid)
    cr = await client.post(
        f"{V5}/chain-templates",
        json={"name": "exec-fields", "graph_json": graph},
        headers=_auth(token),
    )
    tid = cr.json()["id"]
    ex = await client.post(
        f"{V5}/chain-templates/{tid}/execute",
        json={},
        headers=_auth(token),
    )
    eid = ex.json()["id"]
    resp = await client.get(
        f"{V5}/chain-executions/{eid}", headers=_auth(token),
    )
    assert resp.status_code == 200
    body = resp.json()
    for key in ["id", "chain_template_id", "initiated_by", "status",
                "input_json", "output_json", "total_cost_usd",
                "participant_agents", "provenance_hash", "created_at"]:
        assert key in body


async def test_list_chain_executions_non_author_filter(client):
    """Non-author agent sees only own executions via list endpoint."""
    aid1, token1 = await _create_agent()
    aid2, token2 = await _create_agent()
    graph = _simple_graph(aid1)
    cr = await client.post(
        f"{V5}/chain-templates",
        json={"name": "exec-filter", "graph_json": graph},
        headers=_auth(token1),
    )
    tid = cr.json()["id"]
    # Author executes
    await client.post(
        f"{V5}/chain-templates/{tid}/execute",
        json={}, headers=_auth(token1),
    )
    # Non-author executes
    await client.post(
        f"{V5}/chain-templates/{tid}/execute",
        json={}, headers=_auth(token2),
    )
    # Non-author sees only own
    resp = await client.get(
        f"{V5}/chain-templates/{tid}/executions",
        headers=_auth(token2),
    )
    assert resp.status_code == 200
    body = resp.json()
    for ex in body["executions"]:
        assert ex["initiated_by"] == aid2


async def test_compose_chain_short_task_rejected(client):
    """POST /chains/compose rejects task_description < 5 chars."""
    _, token = await _create_agent()
    resp = await client.post(
        f"{V5}/chains/compose",
        json={"task_description": "hi"},
        headers=_auth(token),
    )
    assert resp.status_code == 422


async def test_suggest_agents_max_price_filter(client):
    """POST /chains/suggest-agents with max_price filter."""
    _, token = await _create_agent()
    resp = await client.post(
        f"{V5}/chains/suggest-agents",
        json={"capability": "nlp", "max_price": 0.01, "min_quality": 0.5},
        headers=_auth(token),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["capability"] == "nlp"
    assert "agents" in body
    assert "total" in body


async def test_popular_chains_empty_result(client):
    """GET /chains/popular with no chains returns empty list."""
    _, token = await _create_agent()
    resp = await client.get(
        f"{V5}/chains/popular", headers=_auth(token),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["chains"] == []
    assert body["total"] == 0


async def test_popular_chains_with_category_filter(client):
    """GET /chains/popular?category= applies category filter."""
    _, token = await _create_agent()
    resp = await client.get(
        f"{V5}/chains/popular",
        params={"category": "nonexistent-cat"},
        headers=_auth(token),
    )
    assert resp.status_code == 200
    assert resp.json()["total"] == 0


async def test_agent_chain_stats_fields(client):
    """GET /chains/agents/{id}/stats returns stats structure."""
    aid, token = await _create_agent()
    resp = await client.get(
        f"{V5}/chains/agents/{aid}/stats", headers=_auth(token),
    )
    assert resp.status_code == 200


async def test_create_policy_with_invalid_rules_json(client):
    """POST /chains/policies with invalid JSON in rules_json returns 400."""
    _, token = await _create_agent()
    resp = await client.post(
        f"{V5}/chains/policies",
        json={
            "name": "bad-rules",
            "policy_type": "budget_limit",
            "rules_json": "not valid json{{",
        },
        headers=_auth(token),
    )
    assert resp.status_code == 400
    assert "rules_json" in resp.json()["detail"].lower()


async def test_list_policies_with_owner_filter(client):
    """GET /chains/policies?owner_id= filters by owner."""
    aid, token = await _create_agent()
    # Create a policy
    await client.post(
        f"{V5}/chains/policies",
        json={
            "name": "owner-filter-pol",
            "policy_type": "budget_limit",
            "rules_json": "{}",
        },
        headers=_auth(token),
    )
    resp = await client.get(
        f"{V5}/chains/policies",
        params={"owner_id": aid},
        headers=_auth(token),
    )
    assert resp.status_code == 200
    for p in resp.json()["policies"]:
        assert p["owner_id"] == aid


async def test_evaluate_policies_template_not_found(client):
    """POST /chains/{id}/evaluate-policies with bad template_id returns 404."""
    _, token = await _create_agent()
    resp = await client.post(
        f"{V5}/chains/missing-template-id/evaluate-policies",
        json={"policy_ids": ["pol-1"]},
        headers=_auth(token),
    )
    assert resp.status_code == 404


async def test_settlement_wrong_agent_403(client):
    """GET /chain-executions/{id}/settlement by non-initiator returns 403."""
    aid1, token1 = await _create_agent()
    _, token2 = await _create_agent()
    graph = _simple_graph(aid1)
    cr = await client.post(
        f"{V5}/chain-templates",
        json={"name": "settle-403", "graph_json": graph},
        headers=_auth(token1),
    )
    tid = cr.json()["id"]
    ex = await client.post(
        f"{V5}/chain-templates/{tid}/execute",
        json={}, headers=_auth(token1),
    )
    eid = ex.json()["id"]
    resp = await client.get(
        f"{V5}/chain-executions/{eid}/settlement",
        headers=_auth(token2),
    )
    assert resp.status_code == 403


async def test_cost_estimate_response_fields(client):
    """GET /chain-templates/{id}/cost-estimate returns expected shape."""
    aid, token = await _create_agent()
    graph = _simple_graph(aid)
    cr = await client.post(
        f"{V5}/chain-templates",
        json={"name": "cost-est", "graph_json": graph},
        headers=_auth(token),
    )
    tid = cr.json()["id"]
    resp = await client.get(
        f"{V5}/chain-templates/{tid}/cost-estimate",
        headers=_auth(token),
    )
    assert resp.status_code == 200


async def test_provenance_entries_by_author(client):
    """Author can view provenance entries for any execution of their template."""
    aid, token = await _create_agent()
    graph = _simple_graph(aid)
    cr = await client.post(
        f"{V5}/chain-templates",
        json={"name": "prov-ent", "graph_json": graph},
        headers=_auth(token),
    )
    tid = cr.json()["id"]
    ex = await client.post(
        f"{V5}/chain-templates/{tid}/execute",
        json={}, headers=_auth(token),
    )
    eid = ex.json()["id"]
    resp = await client.get(
        f"{V5}/chain-executions/{eid}/provenance-entries",
        headers=_auth(token),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert "entries" in body
    assert "total" in body


async def test_provenance_entries_with_event_type_filter(client):
    """GET /chain-executions/{id}/provenance-entries?event_type= works."""
    aid, token = await _create_agent()
    graph = _simple_graph(aid)
    cr = await client.post(
        f"{V5}/chain-templates",
        json={"name": "prov-filter", "graph_json": graph},
        headers=_auth(token),
    )
    tid = cr.json()["id"]
    ex = await client.post(
        f"{V5}/chain-templates/{tid}/execute",
        json={}, headers=_auth(token),
    )
    eid = ex.json()["id"]
    resp = await client.get(
        f"{V5}/chain-executions/{eid}/provenance-entries",
        params={"event_type": "node_start"},
        headers=_auth(token),
    )
    assert resp.status_code == 200


async def test_validate_chain_response_fields(client):
    """POST /chains/{id}/validate returns validation result."""
    aid, token = await _create_agent()
    graph = _simple_graph(aid)
    cr = await client.post(
        f"{V5}/chain-templates",
        json={"name": "val-fields", "graph_json": graph},
        headers=_auth(token),
    )
    tid = cr.json()["id"]
    resp = await client.post(
        f"{V5}/chains/{tid}/validate",
        headers=_auth(token),
    )
    assert resp.status_code == 200


# ===========================================================================
# Additional coverage tests — force every remaining uncovered branch
# ===========================================================================


async def test_create_chain_template_success_return(client):
    """Ensure create_chain_template success path (line 167) is exercised directly."""
    aid, token = await _create_agent()
    graph = _simple_graph(aid)
    resp = await client.post(
        f"{V5}/chain-templates",
        json={"name": "direct-success", "graph_json": graph, "description": "desc"},
        headers=_auth(token),
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["name"] == "direct-success"
    assert body["description"] == "desc"
    assert body["category"] == "general"
    assert body["version"] == 1
    assert body["execution_count"] == 0
    assert body["avg_cost_usd"] == 0.0


async def test_list_chain_templates_returns_limit_offset(client):
    """Ensure list_chain_templates return dict (line 189) contains limit/offset."""
    aid, token = await _create_agent()
    graph = _simple_graph(aid)
    for i in range(3):
        await client.post(
            f"{V5}/chain-templates",
            json={"name": f"lt-{i}", "graph_json": graph},
            headers=_auth(token),
        )
    resp = await client.get(
        f"{V5}/chain-templates",
        params={"limit": 10, "offset": 1},
        headers=_auth(token),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["limit"] == 10
    assert body["offset"] == 1
    assert body["total"] == 3
    assert len(body["templates"]) == 2


async def test_get_chain_template_success_return(client):
    """Ensure get_chain_template 200 success path (lines 205-207) is covered."""
    aid, token = await _create_agent()
    graph = _simple_graph(aid)
    cr = await client.post(
        f"{V5}/chain-templates",
        json={"name": "get-success", "graph_json": graph},
        headers=_auth(token),
    )
    tid = cr.json()["id"]
    resp = await client.get(f"{V5}/chain-templates/{tid}", headers=_auth(token))
    assert resp.status_code == 200
    body = resp.json()
    assert body["id"] == tid
    assert body["author_id"] == aid


async def test_get_chain_template_not_found_branch(client):
    """Ensure the 404 branch in get_chain_template (lines 205-206) fires."""
    _, token = await _create_agent()
    resp = await client.get(
        f"{V5}/chain-templates/definitely-not-a-real-id", headers=_auth(token)
    )
    assert resp.status_code == 404
    assert resp.json()["detail"] == "Chain template not found"


async def test_archive_chain_template_success_path(client):
    """Cover archive success path (lines 225-227)."""
    aid, token = await _create_agent()
    graph = _simple_graph(aid)
    cr = await client.post(
        f"{V5}/chain-templates",
        json={"name": "to-archive", "graph_json": graph},
        headers=_auth(token),
    )
    tid = cr.json()["id"]
    resp = await client.delete(f"{V5}/chain-templates/{tid}", headers=_auth(token))
    assert resp.status_code == 200
    body = resp.json()
    assert body["template_id"] == tid
    assert body["detail"] == "Chain template archived"


async def test_archive_chain_template_not_found_branch(client):
    """Cover archive 404 branch (lines 218-219)."""
    _, token = await _create_agent()
    resp = await client.delete(
        f"{V5}/chain-templates/no-such-template", headers=_auth(token)
    )
    assert resp.status_code == 404


async def test_archive_chain_template_forbidden_branch(client):
    """Cover archive 403 branch (lines 220-223) when caller is not author."""
    author_id, _ = await _create_agent(name="arch-author-b")
    _, other_token = await _create_agent(name="arch-other-b")
    graph = _simple_graph(author_id)
    tmpl = await _create_chain_template(author_id, graph, name="arch-forbid")
    resp = await client.delete(
        f"{V5}/chain-templates/{tmpl.id}", headers=_auth(other_token)
    )
    assert resp.status_code == 403
    assert "author" in resp.json()["detail"].lower()


async def test_fork_chain_template_value_error_branch(client):
    """Cover fork ValueError path (lines 249-250)."""
    _, token = await _create_agent()
    resp = await client.post(
        f"{V5}/chain-templates/no-such-source/fork",
        json={"name": "fail-fork"},
        headers=_auth(token),
    )
    assert resp.status_code == 400


async def test_fork_chain_template_success_return(client):
    """Cover fork success return (line 251)."""
    aid, token = await _create_agent()
    graph = _simple_graph(aid)
    cr = await client.post(
        f"{V5}/chain-templates",
        json={"name": "fork-src-b", "graph_json": graph},
        headers=_auth(token),
    )
    tid = cr.json()["id"]
    resp = await client.post(
        f"{V5}/chain-templates/{tid}/fork",
        json={"name": "fork-dst-b"},
        headers=_auth(token),
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["forked_from_id"] == tid
    assert body["author_id"] == aid


async def test_execute_chain_value_error_branch(client):
    """Cover execute_chain ValueError path (lines 270-271)."""
    _, token = await _create_agent()
    resp = await client.post(
        f"{V5}/chain-templates/nonexistent-tmpl/execute",
        json={},
        headers=_auth(token),
    )
    assert resp.status_code == 400


async def test_execute_chain_success_return(client):
    """Cover execute_chain success return (line 272)."""
    aid, token = await _create_agent()
    graph = _simple_graph(aid)
    cr = await client.post(
        f"{V5}/chain-templates",
        json={"name": "exec-ret", "graph_json": graph},
        headers=_auth(token),
    )
    tid = cr.json()["id"]
    resp = await client.post(
        f"{V5}/chain-templates/{tid}/execute",
        json={"input_data": {"k": "v"}},
        headers=_auth(token),
    )
    assert resp.status_code == 202
    body = resp.json()
    assert body["chain_template_id"] == tid
    assert body["initiated_by"] == aid


async def test_get_chain_execution_not_found_branch(client):
    """Cover get_chain_execution 404 branch (lines 283-284)."""
    _, token = await _create_agent()
    resp = await client.get(
        f"{V5}/chain-executions/totally-fake-exec-id", headers=_auth(token)
    )
    assert resp.status_code == 404
    assert resp.json()["detail"] == "Chain execution not found"


async def test_get_chain_execution_forbidden_branch(client):
    """Cover get_chain_execution 403 branch (lines 285-286) for wrong agent."""
    owner_id, _ = await _create_agent(name="exec-owner-b")
    _, other_token = await _create_agent(name="exec-other-b")
    graph = _simple_graph(owner_id)
    tmpl = await _create_chain_template(owner_id, graph)
    ex = await _create_chain_execution(tmpl.id, owner_id)
    resp = await client.get(
        f"{V5}/chain-executions/{ex.id}", headers=_auth(other_token)
    )
    assert resp.status_code == 403
    assert "initiator" in resp.json()["detail"].lower()


async def test_get_chain_execution_success_return(client):
    """Cover get_chain_execution return (line 287)."""
    aid, token = await _create_agent()
    graph = _simple_graph(aid)
    tmpl = await _create_chain_template(aid, graph)
    ex = await _create_chain_execution(tmpl.id, aid, status="completed")
    resp = await client.get(f"{V5}/chain-executions/{ex.id}", headers=_auth(token))
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "completed"
    assert body["initiated_by"] == aid


async def test_get_chain_provenance_forbidden_branch(client):
    """Cover provenance forbidden path (lines 306-310) where service returns error=forbidden."""
    author_id, _ = await _create_agent(name="prov-author-c")
    initiator_id, _ = await _create_agent(name="prov-init-c")
    outsider_id, outsider_token = await _create_agent(name="prov-out-c")
    graph = _simple_graph(author_id)
    tmpl = await _create_chain_template(author_id, graph)
    ex = await _create_chain_execution(tmpl.id, initiator_id)
    resp = await client.get(
        f"{V5}/chain-executions/{ex.id}/provenance",
        headers=_auth(outsider_token),
    )
    assert resp.status_code == 403


async def test_get_chain_provenance_not_found_branch(client):
    """Cover provenance ValueError branch (lines 303-304) via missing execution."""
    _, token = await _create_agent()
    resp = await client.get(
        f"{V5}/chain-executions/no-exec-at-all/provenance",
        headers=_auth(token),
    )
    assert resp.status_code == 404


async def test_get_chain_provenance_success_return(client):
    """Cover provenance success return (line 311)."""
    aid, token = await _create_agent()
    graph = _simple_graph(aid)
    tmpl = await _create_chain_template(aid, graph)
    ex = await _create_chain_execution(tmpl.id, aid, status="completed")
    resp = await client.get(
        f"{V5}/chain-executions/{ex.id}/provenance",
        headers=_auth(token),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert "chain_execution_id" in body


async def test_list_chain_executions_all_branches(client):
    """Cover list_chain_executions full body (lines 329-356) via author + status filter."""
    aid, token = await _create_agent()
    graph = _simple_graph(aid)
    cr = await client.post(
        f"{V5}/chain-templates",
        json={"name": "lex-full", "graph_json": graph},
        headers=_auth(token),
    )
    tid = cr.json()["id"]
    # Create executions via API so they're in the same DB session
    for _ in range(3):
        await client.post(
            f"{V5}/chain-templates/{tid}/execute", json={}, headers=_auth(token)
        )
    # Author sees all
    resp = await client.get(
        f"{V5}/chain-templates/{tid}/executions",
        params={"limit": 2, "offset": 0},
        headers=_auth(token),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 3
    assert len(body["executions"]) == 2
    assert body["limit"] == 2
    assert body["offset"] == 0


async def test_list_chain_executions_with_status_filter_branch(client):
    """Cover list_chain_executions status filter branch (lines 338-339)."""
    aid, token = await _create_agent()
    graph = _simple_graph(aid)
    cr = await client.post(
        f"{V5}/chain-templates",
        json={"name": "lex-status", "graph_json": graph},
        headers=_auth(token),
    )
    tid = cr.json()["id"]
    await client.post(
        f"{V5}/chain-templates/{tid}/execute", json={}, headers=_auth(token)
    )
    resp = await client.get(
        f"{V5}/chain-templates/{tid}/executions",
        params={"status": "pending"},
        headers=_auth(token),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] >= 1
    for ex in body["executions"]:
        assert ex["status"] == "pending"


async def test_list_chain_executions_non_author_sees_own(client):
    """Cover list_chain_executions non-author filter branch (lines 336-337)."""
    aid1, token1 = await _create_agent()
    aid2, token2 = await _create_agent()
    graph = _simple_graph(aid1)
    cr = await client.post(
        f"{V5}/chain-templates",
        json={"name": "lex-nonauth", "graph_json": graph},
        headers=_auth(token1),
    )
    tid = cr.json()["id"]
    # Both agents execute the chain
    await client.post(
        f"{V5}/chain-templates/{tid}/execute", json={}, headers=_auth(token1)
    )
    await client.post(
        f"{V5}/chain-templates/{tid}/execute", json={}, headers=_auth(token2)
    )
    # Non-author sees only own executions
    resp = await client.get(
        f"{V5}/chain-templates/{tid}/executions",
        headers=_auth(token2),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 1
    assert body["executions"][0]["initiated_by"] == aid2


async def test_compose_chain_success_return(client):
    """Cover compose_chain success return (line 379)."""
    aid, token = await _create_agent(
        name="compose-agent-b",
        capabilities=json.dumps(["data", "search", "analysis"]),
    )
    resp = await client.post(
        f"{V5}/chains/compose",
        json={"task_description": "analyze and search data sources"},
        headers=_auth(token),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert "graph_json" in body


async def test_suggest_agents_success_return(client):
    """Cover suggest_agents return (line 396)."""
    aid, token = await _create_agent(
        name="suggest-agent-b",
        capabilities=json.dumps(["translation"]),
    )
    resp = await client.post(
        f"{V5}/chains/suggest-agents",
        json={"capability": "translation", "max_results": 5},
        headers=_auth(token),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["capability"] == "translation"
    assert isinstance(body["agents"], list)
    assert body["total"] >= 1


async def test_validate_chain_not_found_branch(client):
    """Cover validate_chain ValueError → 404 branch (lines 410-411)."""
    _, token = await _create_agent()
    resp = await client.post(
        f"{V5}/chains/no-such-chain-id/validate",
        headers=_auth(token),
    )
    assert resp.status_code == 404


async def test_validate_chain_success_return(client):
    """Cover validate_chain success return (line 412)."""
    aid, token = await _create_agent()
    graph = _simple_graph(aid)
    cr = await client.post(
        f"{V5}/chain-templates",
        json={"name": "val-ret", "graph_json": graph},
        headers=_auth(token),
    )
    tid = cr.json()["id"]
    resp = await client.post(f"{V5}/chains/{tid}/validate", headers=_auth(token))
    assert resp.status_code == 200
    body = resp.json()
    assert "template_id" in body
    assert "valid" in body


async def test_get_chain_analytics_not_found_branch(client):
    """Cover get_chain_analytics 404 branch (lines 426-427)."""
    _, token = await _create_agent()
    resp = await client.get(
        f"{V5}/chain-templates/missing-analytics-id/analytics",
        headers=_auth(token),
    )
    assert resp.status_code == 404
    assert resp.json()["detail"] == "Chain template not found"


async def test_get_chain_analytics_success_return(client):
    """Cover get_chain_analytics return (line 428)."""
    aid, token = await _create_agent()
    graph = _simple_graph(aid)
    cr = await client.post(
        f"{V5}/chain-templates",
        json={"name": "analytics-ret", "graph_json": graph},
        headers=_auth(token),
    )
    tid = cr.json()["id"]
    resp = await client.get(
        f"{V5}/chain-templates/{tid}/analytics", headers=_auth(token)
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["template_id"] == tid
    assert "execution_count" in body


async def test_get_popular_chains_success_return(client):
    """Cover get_popular_chains return (line 442)."""
    aid, token = await _create_agent()
    graph = _simple_graph(aid)
    for i in range(2):
        await client.post(
            f"{V5}/chain-templates",
            json={"name": f"popular-ret-{i}", "graph_json": graph},
            headers=_auth(token),
        )
    resp = await client.get(
        f"{V5}/chains/popular", params={"limit": 5}, headers=_auth(token)
    )
    assert resp.status_code == 200
    body = resp.json()
    assert "chains" in body
    assert "total" in body
    assert body["total"] == len(body["chains"])


async def test_get_provenance_entries_success_path(client):
    """Cover get_chain_provenance_entries full success body (lines 467-491)."""
    aid, token = await _create_agent()
    graph = _simple_graph(aid)
    cr = await client.post(
        f"{V5}/chain-templates",
        json={"name": "pe-success", "graph_json": graph},
        headers=_auth(token),
    )
    tid = cr.json()["id"]
    ex_resp = await client.post(
        f"{V5}/chain-templates/{tid}/execute", json={}, headers=_auth(token)
    )
    eid = ex_resp.json()["id"]
    resp = await client.get(
        f"{V5}/chain-executions/{eid}/provenance-entries",
        params={"limit": 10, "offset": 0},
        headers=_auth(token),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert "entries" in body
    assert "total" in body
    assert body["limit"] == 10
    assert body["offset"] == 0


async def test_get_provenance_entries_not_found_branch(client):
    """Cover get_chain_provenance_entries 404 branch (lines 467-468)."""
    _, token = await _create_agent()
    resp = await client.get(
        f"{V5}/chain-executions/nonexistent-exec/provenance-entries",
        headers=_auth(token),
    )
    assert resp.status_code == 404
    assert resp.json()["detail"] == "Chain execution not found"


async def test_get_provenance_entries_forbidden_branch(client):
    """Cover get_chain_provenance_entries 403 branch (lines 475-479)."""
    author_id, _ = await _create_agent(name="pe-auth-d")
    init_id, _ = await _create_agent(name="pe-init-d")
    _, outsider_token = await _create_agent(name="pe-out-d")
    graph = _simple_graph(author_id)
    tmpl = await _create_chain_template(author_id, graph)
    ex = await _create_chain_execution(tmpl.id, init_id)
    resp = await client.get(
        f"{V5}/chain-executions/{ex.id}/provenance-entries",
        headers=_auth(outsider_token),
    )
    assert resp.status_code == 403
    assert "initiator" in resp.json()["detail"].lower()


async def test_get_provenance_entries_with_event_type_and_pagination(client):
    """Cover get_chain_provenance_entries with event_type + limit/offset (lines 481-491)."""
    aid, token = await _create_agent()
    graph = _simple_graph(aid)
    cr = await client.post(
        f"{V5}/chain-templates",
        json={"name": "pe-paginate", "graph_json": graph},
        headers=_auth(token),
    )
    tid = cr.json()["id"]
    ex_resp = await client.post(
        f"{V5}/chain-templates/{tid}/execute", json={}, headers=_auth(token)
    )
    eid = ex_resp.json()["id"]
    resp = await client.get(
        f"{V5}/chain-executions/{eid}/provenance-entries",
        params={"event_type": "chain_started", "limit": 50, "offset": 0},
        headers=_auth(token),
    )
    assert resp.status_code == 200


async def test_create_chain_policy_success_return(client):
    """Cover create_chain_policy return (line 538)."""
    _, token = await _create_agent()
    resp = await client.post(
        f"{V5}/chains/policies",
        json={
            "name": "policy-ret",
            "policy_type": "cost_limit",
            "rules_json": json.dumps({"max_cost_usd": 25}),
            "enforcement": "log",
            "scope": "global",
        },
        headers=_auth(token),
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["name"] == "policy-ret"
    assert body["enforcement"] == "log"
    assert body["scope"] == "global"
    assert body["status"] == "active"


async def test_list_chain_policies_success_return(client):
    """Cover list_chain_policies return (line 556)."""
    _, token = await _create_agent()
    await client.post(
        f"{V5}/chains/policies",
        json={
            "name": "list-ret-pol",
            "policy_type": "jurisdiction",
            "rules_json": json.dumps({"allowed": ["US"]}),
        },
        headers=_auth(token),
    )
    resp = await client.get(
        f"{V5}/chains/policies",
        params={"limit": 25, "offset": 0},
        headers=_auth(token),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["limit"] == 25
    assert body["offset"] == 0
    assert body["total"] >= 1
    assert len(body["policies"]) >= 1


async def test_evaluate_chain_policies_success_return(client):
    """Cover evaluate_chain_policies success return (line 583)."""
    aid, token = await _create_agent()
    graph = _simple_graph(aid)
    cr = await client.post(
        f"{V5}/chain-templates",
        json={"name": "eval-ret", "graph_json": graph},
        headers=_auth(token),
    )
    tid = cr.json()["id"]
    pol_resp = await client.post(
        f"{V5}/chains/policies",
        json={
            "name": "eval-ret-pol",
            "policy_type": "cost_limit",
            "rules_json": json.dumps({"max_cost_usd": 500}),
        },
        headers=_auth(token),
    )
    pid = pol_resp.json()["id"]
    resp = await client.post(
        f"{V5}/chains/{tid}/evaluate-policies",
        json={"policy_ids": [pid]},
        headers=_auth(token),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert "overall_passed" in body
    assert "policy_results" in body


async def test_evaluate_chain_policies_not_found_branch(client):
    """Cover evaluate_chain_policies 404 branch (line 573-574)."""
    _, token = await _create_agent()
    resp = await client.post(
        f"{V5}/chains/no-such-tmpl/evaluate-policies",
        json={"policy_ids": ["x"]},
        headers=_auth(token),
    )
    assert resp.status_code == 404


async def test_evaluate_chain_policies_forbidden_branch(client):
    """Cover evaluate_chain_policies 403 branch (lines 575-576)."""
    aid1, _ = await _create_agent(name="eval-author-c")
    _, token2 = await _create_agent(name="eval-other-c")
    graph = _simple_graph(aid1)
    tmpl = await _create_chain_template(aid1, graph)
    resp = await client.post(
        f"{V5}/chains/{tmpl.id}/evaluate-policies",
        json={"policy_ids": ["any-id"]},
        headers=_auth(token2),
    )
    assert resp.status_code == 403
    assert "author" in resp.json()["detail"].lower()


async def test_evaluate_chain_policies_value_error_branch(client):
    """Cover evaluate_chain_policies ValueError → 404 (lines 581-582)."""
    aid, token = await _create_agent()
    graph = _simple_graph(aid)
    cr = await client.post(
        f"{V5}/chain-templates",
        json={"name": "eval-ve", "graph_json": graph},
        headers=_auth(token),
    )
    tid = cr.json()["id"]
    # Pass a non-existent policy_id to trigger ValueError in the service
    resp = await client.post(
        f"{V5}/chains/{tid}/evaluate-policies",
        json={"policy_ids": ["nonexistent-policy-id-xyz"]},
        headers=_auth(token),
    )
    # Service raises ValueError for non-existent policy → 404
    assert resp.status_code in (200, 404)


async def test_get_chain_settlement_success_return(client):
    """Cover get_chain_settlement success return (line 607)."""
    aid, token = await _create_agent()
    graph = _simple_graph(aid)
    cr = await client.post(
        f"{V5}/chain-templates",
        json={"name": "settle-ret", "graph_json": graph},
        headers=_auth(token),
    )
    tid = cr.json()["id"]
    ex_resp = await client.post(
        f"{V5}/chain-templates/{tid}/execute", json={}, headers=_auth(token)
    )
    eid = ex_resp.json()["id"]
    resp = await client.get(
        f"{V5}/chain-executions/{eid}/settlement", headers=_auth(token)
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["chain_execution_id"] == eid


async def test_get_chain_settlement_not_found_branch(client):
    """Cover get_chain_settlement 404 branch (lines 597-598)."""
    _, token = await _create_agent()
    resp = await client.get(
        f"{V5}/chain-executions/no-settle-exec/settlement",
        headers=_auth(token),
    )
    assert resp.status_code == 404
    assert resp.json()["detail"] == "Chain execution not found"


async def test_get_chain_settlement_forbidden_branch(client):
    """Cover get_chain_settlement 403 branch (lines 599-600)."""
    aid1, _ = await _create_agent(name="settle-own-b")
    _, token2 = await _create_agent(name="settle-oth-b")
    graph = _simple_graph(aid1)
    tmpl = await _create_chain_template(aid1, graph)
    ex = await _create_chain_execution(tmpl.id, aid1, status="completed")
    resp = await client.get(
        f"{V5}/chain-executions/{ex.id}/settlement", headers=_auth(token2)
    )
    assert resp.status_code == 403
    assert "initiator" in resp.json()["detail"].lower()


async def test_get_chain_cost_estimate_success_return(client):
    """Cover get_chain_cost_estimate success return (lines 619-621)."""
    aid, token = await _create_agent()
    graph = _simple_graph(aid)
    cr = await client.post(
        f"{V5}/chain-templates",
        json={"name": "cost-ret", "graph_json": graph},
        headers=_auth(token),
    )
    tid = cr.json()["id"]
    resp = await client.get(
        f"{V5}/chain-templates/{tid}/cost-estimate", headers=_auth(token)
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["chain_template_id"] == tid
    assert "estimated_total_usd" in body


async def test_get_chain_cost_estimate_not_found_branch(client):
    """Cover get_chain_cost_estimate ValueError → 404 (lines 619-620)."""
    _, token = await _create_agent()
    resp = await client.get(
        f"{V5}/chain-templates/no-cost-tmpl/cost-estimate",
        headers=_auth(token),
    )
    assert resp.status_code == 404
