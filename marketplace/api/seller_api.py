"""Seller API: bulk listing, demand intelligence, pricing, webhooks."""

import json

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from marketplace.core.auth import get_current_agent_id
from marketplace.database import get_db
from marketplace.services import seller_service

router = APIRouter(prefix="/seller", tags=["seller"])


class BulkListRequest(BaseModel):
    items: list[dict] = Field(..., min_length=1, max_length=100)


class PriceSuggestRequest(BaseModel):
    category: str
    quality_score: float = Field(default=0.5, ge=0, le=1)


class WebhookRegisterRequest(BaseModel):
    url: str = Field(..., min_length=1, max_length=500)
    event_types: list[str] | None = None
    secret: str | None = None


@router.post("/bulk-list")
async def bulk_list(
    req: BulkListRequest,
    db: AsyncSession = Depends(get_db),
    seller_id: str = Depends(get_current_agent_id),
):
    """Create up to 100 listings in a single request."""
    return await seller_service.bulk_list(db, seller_id, req.items)


@router.get("/demand-for-me")
async def demand_for_me(
    db: AsyncSession = Depends(get_db),
    seller_id: str = Depends(get_current_agent_id),
):
    """Get demand signals matching your catalog capabilities."""
    matches = await seller_service.get_demand_for_seller(db, seller_id)
    return {"matches": matches, "count": len(matches)}


@router.post("/price-suggest")
async def price_suggest(
    req: PriceSuggestRequest,
    db: AsyncSession = Depends(get_db),
    seller_id: str = Depends(get_current_agent_id),
):
    """Get optimal pricing suggestion based on market data."""
    return await seller_service.suggest_price(db, seller_id, req.category, req.quality_score)


@router.post("/webhook")
async def register_webhook(
    req: WebhookRegisterRequest,
    db: AsyncSession = Depends(get_db),
    seller_id: str = Depends(get_current_agent_id),
):
    """Register a webhook for demand/event notifications."""
    wh = await seller_service.register_webhook(
        db, seller_id, req.url, req.event_types, req.secret,
    )
    return {
        "id": wh.id,
        "url": wh.url,
        "event_types": json.loads(wh.event_types),
        "status": wh.status,
    }


@router.get("/webhooks")
async def list_webhooks(
    db: AsyncSession = Depends(get_db),
    seller_id: str = Depends(get_current_agent_id),
):
    """List your registered webhooks."""
    webhooks = await seller_service.get_webhooks(db, seller_id)
    return {
        "webhooks": [
            {
                "id": wh.id,
                "url": wh.url,
                "event_types": json.loads(wh.event_types),
                "status": wh.status,
                "failure_count": wh.failure_count,
            }
            for wh in webhooks
        ],
        "count": len(webhooks),
    }
