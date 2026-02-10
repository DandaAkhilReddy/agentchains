from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import APIRouter, Depends

from marketplace.database import get_db
from marketplace.models.agent import RegisteredAgent
from marketplace.models.listing import DataListing
from marketplace.models.transaction import Transaction
from marketplace.schemas.common import HealthResponse

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
async def health_check(db: AsyncSession = Depends(get_db)):
    agents = (await db.execute(select(func.count(RegisteredAgent.id)))).scalar() or 0
    listings = (await db.execute(select(func.count(DataListing.id)))).scalar() or 0
    txns = (await db.execute(select(func.count(Transaction.id)))).scalar() or 0

    return HealthResponse(
        status="healthy",
        version="0.1.0",
        agents_count=agents,
        listings_count=listings,
        transactions_count=txns,
    )
