"""Express delivery endpoint — single-request purchase returning content immediately."""

from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from marketplace.core.auth import get_current_agent_id
from marketplace.core.async_tasks import fire_and_forget
from marketplace.database import async_session, get_db
from marketplace.services import demand_service, express_service

router = APIRouter(prefix="/express", tags=["express"])


class ExpressBuyRequest(BaseModel):
    payment_method: str = Field("token", pattern="^(token|fiat|simulated)$")


@router.post("/{listing_id}")
async def express_buy(
    listing_id: str,
    body: Optional[ExpressBuyRequest] = None,
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
    payment_method = body.payment_method if body else "token"
    response = await express_service.express_buy(db, listing_id, buyer_id, payment_method)

    # Log demand signal in background with its own session
    # (the request-scoped `db` will close when the handler returns)
    async def _log_demand():
        try:
            async with async_session() as bg_db:
                await demand_service.log_search(
                    bg_db, query_text=listing_id, source="express",
                    requester_id=buyer_id, matched_count=1, led_to_purchase=1,
                )
        except Exception:
            pass

    fire_and_forget(_log_demand(), task_name="express_log_demand")

    return response
