"""Orchestration engine tests — DAG parsing, topological sort, condition evaluation, and lifecycle."""

import json
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from marketplace.services.orchestration_service import (
    _execute_condition,
    _topological_sort_layers,
)


# ---------------------------------------------------------------------------
# Topological sort / DAG layer tests
# ---------------------------------------------------------------------------


class TestTopologicalSortLayers:
    """Tests for _topological_sort_layers (Kahn's algorithm)."""

    def test_single_node_graph(self):
        graph = {
            "nodes": {"a": {"type": "agent_call", "config": {}}},
            "edges": [],
        }
        layers = _topological_sort_layers(graph)
        assert len(layers) == 1
        assert layers[0][0]["_node_id"] == "a"

    def test_linear_chain(self):
        graph = {
            "nodes": {
                "a": {"type": "agent_call", "config": {}},
                "b": {"type": "agent_call", "config": {}, "depends_on": ["a"]},
                "c": {"type": "agent_call", "config": {}, "depends_on": ["b"]},
            },
            "edges": [],
        }
        layers = _topological_sort_layers(graph)
        assert len(layers) == 3
        assert layers[0][0]["_node_id"] == "a"
        assert layers[1][0]["_node_id"] == "b"
        assert layers[2][0]["_node_id"] == "c"

    def test_parallel_fan_out(self):
        graph = {
            "nodes": {
                "start": {"type": "agent_call", "config": {}},
                "b": {"type": "agent_call", "config": {}, "depends_on": ["start"]},
                "c": {"type": "agent_call", "config": {}, "depends_on": ["start"]},
                "d": {"type": "agent_call", "config": {}, "depends_on": ["start"]},
            },
            "edges": [],
        }
        layers = _topological_sort_layers(graph)
        assert len(layers) == 2
        assert layers[0][0]["_node_id"] == "start"
        layer_1_ids = {n["_node_id"] for n in layers[1]}
        assert layer_1_ids == {"b", "c", "d"}

    def test_diamond_dag(self):
        graph = {
            "nodes": {
                "a": {"type": "agent_call", "config": {}},
                "b": {"type": "agent_call", "config": {}, "depends_on": ["a"]},
                "c": {"type": "agent_call", "config": {}, "depends_on": ["a"]},
                "d": {"type": "agent_call", "config": {}, "depends_on": ["b", "c"]},
            },
            "edges": [],
        }
        layers = _topological_sort_layers(graph)
        assert len(layers) == 3
        assert layers[0][0]["_node_id"] == "a"
        layer_1_ids = {n["_node_id"] for n in layers[1]}
        assert layer_1_ids == {"b", "c"}
        assert layers[2][0]["_node_id"] == "d"

    def test_cycle_detection(self):
        graph = {
            "nodes": {
                "a": {"type": "agent_call", "config": {}, "depends_on": ["c"]},
                "b": {"type": "agent_call", "config": {}, "depends_on": ["a"]},
                "c": {"type": "agent_call", "config": {}, "depends_on": ["b"]},
            },
            "edges": [],
        }
        with pytest.raises(ValueError, match="Cycle detected"):
            _topological_sort_layers(graph)

    def test_empty_graph(self):
        graph = {"nodes": {}, "edges": []}
        layers = _topological_sort_layers(graph)
        assert len(layers) == 0

    def test_edges_based_dependencies(self):
        graph = {
            "nodes": {
                "a": {"type": "agent_call", "config": {}},
                "b": {"type": "agent_call", "config": {}},
            },
            "edges": [{"from": "a", "to": "b"}],
        }
        layers = _topological_sort_layers(graph)
        assert len(layers) == 2
        assert layers[0][0]["_node_id"] == "a"
        assert layers[1][0]["_node_id"] == "b"

    def test_mixed_edges_and_depends_on(self):
        graph = {
            "nodes": {
                "a": {"type": "agent_call", "config": {}},
                "b": {"type": "agent_call", "config": {}, "depends_on": ["a"]},
                "c": {"type": "agent_call", "config": {}},
            },
            "edges": [{"from": "b", "to": "c"}],
        }
        layers = _topological_sort_layers(graph)
        assert len(layers) == 3
        assert layers[0][0]["_node_id"] == "a"
        assert layers[1][0]["_node_id"] == "b"
        assert layers[2][0]["_node_id"] == "c"

    def test_wide_parallel_layer(self):
        nodes = {f"n{i}": {"type": "agent_call", "config": {}} for i in range(10)}
        graph = {"nodes": nodes, "edges": []}
        layers = _topological_sort_layers(graph)
        assert len(layers) == 1
        assert len(layers[0]) == 10

    def test_node_def_preserved(self):
        graph = {
            "nodes": {
                "a": {"type": "condition", "config": {"field": "x", "operator": "eq", "value": 1}},
            },
            "edges": [],
        }
        layers = _topological_sort_layers(graph)
        node = layers[0][0]
        assert node["type"] == "condition"
        assert node["config"]["field"] == "x"
        assert node["_node_id"] == "a"


