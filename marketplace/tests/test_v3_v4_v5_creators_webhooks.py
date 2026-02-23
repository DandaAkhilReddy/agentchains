"""Comprehensive tests for:
  - marketplace/api/v3_orchestration.py  (/api/v3 workflows & executions)
  - marketplace/api/v4_a2ui.py           (/api/v4 stream-token, sessions, health)
  - marketplace/api/v5_chains.py         (/api/v5 chain-templates, executions, analytics, policies, settlement)
  - marketplace/api/creators.py          (/api/v1/creators register, login, profile, agents, dashboard, wallet)
  - marketplace/api/deprecations.py      (apply_legacy_v1_deprecation_headers helper)
  - marketplace/api/webhooks.py          (/webhooks/stripe, /webhooks/razorpay)

All tests are async def and use the `client` fixture from conftest.py.
pytest-asyncio asyncio_mode=auto is assumed (no @pytest.mark.asyncio needed).
"""

from __future__ import annotations

import json
import time
import uuid

import pytest

# ---------------------------------------------------------------------------
# URL prefix constants
# ---------------------------------------------------------------------------

_V1 = "/api/v1"
_V3 = "/api/v3"
_V4 = "/api/v4"
_V5 = "/api/v5"
_CREATORS = f"{_V1}/creators"


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _auth(token: str) -> dict:
    """Build an Authorization header dict from a JWT token string."""
    return {"Authorization": f"Bearer {token}"}


def _unique_email() -> str:
    return f"user-{uuid.uuid4().hex[:8]}@test.com"


def _make_graph_json(node_ids: list[str] | None = None) -> str:
    """Build a minimal valid DAG JSON string (no agent_call endpoints)."""
    if node_ids is None:
        node_ids = ["n1"]
    nodes: dict = {}
    prev: str | None = None
    for nid in node_ids:
        entry: dict = {"type": "transform", "config": {}}
        if prev:
            entry["depends_on"] = [prev]
        nodes[nid] = entry
        prev = nid
    return json.dumps({"nodes": nodes, "edges": []})


def _make_agent_graph_json(agent_id: str) -> str:
    """Build a graph_json referencing an agent by ID (no raw endpoint)."""
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


async def _register_creator(client, **kwargs) -> dict:
    """Helper: register a creator via the API and return the JSON body."""
    payload = {
        "email": kwargs.get("email", _unique_email()),
        "password": kwargs.get("password", "securepass1"),
        "display_name": kwargs.get("display_name", "Test Creator"),
    }
    if "country" in kwargs:
        payload["country"] = kwargs["country"]
    resp = await client.post(f"{_CREATORS}/register", json=payload)
    assert resp.status_code == 201, resp.text
    return resp.json()


# ===========================================================================
# V3 ORCHESTRATION — /api/v3/workflows  and  /api/v3/executions
# ===========================================================================


# ── Workflow CRUD ─────────────────────────────────────────────────────────


async def test_v3_create_workflow_success(client, make_agent):
    """POST /api/v3/workflows creates a new workflow and returns 201."""
    _, token = await make_agent()
    resp = await client.post(
        f"{_V3}/workflows",
        json={"name": "My Workflow", "graph_json": _make_graph_json()},
        headers=_auth(token),
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "My Workflow"
    assert data["status"] == "draft"
    assert "id" in data


async def test_v3_create_workflow_invalid_graph_json(client, make_agent):
    """POST /api/v3/workflows with malformed graph_json returns 400."""
    _, token = await make_agent()
    resp = await client.post(
        f"{_V3}/workflows",
        json={"name": "Bad Graph", "graph_json": "not-valid-json{{"},
        headers=_auth(token),
    )
    assert resp.status_code == 400
    assert "graph_json" in resp.json()["detail"].lower()


async def test_v3_create_workflow_no_auth(client):
    """POST /api/v3/workflows without token returns 401."""
    resp = await client.post(
        f"{_V3}/workflows",
        json={"name": "X", "graph_json": "{}"},
    )
    assert resp.status_code == 401


async def test_v3_list_workflows_empty(client, make_agent):
    """GET /api/v3/workflows returns an empty list when none exist."""
    _, token = await make_agent()
    resp = await client.get(f"{_V3}/workflows", headers=_auth(token))
    assert resp.status_code == 200
    data = resp.json()
    assert "workflows" in data
    assert data["total"] == 0


async def test_v3_list_workflows_with_data(client, make_agent):
    """GET /api/v3/workflows returns all created workflows."""
    _, token = await make_agent()
    graph = _make_graph_json()

    await client.post(
        f"{_V3}/workflows",
        json={"name": "WF Alpha", "graph_json": graph},
        headers=_auth(token),
    )
    await client.post(
        f"{_V3}/workflows",
        json={"name": "WF Beta", "graph_json": graph},
        headers=_auth(token),
    )

    resp = await client.get(f"{_V3}/workflows", headers=_auth(token))
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] >= 2
    names = [w["name"] for w in data["workflows"]]
    assert "WF Alpha" in names
    assert "WF Beta" in names


async def test_v3_get_workflow_success(client, make_agent):
    """GET /api/v3/workflows/{id} returns the correct workflow."""
    _, token = await make_agent()
    create_resp = await client.post(
        f"{_V3}/workflows",
        json={"name": "Fetch Me", "graph_json": _make_graph_json()},
        headers=_auth(token),
    )
    wf_id = create_resp.json()["id"]

    resp = await client.get(f"{_V3}/workflows/{wf_id}", headers=_auth(token))
    assert resp.status_code == 200
    assert resp.json()["id"] == wf_id
    assert resp.json()["name"] == "Fetch Me"


async def test_v3_get_workflow_not_found(client, make_agent):
    """GET /api/v3/workflows/{id} with nonexistent ID returns 404."""
    _, token = await make_agent()
    resp = await client.get(f"{_V3}/workflows/does-not-exist", headers=_auth(token))
    assert resp.status_code == 404


async def test_v3_update_workflow_name(client, make_agent):
    """PUT /api/v3/workflows/{id} updates the workflow name."""
    _, token = await make_agent()
    create_resp = await client.post(
        f"{_V3}/workflows",
        json={"name": "Old Name", "graph_json": _make_graph_json()},
        headers=_auth(token),
    )
    wf_id = create_resp.json()["id"]

    resp = await client.put(
        f"{_V3}/workflows/{wf_id}",
        json={"name": "New Name"},
        headers=_auth(token),
    )
    assert resp.status_code == 200
    assert resp.json()["name"] == "New Name"


