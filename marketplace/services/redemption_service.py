"""Withdrawal service -- convert USD balance to API credits, gift cards, or cash."""
import logging
import uuid
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from marketplace.core.async_tasks import fire_and_forget
from marketplace.models.redemption import ApiCreditBalance, RedemptionRequest
from marketplace.models.token_account import TokenAccount, TokenLedger

logger = logging.getLogger(__name__)

# Minimum thresholds by redemption type (in USD)
_MIN_THRESHOLDS: dict[str, float] = {
    "api_credits": 0.10,       # $0.10
    "gift_card": 1.00,         # $1.00
    "upi": 5.00,               # $5.00
    "bank_withdrawal": 10.00,  # $10.00
}


def _emit_admin_event(event_type: str, payload: dict) -> None:
    try:
        from marketplace.main import broadcast_event

        fire_and_forget(
            broadcast_event(event_type, payload),
            task_name=f"redemption_{event_type}",
        )
    except Exception:
        # Never block payout flow due to notification transport failure.
        return


async def create_redemption(
    db: AsyncSession,
    creator_id: str,
    redemption_type: str,
    amount_usd: float,
    currency: str = "USD",
) -> dict:
    """Create a redemption request. Validates balance and minimum thresholds."""
    # Validate redemption type
    if redemption_type not in _MIN_THRESHOLDS:
        raise ValueError(f"Invalid redemption type: {redemption_type}")

    # Validate minimum
    minimum = _MIN_THRESHOLDS[redemption_type]
    if amount_usd < minimum:
        raise ValueError(
            f"Minimum for {redemption_type} is ${minimum:.2f} USD"
        )

    # Get creator's token account
    result = await db.execute(
        select(TokenAccount).where(TokenAccount.creator_id == creator_id)
    )
    account = result.scalar_one_or_none()
    if not account:
        raise ValueError("Creator has no token account")

    amount_d = Decimal(str(amount_usd))
    if Decimal(str(account.balance)) < amount_d:
        raise ValueError(
            f"Insufficient balance: ${float(account.balance):.2f} "
            f"(need ${amount_usd:.2f})"
        )

    # Debit creator's account immediately (hold)
    account.balance = Decimal(str(account.balance)) - amount_d
    account.total_spent = Decimal(str(account.total_spent)) + amount_d
    account.updated_at = datetime.now(timezone.utc)

    # Create ledger entry for the withdrawal hold
    ledger = TokenLedger(
        id=str(uuid.uuid4()),
        from_account_id=account.id,
        to_account_id=None,  # withdrawal / redemption
        amount=amount_d,
        fee_amount=Decimal("0"),
        tx_type="withdrawal",
        reference_type="redemption",
        memo=f"Withdrawal hold: {redemption_type} ${amount_usd:.2f}",
        created_at=datetime.now(timezone.utc),
    )
    db.add(ledger)

    # Create redemption request
    # amount_fiat for non-api_credits is just amount_usd directly
    amount_fiat = amount_d if redemption_type != "api_credits" else None

    redemption = RedemptionRequest(
        id=str(uuid.uuid4()),
        creator_id=creator_id,
        redemption_type=redemption_type,
        amount_usd=amount_d,
        amount_fiat=amount_fiat,
        currency=currency,
        status="pending",
        ledger_entry_id=ledger.id,
    )
    db.add(redemption)
    await db.commit()
    await db.refresh(redemption)

    logger.info(
        "Withdrawal created: %s $%.2f -> %s (creator=%s)",
        redemption.id, amount_usd, redemption_type, creator_id,
    )
    _emit_admin_event(
        "admin.payout.pending",
        {
            "creator_id": creator_id,
            "request_id": redemption.id,
            "redemption_type": redemption.redemption_type,
            "amount_usd": float(redemption.amount_usd),
            "status": redemption.status,
        },
    )

    # Auto-process API credits (instant)
    if redemption_type == "api_credits":
        return await process_api_credit_redemption(db, redemption.id)

    return _redemption_to_dict(redemption)


async def process_api_credit_redemption(db: AsyncSession, redemption_id: str) -> dict:
    """Instant: convert USD to API call credits. $1 = 1000 credits."""
    result = await db.execute(
        select(RedemptionRequest).where(RedemptionRequest.id == redemption_id)
    )
    redemption = result.scalar_one_or_none()
    if not redemption:
        raise ValueError("Redemption not found")

    credits = int(redemption.amount_usd * 1000)

    # Upsert API credit balance
    credit_result = await db.execute(
        select(ApiCreditBalance).where(
            ApiCreditBalance.creator_id == redemption.creator_id
        )
    )
    credit_balance = credit_result.scalar_one_or_none()
    if credit_balance:
        credit_balance.credits_remaining = int(credit_balance.credits_remaining) + credits
        credit_balance.credits_total_purchased = int(credit_balance.credits_total_purchased) + credits
    else:
        credit_balance = ApiCreditBalance(
            id=str(uuid.uuid4()),
            creator_id=redemption.creator_id,
            credits_remaining=credits,
            credits_total_purchased=credits,
        )
        db.add(credit_balance)

    # Mark redemption as completed
    now = datetime.now(timezone.utc)
    redemption.status = "completed"
    redemption.processed_at = now
    redemption.completed_at = now
    redemption.payout_ref = f"api_credits_{credits}"

    await db.commit()
    await db.refresh(redemption)

    logger.info("API credits redeemed: %d credits for creator %s", credits, redemption.creator_id)
    return _redemption_to_dict(redemption)


