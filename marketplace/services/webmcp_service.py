"""WebMCP Service: tool registration, discovery, and action listing management."""

import hashlib
import json
import logging
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from marketplace.models.webmcp_tool import WebMCPTool
from marketplace.models.action_listing import ActionListing

logger = logging.getLogger(__name__)


def _hash_schema(schema: dict) -> str:
    """SHA-256 hash of JSON Schema for Tool Lock verification."""
    canonical = json.dumps(schema, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode()).hexdigest()


def _tool_to_dict(tool: WebMCPTool) -> dict:
    """Convert WebMCPTool ORM to response dict."""
    return {
        "id": tool.id,
        "name": tool.name,
        "description": tool.description,
        "domain": tool.domain,
        "endpoint_url": tool.endpoint_url,
        "input_schema": json.loads(tool.input_schema) if tool.input_schema else {},
        "output_schema": json.loads(tool.output_schema) if tool.output_schema else {},
        "creator_id": tool.creator_id,
        "agent_id": tool.agent_id,
        "category": tool.category,
        "version": tool.version,
        "status": tool.status,
        "execution_count": tool.execution_count,
        "avg_execution_time_ms": tool.avg_execution_time_ms,
        "success_rate": float(tool.success_rate) if tool.success_rate else 1.0,
        "created_at": tool.created_at.isoformat() if tool.created_at else None,
        "updated_at": tool.updated_at.isoformat() if tool.updated_at else None,
    }


def _listing_to_dict(listing: ActionListing) -> dict:
    """Convert ActionListing ORM to response dict."""
    return {
        "id": listing.id,
        "tool_id": listing.tool_id,
        "seller_id": listing.seller_id,
        "title": listing.title,
        "description": listing.description,
        "price_per_execution": float(listing.price_per_execution),
        "currency": listing.currency,
        "default_parameters": json.loads(listing.default_parameters) if listing.default_parameters else {},
        "max_executions_per_hour": listing.max_executions_per_hour,
        "requires_consent": listing.requires_consent,
        "domain_lock": json.loads(listing.domain_lock) if listing.domain_lock else [],
        "status": listing.status,
        "tags": json.loads(listing.tags) if listing.tags else [],
        "access_count": listing.access_count,
        "created_at": listing.created_at.isoformat() if listing.created_at else None,
        "updated_at": listing.updated_at.isoformat() if listing.updated_at else None,
    }


# ── Tool Registration & Discovery ──────────────────────────────


async def register_tool(
    db: AsyncSession,
    creator_id: str,
    name: str,
    domain: str,
    endpoint_url: str,
    category: str,
    description: str = "",
    input_schema: dict | None = None,
    output_schema: dict | None = None,
    agent_id: str | None = None,
    version: str = "1.0.0",
) -> dict:
    """Register a new WebMCP tool for marketplace discovery."""
    input_schema = input_schema or {}
    output_schema = output_schema or {}

    tool = WebMCPTool(
        name=name,
        description=description,
        domain=domain,
        endpoint_url=endpoint_url,
        input_schema=json.dumps(input_schema),
        output_schema=json.dumps(output_schema),
        schema_hash=_hash_schema(input_schema),
        creator_id=creator_id,
        agent_id=agent_id,
        category=category,
        version=version,
        status="pending",
    )
    db.add(tool)
    await db.commit()
    await db.refresh(tool)

    logger.info("WebMCP tool registered: %s (domain=%s)", tool.name, tool.domain)
    return _tool_to_dict(tool)


async def list_tools(
    db: AsyncSession,
    q: str | None = None,
    category: str | None = None,
    domain: str | None = None,
    status: str | None = None,
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[dict], int]:
    """Discover available WebMCP tools with optional filters."""
    query = select(WebMCPTool)
    count_query = select(func.count(WebMCPTool.id))

    # Default to showing only approved/active tools for public queries
    if status:
        query = query.where(WebMCPTool.status == status)
        count_query = count_query.where(WebMCPTool.status == status)
    else:
        query = query.where(WebMCPTool.status.in_(["approved", "active"]))
        count_query = count_query.where(WebMCPTool.status.in_(["approved", "active"]))

    if q:
        pattern = f"%{q}%"
        cond = WebMCPTool.name.ilike(pattern) | WebMCPTool.description.ilike(pattern)
        query = query.where(cond)
        count_query = count_query.where(cond)

    if category:
        query = query.where(WebMCPTool.category == category)
        count_query = count_query.where(WebMCPTool.category == category)

    if domain:
        query = query.where(WebMCPTool.domain == domain)
        count_query = count_query.where(WebMCPTool.domain == domain)

    total = (await db.execute(count_query)).scalar() or 0
    query = query.order_by(WebMCPTool.execution_count.desc())
    query = query.offset((page - 1) * page_size).limit(page_size)

    result = await db.execute(query)
    tools = [_tool_to_dict(t) for t in result.scalars().all()]

    return tools, total


