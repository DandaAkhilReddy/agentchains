"""USD deposit service for AgentChains marketplace. Handles USD deposits directly."""

import logging
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from marketplace.config import settings
from marketplace.models.token_account import TokenDeposit

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Async DB operations
# ---------------------------------------------------------------------------

async def create_deposit(
    db: AsyncSession,
    agent_id: str,
    amount_usd: float | Decimal,
    payment_method: str = "admin_credit",
) -> dict:
    """Create a new pending USD deposit.

    Returns a dict with the deposit details (not yet confirmed).
    """
    amount_usd_d = Decimal(str(amount_usd))
    if amount_usd_d <= 0:
        raise ValueError("Deposit amount must be positive")

    deposit = TokenDeposit(
        agent_id=agent_id,
        amount_usd=amount_usd_d,
        currency="USD",
        status="pending",
        payment_method=payment_method,
    )
    db.add(deposit)
    await db.commit()
    await db.refresh(deposit)

    logger.info(
        "Deposit %s created: $%.2f USD (agent=%s, method=%s)",
        deposit.id, amount_usd_d, agent_id, payment_method,
    )

    return _deposit_to_dict(deposit)


async def confirm_deposit(db: AsyncSession, deposit_id: str) -> dict:
    """Confirm a pending deposit: credit USD to the agent's token account.

    Raises ``ValueError`` if the deposit is not in *pending* status.
    """
    deposit = await _get_deposit(db, deposit_id)
    if deposit.status != "pending":
        raise ValueError(
            f"Deposit {deposit_id} is '{deposit.status}', expected 'pending'"
        )

    # Credit USD via the token service
    from marketplace.services.token_service import deposit as token_deposit
    await token_deposit(
        db,
        agent_id=deposit.agent_id,
        amount_usd=Decimal(str(deposit.amount_usd)),
        deposit_id=deposit.id,
        memo=f"Deposit: ${deposit.amount_usd}",
    )

    deposit.status = "completed"
    deposit.completed_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(deposit)

    logger.info(
        "Deposit confirmed: $%.2f credited to agent %s",
        float(deposit.amount_usd), deposit.agent_id,
    )

    return _deposit_to_dict(deposit)


async def cancel_deposit(db: AsyncSession, deposit_id: str) -> dict:
    """Mark a deposit as failed."""
    deposit = await _get_deposit(db, deposit_id)
    deposit.status = "failed"
    await db.commit()
    await db.refresh(deposit)

    logger.info("Deposit %s marked as failed", deposit.id)

    return _deposit_to_dict(deposit)


async def get_deposits(
    db: AsyncSession,
    agent_id: str,
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[dict], int]:
    """Paginated deposit history for an agent.

    Returns ``(deposits, total_count)``.
    """
    base_filter = TokenDeposit.agent_id == agent_id

    # Total count
    count_q = select(func.count(TokenDeposit.id)).where(base_filter)
    total: int = (await db.execute(count_q)).scalar() or 0

    # Paginated rows
    rows_q = (
        select(TokenDeposit)
        .where(base_filter)
        .order_by(TokenDeposit.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    result = await db.execute(rows_q)
    deposits = [_deposit_to_dict(d) for d in result.scalars().all()]

    return deposits, total


async def credit_signup_bonus(db: AsyncSession, agent_id: str) -> dict:
    """Create and auto-confirm a signup bonus deposit.

    Uses ``settings.signup_bonus_usd`` as the USD amount.
    """
    bonus_usd = Decimal(str(settings.signup_bonus_usd))

    deposit_dict = await create_deposit(
        db,
        agent_id=agent_id,
        amount_usd=bonus_usd,
        payment_method="signup_bonus",
    )

    confirmed = await confirm_deposit(db, deposit_dict["id"])

    logger.info(
        "Signup bonus of $%.2f credited to agent %s",
        float(bonus_usd), agent_id,
    )

    return confirmed


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

async def _get_deposit(db: AsyncSession, deposit_id: str) -> TokenDeposit:
    """Fetch a single deposit or raise HTTP 404."""
    result = await db.execute(
        select(TokenDeposit).where(TokenDeposit.id == deposit_id)
    )
    deposit = result.scalar_one_or_none()
    if deposit is None:
        from fastapi import HTTPException, status
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Deposit {deposit_id} not found",
        )
    return deposit


def _deposit_to_dict(deposit: TokenDeposit) -> dict:
    """Serialize a ``TokenDeposit`` row to a plain dict."""
    return {
        "id": deposit.id,
        "agent_id": deposit.agent_id,
        "amount_usd": float(deposit.amount_usd),
        "currency": deposit.currency,
        "status": deposit.status,
        "payment_method": deposit.payment_method,
        "payment_ref": deposit.payment_ref,
        "created_at": deposit.created_at.isoformat() if deposit.created_at else None,
        "completed_at": deposit.completed_at.isoformat() if deposit.completed_at else None,
    }
