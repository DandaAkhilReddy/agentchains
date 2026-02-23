"""Chain Registry v5 API — chain template CRUD, execution, forking, and provenance."""

from __future__ import annotations

import json
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from marketplace.core.auth import get_current_agent_id
from marketplace.database import get_db
from marketplace.models.chain_template import ChainExecution
from marketplace.services import chain_registry_service

router = APIRouter(prefix="", tags=["chains"])


# ── Pydantic request models ──────────────────────────────────────


class ChainTemplateCreateRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    name: str = Field(..., min_length=1, max_length=200)
    description: str = ""
    category: str = Field(default="general", max_length=50)
    graph_json: str = Field(..., min_length=2, description="JSON DAG definition")
    tags: list[str] = Field(default_factory=list)
    max_budget_usd: float | None = Field(default=None, ge=0)


class ChainTemplateForkRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    name: str | None = Field(default=None, min_length=1, max_length=200)
    graph_json: str | None = Field(default=None, min_length=2)


class ChainExecuteRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    input_data: dict = Field(default_factory=dict)
    idempotency_key: str | None = Field(default=None, max_length=64)


# ── Serializers ───────────────────────────────────────────────────


def _template_to_dict(t) -> dict:
    """Serialise a ChainTemplate ORM instance to a plain dict."""
    return {
        "id": t.id,
        "name": t.name,
        "description": t.description,
        "category": t.category,
        "workflow_id": t.workflow_id,
        "graph_json": t.graph_json,
        "author_id": t.author_id,
        "forked_from_id": t.forked_from_id,
        "version": t.version,
        "status": t.status,
        "tags": json.loads(t.tags_json) if t.tags_json else [],
        "execution_count": t.execution_count or 0,
        "avg_cost_usd": float(t.avg_cost_usd) if t.avg_cost_usd else 0.0,
        "avg_duration_ms": t.avg_duration_ms or 0,
        "trust_score": t.trust_score or 0,
        "max_budget_usd": float(t.max_budget_usd) if t.max_budget_usd else None,
        "created_at": t.created_at.isoformat() if t.created_at else None,
        "updated_at": t.updated_at.isoformat() if t.updated_at else None,
    }


def _execution_to_dict(ex) -> dict:
    """Serialise a ChainExecution ORM instance to a plain dict."""
    return {
        "id": ex.id,
        "chain_template_id": ex.chain_template_id,
        "workflow_execution_id": ex.workflow_execution_id,
        "initiated_by": ex.initiated_by,
        "status": ex.status,
        "input_json": ex.input_json,
        "output_json": ex.output_json,
        "total_cost_usd": float(ex.total_cost_usd) if ex.total_cost_usd else 0.0,
        "participant_agents": (
            json.loads(ex.participant_agents_json)
            if ex.participant_agents_json
            else []
        ),
        "provenance_hash": ex.provenance_hash,
        "idempotency_key": ex.idempotency_key,
        "created_at": ex.created_at.isoformat() if ex.created_at else None,
        "completed_at": ex.completed_at.isoformat() if ex.completed_at else None,
    }


# ── CRUD Endpoints ────────────────────────────────────────────────


