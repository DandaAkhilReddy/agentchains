"""Tests for workflow models: WorkflowDefinition, WorkflowExecution, WorkflowNodeExecution.

Covers: creation, defaults, status transitions, queries, relationships.
"""

import uuid
from datetime import datetime, timezone
from decimal import Decimal

import pytest
from sqlalchemy import select

from marketplace.models.workflow import (
    WorkflowDefinition,
    WorkflowExecution,
    WorkflowNodeExecution,
    utcnow,
)


def _uid() -> str:
    return str(uuid.uuid4())


# ---------------------------------------------------------------------------
# WorkflowDefinition
# ---------------------------------------------------------------------------


class TestWorkflowDefinitionModel:
    async def test_create_with_defaults(self, db):
        wf = WorkflowDefinition(
            id=_uid(),
            name="Data Pipeline",
            graph_json='{"nodes": [], "edges": []}',
            owner_id="owner-1",
        )
        db.add(wf)
        await db.commit()
        await db.refresh(wf)

        assert wf.name == "Data Pipeline"
        assert wf.description == ""
        assert wf.version == 1
        assert wf.status == "draft"
        assert wf.max_budget_usd is None
        assert wf.created_at is not None
        assert wf.updated_at is not None

    async def test_create_with_all_fields(self, db):
        wf = WorkflowDefinition(
            id=_uid(),
            name="Complex Workflow",
            description="Multi-step analysis pipeline with error handling",
            graph_json='{"nodes": [{"id": "start"}, {"id": "end"}], "edges": [{"from": "start", "to": "end"}]}',
            owner_id="owner-2",
            version=5,
            status="active",
            max_budget_usd=Decimal("25.0000"),
        )
        db.add(wf)
        await db.commit()
        await db.refresh(wf)

        assert wf.version == 5
        assert wf.status == "active"
        assert wf.max_budget_usd == Decimal("25.0000")

    async def test_status_transitions(self, db):
        wf = WorkflowDefinition(
            id=_uid(),
            name="Mutable WF",
            graph_json="{}",
            owner_id="o1",
            status="draft",
        )
        db.add(wf)
        await db.commit()

        wf.status = "active"
        wf.version = 2
        await db.commit()
        await db.refresh(wf)

        assert wf.status == "active"
        assert wf.version == 2

    async def test_multiple_workflows_per_owner(self, db):
        owner = "shared-owner"
        for i in range(3):
            wf = WorkflowDefinition(
                id=_uid(),
                name=f"Workflow {i}",
                graph_json="{}",
                owner_id=owner,
            )
            db.add(wf)
        await db.commit()

        result = await db.execute(
            select(WorkflowDefinition).where(WorkflowDefinition.owner_id == owner)
        )
        found = list(result.scalars().all())
        assert len(found) == 3


# ---------------------------------------------------------------------------
# WorkflowExecution
# ---------------------------------------------------------------------------


class TestWorkflowExecutionModel:
    async def _make_workflow(self, db) -> WorkflowDefinition:
        wf = WorkflowDefinition(
            id=_uid(),
            name="Test WF",
            graph_json="{}",
            owner_id="o1",
        )
        db.add(wf)
        await db.commit()
        return wf

    async def test_create_with_defaults(self, db):
        wf = await self._make_workflow(db)
        execution = WorkflowExecution(
            id=_uid(),
            workflow_id=wf.id,
            initiated_by="agent-1",
        )
        db.add(execution)
        await db.commit()
        await db.refresh(execution)

        assert execution.status == "pending"
        assert execution.input_json == "{}"
        assert execution.output_json == "{}"
        assert execution.total_cost_usd == Decimal("0")
        assert execution.started_at is None
        assert execution.completed_at is None
        assert execution.error_message is None
        assert execution.created_at is not None

    async def test_running_execution(self, db):
        wf = await self._make_workflow(db)
        execution = WorkflowExecution(
            id=_uid(),
            workflow_id=wf.id,
            initiated_by="agent-1",
            status="running",
            input_json='{"query": "find data"}',
            started_at=datetime.now(timezone.utc),
        )
        db.add(execution)
        await db.commit()
        await db.refresh(execution)

        assert execution.status == "running"
        assert execution.started_at is not None

    async def test_completed_execution(self, db):
        wf = await self._make_workflow(db)
        now = datetime.now(timezone.utc)
        execution = WorkflowExecution(
            id=_uid(),
            workflow_id=wf.id,
            initiated_by="agent-1",
            status="completed",
            input_json='{"q": "test"}',
            output_json='{"result": [1, 2, 3]}',
            total_cost_usd=Decimal("0.150000"),
            started_at=now,
            completed_at=now,
        )
        db.add(execution)
        await db.commit()
        await db.refresh(execution)

        assert execution.status == "completed"
        assert execution.total_cost_usd == Decimal("0.150000")

    async def test_failed_execution(self, db):
        wf = await self._make_workflow(db)
        execution = WorkflowExecution(
            id=_uid(),
            workflow_id=wf.id,
            initiated_by="agent-1",
            status="failed",
            error_message="Node 'fetch_data' timed out after 30s",
        )
        db.add(execution)
        await db.commit()
        await db.refresh(execution)

        assert execution.status == "failed"
        assert "timed out" in execution.error_message

    async def test_query_executions_by_workflow(self, db):
        wf = await self._make_workflow(db)
        for _ in range(4):
            execution = WorkflowExecution(
                id=_uid(),
                workflow_id=wf.id,
                initiated_by="agent-1",
            )
            db.add(execution)
        await db.commit()

        result = await db.execute(
            select(WorkflowExecution).where(WorkflowExecution.workflow_id == wf.id)
        )
        found = list(result.scalars().all())
        assert len(found) == 4

    async def test_status_transition_lifecycle(self, db):
        wf = await self._make_workflow(db)
        execution = WorkflowExecution(
            id=_uid(),
            workflow_id=wf.id,
            initiated_by="agent-1",
            status="pending",
        )
        db.add(execution)
        await db.commit()

        # pending -> running
        execution.status = "running"
        execution.started_at = datetime.now(timezone.utc)
        await db.commit()
        await db.refresh(execution)
        assert execution.status == "running"

        # running -> completed
        execution.status = "completed"
        execution.completed_at = datetime.now(timezone.utc)
        execution.output_json = '{"done": true}'
        await db.commit()
        await db.refresh(execution)
        assert execution.status == "completed"


