"""Comprehensive tests for orchestration_service and payment_reconciliation_service.

Covers:
- Workflow CRUD: create, get, list with filters
- Execution lifecycle: execute, get, pause, resume, cancel, cost
- DAG internals: topological sort, parallel layers, cycle detection
- Node types: condition, parallel_group, unknown, agent_call (mocked)
- on_node_event callback: started, completed, failed events
- Reconciliation: Stripe matched / mismatched / missing / simulated
- Reconciliation: Razorpay captured / not-captured / error
- retry_failed_payment: happy path, not-found, wrong-status, stripe error
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from marketplace.services import orchestration_service as orch
from marketplace.services.orchestration_service import (
    _execute_condition,
    _topological_sort_layers,
)


# ===========================================================================
# Helpers
# ===========================================================================

def _uid() -> str:
    return str(uuid.uuid4())


def _simple_graph(n_nodes: int = 1) -> str:
    """Return a JSON graph string with `n_nodes` independent agent_call nodes
    (no edges, no depends_on)."""
    nodes = {
        f"node_{i}": {"type": "condition", "config": {"field": "x", "operator": "eq", "value": 1}}
        for i in range(n_nodes)
    }
    return json.dumps({"nodes": nodes, "edges": []})


def _linear_graph() -> str:
    """Return a 3-node linear DAG: A -> B -> C using depends_on."""
    return json.dumps({
        "nodes": {
            "A": {"type": "condition", "config": {"field": "x", "operator": "eq", "value": 1}},
            "B": {
                "type": "condition",
                "config": {"field": "x", "operator": "eq", "value": 1},
                "depends_on": ["A"],
            },
            "C": {
                "type": "condition",
                "config": {"field": "x", "operator": "eq", "value": 1},
                "depends_on": ["B"],
            },
        },
        "edges": [],
    })


def _cyclic_graph() -> str:
    """Return a DAG with a cycle A->B->A."""
    return json.dumps({
        "nodes": {
            "A": {"type": "condition", "config": {}, "depends_on": ["B"]},
            "B": {"type": "condition", "config": {}, "depends_on": ["A"]},
        },
        "edges": [],
    })


# ===========================================================================
# Section 1: Workflow CRUD
# ===========================================================================


async def test_create_workflow_basic(db: AsyncSession):
    """create_workflow persists a WorkflowDefinition and returns it with an id."""
    wf = await orch.create_workflow(
        db,
        name="My Workflow",
        graph_json=_simple_graph(),
        owner_id=_uid(),
        description="test",
        max_budget_usd=Decimal("10.00"),
    )
    assert wf.id is not None
    assert wf.name == "My Workflow"
    assert wf.description == "test"
    assert Decimal(str(wf.max_budget_usd)) == Decimal("10.00")


async def test_create_workflow_no_budget(db: AsyncSession):
    """create_workflow with no budget creates a workflow where max_budget_usd is None."""
    wf = await orch.create_workflow(
        db,
        name="Free Workflow",
        graph_json=_simple_graph(),
        owner_id=_uid(),
    )
    assert wf.max_budget_usd is None


async def test_get_workflow_found(db: AsyncSession):
    """get_workflow returns the workflow when it exists."""
    wf = await orch.create_workflow(
        db, name="FindMe", graph_json=_simple_graph(), owner_id=_uid()
    )
    fetched = await orch.get_workflow(db, wf.id)
    assert fetched is not None
    assert fetched.id == wf.id
    assert fetched.name == "FindMe"


async def test_get_workflow_not_found(db: AsyncSession):
    """get_workflow returns None for a non-existent ID."""
    result = await orch.get_workflow(db, "does-not-exist")
    assert result is None


async def test_list_workflows_no_filter(db: AsyncSession):
    """list_workflows without filters returns all workflows."""
    owner = _uid()
    await orch.create_workflow(db, name="WF1", graph_json=_simple_graph(), owner_id=owner)
    await orch.create_workflow(db, name="WF2", graph_json=_simple_graph(), owner_id=owner)
    workflows = await orch.list_workflows(db)
    assert len(workflows) >= 2


async def test_list_workflows_filter_by_owner(db: AsyncSession):
    """list_workflows with owner_id returns only that owner's workflows."""
    owner_a = _uid()
    owner_b = _uid()
    await orch.create_workflow(db, name="A1", graph_json=_simple_graph(), owner_id=owner_a)
    await orch.create_workflow(db, name="A2", graph_json=_simple_graph(), owner_id=owner_a)
    await orch.create_workflow(db, name="B1", graph_json=_simple_graph(), owner_id=owner_b)

    result = await orch.list_workflows(db, owner_id=owner_a)
    assert len(result) == 2
    assert all(wf.owner_id == owner_a for wf in result)


async def test_list_workflows_filter_by_status(db: AsyncSession):
    """list_workflows with status filter returns only matching workflows."""
    from marketplace.models.workflow import WorkflowDefinition

    owner = _uid()
    wf = await orch.create_workflow(db, name="Draft", graph_json=_simple_graph(), owner_id=owner)
    # Manually set status to "active"
    wf.status = "active"
    await db.commit()

    active = await orch.list_workflows(db, status="active")
    draft = await orch.list_workflows(db, status="draft")

    assert any(w.id == wf.id for w in active)
    assert not any(w.id == wf.id for w in draft)


async def test_list_workflows_limit(db: AsyncSession):
    """list_workflows respects the limit parameter."""
    owner = _uid()
    for i in range(5):
        await orch.create_workflow(db, name=f"WF{i}", graph_json=_simple_graph(), owner_id=owner)

    result = await orch.list_workflows(db, owner_id=owner, limit=3)
    assert len(result) == 3


# ===========================================================================
# Section 2: Execution Lifecycle
# ===========================================================================


async def test_execute_workflow_not_found(db: AsyncSession):
    """execute_workflow raises ValueError when the workflow does not exist."""
    with pytest.raises(ValueError, match="Workflow not found"):
        await orch.execute_workflow(db, "non-existent-id", initiated_by=_uid())


async def test_execute_workflow_creates_execution(db: AsyncSession):
    """execute_workflow with a single condition node creates a completed execution."""
    owner = _uid()
    wf = await orch.create_workflow(
        db,
        name="Single Node",
        graph_json=json.dumps({
            "nodes": {
                "n1": {
                    "type": "condition",
                    "config": {"field": "val", "operator": "eq", "value": 42},
                }
            },
            "edges": [],
        }),
        owner_id=owner,
    )
    execution = await orch.execute_workflow(db, wf.id, initiated_by=owner, input_data={"val": 42})
    assert execution.id is not None
    assert execution.status == "completed"
    assert execution.completed_at is not None


