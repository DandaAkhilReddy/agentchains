"""Fiat -> AXN on-ramp service for the AgentChains marketplace token economy.

Converts fiat deposits (USD, INR, EUR, GBP) into AXN tokens using
hardcoded exchange rates (Phase 1 MVP). Phase 2 will integrate a live
FX API for real-time pricing.
"""

import logging
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from marketplace.config import settings
from marketplace.models.token_account import TokenDeposit

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Exchange rates: 1 AXN = X fiat
# Derived from settings.token_peg_usd (0.001) and approximate FX rates.
# Phase 2: replace with live API calls.
# ---------------------------------------------------------------------------
_EXCHANGE_RATES: dict[str, dict] = {
    "USD": {
        "name": "US Dollar",
        "symbol": "$",
        "rate_per_axn": Decimal("0.001000"),
    },
    "INR": {
        "name": "Indian Rupee",
        "symbol": "\u20b9",
        "rate_per_axn": Decimal("0.084000"),
    },
    "EUR": {
        "name": "Euro",
        "symbol": "\u20ac",
        "rate_per_axn": Decimal("0.000920"),
    },
    "GBP": {
        "name": "British Pound",
        "symbol": "\u00a3",
        "rate_per_axn": Decimal("0.000790"),
    },
}


# ---------------------------------------------------------------------------
# Pure helpers
# ---------------------------------------------------------------------------

def get_exchange_rate(currency: str) -> Decimal:
    """Return the exchange rate (fiat per 1 AXN) for *currency*.

    Raises ``ValueError`` for unsupported currency codes.
    """
    currency = currency.upper().strip()
    entry = _EXCHANGE_RATES.get(currency)
    if entry is None:
        supported = ", ".join(sorted(_EXCHANGE_RATES))
        raise ValueError(
            f"Unsupported currency '{currency}'. Supported: {supported}"
        )
    return entry["rate_per_axn"]


def get_supported_currencies() -> list[dict]:
    """Return metadata for every supported fiat currency.

    Each item contains: code, name, symbol, rate_per_axn, axn_per_unit.
    """
    result: list[dict] = []
    for code, meta in _EXCHANGE_RATES.items():
        rate = meta["rate_per_axn"]
        axn_per_unit = (Decimal("1") / rate).quantize(
            Decimal("0.000001"), rounding=ROUND_HALF_UP
        )
        result.append({
            "code": code,
            "name": meta["name"],
            "symbol": meta["symbol"],
            "rate_per_axn": float(rate),
            "axn_per_unit": float(axn_per_unit),
        })
    return result


def _calculate_axn(amount_fiat: Decimal, rate_per_axn: Decimal) -> Decimal:
    """amount_fiat / rate_per_axn, rounded to 6 decimal places."""
    return (amount_fiat / rate_per_axn).quantize(
        Decimal("0.000001"), rounding=ROUND_HALF_UP
    )


# ---------------------------------------------------------------------------
# Async DB operations
# ---------------------------------------------------------------------------

async def create_deposit(
    db: AsyncSession,
    agent_id: str,
    amount_fiat: float | Decimal,
    currency: str,
    payment_method: str = "admin_credit",
) -> dict:
    """Create a new pending deposit converting *amount_fiat* to AXN.

    Returns a dict with the deposit details (not yet confirmed).
    """
    rate = get_exchange_rate(currency)  # raises ValueError if unsupported
    amount_fiat_d = Decimal(str(amount_fiat))
    if amount_fiat_d <= 0:
        raise ValueError("Deposit amount must be positive")

    amount_axn = _calculate_axn(amount_fiat_d, rate)

    deposit = TokenDeposit(
        agent_id=agent_id,
        amount_fiat=amount_fiat_d,
        currency=currency.upper().strip(),
        exchange_rate=rate,
        amount_axn=amount_axn,
        status="pending",
        payment_method=payment_method,
    )
    db.add(deposit)
    await db.commit()
    await db.refresh(deposit)

    logger.info(
        "Deposit %s created: %s %s -> %s AXN (agent=%s, method=%s)",
        deposit.id, amount_fiat_d, currency.upper(), amount_axn,
        agent_id, payment_method,
    )

    return _deposit_to_dict(deposit)


async def confirm_deposit(db: AsyncSession, deposit_id: str) -> dict:
    """Confirm a pending deposit: credit AXN to the agent's token account.

    Raises ``ValueError`` if the deposit is not in *pending* status.
    """
    deposit = await _get_deposit(db, deposit_id)
    if deposit.status != "pending":
        raise ValueError(
            f"Deposit {deposit_id} is '{deposit.status}', expected 'pending'"
        )

    # Credit tokens via the token service
    from marketplace.services.token_service import deposit as token_deposit
    await token_deposit(
        db,
        agent_id=deposit.agent_id,
        amount=Decimal(str(deposit.amount_axn)),
        reference_id=deposit.id,
        reference_type="deposit",
        memo=f"Fiat deposit: {deposit.amount_fiat} {deposit.currency}",
    )

    deposit.status = "completed"
    deposit.completed_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(deposit)

    logger.info(
        "Deposit %s confirmed: %s AXN credited to agent %s",
        deposit.id, deposit.amount_axn, deposit.agent_id,
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

    Uses ``settings.token_signup_bonus`` as the AXN amount.  The fiat
    equivalent is calculated at the USD rate for record-keeping.
    """
    bonus_axn = Decimal(str(settings.token_signup_bonus))
    usd_rate = _EXCHANGE_RATES["USD"]["rate_per_axn"]
    fiat_equivalent = (bonus_axn * usd_rate).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP
    )

    deposit_dict = await create_deposit(
        db,
        agent_id=agent_id,
        amount_fiat=fiat_equivalent,
        currency="USD",
        payment_method="signup_bonus",
    )

    confirmed = await confirm_deposit(db, deposit_dict["id"])

    logger.info(
        "Signup bonus of %s AXN credited to agent %s",
        bonus_axn, agent_id,
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
        "amount_fiat": float(deposit.amount_fiat),
        "currency": deposit.currency,
        "exchange_rate": float(deposit.exchange_rate),
        "amount_axn": float(deposit.amount_axn),
        "status": deposit.status,
        "payment_method": deposit.payment_method,
        "payment_ref": deposit.payment_ref,
        "created_at": deposit.created_at.isoformat() if deposit.created_at else None,
        "completed_at": deposit.completed_at.isoformat() if deposit.completed_at else None,
    }
