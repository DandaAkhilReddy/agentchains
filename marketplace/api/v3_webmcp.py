"""WebMCP v3 API — tool registration, action listings, and execution."""

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession

from marketplace.core.auth import get_current_agent_id
from marketplace.core.creator_auth import get_current_creator_id
from marketplace.database import get_db
from marketplace.services import webmcp_service
from marketplace.services import action_executor

router = APIRouter(prefix="/webmcp", tags=["webmcp"])


# ── Request/Response Models ─────────────────────────────────────


class ToolRegisterRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    name: str = Field(..., min_length=1, max_length=200)
    description: str = ""
    domain: str = Field(..., min_length=1, max_length=500)
    endpoint_url: str = Field(..., min_length=1, max_length=1000)
    category: str = Field(..., min_length=1, max_length=50)
    input_schema: dict | None = None
    output_schema: dict | None = None
    agent_id: str | None = None
    version: str = "1.0.0"


class ToolApproveRequest(BaseModel):
    notes: str = ""


class ActionCreateRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    tool_id: str = Field(..., min_length=1)
    title: str = Field(..., min_length=1, max_length=255)
    description: str = ""
    price_per_execution: float = Field(..., gt=0)
    default_parameters: dict | None = None
    max_executions_per_hour: int = Field(default=60, ge=1, le=10000)
    requires_consent: bool = True
    domain_lock: list[str] | None = None
    tags: list[str] | None = None


class ExecuteRequest(BaseModel):
    parameters: dict = Field(default_factory=dict)
    consent: bool = False


# ── Tool Endpoints ──────────────────────────────────────────────


@router.post("/tools")
async def register_tool(
    req: ToolRegisterRequest,
    db: AsyncSession = Depends(get_db),
    creator_id: str = Depends(get_current_creator_id),
):
    """Register a new WebMCP tool (requires creator auth)."""
    result = await webmcp_service.register_tool(
        db,
        creator_id=creator_id,
        name=req.name,
        domain=req.domain,
        endpoint_url=req.endpoint_url,
        category=req.category,
        description=req.description,
        input_schema=req.input_schema,
        output_schema=req.output_schema,
        agent_id=req.agent_id,
        version=req.version,
    )
    return result


@router.get("/tools")
async def list_tools(
    q: str | None = None,
    category: str | None = None,
    domain: str | None = None,
    status: str | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """Discover available WebMCP tools (public)."""
    tools, total = await webmcp_service.list_tools(
        db, q=q, category=category, domain=domain,
        status=status, page=page, page_size=page_size,
    )
    return {"tools": tools, "total": total, "page": page, "page_size": page_size}


@router.get("/tools/{tool_id}")
async def get_tool(
    tool_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Get WebMCP tool details (public)."""
    tool = await webmcp_service.get_tool(db, tool_id)
    if not tool:
        raise HTTPException(status_code=404, detail="Tool not found")
    return tool


@router.put("/tools/{tool_id}/approve")
async def approve_tool(
    tool_id: str,
    req: ToolApproveRequest,
    db: AsyncSession = Depends(get_db),
    creator_id: str = Depends(get_current_creator_id),
):
    """Approve a pending WebMCP tool (admin only)."""
    result = await webmcp_service.approve_tool(db, tool_id, creator_id, req.notes)
    if not result:
        raise HTTPException(status_code=404, detail="Tool not found")
    return result


# ── Action Listing Endpoints ────────────────────────────────────


@router.post("/actions")
async def create_action(
    req: ActionCreateRequest,
    db: AsyncSession = Depends(get_db),
    agent_id: str = Depends(get_current_agent_id),
):
    """Create an action listing for a WebMCP tool (requires agent auth)."""
    try:
        result = await webmcp_service.create_action_listing(
            db,
            tool_id=req.tool_id,
            seller_id=agent_id,
            title=req.title,
            description=req.description,
            price_per_execution=req.price_per_execution,
            default_parameters=req.default_parameters,
            max_executions_per_hour=req.max_executions_per_hour,
            requires_consent=req.requires_consent,
            domain_lock=req.domain_lock,
            tags=req.tags,
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/actions")
async def list_actions(
    q: str | None = None,
    category: str | None = None,
    max_price: float | None = Query(default=None, ge=0),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """Browse available action listings (public)."""
    listings, total = await webmcp_service.list_action_listings(
        db, q=q, category=category, max_price=max_price,
        page=page, page_size=page_size,
    )
    return {"actions": listings, "total": total, "page": page, "page_size": page_size}


@router.get("/actions/{action_id}")
async def get_action(
    action_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Get action listing details (public)."""
    listing = await webmcp_service.get_action_listing(db, action_id)
    if not listing:
        raise HTTPException(status_code=404, detail="Action listing not found")
    return listing


# ── Execution Endpoints ─────────────────────────────────────────


@router.post("/execute/{action_id}")
async def execute_action(
    action_id: str,
    req: ExecuteRequest,
    db: AsyncSession = Depends(get_db),
    agent_id: str = Depends(get_current_agent_id),
):
    """Execute a WebMCP action (requires agent auth + consent)."""
    try:
        result = await action_executor.execute_action(
            db,
            listing_id=action_id,
            buyer_id=agent_id,
            parameters=req.parameters,
            consent=req.consent,
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/executions")
async def list_executions(
    status: str | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    agent_id: str = Depends(get_current_agent_id),
):
    """List my executions (requires agent auth)."""
    executions, total = await action_executor.list_executions(
        db, buyer_id=agent_id, status=status,
        page=page, page_size=page_size,
    )
    return {"executions": executions, "total": total, "page": page, "page_size": page_size}


@router.get("/executions/{execution_id}")
async def get_execution(
    execution_id: str,
    db: AsyncSession = Depends(get_db),
    agent_id: str = Depends(get_current_agent_id),
):
    """Get execution details with proof (requires agent auth)."""
    result = await action_executor.get_execution(db, execution_id)
    if not result:
        raise HTTPException(status_code=404, detail="Execution not found")
    return result


@router.post("/executions/{execution_id}/cancel")
async def cancel_execution(
    execution_id: str,
    db: AsyncSession = Depends(get_db),
    agent_id: str = Depends(get_current_agent_id),
):
    """Cancel a pending execution (requires agent auth)."""
    try:
        result = await action_executor.cancel_execution(db, execution_id, agent_id)
        if not result:
            raise HTTPException(status_code=404, detail="Execution not found")
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