# ---------------------------------------------------------------------------
# Condition evaluation tests
# ---------------------------------------------------------------------------


class TestConditionExecution:
    """Tests for _execute_condition — JSONPath-like expression evaluation."""

    def test_eq_operator(self):
        result = _execute_condition(
            {"field": "status", "operator": "eq", "value": "active"},
            {"status": "active"},
        )
        assert result["condition_met"] is True

    def test_neq_operator(self):
        result = _execute_condition(
            {"field": "status", "operator": "neq", "value": "active"},
            {"status": "inactive"},
        )
        assert result["condition_met"] is True

    def test_gt_operator(self):
        result = _execute_condition(
            {"field": "score", "operator": "gt", "value": 50},
            {"score": 75},
        )
        assert result["condition_met"] is True

    def test_gt_operator_false(self):
        result = _execute_condition(
            {"field": "score", "operator": "gt", "value": 100},
            {"score": 75},
        )
        assert result["condition_met"] is False

    def test_lt_operator(self):
        result = _execute_condition(
            {"field": "count", "operator": "lt", "value": 10},
            {"count": 5},
        )
        assert result["condition_met"] is True

    def test_gte_operator(self):
        result = _execute_condition(
            {"field": "count", "operator": "gte", "value": 5},
            {"count": 5},
        )
        assert result["condition_met"] is True

    def test_lte_operator(self):
        result = _execute_condition(
            {"field": "count", "operator": "lte", "value": 5},
            {"count": 5},
        )
        assert result["condition_met"] is True

    def test_in_operator(self):
        result = _execute_condition(
            {"field": "role", "operator": "in", "value": ["admin", "mod"]},
            {"role": "admin"},
        )
        assert result["condition_met"] is True

    def test_contains_operator(self):
        result = _execute_condition(
            {"field": "name", "operator": "contains", "value": "agent"},
            {"name": "my-agent-001"},
        )
        assert result["condition_met"] is True

    def test_nested_field_resolution(self):
        result = _execute_condition(
            {"field": "data.result.score", "operator": "gt", "value": 80},
            {"data": {"result": {"score": 95}}},
        )
        assert result["condition_met"] is True

    def test_missing_field_returns_none(self):
        result = _execute_condition(
            {"field": "nonexistent", "operator": "eq", "value": None},
            {"other": "data"},
        )
        assert result["condition_met"] is True
        assert result["actual_value"] is None

    def test_then_branch_selected(self):
        result = _execute_condition(
            {
                "field": "ok",
                "operator": "eq",
                "value": True,
                "then_branch": "node_success",
                "else_branch": "node_failure",
            },
            {"ok": True},
        )
        assert result["selected_branch"] == "node_success"

    def test_else_branch_selected(self):
        result = _execute_condition(
            {
                "field": "ok",
                "operator": "eq",
                "value": True,
                "then_branch": "node_success",
                "else_branch": "node_failure",
            },
            {"ok": False},
        )
        assert result["selected_branch"] == "node_failure"

    def test_default_operator_is_eq(self):
        result = _execute_condition(
            {"field": "x", "value": 42},
            {"x": 42},
        )
        assert result["condition_met"] is True

    def test_gt_with_none_values(self):
        result = _execute_condition(
            {"field": "missing", "operator": "gt", "value": 10},
            {},
        )
        assert result["condition_met"] is False

    def test_contains_with_none_actual(self):
        result = _execute_condition(
            {"field": "missing", "operator": "contains", "value": "x"},
            {},
        )
        assert result["condition_met"] is False

    def test_in_with_none_value(self):
        result = _execute_condition(
            {"field": "role", "operator": "in", "value": None},
            {"role": "admin"},
        )
        assert result["condition_met"] is False

    def test_deeply_nested_field(self):
        result = _execute_condition(
            {"field": "a.b.c.d", "operator": "eq", "value": "deep"},
            {"a": {"b": {"c": {"d": "deep"}}}},
        )
        assert result["condition_met"] is True

    def test_result_includes_field_and_actual(self):
        result = _execute_condition(
            {"field": "name", "operator": "eq", "value": "test"},
            {"name": "test"},
        )
        assert result["field"] == "name"
        assert result["actual_value"] == "test"

    def test_non_dict_traversal_returns_none(self):
        result = _execute_condition(
            {"field": "a.b", "operator": "eq", "value": None},
            {"a": "string_not_dict"},
        )
        assert result["actual_value"] is None
        assert result["condition_met"] is True


