"""Auto-match endpoint: agents describe what they need, marketplace finds the best seller."""

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from marketplace.core.auth import get_current_agent_id
from marketplace.core.async_tasks import fire_and_forget
from marketplace.database import async_session, get_db
from marketplace.services import demand_service, match_service

router = APIRouter(prefix="/agents", tags=["auto-match"])


class AutoMatchRequest(BaseModel):
    description: str = Field(..., min_length=1, max_length=500)
    category: str | None = None
    max_price: float | None = Field(default=None, ge=0)
    auto_buy: bool = False
    auto_buy_max_price: float | None = Field(default=None, ge=0)
    routing_strategy: str | None = None  # cheapest | fastest | highest_quality | best_value | round_robin | weighted_random | locality
    buyer_region: str | None = None


@router.post("/auto-match")
async def auto_match(
    req: AutoMatchRequest,
    db: AsyncSession = Depends(get_db),
    buyer_id: str = Depends(get_current_agent_id),
):
    """Find the best listing matching a buyer's described need.

    If auto_buy=True and a match is found under auto_buy_max_price
    with score >= 0.3, automatically executes an express purchase.
    """
    result = await match_service.auto_match(
        db, req.description, req.category, req.max_price, buyer_id,
        routing_strategy=req.routing_strategy, buyer_region=req.buyer_region,
    )

    # Log demand signal with its own session
    async def _log_demand():
        try:
            async with async_session() as bg_db:
                await demand_service.log_search(
                    bg_db, query_text=req.description, category=req.category,
                    source="auto_match", requester_id=buyer_id,
                    matched_count=len(result["matches"]), max_price=req.max_price,
                    led_to_purchase=1 if (req.auto_buy and result["matches"]) else 0,
                )
        except Exception:
            pass

    fire_and_forget(_log_demand(), task_name="automatch_log_demand")

    if req.auto_buy and result["matches"]:
        top = result["matches"][0]
        max_auto = req.auto_buy_max_price or req.max_price or 0.05
        if top["price_usdc"] <= max_auto and top["match_score"] >= 0.3:
            from marketplace.services.express_service import express_buy

            purchase_response = await express_buy(db, top["listing_id"], buyer_id)
            purchase_data = purchase_response.body.decode("utf-8")
            import json

            result["auto_purchased"] = True
            result["purchase_result"] = json.loads(purchase_data)

    return result
