"""Chain Registry v5 API — chain template CRUD, execution, forking, and provenance."""

from __future__ import annotations

import json
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from marketplace.core.auth import get_current_agent_id
from marketplace.core.auth_context import AuthContext
from marketplace.core.trust_gate import require_trust_tier
from marketplace.database import get_db
from marketplace.models.chain_template import ChainExecution
from marketplace.services import (
    auto_chain_service,
    chain_analytics_service,
    chain_policy_service,
    chain_provenance_service,
    chain_registry_service,
    chain_settlement_service,
)
from marketplace.services.smart_orchestrator import SmartOrchestrator

router = APIRouter(prefix="", tags=["chains"])


# ── Pydantic request models ──────────────────────────────────────


class ChainTemplateCreateRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    name: str = Field(..., min_length=1, max_length=200)
    description: str = Field(default="", max_length=10_000)
    category: str = Field(default="general", max_length=50)
    graph_json: str = Field(..., min_length=2, max_length=1_000_000, description="JSON DAG definition")
    tags: list[str] = Field(default_factory=list, max_length=50)
    max_budget_usd: float | None = Field(default=None, ge=0, le=1_000_000)


class ChainTemplateForkRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    name: str | None = Field(default=None, min_length=1, max_length=200)
    graph_json: str | None = Field(default=None, min_length=2, max_length=1_000_000)


class ChainExecuteRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    input_data: dict = Field(default_factory=dict)
    idempotency_key: str | None = Field(default=None, max_length=64)


class ChainComposeRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    task_description: str = Field(..., min_length=5, max_length=2000)
    max_price: float | None = Field(default=None, ge=0)
    min_quality: float | None = Field(default=None, ge=0, le=1)


class SuggestAgentsRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    capability: str = Field(..., min_length=1, max_length=100)
    max_results: int = Field(default=10, ge=1, le=50)
    max_price: float | None = Field(default=None, ge=0)
    min_quality: float | None = Field(default=None, ge=0, le=1)


class SmartComposeRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    task_description: str = Field(..., min_length=5, max_length=2000)
    auto_approve: bool = Field(default=True)


class ChainPolicyCreateRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    name: str = Field(..., min_length=1, max_length=200)
    description: str = Field(default="", max_length=5000)
    policy_type: str = Field(..., max_length=30, pattern="^[a-zA-Z_][a-zA-Z0-9_-]*$")
    rules_json: str = Field(..., min_length=2, max_length=100_000)
    enforcement: str = Field(default="block", pattern="^(block|warn|log)$")
    scope: str = Field(default="chain", pattern="^(chain|node|global)$")


class EvaluatePoliciesRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    policy_ids: list[str] = Field(..., min_length=1)


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
    _trust: AuthContext = Depends(require_trust_tier("T2")),
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
    if execution.initiated_by != agent_id:
        raise HTTPException(status_code=403, detail="Only the execution initiator can view this execution")
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
    """List executions for a specific chain template.

    Only the template author or execution initiator can see executions.
    Authors see all executions; other agents see only their own.
    """
    template = await chain_registry_service.get_chain_template(db, template_id)
    if not template:
        raise HTTPException(status_code=404, detail="Chain template not found")

    base = select(ChainExecution).where(
        ChainExecution.chain_template_id == template_id
    )
    # Non-authors can only see their own executions
    if template.author_id != agent_id:
        base = base.where(ChainExecution.initiated_by == agent_id)
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


# ── Auto-Chaining Endpoints ─────────────────────────────────────


