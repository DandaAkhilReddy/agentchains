"""Orchestration v3 API — workflow CRUD, execution lifecycle, and cost tracking."""

from __future__ import annotations

import json
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession

from marketplace.core.auth import get_current_agent_id
from marketplace.database import get_db
from marketplace.services import orchestration_service

router = APIRouter(prefix="", tags=["orchestration"])


# ── Helpers ────────────────────────────────────────────────────────


def _workflow_to_dict(wf) -> dict:
    """Serialise a WorkflowDefinition ORM instance to a plain dict."""
    return {
        "id": wf.id,
        "name": wf.name,
        "description": wf.description,
        "graph_json": wf.graph_json,
        "owner_id": wf.owner_id,
        "version": wf.version,
        "status": wf.status,
        "max_budget_usd": float(wf.max_budget_usd) if wf.max_budget_usd else None,
        "created_at": wf.created_at.isoformat() if wf.created_at else None,
        "updated_at": wf.updated_at.isoformat() if wf.updated_at else None,
    }


def _execution_to_dict(ex) -> dict:
    """Serialise a WorkflowExecution ORM instance to a plain dict."""
    return {
        "id": ex.id,
        "workflow_id": ex.workflow_id,
        "initiated_by": ex.initiated_by,
        "status": ex.status,
        "input_json": ex.input_json,
        "output_json": ex.output_json,
        "total_cost_usd": float(ex.total_cost_usd) if ex.total_cost_usd else 0.0,
        "started_at": ex.started_at.isoformat() if ex.started_at else None,
        "completed_at": ex.completed_at.isoformat() if ex.completed_at else None,
        "error_message": ex.error_message,
        "created_at": ex.created_at.isoformat() if ex.created_at else None,
    }


def _node_execution_to_dict(ne) -> dict:
    """Serialise a WorkflowNodeExecution ORM instance to a plain dict."""
    return {
        "id": ne.id,
        "execution_id": ne.execution_id,
        "node_id": ne.node_id,
        "node_type": ne.node_type,
        "status": ne.status,
        "input_json": ne.input_json,
        "output_json": ne.output_json,
        "cost_usd": float(ne.cost_usd) if ne.cost_usd else 0.0,
        "started_at": ne.started_at.isoformat() if ne.started_at else None,
        "completed_at": ne.completed_at.isoformat() if ne.completed_at else None,
        "error_message": ne.error_message,
        "attempt": ne.attempt,
    }


# ── Request Models ─────────────────────────────────────────────────


class WorkflowCreateRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    name: str = Field(..., min_length=1, max_length=200)
    description: str = ""
    graph_json: str = Field(..., min_length=2, description="JSON string of the DAG definition")
    max_budget_usd: float | None = Field(default=None, ge=0)


class WorkflowUpdateRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    name: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = None
    graph_json: str | None = None
    status: str | None = Field(default=None, pattern="^(draft|active|archived)$")
    max_budget_usd: float | None = Field(default=None, ge=0)


class WorkflowExecuteRequest(BaseModel):
    input_data: dict = Field(default_factory=dict)


# ── Built-in Workflow Templates ────────────────────────────────────


WORKFLOW_TEMPLATES: list[dict] = [
    {
        "key": "sequential-pipeline",
        "name": "Sequential Pipeline",
        "description": (
            "A linear chain of agent calls where each node passes its "
            "output to the next. Ideal for multi-step data processing "
            "and enrichment workflows."
        ),
        "graph_json": json.dumps({
            "nodes": {
                "step_1": {"type": "agent_call", "config": {"endpoint": ""}, "depends_on": []},
                "step_2": {"type": "agent_call", "config": {"endpoint": ""}, "depends_on": ["step_1"]},
                "step_3": {"type": "agent_call", "config": {"endpoint": ""}, "depends_on": ["step_2"]},
            },
            "edges": [],
        }),
    },
    {
        "key": "fan-out-fan-in",
        "name": "Fan-out / Fan-in",
        "description": (
            "Splits work across multiple parallel agents, then "
            "aggregates results in a final merge node. Perfect for "
            "search, comparison, and ensemble-voting patterns."
        ),
        "graph_json": json.dumps({
            "nodes": {
                "split": {"type": "agent_call", "config": {"endpoint": ""}, "depends_on": []},
                "worker_a": {"type": "agent_call", "config": {"endpoint": ""}, "depends_on": ["split"]},
                "worker_b": {"type": "agent_call", "config": {"endpoint": ""}, "depends_on": ["split"]},
                "worker_c": {"type": "agent_call", "config": {"endpoint": ""}, "depends_on": ["split"]},
                "merge": {"type": "agent_call", "config": {"endpoint": ""}, "depends_on": ["worker_a", "worker_b", "worker_c"]},
            },
            "edges": [],
        }),
    },
    {
        "key": "human-in-the-loop",
        "name": "Human-in-the-Loop",
        "description": (
            "Runs an initial agent step, pauses for human approval, "
            "then continues with the next step. Suited for workflows "
            "that require manual review before proceeding."
        ),
        "graph_json": json.dumps({
            "nodes": {
                "prepare": {"type": "agent_call", "config": {"endpoint": ""}, "depends_on": []},
                "review": {"type": "human_approval", "config": {"message": "Please review and approve."}, "depends_on": ["prepare"]},
                "finalise": {"type": "agent_call", "config": {"endpoint": ""}, "depends_on": ["review"]},
            },
            "edges": [],
        }),
    },
]


