"""Comprehensive tests for orchestration_service — DAG-based workflow execution,
topological sorting, node dispatch, cost tracking, budget enforcement, and
execution lifecycle (pause/resume/cancel).

Uses in-memory SQLite via conftest fixtures.  asyncio_mode = "auto".
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from marketplace.models.workflow import (
    WorkflowDefinition,
    WorkflowExecution,
    WorkflowNodeExecution,
)
from marketplace.services import orchestration_service as svc


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _simple_graph(nodes: dict | None = None, edges: list | None = None) -> str:
    """Build a graph_json string from nodes and edges dicts."""
    return json.dumps({
        "nodes": nodes or {},
        "edges": edges or [],
    })


def _linear_graph() -> str:
    """A -> B -> C linear DAG."""
    return _simple_graph(
        nodes={
            "A": {"type": "agent_call", "config": {"endpoint": "http://a"}, "depends_on": []},
            "B": {"type": "agent_call", "config": {"endpoint": "http://b"}, "depends_on": ["A"]},
            "C": {"type": "agent_call", "config": {"endpoint": "http://c"}, "depends_on": ["B"]},
        },
    )


def _parallel_graph() -> str:
    """A and B run in parallel, then C depends on both."""
    return _simple_graph(
        nodes={
            "A": {"type": "agent_call", "config": {"endpoint": "http://a"}, "depends_on": []},
            "B": {"type": "agent_call", "config": {"endpoint": "http://b"}, "depends_on": []},
            "C": {"type": "agent_call", "config": {"endpoint": "http://c"}, "depends_on": ["A", "B"]},
        },
    )


def _cyclic_graph() -> str:
    """A -> B -> C -> A (cycle)."""
    return _simple_graph(
        nodes={
            "A": {"type": "agent_call", "config": {}, "depends_on": ["C"]},
            "B": {"type": "agent_call", "config": {}, "depends_on": ["A"]},
            "C": {"type": "agent_call", "config": {}, "depends_on": ["B"]},
        },
    )


# ---------------------------------------------------------------------------
# Workflow CRUD
# ---------------------------------------------------------------------------

class TestWorkflowCRUD:
    async def test_create_workflow(self, db: AsyncSession):
        wf = await svc.create_workflow(
            db, name="Test WF", graph_json=_linear_graph(),
            owner_id="owner-1", description="A test workflow",
        )
        assert wf.name == "Test WF"
        assert wf.owner_id == "owner-1"
        assert wf.description == "A test workflow"
        assert wf.id is not None

    async def test_create_workflow_with_budget(self, db: AsyncSession):
        wf = await svc.create_workflow(
            db, name="Budgeted", graph_json=_linear_graph(),
            owner_id="o-1", max_budget_usd=Decimal("5.00"),
        )
        assert wf.max_budget_usd == Decimal("5.00")

    async def test_get_workflow_success(self, db: AsyncSession):
        wf = await svc.create_workflow(
            db, name="Get Me", graph_json=_linear_graph(), owner_id="o-1",
        )
        fetched = await svc.get_workflow(db, wf.id)
        assert fetched is not None
        assert fetched.name == "Get Me"

    async def test_get_workflow_nonexistent(self, db: AsyncSession):
        result = await svc.get_workflow(db, "nonexistent-id")
        assert result is None

    async def test_list_workflows_empty(self, db: AsyncSession):
        result = await svc.list_workflows(db)
        assert result == []

    async def test_list_workflows_all(self, db: AsyncSession):
        await svc.create_workflow(db, name="WF1", graph_json=_linear_graph(), owner_id="o-1")
        await svc.create_workflow(db, name="WF2", graph_json=_linear_graph(), owner_id="o-2")
        result = await svc.list_workflows(db)
        assert len(result) == 2

    async def test_list_workflows_filter_by_owner(self, db: AsyncSession):
        await svc.create_workflow(db, name="Mine", graph_json=_linear_graph(), owner_id="o-1")
        await svc.create_workflow(db, name="Theirs", graph_json=_linear_graph(), owner_id="o-2")
        result = await svc.list_workflows(db, owner_id="o-1")
        assert len(result) == 1
        assert result[0].name == "Mine"

    async def test_list_workflows_filter_by_status(self, db: AsyncSession):
        wf = await svc.create_workflow(
            db, name="Active", graph_json=_linear_graph(), owner_id="o-1",
        )
        wf.status = "active"
        await db.commit()

        await svc.create_workflow(
            db, name="Draft", graph_json=_linear_graph(), owner_id="o-1",
        )

        result = await svc.list_workflows(db, status="active")
        assert len(result) == 1
        assert result[0].name == "Active"

    async def test_list_workflows_respects_limit(self, db: AsyncSession):
        for i in range(10):
            await svc.create_workflow(
                db, name=f"WF-{i}", graph_json=_linear_graph(), owner_id="o-1",
            )
        result = await svc.list_workflows(db, limit=3)
        assert len(result) == 3


# ---------------------------------------------------------------------------
# Topological sort
# ---------------------------------------------------------------------------

class TestTopologicalSort:
    def test_linear_graph_three_layers(self):
        graph = json.loads(_linear_graph())
        layers = svc._topological_sort_layers(graph)
        assert len(layers) == 3
        assert layers[0][0]["_node_id"] == "A"
        assert layers[1][0]["_node_id"] == "B"
        assert layers[2][0]["_node_id"] == "C"

    def test_parallel_graph_two_layers(self):
        graph = json.loads(_parallel_graph())
        layers = svc._topological_sort_layers(graph)
        assert len(layers) == 2
        # First layer has A and B
        first_ids = {n["_node_id"] for n in layers[0]}
        assert first_ids == {"A", "B"}
        # Second layer has C
        assert layers[1][0]["_node_id"] == "C"

    def test_single_node(self):
        graph = {"nodes": {"only": {"type": "agent_call", "config": {}}}, "edges": []}
        layers = svc._topological_sort_layers(graph)
        assert len(layers) == 1
        assert layers[0][0]["_node_id"] == "only"

    def test_empty_graph(self):
        graph = {"nodes": {}, "edges": []}
        layers = svc._topological_sort_layers(graph)
        assert layers == []

    def test_cycle_detection_raises(self):
        graph = json.loads(_cyclic_graph())
        with pytest.raises(ValueError, match="Cycle detected"):
            svc._topological_sort_layers(graph)

    def test_edge_based_dependencies(self):
        graph = {
            "nodes": {
                "X": {"type": "agent_call", "config": {}},
                "Y": {"type": "agent_call", "config": {}},
            },
            "edges": [{"from": "X", "to": "Y"}],
        }
        layers = svc._topological_sort_layers(graph)
        assert len(layers) == 2
        assert layers[0][0]["_node_id"] == "X"
        assert layers[1][0]["_node_id"] == "Y"

    def test_diamond_graph(self):
        """A -> B, A -> C, B -> D, C -> D (diamond shape)."""
        graph = {
            "nodes": {
                "A": {"type": "agent_call", "config": {}, "depends_on": []},
                "B": {"type": "agent_call", "config": {}, "depends_on": ["A"]},
                "C": {"type": "agent_call", "config": {}, "depends_on": ["A"]},
                "D": {"type": "agent_call", "config": {}, "depends_on": ["B", "C"]},
            },
            "edges": [],
        }
        layers = svc._topological_sort_layers(graph)
        assert len(layers) == 3
        assert layers[0][0]["_node_id"] == "A"
        second_ids = {n["_node_id"] for n in layers[1]}
        assert second_ids == {"B", "C"}
        assert layers[2][0]["_node_id"] == "D"


# ---------------------------------------------------------------------------
# _execute_condition
# ---------------------------------------------------------------------------

class TestExecuteCondition:
    def test_eq_true(self):
        result = svc._execute_condition(
            {"field": "status", "operator": "eq", "value": "active",
             "then_branch": "next", "else_branch": "skip"},
            {"status": "active"},
        )
        assert result["condition_met"] is True
        assert result["selected_branch"] == "next"

    def test_eq_false(self):
        result = svc._execute_condition(
            {"field": "status", "operator": "eq", "value": "active",
             "then_branch": "next", "else_branch": "skip"},
            {"status": "inactive"},
        )
        assert result["condition_met"] is False
        assert result["selected_branch"] == "skip"

    def test_neq(self):
        result = svc._execute_condition(
            {"field": "x", "operator": "neq", "value": 5},
            {"x": 10},
        )
        assert result["condition_met"] is True

    def test_gt(self):
        result = svc._execute_condition(
            {"field": "score", "operator": "gt", "value": 80},
            {"score": 90},
        )
        assert result["condition_met"] is True

    def test_gt_false(self):
        result = svc._execute_condition(
            {"field": "score", "operator": "gt", "value": 80},
            {"score": 70},
        )
        assert result["condition_met"] is False

    def test_lt(self):
        result = svc._execute_condition(
            {"field": "score", "operator": "lt", "value": 80},
            {"score": 70},
        )
        assert result["condition_met"] is True

    def test_gte(self):
        result = svc._execute_condition(
            {"field": "score", "operator": "gte", "value": 80},
            {"score": 80},
        )
        assert result["condition_met"] is True

    def test_lte(self):
        result = svc._execute_condition(
            {"field": "score", "operator": "lte", "value": 80},
            {"score": 80},
        )
        assert result["condition_met"] is True

    def test_in_operator(self):
        result = svc._execute_condition(
            {"field": "role", "operator": "in", "value": ["admin", "mod"]},
            {"role": "admin"},
        )
        assert result["condition_met"] is True

    def test_in_operator_false(self):
        result = svc._execute_condition(
            {"field": "role", "operator": "in", "value": ["admin", "mod"]},
            {"role": "user"},
        )
        assert result["condition_met"] is False

    def test_contains_operator(self):
        result = svc._execute_condition(
            {"field": "text", "operator": "contains", "value": "hello"},
            {"text": "say hello world"},
        )
        assert result["condition_met"] is True

    def test_nested_field(self):
        result = svc._execute_condition(
            {"field": "a.b.c", "operator": "eq", "value": 42},
            {"a": {"b": {"c": 42}}},
        )
        assert result["condition_met"] is True

    def test_missing_field_eq_none(self):
        result = svc._execute_condition(
            {"field": "missing", "operator": "eq", "value": None},
            {},
        )
        assert result["condition_met"] is True

    def test_unknown_operator_defaults_to_eq(self):
        result = svc._execute_condition(
            {"field": "x", "operator": "unknown_op", "value": 5},
            {"x": 5},
        )
        assert result["condition_met"] is True

    def test_gt_with_none_actual(self):
        result = svc._execute_condition(
            {"field": "missing", "operator": "gt", "value": 0},
            {},
        )
        assert result["condition_met"] is False


# ---------------------------------------------------------------------------
# _execute_agent_call
# ---------------------------------------------------------------------------

class TestExecuteAgentCall:
    async def test_no_endpoint_returns_error(self):
        result = await svc._execute_agent_call({}, {})
        assert "error" in result

    async def test_successful_post(self):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"output": "result"}
        mock_resp.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_resp)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_cls.return_value = mock_client

            result = await svc._execute_agent_call(
                {"endpoint": "http://agent/run"}, {"input": "data"},
            )

        assert result == {"output": "result"}

    async def test_successful_get(self):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"data": "get_result"}
        mock_resp.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_resp)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_cls.return_value = mock_client

            result = await svc._execute_agent_call(
                {"endpoint": "http://agent/data", "method": "GET"}, {"q": "test"},
            )

        assert result == {"data": "get_result"}

    async def test_http_error_returns_error_dict(self):
        mock_resp = MagicMock()
        mock_resp.status_code = 500
        mock_resp.raise_for_status = MagicMock(
            side_effect=httpx.HTTPStatusError(
                "Server Error", request=MagicMock(), response=mock_resp,
            )
        )

        with patch("httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_resp)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_cls.return_value = mock_client

            result = await svc._execute_agent_call(
                {"endpoint": "http://agent/fail"}, {},
            )

        assert "error" in result
        assert "500" in result["error"]

    async def test_request_error_returns_error_dict(self):
        with patch("httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(
                side_effect=httpx.RequestError("Connection refused"),
            )
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_cls.return_value = mock_client

            result = await svc._execute_agent_call(
                {"endpoint": "http://agent/down"}, {},
            )

        assert "error" in result
        assert "Connection refused" in result["error"]

    async def test_payload_merges_config_payload(self):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"ok": True}
        mock_resp.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_resp)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_cls.return_value = mock_client

            await svc._execute_agent_call(
                {"endpoint": "http://a", "payload": {"extra": "config"}},
                {"input": "data"},
            )
            call_kwargs = mock_client.post.call_args
            sent_json = call_kwargs.kwargs.get("json") or call_kwargs[1].get("json")
            assert sent_json["input"] == "data"
            assert sent_json["extra"] == "config"


# ---------------------------------------------------------------------------
# _execute_loop
# ---------------------------------------------------------------------------

class TestExecuteLoop:
    async def test_loop_without_endpoint(self):
        result = await svc._execute_loop(
            MagicMock(), "exec-1",
            {"iterator_field": "items"},
            {"items": [1, 2, 3]},
        )
        assert result["iterations"] == 3
        assert len(result["results"]) == 3
        assert result["results"][0] == {"item": 1, "index": 0}

    async def test_loop_with_endpoint(self):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"processed": True}
        mock_resp.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_resp)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_cls.return_value = mock_client

            result = await svc._execute_loop(
                MagicMock(), "exec-1",
                {"iterator_field": "items", "body_endpoint": "http://process"},
                {"items": ["a", "b"]},
            )

        assert result["iterations"] == 2

    async def test_loop_respects_max_iterations(self):
        result = await svc._execute_loop(
            MagicMock(), "exec-1",
            {"iterator_field": "items", "max_iterations": 2},
            {"items": [1, 2, 3, 4, 5]},
        )
        assert result["iterations"] == 2

    async def test_loop_non_list_returns_error(self):
        result = await svc._execute_loop(
            MagicMock(), "exec-1",
            {"iterator_field": "items"},
            {"items": "not-a-list"},
        )
        assert "error" in result

    async def test_loop_missing_field_iterates_empty(self):
        result = await svc._execute_loop(
            MagicMock(), "exec-1",
            {"iterator_field": "missing"},
            {},
        )
        assert result["iterations"] == 0


# ---------------------------------------------------------------------------
# _execute_human_approval
# ---------------------------------------------------------------------------

class TestExecuteHumanApproval:
    async def test_pauses_execution(self, db: AsyncSession):
        wf = await svc.create_workflow(
            db, name="Approval WF", graph_json=_linear_graph(), owner_id="o-1",
        )
        execution = WorkflowExecution(
            workflow_id=wf.id, initiated_by="user", status="running",
        )
        db.add(execution)
        await db.commit()
        await db.refresh(execution)

        result = await svc._execute_human_approval(
            db, execution.id, "node-1",
            {"message": "Please approve"},
        )
        assert result["status"] == "awaiting_approval"
        assert result["message"] == "Please approve"

        await db.refresh(execution)
        assert execution.status == "paused"

    async def test_default_message(self, db: AsyncSession):
        wf = await svc.create_workflow(
            db, name="WF", graph_json=_linear_graph(), owner_id="o-1",
        )
        execution = WorkflowExecution(
            workflow_id=wf.id, initiated_by="user", status="running",
        )
        db.add(execution)
        await db.commit()
        await db.refresh(execution)

        result = await svc._execute_human_approval(db, execution.id, "n-1", {})
        assert result["message"] == "Human approval required"


# ---------------------------------------------------------------------------
# Execution lifecycle (pause / resume / cancel)
# ---------------------------------------------------------------------------

class TestExecutionLifecycle:
    async def _create_execution(self, db: AsyncSession, status: str = "running"):
        wf = await svc.create_workflow(
            db, name="Lifecycle WF", graph_json=_linear_graph(), owner_id="o-1",
        )
        execution = WorkflowExecution(
            workflow_id=wf.id, initiated_by="user", status=status,
        )
        db.add(execution)
        await db.commit()
        await db.refresh(execution)
        return execution

    async def test_pause_running_execution(self, db: AsyncSession):
        execution = await self._create_execution(db, "running")
        result = await svc.pause_execution(db, execution.id)
        assert result is True
        await db.refresh(execution)
        assert execution.status == "paused"

    async def test_pause_non_running_fails(self, db: AsyncSession):
        execution = await self._create_execution(db, "pending")
        result = await svc.pause_execution(db, execution.id)
        assert result is False

    async def test_pause_nonexistent_fails(self, db: AsyncSession):
        result = await svc.pause_execution(db, "nonexistent")
        assert result is False

    async def test_resume_paused_execution(self, db: AsyncSession):
        execution = await self._create_execution(db, "paused")
        result = await svc.resume_execution(db, execution.id)
        assert result is True
        await db.refresh(execution)
        assert execution.status == "running"

    async def test_resume_non_paused_fails(self, db: AsyncSession):
        execution = await self._create_execution(db, "running")
        result = await svc.resume_execution(db, execution.id)
        assert result is False

    async def test_cancel_pending_execution(self, db: AsyncSession):
        execution = await self._create_execution(db, "pending")
        result = await svc.cancel_execution(db, execution.id)
        assert result is True
        await db.refresh(execution)
        assert execution.status == "cancelled"
        assert execution.completed_at is not None

    async def test_cancel_running_execution(self, db: AsyncSession):
        execution = await self._create_execution(db, "running")
        result = await svc.cancel_execution(db, execution.id)
        assert result is True

    async def test_cancel_paused_execution(self, db: AsyncSession):
        execution = await self._create_execution(db, "paused")
        result = await svc.cancel_execution(db, execution.id)
        assert result is True

    async def test_cancel_completed_fails(self, db: AsyncSession):
        execution = await self._create_execution(db, "completed")
        result = await svc.cancel_execution(db, execution.id)
        assert result is False

    async def test_cancel_failed_fails(self, db: AsyncSession):
        execution = await self._create_execution(db, "failed")
        result = await svc.cancel_execution(db, execution.id)
        assert result is False


# ---------------------------------------------------------------------------
# get_execution / get_execution_nodes / get_execution_cost
# ---------------------------------------------------------------------------

class TestExecutionQueries:
    async def test_get_execution_success(self, db: AsyncSession):
        wf = await svc.create_workflow(
            db, name="Query WF", graph_json=_linear_graph(), owner_id="o-1",
        )
        execution = WorkflowExecution(
            workflow_id=wf.id, initiated_by="user", status="completed",
        )
        db.add(execution)
        await db.commit()
        await db.refresh(execution)

        fetched = await svc.get_execution(db, execution.id)
        assert fetched is not None
        assert fetched.id == execution.id

    async def test_get_execution_nonexistent(self, db: AsyncSession):
        result = await svc.get_execution(db, "nonexistent")
        assert result is None

    async def test_get_execution_nodes(self, db: AsyncSession):
        wf = await svc.create_workflow(
            db, name="Nodes WF", graph_json=_linear_graph(), owner_id="o-1",
        )
        execution = WorkflowExecution(
            workflow_id=wf.id, initiated_by="user", status="completed",
        )
        db.add(execution)
        await db.commit()
        await db.refresh(execution)

        node = WorkflowNodeExecution(
            execution_id=execution.id,
            node_id="A",
            node_type="agent_call",
            status="completed",
            cost_usd=Decimal("0.05"),
            started_at=datetime.now(timezone.utc),
        )
        db.add(node)
        await db.commit()

        nodes = await svc.get_execution_nodes(db, execution.id)
        assert len(nodes) == 1
        assert nodes[0].node_id == "A"

    async def test_get_execution_cost(self, db: AsyncSession):
        wf = await svc.create_workflow(
            db, name="Cost WF", graph_json=_linear_graph(), owner_id="o-1",
        )
        execution = WorkflowExecution(
            workflow_id=wf.id, initiated_by="user", status="completed",
        )
        db.add(execution)
        await db.commit()
        await db.refresh(execution)

        for cost in [Decimal("0.05"), Decimal("0.10"), Decimal("0.15")]:
            db.add(WorkflowNodeExecution(
                execution_id=execution.id,
                node_id=f"node-{cost}",
                node_type="agent_call",
                status="completed",
                cost_usd=cost,
                started_at=datetime.now(timezone.utc),
            ))
        await db.commit()

        total = await svc.get_execution_cost(db, execution.id)
        assert total == Decimal("0.30")

    async def test_get_execution_cost_empty(self, db: AsyncSession):
        wf = await svc.create_workflow(
            db, name="Empty Cost", graph_json=_linear_graph(), owner_id="o-1",
        )
        execution = WorkflowExecution(
            workflow_id=wf.id, initiated_by="user", status="pending",
        )
        db.add(execution)
        await db.commit()
        await db.refresh(execution)

        total = await svc.get_execution_cost(db, execution.id)
        assert total == Decimal("0")

    async def test_get_execution_cost_with_null_costs(self, db: AsyncSession):
        wf = await svc.create_workflow(
            db, name="Null Cost", graph_json=_linear_graph(), owner_id="o-1",
        )
        execution = WorkflowExecution(
            workflow_id=wf.id, initiated_by="user", status="completed",
        )
        db.add(execution)
        await db.commit()
        await db.refresh(execution)

        db.add(WorkflowNodeExecution(
            execution_id=execution.id,
            node_id="n1",
            node_type="agent_call",
            status="completed",
            cost_usd=None,
            started_at=datetime.now(timezone.utc),
        ))
        await db.commit()

        total = await svc.get_execution_cost(db, execution.id)
        assert total == Decimal("0")


# ---------------------------------------------------------------------------
# execute_workflow (integration with DAG runner)
# ---------------------------------------------------------------------------

class TestExecuteWorkflow:
    async def test_nonexistent_workflow_raises(self, db: AsyncSession):
        with pytest.raises(ValueError, match="Workflow not found"):
            await svc.execute_workflow(db, "nonexistent", "user-1")

    async def test_single_node_workflow_completes(self, db: AsyncSession):
        graph = _simple_graph(
            nodes={"only": {"type": "condition", "config": {
                "field": "x", "operator": "eq", "value": 1,
            }}},
        )
        wf = await svc.create_workflow(
            db, name="Single", graph_json=graph, owner_id="o-1",
        )
        execution = await svc.execute_workflow(
            db, wf.id, "user-1", input_data={"x": 1},
        )
        assert execution.status == "completed"

    async def test_condition_node_workflow(self, db: AsyncSession):
        graph = _simple_graph(
            nodes={"check": {"type": "condition", "config": {
                "field": "score", "operator": "gt", "value": 50,
                "then_branch": "pass", "else_branch": "fail",
            }}},
        )
        wf = await svc.create_workflow(
            db, name="Condition WF", graph_json=graph, owner_id="o-1",
        )
        execution = await svc.execute_workflow(
            db, wf.id, "user-1", input_data={"score": 80},
        )
        assert execution.status == "completed"
        output = json.loads(execution.output_json)
        assert output["check"]["condition_met"] is True
        assert output["check"]["selected_branch"] == "pass"

    async def test_parallel_group_passthrough(self, db: AsyncSession):
        graph = _simple_graph(
            nodes={"pg": {"type": "parallel_group", "config": {}}},
        )
        wf = await svc.create_workflow(
            db, name="PG WF", graph_json=graph, owner_id="o-1",
        )
        execution = await svc.execute_workflow(
            db, wf.id, "user-1", input_data={"data": "hello"},
        )
        assert execution.status == "completed"

    async def test_unknown_node_type(self, db: AsyncSession):
        graph = _simple_graph(
            nodes={"unk": {"type": "magic_node", "config": {}}},
        )
        wf = await svc.create_workflow(
            db, name="Unknown", graph_json=graph, owner_id="o-1",
        )
        execution = await svc.execute_workflow(
            db, wf.id, "user-1",
        )
        assert execution.status == "completed"
        output = json.loads(execution.output_json)
        assert "error" in output["unk"]

    async def test_agent_call_node_fails_marks_execution_failed(self, db: AsyncSession):
        graph = _simple_graph(
            nodes={"call": {"type": "agent_call", "config": {
                "endpoint": "http://failing-agent/run",
            }}},
        )
        wf = await svc.create_workflow(
            db, name="Failing WF", graph_json=graph, owner_id="o-1",
        )

        with patch("httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(
                side_effect=Exception("Connection refused"),
            )
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_cls.return_value = mock_client

            execution = await svc.execute_workflow(
                db, wf.id, "user-1",
            )

        assert execution.status == "failed"
        assert execution.error_message is not None

    async def test_budget_exceeded_fails_execution(self, db: AsyncSession):
        graph = _simple_graph(
            nodes={"expensive": {"type": "condition", "config": {
                "field": "x", "operator": "eq", "value": 1,
            }}},
        )
        wf = await svc.create_workflow(
            db, name="Budget WF", graph_json=graph, owner_id="o-1",
            max_budget_usd=Decimal("0.001"),
        )

        # Patch get_execution_cost to return a high cost
        with patch.object(svc, "get_execution_cost", return_value=Decimal("10.00")):
            execution = await svc.execute_workflow(
                db, wf.id, "user-1", input_data={"x": 1},
            )

        assert execution.status == "failed"
        assert "Budget exceeded" in execution.error_message

    async def test_on_node_event_callback_fires(self, db: AsyncSession):
        graph = _simple_graph(
            nodes={"n1": {"type": "condition", "config": {
                "field": "x", "operator": "eq", "value": 1,
            }}},
        )
        wf = await svc.create_workflow(
            db, name="Callback WF", graph_json=graph, owner_id="o-1",
        )

        events_received = []

        async def _on_event(event_type, node_id, node_type, **kwargs):
            events_received.append((event_type, node_id, node_type))

        execution = await svc.execute_workflow(
            db, wf.id, "user-1", input_data={"x": 1},
            on_node_event=_on_event,
        )
        assert execution.status == "completed"
        event_types = [e[0] for e in events_received]
        assert "node_started" in event_types
        assert "node_completed" in event_types

    async def test_on_node_event_callback_failure_does_not_crash(self, db: AsyncSession):
        graph = _simple_graph(
            nodes={"n1": {"type": "condition", "config": {
                "field": "x", "operator": "eq", "value": 1,
            }}},
        )
        wf = await svc.create_workflow(
            db, name="Failing CB WF", graph_json=graph, owner_id="o-1",
        )

        async def _bad_callback(event_type, node_id, node_type, **kwargs):
            raise RuntimeError("callback crashed")

        execution = await svc.execute_workflow(
            db, wf.id, "user-1", input_data={"x": 1},
            on_node_event=_bad_callback,
        )
        # Should still complete despite callback failure
        assert execution.status == "completed"

    async def test_cyclic_graph_fails_execution(self, db: AsyncSession):
        wf = await svc.create_workflow(
            db, name="Cyclic WF", graph_json=_cyclic_graph(), owner_id="o-1",
        )
        execution = await svc.execute_workflow(db, wf.id, "user-1")
        assert execution.status == "failed"
        assert "Cycle detected" in (execution.error_message or "")


# ---------------------------------------------------------------------------
# _execute_subworkflow
# ---------------------------------------------------------------------------

class TestExecuteSubworkflow:
    async def test_no_workflow_id_returns_error(self, db: AsyncSession):
        result = await svc._execute_subworkflow(db, {}, {})
        assert "error" in result

    async def test_subworkflow_runs_inner_workflow(self, db: AsyncSession):
        inner_graph = _simple_graph(
            nodes={"inner": {"type": "condition", "config": {
                "field": "val", "operator": "eq", "value": 42,
            }}},
        )
        inner_wf = await svc.create_workflow(
            db, name="Inner", graph_json=inner_graph, owner_id="o-1",
        )
        result = await svc._execute_subworkflow(
            db,
            {"workflow_id": inner_wf.id, "initiated_by": "outer"},
            {"val": 42},
        )
        assert result["status"] == "completed"
        assert "sub_execution_id" in result


# ---------------------------------------------------------------------------
# _execute_node (dispatcher)
# ---------------------------------------------------------------------------

class TestExecuteNode:
    async def test_creates_node_execution_record(self, db: AsyncSession):
        wf = await svc.create_workflow(
            db, name="Node WF", graph_json=_linear_graph(), owner_id="o-1",
        )
        execution = WorkflowExecution(
            workflow_id=wf.id, initiated_by="user", status="running",
        )
        db.add(execution)
        await db.commit()
        await db.refresh(execution)

        node_def = {"_node_id": "test-node", "type": "condition", "config": {
            "field": "x", "operator": "eq", "value": 1,
        }}
        result = await svc._execute_node(
            db, execution.id, node_def, {"x": 1},
        )
        assert result["condition_met"] is True

        nodes = await svc.get_execution_nodes(db, execution.id)
        assert len(nodes) == 1
        assert nodes[0].status == "completed"

    async def test_failed_node_records_error(self, db: AsyncSession):
        wf = await svc.create_workflow(
            db, name="Fail Node WF", graph_json=_linear_graph(), owner_id="o-1",
        )
        execution = WorkflowExecution(
            workflow_id=wf.id, initiated_by="user", status="running",
        )
        db.add(execution)
        await db.commit()
        await db.refresh(execution)

        node_def = {
            "_node_id": "fail-node",
            "type": "agent_call",
            "config": {"endpoint": "http://fail"},
        }

        with patch("httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(side_effect=Exception("boom"))
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_cls.return_value = mock_client

            with pytest.raises(Exception, match="boom"):
                await svc._execute_node(
                    db, execution.id, node_def, {},
                )

        nodes = await svc.get_execution_nodes(db, execution.id)
        assert len(nodes) == 1
        assert nodes[0].status == "failed"
        assert "boom" in (nodes[0].error_message or "")


# ---------------------------------------------------------------------------
# OrchestrationService class wrapper
# ---------------------------------------------------------------------------

class TestOrchestrationServiceClass:
    async def test_create_workflow_delegates(self, db: AsyncSession):
        service = svc.OrchestrationService()
        wf = await service.create_workflow(
            db, name="Class WF", graph_json=_linear_graph(), owner_id="o-1",
        )
        assert wf.name == "Class WF"

    async def test_get_execution_delegates(self, db: AsyncSession):
        service = svc.OrchestrationService()
        wf = await service.create_workflow(
            db, name="Class Exec", graph_json=_linear_graph(), owner_id="o-1",
        )
        execution = WorkflowExecution(
            workflow_id=wf.id, initiated_by="user", status="completed",
        )
        db.add(execution)
        await db.commit()
        await db.refresh(execution)

        fetched = await service.get_execution(db, execution.id)
        assert fetched.id == execution.id
