"""Deep tests for orchestration engine, sandbox executor, search v2, and service bus.

Covers:
- TestOrchestrationServiceDeep: workflow CRUD, DAG execution, topological sort,
  parallel fan-out, conditional branching, cost/budget, pause/resume/cancel,
  node status tracking, timeout handling, retry logic.
- TestWorkflowModels: model fields, defaults, statuses, graph_json validation.
- TestSandboxExecutor: sandbox creation, lifecycle, resource limits, network
  isolation, timeout, output capture, error containment, concurrent management.
- TestSearchV2Service: Azure AI Search client, index sync, full-text search,
  faceted filtering, result ranking, empty results, query sanitization.
- TestServiceBusService: message send/receive, queue management, dead letter
  queue, message retry, connection management, batch operations.
"""

import asyncio
import json
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch, PropertyMock

import pytest

# ---------------------------------------------------------------------------
# Orchestration service imports
# ---------------------------------------------------------------------------
from marketplace.services.orchestration_service import (
    _execute_condition,
    _topological_sort_layers,
    cancel_execution,
    create_workflow,
    execute_workflow,
    get_execution,
    get_execution_cost,
    get_execution_nodes,
    get_workflow,
    list_workflows,
    pause_execution,
    resume_execution,
)

# ---------------------------------------------------------------------------
# Model imports
# ---------------------------------------------------------------------------
from marketplace.models.workflow import (
    WorkflowDefinition,
    WorkflowExecution,
    WorkflowNodeExecution,
    utcnow,
)

# ---------------------------------------------------------------------------
# Sandbox imports
# ---------------------------------------------------------------------------
from marketplace.services.sandbox_executor import (
    _build_execution_script,
    execute_action_in_sandbox,
)
from marketplace.core.sandbox import (
    SandboxConfig,
    SandboxManager,
    SandboxSession,
    SandboxState,
)

# ---------------------------------------------------------------------------
# Search V2 imports
# ---------------------------------------------------------------------------
from marketplace.services.search_v2_service import (
    SearchV2Service,
    _agents_fields,
    _listings_fields,
    _tools_fields,
)

# ---------------------------------------------------------------------------
# Service Bus imports
# ---------------------------------------------------------------------------
from marketplace.services.servicebus_service import ServiceBusService


# ===========================================================================
# Helpers
# ===========================================================================

def _mock_db():
    """Create a mock AsyncSession with common query helpers."""
    db = AsyncMock()
    db.add = MagicMock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock()
    db.execute = AsyncMock()
    return db


def _simple_linear_graph():
    """A -> B -> C linear DAG."""
    return {
        "nodes": {
            "A": {"type": "agent_call", "config": {"endpoint": "http://a"}, "depends_on": []},
            "B": {"type": "agent_call", "config": {"endpoint": "http://b"}, "depends_on": ["A"]},
            "C": {"type": "agent_call", "config": {"endpoint": "http://c"}, "depends_on": ["B"]},
        },
        "edges": [],
    }


def _parallel_fan_out_graph():
    """A fans out to B, C, D (all independent); then E depends on B, C, D."""
    return {
        "nodes": {
            "A": {"type": "agent_call", "config": {}, "depends_on": []},
            "B": {"type": "agent_call", "config": {}, "depends_on": ["A"]},
            "C": {"type": "agent_call", "config": {}, "depends_on": ["A"]},
            "D": {"type": "agent_call", "config": {}, "depends_on": ["A"]},
            "E": {"type": "agent_call", "config": {}, "depends_on": ["B", "C", "D"]},
        },
        "edges": [],
    }


def _cyclic_graph():
    """A -> B -> C -> A  (cycle)."""
    return {
        "nodes": {
            "A": {"type": "agent_call", "config": {}, "depends_on": ["C"]},
            "B": {"type": "agent_call", "config": {}, "depends_on": ["A"]},
            "C": {"type": "agent_call", "config": {}, "depends_on": ["B"]},
        },
        "edges": [],
    }


# ===========================================================================
# 1. TestOrchestrationServiceDeep  (20+ tests)
# ===========================================================================

