"""Tests for Chain Registry v5 API routes (marketplace/api/v5_chains.py).

Covers CRUD, fork, execute, analytics, provenance, policy, and settlement
endpoints with both happy-path and error-path scenarios.
"""

from __future__ import annotations

import json
from decimal import Decimal
from unittest.mock import AsyncMock, patch

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


def _auth(jwt: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {jwt}"}


# ═══════════════════════════════════════════════════════════════════
# POST /chain-templates — create
# ═══════════════════════════════════════════════════════════════════


async def test_create_chain_template_201(client):
    agent_id, jwt = await _create_agent()
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
        headers=_auth(jwt),
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["name"] == "My Chain"
    assert body["author_id"] == agent_id
    assert body["status"] == "active"
    assert "test" in body["tags"]


async def test_create_chain_template_invalid_graph(client):
    agent_id, jwt = await _create_agent()

    resp = await client.post(
        f"{V5}/chain-templates",
        json={
            "name": "Bad Chain",
            "graph_json": "not-json",
        },
        headers=_auth(jwt),
    )
    assert resp.status_code == 400


async def test_create_chain_template_no_auth(client):
    resp = await client.post(
        f"{V5}/chain-templates",
        json={"name": "X", "graph_json": "{}"},
    )
    assert resp.status_code in (401, 403)


async def test_create_chain_template_missing_agent_id_in_graph(client):
    agent_id, jwt = await _create_agent()

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
        headers=_auth(jwt),
    )
    assert resp.status_code == 400


async def test_create_chain_template_raw_endpoint_rejected(client):
    agent_id, jwt = await _create_agent()

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
        headers=_auth(jwt),
    )
    assert resp.status_code == 400


# ═══════════════════════════════════════════════════════════════════
# GET /chain-templates — list
# ═══════════════════════════════════════════════════════════════════


async def test_list_chain_templates_empty(client):
    _, jwt = await _create_agent()
    resp = await client.get(f"{V5}/chain-templates", headers=_auth(jwt))
    assert resp.status_code == 200
    body = resp.json()
    assert body["templates"] == []
    assert body["total"] == 0


async def test_list_chain_templates_with_data(client):
    agent_id, jwt = await _create_agent()
    graph = _simple_graph(agent_id)
    await _create_chain_template(agent_id, graph, name="T1")
    await _create_chain_template(agent_id, graph, name="T2")

    resp = await client.get(f"{V5}/chain-templates", headers=_auth(jwt))
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 2
    assert len(body["templates"]) == 2


