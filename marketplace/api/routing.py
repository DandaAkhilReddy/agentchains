"""Routing API: direct route selection for a known content_hash."""

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from marketplace.database import get_db
from marketplace.services.router_service import STRATEGIES, smart_route

router = APIRouter(prefix="/route", tags=["routing"])


class RouteSelectRequest(BaseModel):
    candidates: list[dict] = Field(..., min_length=1)
    strategy: str = "best_value"
    buyer_region: str | None = None


@router.post("/select")
async def route_select(req: RouteSelectRequest):
    """Apply a routing strategy to rank candidates.

    Available strategies: cheapest, fastest, highest_quality, best_value,
    round_robin, weighted_random, locality.
    """
    result = smart_route(req.candidates, req.strategy, req.buyer_region)
    return {
        "strategy": req.strategy,
        "ranked": result,
        "count": len(result),
    }


@router.get("/strategies")
async def list_strategies():
    """List all available routing strategies."""
    return {
        "strategies": STRATEGIES,
        "default": "best_value",
        "descriptions": {
            "cheapest": "Score = 1 - normalize(price). Cheapest wins.",
            "fastest": "Score = 1 - normalize(avg_response_ms). Fastest wins.",
            "highest_quality": "0.5*quality + 0.3*reputation + 0.2*freshness.",
            "best_value": "0.4*(quality/price) + 0.25*reputation + 0.2*freshness + 0.15*(1-price).",
            "round_robin": "Fair rotation: score = 1/(1+access_count).",
            "weighted_random": "Probabilistic selection proportional to quality*reputation/price.",
            "locality": "Region-aware: 1.0 same, 0.5 adjacent, 0.2 other.",
        },
    }