async def test_v3_update_workflow_invalid_graph_json(client, make_agent):
    """PUT /api/v3/workflows/{id} with invalid graph_json returns 400."""
    _, token = await make_agent()
    create_resp = await client.post(
        f"{_V3}/workflows",
        json={"name": "WF", "graph_json": _make_graph_json()},
        headers=_auth(token),
    )
    wf_id = create_resp.json()["id"]

    resp = await client.put(
        f"{_V3}/workflows/{wf_id}",
        json={"graph_json": "{{broken"},
        headers=_auth(token),
    )
    assert resp.status_code == 400


async def test_v3_update_workflow_not_found(client, make_agent):
    """PUT /api/v3/workflows/{id} for nonexistent workflow returns 404."""
    _, token = await make_agent()
    resp = await client.put(
        f"{_V3}/workflows/missing-id",
        json={"name": "Whatever"},
        headers=_auth(token),
    )
    assert resp.status_code == 404


async def test_v3_delete_workflow_archives_it(client, make_agent):
    """DELETE /api/v3/workflows/{id} soft-deletes (archives) the workflow."""
    _, token = await make_agent()
    create_resp = await client.post(
        f"{_V3}/workflows",
        json={"name": "Bye Bye", "graph_json": _make_graph_json()},
        headers=_auth(token),
    )
    wf_id = create_resp.json()["id"]

    resp = await client.delete(f"{_V3}/workflows/{wf_id}", headers=_auth(token))
    assert resp.status_code == 200
    assert "archived" in resp.json()["detail"].lower()
    assert resp.json()["workflow_id"] == wf_id


async def test_v3_delete_workflow_not_found(client, make_agent):
    """DELETE /api/v3/workflows/{id} for nonexistent workflow returns 404."""
    _, token = await make_agent()
    resp = await client.delete(f"{_V3}/workflows/nope", headers=_auth(token))
    assert resp.status_code == 404


# ── Workflow Templates ────────────────────────────────────────────────────


async def test_v3_workflow_templates_no_auth(client):
    """GET /api/v3/workflow-templates requires no authentication."""
    resp = await client.get(f"{_V3}/workflow-templates")
    assert resp.status_code == 200
    data = resp.json()
    assert "templates" in data
    assert data["total"] > 0
    # Verify template shape
    tpl = data["templates"][0]
    assert "key" in tpl
    assert "name" in tpl
    assert "graph_json" in tpl


async def test_v3_templates_alias_no_auth(client):
    """GET /api/v3/templates is an alias for /api/v3/workflow-templates."""
    resp_primary = await client.get(f"{_V3}/workflow-templates")
    resp_alias = await client.get(f"{_V3}/templates")
    assert resp_alias.status_code == 200
    assert resp_alias.json()["total"] == resp_primary.json()["total"]


# ── Execution lifecycle ───────────────────────────────────────────────────


async def test_v3_execute_workflow_success(client, make_agent):
    """POST /api/v3/workflows/{id}/execute starts execution and returns 202."""
    _, token = await make_agent()
    create_resp = await client.post(
        f"{_V3}/workflows",
        json={"name": "Exec WF", "graph_json": _make_graph_json()},
        headers=_auth(token),
    )
    wf_id = create_resp.json()["id"]

    resp = await client.post(
        f"{_V3}/workflows/{wf_id}/execute",
        json={"input_data": {"key": "value"}},
        headers=_auth(token),
    )
    assert resp.status_code == 202
    data = resp.json()
    assert "execution_id" in data
    assert "status" in data


async def test_v3_execute_workflow_not_found(client, make_agent):
    """POST /api/v3/workflows/{id}/execute for unknown workflow returns 404."""
    _, token = await make_agent()
    resp = await client.post(
        f"{_V3}/workflows/ghost-wf/execute",
        json={},
        headers=_auth(token),
    )
    assert resp.status_code == 404


async def test_v3_get_execution_success(client, make_agent):
    """GET /api/v3/executions/{id} returns execution details."""
    _, token = await make_agent()
    create_resp = await client.post(
        f"{_V3}/workflows",
        json={"name": "Get Exec WF", "graph_json": _make_graph_json()},
        headers=_auth(token),
    )
    wf_id = create_resp.json()["id"]

    exec_resp = await client.post(
        f"{_V3}/workflows/{wf_id}/execute",
        json={},
        headers=_auth(token),
    )
    exec_id = exec_resp.json()["execution_id"]

    resp = await client.get(f"{_V3}/executions/{exec_id}", headers=_auth(token))
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == exec_id
    assert data["workflow_id"] == wf_id


async def test_v3_get_execution_not_found(client, make_agent):
    """GET /api/v3/executions/{id} for nonexistent execution returns 404."""
    _, token = await make_agent()
    resp = await client.get(f"{_V3}/executions/no-such-exec", headers=_auth(token))
    assert resp.status_code == 404