@router.post("/chain-templates", status_code=201)
async def create_chain_template(
    req: ChainTemplateCreateRequest,
    db: AsyncSession = Depends(get_db),
    agent_id: str = Depends(get_current_agent_id),
):
    """Publish a new chain template. Validates DAG structure and agent references."""
    try:
        template = await chain_registry_service.publish_chain_template(
            db,
            name=req.name,
            graph_json=req.graph_json,
            author_id=agent_id,
            description=req.description,
            category=req.category,
            tags=req.tags,
            max_budget_usd=(
                Decimal(str(req.max_budget_usd))
                if req.max_budget_usd is not None
                else None
            ),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return _template_to_dict(template)


@router.get("/chain-templates")
async def list_chain_templates(
    category: str | None = None,
    author_id: str | None = None,
    status: str | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
    agent_id: str = Depends(get_current_agent_id),
):
    """List chain templates with optional filters."""
    templates, total = await chain_registry_service.list_chain_templates(
        db,
        category=category,
        author_id=author_id,
        status=status,
        limit=limit,
        offset=offset,
    )
    return {
        "templates": [_template_to_dict(t) for t in templates],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


@router.get("/chain-templates/{template_id}")
async def get_chain_template(
    template_id: str,
    db: AsyncSession = Depends(get_db),
    agent_id: str = Depends(get_current_agent_id),
):
    """Get a single chain template by ID."""
    template = await chain_registry_service.get_chain_template(db, template_id)
    if not template:
        raise HTTPException(status_code=404, detail="Chain template not found")
    return _template_to_dict(template)


@router.delete("/chain-templates/{template_id}")
async def archive_chain_template(
    template_id: str,
    db: AsyncSession = Depends(get_db),
    agent_id: str = Depends(get_current_agent_id),
):
    """Archive (soft-delete) a chain template. Only the author can archive."""
    template = await chain_registry_service.get_chain_template(db, template_id)
    if not template:
        raise HTTPException(status_code=404, detail="Chain template not found")
    if template.author_id != agent_id:
        raise HTTPException(
            status_code=403, detail="Only the template author can archive"
        )

    template.status = "archived"
    await db.commit()
    return {"detail": "Chain template archived", "template_id": template_id}


# ── Fork / Execute / Execution Endpoints ──────────────────────────


@router.post("/chain-templates/{template_id}/fork", status_code=201)
async def fork_chain_template(
    template_id: str,
    req: ChainTemplateForkRequest,
    db: AsyncSession = Depends(get_db),
    agent_id: str = Depends(get_current_agent_id),
):
    """Fork an existing chain template, optionally modifying name or graph."""
    try:
        forked = await chain_registry_service.fork_chain_template(
            db,
            source_template_id=template_id,
            new_author_id=agent_id,
            name=req.name,
            graph_json=req.graph_json,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return _template_to_dict(forked)


@router.post("/chain-templates/{template_id}/execute", status_code=202)
async def execute_chain(
    template_id: str,
    req: ChainExecuteRequest,
    db: AsyncSession = Depends(get_db),
    agent_id: str = Depends(get_current_agent_id),
):
    """Execute a chain template. Returns execution_id immediately (async)."""
    try:
        execution = await chain_registry_service.execute_chain(
            db,
            template_id=template_id,
            initiated_by=agent_id,
            input_data=req.input_data,
            idempotency_key=req.idempotency_key,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return _execution_to_dict(execution)


@router.get("/chain-executions/{execution_id}")
async def get_chain_execution(
    execution_id: str,
    db: AsyncSession = Depends(get_db),
    agent_id: str = Depends(get_current_agent_id),
):
    """Get chain execution status and details."""
    execution = await chain_registry_service.get_chain_execution(db, execution_id)
    if not execution:
        raise HTTPException(status_code=404, detail="Chain execution not found")
    return _execution_to_dict(execution)


@router.get("/chain-executions/{execution_id}/provenance")
async def get_chain_provenance(
    execution_id: str,
    db: AsyncSession = Depends(get_db),
    agent_id: str = Depends(get_current_agent_id),
):
    """Get provenance data. Access restricted to initiator and template author."""
    try:
        provenance = await chain_registry_service.get_chain_provenance(
            db,
            chain_execution_id=execution_id,
            requesting_agent_id=agent_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))

    if provenance.get("error") == "forbidden":
        raise HTTPException(
            status_code=403,
            detail="Only the chain initiator or template author can view provenance",
        )
    return provenance


@router.get("/chain-templates/{template_id}/executions")
async def list_chain_executions(
    template_id: str,
    status: str | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
    agent_id: str = Depends(get_current_agent_id),
):
    """List executions for a specific chain template."""
    template = await chain_registry_service.get_chain_template(db, template_id)
    if not template:
        raise HTTPException(status_code=404, detail="Chain template not found")

    base = select(ChainExecution).where(
        ChainExecution.chain_template_id == template_id
    )
    if status:
        base = base.where(ChainExecution.status == status)

    count_q = select(func.count()).select_from(base.subquery())
    total_result = await db.execute(count_q)
    total = total_result.scalar() or 0

    query = (
        base.order_by(ChainExecution.created_at.desc()).offset(offset).limit(limit)
    )
    result = await db.execute(query)
    executions = list(result.scalars().all())

    return {
        "executions": [_execution_to_dict(e) for e in executions],
        "total": total,
        "limit": limit,
        "offset": offset,
    }