async def process_gift_card_redemption(db: AsyncSession, redemption_id: str) -> dict:
    """Async: flag for admin fulfillment. In production: Amazon Incentives API."""
    result = await db.execute(
        select(RedemptionRequest).where(RedemptionRequest.id == redemption_id)
    )
    redemption = result.scalar_one_or_none()
    if not redemption:
        raise ValueError("Redemption not found")

    redemption.status = "processing"
    redemption.processed_at = datetime.now(timezone.utc)
    redemption.admin_notes = "Awaiting admin fulfillment (Amazon gift card)"
    await db.commit()
    await db.refresh(redemption)

    logger.info("Gift card redemption queued: %s ($%.2f)", redemption.id, float(redemption.amount_fiat or 0))
    return _redemption_to_dict(redemption)


async def process_bank_withdrawal(db: AsyncSession, redemption_id: str) -> dict:
    """Async: initiate bank transfer. In production: Razorpay/Stripe Payouts."""
    result = await db.execute(
        select(RedemptionRequest).where(RedemptionRequest.id == redemption_id)
    )
    redemption = result.scalar_one_or_none()
    if not redemption:
        raise ValueError("Redemption not found")

    redemption.status = "processing"
    redemption.processed_at = datetime.now(timezone.utc)
    redemption.admin_notes = "Queued for bank transfer processing (3-7 business days)"
    await db.commit()
    await db.refresh(redemption)

    logger.info("Bank withdrawal queued: %s ($%.2f)", redemption.id, float(redemption.amount_fiat or 0))
    return _redemption_to_dict(redemption)


async def process_upi_transfer(db: AsyncSession, redemption_id: str) -> dict:
    """Near-instant: UPI transfer via Razorpay Payouts API."""
    result = await db.execute(
        select(RedemptionRequest).where(RedemptionRequest.id == redemption_id)
    )
    redemption = result.scalar_one_or_none()
    if not redemption:
        raise ValueError("Redemption not found")

    redemption.status = "processing"
    redemption.processed_at = datetime.now(timezone.utc)
    redemption.admin_notes = "Queued for UPI transfer"
    await db.commit()
    await db.refresh(redemption)

    logger.info("UPI transfer queued: %s ($%.2f)", redemption.id, float(redemption.amount_fiat or 0))
    return _redemption_to_dict(redemption)


async def cancel_redemption(db: AsyncSession, redemption_id: str, creator_id: str) -> dict:
    """Cancel a pending redemption and refund USD to creator."""
    result = await db.execute(
        select(RedemptionRequest).where(
            RedemptionRequest.id == redemption_id,
            RedemptionRequest.creator_id == creator_id,
        )
    )
    redemption = result.scalar_one_or_none()
    if not redemption:
        raise ValueError("Redemption not found")
    if redemption.status != "pending":
        raise ValueError(f"Cannot cancel redemption in '{redemption.status}' status")

    # Refund USD to creator
    acct_result = await db.execute(
        select(TokenAccount).where(TokenAccount.creator_id == creator_id)
    )
    account = acct_result.scalar_one_or_none()
    if account:
        amount_d = Decimal(str(redemption.amount_usd))
        account.balance = Decimal(str(account.balance)) + amount_d
        account.total_spent = Decimal(str(account.total_spent)) - amount_d
        account.updated_at = datetime.now(timezone.utc)

        # Refund ledger entry
        refund_ledger = TokenLedger(
            id=str(uuid.uuid4()),
            from_account_id=None,
            to_account_id=account.id,
            amount=amount_d,
            fee_amount=Decimal("0"),
            tx_type="refund",
            reference_id=redemption.id,
            reference_type="redemption_cancel",
            memo=f"Redemption cancelled: {redemption.id}",
            created_at=datetime.now(timezone.utc),
        )
        db.add(refund_ledger)

    redemption.status = "rejected"
    redemption.rejection_reason = "Cancelled by creator"
    redemption.completed_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(redemption)

    logger.info("Redemption cancelled: %s", redemption.id)
    return _redemption_to_dict(redemption)