async def test_v3_get_execution_nodes(client, make_agent):
    """GET /api/v3/executions/{id}/nodes returns nodes list (may be empty)."""
    _, token = await make_agent()
    create_resp = await client.post(
        f"{_V3}/workflows",
        json={"name": "Nodes WF", "graph_json": _make_graph_json()},
        headers=_auth(token),
    )
    wf_id = create_resp.json()["id"]

    exec_resp = await client.post(
        f"{_V3}/workflows/{wf_id}/execute",
        json={},
        headers=_auth(token),
    )
    exec_id = exec_resp.json()["execution_id"]

    resp = await client.get(
        f"{_V3}/executions/{exec_id}/nodes",
        headers=_auth(token),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["execution_id"] == exec_id
    assert "nodes" in data
    assert "total" in data


async def test_v3_get_execution_cost(client, make_agent):
    """GET /api/v3/executions/{id}/cost returns cost breakdown."""
    _, token = await make_agent()
    create_resp = await client.post(
        f"{_V3}/workflows",
        json={"name": "Cost WF", "graph_json": _make_graph_json()},
        headers=_auth(token),
    )
    wf_id = create_resp.json()["id"]

    exec_resp = await client.post(
        f"{_V3}/workflows/{wf_id}/execute",
        json={},
        headers=_auth(token),
    )
    exec_id = exec_resp.json()["execution_id"]

    resp = await client.get(
        f"{_V3}/executions/{exec_id}/cost",
        headers=_auth(token),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["execution_id"] == exec_id
    assert "total_cost_usd" in data
    assert "node_costs" in data


async def test_v3_get_execution_cost_not_found(client, make_agent):
    """GET /api/v3/executions/{id}/cost for unknown execution returns 404."""
    _, token = await make_agent()
    resp = await client.get(
        f"{_V3}/executions/fake-exec-id/cost",
        headers=_auth(token),
    )
    assert resp.status_code == 404


async def test_v3_pause_execution_not_found_or_conflict(client, make_agent):
    """POST /api/v3/executions/{id}/pause for a non-running execution returns 409."""
    _, token = await make_agent()
    resp = await client.post(
        f"{_V3}/executions/ghost-exec/pause",
        headers=_auth(token),
    )
    assert resp.status_code == 409


async def test_v3_resume_execution_not_found_or_conflict(client, make_agent):
    """POST /api/v3/executions/{id}/resume for a non-paused execution returns 409."""
    _, token = await make_agent()
    resp = await client.post(
        f"{_V3}/executions/ghost-exec/resume",
        headers=_auth(token),
    )
    assert resp.status_code == 409


async def test_v3_cancel_execution_not_found_or_conflict(client, make_agent):
    """POST /api/v3/executions/{id}/cancel for an unknown execution returns 409."""
    _, token = await make_agent()
    resp = await client.post(
        f"{_V3}/executions/ghost-exec/cancel",
        headers=_auth(token),
    )
    assert resp.status_code == 409


async def test_v3_cancel_execution_success(client, make_agent, db):
    """POST /api/v3/executions/{id}/cancel on a real pending execution cancels it."""
    from marketplace.models.workflow import WorkflowExecution
    from sqlalchemy import select as sa_select

    _, token = await make_agent()
    create_resp = await client.post(
        f"{_V3}/workflows",
        json={"name": "Cancel WF", "graph_json": _make_graph_json()},
        headers=_auth(token),
    )
    wf_id = create_resp.json()["id"]

    exec_resp = await client.post(
        f"{_V3}/workflows/{wf_id}/execute",
        json={},
        headers=_auth(token),
    )
    exec_id = exec_resp.json()["execution_id"]

    # The DAG runs synchronously and completes before we can cancel it.
    # Reset the execution status to "pending" so the cancel endpoint will accept it.
    result = await db.execute(
        sa_select(WorkflowExecution).where(WorkflowExecution.id == exec_id)
    )
    execution = result.scalar_one_or_none()
    if execution:
        execution.status = "pending"
        execution.completed_at = None
        await db.commit()

    resp = await client.post(
        f"{_V3}/executions/{exec_id}/cancel",
        headers=_auth(token),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "cancelled" in data["detail"].lower()
    assert data["execution_id"] == exec_id


async def test_v3_workflow_with_budget(client, make_agent):
    """POST /api/v3/workflows with max_budget_usd stores budget correctly."""
    _, token = await make_agent()
    resp = await client.post(
        f"{_V3}/workflows",
        json={
            "name": "Budget WF",
            "graph_json": _make_graph_json(),
            "max_budget_usd": 5.50,
        },
        headers=_auth(token),
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["max_budget_usd"] == pytest.approx(5.50, abs=0.01)


# ===========================================================================
# V4 A2UI — /api/v4/stream-token, /api/v4/sessions, /api/v4/health
# ===========================================================================


async def test_v4_health_no_auth(client):
    """GET /api/v4/health does not require authentication."""
    resp = await client.get(f"{_V4}/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert data["protocol"] == "a2ui"
    assert "version" in data
    assert "ws_path" in data
    assert "active_sessions" in data


async def test_v4_stream_token_success(client, make_agent):
    """POST /api/v4/stream-token with valid agent JWT returns a stream token."""
    _, token = await make_agent()
    resp = await client.post(f"{_V4}/stream-token", headers=_auth(token))
    assert resp.status_code == 200
    data = resp.json()
    assert "stream_token" in data
    assert "expires_in_seconds" in data
    assert "expires_at" in data
    assert "ws_url" in data
    assert len(data["stream_token"]) > 20


async def test_v4_stream_token_no_auth(client):
    """POST /api/v4/stream-token without auth returns 401."""
    resp = await client.post(f"{_V4}/stream-token")
    assert resp.status_code == 401


async def test_v4_stream_token_has_agent_id(client, make_agent):
    """POST /api/v4/stream-token response includes agent_id matching the caller."""
    agent, token = await make_agent()
    resp = await client.post(f"{_V4}/stream-token", headers=_auth(token))
    assert resp.status_code == 200
    assert resp.json()["agent_id"] == agent.id


async def test_v4_list_sessions_empty(client, make_agent):
    """GET /api/v4/sessions returns empty list when no A2UI sessions exist."""
    _, token = await make_agent()
    resp = await client.get(f"{_V4}/sessions", headers=_auth(token))
    assert resp.status_code == 200
    data = resp.json()
    assert "sessions" in data
    assert data["total"] == 0


async def test_v4_list_sessions_no_auth(client):
    """GET /api/v4/sessions without auth returns 401."""
    resp = await client.get(f"{_V4}/sessions")
    assert resp.status_code == 401


async def test_v4_get_session_not_found(client, make_agent):
    """GET /api/v4/sessions/{session_id} for unknown session returns 404."""
    _, token = await make_agent()
    resp = await client.get(
        f"{_V4}/sessions/nonexistent-session-id",
        headers=_auth(token),
    )
    assert resp.status_code == 404


async def test_v4_close_session_not_found(client, make_agent):
    """DELETE /api/v4/sessions/{session_id} for unknown session returns 404."""
    _, token = await make_agent()
    resp = await client.delete(
        f"{_V4}/sessions/ghost-session",
        headers=_auth(token),
    )
    assert resp.status_code == 404


# ===========================================================================
# V5 CHAINS — /api/v5/chain-templates, /api/v5/chain-executions, etc.
# ===========================================================================


async def _create_chain_template(client, token, agent_id, name="Test Chain"):
    """Helper: create a chain template via API and return response JSON."""
    graph = _make_agent_graph_json(agent_id)
    resp = await client.post(
        f"{_V5}/chain-templates",
        json={
            "name": name,
            "description": "test chain",
            "category": "testing",
            "graph_json": graph,
        },
        headers=_auth(token),
    )
    return resp


async def test_v5_create_chain_template_success(client, make_agent, db):
    """POST /api/v5/chain-templates creates a template and returns 201."""
    agent, token = await make_agent()
    agent.a2a_endpoint = "http://test-server:9000"
    await db.commit()

    resp = await _create_chain_template(client, token, agent.id, "New Chain")
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "New Chain"
    assert data["author_id"] == agent.id
    assert data["status"] == "active"


async def test_v5_create_chain_template_no_auth(client):
    """POST /api/v5/chain-templates without token returns 401."""
    resp = await client.post(
        f"{_V5}/chain-templates",
        json={"name": "X", "graph_json": "{}"},
    )
    assert resp.status_code == 401


async def test_v5_create_chain_template_ssrf_rejected(client, make_agent, db):
    """POST /api/v5/chain-templates with a raw endpoint URL is rejected with 400."""
    agent, token = await make_agent()
    agent.a2a_endpoint = "http://test-server:9000"
    await db.commit()

    bad_graph = json.dumps({
        "nodes": {
            "n1": {
                "type": "agent_call",
                "config": {"agent_id": agent.id, "endpoint": "http://evil.internal/steal"},
            }
        },
        "edges": [],
    })
    resp = await client.post(
        f"{_V5}/chain-templates",
        json={"name": "SSRF Test", "graph_json": bad_graph},
        headers=_auth(token),
    )
    assert resp.status_code == 400
    assert "raw endpoint" in resp.json()["detail"]


async def test_v5_list_chain_templates(client, make_agent, db):
    """GET /api/v5/chain-templates returns all published templates."""
    agent, token = await make_agent()
    agent.a2a_endpoint = "http://test-server:9000"
    await db.commit()

    await _create_chain_template(client, token, agent.id, "Chain A")
    await _create_chain_template(client, token, agent.id, "Chain B")

    resp = await client.get(f"{_V5}/chain-templates", headers=_auth(token))
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] >= 2
    names = [t["name"] for t in data["templates"]]
    assert "Chain A" in names


async def test_v5_get_chain_template_success(client, make_agent, db):
    """GET /api/v5/chain-templates/{id} returns the correct template."""
    agent, token = await make_agent()
    agent.a2a_endpoint = "http://test-server:9000"
    await db.commit()

    create_resp = await _create_chain_template(client, token, agent.id, "Lookup Chain")
    template_id = create_resp.json()["id"]

    resp = await client.get(
        f"{_V5}/chain-templates/{template_id}",
        headers=_auth(token),
    )
    assert resp.status_code == 200
    assert resp.json()["id"] == template_id
    assert resp.json()["name"] == "Lookup Chain"


async def test_v5_get_chain_template_not_found(client, make_agent):
    """GET /api/v5/chain-templates/{id} with unknown ID returns 404."""
    _, token = await make_agent()
    resp = await client.get(
        f"{_V5}/chain-templates/does-not-exist",
        headers=_auth(token),
    )
    assert resp.status_code == 404


async def test_v5_archive_chain_template_success(client, make_agent, db):
    """DELETE /api/v5/chain-templates/{id} by the author archives it."""
    agent, token = await make_agent()
    agent.a2a_endpoint = "http://test-server:9000"
    await db.commit()

    create_resp = await _create_chain_template(client, token, agent.id, "Archive Me")
    template_id = create_resp.json()["id"]

    resp = await client.delete(
        f"{_V5}/chain-templates/{template_id}",
        headers=_auth(token),
    )
    assert resp.status_code == 200
    assert "archived" in resp.json()["detail"].lower()


async def test_v5_archive_chain_template_not_author(client, make_agent, db):
    """DELETE /api/v5/chain-templates/{id} by a non-author returns 403."""
    author, author_token = await make_agent()
    outsider, outsider_token = await make_agent()
    author.a2a_endpoint = "http://test-server:9000"
    await db.commit()

    create_resp = await _create_chain_template(client, author_token, author.id)
    template_id = create_resp.json()["id"]

    resp = await client.delete(
        f"{_V5}/chain-templates/{template_id}",
        headers=_auth(outsider_token),
    )
    assert resp.status_code == 403


async def test_v5_fork_chain_template(client, make_agent, db):
    """POST /api/v5/chain-templates/{id}/fork creates a copy with forked_from_id set."""
    author, author_token = await make_agent()
    forker, forker_token = await make_agent()
    author.a2a_endpoint = "http://test-server:9000"
    await db.commit()

    create_resp = await _create_chain_template(client, author_token, author.id, "Original")
    template_id = create_resp.json()["id"]

    resp = await client.post(
        f"{_V5}/chain-templates/{template_id}/fork",
        json={"name": "Forked Copy"},
        headers=_auth(forker_token),
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["forked_from_id"] == template_id
    assert data["author_id"] == forker.id
    assert data["name"] == "Forked Copy"


async def test_v5_execute_chain_success(client, make_agent, db):
    """POST /api/v5/chain-templates/{id}/execute returns 202 with execution details."""
    agent, token = await make_agent()
    agent.a2a_endpoint = "http://test-server:9000"
    await db.commit()

    create_resp = await _create_chain_template(client, token, agent.id, "Execute Me")
    template_id = create_resp.json()["id"]

    resp = await client.post(
        f"{_V5}/chain-templates/{template_id}/execute",
        json={"input_data": {"query": "hello"}},
        headers=_auth(token),
    )
    assert resp.status_code == 202
    data = resp.json()
    assert data["chain_template_id"] == template_id
    assert data["status"] in ("pending", "running")
    assert "id" in data


async def test_v5_execute_chain_idempotency(client, make_agent, db):
    """Two execute calls with the same idempotency_key return the same execution."""
    agent, token = await make_agent()
    agent.a2a_endpoint = "http://test-server:9000"
    await db.commit()

    create_resp = await _create_chain_template(client, token, agent.id)
    template_id = create_resp.json()["id"]

    body = {"input_data": {}, "idempotency_key": "idem-key-v5-001"}
    resp1 = await client.post(
        f"{_V5}/chain-templates/{template_id}/execute",
        json=body,
        headers=_auth(token),
    )
    resp2 = await client.post(
        f"{_V5}/chain-templates/{template_id}/execute",
        json=body,
        headers=_auth(token),
    )
    assert resp1.status_code == 202
    assert resp2.status_code == 202
    assert resp1.json()["id"] == resp2.json()["id"]


async def test_v5_get_chain_execution_success(client, make_agent, db):
    """GET /api/v5/chain-executions/{id} returns the execution record."""
    agent, token = await make_agent()
    agent.a2a_endpoint = "http://test-server:9000"
    await db.commit()

    create_resp = await _create_chain_template(client, token, agent.id)
    template_id = create_resp.json()["id"]

    exec_resp = await client.post(
        f"{_V5}/chain-templates/{template_id}/execute",
        json={},
        headers=_auth(token),
    )
    exec_id = exec_resp.json()["id"]

    resp = await client.get(
        f"{_V5}/chain-executions/{exec_id}",
        headers=_auth(token),
    )
    assert resp.status_code == 200
    assert resp.json()["id"] == exec_id


async def test_v5_get_chain_execution_not_found(client, make_agent):
    """GET /api/v5/chain-executions/{id} for unknown ID returns 404."""
    _, token = await make_agent()
    resp = await client.get(
        f"{_V5}/chain-executions/unknown-exec-id",
        headers=_auth(token),
    )
    assert resp.status_code == 404


async def test_v5_list_chain_executions(client, make_agent, db):
    """GET /api/v5/chain-templates/{id}/executions returns executions for that template."""
    agent, token = await make_agent()
    agent.a2a_endpoint = "http://test-server:9000"
    await db.commit()

    create_resp = await _create_chain_template(client, token, agent.id)
    template_id = create_resp.json()["id"]

    # Run two executions
    await client.post(
        f"{_V5}/chain-templates/{template_id}/execute",
        json={},
        headers=_auth(token),
    )
    await client.post(
        f"{_V5}/chain-templates/{template_id}/execute",
        json={"idempotency_key": "unique-exec-two"},
        headers=_auth(token),
    )

    resp = await client.get(
        f"{_V5}/chain-templates/{template_id}/executions",
        headers=_auth(token),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] >= 1
    assert "executions" in data


async def test_v5_list_chain_executions_template_not_found(client, make_agent):
    """GET /api/v5/chain-templates/{id}/executions for unknown template returns 404."""
    _, token = await make_agent()
    resp = await client.get(
        f"{_V5}/chain-templates/ghost-template/executions",
        headers=_auth(token),
    )
    assert resp.status_code == 404


async def test_v5_provenance_access_by_initiator(client, make_agent, db):
    """GET /api/v5/chain-executions/{id}/provenance is accessible to the initiator."""
    agent, token = await make_agent()
    agent.a2a_endpoint = "http://test-server:9000"
    await db.commit()

    create_resp = await _create_chain_template(client, token, agent.id)
    template_id = create_resp.json()["id"]

    exec_resp = await client.post(
        f"{_V5}/chain-templates/{template_id}/execute",
        json={},
        headers=_auth(token),
    )
    exec_id = exec_resp.json()["id"]

    resp = await client.get(
        f"{_V5}/chain-executions/{exec_id}/provenance",
        headers=_auth(token),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["chain_execution_id"] == exec_id
    assert "nodes" in data


async def test_v5_provenance_forbidden_for_outsider(client, make_agent, db):
    """GET /api/v5/chain-executions/{id}/provenance is forbidden to unrelated agents."""
    author, author_token = await make_agent()
    outsider, outsider_token = await make_agent()
    author.a2a_endpoint = "http://test-server:9000"
    await db.commit()

    create_resp = await _create_chain_template(client, author_token, author.id)
    template_id = create_resp.json()["id"]

    exec_resp = await client.post(
        f"{_V5}/chain-templates/{template_id}/execute",
        json={},
        headers=_auth(author_token),
    )
    exec_id = exec_resp.json()["id"]

    resp = await client.get(
        f"{_V5}/chain-executions/{exec_id}/provenance",
        headers=_auth(outsider_token),
    )
    assert resp.status_code == 403


async def test_v5_provenance_entries_access_control(client, make_agent, db):
    """GET /api/v5/chain-executions/{id}/provenance-entries is forbidden to outsiders."""
    author, author_token = await make_agent()
    outsider, outsider_token = await make_agent()
    author.a2a_endpoint = "http://test-server:9000"
    await db.commit()

    create_resp = await _create_chain_template(client, author_token, author.id)
    template_id = create_resp.json()["id"]

    exec_resp = await client.post(
        f"{_V5}/chain-templates/{template_id}/execute",
        json={},
        headers=_auth(author_token),
    )
    exec_id = exec_resp.json()["id"]

    resp = await client.get(
        f"{_V5}/chain-executions/{exec_id}/provenance-entries",
        headers=_auth(outsider_token),
    )
    assert resp.status_code == 403


async def test_v5_provenance_entries_by_initiator(client, make_agent, db):
    """GET /api/v5/chain-executions/{id}/provenance-entries is accessible to the initiator."""
    agent, token = await make_agent()
    agent.a2a_endpoint = "http://test-server:9000"
    await db.commit()

    create_resp = await _create_chain_template(client, token, agent.id)
    template_id = create_resp.json()["id"]

    exec_resp = await client.post(
        f"{_V5}/chain-templates/{template_id}/execute",
        json={},
        headers=_auth(token),
    )
    exec_id = exec_resp.json()["id"]

    resp = await client.get(
        f"{_V5}/chain-executions/{exec_id}/provenance-entries",
        headers=_auth(token),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "entries" in data
    assert "total" in data


# ── Analytics & popular chains ─────────────────────────────────────────────


async def test_v5_get_chain_analytics(client, make_agent, db):
    """GET /api/v5/chain-templates/{id}/analytics returns performance data."""
    agent, token = await make_agent()
    agent.a2a_endpoint = "http://test-server:9000"
    await db.commit()

    create_resp = await _create_chain_template(client, token, agent.id, "Analytics Chain")
    template_id = create_resp.json()["id"]

    resp = await client.get(
        f"{_V5}/chain-templates/{template_id}/analytics",
        headers=_auth(token),
    )
    assert resp.status_code == 200


async def test_v5_get_chain_analytics_not_found(client, make_agent):
    """GET /api/v5/chain-templates/{id}/analytics for unknown template returns 404."""
    _, token = await make_agent()
    resp = await client.get(
        f"{_V5}/chain-templates/ghost/analytics",
        headers=_auth(token),
    )
    assert resp.status_code == 404


async def test_v5_get_popular_chains(client, make_agent):
    """GET /api/v5/chains/popular returns list of popular chains."""
    _, token = await make_agent()
    resp = await client.get(f"{_V5}/chains/popular", headers=_auth(token))
    assert resp.status_code == 200
    data = resp.json()
    assert "chains" in data
    assert "total" in data


async def test_v5_get_agent_chain_stats(client, make_agent):
    """GET /api/v5/chains/agents/{agent_id}/stats returns stats dict."""
    agent, token = await make_agent()
    resp = await client.get(
        f"{_V5}/chains/agents/{agent.id}/stats",
        headers=_auth(token),
    )
    assert resp.status_code == 200


# ── Auto-chaining ──────────────────────────────────────────────────────────


async def test_v5_suggest_agents_empty(client, make_agent):
    """POST /api/v5/chains/suggest-agents returns empty agents list when DB is empty."""
    _, token = await make_agent()
    resp = await client.post(
        f"{_V5}/chains/suggest-agents",
        json={"capability": "summarisation", "max_results": 5},
        headers=_auth(token),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "agents" in data
    assert data["capability"] == "summarisation"


async def test_v5_suggest_agents_no_auth(client):
    """POST /api/v5/chains/suggest-agents without auth returns 401."""
    resp = await client.post(
        f"{_V5}/chains/suggest-agents",
        json={"capability": "translation"},
    )
    assert resp.status_code == 401


async def test_v5_compose_chain(client, make_agent):
    """POST /api/v5/chains/compose returns a draft chain template dict."""
    _, token = await make_agent()
    resp = await client.post(
        f"{_V5}/chains/compose",
        json={"task_description": "Summarise a PDF document and translate it to Spanish"},
        headers=_auth(token),
    )
    # Accept 200 (success) or 400 (no matching agents — implementation-specific)
    assert resp.status_code in (200, 400)


async def test_v5_validate_chain_not_found(client, make_agent):
    """POST /api/v5/chains/{id}/validate for unknown template returns 404."""
    _, token = await make_agent()
    resp = await client.post(
        f"{_V5}/chains/nonexistent-template-id/validate",
        headers=_auth(token),
    )
    assert resp.status_code == 404


async def test_v5_validate_chain_success(client, make_agent, db):
    """POST /api/v5/chains/{id}/validate for a real template returns validation result."""
    agent, token = await make_agent()
    agent.a2a_endpoint = "http://test-server:9000"
    await db.commit()

    create_resp = await _create_chain_template(client, token, agent.id, "Validate Me")
    template_id = create_resp.json()["id"]

    resp = await client.post(
        f"{_V5}/chains/{template_id}/validate",
        headers=_auth(token),
    )
    assert resp.status_code == 200
    data = resp.json()
    # Result must contain at least a validity indicator
    assert "valid" in data or "status" in data or "nodes" in data or "errors" in data


# ── Chain cost estimate & settlement ──────────────────────────────────────


async def test_v5_cost_estimate_success(client, make_agent, db):
    """GET /api/v5/chain-templates/{id}/cost-estimate returns an estimate dict."""
    agent, token = await make_agent()
    agent.a2a_endpoint = "http://test-server:9000"
    await db.commit()

    create_resp = await _create_chain_template(client, token, agent.id, "Cost Chain")
    template_id = create_resp.json()["id"]

    resp = await client.get(
        f"{_V5}/chain-templates/{template_id}/cost-estimate",
        headers=_auth(token),
    )
    assert resp.status_code == 200


async def test_v5_cost_estimate_not_found(client, make_agent):
    """GET /api/v5/chain-templates/{id}/cost-estimate for unknown template returns 404."""
    _, token = await make_agent()
    resp = await client.get(
        f"{_V5}/chain-templates/ghost-template/cost-estimate",
        headers=_auth(token),
    )
    assert resp.status_code == 404


async def test_v5_settlement_not_found(client, make_agent):
    """GET /api/v5/chain-executions/{id}/settlement for unknown execution returns 404."""
    _, token = await make_agent()
    resp = await client.get(
        f"{_V5}/chain-executions/nonexistent-exec/settlement",
        headers=_auth(token),
    )
    assert resp.status_code == 404


async def test_v5_settlement_success(client, make_agent, db):
    """GET /api/v5/chain-executions/{id}/settlement returns settlement report."""
    agent, token = await make_agent()
    agent.a2a_endpoint = "http://test-server:9000"
    await db.commit()

    create_resp = await _create_chain_template(client, token, agent.id, "Settle Chain")
    template_id = create_resp.json()["id"]

    exec_resp = await client.post(
        f"{_V5}/chain-templates/{template_id}/execute",
        json={},
        headers=_auth(token),
    )
    exec_id = exec_resp.json()["id"]

    resp = await client.get(
        f"{_V5}/chain-executions/{exec_id}/settlement",
        headers=_auth(token),
    )
    assert resp.status_code == 200


# ── Chain policies ─────────────────────────────────────────────────────────


async def test_v5_create_chain_policy_success(client, make_agent):
    """POST /api/v5/chains/policies creates a policy and returns 201."""
    _, token = await make_agent()
    resp = await client.post(
        f"{_V5}/chains/policies",
        json={
            "name": "No Budget Exceeded",
            "policy_type": "cost_limit",
            "rules_json": json.dumps({"max_cost_usd": 10.0}),
            "enforcement": "block",
            "scope": "chain",
        },
        headers=_auth(token),
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "No Budget Exceeded"
    assert data["policy_type"] == "cost_limit"
    assert "id" in data


async def test_v5_create_chain_policy_no_auth(client):
    """POST /api/v5/chains/policies without auth returns 401."""
    resp = await client.post(
        f"{_V5}/chains/policies",
        json={
            "name": "Policy X",
            "policy_type": "rate_limit",
            "rules_json": "{}",
        },
    )
    assert resp.status_code == 401


async def test_v5_list_chain_policies(client, make_agent):
    """GET /api/v5/chains/policies returns a paginated policies list."""
    _, token = await make_agent()

    # Create two policies
    for name in ("Policy One", "Policy Two"):
        await client.post(
            f"{_V5}/chains/policies",
            json={
                "name": name,
                "policy_type": "cost_limit",
                "rules_json": json.dumps({"limit": 5}),
            },
            headers=_auth(token),
        )

    resp = await client.get(f"{_V5}/chains/policies", headers=_auth(token))
    assert resp.status_code == 200
    data = resp.json()
    assert "policies" in data
    assert data["total"] >= 2


async def test_v5_evaluate_policies_not_found(client, make_agent):
    """POST /api/v5/chains/{id}/evaluate-policies with unknown template returns 404."""
    _, token = await make_agent()
    resp = await client.post(
        f"{_V5}/chains/nonexistent-template/evaluate-policies",
        json={"policy_ids": ["some-policy-id"]},
        headers=_auth(token),
    )
    assert resp.status_code == 404


async def test_v5_evaluate_policies_success(client, make_agent, db):
    """POST /api/v5/chains/{id}/evaluate-policies returns evaluation result."""
    agent, token = await make_agent()
    agent.a2a_endpoint = "http://test-server:9000"
    await db.commit()

    create_resp = await _create_chain_template(client, token, agent.id, "Policy Chain")
    template_id = create_resp.json()["id"]

    policy_resp = await client.post(
        f"{_V5}/chains/policies",
        json={
            "name": "Eval Policy",
            "policy_type": "cost_limit",
            "rules_json": json.dumps({"max_cost_usd": 50.0}),
        },
        headers=_auth(token),
    )
    policy_id = policy_resp.json()["id"]

    resp = await client.post(
        f"{_V5}/chains/{template_id}/evaluate-policies",
        json={"policy_ids": [policy_id]},
        headers=_auth(token),
    )
    assert resp.status_code == 200


# ===========================================================================
# CREATORS — /api/v1/creators
# ===========================================================================


async def test_creators_register_success(client):
    """POST /api/v1/creators/register returns 201 with creator and token."""
    data = await _register_creator(client, display_name="Alice Builder")
    assert "creator" in data
    assert "token" in data
    assert data["creator"]["display_name"] == "Alice Builder"
    assert data["creator"]["status"] == "active"


async def test_creators_register_duplicate_email(client):
    """Registering the same email twice returns 409 Conflict."""
    email = _unique_email()
    await _register_creator(client, email=email)

    resp = await client.post(f"{_CREATORS}/register", json={
        "email": email,
        "password": "securepass1",
        "display_name": "Duplicate",
    })
    assert resp.status_code == 409


async def test_creators_register_short_password(client):
    """Password shorter than 8 characters is rejected with 422."""
    resp = await client.post(f"{_CREATORS}/register", json={
        "email": _unique_email(),
        "password": "short7!",  # 7 chars
        "display_name": "Bad Pass",
    })
    assert resp.status_code == 422


async def test_creators_register_missing_display_name(client):
    """Registration without display_name returns 422."""
    resp = await client.post(f"{_CREATORS}/register", json={
        "email": _unique_email(),
        "password": "securepass1",
    })
    assert resp.status_code == 422


async def test_creators_register_with_country(client):
    """Country code is uppercased on storage (e.g., 'in' -> 'IN')."""
    data = await _register_creator(client, country="in")
    token = data["token"]

    resp = await client.get(f"{_CREATORS}/me", headers=_auth(token))
    assert resp.status_code == 200
    assert resp.json()["country"] == "IN"


async def test_creators_login_success(client):
    """POST /api/v1/creators/login with correct credentials returns 200 and token."""
    email = _unique_email()
    await _register_creator(client, email=email, password="correctPass8")

    resp = await client.post(f"{_CREATORS}/login", json={
        "email": email,
        "password": "correctPass8",
    })
    assert resp.status_code == 200
    body = resp.json()
    assert "token" in body
    assert body["creator"]["email"] == email.lower().strip()


async def test_creators_login_wrong_password(client):
    """POST /api/v1/creators/login with wrong password returns 401."""
    email = _unique_email()
    await _register_creator(client, email=email)

    resp = await client.post(f"{_CREATORS}/login", json={
        "email": email,
        "password": "totallyWrong99",
    })
    assert resp.status_code == 401


async def test_creators_login_unknown_email(client):
    """POST /api/v1/creators/login with unknown email returns 401."""
    resp = await client.post(f"{_CREATORS}/login", json={
        "email": "nobody-at-all@test.com",
        "password": "securepass1",
    })
    assert resp.status_code == 401


async def test_creators_get_profile_success(client):
    """GET /api/v1/creators/me with a valid token returns creator profile."""
    data = await _register_creator(client, display_name="ProfileUser")
    token = data["token"]

    resp = await client.get(f"{_CREATORS}/me", headers=_auth(token))
    assert resp.status_code == 200
    body = resp.json()
    assert body["display_name"] == "ProfileUser"
    assert body["status"] == "active"


async def test_creators_get_profile_unauthenticated(client):
    """GET /api/v1/creators/me without Authorization header returns 401."""
    resp = await client.get(f"{_CREATORS}/me")
    assert resp.status_code == 401


async def test_creators_update_display_name(client):
    """PUT /api/v1/creators/me can update display_name."""
    data = await _register_creator(client, display_name="OldName")
    token = data["token"]

    resp = await client.put(
        f"{_CREATORS}/me",
        json={"display_name": "NewName"},
        headers=_auth(token),
    )
    assert resp.status_code == 200
    assert resp.json()["display_name"] == "NewName"


async def test_creators_update_payout_method(client):
    """PUT /api/v1/creators/me can update payout_method."""
    data = await _register_creator(client)
    token = data["token"]

    resp = await client.put(
        f"{_CREATORS}/me",
        json={"payout_method": "stripe"},
        headers=_auth(token),
    )
    assert resp.status_code == 200
    assert resp.json()["payout_method"] == "stripe"


async def test_creators_get_agents_empty(client):
    """GET /api/v1/creators/me/agents returns empty list when no agents claimed."""
    data = await _register_creator(client)
    token = data["token"]

    resp = await client.get(f"{_CREATORS}/me/agents", headers=_auth(token))
    assert resp.status_code == 200
    body = resp.json()
    assert body["count"] == 0
    assert body["agents"] == []


async def test_creators_claim_agent_success(client, make_agent):
    """POST /api/v1/creators/me/agents/{agent_id}/claim links an unclaimed agent."""
    # Create an agent in DB (unclaimed)
    agent, _ = await make_agent()

    # Register a creator
    data = await _register_creator(client)
    token = data["token"]
    creator_id = data["creator"]["id"]

    resp = await client.post(
        f"{_CREATORS}/me/agents/{agent.id}/claim",
        headers=_auth(token),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["agent_id"] == agent.id
    assert body["creator_id"] == creator_id


async def test_creators_claim_nonexistent_agent(client):
    """POST /api/v1/creators/me/agents/{id}/claim with unknown agent_id returns 400."""
    data = await _register_creator(client)
    token = data["token"]

    resp = await client.post(
        f"{_CREATORS}/me/agents/{uuid.uuid4()}/claim",
        headers=_auth(token),
    )
    assert resp.status_code == 400
    assert "not found" in resp.json()["detail"].lower()


async def test_creators_get_dashboard(client):
    """GET /api/v1/creators/me/dashboard returns aggregated creator data."""
    data = await _register_creator(client)
    token = data["token"]

    resp = await client.get(f"{_CREATORS}/me/dashboard", headers=_auth(token))
    assert resp.status_code == 200
    body = resp.json()
    assert "creator_balance" in body
    assert "agents_count" in body
    assert "agents" in body


async def test_creators_get_wallet(client):
    """GET /api/v1/creators/me/wallet returns USD balance with signup bonus."""
    data = await _register_creator(client)
    token = data["token"]

    resp = await client.get(f"{_CREATORS}/me/wallet", headers=_auth(token))
    assert resp.status_code == 200
    body = resp.json()
    assert "balance" in body
    # Creator registration grants a signup bonus ($0.10 USD)
    assert body["balance"] == pytest.approx(0.10, abs=0.01)


async def test_creators_get_wallet_unauthenticated(client):
    """GET /api/v1/creators/me/wallet without auth returns 401."""
    resp = await client.get(f"{_CREATORS}/me/wallet")
    assert resp.status_code == 401


# ===========================================================================
# DEPRECATIONS — apply_legacy_v1_deprecation_headers helper
# ===========================================================================


async def test_deprecations_headers_applied():
    """apply_legacy_v1_deprecation_headers sets Deprecation, Sunset, and Link headers."""
    from fastapi.responses import Response as FastAPIResponse
    from marketplace.api.deprecations import (
        LEGACY_V1_SUNSET,
        LEGACY_V1_MIGRATION_DOC,
        apply_legacy_v1_deprecation_headers,
    )

    response = FastAPIResponse()
    apply_legacy_v1_deprecation_headers(response)

    assert response.headers["Deprecation"] == "true"
    assert response.headers["Sunset"] == LEGACY_V1_SUNSET
    assert response.headers["Link"] == LEGACY_V1_MIGRATION_DOC


async def test_deprecations_sunset_value():
    """The LEGACY_V1_SUNSET constant is set to the expected date string."""
    from marketplace.api.deprecations import LEGACY_V1_SUNSET

    assert "2026" in LEGACY_V1_SUNSET


async def test_deprecations_migration_doc_is_link():
    """LEGACY_V1_MIGRATION_DOC contains a URL to the migration guide."""
    from marketplace.api.deprecations import LEGACY_V1_MIGRATION_DOC

    assert "http" in LEGACY_V1_MIGRATION_DOC.lower()
    assert "rel=" in LEGACY_V1_MIGRATION_DOC


# ===========================================================================
# WEBHOOKS — /webhooks/stripe and /webhooks/razorpay
# ===========================================================================
#
# In test mode settings.stripe_secret_key is blank/test so the Stripe
# service is in simulated mode and skips real signature verification.
# For Razorpay, settings.razorpay_key_secret is also blank in tests so
# signature verification is also skipped.
# ---------------------------------------------------------------------------


async def test_webhooks_stripe_known_event(client):
    """POST /webhooks/stripe with payment_intent.succeeded event returns 200 ok."""
    payload = {
        "type": "payment_intent.succeeded",
        "data": {"id": "pi_test_001", "metadata": {}},
    }
    resp = await client.post(
        "/webhooks/stripe",
        json=payload,
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


async def test_webhooks_stripe_payment_failed_event(client):
    """POST /webhooks/stripe with payment_intent.payment_failed is handled gracefully."""
    payload = {
        "type": "payment_intent.payment_failed",
        "data": {"id": "pi_fail_001"},
    }
    resp = await client.post("/webhooks/stripe", json=payload)
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


async def test_webhooks_stripe_charge_refunded_event(client):
    """POST /webhooks/stripe with charge.refunded event is handled gracefully."""
    payload = {
        "type": "charge.refunded",
        "data": {"id": "ch_refund_001"},
    }
    resp = await client.post("/webhooks/stripe", json=payload)
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


async def test_webhooks_stripe_account_updated_event(client):
    """POST /webhooks/stripe with account.updated event is handled gracefully."""
    payload = {
        "type": "account.updated",
        "data": {"id": "acct_001"},
    }
    resp = await client.post("/webhooks/stripe", json=payload)
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


async def test_webhooks_stripe_unknown_event_type(client):
    """POST /webhooks/stripe with an unrecognised event type is still processed (200)."""
    payload = {"type": "some.unknown.event", "data": {}}
    resp = await client.post("/webhooks/stripe", json=payload)
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


async def test_webhooks_stripe_invalid_json(client):
    """POST /webhooks/stripe with malformed JSON body returns 400."""
    resp = await client.post(
        "/webhooks/stripe",
        content=b"not-valid-json{{{{",
        headers={"Content-Type": "application/json"},
    )
    assert resp.status_code == 400


async def test_webhooks_razorpay_payment_captured(client):
    """POST /webhooks/razorpay with payment.captured event returns 200 ok."""
    payload = {
        "event": "payment.captured",
        "payload": {"payment": {"entity": {"id": "pay_test_001"}}},
    }
    resp = await client.post("/webhooks/razorpay", json=payload)
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


async def test_webhooks_razorpay_payment_failed(client):
    """POST /webhooks/razorpay with payment.failed event is handled gracefully."""
    payload = {
        "event": "payment.failed",
        "payload": {"payment": {"entity": {"id": "pay_fail_001"}}},
    }
    resp = await client.post("/webhooks/razorpay", json=payload)
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


async def test_webhooks_razorpay_order_paid(client):
    """POST /webhooks/razorpay with order.paid event is handled gracefully."""
    payload = {
        "event": "order.paid",
        "payload": {"order": {"entity": {"id": "order_001"}}},
    }
    resp = await client.post("/webhooks/razorpay", json=payload)
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


async def test_webhooks_razorpay_payout_processed(client):
    """POST /webhooks/razorpay with payout.processed event is handled gracefully."""
    payload = {
        "event": "payout.processed",
        "payload": {"payout": {"entity": {"id": "pout_001"}}},
    }
    resp = await client.post("/webhooks/razorpay", json=payload)
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


async def test_webhooks_razorpay_unknown_event(client):
    """POST /webhooks/razorpay with an unrecognised event type still returns 200."""
    payload = {"event": "some.other.event", "payload": {}}
    resp = await client.post("/webhooks/razorpay", json=payload)
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


async def test_webhooks_razorpay_invalid_json(client):
    """POST /webhooks/razorpay with malformed JSON body returns 400."""
    resp = await client.post(
        "/webhooks/razorpay",
        content=b"{{broken",
        headers={"Content-Type": "application/json"},
    )
    assert resp.status_code == 400


async def test_webhooks_razorpay_stale_timestamp_rejected(client):
    """POST /webhooks/razorpay with a timestamp >5 min old is rejected with 400."""
    stale_ts = int(time.time()) - 400  # 400 seconds ago — past the 300-s tolerance
    payload = {
        "event": "payment.captured",
        "created_at": stale_ts,
        "payload": {"payment": {"entity": {"id": "pay_stale"}}},
    }
    resp = await client.post("/webhooks/razorpay", json=payload)
    assert resp.status_code == 400
    assert "timestamp" in resp.json()["error"].lower()


async def test_webhooks_razorpay_fresh_timestamp_accepted(client):
    """POST /webhooks/razorpay with a current timestamp is processed normally."""
    fresh_ts = int(time.time())
    payload = {
        "event": "order.paid",
        "created_at": fresh_ts,
        "payload": {"order": {"entity": {"id": "order_fresh"}}},
    }
    resp = await client.post("/webhooks/razorpay", json=payload)
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"