@router.post("/chains/compose", status_code=200)
async def compose_chain(
    req: ChainComposeRequest,
    db: AsyncSession = Depends(get_db),
    agent_id: str = Depends(get_current_agent_id),
):
    """Compose a draft chain template from a natural-language task description."""
    try:
        draft = await auto_chain_service.compose_chain_from_task(
            db,
            task_description=req.task_description,
            author_id=agent_id,
            max_price=req.max_price,
            min_quality=req.min_quality,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return draft


@router.post("/chains/suggest-agents", status_code=200)
async def suggest_agents(
    req: SuggestAgentsRequest,
    db: AsyncSession = Depends(get_db),
    agent_id: str = Depends(get_current_agent_id),
):
    """Suggest ranked agents for a given capability."""
    agents = await auto_chain_service.suggest_agents_for_capability(
        db,
        capability=req.capability,
        max_results=req.max_results,
        max_price=req.max_price,
        min_quality=req.min_quality,
    )
    return {"capability": req.capability, "agents": agents, "total": len(agents)}


@router.post("/chains/{chain_template_id}/validate", status_code=200)
async def validate_chain(
    chain_template_id: str,
    db: AsyncSession = Depends(get_db),
    agent_id: str = Depends(get_current_agent_id),
):
    """Validate that all agents in a chain template are active and reachable."""
    try:
        result = await auto_chain_service.validate_chain_compatibility(
            db, chain_template_id
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    return result


@router.post("/chains/smart-compose", status_code=200)
async def smart_compose_chain(
    req: SmartComposeRequest,
    db: AsyncSession = Depends(get_db),
    agent_id: str = Depends(get_current_agent_id),
):
    """Use an LLM to decompose a task and build an agent chain.

    When a LangGraph-compatible environment and LLM client are configured,
    this endpoint performs full LLM-driven task decomposition, agent matching,
    DAG construction, workflow execution, and result synthesis.

    Without an LLM client it falls back to keyword-based capability extraction
    using the existing auto_chain_service — no external dependencies required.
    """
    orchestrator = SmartOrchestrator(
        db=db,
        llm_client=None,  # No LLM client wired by default; callers may extend this
        auto_approve=req.auto_approve,
    )
    try:
        result = await orchestrator.compose_and_execute(
            task_description=req.task_description,
            initiated_by=agent_id,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
    return result


# ── Analytics & Provenance Entries Endpoints ──────────────────────


@router.get("/chain-templates/{template_id}/analytics")
async def get_chain_analytics(
    template_id: str,
    db: AsyncSession = Depends(get_db),
    agent_id: str = Depends(get_current_agent_id),
):
    """Get performance analytics for a chain template."""
    template = await chain_registry_service.get_chain_template(db, template_id)
    if not template:
        raise HTTPException(status_code=404, detail="Chain template not found")
    return await chain_analytics_service.get_chain_performance(db, template_id)


@router.get("/chains/popular")
async def get_popular_chains(
    category: str | None = None,
    limit: int = Query(default=20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    agent_id: str = Depends(get_current_agent_id),
):
    """Get the most popular chain templates by execution count."""
    chains = await chain_analytics_service.get_popular_chains(
        db, category=category, limit=limit
    )
    return {"chains": chains, "total": len(chains)}


@router.get("/chains/agents/{target_agent_id}/stats")
async def get_agent_chain_stats(
    target_agent_id: str,
    db: AsyncSession = Depends(get_db),
    agent_id: str = Depends(get_current_agent_id),
):
    """Get chain participation statistics for a specific agent."""
    return await chain_analytics_service.get_agent_chain_stats(db, target_agent_id)


@router.get("/chain-executions/{execution_id}/provenance-entries")
async def get_chain_provenance_entries(
    execution_id: str,
    event_type: str | None = None,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
    agent_id: str = Depends(get_current_agent_id),
):
    """Get provenance entries for a chain execution. Access-controlled."""
    # Access control: reuse same check as provenance endpoint
    execution = await chain_registry_service.get_chain_execution(db, execution_id)
    if not execution:
        raise HTTPException(status_code=404, detail="Chain execution not found")

    template = await chain_registry_service.get_chain_template(
        db, execution.chain_template_id
    )
    author_id = template.author_id if template else None

    if agent_id != execution.initiated_by and agent_id != author_id:
        raise HTTPException(
            status_code=403,
            detail="Only the chain initiator or template author can view provenance entries",
        )

    entries, total = await chain_provenance_service.get_provenance_entries(
        db, execution_id, event_type=event_type, limit=limit, offset=offset
    )
    timeline = await chain_provenance_service.get_provenance_timeline(db, execution_id)

    return {
        "entries": timeline[:limit],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


# ── Policy Endpoints ─────────────────────────────────────────────


def _policy_to_dict(p) -> dict:
    """Serialise a ChainPolicy ORM instance to a plain dict."""
    return {
        "id": p.id,
        "name": p.name,
        "description": p.description,
        "policy_type": p.policy_type,
        "rules_json": p.rules_json,
        "enforcement": p.enforcement,
        "owner_id": p.owner_id,
        "scope": p.scope,
        "status": p.status,
        "created_at": p.created_at.isoformat() if p.created_at else None,
        "updated_at": p.updated_at.isoformat() if p.updated_at else None,
    }


@router.post("/chains/policies", status_code=201)
async def create_chain_policy(
    req: ChainPolicyCreateRequest,
    db: AsyncSession = Depends(get_db),
    agent_id: str = Depends(get_current_agent_id),
):
    """Create a new chain policy."""
    try:
        json.loads(req.rules_json)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="rules_json must be valid JSON")
    try:
        policy = await chain_policy_service.create_policy(
            db,
            name=req.name,
            policy_type=req.policy_type,
            rules_json=req.rules_json,
            owner_id=agent_id,
            description=req.description,
            enforcement=req.enforcement,
            scope=req.scope,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return _policy_to_dict(policy)


@router.get("/chains/policies")
async def list_chain_policies(
    owner_id: str | None = None,
    policy_type: str | None = None,
    status: str | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
    agent_id: str = Depends(get_current_agent_id),
):
    """List chain policies with optional filters."""
    policies, total = await chain_policy_service.list_policies(
        db, owner_id=owner_id, policy_type=policy_type,
        status=status, limit=limit, offset=offset,
    )
    return {
        "policies": [_policy_to_dict(p) for p in policies],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


@router.post("/chains/{chain_template_id}/evaluate-policies")
async def evaluate_chain_policies(
    chain_template_id: str,
    req: EvaluatePoliciesRequest,
    db: AsyncSession = Depends(get_db),
    agent_id: str = Depends(get_current_agent_id),
):
    """Dry-run policy evaluation against a chain template."""
    template = await chain_registry_service.get_chain_template(db, chain_template_id)
    if not template:
        raise HTTPException(status_code=404, detail="Chain template not found")
    if template.author_id != agent_id:
        raise HTTPException(status_code=403, detail="Only the template author can evaluate policies")
    try:
        result = await chain_policy_service.evaluate_chain_policies(
            db, chain_template_id, req.policy_ids
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    return result


# ── Settlement Endpoints ─────────────────────────────────────────


@router.get("/chain-executions/{execution_id}/settlement")
async def get_chain_settlement(
    execution_id: str,
    db: AsyncSession = Depends(get_db),
    agent_id: str = Depends(get_current_agent_id),
):
    """Get settlement report for a chain execution."""
    execution = await chain_registry_service.get_chain_execution(db, execution_id)
    if not execution:
        raise HTTPException(status_code=404, detail="Chain execution not found")
    if execution.initiated_by != agent_id:
        raise HTTPException(status_code=403, detail="Only the execution initiator can view settlement")
    try:
        report = await chain_settlement_service.get_settlement_report(
            db, execution_id
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    return report


@router.get("/chain-templates/{template_id}/cost-estimate")
async def get_chain_cost_estimate(
    template_id: str,
    db: AsyncSession = Depends(get_db),
    agent_id: str = Depends(get_current_agent_id),
):
    """Get a pre-execution cost estimate for a chain template."""
    try:
        estimate = await chain_settlement_service.estimate_chain_cost(db, template_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    return estimate
