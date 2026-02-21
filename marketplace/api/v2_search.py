"""Search V2 API — Azure AI Search powered endpoints for listings, agents, and tools."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from marketplace.config import settings
from marketplace.core.creator_auth import get_current_creator_id
from marketplace.database import get_db
from marketplace.services.search_v2_service import get_search_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/search", tags=["search"])


# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------

class FacetValue(BaseModel):
    value: str
    count: int


class SearchResult(BaseModel):
    results: list[dict] = Field(default_factory=list)
    count: int = 0
    facets: dict[str, list[FacetValue]] = Field(default_factory=dict)


class SuggestionResult(BaseModel):
    suggestions: list[str] = Field(default_factory=list)


class ReindexResult(BaseModel):
    status: str = "completed"
    indexes_created: dict[str, bool] = Field(default_factory=dict)
    documents_indexed: dict[str, int] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

# OData keywords that must not appear in user-supplied filter values
_ODATA_KEYWORDS = {"eq", "ne", "and", "or", "not", "gt", "lt", "ge", "le"}


def _sanitize_odata_value(value: str) -> str:
    """Sanitize a user-supplied value before interpolation into an OData filter.

    Raises HTTPException if the value contains single quotes or OData operators.
    """
    if "'" in value:
        raise HTTPException(
            status_code=400,
            detail="Invalid filter value: single quotes are not allowed",
        )
    # Check for OData keyword injection (whole-word match, case-insensitive)
    tokens = value.lower().split()
    for token in tokens:
        if token in _ODATA_KEYWORDS:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid filter value: reserved keyword '{token}'",
            )
    return value


def _admin_ids() -> set[str]:
    return {v.strip() for v in settings.admin_creator_ids.split(",") if v.strip()}


def _require_admin(authorization: str | None) -> str:
    """Verify that the caller is an admin."""
    creator_id = get_current_creator_id(authorization)
    admin_ids = _admin_ids()
    if admin_ids and creator_id not in admin_ids:
        raise HTTPException(status_code=403, detail="Admin access required")
    return creator_id


def _build_listing_filter(
    category: str | None = None,
    min_price: float | None = None,
    max_price: float | None = None,
) -> str | None:
    """Construct an OData filter expression for listings."""
    parts: list[str] = []
    if category:
        parts.append(f"category eq '{_sanitize_odata_value(category)}'")
    if min_price is not None:
        parts.append(f"price_usd ge {min_price}")
    if max_price is not None:
        parts.append(f"price_usd le {max_price}")
    return " and ".join(parts) if parts else None


def _build_category_filter(category: str | None = None) -> str | None:
    if category:
        return f"category eq '{_sanitize_odata_value(category)}'"
    return None


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.get("", response_model=SearchResult)
async def search_all(
    q: str = Query("", description="Search text"),
    type: str = Query("listing", description="Entity type: listing, agent, tool"),
    category: str | None = Query(None, description="Filter by category"),
    min_price: float | None = Query(None, description="Minimum price (listings only)"),
    max_price: float | None = Query(None, description="Maximum price (listings only)"),
    sort_by: str | None = Query(None, description="Sort field (e.g. price_usd, created_at)"),
    top: int = Query(20, ge=1, le=100, description="Number of results"),
    skip: int = Query(0, ge=0, description="Number of results to skip"),
) -> SearchResult:
    """Full-text search across listings, agents, or tools."""
    svc = get_search_service()

    if type == "listing":
        filters = _build_listing_filter(category, min_price, max_price)
        data = svc.search_listings(query=q, filters=filters, top=top, skip=skip)
    elif type == "agent":
        filters = _build_category_filter(category)
        data = svc.search_agents(query=q, filters=filters, top=top, skip=skip)
    elif type == "tool":
        filters = _build_category_filter(category)
        data = svc.search_tools(query=q, filters=filters, top=top, skip=skip)
    else:
        raise HTTPException(status_code=400, detail=f"Invalid type: {type}. Use listing, agent, or tool.")

    return SearchResult(**data)


@router.get("/listings", response_model=SearchResult)
async def search_listings(
    query: str = Query("", alias="q", description="Search text"),
    category: str | None = Query(None),
    min_price: float | None = Query(None),
    max_price: float | None = Query(None),
    sort_by: str | None = Query(None, description="Sort field (e.g. price_usd, created_at)"),
    top: int = Query(20, ge=1, le=100),
    skip: int = Query(0, ge=0),
) -> SearchResult:
    """Full-text search listings with facets for category, status, and tags."""
    svc = get_search_service()
    filters = _build_listing_filter(category, min_price, max_price)
    data = svc.search_listings(query=query, filters=filters, top=top, skip=skip)
    return SearchResult(**data)


@router.get("/agents", response_model=SearchResult)
async def search_agents(
    query: str = Query("", alias="q", description="Search text"),
    agent_type: str | None = Query(None, description="Filter by agent type (seller/buyer/both)"),
    status: str | None = Query(None, description="Filter by status (active/inactive)"),
    top: int = Query(20, ge=1, le=100),
    skip: int = Query(0, ge=0),
) -> SearchResult:
    """Search registered agents with optional agent_type and status filters."""
    svc = get_search_service()
    parts: list[str] = []
    if agent_type:
        parts.append(f"category eq '{_sanitize_odata_value(agent_type)}'")
    if status:
        parts.append(f"status eq '{_sanitize_odata_value(status)}'")
    filters = " and ".join(parts) if parts else None
    data = svc.search_agents(query=query, filters=filters, top=top, skip=skip)
    return SearchResult(**data)


@router.get("/tools", response_model=SearchResult)
async def search_tools(
    query: str = Query("", alias="q", description="Search text"),
    category: str | None = Query(None),
    top: int = Query(20, ge=1, le=100),
    skip: int = Query(0, ge=0),
) -> SearchResult:
    """Search WebMCP tools with optional category filter."""
    svc = get_search_service()
    filters = _build_category_filter(category)
    data = svc.search_tools(query=query, filters=filters, top=top, skip=skip)
    return SearchResult(**data)


@router.get("/suggestions", response_model=SuggestionResult)
async def search_suggestions(
    q: str = Query("", min_length=1, description="Query prefix for typeahead"),
    type: str = Query("listing", description="Entity type: listing, agent, tool"),
    top: int = Query(5, ge=1, le=20),
) -> SuggestionResult:
    """Return typeahead suggestions for a query prefix.

    Uses a lightweight search with limited fields to provide fast suggestions.
    """
    svc = get_search_service()

    if type == "listing":
        data = svc.search_listings(query=q, top=top, skip=0)
        suggestions = [r.get("title", "") for r in data.get("results", []) if r.get("title")]
    elif type == "agent":
        data = svc.search_agents(query=q, top=top, skip=0)
        suggestions = [r.get("name", "") for r in data.get("results", []) if r.get("name")]
    elif type == "tool":
        data = svc.search_tools(query=q, top=top, skip=0)
        suggestions = [r.get("name", "") for r in data.get("results", []) if r.get("name")]
    else:
        raise HTTPException(status_code=400, detail=f"Invalid type: {type}. Use listing, agent, or tool.")

    return SuggestionResult(suggestions=suggestions)


@router.post("/reindex", response_model=ReindexResult)
async def reindex(
    authorization: str | None = Header(default=None),
    db: AsyncSession = Depends(get_db),
) -> ReindexResult:
    """Trigger a full reindex of all entities into Azure AI Search.

    Requires admin authentication. Syncs listings, agents, and tools
    from the database to Azure AI Search indexes.
    """
    _require_admin(authorization)

    svc = get_search_service()

    # Ensure indexes exist
    indexes_created = svc.ensure_indexes()

    # Sync data from database to search indexes
    from marketplace.services.search_v2_service import (
        sync_listings_index,
        sync_agents_index,
        sync_tools_index,
    )

    listings_result = await sync_listings_index(db)
    agents_result = await sync_agents_index(db)
    tools_result = await sync_tools_index(db)

    logger.info(
        "Reindex triggered by admin — listings=%s agents=%s tools=%s",
        listings_result, agents_result, tools_result,
    )

    return ReindexResult(
        status="completed",
        indexes_created=indexes_created,
        documents_indexed={
            "listings": listings_result.get("synced", 0),
            "agents": agents_result.get("synced", 0),
            "tools": tools_result.get("synced", 0),
        },
    )