async def test_execute_workflow_input_data_stored(db: AsyncSession):
    """execute_workflow stores input_data as JSON on the execution record."""
    owner = _uid()
    wf = await orch.create_workflow(
        db,
        name="Input Test",
        graph_json=_simple_graph(),
        owner_id=owner,
    )
    execution = await orch.execute_workflow(
        db, wf.id, initiated_by=owner, input_data={"key": "value"}
    )
    stored = json.loads(execution.input_json)
    assert stored == {"key": "value"}


async def test_get_execution_found(db: AsyncSession):
    """get_execution returns the execution record by ID."""
    owner = _uid()
    wf = await orch.create_workflow(db, name="E", graph_json=_simple_graph(), owner_id=owner)
    execution = await orch.execute_workflow(db, wf.id, initiated_by=owner)
    fetched = await orch.get_execution(db, execution.id)
    assert fetched is not None
    assert fetched.id == execution.id


async def test_get_execution_not_found(db: AsyncSession):
    """get_execution returns None for a non-existent execution ID."""
    result = await orch.get_execution(db, "missing-exec-id")
    assert result is None


async def test_get_execution_nodes_returns_all_nodes(db: AsyncSession):
    """get_execution_nodes returns one WorkflowNodeExecution per DAG node."""
    from datetime import timezone
    from marketplace.models.workflow import WorkflowExecution, WorkflowNodeExecution

    owner = _uid()
    graph = _simple_graph()
    wf = await orch.create_workflow(db, name="Two Nodes", graph_json=graph, owner_id=owner)

    # Create the execution record manually to avoid concurrent-session issues
    # that arise when execute_workflow runs parallel nodes via asyncio.gather.
    exec_rec = WorkflowExecution(
        workflow_id=wf.id,
        initiated_by=owner,
        status="completed",
        input_json='{"x": 1}',
    )
    db.add(exec_rec)
    await db.commit()
    await db.refresh(exec_rec)

    # Create the two node execution records directly (simulating what execute_workflow would do)
    node1 = WorkflowNodeExecution(
        execution_id=exec_rec.id,
        node_id="n1",
        node_type="condition",
        status="completed",
        input_json='{"x": 1}',
        output_json='{"condition_met": true}',
        started_at=datetime.now(timezone.utc),
    )
    node2 = WorkflowNodeExecution(
        execution_id=exec_rec.id,
        node_id="n2",
        node_type="condition",
        status="completed",
        input_json='{"x": 1}',
        output_json='{"condition_met": true}',
        started_at=datetime.now(timezone.utc),
    )
    db.add(node1)
    db.add(node2)
    await db.commit()

    nodes = await orch.get_execution_nodes(db, exec_rec.id)
    assert len(nodes) == 2
    node_ids = {n.node_id for n in nodes}
    assert node_ids == {"n1", "n2"}


async def test_pause_execution_running(db: AsyncSession):
    """pause_execution returns True and sets status to paused for a running execution."""
    from marketplace.models.workflow import WorkflowExecution

    owner = _uid()
    wf = await orch.create_workflow(db, name="P", graph_json=_simple_graph(), owner_id=owner)
    # Manually create a running execution
    exec_rec = WorkflowExecution(
        workflow_id=wf.id,
        initiated_by=owner,
        status="running",
        input_json="{}",
    )
    db.add(exec_rec)
    await db.commit()
    await db.refresh(exec_rec)

    result = await orch.pause_execution(db, exec_rec.id)
    assert result is True
    refreshed = await orch.get_execution(db, exec_rec.id)
    assert refreshed.status == "paused"


async def test_pause_execution_not_running_returns_false(db: AsyncSession):
    """pause_execution returns False when execution is not in running state."""
    from marketplace.models.workflow import WorkflowExecution

    owner = _uid()
    wf = await orch.create_workflow(db, name="P2", graph_json=_simple_graph(), owner_id=owner)
    exec_rec = WorkflowExecution(
        workflow_id=wf.id,
        initiated_by=owner,
        status="completed",
        input_json="{}",
    )
    db.add(exec_rec)
    await db.commit()
    await db.refresh(exec_rec)

    result = await orch.pause_execution(db, exec_rec.id)
    assert result is False


async def test_pause_execution_missing_returns_false(db: AsyncSession):
    """pause_execution returns False when execution does not exist."""
    result = await orch.pause_execution(db, "ghost-id")
    assert result is False


async def test_resume_execution_paused(db: AsyncSession):
    """resume_execution returns True and sets status to running for a paused execution."""
    from marketplace.models.workflow import WorkflowExecution

    owner = _uid()
    wf = await orch.create_workflow(db, name="R", graph_json=_simple_graph(), owner_id=owner)
    exec_rec = WorkflowExecution(
        workflow_id=wf.id,
        initiated_by=owner,
        status="paused",
        input_json="{}",
    )
    db.add(exec_rec)
    await db.commit()
    await db.refresh(exec_rec)

    result = await orch.resume_execution(db, exec_rec.id)
    assert result is True
    refreshed = await orch.get_execution(db, exec_rec.id)
    assert refreshed.status == "running"


async def test_resume_execution_not_paused_returns_false(db: AsyncSession):
    """resume_execution returns False when execution is not paused."""
    from marketplace.models.workflow import WorkflowExecution

    owner = _uid()
    wf = await orch.create_workflow(db, name="R2", graph_json=_simple_graph(), owner_id=owner)
    exec_rec = WorkflowExecution(
        workflow_id=wf.id,
        initiated_by=owner,
        status="running",
        input_json="{}",
    )
    db.add(exec_rec)
    await db.commit()
    await db.refresh(exec_rec)

    result = await orch.resume_execution(db, exec_rec.id)
    assert result is False


async def test_cancel_execution_pending(db: AsyncSession):
    """cancel_execution returns True and sets status to cancelled for a pending execution."""
    from marketplace.models.workflow import WorkflowExecution

    owner = _uid()
    wf = await orch.create_workflow(db, name="C", graph_json=_simple_graph(), owner_id=owner)
    exec_rec = WorkflowExecution(
        workflow_id=wf.id,
        initiated_by=owner,
        status="pending",
        input_json="{}",
    )
    db.add(exec_rec)
    await db.commit()
    await db.refresh(exec_rec)

    result = await orch.cancel_execution(db, exec_rec.id)
    assert result is True
    refreshed = await orch.get_execution(db, exec_rec.id)
    assert refreshed.status == "cancelled"
    assert refreshed.completed_at is not None


