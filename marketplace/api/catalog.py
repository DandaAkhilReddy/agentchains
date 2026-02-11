"""Data Catalog API: sellers register capabilities, buyers discover and subscribe."""

import json

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from marketplace.core.auth import get_current_agent_id
from marketplace.database import get_db
from marketplace.services import catalog_service

router = APIRouter(prefix="/catalog", tags=["catalog"])


class CatalogCreateRequest(BaseModel):
    namespace: str = Field(..., min_length=1, max_length=100)
    topic: str = Field(..., min_length=1, max_length=200)
    description: str = ""
    schema_json: dict | None = None
    price_range_min: float = Field(default=0.001, ge=0)
    price_range_max: float = Field(default=0.01, ge=0)


class CatalogUpdateRequest(BaseModel):
    topic: str | None = None
    description: str | None = None
    schema_json: dict | None = None
    price_range_min: float | None = None
    price_range_max: float | None = None
    status: str | None = None


class SubscribeRequest(BaseModel):
    namespace_pattern: str = Field(..., min_length=1, max_length=100)
    topic_pattern: str = "*"
    category_filter: str | None = None
    max_price: float | None = Field(default=None, ge=0)
    min_quality: float | None = Field(default=None, ge=0, le=1)
    notify_via: str = "websocket"
    webhook_url: str | None = None


def _entry_to_dict(entry) -> dict:
    return {
        "id": entry.id,
        "agent_id": entry.agent_id,
        "namespace": entry.namespace,
        "topic": entry.topic,
        "description": entry.description,
        "schema_json": json.loads(entry.schema_json) if entry.schema_json else {},
        "price_range": [float(entry.price_range_min), float(entry.price_range_max)],
        "quality_avg": float(entry.quality_avg) if entry.quality_avg else 0.5,
        "active_listings_count": entry.active_listings_count,
        "status": entry.status,
        "created_at": entry.created_at.isoformat() if entry.created_at else None,
    }


@router.post("")
async def register_entry(
    req: CatalogCreateRequest,
    db: AsyncSession = Depends(get_db),
    agent_id: str = Depends(get_current_agent_id),
):
    """Register a capability in the data catalog."""
    entry = await catalog_service.register_catalog_entry(
        db, agent_id, req.namespace, req.topic,
        req.description, req.schema_json,
        req.price_range_min, req.price_range_max,
    )
    return _entry_to_dict(entry)


@router.get("/search")
async def search_catalog(
    q: str | None = None,
    namespace: str | None = None,
    min_quality: float | None = Query(default=None, ge=0, le=1),
    max_price: float | None = Query(default=None, ge=0),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """Search the data catalog for capabilities."""
    entries, total = await catalog_service.search_catalog(
        db, q=q, namespace=namespace,
        min_quality=min_quality, max_price=max_price,
        page=page, page_size=page_size,
    )
    return {
        "entries": [_entry_to_dict(e) for e in entries],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.get("/agent/{agent_id}")
async def get_agent_catalog(
    agent_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Get all catalog entries for a specific agent."""
    entries = await catalog_service.get_agent_catalog(db, agent_id)
    return {"entries": [_entry_to_dict(e) for e in entries], "count": len(entries)}


@router.get("/{entry_id}")
async def get_entry(
    entry_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Get a single catalog entry."""
    entry = await catalog_service.get_catalog_entry(db, entry_id)
    if not entry:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Catalog entry not found")
    return _entry_to_dict(entry)


@router.patch("/{entry_id}")
async def update_entry(
    entry_id: str,
    req: CatalogUpdateRequest,
    db: AsyncSession = Depends(get_db),
    agent_id: str = Depends(get_current_agent_id),
):
    """Update a catalog entry (owner only)."""
    kwargs = req.model_dump(exclude_unset=True)
    if "schema_json" in kwargs and kwargs["schema_json"] is not None:
        kwargs["schema_json"] = json.dumps(kwargs["schema_json"])
    entry = await catalog_service.update_catalog_entry(db, entry_id, agent_id, **kwargs)
    if not entry:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Entry not found or not owner")
    return _entry_to_dict(entry)


@router.delete("/{entry_id}")
async def delete_entry(
    entry_id: str,
    db: AsyncSession = Depends(get_db),
    agent_id: str = Depends(get_current_agent_id),
):
    """Retire a catalog entry (owner only)."""
    ok = await catalog_service.delete_catalog_entry(db, entry_id, agent_id)
    if not ok:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Entry not found or not owner")
    return {"deleted": True}


@router.post("/subscribe")
async def subscribe(
    req: SubscribeRequest,
    db: AsyncSession = Depends(get_db),
    subscriber_id: str = Depends(get_current_agent_id),
):
    """Subscribe to catalog updates matching a pattern."""
    sub = await catalog_service.subscribe(
        db, subscriber_id, req.namespace_pattern,
        req.topic_pattern, req.category_filter,
        req.max_price, req.min_quality,
        req.notify_via, req.webhook_url,
    )
    return {
        "id": sub.id,
        "namespace_pattern": sub.namespace_pattern,
        "topic_pattern": sub.topic_pattern,
        "notify_via": sub.notify_via,
        "status": sub.status,
    }


@router.delete("/subscribe/{sub_id}")
async def unsubscribe(
    sub_id: str,
    db: AsyncSession = Depends(get_db),
    subscriber_id: str = Depends(get_current_agent_id),
):
    """Unsubscribe from catalog updates."""
    ok = await catalog_service.unsubscribe(db, sub_id, subscriber_id)
    if not ok:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Subscription not found or not owner")
    return {"unsubscribed": True}


@router.post("/auto-populate")
async def auto_populate(
    db: AsyncSession = Depends(get_db),
    agent_id: str = Depends(get_current_agent_id),
):
    """Scan agent's existing listings and auto-create catalog entries."""
    entries = await catalog_service.auto_populate_catalog(db, agent_id)
    return {
        "created": len(entries),
        "entries": [_entry_to_dict(e) for e in entries],
    }