async def admin_approve_redemption(db: AsyncSession, redemption_id: str, admin_notes: str = "") -> dict:
    """Admin approves and processes a pending redemption."""
    result = await db.execute(
        select(RedemptionRequest).where(RedemptionRequest.id == redemption_id)
    )
    redemption = result.scalar_one_or_none()
    if not redemption:
        raise ValueError("Redemption not found")

    if admin_notes:
        redemption.admin_notes = admin_notes

    # Route to the appropriate processor
    if redemption.redemption_type == "api_credits":
        result = await process_api_credit_redemption(db, redemption_id)
    elif redemption.redemption_type == "gift_card":
        result = await process_gift_card_redemption(db, redemption_id)
    elif redemption.redemption_type == "bank_withdrawal":
        result = await process_bank_withdrawal(db, redemption_id)
    elif redemption.redemption_type == "upi":
        result = await process_upi_transfer(db, redemption_id)
    else:
        raise ValueError(f"Unknown redemption type: {redemption.redemption_type}")

    _emit_admin_event(
        "admin.dashboard.updated",
        {
            "creator_id": redemption.creator_id,
            "request_id": redemption.id,
            "status": result.get("status", redemption.status),
        },
    )
    return result


async def admin_reject_redemption(db: AsyncSession, redemption_id: str, reason: str) -> dict:
    """Admin rejects a redemption and refunds USD."""
    result = await db.execute(
        select(RedemptionRequest).where(RedemptionRequest.id == redemption_id)
    )
    redemption = result.scalar_one_or_none()
    if not redemption:
        raise ValueError("Redemption not found")

    # Refund USD to creator
    acct_result = await db.execute(
        select(TokenAccount).where(TokenAccount.creator_id == redemption.creator_id)
    )
    account = acct_result.scalar_one_or_none()
    if account:
        amount_d = Decimal(str(redemption.amount_usd))
        account.balance = Decimal(str(account.balance)) + amount_d
        account.total_spent = Decimal(str(account.total_spent)) - amount_d

        refund_ledger = TokenLedger(
            id=str(uuid.uuid4()),
            from_account_id=None,
            to_account_id=account.id,
            amount=amount_d,
            tx_type="refund",
            reference_id=redemption.id,
            reference_type="redemption_rejected",
            memo=f"Redemption rejected: {reason}",
            created_at=datetime.now(timezone.utc),
        )
        db.add(refund_ledger)

    redemption.status = "rejected"
    redemption.rejection_reason = reason
    redemption.completed_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(redemption)

    logger.info("Redemption rejected: %s -- %s", redemption.id, reason)
    _emit_admin_event(
        "admin.dashboard.updated",
        {
            "creator_id": redemption.creator_id,
            "request_id": redemption.id,
            "status": redemption.status,
        },
    )
    return _redemption_to_dict(redemption)


async def list_redemptions(
    db: AsyncSession,
    creator_id: str,
    status: str | None = None,
    page: int = 1,
    page_size: int = 20,
) -> dict:
    """Paginated list of redemption requests."""
    stmt = select(RedemptionRequest).where(
        RedemptionRequest.creator_id == creator_id
    ).order_by(RedemptionRequest.created_at.desc())

    if status:
        stmt = stmt.where(RedemptionRequest.status == status)

    total_stmt = select(func.count(RedemptionRequest.id)).where(
        RedemptionRequest.creator_id == creator_id
    )
    if status:
        total_stmt = total_stmt.where(RedemptionRequest.status == status)

    total = (await db.execute(total_stmt)).scalar() or 0
    result = await db.execute(stmt.offset((page - 1) * page_size).limit(page_size))
    entries = result.scalars().all()

    return {
        "redemptions": [_redemption_to_dict(r) for r in entries],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


async def get_redemption_methods() -> dict:
    """Return available redemption methods and their thresholds."""
    return {
        "methods": [
            {
                "type": "api_credits",
                "label": "API Call Credits",
                "description": "Convert balance to API credits ($1 = 1000 credits)",
                "min_usd": _MIN_THRESHOLDS["api_credits"],
                "processing_time": "Instant",
            },
            {
                "type": "gift_card",
                "label": "Amazon Gift Card",
                "description": "Redeem for Amazon gift cards (email delivery)",
                "min_usd": _MIN_THRESHOLDS["gift_card"],
                "processing_time": "24 hours",
            },
            {
                "type": "upi",
                "label": "UPI Transfer (India)",
                "description": "Near-instant transfer to your UPI ID",
                "min_usd": _MIN_THRESHOLDS["upi"],
                "processing_time": "Minutes",
                "countries": ["IN"],
            },
            {
                "type": "bank_withdrawal",
                "label": "Bank Transfer",
                "description": "Transfer to your bank account",
                "min_usd": _MIN_THRESHOLDS["bank_withdrawal"],
                "processing_time": "3-7 business days",
            },
        ],
    }


def _redemption_to_dict(r: RedemptionRequest) -> dict:
    return {
        "id": r.id,
        "creator_id": r.creator_id,
        "redemption_type": r.redemption_type,
        "amount_usd": float(r.amount_usd),
        "amount_fiat": float(r.amount_fiat) if r.amount_fiat else None,
        "currency": r.currency,
        "status": r.status,
        "payout_ref": r.payout_ref,
        "admin_notes": r.admin_notes,
        "rejection_reason": r.rejection_reason,
        "created_at": str(r.created_at),
        "processed_at": str(r.processed_at) if r.processed_at else None,
        "completed_at": str(r.completed_at) if r.completed_at else None,
    }