# ── Workflow CRUD Endpoints ────────────────────────────────────────


@router.post("/workflows", status_code=201)
async def create_workflow(
    req: WorkflowCreateRequest,
    db: AsyncSession = Depends(get_db),
    agent_id: str = Depends(get_current_agent_id),
):
    """Create a new workflow definition."""
    # Validate that graph_json is valid JSON
    try:
        json.loads(req.graph_json)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="graph_json must be valid JSON")

    workflow = await orchestration_service.create_workflow(
        db,
        name=req.name,
        graph_json=req.graph_json,
        owner_id=agent_id,
        description=req.description,
        max_budget_usd=Decimal(str(req.max_budget_usd)) if req.max_budget_usd is not None else None,
    )
    return _workflow_to_dict(workflow)


@router.get("/workflows")
async def list_workflows(
    owner_id: str | None = None,
    status: str | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
    agent_id: str = Depends(get_current_agent_id),
):
    """List workflow definitions with optional filters."""
    workflows = await orchestration_service.list_workflows(
        db, owner_id=owner_id, status=status, limit=limit,
    )
    # Apply offset manually (service returns up to limit)
    sliced = workflows[offset:]
    return {
        "workflows": [_workflow_to_dict(w) for w in sliced],
        "total": len(workflows),
        "limit": limit,
        "offset": offset,
    }


@router.get("/workflows/{workflow_id}")
async def get_workflow(
    workflow_id: str,
    db: AsyncSession = Depends(get_db),
    agent_id: str = Depends(get_current_agent_id),
):
    """Get a single workflow definition by ID."""
    workflow = await orchestration_service.get_workflow(db, workflow_id)
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")
    return _workflow_to_dict(workflow)


@router.put("/workflows/{workflow_id}")
async def update_workflow(
    workflow_id: str,
    req: WorkflowUpdateRequest,
    db: AsyncSession = Depends(get_db),
    agent_id: str = Depends(get_current_agent_id),
):
    """Update an existing workflow definition."""
    workflow = await orchestration_service.get_workflow(db, workflow_id)
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")

    if req.name is not None:
        workflow.name = req.name
    if req.description is not None:
        workflow.description = req.description
    if req.graph_json is not None:
        try:
            json.loads(req.graph_json)
        except json.JSONDecodeError:
            raise HTTPException(status_code=400, detail="graph_json must be valid JSON")
        workflow.graph_json = req.graph_json
    if req.status is not None:
        workflow.status = req.status
    if req.max_budget_usd is not None:
        workflow.max_budget_usd = Decimal(str(req.max_budget_usd))

    await db.commit()
    await db.refresh(workflow)
    return _workflow_to_dict(workflow)


@router.delete("/workflows/{workflow_id}")
async def delete_workflow(
    workflow_id: str,
    db: AsyncSession = Depends(get_db),
    agent_id: str = Depends(get_current_agent_id),
):
    """Archive (soft-delete) a workflow definition."""
    workflow = await orchestration_service.get_workflow(db, workflow_id)
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")

    workflow.status = "archived"
    await db.commit()
    return {"detail": "Workflow archived", "workflow_id": workflow_id}


# ── Execution Endpoints ────────────────────────────────────────────