async def test_list_chain_templates_filter_category(client):
    agent_id, jwt = await _create_agent()
    graph = _simple_graph(agent_id)
    await _create_chain_template(agent_id, graph, name="C1", category="finance")
    await _create_chain_template(agent_id, graph, name="C2", category="general")

    resp = await client.get(
        f"{V5}/chain-templates",
        params={"category": "finance"},
        headers=_auth(jwt),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 1
    assert body["templates"][0]["category"] == "finance"


async def test_list_chain_templates_pagination(client):
    agent_id, jwt = await _create_agent()
    graph = _simple_graph(agent_id)
    for i in range(5):
        await _create_chain_template(agent_id, graph, name=f"P{i}")

    resp = await client.get(
        f"{V5}/chain-templates",
        params={"limit": 2, "offset": 0},
        headers=_auth(jwt),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 5
    assert len(body["templates"]) == 2


# ═══════════════════════════════════════════════════════════════════
# GET /chain-templates/{id} — get single
# ═══════════════════════════════════════════════════════════════════


async def test_get_chain_template_200(client):
    agent_id, jwt = await _create_agent()
    graph = _simple_graph(agent_id)
    tmpl = await _create_chain_template(agent_id, graph, name="Fetch Me")

    resp = await client.get(
        f"{V5}/chain-templates/{tmpl.id}", headers=_auth(jwt),
    )
    assert resp.status_code == 200
    assert resp.json()["name"] == "Fetch Me"


async def test_get_chain_template_404(client):
    _, jwt = await _create_agent()
    resp = await client.get(
        f"{V5}/chain-templates/nonexistent-id", headers=_auth(jwt),
    )
    assert resp.status_code == 404


# ═══════════════════════════════════════════════════════════════════
# DELETE /chain-templates/{id} — archive
# ═══════════════════════════════════════════════════════════════════


async def test_archive_chain_template_by_author(client):
    agent_id, jwt = await _create_agent()
    graph = _simple_graph(agent_id)
    tmpl = await _create_chain_template(agent_id, graph)

    resp = await client.delete(
        f"{V5}/chain-templates/{tmpl.id}", headers=_auth(jwt),
    )
    assert resp.status_code == 200
    assert resp.json()["detail"] == "Chain template archived"


async def test_archive_chain_template_403_non_author(client):
    author_id, _ = await _create_agent(name="author-arch")
    other_id, other_jwt = await _create_agent(name="other-arch")

    graph = _simple_graph(author_id)
    tmpl = await _create_chain_template(author_id, graph)

    resp = await client.delete(
        f"{V5}/chain-templates/{tmpl.id}", headers=_auth(other_jwt),
    )
    assert resp.status_code == 403


async def test_archive_chain_template_404(client):
    _, jwt = await _create_agent()
    resp = await client.delete(
        f"{V5}/chain-templates/no-such-id", headers=_auth(jwt),
    )
    assert resp.status_code == 404


# ═══════════════════════════════════════════════════════════════════
# POST /chain-templates/{id}/fork
# ═══════════════════════════════════════════════════════════════════


async def test_fork_chain_template_201(client):
    agent_id, jwt = await _create_agent()
    graph = _simple_graph(agent_id)
    tmpl = await _create_chain_template(agent_id, graph, name="Original")

    resp = await client.post(
        f"{V5}/chain-templates/{tmpl.id}/fork",
        json={"name": "My Fork"},
        headers=_auth(jwt),
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["name"] == "My Fork"
    assert body["forked_from_id"] == tmpl.id


async def test_fork_chain_template_default_name(client):
    agent_id, jwt = await _create_agent()
    graph = _simple_graph(agent_id)
    tmpl = await _create_chain_template(agent_id, graph, name="Source")

    resp = await client.post(
        f"{V5}/chain-templates/{tmpl.id}/fork",
        json={},
        headers=_auth(jwt),
    )
    assert resp.status_code == 201
    assert resp.json()["name"].startswith("Fork of ")


async def test_fork_chain_template_invalid_source(client):
    _, jwt = await _create_agent()
    resp = await client.post(
        f"{V5}/chain-templates/nonexistent/fork",
        json={},
        headers=_auth(jwt),
    )
    assert resp.status_code == 400


# ═══════════════════════════════════════════════════════════════════
# POST /chain-templates/{id}/execute
# ═══════════════════════════════════════════════════════════════════


async def test_execute_chain_202(client):
    agent_id, jwt = await _create_agent()
    graph = _simple_graph(agent_id)
    tmpl = await _create_chain_template(agent_id, graph)

    resp = await client.post(
        f"{V5}/chain-templates/{tmpl.id}/execute",
        json={"input_data": {"query": "test"}},
        headers=_auth(jwt),
    )
    assert resp.status_code == 202
    body = resp.json()
    assert body["chain_template_id"] == tmpl.id
    assert body["status"] == "pending"


async def test_execute_chain_with_idempotency_key(client):
    agent_id, jwt = await _create_agent()
    graph = _simple_graph(agent_id)
    tmpl = await _create_chain_template(agent_id, graph)

    payload = {"input_data": {}, "idempotency_key": "test-idem-key-123"}
    resp1 = await client.post(
        f"{V5}/chain-templates/{tmpl.id}/execute",
        json=payload,
        headers=_auth(jwt),
    )
    assert resp1.status_code == 202
    exec_id_1 = resp1.json()["id"]

    # Same idempotency key returns same execution
    resp2 = await client.post(
        f"{V5}/chain-templates/{tmpl.id}/execute",
        json=payload,
        headers=_auth(jwt),
    )
    assert resp2.status_code == 202
    assert resp2.json()["id"] == exec_id_1


async def test_execute_chain_nonexistent_template(client):
    _, jwt = await _create_agent()
    resp = await client.post(
        f"{V5}/chain-templates/bad-id/execute",
        json={},
        headers=_auth(jwt),
    )
    assert resp.status_code == 400


# ═══════════════════════════════════════════════════════════════════
# GET /chain-executions/{id} — get execution
# ═══════════════════════════════════════════════════════════════════


async def test_get_chain_execution_200(client):
    agent_id, jwt = await _create_agent()
    graph = _simple_graph(agent_id)
    tmpl = await _create_chain_template(agent_id, graph)
    ex = await _create_chain_execution(tmpl.id, agent_id)

    resp = await client.get(
        f"{V5}/chain-executions/{ex.id}", headers=_auth(jwt),
    )
    assert resp.status_code == 200
    assert resp.json()["id"] == ex.id


async def test_get_chain_execution_404(client):
    _, jwt = await _create_agent()
    resp = await client.get(
        f"{V5}/chain-executions/no-such-id", headers=_auth(jwt),
    )
    assert resp.status_code == 404


async def test_get_chain_execution_403_wrong_agent(client):
    agent_id, _ = await _create_agent(name="exec-owner")
    other_id, other_jwt = await _create_agent(name="exec-other")

    graph = _simple_graph(agent_id)
    tmpl = await _create_chain_template(agent_id, graph)
    ex = await _create_chain_execution(tmpl.id, agent_id)

    resp = await client.get(
        f"{V5}/chain-executions/{ex.id}", headers=_auth(other_jwt),
    )
    assert resp.status_code == 403


# ═══════════════════════════════════════════════════════════════════
# GET /chain-executions/{id}/provenance
# ═══════════════════════════════════════════════════════════════════


async def test_get_chain_provenance_by_initiator(client):
    agent_id, jwt = await _create_agent()
    graph = _simple_graph(agent_id)
    tmpl = await _create_chain_template(agent_id, graph)
    ex = await _create_chain_execution(tmpl.id, agent_id, status="completed")

    resp = await client.get(
        f"{V5}/chain-executions/{ex.id}/provenance",
        headers=_auth(jwt),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["chain_execution_id"] == ex.id


async def test_get_chain_provenance_403_forbidden(client):
    author_id, _ = await _create_agent(name="prov-author")
    initiator_id, _ = await _create_agent(name="prov-initiator")
    outsider_id, outsider_jwt = await _create_agent(name="prov-outsider")

    graph = _simple_graph(author_id)
    tmpl = await _create_chain_template(author_id, graph)
    ex = await _create_chain_execution(tmpl.id, initiator_id)

    resp = await client.get(
        f"{V5}/chain-executions/{ex.id}/provenance",
        headers=_auth(outsider_jwt),
    )
    assert resp.status_code == 403


async def test_get_chain_provenance_404(client):
    _, jwt = await _create_agent()
    resp = await client.get(
        f"{V5}/chain-executions/nope/provenance",
        headers=_auth(jwt),
    )
    assert resp.status_code == 404


# ═══════════════════════════════════════════════════════════════════
# GET /chain-templates/{id}/executions
# ═══════════════════════════════════════════════════════════════════


async def test_list_chain_executions_by_author(client):
    agent_id, jwt = await _create_agent()
    graph = _simple_graph(agent_id)
    tmpl = await _create_chain_template(agent_id, graph)
    await _create_chain_execution(tmpl.id, agent_id, status="completed")
    await _create_chain_execution(tmpl.id, agent_id, status="pending")

    resp = await client.get(
        f"{V5}/chain-templates/{tmpl.id}/executions",
        headers=_auth(jwt),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 2


async def test_list_chain_executions_non_author_sees_own_only(client):
    author_id, author_jwt = await _create_agent(name="list-exec-author")
    other_id, other_jwt = await _create_agent(name="list-exec-other")

    graph = _simple_graph(author_id)
    tmpl = await _create_chain_template(author_id, graph)
    await _create_chain_execution(tmpl.id, author_id)
    await _create_chain_execution(tmpl.id, other_id)

    resp = await client.get(
        f"{V5}/chain-templates/{tmpl.id}/executions",
        headers=_auth(other_jwt),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 1


async def test_list_chain_executions_404_template(client):
    _, jwt = await _create_agent()
    resp = await client.get(
        f"{V5}/chain-templates/missing/executions",
        headers=_auth(jwt),
    )
    assert resp.status_code == 404


async def test_list_chain_executions_filter_status(client):
    agent_id, jwt = await _create_agent()
    graph = _simple_graph(agent_id)
    tmpl = await _create_chain_template(agent_id, graph)
    await _create_chain_execution(tmpl.id, agent_id, status="completed")
    await _create_chain_execution(tmpl.id, agent_id, status="failed")

    resp = await client.get(
        f"{V5}/chain-templates/{tmpl.id}/executions",
        params={"status": "completed"},
        headers=_auth(jwt),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 1


# ═══════════════════════════════════════════════════════════════════
# POST /chains/compose
# ═══════════════════════════════════════════════════════════════════


async def test_compose_chain_no_capabilities_400(client):
    _, jwt = await _create_agent()
    resp = await client.post(
        f"{V5}/chains/compose",
        json={"task_description": "do absolutely nothing unique xyz123"},
        headers=_auth(jwt),
    )
    assert resp.status_code == 400


async def test_compose_chain_success(client):
    agent_id, jwt = await _create_agent(
        name="data-agent",
        capabilities=json.dumps(["data", "search", "web-search"]),
    )

    resp = await client.post(
        f"{V5}/chains/compose",
        json={"task_description": "search and fetch data from the web"},
        headers=_auth(jwt),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert "capabilities" in body
    assert "graph_json" in body


# ═══════════════════════════════════════════════════════════════════
# POST /chains/suggest-agents
# ═══════════════════════════════════════════════════════════════════


async def test_suggest_agents_empty(client):
    _, jwt = await _create_agent()
    resp = await client.post(
        f"{V5}/chains/suggest-agents",
        json={"capability": "nonexistent_cap"},
        headers=_auth(jwt),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 0
    assert body["agents"] == []


async def test_suggest_agents_with_results(client):
    agent_id, jwt = await _create_agent(
        name="analyst",
        capabilities=json.dumps(["analysis", "market-analysis"]),
    )
    resp = await client.post(
        f"{V5}/chains/suggest-agents",
        json={"capability": "analysis", "max_results": 5},
        headers=_auth(jwt),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] >= 1


# ═══════════════════════════════════════════════════════════════════
# POST /chains/{id}/validate
# ═══════════════════════════════════════════════════════════════════


async def test_validate_chain_200(client):
    agent_id, jwt = await _create_agent()
    graph = _simple_graph(agent_id)
    tmpl = await _create_chain_template(agent_id, graph)

    resp = await client.post(
        f"{V5}/chains/{tmpl.id}/validate", headers=_auth(jwt),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["template_id"] == tmpl.id


async def test_validate_chain_404(client):
    _, jwt = await _create_agent()
    resp = await client.post(
        f"{V5}/chains/nonexistent-id/validate", headers=_auth(jwt),
    )
    assert resp.status_code == 404


# ═══════════════════════════════════════════════════════════════════
# GET /chain-templates/{id}/analytics
# ═══════════════════════════════════════════════════════════════════


async def test_get_chain_analytics_200(client):
    agent_id, jwt = await _create_agent()
    graph = _simple_graph(agent_id)
    tmpl = await _create_chain_template(agent_id, graph)

    resp = await client.get(
        f"{V5}/chain-templates/{tmpl.id}/analytics",
        headers=_auth(jwt),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["template_id"] == tmpl.id
    assert body["execution_count"] == 0


async def test_get_chain_analytics_404(client):
    _, jwt = await _create_agent()
    resp = await client.get(
        f"{V5}/chain-templates/no-such/analytics",
        headers=_auth(jwt),
    )
    assert resp.status_code == 404


# ═══════════════════════════════════════════════════════════════════
# GET /chains/popular
# ═══════════════════════════════════════════════════════════════════


async def test_get_popular_chains(client):
    agent_id, jwt = await _create_agent()
    graph = _simple_graph(agent_id)
    await _create_chain_template(agent_id, graph, name="Popular1")

    resp = await client.get(
        f"{V5}/chains/popular", headers=_auth(jwt),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert "chains" in body
    assert isinstance(body["chains"], list)


async def test_get_popular_chains_filter_category(client):
    agent_id, jwt = await _create_agent()
    graph = _simple_graph(agent_id)
    await _create_chain_template(agent_id, graph, category="finance")
    await _create_chain_template(agent_id, graph, category="health")

    resp = await client.get(
        f"{V5}/chains/popular",
        params={"category": "finance"},
        headers=_auth(jwt),
    )
    assert resp.status_code == 200
    body = resp.json()
    for chain in body["chains"]:
        assert chain["category"] == "finance"


# ═══════════════════════════════════════════════════════════════════
# GET /chains/agents/{id}/stats
# ═══════════════════════════════════════════════════════════════════


async def test_get_agent_chain_stats(client):
    agent_id, jwt = await _create_agent()
    resp = await client.get(
        f"{V5}/chains/agents/{agent_id}/stats",
        headers=_auth(jwt),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["agent_id"] == agent_id
    assert "chains_authored" in body
    assert "executions_initiated" in body


# ═══════════════════════════════════════════════════════════════════
# GET /chain-executions/{id}/provenance-entries
# ═══════════════════════════════════════════════════════════════════


async def test_get_provenance_entries_by_initiator(client):
    agent_id, jwt = await _create_agent()
    graph = _simple_graph(agent_id)
    tmpl = await _create_chain_template(agent_id, graph)
    ex = await _create_chain_execution(tmpl.id, agent_id)

    resp = await client.get(
        f"{V5}/chain-executions/{ex.id}/provenance-entries",
        headers=_auth(jwt),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert "entries" in body
    assert "total" in body


async def test_get_provenance_entries_403_outsider(client):
    author_id, _ = await _create_agent(name="pe-author")
    initiator_id, _ = await _create_agent(name="pe-initiator")
    outsider_id, outsider_jwt = await _create_agent(name="pe-outsider")

    graph = _simple_graph(author_id)
    tmpl = await _create_chain_template(author_id, graph)
    ex = await _create_chain_execution(tmpl.id, initiator_id)

    resp = await client.get(
        f"{V5}/chain-executions/{ex.id}/provenance-entries",
        headers=_auth(outsider_jwt),
    )
    assert resp.status_code == 403


async def test_get_provenance_entries_404(client):
    _, jwt = await _create_agent()
    resp = await client.get(
        f"{V5}/chain-executions/missing/provenance-entries",
        headers=_auth(jwt),
    )
    assert resp.status_code == 404


# ═══════════════════════════════════════════════════════════════════
# POST /chains/policies — create policy
# ═══════════════════════════════════════════════════════════════════


async def test_create_chain_policy_201(client):
    _, jwt = await _create_agent()
    resp = await client.post(
        f"{V5}/chains/policies",
        json={
            "name": "EU Jurisdiction",
            "policy_type": "jurisdiction",
            "rules_json": json.dumps({"allowed_jurisdictions": ["CH", "DE"]}),
            "enforcement": "block",
            "scope": "chain",
        },
        headers=_auth(jwt),
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["name"] == "EU Jurisdiction"
    assert body["policy_type"] == "jurisdiction"
    assert body["status"] == "active"


async def test_create_chain_policy_invalid_rules_json(client):
    _, jwt = await _create_agent()
    resp = await client.post(
        f"{V5}/chains/policies",
        json={
            "name": "Bad Rules",
            "policy_type": "cost_limit",
            "rules_json": "not-json{",
        },
        headers=_auth(jwt),
    )
    assert resp.status_code == 400


async def test_create_chain_policy_invalid_type(client):
    _, jwt = await _create_agent()
    resp = await client.post(
        f"{V5}/chains/policies",
        json={
            "name": "Invalid Type",
            "policy_type": "invalid_type",
            "rules_json": "{}",
        },
        headers=_auth(jwt),
    )
    assert resp.status_code == 400


# ═══════════════════════════════════════════════════════════════════
# GET /chains/policies — list policies
# ═══════════════════════════════════════════════════════════════════


async def test_list_chain_policies(client):
    _, jwt = await _create_agent()
    # Create two policies first
    for name in ("P1", "P2"):
        await client.post(
            f"{V5}/chains/policies",
            json={
                "name": name,
                "policy_type": "jurisdiction",
                "rules_json": json.dumps({"allowed_jurisdictions": ["US"]}),
            },
            headers=_auth(jwt),
        )

    resp = await client.get(f"{V5}/chains/policies", headers=_auth(jwt))
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 2


# ═══════════════════════════════════════════════════════════════════
# POST /chains/{id}/evaluate-policies
# ═══════════════════════════════════════════════════════════════════


async def test_evaluate_policies_200(client):
    agent_id, jwt = await _create_agent()
    graph = _simple_graph(agent_id)
    tmpl = await _create_chain_template(agent_id, graph)

    # Create a cost_limit policy
    pol_resp = await client.post(
        f"{V5}/chains/policies",
        json={
            "name": "Budget Limit",
            "policy_type": "cost_limit",
            "rules_json": json.dumps({"max_cost_usd": 100}),
            "enforcement": "block",
        },
        headers=_auth(jwt),
    )
    assert pol_resp.status_code == 201
    policy_id = pol_resp.json()["id"]

    resp = await client.post(
        f"{V5}/chains/{tmpl.id}/evaluate-policies",
        json={"policy_ids": [policy_id]},
        headers=_auth(jwt),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert "overall_passed" in body
    assert "policy_results" in body


async def test_evaluate_policies_404_template(client):
    _, jwt = await _create_agent()
    resp = await client.post(
        f"{V5}/chains/nonexistent/evaluate-policies",
        json={"policy_ids": ["some-id"]},
        headers=_auth(jwt),
    )
    assert resp.status_code == 404


async def test_evaluate_policies_403_non_author(client):
    author_id, _ = await _create_agent(name="eval-author")
    other_id, other_jwt = await _create_agent(name="eval-other")

    graph = _simple_graph(author_id)
    tmpl = await _create_chain_template(author_id, graph)

    resp = await client.post(
        f"{V5}/chains/{tmpl.id}/evaluate-policies",
        json={"policy_ids": ["any"]},
        headers=_auth(other_jwt),
    )
    assert resp.status_code == 403


# ═══════════════════════════════════════════════════════════════════
# GET /chain-executions/{id}/settlement
# ═══════════════════════════════════════════════════════════════════


async def test_get_settlement_200(client):
    agent_id, jwt = await _create_agent()
    graph = _simple_graph(agent_id)
    tmpl = await _create_chain_template(agent_id, graph)
    ex = await _create_chain_execution(tmpl.id, agent_id, status="completed")

    resp = await client.get(
        f"{V5}/chain-executions/{ex.id}/settlement",
        headers=_auth(jwt),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["chain_execution_id"] == ex.id


async def test_get_settlement_404(client):
    _, jwt = await _create_agent()
    resp = await client.get(
        f"{V5}/chain-executions/missing-id/settlement",
        headers=_auth(jwt),
    )
    assert resp.status_code == 404


async def test_get_settlement_403_wrong_agent(client):
    agent_id, _ = await _create_agent(name="settle-owner")
    other_id, other_jwt = await _create_agent(name="settle-other")

    graph = _simple_graph(agent_id)
    tmpl = await _create_chain_template(agent_id, graph)
    ex = await _create_chain_execution(tmpl.id, agent_id)

    resp = await client.get(
        f"{V5}/chain-executions/{ex.id}/settlement",
        headers=_auth(other_jwt),
    )
    assert resp.status_code == 403


# ═══════════════════════════════════════════════════════════════════
# GET /chain-templates/{id}/cost-estimate
# ═══════════════════════════════════════════════════════════════════


async def test_get_cost_estimate_200(client):
    agent_id, jwt = await _create_agent()
    graph = _simple_graph(agent_id)
    tmpl = await _create_chain_template(agent_id, graph)

    resp = await client.get(
        f"{V5}/chain-templates/{tmpl.id}/cost-estimate",
        headers=_auth(jwt),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["chain_template_id"] == tmpl.id
    assert "estimated_total_usd" in body


async def test_get_cost_estimate_404(client):
    _, jwt = await _create_agent()
    resp = await client.get(
        f"{V5}/chain-templates/missing/cost-estimate",
        headers=_auth(jwt),
    )
    assert resp.status_code == 404
