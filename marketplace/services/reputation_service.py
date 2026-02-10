from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from marketplace.models.reputation import ReputationScore
from marketplace.models.transaction import Transaction


async def calculate_reputation(db: AsyncSession, agent_id: str) -> ReputationScore:
    """Recalculate and store the composite reputation score for an agent.

    Formula: 0.4 * delivery_rate + 0.3 * verification_rate + 0.2 * response_time_score + 0.1 * volume_score
    """
    # Get or create reputation record
    result = await db.execute(
        select(ReputationScore).where(ReputationScore.agent_id == agent_id)
    )
    rep = result.scalar_one_or_none()
    if not rep:
        rep = ReputationScore(agent_id=agent_id)
        db.add(rep)

    # Count transactions as seller
    seller_txns = await db.execute(
        select(Transaction).where(Transaction.seller_id == agent_id)
    )
    seller_list = list(seller_txns.scalars().all())

    # Count transactions as buyer
    buyer_txns = await db.execute(
        select(Transaction).where(Transaction.buyer_id == agent_id)
    )
    buyer_list = list(buyer_txns.scalars().all())

    all_txns = seller_list + buyer_list
    rep.total_transactions = len(all_txns)

    # Delivery metrics (seller perspective)
    completed = [t for t in seller_list if t.status == "completed"]
    failed = [t for t in seller_list if t.status in ("failed", "disputed")]
    rep.successful_deliveries = len(completed)
    rep.failed_deliveries = len(failed)

    # Verification metrics
    verified = [t for t in all_txns if t.verification_status == "verified"]
    ver_failed = [t for t in all_txns if t.verification_status == "failed"]
    rep.verified_count = len(verified)
    rep.verification_failures = len(ver_failed)

    # Volume
    rep.total_volume_usdc = sum(float(t.amount_usdc) for t in all_txns)

    # Compute composite score
    total_seller = len(seller_list)
    delivery_rate = rep.successful_deliveries / max(total_seller, 1)
    verification_rate = rep.verified_count / max(rep.total_transactions, 1)
    response_time_score = 0.8  # Placeholder until we track response times
    volume_score = min(rep.total_transactions / 100, 1.0)  # Saturates at 100 txns

    rep.composite_score = round(
        0.4 * delivery_rate
        + 0.3 * verification_rate
        + 0.2 * response_time_score
        + 0.1 * volume_score,
        3,
    )
    rep.last_calculated_at = datetime.now(timezone.utc)

    await db.commit()
    await db.refresh(rep)
    return rep


async def get_reputation(db: AsyncSession, agent_id: str) -> ReputationScore | None:
    """Get the reputation score for an agent."""
    result = await db.execute(
        select(ReputationScore).where(ReputationScore.agent_id == agent_id)
    )
    return result.scalar_one_or_none()


async def get_leaderboard(
    db: AsyncSession, limit: int = 20
) -> list[ReputationScore]:
    """Get the top agents by composite score."""
    result = await db.execute(
        select(ReputationScore)
        .order_by(ReputationScore.composite_score.desc())
        .limit(limit)
    )
    return list(result.scalars().all())
