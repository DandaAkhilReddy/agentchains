from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from marketplace.database import get_db
from marketplace.schemas.reputation import LeaderboardEntry, LeaderboardResponse, ReputationResponse
from marketplace.services import reputation_service, registry_service

router = APIRouter(prefix="/reputation", tags=["reputation"])


@router.get("/{agent_id}", response_model=ReputationResponse)
async def get_reputation(
    agent_id: str,
    recalculate: bool = Query(False, description="Recalculate before returning"),
    db: AsyncSession = Depends(get_db),
):
    if recalculate:
        rep = await reputation_service.calculate_reputation(db, agent_id)
    else:
        rep = await reputation_service.get_reputation(db, agent_id)
        if not rep:
            rep = await reputation_service.calculate_reputation(db, agent_id)

    agent = await registry_service.get_agent(db, agent_id)

    return ReputationResponse(
        agent_id=rep.agent_id,
        agent_name=agent.name,
        total_transactions=rep.total_transactions,
        successful_deliveries=rep.successful_deliveries,
        failed_deliveries=rep.failed_deliveries,
        verified_count=rep.verified_count,
        verification_failures=rep.verification_failures,
        avg_response_ms=float(rep.avg_response_ms) if rep.avg_response_ms else None,
        total_volume_usdc=float(rep.total_volume_usdc),
        composite_score=float(rep.composite_score),
        last_calculated_at=rep.last_calculated_at,
    )


@router.get("/leaderboard", response_model=LeaderboardResponse)
async def leaderboard(
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    scores = await reputation_service.get_leaderboard(db, limit)
    entries = []
    for rank, score in enumerate(scores, 1):
        try:
            agent = await registry_service.get_agent(db, score.agent_id)
            name = agent.name
        except Exception:
            name = "unknown"
        entries.append(LeaderboardEntry(
            rank=rank,
            agent_id=score.agent_id,
            agent_name=name,
            composite_score=float(score.composite_score),
            total_transactions=score.total_transactions,
            total_volume_usdc=float(score.total_volume_usdc),
        ))
    return LeaderboardResponse(entries=entries)
