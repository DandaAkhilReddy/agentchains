"""Analytics API: trending queries, demand gaps, opportunities, earnings, agent profiles, leaderboards."""

import json

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from marketplace.core.auth import get_current_agent_id
from marketplace.database import get_db
from marketplace.models.agent import RegisteredAgent
from marketplace.schemas.analytics import (
    AgentStatsResponse,
    DemandGapResponse,
    DemandGapsResponse,
    EarningsResponse,
    EarningsTimelineEntry,
    MultiLeaderboardEntry,
    MultiLeaderboardResponse,
    OpportunitiesResponse,
    OpportunityResponse,
    TrendingQueryResponse,
    TrendingResponse,
)
from marketplace.services import analytics_service, demand_service

router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get("/trending", response_model=TrendingResponse)
async def get_trending(
    limit: int = Query(20, ge=1, le=100),
    hours: int = Query(6, ge=1, le=168),
    db: AsyncSession = Depends(get_db),
):
    """Get trending search queries by velocity."""
    signals = await demand_service.get_trending(db, limit=limit, hours=hours)
    return TrendingResponse(
        time_window_hours=hours,
        trends=[
            TrendingQueryResponse(
                query_pattern=s.query_pattern,
                category=s.category,
                search_count=s.search_count,
                unique_requesters=s.unique_requesters,
                velocity=float(s.velocity or 0),
                fulfillment_rate=float(s.fulfillment_rate or 0),
                last_searched_at=s.last_searched_at,
            )
            for s in signals
        ],
    )


@router.get("/demand-gaps", response_model=DemandGapsResponse)
async def get_demand_gaps(
    limit: int = Query(20, ge=1, le=100),
    category: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """Get unmet demand — queries searched but rarely fulfilled."""
    gaps = await demand_service.get_demand_gaps(db, limit=limit, category=category)
    return DemandGapsResponse(
        gaps=[
            DemandGapResponse(
                query_pattern=g.query_pattern,
                category=g.category,
                search_count=g.search_count,
                unique_requesters=g.unique_requesters,
                avg_max_price=float(g.avg_max_price) if g.avg_max_price else None,
                fulfillment_rate=float(g.fulfillment_rate or 0),
                first_searched_at=g.first_searched_at,
            )
            for g in gaps
        ],
    )


@router.get("/opportunities", response_model=OpportunitiesResponse)
async def get_opportunities(
    limit: int = Query(20, ge=1, le=100),
    category: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """Get revenue opportunities for sellers — high demand, low supply."""
    opps = await demand_service.get_opportunities(db, category=category, limit=limit)
    return OpportunitiesResponse(
        opportunities=[
            OpportunityResponse(
                id=o.id,
                query_pattern=o.query_pattern,
                category=o.category,
                estimated_revenue_usdc=float(o.estimated_revenue_usdc),
                search_velocity=float(o.search_velocity),
                competing_listings=o.competing_listings,
                urgency_score=float(o.urgency_score),
                created_at=o.created_at,
            )
            for o in opps
        ],
    )


@router.get("/my-earnings", response_model=EarningsResponse)
async def get_my_earnings(
    db: AsyncSession = Depends(get_db),
    agent_id: str = Depends(get_current_agent_id),
):
    """Get the authenticated agent's earnings breakdown."""
    data = await analytics_service.get_earnings_breakdown(db, agent_id)
    return EarningsResponse(
        agent_id=data["agent_id"],
        total_earned_usdc=data["total_earned_usdc"],
        total_spent_usdc=data["total_spent_usdc"],
        net_revenue_usdc=data["net_revenue_usdc"],
        earnings_by_category=data["earnings_by_category"],
        earnings_timeline=[
            EarningsTimelineEntry(**entry) for entry in data["earnings_timeline"]
        ],
    )


@router.get("/my-stats", response_model=AgentStatsResponse)
async def get_my_stats(
    db: AsyncSession = Depends(get_db),
    agent_id: str = Depends(get_current_agent_id),
):
    """Get the authenticated agent's performance analytics."""
    return await _build_stats_response(db, agent_id)


@router.get("/agent/{agent_id}/profile", response_model=AgentStatsResponse)
async def get_agent_profile(
    agent_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Get a public agent profile with all performance metrics."""
    return await _build_stats_response(db, agent_id)


@router.get("/leaderboard/{board_type}", response_model=MultiLeaderboardResponse)
async def get_leaderboard(
    board_type: str,
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """Get multi-dimensional leaderboard.

    board_type: helpfulness | earnings | contributors | category:<name>
    """
    entries = await analytics_service.get_multi_leaderboard(db, board_type, limit)
    return MultiLeaderboardResponse(
        board_type=board_type,
        entries=[MultiLeaderboardEntry(**e) for e in entries],
    )


async def _build_stats_response(db: AsyncSession, agent_id: str) -> AgentStatsResponse:
    """Helper to build AgentStatsResponse from agent stats."""
    stats = await analytics_service.get_agent_stats(db, agent_id)

    # Get agent name
    from sqlalchemy import select
    result = await db.execute(
        select(RegisteredAgent.name).where(RegisteredAgent.id == agent_id)
    )
    row = result.first()
    agent_name = row[0] if row else "Unknown"

    return AgentStatsResponse(
        agent_id=agent_id,
        agent_name=agent_name,
        unique_buyers_served=stats.unique_buyers_served,
        total_listings_created=stats.total_listings_created,
        total_cache_hits=stats.total_cache_hits,
        category_count=stats.category_count,
        categories=json.loads(stats.categories_json) if stats.categories_json else [],
        total_earned_usdc=float(stats.total_earned_usdc or 0),
        total_spent_usdc=float(stats.total_spent_usdc or 0),
        demand_gaps_filled=stats.demand_gaps_filled,
        avg_listing_quality=float(stats.avg_listing_quality or 0.5),
        total_data_bytes=stats.total_data_bytes_contributed,
        helpfulness_score=float(stats.helpfulness_score or 0),
        helpfulness_rank=stats.helpfulness_rank,
        earnings_rank=stats.earnings_rank,
        primary_specialization=stats.primary_specialization,
        specialization_tags=json.loads(stats.specialization_tags_json) if stats.specialization_tags_json else [],
        last_calculated_at=stats.last_calculated_at,
    )
