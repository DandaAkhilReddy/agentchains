"""Open analytics endpoints for public market metrics."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from marketplace.database import get_db
from marketplace.schemas.dashboard import OpenMarketAnalyticsResponse
from marketplace.services import dashboard_service

router = APIRouter(prefix="/analytics", tags=["analytics-v2"])
logger = logging.getLogger(__name__)


@router.get("/market/open", response_model=OpenMarketAnalyticsResponse)
async def open_market_analytics(
    limit: int = Query(10, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
):
    try:
        return await dashboard_service.get_open_market_analytics(db, limit=limit)
    except Exception:
        logger.exception("open_market_analytics_failed")
        return {
            "generated_at": dashboard_service._utcnow(),  # noqa: SLF001
            "total_agents": 0,
            "total_listings": 0,
            "total_completed_transactions": 0,
            "platform_volume_usd": 0.0,
            "total_money_saved_usd": 0.0,
            "top_agents_by_revenue": [],
            "top_agents_by_usage": [],
            "top_categories_by_usage": [],
        }