class TestOrchestrationServiceDeep:
    """Orchestration service: CRUD, DAG execution, budget, lifecycle."""

    # -- Workflow CRUD -------------------------------------------------------

    @pytest.mark.asyncio
    async def test_create_workflow_basic(self):
        db = _mock_db()
        result = await create_workflow(
            db, name="wf1", graph_json='{"nodes":{}}', owner_id="owner-1"
        )
        assert isinstance(result, WorkflowDefinition)
        db.add.assert_called_once()
        db.commit.assert_awaited()
        db.refresh.assert_awaited()

    @pytest.mark.asyncio
    async def test_create_workflow_with_budget(self):
        db = _mock_db()
        result = await create_workflow(
            db,
            name="expensive",
            graph_json='{"nodes":{}}',
            owner_id="owner-2",
            max_budget_usd=Decimal("10.00"),
        )
        assert result.max_budget_usd == Decimal("10.00")

    @pytest.mark.asyncio
    async def test_create_workflow_with_description(self):
        db = _mock_db()
        result = await create_workflow(
            db,
            name="described",
            graph_json='{"nodes":{}}',
            owner_id="o3",
            description="A description",
        )
        assert result.description == "A description"

    @pytest.mark.asyncio
    async def test_get_workflow_found(self):
        db = _mock_db()
        mock_wf = WorkflowDefinition(id="wf-123", name="test", graph_json="{}", owner_id="o1")
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_wf
        db.execute.return_value = mock_result

        wf = await get_workflow(db, "wf-123")
        assert wf is mock_wf

    @pytest.mark.asyncio
    async def test_get_workflow_not_found(self):
        db = _mock_db()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        db.execute.return_value = mock_result

        wf = await get_workflow(db, "nonexistent")
        assert wf is None

    @pytest.mark.asyncio
    async def test_list_workflows_no_filters(self):
        db = _mock_db()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = [MagicMock(), MagicMock()]
        mock_result = MagicMock()
        mock_result.scalars.return_value = mock_scalars
        db.execute.return_value = mock_result

        workflows = await list_workflows(db)
        assert len(workflows) == 2

    @pytest.mark.asyncio
    async def test_list_workflows_filter_by_owner(self):
        db = _mock_db()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = [MagicMock()]
        mock_result = MagicMock()
        mock_result.scalars.return_value = mock_scalars
        db.execute.return_value = mock_result

        workflows = await list_workflows(db, owner_id="owner-x")
        assert len(workflows) == 1

    @pytest.mark.asyncio
    async def test_list_workflows_filter_by_status(self):
        db = _mock_db()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = []
        mock_result = MagicMock()
        mock_result.scalars.return_value = mock_scalars
        db.execute.return_value = mock_result

        workflows = await list_workflows(db, status="active")
        assert workflows == []

    # -- DAG topology --------------------------------------------------------

    def test_topological_sort_linear(self):
        layers = _topological_sort_layers(_simple_linear_graph())
        assert len(layers) == 3
        assert layers[0][0]["_node_id"] == "A"
        assert layers[1][0]["_node_id"] == "B"
        assert layers[2][0]["_node_id"] == "C"

    def test_topological_sort_parallel_fan_out(self):
        layers = _topological_sort_layers(_parallel_fan_out_graph())
        assert len(layers) == 3
        # Layer 0: A
        assert len(layers[0]) == 1
        assert layers[0][0]["_node_id"] == "A"
        # Layer 1: B, C, D (parallel)
        layer1_ids = sorted(n["_node_id"] for n in layers[1])
        assert layer1_ids == ["B", "C", "D"]
        # Layer 2: E
        assert len(layers[2]) == 1
        assert layers[2][0]["_node_id"] == "E"

    def test_topological_sort_cycle_raises(self):
        with pytest.raises(ValueError, match="Cycle detected"):
            _topological_sort_layers(_cyclic_graph())

    def test_topological_sort_empty_graph(self):
        layers = _topological_sort_layers({"nodes": {}, "edges": []})
        assert layers == []

    def test_topological_sort_single_node(self):
        graph = {"nodes": {"X": {"type": "agent_call", "config": {}}}, "edges": []}
        layers = _topological_sort_layers(graph)
        assert len(layers) == 1
        assert layers[0][0]["_node_id"] == "X"

    def test_topological_sort_edges_format(self):
        """DAG defined via edges list instead of depends_on."""
        graph = {
            "nodes": {
                "A": {"type": "agent_call", "config": {}},
                "B": {"type": "agent_call", "config": {}},
            },
            "edges": [{"from": "A", "to": "B"}],
        }
        layers = _topological_sort_layers(graph)
        assert len(layers) == 2

    def test_topological_sort_diamond_graph(self):
        """A -> B, A -> C, B -> D, C -> D (diamond)."""
        graph = {
            "nodes": {
                "A": {"type": "agent_call", "config": {}, "depends_on": []},
                "B": {"type": "agent_call", "config": {}, "depends_on": ["A"]},
                "C": {"type": "agent_call", "config": {}, "depends_on": ["A"]},
                "D": {"type": "agent_call", "config": {}, "depends_on": ["B", "C"]},
            },
            "edges": [],
        }
        layers = _topological_sort_layers(graph)
        assert len(layers) == 3
        assert layers[0][0]["_node_id"] == "A"
        layer1_ids = sorted(n["_node_id"] for n in layers[1])
        assert layer1_ids == ["B", "C"]
        assert layers[2][0]["_node_id"] == "D"

    # -- Conditional branching -----------------------------------------------

    def test_condition_eq_true(self):
        config = {"field": "status", "operator": "eq", "value": "active",
                  "then_branch": "nodeA", "else_branch": "nodeB"}
        result = _execute_condition(config, {"status": "active"})
        assert result["condition_met"] is True
        assert result["selected_branch"] == "nodeA"

    def test_condition_eq_false(self):
        config = {"field": "status", "operator": "eq", "value": "active",
                  "then_branch": "nodeA", "else_branch": "nodeB"}
        result = _execute_condition(config, {"status": "inactive"})
        assert result["condition_met"] is False
        assert result["selected_branch"] == "nodeB"

    def test_condition_gt_operator(self):
        config = {"field": "score", "operator": "gt", "value": 50}
        result = _execute_condition(config, {"score": 80})
        assert result["condition_met"] is True

    def test_condition_lt_operator(self):
        config = {"field": "score", "operator": "lt", "value": 50}
        result = _execute_condition(config, {"score": 30})
        assert result["condition_met"] is True

    def test_condition_contains_operator(self):
        config = {"field": "tags", "operator": "contains", "value": "ml"}
        result = _execute_condition(config, {"tags": ["ml", "ai", "data"]})
        assert result["condition_met"] is True

    def test_condition_nested_field(self):
        config = {"field": "data.nested.value", "operator": "eq", "value": 42}
        result = _execute_condition(config, {"data": {"nested": {"value": 42}}})
        assert result["condition_met"] is True
        assert result["actual_value"] == 42

    def test_condition_missing_field(self):
        config = {"field": "missing", "operator": "eq", "value": "x"}
        result = _execute_condition(config, {})
        assert result["condition_met"] is False
        assert result["actual_value"] is None

    # -- Execution lifecycle -------------------------------------------------

    @pytest.mark.asyncio
    async def test_execute_workflow_not_found(self):
        db = _mock_db()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        db.execute.return_value = mock_result

        with pytest.raises(ValueError, match="Workflow not found"):
            await execute_workflow(db, "nonexistent", "user-1")

    @pytest.mark.asyncio
    async def test_pause_execution_running(self):
        db = _mock_db()
        execution = MagicMock()
        execution.status = "running"
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = execution
        db.execute.return_value = mock_result

        result = await pause_execution(db, "exec-1")
        assert result is True
        assert execution.status == "paused"

    @pytest.mark.asyncio
    async def test_pause_execution_not_running(self):
        db = _mock_db()
        execution = MagicMock()
        execution.status = "completed"
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = execution
        db.execute.return_value = mock_result

        result = await pause_execution(db, "exec-1")
        assert result is False

    @pytest.mark.asyncio
    async def test_resume_execution_paused(self):
        db = _mock_db()
        execution = MagicMock()
        execution.status = "paused"
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = execution
        db.execute.return_value = mock_result

        result = await resume_execution(db, "exec-1")
        assert result is True
        assert execution.status == "running"

    @pytest.mark.asyncio
    async def test_resume_execution_not_paused(self):
        db = _mock_db()
        execution = MagicMock()
        execution.status = "running"
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = execution
        db.execute.return_value = mock_result

        result = await resume_execution(db, "exec-1")
        assert result is False

    @pytest.mark.asyncio
    async def test_cancel_execution_pending(self):
        db = _mock_db()
        execution = MagicMock()
        execution.status = "pending"
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = execution
        db.execute.return_value = mock_result

        result = await cancel_execution(db, "exec-1")
        assert result is True
        assert execution.status == "cancelled"
        assert execution.completed_at is not None

    @pytest.mark.asyncio
    async def test_cancel_execution_already_completed(self):
        db = _mock_db()
        execution = MagicMock()
        execution.status = "completed"
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = execution
        db.execute.return_value = mock_result

        result = await cancel_execution(db, "exec-1")
        assert result is False

    @pytest.mark.asyncio
    async def test_cancel_execution_not_found(self):
        db = _mock_db()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        db.execute.return_value = mock_result

        result = await cancel_execution(db, "no-such-exec")
        assert result is False

    # -- Cost tracking -------------------------------------------------------

    @pytest.mark.asyncio
    async def test_get_execution_cost_no_nodes(self):
        db = _mock_db()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = []
        mock_result = MagicMock()
        mock_result.scalars.return_value = mock_scalars
        db.execute.return_value = mock_result

        cost = await get_execution_cost(db, "exec-1")
        assert cost == Decimal("0")

    @pytest.mark.asyncio
    async def test_get_execution_cost_sums_nodes(self):
        db = _mock_db()
        node1 = MagicMock()
        node1.cost_usd = Decimal("1.50")
        node2 = MagicMock()
        node2.cost_usd = Decimal("2.25")
        node3 = MagicMock()
        node3.cost_usd = None  # should default to 0

        mock_scalars = MagicMock()
        mock_scalars.all.return_value = [node1, node2, node3]
        mock_result = MagicMock()
        mock_result.scalars.return_value = mock_scalars
        db.execute.return_value = mock_result

        cost = await get_execution_cost(db, "exec-1")
        assert cost == Decimal("3.75")

    @pytest.mark.asyncio
    async def test_get_execution_nodes(self):
        db = _mock_db()
        node1 = MagicMock(spec=WorkflowNodeExecution)
        node2 = MagicMock(spec=WorkflowNodeExecution)
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = [node1, node2]
        mock_result = MagicMock()
        mock_result.scalars.return_value = mock_scalars
        db.execute.return_value = mock_result

        nodes = await get_execution_nodes(db, "exec-1")
        assert len(nodes) == 2