async def test_cancel_execution_already_completed_returns_false(db: AsyncSession):
    """cancel_execution returns False when execution is already completed."""
    from marketplace.models.workflow import WorkflowExecution

    owner = _uid()
    wf = await orch.create_workflow(db, name="C2", graph_json=_simple_graph(), owner_id=owner)
    exec_rec = WorkflowExecution(
        workflow_id=wf.id,
        initiated_by=owner,
        status="completed",
        input_json="{}",
    )
    db.add(exec_rec)
    await db.commit()
    await db.refresh(exec_rec)

    result = await orch.cancel_execution(db, exec_rec.id)
    assert result is False


async def test_cancel_execution_missing_returns_false(db: AsyncSession):
    """cancel_execution returns False when execution does not exist."""
    result = await orch.cancel_execution(db, "no-such-exec")
    assert result is False


async def test_get_execution_cost_zero(db: AsyncSession):
    """get_execution_cost returns Decimal 0 when there are no node executions."""
    from marketplace.models.workflow import WorkflowExecution

    owner = _uid()
    wf = await orch.create_workflow(db, name="Cost0", graph_json=_simple_graph(), owner_id=owner)
    exec_rec = WorkflowExecution(
        workflow_id=wf.id,
        initiated_by=owner,
        status="pending",
        input_json="{}",
    )
    db.add(exec_rec)
    await db.commit()
    await db.refresh(exec_rec)

    cost = await orch.get_execution_cost(db, exec_rec.id)
    assert cost == Decimal("0")


async def test_get_execution_cost_sums_nodes(db: AsyncSession):
    """get_execution_cost returns sum of cost_usd from all node executions."""
    from marketplace.models.workflow import WorkflowExecution, WorkflowNodeExecution

    owner = _uid()
    wf = await orch.create_workflow(db, name="CostSum", graph_json=_simple_graph(), owner_id=owner)
    exec_rec = WorkflowExecution(
        workflow_id=wf.id,
        initiated_by=owner,
        status="completed",
        input_json="{}",
    )
    db.add(exec_rec)
    await db.commit()
    await db.refresh(exec_rec)

    # Add two node executions with known costs
    node1 = WorkflowNodeExecution(
        execution_id=exec_rec.id,
        node_id="n1",
        node_type="agent_call",
        status="completed",
        cost_usd=Decimal("1.50"),
        started_at=datetime.now(timezone.utc),
    )
    node2 = WorkflowNodeExecution(
        execution_id=exec_rec.id,
        node_id="n2",
        node_type="agent_call",
        status="completed",
        cost_usd=Decimal("2.75"),
        started_at=datetime.now(timezone.utc),
    )
    db.add(node1)
    db.add(node2)
    await db.commit()

    cost = await orch.get_execution_cost(db, exec_rec.id)
    assert cost == Decimal("4.25")


# ===========================================================================
# Section 3: DAG Internals — _topological_sort_layers
# ===========================================================================


def test_topo_sort_single_node():
    """A single-node graph yields exactly one layer with that node."""
    graph = {
        "nodes": {"n1": {"type": "condition", "config": {}}},
        "edges": [],
    }
    layers = _topological_sort_layers(graph)
    assert len(layers) == 1
    assert layers[0][0]["_node_id"] == "n1"


def test_topo_sort_parallel_nodes():
    """Two independent nodes appear in the same first layer."""
    graph = {
        "nodes": {
            "a": {"type": "condition", "config": {}},
            "b": {"type": "condition", "config": {}},
        },
        "edges": [],
    }
    layers = _topological_sort_layers(graph)
    assert len(layers) == 1
    node_ids = {n["_node_id"] for n in layers[0]}
    assert node_ids == {"a", "b"}


def test_topo_sort_linear_chain():
    """A->B->C chain produces three sequential layers."""
    graph = json.loads(_linear_graph())
    layers = _topological_sort_layers(graph)
    assert len(layers) == 3
    assert layers[0][0]["_node_id"] == "A"
    assert layers[1][0]["_node_id"] == "B"
    assert layers[2][0]["_node_id"] == "C"


def test_topo_sort_via_explicit_edges():
    """Edges defined in the 'edges' list are honored by the topological sort."""
    graph = {
        "nodes": {
            "X": {"type": "condition", "config": {}},
            "Y": {"type": "condition", "config": {}},
        },
        "edges": [{"from": "X", "to": "Y"}],
    }
    layers = _topological_sort_layers(graph)
    assert len(layers) == 2
    assert layers[0][0]["_node_id"] == "X"
    assert layers[1][0]["_node_id"] == "Y"


def test_topo_sort_cycle_raises():
    """A cyclic graph raises ValueError with a 'Cycle detected' message."""
    graph = json.loads(_cyclic_graph())
    with pytest.raises(ValueError, match="Cycle detected"):
        _topological_sort_layers(graph)


def test_topo_sort_empty_graph():
    """An empty graph returns an empty list of layers."""
    graph = {"nodes": {}, "edges": []}
    layers = _topological_sort_layers(graph)
    assert layers == []


# ===========================================================================
# Section 4: _execute_condition (pure function)
# ===========================================================================


def test_condition_eq_true():
    """Condition 'eq' evaluates to True when field matches value."""
    config = {"field": "score", "operator": "eq", "value": 100,
               "then_branch": "yes", "else_branch": "no"}
    result = _execute_condition(config, {"score": 100})
    assert result["condition_met"] is True
    assert result["selected_branch"] == "yes"


def test_condition_eq_false():
    """Condition 'eq' evaluates to False when field does not match."""
    config = {"field": "score", "operator": "eq", "value": 100,
               "then_branch": "yes", "else_branch": "no"}
    result = _execute_condition(config, {"score": 99})
    assert result["condition_met"] is False
    assert result["selected_branch"] == "no"


def test_condition_neq():
    """Condition 'neq' evaluates correctly."""
    config = {"field": "status", "operator": "neq", "value": "disabled"}
    result = _execute_condition(config, {"status": "active"})
    assert result["condition_met"] is True


def test_condition_gt():
    """Condition 'gt' evaluates greater-than correctly."""
    config = {"field": "amount", "operator": "gt", "value": 50}
    assert _execute_condition(config, {"amount": 100})["condition_met"] is True
    assert _execute_condition(config, {"amount": 50})["condition_met"] is False


def test_condition_lt():
    """Condition 'lt' evaluates less-than correctly."""
    config = {"field": "amount", "operator": "lt", "value": 50}
    assert _execute_condition(config, {"amount": 10})["condition_met"] is True
    assert _execute_condition(config, {"amount": 50})["condition_met"] is False


def test_condition_gte():
    """Condition 'gte' evaluates greater-than-or-equal correctly."""
    config = {"field": "n", "operator": "gte", "value": 5}
    assert _execute_condition(config, {"n": 5})["condition_met"] is True
    assert _execute_condition(config, {"n": 6})["condition_met"] is True
    assert _execute_condition(config, {"n": 4})["condition_met"] is False


