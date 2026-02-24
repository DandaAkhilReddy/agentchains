import logging

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from marketplace.database import get_db
from marketplace.models.agent import RegisteredAgent
from marketplace.models.listing import DataListing
from marketplace.models.transaction import Transaction
from marketplace.schemas.common import CacheStats, HealthResponse
from marketplace.services.cache_service import agent_cache, content_cache, listing_cache

logger = logging.getLogger(__name__)

router = APIRouter(tags=["health"])

_VERSION = "0.4.0"


@router.get("/health")
async def health_check(db: AsyncSession = Depends(get_db)):
    from marketplace.config import settings as _cfg

    _is_prod = _cfg.environment.lower() in {"production", "prod"}

    # In production, return minimal info to avoid leaking operational metrics
    if _is_prod:
        try:
            await db.execute(text("SELECT 1"))
            return {"status": "healthy", "version": _VERSION}
        except Exception:
            return JSONResponse(
                status_code=503,
                content={"status": "unhealthy", "version": _VERSION},
            )

    agents = (await db.execute(select(func.count(RegisteredAgent.id)))).scalar() or 0
    listings = (await db.execute(select(func.count(DataListing.id)))).scalar() or 0
    txns = (await db.execute(select(func.count(Transaction.id)))).scalar() or 0

    return HealthResponse(
        status="healthy",
        version=_VERSION,
        agents_count=agents,
        listings_count=listings,
        transactions_count=txns,
        cache_stats=CacheStats(
            listings=listing_cache.stats(),
            content=content_cache.stats(),
            agents=agent_cache.stats(),
        ),
    )


@router.get("/health/ready")
async def readiness_check(db: AsyncSession = Depends(get_db)):
    """Readiness probe — verifies DB connectivity."""
    try:
        await db.execute(text("SELECT 1"))
        return {"status": "ready", "database": "connected"}
    except Exception:
        logger.exception("Readiness check failed — database unreachable")
        return JSONResponse(
            status_code=503,
            content={"status": "not_ready", "database": "unavailable"},
        )