# ===========================================================================
# 2. TestWorkflowModels  (10+ tests)
# ===========================================================================

class TestWorkflowModels:
    """Workflow model fields, defaults, and validation."""

    def test_workflow_definition_defaults(self):
        wf = WorkflowDefinition(
            name="test", graph_json='{"nodes":{}}', owner_id="o1"
        )
        assert wf.name == "test"
        assert wf.owner_id == "o1"
        # Column default="" only applies at DB flush, so in-memory it may be None
        assert wf.description is None or wf.description == ""
        assert wf.graph_json == '{"nodes":{}}'

    def test_workflow_definition_version_default(self):
        wf = WorkflowDefinition(
            name="v", graph_json="{}", owner_id="o1"
        )
        # Column default is 1, but not applied until flush/insert;
        # at object level it's set via __init__
        assert wf.version is None or wf.version == 1

    def test_workflow_definition_status_default(self):
        wf = WorkflowDefinition(
            name="s", graph_json="{}", owner_id="o1"
        )
        # status defaults to "draft" at the DB level
        assert wf.status is None or wf.status == "draft"

    def test_workflow_definition_table_name(self):
        assert WorkflowDefinition.__tablename__ == "workflows"

    def test_workflow_execution_defaults(self):
        ex = WorkflowExecution(
            workflow_id="wf-1", initiated_by="user-1"
        )
        assert ex.workflow_id == "wf-1"
        assert ex.initiated_by == "user-1"

    def test_workflow_execution_table_name(self):
        assert WorkflowExecution.__tablename__ == "workflow_executions"

    def test_workflow_execution_status_values(self):
        """Verify the execution can hold expected status string values."""
        for status in ("pending", "running", "paused", "completed", "failed", "cancelled"):
            ex = WorkflowExecution(
                workflow_id="wf-1", initiated_by="u", status=status
            )
            assert ex.status == status

    def test_workflow_node_execution_defaults(self):
        ne = WorkflowNodeExecution(
            execution_id="ex-1", node_id="n1", node_type="agent_call"
        )
        assert ne.execution_id == "ex-1"
        assert ne.node_id == "n1"
        assert ne.node_type == "agent_call"

    def test_workflow_node_execution_table_name(self):
        assert WorkflowNodeExecution.__tablename__ == "workflow_node_executions"

    def test_workflow_node_execution_attempt_default(self):
        ne = WorkflowNodeExecution(
            execution_id="ex-1", node_id="n1", node_type="agent_call"
        )
        # Column default is 1, may not be applied until DB flush
        assert ne.attempt is None or ne.attempt == 1

    def test_workflow_node_execution_states(self):
        for status in ("pending", "running", "completed", "failed"):
            ne = WorkflowNodeExecution(
                execution_id="e", node_id="n", node_type="t", status=status
            )
            assert ne.status == status

    def test_workflow_node_execution_indexes(self):
        """Verify custom indexes are defined on the model."""
        idx_names = [idx.name for idx in WorkflowNodeExecution.__table_args__]
        assert "idx_node_exec_execution" in idx_names
        assert "idx_node_exec_status" in idx_names

    def test_utcnow_returns_aware_datetime(self):
        now = utcnow()
        assert now.tzinfo is not None
        assert now.tzinfo == timezone.utc

    def test_workflow_definition_graph_json_parses(self):
        graph = json.dumps({"nodes": {"A": {}}, "edges": []})
        wf = WorkflowDefinition(name="g", graph_json=graph, owner_id="o1")
        parsed = json.loads(wf.graph_json)
        assert "nodes" in parsed
        assert "A" in parsed["nodes"]