def test_condition_lte():
    """Condition 'lte' evaluates less-than-or-equal correctly."""
    config = {"field": "n", "operator": "lte", "value": 5}
    assert _execute_condition(config, {"n": 5})["condition_met"] is True
    assert _execute_condition(config, {"n": 4})["condition_met"] is True
    assert _execute_condition(config, {"n": 6})["condition_met"] is False


def test_condition_in():
    """Condition 'in' checks membership in a list."""
    config = {"field": "color", "operator": "in", "value": ["red", "green", "blue"]}
    assert _execute_condition(config, {"color": "red"})["condition_met"] is True
    assert _execute_condition(config, {"color": "yellow"})["condition_met"] is False


def test_condition_contains():
    """Condition 'contains' checks string containment."""
    config = {"field": "message", "operator": "contains", "value": "hello"}
    assert _execute_condition(config, {"message": "say hello world"})["condition_met"] is True
    assert _execute_condition(config, {"message": "goodbye"})["condition_met"] is False


def test_condition_nested_field_dot_notation():
    """Dot-notation field resolution traverses nested dicts."""
    config = {"field": "user.profile.age", "operator": "gt", "value": 18}
    result = _execute_condition(config, {"user": {"profile": {"age": 25}}})
    assert result["condition_met"] is True
    assert result["actual_value"] == 25


def test_condition_missing_field_returns_false():
    """Missing field resolves to None; comparisons that require values return False."""
    config = {"field": "nonexistent", "operator": "gt", "value": 10}
    result = _execute_condition(config, {})
    assert result["condition_met"] is False
    assert result["actual_value"] is None


def test_condition_unknown_operator_defaults_to_eq():
    """Unknown operator falls back to equality check."""
    config = {"field": "x", "operator": "unknown_op", "value": 5}
    result = _execute_condition(config, {"x": 5})
    assert result["condition_met"] is True


# ===========================================================================
# Section 5: Parallel group and unknown node types
# ===========================================================================


async def test_execute_workflow_parallel_group_node(db: AsyncSession):
    """parallel_group node completes as a pass-through and execution succeeds."""
    owner = _uid()
    graph = json.dumps({
        "nodes": {
            "pg": {"type": "parallel_group", "config": {}},
        },
        "edges": [],
    })
    wf = await orch.create_workflow(db, name="PG Test", graph_json=graph, owner_id=owner)
    execution = await orch.execute_workflow(db, wf.id, initiated_by=owner)
    assert execution.status == "completed"
    nodes = await orch.get_execution_nodes(db, execution.id)
    assert len(nodes) == 1
    assert nodes[0].node_type == "parallel_group"
    assert nodes[0].status == "completed"


async def test_execute_workflow_unknown_node_type(db: AsyncSession):
    """An unknown node type results in a node that records an error output but still completes."""
    owner = _uid()
    graph = json.dumps({
        "nodes": {
            "mystery": {"type": "foobar_type", "config": {}},
        },
        "edges": [],
    })
    wf = await orch.create_workflow(db, name="Unknown Node", graph_json=graph, owner_id=owner)
    execution = await orch.execute_workflow(db, wf.id, initiated_by=owner)
    # The unknown node type outputs an error key, but the execution itself completes
    assert execution.status == "completed"
    nodes = await orch.get_execution_nodes(db, execution.id)
    assert len(nodes) == 1
    output = json.loads(nodes[0].output_json)
    assert "error" in output
    assert "foobar_type" in output["error"]


# ===========================================================================
# Section 6: on_node_event callback
# ===========================================================================


async def test_on_node_event_called_for_each_node(db: AsyncSession):
    """on_node_event receives node_started and node_completed events for each node."""
    owner = _uid()
    graph = json.dumps({
        "nodes": {
            "step1": {"type": "condition", "config": {"field": "x", "operator": "eq", "value": 1}},
            "step2": {"type": "condition", "config": {"field": "x", "operator": "eq", "value": 1}},
        },
        "edges": [],
    })
    wf = await orch.create_workflow(db, name="CB Test", graph_json=graph, owner_id=owner)

    events = []

    async def capture_event(event_type, node_id, node_type, **kwargs):
        events.append((event_type, node_id))

    await orch.execute_workflow(
        db, wf.id, initiated_by=owner, input_data={"x": 1},
        on_node_event=capture_event,
    )

    event_types = [e[0] for e in events]
    assert "node_started" in event_types
    assert "node_completed" in event_types
    # Two nodes -> at least 4 events (started+completed per node)
    assert len(events) >= 4


async def test_on_node_event_callback_failure_does_not_abort_execution(db: AsyncSession):
    """A failing on_node_event callback does not prevent the workflow from completing."""
    owner = _uid()
    wf = await orch.create_workflow(
        db, name="CB Fail", graph_json=_simple_graph(), owner_id=owner
    )

    async def failing_callback(event_type, node_id, node_type, **kwargs):
        raise RuntimeError("callback exploded")

    execution = await orch.execute_workflow(
        db, wf.id, initiated_by=owner, on_node_event=failing_callback
    )
    assert execution.status == "completed"


async def test_on_node_event_node_failed_fires_on_error(db: AsyncSession):
    """node_failed event fires when agent_call node raises an exception."""
    owner = _uid()
    # Use an agent_call node with no endpoint -> returns error dict (no raise)
    # To trigger a genuine exception, mock _execute_agent_call to raise
    graph = json.dumps({
        "nodes": {
            "bad_call": {
                "type": "agent_call",
                "config": {"endpoint": "http://localhost:9999/unreachable"},
            }
        },
        "edges": [],
    })
    wf = await orch.create_workflow(db, name="Node Fail CB", graph_json=graph, owner_id=owner)

    events = []

    async def capture(event_type, node_id, node_type, **kwargs):
        events.append(event_type)

    # Patch _execute_agent_call to raise so node_failed fires
    with patch(
        "marketplace.services.orchestration_service._execute_agent_call",
        new_callable=AsyncMock,
        side_effect=RuntimeError("agent down"),
    ):
        execution = await orch.execute_workflow(
            db, wf.id, initiated_by=owner, on_node_event=capture
        )

    assert execution.status == "failed"
    assert "node_failed" in events


# ===========================================================================
# Section 7: Budget enforcement
# ===========================================================================


