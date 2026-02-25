"""Tests for Orchestration v3 API routes (marketplace/api/v3_orchestration.py).

Covers workflow CRUD, execution lifecycle (execute, pause, resume, cancel),
node inspection, cost tracking, and the template endpoints.

All tests make real HTTP requests via the client fixture. No service mocks.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from decimal import Decimal

import pytest

from marketplace.core.auth import create_access_token
from marketplace.models.agent import RegisteredAgent
from marketplace.models.workflow import (
    WorkflowDefinition,
    WorkflowExecution,
    WorkflowNodeExecution,
)
from marketplace.tests.conftest import TestSession, _new_id

V3 = "/api/v3"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _create_agent(name: str | None = None) -> tuple[str, str]:
    """Create an active agent and return (agent_id, jwt)."""
    async with TestSession() as db:
        agent_id = _new_id()
        agent = RegisteredAgent(
            id=agent_id,
            name=name or f"orch-agent-{agent_id[:8]}",
            agent_type="both",
            public_key="ssh-rsa AAAA_test",
            status="active",
        )
        db.add(agent)
        await db.commit()
        return agent_id, create_access_token(agent_id, agent.name)


def _simple_graph() -> str:
    """Return a minimal valid DAG graph JSON string."""
    return json.dumps({
        "nodes": {
            "step_1": {
                "type": "agent_call",
                "config": {"endpoint": ""},
                "depends_on": [],
            }
        },
        "edges": [],
    })


def _two_node_graph() -> str:
    return json.dumps({
        "nodes": {
            "a": {
                "type": "agent_call",
                "config": {"endpoint": "http://a"},
                "depends_on": [],
            },
            "b": {
                "type": "agent_call",
                "config": {"endpoint": "http://b"},
                "depends_on": ["a"],
            },
        },
        "edges": [],
    })


async def _create_workflow(
    owner_id: str,
    name: str = "Test Workflow",
    graph_json: str | None = None,
    status: str = "draft",
    max_budget_usd: Decimal | None = None,
) -> WorkflowDefinition:
    """Directly insert a WorkflowDefinition."""
    async with TestSession() as db:
        wf = WorkflowDefinition(
            id=_new_id(),
            name=name,
            description="test workflow",
            graph_json=graph_json or _simple_graph(),
            owner_id=owner_id,
            status=status,
            max_budget_usd=max_budget_usd,
        )
        db.add(wf)
        await db.commit()
        await db.refresh(wf)
        return wf


async def _create_execution(
    workflow_id: str,
    initiated_by: str,
    status: str = "pending",
    total_cost_usd: Decimal | None = None,
    input_json: str = "{}",
    output_json: str | None = None,
    error_message: str | None = None,
) -> WorkflowExecution:
    """Directly insert a WorkflowExecution."""
    async with TestSession() as db:
        ex = WorkflowExecution(
            id=_new_id(),
            workflow_id=workflow_id,
            initiated_by=initiated_by,
            status=status,
            input_json=input_json,
            output_json=output_json,
            total_cost_usd=total_cost_usd,
            error_message=error_message,
        )
        db.add(ex)
        await db.commit()
        await db.refresh(ex)
        return ex


async def _create_node_execution(
    execution_id: str,
    node_id: str = "step_1",
    node_type: str = "agent_call",
    status: str = "completed",
    cost_usd: Decimal = Decimal("0.05"),
    error_message: str | None = None,
    attempt: int = 1,
) -> WorkflowNodeExecution:
    """Directly insert a WorkflowNodeExecution."""
    async with TestSession() as db:
        ne = WorkflowNodeExecution(
            id=_new_id(),
            execution_id=execution_id,
            node_id=node_id,
            node_type=node_type,
            status=status,
            input_json="{}",
            output_json='{"result": "ok"}',
            cost_usd=cost_usd,
            started_at=datetime.now(timezone.utc),
            completed_at=datetime.now(timezone.utc),
            error_message=error_message,
            attempt=attempt,
        )
        db.add(ne)
        await db.commit()
        await db.refresh(ne)
        return ne


def _auth(jwt: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {jwt}"}


# ===================================================================
# POST /workflows -- create workflow
# ===================================================================


async def test_create_workflow_201(client):
    _, jwt = await _create_agent()

    resp = await client.post(
        f"{V3}/workflows",
        json={
            "name": "My Pipeline",
            "description": "Test pipeline",
            "graph_json": _simple_graph(),
        },
        headers=_auth(jwt),
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["name"] == "My Pipeline"
    assert body["status"] == "draft"


async def test_create_workflow_with_budget(client):
    _, jwt = await _create_agent()

    resp = await client.post(
        f"{V3}/workflows",
        json={
            "name": "Budgeted",
            "graph_json": _simple_graph(),
            "max_budget_usd": 50.0,
        },
        headers=_auth(jwt),
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["max_budget_usd"] == 50.0


async def test_create_workflow_invalid_graph_json(client):
    _, jwt = await _create_agent()

    resp = await client.post(
        f"{V3}/workflows",
        json={"name": "Bad JSON", "graph_json": "{{not-json}}"},
        headers=_auth(jwt),
    )
    assert resp.status_code == 400
    assert "valid JSON" in resp.json()["detail"]


async def test_create_workflow_no_auth(client):
    resp = await client.post(
        f"{V3}/workflows",
        json={"name": "X", "graph_json": "{}"},
    )
    assert resp.status_code in (401, 403)


async def test_create_workflow_missing_name(client):
    _, jwt = await _create_agent()
    resp = await client.post(
        f"{V3}/workflows",
        json={"graph_json": _simple_graph()},
        headers=_auth(jwt),
    )
    assert resp.status_code == 422


async def test_create_workflow_missing_graph_json(client):
    _, jwt = await _create_agent()
    resp = await client.post(
        f"{V3}/workflows",
        json={"name": "No graph"},
        headers=_auth(jwt),
    )
    assert resp.status_code == 422


async def test_create_workflow_empty_name_rejected(client):
    _, jwt = await _create_agent()
    resp = await client.post(
        f"{V3}/workflows",
        json={"name": "", "graph_json": _simple_graph()},
        headers=_auth(jwt),
    )
    assert resp.status_code == 422


async def test_create_workflow_response_contains_all_fields(client):
    _, jwt = await _create_agent()
    resp = await client.post(
        f"{V3}/workflows",
        json={
            "name": "Full Fields",
            "description": "Desc",
            "graph_json": _simple_graph(),
            "max_budget_usd": 10.0,
        },
        headers=_auth(jwt),
    )
    assert resp.status_code == 201
    body = resp.json()
    assert "id" in body
    assert body["description"] == "Desc"
    assert "owner_id" in body
    assert "version" in body
    assert "created_at" in body
    assert "updated_at" in body


async def test_create_workflow_with_complex_graph(client):
    _, jwt = await _create_agent()
    resp = await client.post(
        f"{V3}/workflows",
        json={
            "name": "Complex Graph",
            "graph_json": _two_node_graph(),
        },
        headers=_auth(jwt),
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["graph_json"] == _two_node_graph()


# ===================================================================
# GET /workflows -- list
# ===================================================================


async def test_list_workflows_empty(client):
    _, jwt = await _create_agent()
    resp = await client.get(f"{V3}/workflows", headers=_auth(jwt))
    assert resp.status_code == 200
    body = resp.json()
    assert body["workflows"] == []
    assert body["total"] == 0


async def test_list_workflows_returns_only_own(client):
    owner_id, owner_jwt = await _create_agent(name="list-owner")
    other_id, other_jwt = await _create_agent(name="list-other")

    await _create_workflow(owner_id, name="Owner WF")
    await _create_workflow(other_id, name="Other WF")

    resp = await client.get(f"{V3}/workflows", headers=_auth(owner_jwt))
    assert resp.status_code == 200
    body = resp.json()
    # Should only see own workflows
    assert body["total"] == 1
    assert body["workflows"][0]["name"] == "Owner WF"


async def test_list_workflows_pagination(client):
    owner_id, jwt = await _create_agent()
    for i in range(5):
        await _create_workflow(owner_id, name=f"WF-{i}")

    # The service applies limit at query level, then route slices by offset.
    # total = len(service_result), so with limit=2, total=2.
    resp = await client.get(
        f"{V3}/workflows",
        params={"limit": 2, "offset": 0},
        headers=_auth(jwt),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 2
    assert len(body["workflows"]) == 2

    # With default limit (50), all 5 should be returned
    resp2 = await client.get(f"{V3}/workflows", headers=_auth(jwt))
    assert resp2.status_code == 200
    assert resp2.json()["total"] == 5


async def test_list_workflows_with_offset(client):
    """Test the offset slicing logic in the list endpoint."""
    owner_id, jwt = await _create_agent()
    for i in range(4):
        await _create_workflow(owner_id, name=f"WF-{i}")

    # Offset = 2 should skip the first 2 from the service result
    resp = await client.get(
        f"{V3}/workflows",
        params={"limit": 50, "offset": 2},
        headers=_auth(jwt),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 4
    assert body["offset"] == 2
    assert len(body["workflows"]) == 2


async def test_list_workflows_response_shape(client):
    _, jwt = await _create_agent()
    resp = await client.get(f"{V3}/workflows", headers=_auth(jwt))
    assert resp.status_code == 200
    body = resp.json()
    assert "workflows" in body
    assert "total" in body
    assert "limit" in body
    assert "offset" in body


# ===================================================================
# GET /workflows/{id} -- get single
# ===================================================================


async def test_get_workflow_200(client):
    owner_id, jwt = await _create_agent()
    wf = await _create_workflow(owner_id, name="Fetch Me")

    resp = await client.get(f"{V3}/workflows/{wf.id}", headers=_auth(jwt))
    assert resp.status_code == 200
    body = resp.json()
    assert body["id"] == wf.id
    assert body["name"] == "Fetch Me"


async def test_get_workflow_404_nonexistent(client):
    _, jwt = await _create_agent()
    resp = await client.get(f"{V3}/workflows/fake-id", headers=_auth(jwt))
    assert resp.status_code == 404


async def test_get_workflow_404_other_owner(client):
    owner_id, _ = await _create_agent(name="wf-owner")
    _, other_jwt = await _create_agent(name="wf-viewer")

    wf = await _create_workflow(owner_id)
    resp = await client.get(f"{V3}/workflows/{wf.id}", headers=_auth(other_jwt))
    # Returns 404 (not 403) to avoid leaking existence
    assert resp.status_code == 404


async def test_get_workflow_includes_budget_field(client):
    owner_id, jwt = await _create_agent()
    wf = await _create_workflow(owner_id, max_budget_usd=Decimal("25.50"))

    resp = await client.get(f"{V3}/workflows/{wf.id}", headers=_auth(jwt))
    assert resp.status_code == 200
    assert resp.json()["max_budget_usd"] == 25.50


async def test_get_workflow_null_budget(client):
    owner_id, jwt = await _create_agent()
    wf = await _create_workflow(owner_id)

    resp = await client.get(f"{V3}/workflows/{wf.id}", headers=_auth(jwt))
    assert resp.status_code == 200
    assert resp.json()["max_budget_usd"] is None


# ===================================================================
# PUT /workflows/{id} -- update
# ===================================================================


async def test_update_workflow_200(client):
    owner_id, jwt = await _create_agent()
    wf = await _create_workflow(owner_id, name="Old Name")

    resp = await client.put(
        f"{V3}/workflows/{wf.id}",
        json={"name": "New Name", "description": "Updated desc"},
        headers=_auth(jwt),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["name"] == "New Name"
    assert body["description"] == "Updated desc"


async def test_update_workflow_change_graph(client):
    owner_id, jwt = await _create_agent()
    wf = await _create_workflow(owner_id)

    new_graph = _two_node_graph()
    resp = await client.put(
        f"{V3}/workflows/{wf.id}",
        json={"graph_json": new_graph},
        headers=_auth(jwt),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["graph_json"] == new_graph


async def test_update_workflow_invalid_graph(client):
    owner_id, jwt = await _create_agent()
    wf = await _create_workflow(owner_id)

    resp = await client.put(
        f"{V3}/workflows/{wf.id}",
        json={"graph_json": "broken-json"},
        headers=_auth(jwt),
    )
    assert resp.status_code == 400


async def test_update_workflow_change_status(client):
    owner_id, jwt = await _create_agent()
    wf = await _create_workflow(owner_id)

    resp = await client.put(
        f"{V3}/workflows/{wf.id}",
        json={"status": "active"},
        headers=_auth(jwt),
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "active"


async def test_update_workflow_status_to_archived(client):
    owner_id, jwt = await _create_agent()
    wf = await _create_workflow(owner_id)

    resp = await client.put(
        f"{V3}/workflows/{wf.id}",
        json={"status": "archived"},
        headers=_auth(jwt),
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "archived"


async def test_update_workflow_invalid_status(client):
    owner_id, jwt = await _create_agent()
    wf = await _create_workflow(owner_id)

    resp = await client.put(
        f"{V3}/workflows/{wf.id}",
        json={"status": "invalid"},
        headers=_auth(jwt),
    )
    assert resp.status_code == 422


async def test_update_workflow_404(client):
    _, jwt = await _create_agent()
    resp = await client.put(
        f"{V3}/workflows/fake-id",
        json={"name": "X"},
        headers=_auth(jwt),
    )
    assert resp.status_code == 404


async def test_update_workflow_403_non_owner(client):
    owner_id, _ = await _create_agent(name="upd-owner")
    _, other_jwt = await _create_agent(name="upd-other")

    wf = await _create_workflow(owner_id)
    resp = await client.put(
        f"{V3}/workflows/{wf.id}",
        json={"name": "Hijack"},
        headers=_auth(other_jwt),
    )
    assert resp.status_code == 403


async def test_update_workflow_budget(client):
    owner_id, jwt = await _create_agent()
    wf = await _create_workflow(owner_id)

    resp = await client.put(
        f"{V3}/workflows/{wf.id}",
        json={"max_budget_usd": 99.50},
        headers=_auth(jwt),
    )
    assert resp.status_code == 200
    assert resp.json()["max_budget_usd"] == 99.50


async def test_update_workflow_only_description(client):
    """Partial update with just description."""
    owner_id, jwt = await _create_agent()
    wf = await _create_workflow(owner_id, name="Keep Name")

    resp = await client.put(
        f"{V3}/workflows/{wf.id}",
        json={"description": "Only desc changed"},
        headers=_auth(jwt),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["name"] == "Keep Name"
    assert body["description"] == "Only desc changed"


async def test_update_workflow_empty_body(client):
    """Update with no fields should succeed (no-op update)."""
    owner_id, jwt = await _create_agent()
    wf = await _create_workflow(owner_id, name="Unchanged")

    resp = await client.put(
        f"{V3}/workflows/{wf.id}",
        json={},
        headers=_auth(jwt),
    )
    assert resp.status_code == 200
    assert resp.json()["name"] == "Unchanged"


async def test_update_workflow_multiple_fields(client):
    """Update name, description, status, and budget in one request."""
    owner_id, jwt = await _create_agent()
    wf = await _create_workflow(owner_id)

    resp = await client.put(
        f"{V3}/workflows/{wf.id}",
        json={
            "name": "Updated",
            "description": "New desc",
            "status": "active",
            "max_budget_usd": 42.0,
        },
        headers=_auth(jwt),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["name"] == "Updated"
    assert body["description"] == "New desc"
    assert body["status"] == "active"
    assert body["max_budget_usd"] == 42.0


# ===================================================================
# DELETE /workflows/{id} -- archive
# ===================================================================


async def test_delete_workflow_200(client):
    owner_id, jwt = await _create_agent()
    wf = await _create_workflow(owner_id)

    resp = await client.delete(f"{V3}/workflows/{wf.id}", headers=_auth(jwt))
    assert resp.status_code == 200
    assert resp.json()["detail"] == "Workflow archived"


async def test_delete_workflow_404(client):
    _, jwt = await _create_agent()
    resp = await client.delete(f"{V3}/workflows/missing", headers=_auth(jwt))
    assert resp.status_code == 404


async def test_delete_workflow_403_non_owner(client):
    owner_id, _ = await _create_agent(name="del-owner")
    _, other_jwt = await _create_agent(name="del-other")

    wf = await _create_workflow(owner_id)
    resp = await client.delete(
        f"{V3}/workflows/{wf.id}", headers=_auth(other_jwt),
    )
    assert resp.status_code == 403


async def test_delete_workflow_response_includes_id(client):
    owner_id, jwt = await _create_agent()
    wf = await _create_workflow(owner_id)

    resp = await client.delete(f"{V3}/workflows/{wf.id}", headers=_auth(jwt))
    assert resp.status_code == 200
    body = resp.json()
    assert body["workflow_id"] == wf.id


async def test_delete_workflow_then_get_shows_archived(client):
    """After delete, workflow should have status=archived."""
    owner_id, jwt = await _create_agent()
    wf = await _create_workflow(owner_id)

    del_resp = await client.delete(f"{V3}/workflows/{wf.id}", headers=_auth(jwt))
    assert del_resp.status_code == 200

    get_resp = await client.get(f"{V3}/workflows/{wf.id}", headers=_auth(jwt))
    assert get_resp.status_code == 200
    assert get_resp.json()["status"] == "archived"


# ===================================================================
# POST /workflows/{id}/execute -- start execution
# ===================================================================


async def test_execute_workflow_202(client):
    owner_id, jwt = await _create_agent()
    wf = await _create_workflow(owner_id)

    resp = await client.post(
        f"{V3}/workflows/{wf.id}/execute",
        json={"input_data": {"key": "value"}},
        headers=_auth(jwt),
    )
    assert resp.status_code == 202
    body = resp.json()
    assert "execution_id" in body
    assert body["status"] in ("pending", "running", "completed", "failed")


async def test_execute_workflow_404_nonexistent(client):
    _, jwt = await _create_agent()
    resp = await client.post(
        f"{V3}/workflows/nonexistent/execute",
        json={},
        headers=_auth(jwt),
    )
    assert resp.status_code == 404


async def test_execute_workflow_empty_input(client):
    owner_id, jwt = await _create_agent()
    wf = await _create_workflow(owner_id)

    resp = await client.post(
        f"{V3}/workflows/{wf.id}/execute",
        json={},
        headers=_auth(jwt),
    )
    assert resp.status_code == 202


async def test_execute_workflow_response_shape(client):
    owner_id, jwt = await _create_agent()
    wf = await _create_workflow(owner_id)

    resp = await client.post(
        f"{V3}/workflows/{wf.id}/execute",
        json={"input_data": {}},
        headers=_auth(jwt),
    )
    assert resp.status_code == 202
    body = resp.json()
    assert "execution_id" in body
    assert "status" in body


# ===================================================================
# GET /executions/{id} -- get execution details
# ===================================================================


async def test_get_execution_200(client):
    owner_id, jwt = await _create_agent()
    wf = await _create_workflow(owner_id)
    ex = await _create_execution(wf.id, owner_id, status="running")

    resp = await client.get(
        f"{V3}/executions/{ex.id}", headers=_auth(jwt),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["id"] == ex.id
    assert body["status"] == "running"


async def test_get_execution_404(client):
    _, jwt = await _create_agent()
    resp = await client.get(f"{V3}/executions/fake", headers=_auth(jwt))
    assert resp.status_code == 404


async def test_get_execution_403_wrong_initiator(client):
    owner_id, _ = await _create_agent(name="exec-ini")
    _, other_jwt = await _create_agent(name="exec-spy")

    wf = await _create_workflow(owner_id)
    ex = await _create_execution(wf.id, owner_id)

    resp = await client.get(
        f"{V3}/executions/{ex.id}", headers=_auth(other_jwt),
    )
    assert resp.status_code == 403


async def test_get_execution_response_fields(client):
    """Verify all expected fields in the execution response."""
    owner_id, jwt = await _create_agent()
    wf = await _create_workflow(owner_id)
    ex = await _create_execution(wf.id, owner_id, status="completed")

    resp = await client.get(f"{V3}/executions/{ex.id}", headers=_auth(jwt))
    assert resp.status_code == 200
    body = resp.json()
    assert "id" in body
    assert "workflow_id" in body
    assert "initiated_by" in body
    assert "status" in body
    assert "input_json" in body
    assert "total_cost_usd" in body
    assert "created_at" in body


# ===================================================================
# GET /executions/{id}/nodes -- node execution statuses
# ===================================================================


async def test_get_execution_nodes_200(client):
    owner_id, jwt = await _create_agent()
    wf = await _create_workflow(owner_id)
    ex = await _create_execution(wf.id, owner_id)
    await _create_node_execution(ex.id, node_id="step_1")
    await _create_node_execution(ex.id, node_id="step_2")

    resp = await client.get(
        f"{V3}/executions/{ex.id}/nodes", headers=_auth(jwt),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["execution_id"] == ex.id
    assert body["total"] == 2


async def test_get_execution_nodes_404(client):
    _, jwt = await _create_agent()
    resp = await client.get(
        f"{V3}/executions/missing/nodes", headers=_auth(jwt),
    )
    assert resp.status_code == 404


async def test_get_execution_nodes_403(client):
    owner_id, _ = await _create_agent(name="nodes-owner")
    _, spy_jwt = await _create_agent(name="nodes-spy")

    wf = await _create_workflow(owner_id)
    ex = await _create_execution(wf.id, owner_id)

    resp = await client.get(
        f"{V3}/executions/{ex.id}/nodes", headers=_auth(spy_jwt),
    )
    assert resp.status_code == 403


async def test_get_execution_nodes_empty(client):
    """Execution with no node executions returns empty list."""
    owner_id, jwt = await _create_agent()
    wf = await _create_workflow(owner_id)
    ex = await _create_execution(wf.id, owner_id)

    resp = await client.get(
        f"{V3}/executions/{ex.id}/nodes", headers=_auth(jwt),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["nodes"] == []
    assert body["total"] == 0


async def test_get_execution_nodes_response_shape(client):
    """Verify each node has expected fields."""
    owner_id, jwt = await _create_agent()
    wf = await _create_workflow(owner_id)
    ex = await _create_execution(wf.id, owner_id)
    await _create_node_execution(
        ex.id, node_id="step_1", node_type="agent_call",
        cost_usd=Decimal("0.10"),
    )

    resp = await client.get(
        f"{V3}/executions/{ex.id}/nodes", headers=_auth(jwt),
    )
    assert resp.status_code == 200
    node = resp.json()["nodes"][0]
    assert "id" in node
    assert "execution_id" in node
    assert "node_id" in node
    assert "node_type" in node
    assert "status" in node
    assert "cost_usd" in node
    assert "attempt" in node


# ===================================================================
# POST /executions/{id}/pause
# ===================================================================


async def test_pause_execution_running(client):
    owner_id, jwt = await _create_agent()
    wf = await _create_workflow(owner_id)
    ex = await _create_execution(wf.id, owner_id, status="running")

    resp = await client.post(
        f"{V3}/executions/{ex.id}/pause", headers=_auth(jwt),
    )
    assert resp.status_code == 200
    assert resp.json()["detail"] == "Execution paused"


async def test_pause_execution_409_not_running(client):
    owner_id, jwt = await _create_agent()
    wf = await _create_workflow(owner_id)
    ex = await _create_execution(wf.id, owner_id, status="pending")

    resp = await client.post(
        f"{V3}/executions/{ex.id}/pause", headers=_auth(jwt),
    )
    assert resp.status_code == 409


async def test_pause_execution_404(client):
    _, jwt = await _create_agent()
    resp = await client.post(
        f"{V3}/executions/nonexistent/pause", headers=_auth(jwt),
    )
    assert resp.status_code == 404


async def test_pause_execution_403(client):
    owner_id, _ = await _create_agent(name="pause-owner")
    _, other_jwt = await _create_agent(name="pause-other")

    wf = await _create_workflow(owner_id)
    ex = await _create_execution(wf.id, owner_id, status="running")

    resp = await client.post(
        f"{V3}/executions/{ex.id}/pause", headers=_auth(other_jwt),
    )
    assert resp.status_code == 403


async def test_pause_execution_409_completed(client):
    """Cannot pause a completed execution."""
    owner_id, jwt = await _create_agent()
    wf = await _create_workflow(owner_id)
    ex = await _create_execution(wf.id, owner_id, status="completed")

    resp = await client.post(
        f"{V3}/executions/{ex.id}/pause", headers=_auth(jwt),
    )
    assert resp.status_code == 409


async def test_pause_execution_409_cancelled(client):
    """Cannot pause a cancelled execution."""
    owner_id, jwt = await _create_agent()
    wf = await _create_workflow(owner_id)
    ex = await _create_execution(wf.id, owner_id, status="cancelled")

    resp = await client.post(
        f"{V3}/executions/{ex.id}/pause", headers=_auth(jwt),
    )
    assert resp.status_code == 409


async def test_pause_execution_response_includes_id(client):
    owner_id, jwt = await _create_agent()
    wf = await _create_workflow(owner_id)
    ex = await _create_execution(wf.id, owner_id, status="running")

    resp = await client.post(
        f"{V3}/executions/{ex.id}/pause", headers=_auth(jwt),
    )
    assert resp.status_code == 200
    assert resp.json()["execution_id"] == ex.id


# ===================================================================
# POST /executions/{id}/resume
# ===================================================================


async def test_resume_execution_paused(client):
    owner_id, jwt = await _create_agent()
    wf = await _create_workflow(owner_id)
    ex = await _create_execution(wf.id, owner_id, status="paused")

    resp = await client.post(
        f"{V3}/executions/{ex.id}/resume", headers=_auth(jwt),
    )
    assert resp.status_code == 200
    assert resp.json()["detail"] == "Execution resumed"


async def test_resume_execution_409_not_paused(client):
    owner_id, jwt = await _create_agent()
    wf = await _create_workflow(owner_id)
    ex = await _create_execution(wf.id, owner_id, status="running")

    resp = await client.post(
        f"{V3}/executions/{ex.id}/resume", headers=_auth(jwt),
    )
    assert resp.status_code == 409


async def test_resume_execution_404(client):
    _, jwt = await _create_agent()
    resp = await client.post(
        f"{V3}/executions/missing/resume", headers=_auth(jwt),
    )
    assert resp.status_code == 404


async def test_resume_execution_403(client):
    owner_id, _ = await _create_agent(name="resume-owner")
    _, other_jwt = await _create_agent(name="resume-other")

    wf = await _create_workflow(owner_id)
    ex = await _create_execution(wf.id, owner_id, status="paused")

    resp = await client.post(
        f"{V3}/executions/{ex.id}/resume", headers=_auth(other_jwt),
    )
    assert resp.status_code == 403


async def test_resume_execution_409_completed(client):
    owner_id, jwt = await _create_agent()
    wf = await _create_workflow(owner_id)
    ex = await _create_execution(wf.id, owner_id, status="completed")

    resp = await client.post(
        f"{V3}/executions/{ex.id}/resume", headers=_auth(jwt),
    )
    assert resp.status_code == 409


async def test_resume_execution_response_includes_id(client):
    owner_id, jwt = await _create_agent()
    wf = await _create_workflow(owner_id)
    ex = await _create_execution(wf.id, owner_id, status="paused")

    resp = await client.post(
        f"{V3}/executions/{ex.id}/resume", headers=_auth(jwt),
    )
    assert resp.status_code == 200
    assert resp.json()["execution_id"] == ex.id


# ===================================================================
# POST /executions/{id}/cancel
# ===================================================================


async def test_cancel_execution_pending(client):
    owner_id, jwt = await _create_agent()
    wf = await _create_workflow(owner_id)
    ex = await _create_execution(wf.id, owner_id, status="pending")

    resp = await client.post(
        f"{V3}/executions/{ex.id}/cancel", headers=_auth(jwt),
    )
    assert resp.status_code == 200
    assert resp.json()["detail"] == "Execution cancelled"


async def test_cancel_execution_running(client):
    owner_id, jwt = await _create_agent()
    wf = await _create_workflow(owner_id)
    ex = await _create_execution(wf.id, owner_id, status="running")

    resp = await client.post(
        f"{V3}/executions/{ex.id}/cancel", headers=_auth(jwt),
    )
    assert resp.status_code == 200


async def test_cancel_execution_paused(client):
    owner_id, jwt = await _create_agent()
    wf = await _create_workflow(owner_id)
    ex = await _create_execution(wf.id, owner_id, status="paused")

    resp = await client.post(
        f"{V3}/executions/{ex.id}/cancel", headers=_auth(jwt),
    )
    assert resp.status_code == 200


async def test_cancel_execution_409_completed(client):
    owner_id, jwt = await _create_agent()
    wf = await _create_workflow(owner_id)
    ex = await _create_execution(wf.id, owner_id, status="completed")

    resp = await client.post(
        f"{V3}/executions/{ex.id}/cancel", headers=_auth(jwt),
    )
    assert resp.status_code == 409


async def test_cancel_execution_409_already_cancelled(client):
    owner_id, jwt = await _create_agent()
    wf = await _create_workflow(owner_id)
    ex = await _create_execution(wf.id, owner_id, status="cancelled")

    resp = await client.post(
        f"{V3}/executions/{ex.id}/cancel", headers=_auth(jwt),
    )
    assert resp.status_code == 409


async def test_cancel_execution_404(client):
    _, jwt = await _create_agent()
    resp = await client.post(
        f"{V3}/executions/missing/cancel", headers=_auth(jwt),
    )
    assert resp.status_code == 404


async def test_cancel_execution_403(client):
    owner_id, _ = await _create_agent(name="cancel-owner")
    _, other_jwt = await _create_agent(name="cancel-other")

    wf = await _create_workflow(owner_id)
    ex = await _create_execution(wf.id, owner_id, status="running")

    resp = await client.post(
        f"{V3}/executions/{ex.id}/cancel", headers=_auth(other_jwt),
    )
    assert resp.status_code == 403


async def test_cancel_execution_409_failed(client):
    """Cannot cancel a failed execution."""
    owner_id, jwt = await _create_agent()
    wf = await _create_workflow(owner_id)
    ex = await _create_execution(wf.id, owner_id, status="failed")

    resp = await client.post(
        f"{V3}/executions/{ex.id}/cancel", headers=_auth(jwt),
    )
    assert resp.status_code == 409


async def test_cancel_execution_response_includes_id(client):
    owner_id, jwt = await _create_agent()
    wf = await _create_workflow(owner_id)
    ex = await _create_execution(wf.id, owner_id, status="running")

    resp = await client.post(
        f"{V3}/executions/{ex.id}/cancel", headers=_auth(jwt),
    )
    assert resp.status_code == 200
    assert resp.json()["execution_id"] == ex.id


# ===================================================================
# GET /executions/{id}/cost -- cost breakdown
# ===================================================================


async def test_get_execution_cost_200(client):
    owner_id, jwt = await _create_agent()
    wf = await _create_workflow(owner_id)
    ex = await _create_execution(wf.id, owner_id)
    await _create_node_execution(ex.id, node_id="n1", cost_usd=Decimal("0.10"))
    await _create_node_execution(ex.id, node_id="n2", cost_usd=Decimal("0.25"))

    resp = await client.get(
        f"{V3}/executions/{ex.id}/cost", headers=_auth(jwt),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["execution_id"] == ex.id
    assert body["total_cost_usd"] == pytest.approx(0.35, abs=0.01)
    assert len(body["node_costs"]) == 2


async def test_get_execution_cost_no_nodes(client):
    owner_id, jwt = await _create_agent()
    wf = await _create_workflow(owner_id)
    ex = await _create_execution(wf.id, owner_id)

    resp = await client.get(
        f"{V3}/executions/{ex.id}/cost", headers=_auth(jwt),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["total_cost_usd"] == 0.0
    assert body["node_costs"] == []


async def test_get_execution_cost_404(client):
    _, jwt = await _create_agent()
    resp = await client.get(
        f"{V3}/executions/nothing/cost", headers=_auth(jwt),
    )
    assert resp.status_code == 404


async def test_get_execution_cost_403(client):
    owner_id, _ = await _create_agent(name="cost-owner")
    _, spy_jwt = await _create_agent(name="cost-spy")

    wf = await _create_workflow(owner_id)
    ex = await _create_execution(wf.id, owner_id)

    resp = await client.get(
        f"{V3}/executions/{ex.id}/cost", headers=_auth(spy_jwt),
    )
    assert resp.status_code == 403


async def test_get_execution_cost_response_shape(client):
    """Verify the cost response includes workflow_id, status, and node_costs."""
    owner_id, jwt = await _create_agent()
    wf = await _create_workflow(owner_id)
    ex = await _create_execution(wf.id, owner_id, status="completed")
    await _create_node_execution(
        ex.id, node_id="s1", node_type="agent_call",
        cost_usd=Decimal("0.05"),
    )

    resp = await client.get(
        f"{V3}/executions/{ex.id}/cost", headers=_auth(jwt),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["workflow_id"] == wf.id
    assert body["status"] == "completed"
    node_cost = body["node_costs"][0]
    assert "node_id" in node_cost
    assert "node_type" in node_cost
    assert "cost_usd" in node_cost
    assert "status" in node_cost


async def test_get_execution_cost_multiple_node_types(client):
    """Cost breakdown with different node types."""
    owner_id, jwt = await _create_agent()
    wf = await _create_workflow(owner_id)
    ex = await _create_execution(wf.id, owner_id)
    await _create_node_execution(
        ex.id, node_id="agent-1", node_type="agent_call",
        cost_usd=Decimal("0.10"),
    )
    await _create_node_execution(
        ex.id, node_id="cond-1", node_type="condition",
        cost_usd=Decimal("0.00"),
    )

    resp = await client.get(
        f"{V3}/executions/{ex.id}/cost", headers=_auth(jwt),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["node_costs"]) == 2
    types = {n["node_type"] for n in body["node_costs"]}
    assert "agent_call" in types
    assert "condition" in types


async def test_get_execution_cost_with_zero_cost_node(client):
    """Node with None cost_usd should be reported as 0.0."""
    owner_id, jwt = await _create_agent()
    wf = await _create_workflow(owner_id)
    ex = await _create_execution(wf.id, owner_id)
    await _create_node_execution(
        ex.id, node_id="free", cost_usd=Decimal("0"),
    )

    resp = await client.get(
        f"{V3}/executions/{ex.id}/cost", headers=_auth(jwt),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["total_cost_usd"] == 0.0
    assert body["node_costs"][0]["cost_usd"] == 0.0


# ===================================================================
# GET /workflow-templates -- built-in templates (no auth)
# ===================================================================


async def test_list_workflow_templates_no_auth(client):
    resp = await client.get(f"{V3}/workflow-templates")
    assert resp.status_code == 200
    body = resp.json()
    assert "templates" in body
    assert body["total"] > 0
    keys = [t["key"] for t in body["templates"]]
    assert "sequential-pipeline" in keys
    assert "fan-out-fan-in" in keys
    assert "human-in-the-loop" in keys


async def test_list_workflow_templates_content(client):
    resp = await client.get(f"{V3}/workflow-templates")
    for tmpl in resp.json()["templates"]:
        assert "key" in tmpl
        assert "name" in tmpl
        assert "description" in tmpl
        assert "graph_json" in tmpl
        # graph_json should be parseable JSON
        graph = json.loads(tmpl["graph_json"])
        assert "nodes" in graph


# ===================================================================
# GET /templates -- alias for workflow-templates (no auth)
# ===================================================================


async def test_list_templates_alias_no_auth(client):
    resp = await client.get(f"{V3}/templates")
    assert resp.status_code == 200
    body = resp.json()
    assert "templates" in body
    assert body["total"] == 3


async def test_templates_and_workflow_templates_consistent(client):
    resp1 = await client.get(f"{V3}/templates")
    resp2 = await client.get(f"{V3}/workflow-templates")
    assert resp1.json() == resp2.json()


# ===================================================================
# Full lifecycle: create -> execute -> pause -> resume -> cancel
# ===================================================================


async def test_full_execution_lifecycle(client):
    owner_id, jwt = await _create_agent()
    headers = _auth(jwt)

    # Create
    create_resp = await client.post(
        f"{V3}/workflows",
        json={"name": "Lifecycle WF", "graph_json": _simple_graph()},
        headers=headers,
    )
    assert create_resp.status_code == 201
    wf_id = create_resp.json()["id"]

    # Execute
    exec_resp = await client.post(
        f"{V3}/workflows/{wf_id}/execute",
        json={"input_data": {"test": True}},
        headers=headers,
    )
    assert exec_resp.status_code == 202
    exec_id = exec_resp.json()["execution_id"]

    # Get execution
    get_resp = await client.get(
        f"{V3}/executions/{exec_id}", headers=headers,
    )
    assert get_resp.status_code == 200


async def test_full_lifecycle_create_list_update_delete(client):
    """Create, list, update, then archive a workflow via API."""
    owner_id, jwt = await _create_agent()
    headers = _auth(jwt)

    # Create
    create_resp = await client.post(
        f"{V3}/workflows",
        json={"name": "CRUD WF", "graph_json": _simple_graph()},
        headers=headers,
    )
    assert create_resp.status_code == 201
    wf_id = create_resp.json()["id"]

    # List -- should appear
    list_resp = await client.get(f"{V3}/workflows", headers=headers)
    assert list_resp.status_code == 200
    assert any(w["id"] == wf_id for w in list_resp.json()["workflows"])

    # Update
    upd_resp = await client.put(
        f"{V3}/workflows/{wf_id}",
        json={"name": "Updated CRUD WF"},
        headers=headers,
    )
    assert upd_resp.status_code == 200
    assert upd_resp.json()["name"] == "Updated CRUD WF"

    # Delete (archive)
    del_resp = await client.delete(
        f"{V3}/workflows/{wf_id}", headers=headers,
    )
    assert del_resp.status_code == 200
    assert del_resp.json()["detail"] == "Workflow archived"


# ===========================================================================
# Extra coverage tests -- uncovered code paths (appended by coverage push)
# ===========================================================================


async def test_create_workflow_with_description(client):
    """POST /workflows with description stores it."""
    _, jwt = await _create_agent()
    resp = await client.post(
        f"{V3}/workflows",
        json={
            "name": "desc-wf",
            "description": "A workflow with a description",
            "graph_json": _simple_graph(),
        },
        headers={"Authorization": f"Bearer {jwt}"},
    )
    assert resp.status_code == 201
    assert resp.json()["description"] == "A workflow with a description"


async def test_list_workflows_status_filter(client):
    """GET /workflows?status=active returns only active workflows."""
    _, jwt = await _create_agent()
    headers = {"Authorization": f"Bearer {jwt}"}
    # Create a workflow
    cr = await client.post(
        f"{V3}/workflows",
        json={"name": "stat-wf", "graph_json": _simple_graph()},
        headers=headers,
    )
    wid = cr.json()["id"]
    # Activate it
    await client.put(
        f"{V3}/workflows/{wid}",
        json={"status": "active"},
        headers=headers,
    )
    resp = await client.get(
        f"{V3}/workflows", params={"status": "active"}, headers=headers,
    )
    assert resp.status_code == 200
    for w in resp.json()["workflows"]:
        assert w["status"] == "active"


async def test_update_workflow_name_only(client):
    """PUT /workflows/{id} with only name field updates name."""
    _, jwt = await _create_agent()
    headers = {"Authorization": f"Bearer {jwt}"}
    cr = await client.post(
        f"{V3}/workflows",
        json={"name": "name-upd", "graph_json": _simple_graph()},
        headers=headers,
    )
    wid = cr.json()["id"]
    resp = await client.put(
        f"{V3}/workflows/{wid}",
        json={"name": "renamed-wf"},
        headers=headers,
    )
    assert resp.status_code == 200
    assert resp.json()["name"] == "renamed-wf"


async def test_execute_workflow_with_input_data(client):
    """POST /workflows/{id}/execute with input_data stores it."""
    _, jwt = await _create_agent()
    headers = {"Authorization": f"Bearer {jwt}"}
    cr = await client.post(
        f"{V3}/workflows",
        json={"name": "inp-wf", "graph_json": _simple_graph()},
        headers=headers,
    )
    wid = cr.json()["id"]
    resp = await client.post(
        f"{V3}/workflows/{wid}/execute",
        json={"input_data": {"key": "value"}},
        headers=headers,
    )
    assert resp.status_code == 202
    eid = resp.json()["execution_id"]
    # Get the execution to verify input was stored
    get_resp = await client.get(
        f"{V3}/executions/{eid}", headers=headers,
    )
    assert get_resp.status_code == 200
    body = get_resp.json()
    assert body["input_json"] is not None


async def test_get_execution_cost_with_node_costs(client):
    """GET /executions/{id}/cost returns node_costs array."""
    aid, jwt = await _create_agent()
    headers = {"Authorization": f"Bearer {jwt}"}
    cr = await client.post(
        f"{V3}/workflows",
        json={"name": "cost-wf", "graph_json": _two_node_graph()},
        headers=headers,
    )
    wid = cr.json()["id"]
    ex = await client.post(
        f"{V3}/workflows/{wid}/execute",
        json={}, headers=headers,
    )
    eid = ex.json()["execution_id"]
    resp = await client.get(
        f"{V3}/executions/{eid}/cost", headers=headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert "node_costs" in body
    assert "total_cost_usd" in body
    assert body["execution_id"] == eid
    assert body["workflow_id"] == wid


async def test_pause_already_paused_execution_409(client):
    """Pausing an already-paused execution returns 409."""
    _, jwt = await _create_agent()
    headers = {"Authorization": f"Bearer {jwt}"}
    cr = await client.post(
        f"{V3}/workflows",
        json={"name": "pp-wf", "graph_json": _simple_graph()},
        headers=headers,
    )
    wid = cr.json()["id"]
    ex = await client.post(
        f"{V3}/workflows/{wid}/execute",
        json={}, headers=headers,
    )
    eid = ex.json()["execution_id"]
    # Set execution to paused directly
    async with TestSession() as db:
        from sqlalchemy import select as sel
        r = await db.execute(
            sel(WorkflowExecution).where(WorkflowExecution.id == eid)
        )
        e = r.scalar_one()
        e.status = "paused"
        await db.commit()
    resp = await client.post(
        f"{V3}/executions/{eid}/pause", headers=headers,
    )
    assert resp.status_code == 409


async def test_resume_running_execution_409(client):
    """Resuming a running (not paused) execution returns 409."""
    _, jwt = await _create_agent()
    headers = {"Authorization": f"Bearer {jwt}"}
    cr = await client.post(
        f"{V3}/workflows",
        json={"name": "rr-wf", "graph_json": _simple_graph()},
        headers=headers,
    )
    wid = cr.json()["id"]
    ex = await client.post(
        f"{V3}/workflows/{wid}/execute",
        json={}, headers=headers,
    )
    eid = ex.json()["execution_id"]
    # Set to running
    async with TestSession() as db:
        from sqlalchemy import select as sel
        r = await db.execute(
            sel(WorkflowExecution).where(WorkflowExecution.id == eid)
        )
        e = r.scalar_one()
        e.status = "running"
        await db.commit()
    resp = await client.post(
        f"{V3}/executions/{eid}/resume", headers=headers,
    )
    assert resp.status_code == 409


async def test_workflow_templates_content(client):
    """GET /workflow-templates returns all expected template fields."""
    resp = await client.get(f"{V3}/workflow-templates")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] > 0
    for tmpl in body["templates"]:
        assert "key" in tmpl
        assert "name" in tmpl
        assert "description" in tmpl
        assert "graph_json" in tmpl


async def test_delete_then_get_shows_archived_status(client):
    """DELETE archives; subsequent GET returns archived status."""
    _, jwt = await _create_agent()
    headers = {"Authorization": f"Bearer {jwt}"}
    cr = await client.post(
        f"{V3}/workflows",
        json={"name": "del-arch-wf", "graph_json": _simple_graph()},
        headers=headers,
    )
    wid = cr.json()["id"]
    del_resp = await client.delete(
        f"{V3}/workflows/{wid}", headers=headers,
    )
    assert del_resp.status_code == 200
    get_resp = await client.get(
        f"{V3}/workflows/{wid}", headers=headers,
    )
    assert get_resp.status_code == 200
    assert get_resp.json()["status"] == "archived"


async def test_get_execution_nodes_returns_list(client):
    """GET /executions/{id}/nodes returns nodes array with total."""
    _, jwt = await _create_agent()
    headers = {"Authorization": f"Bearer {jwt}"}
    cr = await client.post(
        f"{V3}/workflows",
        json={"name": "nodes-wf", "graph_json": _two_node_graph()},
        headers=headers,
    )
    wid = cr.json()["id"]
    ex = await client.post(
        f"{V3}/workflows/{wid}/execute",
        json={}, headers=headers,
    )
    eid = ex.json()["execution_id"]
    resp = await client.get(
        f"{V3}/executions/{eid}/nodes", headers=headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert "nodes" in body
    assert "total" in body
    assert body["execution_id"] == eid


async def test_list_workflows_with_status_param(client):
    """GET /workflows?status=draft returns only draft workflows."""
    _, jwt = await _create_agent()
    headers = {"Authorization": f"Bearer {jwt}"}
    await client.post(
        f"{V3}/workflows",
        json={"name": "draft-wf-x", "graph_json": _simple_graph()},
        headers=headers,
    )
    resp = await client.get(
        f"{V3}/workflows", params={"status": "draft"}, headers=headers,
    )
    assert resp.status_code == 200
    for w in resp.json()["workflows"]:
        assert w["status"] == "draft"


async def test_templates_alias_returns_same_as_workflow_templates(client):
    """GET /templates is an alias returning same content as /workflow-templates."""
    r1 = await client.get(f"{V3}/workflow-templates")
    r2 = await client.get(f"{V3}/templates")
    assert r1.status_code == 200
    assert r2.status_code == 200
    assert r1.json()["total"] == r2.json()["total"]