# ---------------------------------------------------------------------------
# WorkflowNodeExecution
# ---------------------------------------------------------------------------


class TestWorkflowNodeExecutionModel:
    async def _make_execution(self, db) -> WorkflowExecution:
        wf = WorkflowDefinition(
            id=_uid(),
            name="WF",
            graph_json="{}",
            owner_id="o1",
        )
        db.add(wf)
        await db.commit()

        execution = WorkflowExecution(
            id=_uid(),
            workflow_id=wf.id,
            initiated_by="agent-1",
        )
        db.add(execution)
        await db.commit()
        return execution

    async def test_create_with_defaults(self, db):
        execution = await self._make_execution(db)
        node = WorkflowNodeExecution(
            id=_uid(),
            execution_id=execution.id,
            node_id="fetch_data",
            node_type="tool",
        )
        db.add(node)
        await db.commit()
        await db.refresh(node)

        assert node.status == "pending"
        assert node.input_json == "{}"
        assert node.output_json == "{}"
        assert node.cost_usd == Decimal("0")
        assert node.started_at is None
        assert node.completed_at is None
        assert node.error_message is None
        assert node.attempt == 1

    async def test_completed_node_execution(self, db):
        execution = await self._make_execution(db)
        now = datetime.now(timezone.utc)
        node = WorkflowNodeExecution(
            id=_uid(),
            execution_id=execution.id,
            node_id="process_data",
            node_type="agent",
            status="completed",
            input_json='{"data": [1, 2]}',
            output_json='{"processed": true}',
            cost_usd=Decimal("0.005000"),
            started_at=now,
            completed_at=now,
        )
        db.add(node)
        await db.commit()
        await db.refresh(node)

        assert node.status == "completed"
        assert node.cost_usd == Decimal("0.005000")

    async def test_failed_node_with_retry(self, db):
        execution = await self._make_execution(db)
        node = WorkflowNodeExecution(
            id=_uid(),
            execution_id=execution.id,
            node_id="flaky_node",
            node_type="tool",
            status="failed",
            error_message="Connection reset by peer",
            attempt=3,
        )
        db.add(node)
        await db.commit()
        await db.refresh(node)

        assert node.attempt == 3
        assert node.status == "failed"

    async def test_multiple_nodes_per_execution(self, db):
        execution = await self._make_execution(db)
        node_types = [
            ("start", "trigger"),
            ("fetch", "tool"),
            ("process", "agent"),
            ("output", "sink"),
        ]
        for node_id, node_type in node_types:
            node = WorkflowNodeExecution(
                id=_uid(),
                execution_id=execution.id,
                node_id=node_id,
                node_type=node_type,
            )
            db.add(node)
        await db.commit()

        result = await db.execute(
            select(WorkflowNodeExecution).where(
                WorkflowNodeExecution.execution_id == execution.id
            )
        )
        found = list(result.scalars().all())
        assert len(found) == 4

    async def test_query_by_status(self, db):
        execution = await self._make_execution(db)
        for status in ("pending", "running", "completed", "completed", "failed"):
            node = WorkflowNodeExecution(
                id=_uid(),
                execution_id=execution.id,
                node_id=f"node_{status}_{_uid()[:4]}",
                node_type="tool",
                status=status,
            )
            db.add(node)
        await db.commit()

        result = await db.execute(
            select(WorkflowNodeExecution).where(
                WorkflowNodeExecution.execution_id == execution.id,
                WorkflowNodeExecution.status == "completed",
            )
        )
        completed = list(result.scalars().all())
        assert len(completed) == 2

    async def test_node_types(self, db):
        execution = await self._make_execution(db)
        for ntype in ("tool", "agent", "trigger", "sink", "conditional"):
            node = WorkflowNodeExecution(
                id=_uid(),
                execution_id=execution.id,
                node_id=f"n_{ntype}",
                node_type=ntype,
            )
            db.add(node)
        await db.commit()

        result = await db.execute(
            select(WorkflowNodeExecution).where(
                WorkflowNodeExecution.execution_id == execution.id,
            )
        )
        found = list(result.scalars().all())
        assert len(found) == 5