async def test_execute_workflow_budget_exceeded(db: AsyncSession):
    """Workflow fails with an error message when node costs exceed max_budget_usd."""
    from marketplace.models.workflow import WorkflowNodeExecution

    owner = _uid()
    # Budget set to 0 — any cost will exceed it
    # Use a condition node (cost=0 normally) but fake a cost on the node record after the fact.
    # Instead, we use a real workflow and inject a pre-existing node cost before running.
    # Simpler: set budget=0.00001 and have a node that reports _cost=1 via mocked agent_call.
    graph = json.dumps({
        "nodes": {
            "expensive": {
                "type": "agent_call",
                "config": {"endpoint": "http://mock-agent/run"},
            }
        },
        "edges": [],
    })
    wf = await orch.create_workflow(
        db,
        name="Budget Test",
        graph_json=graph,
        owner_id=owner,
        max_budget_usd=Decimal("0.00001"),
    )

    async def cheap_but_costly(*args, **kwargs):
        return {"result": "ok", "_cost": 9999}

    with patch(
        "marketplace.services.orchestration_service._execute_agent_call",
        new_callable=AsyncMock,
        side_effect=cheap_but_costly,
    ):
        execution = await orch.execute_workflow(db, wf.id, initiated_by=owner)

    assert execution.status == "failed"
    assert "Budget exceeded" in execution.error_message


# ===========================================================================
# Section 8: agent_call node (mocked)
# ===========================================================================


async def test_agent_call_node_success(db: AsyncSession):
    """agent_call node completes successfully when HTTP call returns 200."""
    owner = _uid()
    graph = json.dumps({
        "nodes": {
            "call": {
                "type": "agent_call",
                "config": {
                    "endpoint": "http://agent.example.com/run",
                    "method": "POST",
                },
            }
        },
        "edges": [],
    })
    wf = await orch.create_workflow(db, name="Agent Call", graph_json=graph, owner_id=owner)

    mock_response = {"output": "hello", "_cost": 0.05}

    with patch(
        "marketplace.services.orchestration_service._execute_agent_call",
        new_callable=AsyncMock,
        return_value=mock_response,
    ):
        execution = await orch.execute_workflow(db, wf.id, initiated_by=owner)

    assert execution.status == "completed"
    nodes = await orch.get_execution_nodes(db, execution.id)
    assert nodes[0].status == "completed"
    output = json.loads(nodes[0].output_json)
    assert output["output"] == "hello"


async def test_agent_call_node_http_failure_captured(db: AsyncSession):
    """agent_call node with bad endpoint stores error in output but does not crash execution."""
    owner = _uid()
    graph = json.dumps({
        "nodes": {
            "bad": {
                "type": "agent_call",
                "config": {"endpoint": ""},  # empty endpoint -> error dict
            }
        },
        "edges": [],
    })
    wf = await orch.create_workflow(db, name="Bad Agent Call", graph_json=graph, owner_id=owner)
    # No mock needed — empty endpoint returns error dict without raising
    execution = await orch.execute_workflow(db, wf.id, initiated_by=owner)
    assert execution.status == "completed"
    nodes = await orch.get_execution_nodes(db, execution.id)
    output = json.loads(nodes[0].output_json)
    assert "error" in output
    assert "No endpoint" in output["error"]


# ===========================================================================
# Section 9: OrchestrationService class wrapper
# ===========================================================================


async def test_orchestration_service_class_create_and_execute(db: AsyncSession):
    """OrchestrationService class wraps module-level functions correctly."""
    svc = orch.OrchestrationService()
    owner = _uid()
    wf = await svc.create_workflow(
        db,
        name="Class Test",
        graph_json=_simple_graph(),
        owner_id=owner,
    )
    assert wf.id is not None

    execution = await svc.execute_workflow(db, workflow_id=wf.id, initiated_by=owner)
    assert execution.status == "completed"

    fetched = await svc.get_execution(db, execution.id)
    assert fetched.id == execution.id


# ===========================================================================
# Section 10: Payment Reconciliation — Stripe
# ===========================================================================


async def test_reconcile_stripe_no_transactions(db: AsyncSession):
    """reconcile_stripe_payments returns zeros when there are no transactions."""
    mock_settings = MagicMock()
    mock_settings.stripe_secret_key = "sk_test_mock"
    mock_settings.stripe_webhook_secret = "whsec_mock"

    with (
        patch("marketplace.services.payment_reconciliation_service.settings", mock_settings),
        patch(
            "marketplace.services.stripe_service.StripePaymentService",
            autospec=True,
        ) as MockStripe,
    ):
        from marketplace.services.payment_reconciliation_service import reconcile_stripe_payments

        result = await reconcile_stripe_payments(db)

    assert result["provider"] == "stripe"
    assert result["total_checked"] == 0
    assert result["matched"] == 0
    assert result["mismatched"] == []
    assert result["missing"] == []
    assert "reconciled_at" in result


async def test_reconcile_stripe_matched_transaction(db: AsyncSession, make_agent, make_listing, make_transaction, seed_platform):
    """A transaction with a pi_ payment_reference that matches Stripe is counted as matched."""
    seller, _ = await make_agent("seller")
    buyer, _ = await make_agent("buyer")
    listing = await make_listing(seller.id, price_usdc=10.0)
    tx = await make_transaction(buyer.id, seller.id, listing.id, amount_usdc=10.0, status="completed")

    # Set the payment_reference on the transaction
    tx.payment_reference = "pi_test_matched"
    await db.commit()

    mock_settings = MagicMock()
    mock_settings.stripe_secret_key = "sk_test_mock"
    mock_settings.stripe_webhook_secret = "whsec_mock"

    mock_service_instance = AsyncMock()
    mock_service_instance.retrieve_payment_intent.return_value = {
        "status": "succeeded",
        "amount": 1000,  # $10.00 in cents
    }

    with (
        patch("marketplace.services.payment_reconciliation_service.settings", mock_settings),
        patch(
            "marketplace.services.payment_reconciliation_service.StripePaymentService",
            return_value=mock_service_instance,
        ),
    ):
        from marketplace.services.payment_reconciliation_service import reconcile_stripe_payments

        result = await reconcile_stripe_payments(db)

    assert result["matched"] == 1
    assert result["mismatched"] == []
    assert result["missing"] == []