@router.post("/workflows/{workflow_id}/execute", status_code=202)
async def execute_workflow(
    workflow_id: str,
    req: WorkflowExecuteRequest,
    db: AsyncSession = Depends(get_db),
    agent_id: str = Depends(get_current_agent_id),
):
    """Start executing a workflow. Returns the execution_id immediately."""
    try:
        execution = await orchestration_service.execute_workflow(
            db,
            workflow_id=workflow_id,
            initiated_by=agent_id,
            input_data=req.input_data,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))

    return {"execution_id": execution.id, "status": execution.status}


@router.get("/executions/{execution_id}")
async def get_execution(
    execution_id: str,
    db: AsyncSession = Depends(get_db),
    agent_id: str = Depends(get_current_agent_id),
):
    """Get execution status and details."""
    execution = await orchestration_service.get_execution(db, execution_id)
    if not execution:
        raise HTTPException(status_code=404, detail="Execution not found")
    return _execution_to_dict(execution)


@router.get("/executions/{execution_id}/nodes")
async def get_execution_nodes(
    execution_id: str,
    db: AsyncSession = Depends(get_db),
    agent_id: str = Depends(get_current_agent_id),
):
    """Get all node execution statuses for a workflow execution."""
    nodes = await orchestration_service.get_execution_nodes(db, execution_id)
    return {
        "execution_id": execution_id,
        "nodes": [_node_execution_to_dict(n) for n in nodes],
        "total": len(nodes),
    }


@router.post("/executions/{execution_id}/pause")
async def pause_execution(
    execution_id: str,
    db: AsyncSession = Depends(get_db),
    agent_id: str = Depends(get_current_agent_id),
):
    """Pause a running execution."""
    success = await orchestration_service.pause_execution(db, execution_id)
    if not success:
        raise HTTPException(
            status_code=409,
            detail="Execution cannot be paused (not running or not found)",
        )
    return {"detail": "Execution paused", "execution_id": execution_id}


@router.post("/executions/{execution_id}/resume")
async def resume_execution(
    execution_id: str,
    db: AsyncSession = Depends(get_db),
    agent_id: str = Depends(get_current_agent_id),
):
    """Resume a paused execution."""
    success = await orchestration_service.resume_execution(db, execution_id)
    if not success:
        raise HTTPException(
            status_code=409,
            detail="Execution cannot be resumed (not paused or not found)",
        )
    return {"detail": "Execution resumed", "execution_id": execution_id}


@router.post("/executions/{execution_id}/cancel")
async def cancel_execution(
    execution_id: str,
    db: AsyncSession = Depends(get_db),
    agent_id: str = Depends(get_current_agent_id),
):
    """Cancel a pending, running, or paused execution."""
    success = await orchestration_service.cancel_execution(db, execution_id)
    if not success:
        raise HTTPException(
            status_code=409,
            detail="Execution cannot be cancelled (already completed/cancelled or not found)",
        )
    return {"detail": "Execution cancelled", "execution_id": execution_id}


@router.get("/executions/{execution_id}/cost")
async def get_execution_cost(
    execution_id: str,
    db: AsyncSession = Depends(get_db),
    agent_id: str = Depends(get_current_agent_id),
):
    """Get the cost breakdown for an execution."""
    execution = await orchestration_service.get_execution(db, execution_id)
    if not execution:
        raise HTTPException(status_code=404, detail="Execution not found")

    total_cost = await orchestration_service.get_execution_cost(db, execution_id)
    nodes = await orchestration_service.get_execution_nodes(db, execution_id)

    node_costs = [
        {
            "node_id": n.node_id,
            "node_type": n.node_type,
            "cost_usd": float(n.cost_usd) if n.cost_usd else 0.0,
            "status": n.status,
        }
        for n in nodes
    ]

    return {
        "execution_id": execution_id,
        "workflow_id": execution.workflow_id,
        "total_cost_usd": float(total_cost),
        "node_costs": node_costs,
        "status": execution.status,
    }


# ── Templates Endpoint (no auth) ──────────────────────────────────


@router.get("/workflow-templates")
async def list_workflow_templates():
    """List built-in workflow templates. No authentication required."""
    return {"templates": WORKFLOW_TEMPLATES, "total": len(WORKFLOW_TEMPLATES)}


@router.get("/templates")
async def list_templates():
    """List pre-built workflow templates (alias). No authentication required."""
    return {"templates": WORKFLOW_TEMPLATES, "total": len(WORKFLOW_TEMPLATES)}