async def get_tool(db: AsyncSession, tool_id: str) -> dict | None:
    """Get a single WebMCP tool by ID."""
    result = await db.execute(select(WebMCPTool).where(WebMCPTool.id == tool_id))
    tool = result.scalar_one_or_none()
    if not tool:
        return None
    return _tool_to_dict(tool)


async def get_tool_orm(db: AsyncSession, tool_id: str) -> WebMCPTool | None:
    """Get tool ORM object (for internal use)."""
    result = await db.execute(select(WebMCPTool).where(WebMCPTool.id == tool_id))
    return result.scalar_one_or_none()


async def approve_tool(
    db: AsyncSession,
    tool_id: str,
    admin_creator_id: str,
    notes: str = "",
) -> dict | None:
    """Admin approves a pending tool for marketplace use."""
    result = await db.execute(select(WebMCPTool).where(WebMCPTool.id == tool_id))
    tool = result.scalar_one_or_none()
    if not tool:
        return None

    tool.status = "approved"
    tool.approval_notes = notes
    tool.updated_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(tool)

    logger.info("WebMCP tool approved: %s by admin %s", tool.name, admin_creator_id)
    return _tool_to_dict(tool)


# ── Action Listing Management ──────────────────────────────────


async def create_action_listing(
    db: AsyncSession,
    tool_id: str,
    seller_id: str,
    title: str,
    price_per_execution: float,
    description: str = "",
    default_parameters: dict | None = None,
    max_executions_per_hour: int = 60,
    requires_consent: bool = True,
    domain_lock: list[str] | None = None,
    tags: list[str] | None = None,
) -> dict:
    """Create an action listing for a WebMCP tool."""
    # Verify tool exists and is approved
    tool = await get_tool_orm(db, tool_id)
    if not tool:
        raise ValueError(f"Tool {tool_id} not found")
    if tool.status not in ("approved", "active"):
        raise ValueError(f"Tool {tool_id} is not approved (status={tool.status})")

    listing = ActionListing(
        tool_id=tool_id,
        seller_id=seller_id,
        title=title,
        description=description,
        price_per_execution=price_per_execution,
        default_parameters=json.dumps(default_parameters or {}),
        max_executions_per_hour=max_executions_per_hour,
        requires_consent=requires_consent,
        domain_lock=json.dumps(domain_lock or []),
        tags=json.dumps(tags or []),
    )
    db.add(listing)
    await db.commit()
    await db.refresh(listing)

    logger.info("Action listing created: %s (tool=%s)", listing.title, tool_id)
    return _listing_to_dict(listing)


async def list_action_listings(
    db: AsyncSession,
    q: str | None = None,
    category: str | None = None,
    max_price: float | None = None,
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[dict], int]:
    """Browse available action listings."""
    query = select(ActionListing).where(ActionListing.status == "active")
    count_query = select(func.count(ActionListing.id)).where(ActionListing.status == "active")

    if q:
        pattern = f"%{q}%"
        cond = ActionListing.title.ilike(pattern) | ActionListing.description.ilike(pattern)
        query = query.where(cond)
        count_query = count_query.where(cond)

    if max_price is not None:
        query = query.where(ActionListing.price_per_execution <= max_price)
        count_query = count_query.where(ActionListing.price_per_execution <= max_price)

    total = (await db.execute(count_query)).scalar() or 0
    query = query.order_by(ActionListing.access_count.desc())
    query = query.offset((page - 1) * page_size).limit(page_size)

    result = await db.execute(query)
    listings = [_listing_to_dict(al) for al in result.scalars().all()]

    return listings, total


async def get_action_listing(db: AsyncSession, listing_id: str) -> dict | None:
    """Get a single action listing by ID."""
    result = await db.execute(
        select(ActionListing).where(ActionListing.id == listing_id)
    )
    listing = result.scalar_one_or_none()
    if not listing:
        return None
    return _listing_to_dict(listing)


async def get_action_listing_orm(db: AsyncSession, listing_id: str) -> ActionListing | None:
    """Get action listing ORM object (for internal use)."""
    result = await db.execute(
        select(ActionListing).where(ActionListing.id == listing_id)
    )
    return result.scalar_one_or_none()