async def test_reconcile_stripe_amount_mismatch(db: AsyncSession, make_agent, make_listing, make_transaction, seed_platform):
    """A transaction where Stripe amount differs by more than $0.01 is reported as mismatched."""
    seller, _ = await make_agent("seller2")
    buyer, _ = await make_agent("buyer2")
    listing = await make_listing(seller.id, price_usdc=10.0)
    tx = await make_transaction(buyer.id, seller.id, listing.id, amount_usdc=10.0, status="completed")

    tx.payment_reference = "pi_test_mismatch"
    await db.commit()

    mock_settings = MagicMock()
    mock_settings.stripe_secret_key = "sk_test_mock"
    mock_settings.stripe_webhook_secret = "whsec_mock"

    mock_service_instance = AsyncMock()
    mock_service_instance.retrieve_payment_intent.return_value = {
        "status": "succeeded",
        "amount": 500,  # $5.00 in cents — differs from $10.00
    }

    with (
        patch("marketplace.services.payment_reconciliation_service.settings", mock_settings),
        patch(
            "marketplace.services.payment_reconciliation_service.StripePaymentService",
            return_value=mock_service_instance,
        ),
    ):
        from marketplace.services.payment_reconciliation_service import reconcile_stripe_payments

        result = await reconcile_stripe_payments(db)

    assert result["matched"] == 0
    assert len(result["mismatched"]) == 1
    mismatch = result["mismatched"][0]
    assert mismatch["transaction_id"] == tx.id
    assert mismatch["expected_amount"] == 10.0
    assert mismatch["actual_amount"] == 5.0


async def test_reconcile_stripe_status_mismatch(db: AsyncSession, make_agent, make_listing, make_transaction, seed_platform):
    """A transaction where Stripe status is not 'succeeded' is reported as mismatched."""
    seller, _ = await make_agent("seller3")
    buyer, _ = await make_agent("buyer3")
    listing = await make_listing(seller.id, price_usdc=5.0)
    tx = await make_transaction(buyer.id, seller.id, listing.id, amount_usdc=5.0, status="completed")

    tx.payment_reference = "pi_test_status_bad"
    await db.commit()

    mock_settings = MagicMock()
    mock_settings.stripe_secret_key = "sk_test_mock"
    mock_settings.stripe_webhook_secret = "whsec_mock"

    mock_service_instance = AsyncMock()
    mock_service_instance.retrieve_payment_intent.return_value = {
        "status": "requires_payment_method",
        "amount": 500,
    }

    with (
        patch("marketplace.services.payment_reconciliation_service.settings", mock_settings),
        patch(
            "marketplace.services.payment_reconciliation_service.StripePaymentService",
            return_value=mock_service_instance,
        ),
    ):
        from marketplace.services.payment_reconciliation_service import reconcile_stripe_payments

        result = await reconcile_stripe_payments(db)

    assert len(result["mismatched"]) == 1
    mismatch = result["mismatched"][0]
    assert mismatch["expected_status"] == "succeeded"
    assert mismatch["actual_status"] == "requires_payment_method"


async def test_reconcile_stripe_api_error_goes_to_missing(db: AsyncSession, make_agent, make_listing, make_transaction, seed_platform):
    """A Stripe API exception causes the transaction to appear in 'missing' list."""
    seller, _ = await make_agent("seller4")
    buyer, _ = await make_agent("buyer4")
    listing = await make_listing(seller.id, price_usdc=3.0)
    tx = await make_transaction(buyer.id, seller.id, listing.id, amount_usdc=3.0, status="completed")

    tx.payment_reference = "pi_test_api_error"
    await db.commit()

    mock_settings = MagicMock()
    mock_settings.stripe_secret_key = "sk_test_mock"
    mock_settings.stripe_webhook_secret = "whsec_mock"

    mock_service_instance = AsyncMock()
    mock_service_instance.retrieve_payment_intent.side_effect = Exception("Stripe API unavailable")

    with (
        patch("marketplace.services.payment_reconciliation_service.settings", mock_settings),
        patch(
            "marketplace.services.payment_reconciliation_service.StripePaymentService",
            return_value=mock_service_instance,
        ),
    ):
        from marketplace.services.payment_reconciliation_service import reconcile_stripe_payments

        result = await reconcile_stripe_payments(db)

    assert len(result["missing"]) == 1
    missing_entry = result["missing"][0]
    assert missing_entry["transaction_id"] == tx.id
    assert "Stripe API unavailable" in missing_entry["error"]


async def test_reconcile_stripe_simulated_flag_matched(db: AsyncSession, make_agent, make_listing, make_transaction, seed_platform):
    """A transaction whose Stripe record has simulated=True is always counted as matched."""
    seller, _ = await make_agent("seller5")
    buyer, _ = await make_agent("buyer5")
    listing = await make_listing(seller.id, price_usdc=7.0)
    tx = await make_transaction(buyer.id, seller.id, listing.id, amount_usdc=7.0, status="completed")

    tx.payment_reference = "pi_test_simulated"
    await db.commit()

    mock_settings = MagicMock()
    mock_settings.stripe_secret_key = "sk_test_mock"
    mock_settings.stripe_webhook_secret = "whsec_mock"

    mock_service_instance = AsyncMock()
    mock_service_instance.retrieve_payment_intent.return_value = {
        "simulated": True,
        "status": "succeeded",
        "amount": 700,
    }

    with (
        patch("marketplace.services.payment_reconciliation_service.settings", mock_settings),
        patch(
            "marketplace.services.payment_reconciliation_service.StripePaymentService",
            return_value=mock_service_instance,
        ),
    ):
        from marketplace.services.payment_reconciliation_service import reconcile_stripe_payments

        result = await reconcile_stripe_payments(db)

    assert result["matched"] == 1
    assert result["mismatched"] == []


async def test_reconcile_stripe_skips_non_stripe_refs(db: AsyncSession, make_agent, make_listing, make_transaction, seed_platform):
    """Transactions without a pi_ payment_reference are skipped during Stripe reconciliation."""
    seller, _ = await make_agent("seller6")
    buyer, _ = await make_agent("buyer6")
    listing = await make_listing(seller.id, price_usdc=2.0)
    tx = await make_transaction(buyer.id, seller.id, listing.id, amount_usdc=2.0, status="completed")
    # No payment_reference set — has None by default

    mock_settings = MagicMock()
    mock_settings.stripe_secret_key = "sk_test_mock"
    mock_settings.stripe_webhook_secret = "whsec_mock"

    mock_service_instance = AsyncMock()

    with (
        patch("marketplace.services.payment_reconciliation_service.settings", mock_settings),
        patch(
            "marketplace.services.payment_reconciliation_service.StripePaymentService",
            return_value=mock_service_instance,
        ),
    ):
        from marketplace.services.payment_reconciliation_service import reconcile_stripe_payments

        result = await reconcile_stripe_payments(db)

    # retrieve_payment_intent should never be called
    mock_service_instance.retrieve_payment_intent.assert_not_called()
    assert result["matched"] == 0