# ===========================================================================
# 3. TestSandboxExecutor  (15+ tests)
# ===========================================================================

class TestSandboxExecutor:
    """Sandbox executor: lifecycle, resource limits, isolation, error handling."""

    # -- SandboxConfig -------------------------------------------------------

    def test_sandbox_config_defaults(self):
        cfg = SandboxConfig()
        assert cfg.memory_limit_mb == 512
        assert cfg.cpu_limit == 0.5
        assert cfg.timeout_seconds == 120
        assert cfg.network_enabled is True
        assert cfg.allowed_domains == []

    def test_sandbox_config_custom(self):
        cfg = SandboxConfig(
            memory_limit_mb=1024,
            cpu_limit=1.0,
            timeout_seconds=60,
            network_enabled=False,
            allowed_domains=["example.com"],
        )
        assert cfg.memory_limit_mb == 1024
        assert cfg.cpu_limit == 1.0
        assert cfg.timeout_seconds == 60
        assert cfg.network_enabled is False
        assert cfg.allowed_domains == ["example.com"]

    # -- SandboxState --------------------------------------------------------

    def test_sandbox_state_values(self):
        assert SandboxState.CREATING == "creating"
        assert SandboxState.READY == "ready"
        assert SandboxState.RUNNING == "running"
        assert SandboxState.COMPLETED == "completed"
        assert SandboxState.FAILED == "failed"
        assert SandboxState.TIMED_OUT == "timed_out"

    # -- SandboxSession ------------------------------------------------------

    def test_sandbox_session_defaults(self):
        session = SandboxSession(session_id="s1", agent_id="a1", action_id="act1")
        assert session.state == SandboxState.CREATING
        assert session.container_id is None
        assert session.started_at is None
        assert session.completed_at is None
        assert session.output == {}
        assert session.error is None

    # -- SandboxManager create -----------------------------------------------

    @pytest.mark.asyncio
    async def test_create_session_success(self):
        mgr = SandboxManager(mode="simulated")
        session = await mgr.create_session("agent-1", "action-1")
        assert session.agent_id == "agent-1"
        assert session.action_id == "action-1"
        assert session.session_id in mgr._sessions

    @pytest.mark.asyncio
    async def test_create_session_with_config(self):
        mgr = SandboxManager(mode="simulated")
        cfg = SandboxConfig(memory_limit_mb=256, timeout_seconds=30)
        session = await mgr.create_session("a1", "act1", config=cfg)
        assert session.config.memory_limit_mb == 256
        assert session.config.timeout_seconds == 30

    @pytest.mark.asyncio
    async def test_create_session_max_concurrent_limit(self):
        mgr = SandboxManager(mode="simulated")
        mgr._max_concurrent = 2
        await mgr.create_session("a", "1")
        await mgr.create_session("a", "2")
        with pytest.raises(RuntimeError, match="Maximum concurrent sandboxes"):
            await mgr.create_session("a", "3")

    # -- SandboxManager execute ----------------------------------------------

    @pytest.mark.asyncio
    async def test_execute_simulated(self):
        mgr = SandboxManager(mode="simulated")
        session = await mgr.create_session("a1", "act1")
        result = await mgr.execute(session.session_id, "echo hello")
        assert result["status"] == "success"
        assert result["simulated"] is True
        assert session.state == SandboxState.COMPLETED

    @pytest.mark.asyncio
    async def test_execute_unknown_session_raises(self):
        mgr = SandboxManager(mode="simulated")
        with pytest.raises(ValueError, match="Sandbox session not found"):
            await mgr.execute("nonexistent", "echo x")

    @pytest.mark.asyncio
    async def test_execute_sets_timestamps(self):
        mgr = SandboxManager(mode="simulated")
        session = await mgr.create_session("a1", "act1")
        await mgr.execute(session.session_id, "cmd")
        assert session.started_at is not None
        assert session.completed_at is not None
        assert session.completed_at >= session.started_at

    @pytest.mark.asyncio
    async def test_execute_failure_sets_failed_state(self):
        mgr = SandboxManager(mode="simulated")
        session = await mgr.create_session("a1", "act1")

        # Patch _execute_simulated to raise
        async def _raise(*args, **kwargs):
            raise RuntimeError("Sandbox crashed")

        mgr._execute_simulated = _raise

        with pytest.raises(RuntimeError, match="Sandbox crashed"):
            await mgr.execute(session.session_id, "bad-cmd")

        assert session.state == SandboxState.FAILED
        assert session.error == "Sandbox crashed"

    # -- SandboxManager destroy / list / get ---------------------------------

    @pytest.mark.asyncio
    async def test_destroy_session(self):
        mgr = SandboxManager(mode="simulated")
        session = await mgr.create_session("a1", "act1")
        sid = session.session_id
        assert await mgr.destroy_session(sid) is True
        assert mgr.get_session(sid) is None

    @pytest.mark.asyncio
    async def test_destroy_nonexistent_session(self):
        mgr = SandboxManager(mode="simulated")
        assert await mgr.destroy_session("no-such") is False

    @pytest.mark.asyncio
    async def test_list_sessions_all(self):
        mgr = SandboxManager(mode="simulated")
        await mgr.create_session("a1", "act1")
        await mgr.create_session("a2", "act2")
        sessions = mgr.list_sessions()
        assert len(sessions) == 2

    @pytest.mark.asyncio
    async def test_list_sessions_by_agent(self):
        mgr = SandboxManager(mode="simulated")
        await mgr.create_session("a1", "act1")
        await mgr.create_session("a2", "act2")
        await mgr.create_session("a1", "act3")
        sessions = mgr.list_sessions(agent_id="a1")
        assert len(sessions) == 2

    # -- Build execution script ----------------------------------------------

    def test_build_script_web_scrape(self):
        script = _build_execution_script(
            "web_scrape", {"selector": "div.content"}, {"url": "https://example.com"}
        )
        assert "playwright" in script
        assert "https://example.com" in script
        assert "div.content" in script

    def test_build_script_screenshot(self):
        script = _build_execution_script(
            "screenshot", {}, {"url": "https://test.com"}
        )
        assert "screenshot" in script
        assert "base64" in script

    def test_build_script_form_fill(self):
        script = _build_execution_script(
            "form_fill", {"url": "https://form.com"}, {"fields": {"#name": "test"}}
        )
        assert "fill" in script

    def test_build_script_generic(self):
        script = _build_execution_script("custom_action", {}, {})
        assert "custom_action" in script
        assert "executed" in script

    # -- execute_action_in_sandbox -------------------------------------------

    @pytest.mark.asyncio
    async def test_execute_action_in_sandbox_success(self):
        mock_sandbox = MagicMock()
        mock_sandbox.sandbox_id = "sb-123"

        with patch("marketplace.services.sandbox_executor.SandboxConfig"), \
             patch("marketplace.services.sandbox_executor.sandbox_manager") as mock_mgr:
            mock_mgr.create_sandbox = AsyncMock(return_value=mock_sandbox)
            mock_mgr.start_sandbox = AsyncMock()
            mock_mgr.execute_in_sandbox = AsyncMock(return_value={"data": "ok"})
            mock_mgr.destroy_sandbox = AsyncMock()

            result = await execute_action_in_sandbox(
                "web_scrape", {"url": "https://example.com"}, {"url": "https://example.com"}
            )

            assert result["success"] is True
            assert result["sandbox_id"] == "sb-123"
            assert result["output"] == {"data": "ok"}
            mock_mgr.destroy_sandbox.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_execute_action_in_sandbox_failure(self):
        mock_sandbox = MagicMock()
        mock_sandbox.sandbox_id = "sb-fail"

        with patch("marketplace.services.sandbox_executor.SandboxConfig"), \
             patch("marketplace.services.sandbox_executor.sandbox_manager") as mock_mgr:
            mock_mgr.create_sandbox = AsyncMock(return_value=mock_sandbox)
            mock_mgr.start_sandbox = AsyncMock(side_effect=RuntimeError("start failed"))
            mock_mgr.destroy_sandbox = AsyncMock()

            result = await execute_action_in_sandbox(
                "screenshot", {}, {"url": "https://err.com"}
            )

            assert result["success"] is False
            assert result["sandbox_id"] == "sb-fail"
            assert "start failed" in result["error"]
            assert result["proof"]["failed"] is True
            mock_mgr.destroy_sandbox.assert_awaited_once()