# ---------------------------------------------------------------------------
# Integration-style tests (mocked DB)
# ---------------------------------------------------------------------------


class TestWorkflowLifecycle:
    """Tests for workflow lifecycle operations using mocked DB sessions."""

    @pytest.fixture
    def mock_db(self):
        """Create a mock AsyncSession."""
        db = AsyncMock()
        db.commit = AsyncMock()
        db.refresh = AsyncMock()
        db.add = MagicMock()
        return db

    @pytest.mark.asyncio
    async def test_pause_non_running_returns_false(self, mock_db):
        from marketplace.services.orchestration_service import pause_execution

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = MagicMock(status="completed")
        mock_db.execute = AsyncMock(return_value=mock_result)

        result = await pause_execution(mock_db, "exec-123")
        assert result is False

    @pytest.mark.asyncio
    async def test_pause_running_returns_true(self, mock_db):
        from marketplace.services.orchestration_service import pause_execution

        mock_exec = MagicMock(status="running")
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_exec
        mock_db.execute = AsyncMock(return_value=mock_result)

        result = await pause_execution(mock_db, "exec-123")
        assert result is True
        assert mock_exec.status == "paused"

    @pytest.mark.asyncio
    async def test_resume_paused_returns_true(self, mock_db):
        from marketplace.services.orchestration_service import resume_execution

        mock_exec = MagicMock(status="paused")
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_exec
        mock_db.execute = AsyncMock(return_value=mock_result)

        result = await resume_execution(mock_db, "exec-123")
        assert result is True
        assert mock_exec.status == "running"

    @pytest.mark.asyncio
    async def test_resume_non_paused_returns_false(self, mock_db):
        from marketplace.services.orchestration_service import resume_execution

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = MagicMock(status="running")
        mock_db.execute = AsyncMock(return_value=mock_result)

        result = await resume_execution(mock_db, "exec-123")
        assert result is False

    @pytest.mark.asyncio
    async def test_cancel_pending_returns_true(self, mock_db):
        from marketplace.services.orchestration_service import cancel_execution

        mock_exec = MagicMock(status="pending")
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_exec
        mock_db.execute = AsyncMock(return_value=mock_result)

        result = await cancel_execution(mock_db, "exec-123")
        assert result is True
        assert mock_exec.status == "cancelled"

    @pytest.mark.asyncio
    async def test_cancel_completed_returns_false(self, mock_db):
        from marketplace.services.orchestration_service import cancel_execution

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = MagicMock(status="completed")
        mock_db.execute = AsyncMock(return_value=mock_result)

        result = await cancel_execution(mock_db, "exec-123")
        assert result is False

    @pytest.mark.asyncio
    async def test_cancel_nonexistent_returns_false(self, mock_db):
        from marketplace.services.orchestration_service import cancel_execution

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute = AsyncMock(return_value=mock_result)

        result = await cancel_execution(mock_db, "nonexistent")
        assert result is False

    @pytest.mark.asyncio
    async def test_get_execution_cost_empty(self, mock_db):
        from marketplace.services.orchestration_service import get_execution_cost

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_db.execute = AsyncMock(return_value=mock_result)

        cost = await get_execution_cost(mock_db, "exec-123")
        assert cost == Decimal("0")

    @pytest.mark.asyncio
    async def test_get_execution_cost_sum(self, mock_db):
        from marketplace.services.orchestration_service import get_execution_cost

        node1 = MagicMock(cost_usd=Decimal("0.50"))
        node2 = MagicMock(cost_usd=Decimal("1.25"))
        node3 = MagicMock(cost_usd=None)
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [node1, node2, node3]
        mock_db.execute = AsyncMock(return_value=mock_result)

        cost = await get_execution_cost(mock_db, "exec-123")
        assert cost == Decimal("1.75")