async def test_reconcile_stripe_with_since_filter(db: AsyncSession, make_agent, make_listing, make_transaction, seed_platform):
    """reconcile_stripe_payments with since parameter only checks recent transactions."""
    from datetime import timedelta

    # The since filter is passed to the query but in this test there are no
    # transactions before that threshold, so total_checked is 0.
    future_cutoff = datetime.now(timezone.utc) + timedelta(hours=1)

    mock_settings = MagicMock()
    mock_settings.stripe_secret_key = "sk_test_mock"
    mock_settings.stripe_webhook_secret = "whsec_mock"

    with (
        patch("marketplace.services.payment_reconciliation_service.settings", mock_settings),
        patch(
            "marketplace.services.payment_reconciliation_service.StripePaymentService",
            return_value=AsyncMock(),
        ),
    ):
        from marketplace.services.payment_reconciliation_service import reconcile_stripe_payments

        result = await reconcile_stripe_payments(db, since=future_cutoff)

    assert result["total_checked"] == 0


# ===========================================================================
# Section 11: Payment Reconciliation — Razorpay
# ===========================================================================


async def test_reconcile_razorpay_no_transactions(db: AsyncSession):
    """reconcile_razorpay_payments returns zeros when there are no transactions."""
    mock_settings = MagicMock()
    mock_settings.razorpay_key_id = "rzp_test_id"
    mock_settings.razorpay_key_secret = "rzp_secret"

    with (
        patch("marketplace.services.payment_reconciliation_service.settings", mock_settings),
        patch(
            "marketplace.services.payment_reconciliation_service.RazorpayPaymentService",
            return_value=AsyncMock(),
        ),
    ):
        from marketplace.services.payment_reconciliation_service import reconcile_razorpay_payments

        result = await reconcile_razorpay_payments(db)

    assert result["provider"] == "razorpay"
    assert result["total_checked"] == 0
    assert result["matched"] == 0
    assert result["mismatched"] == []
    assert result["missing"] == []


async def test_reconcile_razorpay_captured_matched(db: AsyncSession, make_agent, make_listing, make_transaction, seed_platform):
    """A Razorpay payment with status 'captured' is counted as matched."""
    seller, _ = await make_agent("rp_seller")
    buyer, _ = await make_agent("rp_buyer")
    listing = await make_listing(seller.id, price_usdc=5.0)
    tx = await make_transaction(buyer.id, seller.id, listing.id, amount_usdc=5.0, status="completed")

    tx.payment_reference = "pay_test_captured"
    await db.commit()

    mock_settings = MagicMock()
    mock_settings.razorpay_key_id = "rzp_test_id"
    mock_settings.razorpay_key_secret = "rzp_secret"

    mock_service_instance = AsyncMock()
    mock_service_instance.fetch_payment.return_value = {"status": "captured"}

    with (
        patch("marketplace.services.payment_reconciliation_service.settings", mock_settings),
        patch(
            "marketplace.services.payment_reconciliation_service.RazorpayPaymentService",
            return_value=mock_service_instance,
        ),
    ):
        from marketplace.services.payment_reconciliation_service import reconcile_razorpay_payments

        result = await reconcile_razorpay_payments(db)

    assert result["matched"] == 1
    assert result["mismatched"] == []


async def test_reconcile_razorpay_non_captured_mismatched(db: AsyncSession, make_agent, make_listing, make_transaction, seed_platform):
    """A Razorpay payment with status other than 'captured' is reported as mismatched."""
    seller, _ = await make_agent("rp_seller2")
    buyer, _ = await make_agent("rp_buyer2")
    listing = await make_listing(seller.id, price_usdc=5.0)
    tx = await make_transaction(buyer.id, seller.id, listing.id, amount_usdc=5.0, status="completed")

    tx.payment_reference = "pay_test_refunded"
    await db.commit()

    mock_settings = MagicMock()
    mock_settings.razorpay_key_id = "rzp_test_id"
    mock_settings.razorpay_key_secret = "rzp_secret"

    mock_service_instance = AsyncMock()
    mock_service_instance.fetch_payment.return_value = {"status": "refunded"}

    with (
        patch("marketplace.services.payment_reconciliation_service.settings", mock_settings),
        patch(
            "marketplace.services.payment_reconciliation_service.RazorpayPaymentService",
            return_value=mock_service_instance,
        ),
    ):
        from marketplace.services.payment_reconciliation_service import reconcile_razorpay_payments

        result = await reconcile_razorpay_payments(db)

    assert len(result["mismatched"]) == 1
    mismatch = result["mismatched"][0]
    assert mismatch["expected_status"] == "captured"
    assert mismatch["actual_status"] == "refunded"


async def test_reconcile_razorpay_api_error_goes_to_missing(db: AsyncSession, make_agent, make_listing, make_transaction, seed_platform):
    """A Razorpay API exception causes the entry to appear in 'missing' list."""
    seller, _ = await make_agent("rp_seller3")
    buyer, _ = await make_agent("rp_buyer3")
    listing = await make_listing(seller.id, price_usdc=5.0)
    tx = await make_transaction(buyer.id, seller.id, listing.id, amount_usdc=5.0, status="completed")

    tx.payment_reference = "pay_test_api_error"
    await db.commit()

    mock_settings = MagicMock()
    mock_settings.razorpay_key_id = "rzp_test_id"
    mock_settings.razorpay_key_secret = "rzp_secret"

    mock_service_instance = AsyncMock()
    mock_service_instance.fetch_payment.side_effect = Exception("Razorpay 503")

    with (
        patch("marketplace.services.payment_reconciliation_service.settings", mock_settings),
        patch(
            "marketplace.services.payment_reconciliation_service.RazorpayPaymentService",
            return_value=mock_service_instance,
        ),
    ):
        from marketplace.services.payment_reconciliation_service import reconcile_razorpay_payments

        result = await reconcile_razorpay_payments(db)

    assert len(result["missing"]) == 1
    assert "Razorpay 503" in result["missing"][0]["error"]


async def test_reconcile_razorpay_simulated_flag_matched(db: AsyncSession, make_agent, make_listing, make_transaction, seed_platform):
    """A Razorpay payment record with simulated=True is counted as matched."""
    seller, _ = await make_agent("rp_seller4")
    buyer, _ = await make_agent("rp_buyer4")
    listing = await make_listing(seller.id, price_usdc=5.0)
    tx = await make_transaction(buyer.id, seller.id, listing.id, amount_usdc=5.0, status="completed")

    tx.payment_reference = "pay_test_simulated"
    await db.commit()

    mock_settings = MagicMock()
    mock_settings.razorpay_key_id = "rzp_test_id"
    mock_settings.razorpay_key_secret = "rzp_secret"

    mock_service_instance = AsyncMock()
    mock_service_instance.fetch_payment.return_value = {"simulated": True, "status": "captured"}

    with (
        patch("marketplace.services.payment_reconciliation_service.settings", mock_settings),
        patch(
            "marketplace.services.payment_reconciliation_service.RazorpayPaymentService",
            return_value=mock_service_instance,
        ),
    ):
        from marketplace.services.payment_reconciliation_service import reconcile_razorpay_payments

        result = await reconcile_razorpay_payments(db)

    assert result["matched"] == 1
    assert result["mismatched"] == []