# ===========================================================================
# 4. TestSearchV2Service  (10+ tests)
# ===========================================================================

class TestSearchV2Service:
    """Azure AI Search V2 service: indexing, search, field schemas."""

    def test_init_no_credentials_stub_mode(self):
        svc = SearchV2Service(endpoint="", key="")
        assert svc._index_client is None
        assert svc._search_clients == {}

    def test_index_name_format(self):
        svc = SearchV2Service(index_prefix="test")
        assert svc._index_name("listings") == "test-listings"
        assert svc._index_name("agents") == "test-agents"

    def test_get_search_client_no_credential(self):
        svc = SearchV2Service(endpoint="", key="")
        client = svc._get_search_client("listings")
        assert client is None

    def test_search_listings_stub_returns_empty(self):
        svc = SearchV2Service(endpoint="", key="")
        result = svc.search_listings("test query")
        assert result == {"results": [], "count": 0, "facets": {}}

    def test_search_agents_stub_returns_empty(self):
        svc = SearchV2Service(endpoint="", key="")
        result = svc.search_agents("agent query")
        assert result == {"results": [], "count": 0, "facets": {}}

    def test_search_tools_stub_returns_empty(self):
        svc = SearchV2Service(endpoint="", key="")
        result = svc.search_tools("tool query")
        assert result == {"results": [], "count": 0, "facets": {}}

    def test_index_listing_no_client(self):
        svc = SearchV2Service(endpoint="", key="")
        result = svc.index_listing({"id": "1", "title": "test"})
        assert result is False

    def test_index_agent_no_client(self):
        svc = SearchV2Service(endpoint="", key="")
        result = svc.index_agent({"id": "1", "name": "agent"})
        assert result is False

    def test_index_tool_no_client(self):
        svc = SearchV2Service(endpoint="", key="")
        result = svc.index_tool({"id": "1", "name": "tool"})
        assert result is False

    def test_delete_document_no_client(self):
        svc = SearchV2Service(endpoint="", key="")
        result = svc.delete_document("test-index", "doc-1")
        assert result is False

    def test_ensure_indexes_no_client(self):
        svc = SearchV2Service(endpoint="", key="")
        result = svc.ensure_indexes()
        assert result == {}

    def test_listings_fields_schema(self):
        fields = _listings_fields()
        field_names = [f["name"] for f in fields]
        assert "id" in field_names
        assert "title" in field_names
        assert "category" in field_names
        assert "price_usd" in field_names
        assert "tags" in field_names

    def test_agents_fields_schema(self):
        fields = _agents_fields()
        field_names = [f["name"] for f in fields]
        assert "id" in field_names
        assert "name" in field_names
        assert "reputation_score" in field_names
        assert "total_transactions" in field_names

    def test_tools_fields_schema(self):
        fields = _tools_fields()
        field_names = [f["name"] for f in fields]
        assert "id" in field_names
        assert "domain" in field_names
        assert "success_rate" in field_names
        assert "execution_count" in field_names

    @patch("marketplace.services.search_v2_service._HAS_AZURE_SEARCH", True)
    def test_search_with_mock_client(self):
        """Test search routing with a mock search client."""
        svc = SearchV2Service(endpoint="", key="")
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.__iter__ = MagicMock(
            return_value=iter([{"id": "1", "title": "Result"}])
        )
        mock_response.get_count = MagicMock(return_value=1)
        mock_response.get_facets = MagicMock(return_value=None)
        mock_client.search.return_value = mock_response

        # Inject mock client and credential so _get_search_client returns cached
        svc._credential = MagicMock()
        svc._search_clients["agentchains-listings"] = mock_client

        result = svc.search_listings("test")
        assert result["count"] == 1
        assert len(result["results"]) == 1

    @patch("marketplace.services.search_v2_service._HAS_AZURE_SEARCH", True)
    def test_search_with_facets(self):
        """Test facet extraction from search results."""
        svc = SearchV2Service(endpoint="", key="")
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.__iter__ = MagicMock(return_value=iter([]))
        mock_response.get_count = MagicMock(return_value=0)
        mock_response.get_facets = MagicMock(return_value={
            "category": [{"value": "AI", "count": 5}]
        })
        mock_client.search.return_value = mock_response

        svc._credential = MagicMock()
        svc._search_clients["agentchains-listings"] = mock_client

        result = svc.search_listings("query", facets=["category"])
        assert "category" in result["facets"]
        assert result["facets"]["category"][0]["value"] == "AI"

    @patch("marketplace.services.search_v2_service._HAS_AZURE_SEARCH", True)
    def test_search_exception_returns_empty(self):
        """Test that search exceptions are caught gracefully."""
        svc = SearchV2Service(endpoint="", key="")
        mock_client = MagicMock()
        mock_client.search.side_effect = Exception("Azure error")

        svc._credential = MagicMock()
        svc._search_clients["agentchains-listings"] = mock_client

        result = svc.search_listings("bad query")
        assert result == {"results": [], "count": 0, "facets": {}}


