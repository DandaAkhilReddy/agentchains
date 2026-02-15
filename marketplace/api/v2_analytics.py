"""Open analytics endpoints for public market metrics."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from marketplace.database import get_db
from marketplace.schemas.dashboard import OpenMarketAnalyticsResponse
from marketplace.services import dashboard_service

router = APIRouter(prefix="/analytics", tags=["analytics-v2"])


@router.get("/market/open", response_model=OpenMarketAnalyticsResponse)
async def open_market_analytics(
    limit: int = Query(10, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
):
    return await dashboard_service.get_open_market_analytics(db, limit=limit)