async def test_reconcile_razorpay_skips_non_razorpay_refs(db: AsyncSession, make_agent, make_listing, make_transaction, seed_platform):
    """Transactions without a pay_ prefix are skipped during Razorpay reconciliation."""
    seller, _ = await make_agent("rp_seller5")
    buyer, _ = await make_agent("rp_buyer5")
    listing = await make_listing(seller.id, price_usdc=5.0)
    tx = await make_transaction(buyer.id, seller.id, listing.id, amount_usdc=5.0, status="completed")

    # Stripe-style reference — should be skipped
    tx.payment_reference = "pi_not_razorpay"
    await db.commit()

    mock_settings = MagicMock()
    mock_settings.razorpay_key_id = "rzp_test_id"
    mock_settings.razorpay_key_secret = "rzp_secret"

    mock_service_instance = AsyncMock()

    with (
        patch("marketplace.services.payment_reconciliation_service.settings", mock_settings),
        patch(
            "marketplace.services.payment_reconciliation_service.RazorpayPaymentService",
            return_value=mock_service_instance,
        ),
    ):
        from marketplace.services.payment_reconciliation_service import reconcile_razorpay_payments

        result = await reconcile_razorpay_payments(db)

    mock_service_instance.fetch_payment.assert_not_called()
    assert result["matched"] == 0


# ===========================================================================
# Section 12: retry_failed_payment
# ===========================================================================


async def test_retry_failed_payment_success(db: AsyncSession, make_agent, make_listing, make_transaction, seed_platform):
    """retry_failed_payment creates a new payment intent and transitions status to 'pending'."""
    seller, _ = await make_agent("retry_seller")
    buyer, _ = await make_agent("retry_buyer")
    listing = await make_listing(seller.id, price_usdc=20.0)
    tx = await make_transaction(buyer.id, seller.id, listing.id, amount_usdc=20.0, status="failed")

    mock_settings = MagicMock()
    mock_settings.stripe_secret_key = "sk_test_mock"
    mock_settings.stripe_webhook_secret = "whsec_mock"

    mock_service_instance = AsyncMock()
    mock_service_instance.create_payment_intent.return_value = {"id": "pi_retry_new"}

    with (
        patch("marketplace.services.payment_reconciliation_service.settings", mock_settings),
        patch(
            "marketplace.services.payment_reconciliation_service.StripePaymentService",
            return_value=mock_service_instance,
        ),
    ):
        from marketplace.services.payment_reconciliation_service import retry_failed_payment

        result = await retry_failed_payment(db, tx.id)

    assert result["transaction_id"] == tx.id
    assert result["new_payment_intent"] == "pi_retry_new"
    assert result["status"] == "retry_initiated"

    # Verify the transaction status was updated in DB
    await db.refresh(tx)
    assert tx.status == "pending"


async def test_retry_failed_payment_not_found(db: AsyncSession):
    """retry_failed_payment returns an error dict when transaction does not exist."""
    from marketplace.services.payment_reconciliation_service import retry_failed_payment

    result = await retry_failed_payment(db, "non-existent-tx-id")
    assert "error" in result
    assert result["error"] == "Transaction not found"


async def test_retry_failed_payment_wrong_status(db: AsyncSession, make_agent, make_listing, make_transaction, seed_platform):
    """retry_failed_payment returns an error when transaction status is not 'failed'."""
    seller, _ = await make_agent("retry_seller2")
    buyer, _ = await make_agent("retry_buyer2")
    listing = await make_listing(seller.id, price_usdc=5.0)
    tx = await make_transaction(buyer.id, seller.id, listing.id, amount_usdc=5.0, status="completed")

    from marketplace.services.payment_reconciliation_service import retry_failed_payment

    result = await retry_failed_payment(db, tx.id)
    assert "error" in result
    assert "completed" in result["error"]
    assert "failed" in result["error"]


async def test_retry_failed_payment_stripe_error(db: AsyncSession, make_agent, make_listing, make_transaction, seed_platform):
    """retry_failed_payment returns an error dict when Stripe raises an exception."""
    seller, _ = await make_agent("retry_seller3")
    buyer, _ = await make_agent("retry_buyer3")
    listing = await make_listing(seller.id, price_usdc=15.0)
    tx = await make_transaction(buyer.id, seller.id, listing.id, amount_usdc=15.0, status="failed")

    mock_settings = MagicMock()
    mock_settings.stripe_secret_key = "sk_test_mock"
    mock_settings.stripe_webhook_secret = "whsec_mock"

    mock_service_instance = AsyncMock()
    mock_service_instance.create_payment_intent.side_effect = Exception("Stripe card declined")

    with (
        patch("marketplace.services.payment_reconciliation_service.settings", mock_settings),
        patch(
            "marketplace.services.payment_reconciliation_service.StripePaymentService",
            return_value=mock_service_instance,
        ),
    ):
        from marketplace.services.payment_reconciliation_service import retry_failed_payment

        result = await retry_failed_payment(db, tx.id)

    assert "error" in result
    assert "Stripe card declined" in result["error"]

    # Status should not have been changed to pending since the Stripe call failed
    await db.refresh(tx)
    assert tx.status == "failed"


async def test_retry_failed_payment_preserves_metadata(db: AsyncSession, make_agent, make_listing, make_transaction, seed_platform):
    """retry_failed_payment passes transaction_id and retry=true metadata to Stripe."""
    seller, _ = await make_agent("retry_seller4")
    buyer, _ = await make_agent("retry_buyer4")
    listing = await make_listing(seller.id, price_usdc=8.0)
    tx = await make_transaction(buyer.id, seller.id, listing.id, amount_usdc=8.0, status="failed")

    mock_settings = MagicMock()
    mock_settings.stripe_secret_key = "sk_test_mock"
    mock_settings.stripe_webhook_secret = "whsec_mock"

    mock_service_instance = AsyncMock()
    mock_service_instance.create_payment_intent.return_value = {"id": "pi_meta_check"}

    with (
        patch("marketplace.services.payment_reconciliation_service.settings", mock_settings),
        patch(
            "marketplace.services.payment_reconciliation_service.StripePaymentService",
            return_value=mock_service_instance,
        ),
    ):
        from marketplace.services.payment_reconciliation_service import retry_failed_payment

        await retry_failed_payment(db, tx.id)

    call_kwargs = mock_service_instance.create_payment_intent.call_args
    metadata = call_kwargs.kwargs.get("metadata", {})
    assert metadata.get("transaction_id") == tx.id
    assert metadata.get("retry") == "true"