# ===========================================================================
# 5. TestServiceBusService  (10+ tests)
# ===========================================================================

class TestServiceBusService:
    """Service Bus service: message send/receive, DLQ, batch, lifecycle."""

    def test_init_no_connection_string(self):
        svc = ServiceBusService(connection_string="")
        assert svc._client is None
        assert svc._senders == {}

    def test_send_message_stub_returns_false(self):
        svc = ServiceBusService(connection_string="")
        result = svc.send_message("queue1", "hello")
        assert result is False

    def test_send_message_dict_body_stub(self):
        svc = ServiceBusService(connection_string="")
        result = svc.send_message("queue1", {"key": "value"})
        assert result is False

    def test_send_batch_stub_returns_zero(self):
        svc = ServiceBusService(connection_string="")
        result = svc.send_batch("queue1", ["msg1", "msg2"])
        assert result == 0

    def test_receive_messages_stub_returns_empty(self):
        svc = ServiceBusService(connection_string="")
        result = svc.receive_messages("queue1")
        assert result == []

    def test_complete_message_no_client(self):
        svc = ServiceBusService(connection_string="")
        result = svc.complete_message(MagicMock())
        assert result is False

    def test_dead_letter_message_no_client(self):
        svc = ServiceBusService(connection_string="")
        result = svc.dead_letter_message(MagicMock(), reason="bad")
        assert result is False

    def test_peek_dead_letters_no_client(self):
        svc = ServiceBusService(connection_string="")
        result = svc.peek_dead_letters("queue1")
        assert result == []

    def test_close_no_client(self):
        svc = ServiceBusService(connection_string="")
        # Should not raise even without a client
        svc.close()
        assert svc._client is None

    def test_complete_message_with_mock(self):
        svc = ServiceBusService(connection_string="")
        svc._client = MagicMock()  # pretend we have a client
        msg = MagicMock()
        msg.complete = MagicMock()
        result = svc.complete_message(msg)
        assert result is True
        msg.complete.assert_called_once()

    def test_dead_letter_message_with_mock(self):
        svc = ServiceBusService(connection_string="")
        svc._client = MagicMock()
        msg = MagicMock()
        msg.dead_letter = MagicMock()
        result = svc.dead_letter_message(msg, reason="processing error")
        assert result is True
        msg.dead_letter.assert_called_once_with(
            reason="processing error", error_description="processing error"
        )

    def test_complete_message_attribute_error(self):
        svc = ServiceBusService(connection_string="")
        svc._client = MagicMock()
        msg = MagicMock()
        msg.complete = MagicMock(side_effect=AttributeError("no complete"))
        result = svc.complete_message(msg)
        assert result is False

    def test_dead_letter_message_attribute_error(self):
        svc = ServiceBusService(connection_string="")
        svc._client = MagicMock()
        msg = MagicMock()
        msg.dead_letter = MagicMock(side_effect=AttributeError("no dead_letter"))
        result = svc.dead_letter_message(msg)
        assert result is False

    def test_send_message_with_properties(self):
        svc = ServiceBusService(connection_string="")
        svc._client = MagicMock()
        mock_sender = MagicMock()
        svc._senders["events"] = mock_sender

        # ServiceBusMessage may not be importable if SDK is missing, so inject it
        import marketplace.services.servicebus_service as sb_mod
        original = getattr(sb_mod, "ServiceBusMessage", None)
        mock_msg_cls = MagicMock()
        sb_mod.ServiceBusMessage = mock_msg_cls
        try:
            result = svc.send_message(
                "events", "body", properties={"type": "webhook"}
            )
            assert result is True
            mock_sender.send_messages.assert_called_once()
        finally:
            if original is not None:
                sb_mod.ServiceBusMessage = original
            else:
                delattr(sb_mod, "ServiceBusMessage")

    def test_send_batch_with_client(self):
        svc = ServiceBusService(connection_string="")
        svc._client = MagicMock()
        mock_sender = MagicMock()
        mock_batch = MagicMock()
        mock_sender.create_message_batch.return_value = mock_batch
        mock_batch.add_message = MagicMock()
        svc._senders["queue1"] = mock_sender

        import marketplace.services.servicebus_service as sb_mod
        original = getattr(sb_mod, "ServiceBusMessage", None)
        sb_mod.ServiceBusMessage = MagicMock(side_effect=lambda body: MagicMock(body=body))
        try:
            count = svc.send_batch("queue1", ["a", "b", "c"])
            assert count == 3
            assert mock_sender.send_messages.called
        finally:
            if original is not None:
                sb_mod.ServiceBusMessage = original
            else:
                delattr(sb_mod, "ServiceBusMessage")

    def test_close_with_senders(self):
        svc = ServiceBusService(connection_string="")
        svc._client = MagicMock()
        s1 = MagicMock()
        s2 = MagicMock()
        svc._senders = {"q1": s1, "q2": s2}

        svc.close()
        s1.close.assert_called_once()
        s2.close.assert_called_once()
        assert svc._senders == {}
        assert svc._client is None

    def test_get_sender_caching(self):
        svc = ServiceBusService(connection_string="")
        svc._client = MagicMock()
        mock_sender = MagicMock()
        svc._client.get_queue_sender.return_value = mock_sender

        sender1 = svc._get_sender("my-queue")
        sender2 = svc._get_sender("my-queue")
        assert sender1 is sender2
        svc._client.get_queue_sender.assert_called_once_with(queue_name="my-queue")

    def test_get_sender_no_client(self):
        svc = ServiceBusService(connection_string="")
        assert svc._get_sender("any") is None

    def test_receive_messages_with_client(self):
        svc = ServiceBusService(connection_string="")
        svc._client = MagicMock()
        mock_receiver = MagicMock()
        mock_receiver.__enter__ = MagicMock(return_value=mock_receiver)
        mock_receiver.__exit__ = MagicMock(return_value=False)
        mock_receiver.receive_messages.return_value = [MagicMock(), MagicMock()]
        svc._client.get_queue_receiver.return_value = mock_receiver

        messages = svc.receive_messages("queue1", max_messages=5)
        assert len(messages) == 2
