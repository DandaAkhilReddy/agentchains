"""Express delivery endpoint — single-request purchase returning content immediately."""

import asyncio

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from marketplace.core.auth import get_current_agent_id
from marketplace.database import get_db
from marketplace.services import demand_service, express_service

router = APIRouter(prefix="/express", tags=["express"])


@router.get("/{listing_id}")
async def express_buy(
    listing_id: str,
    db: AsyncSession = Depends(get_db),
    buyer_id: str = Depends(get_current_agent_id),
):
    """Single-request purchase: returns content immediately.

    1. Gets listing metadata (cached or DB)
    2. Gets content bytes (cached or HashFS)
    3. Auto-creates completed transaction record
    4. Returns content with timing info

    Target: <100ms for cached content.
    """
    response = await express_service.express_buy(db, listing_id, buyer_id)

    # Log demand signal
    try:
        asyncio.ensure_future(demand_service.log_search(
            db, query_text=listing_id, source="express",
            requester_id=buyer_id, matched_count=1, led_to_purchase=1,
        ))
    except Exception:
        pass

    return response
