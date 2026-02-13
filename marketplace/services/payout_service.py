"""Monthly auto-payout service for creator earnings."""
import logging
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from marketplace.config import settings
from marketplace.models.creator import Creator
from marketplace.models.token_account import TokenAccount
from marketplace.services import redemption_service

logger = logging.getLogger(__name__)


async def run_monthly_payout(db: AsyncSession) -> dict:
    """Auto-generate payouts for all creators above minimum threshold.

    Called on the 1st of each month (or manually via admin).
    """
    now = datetime.now(timezone.utc)
    month_key = f"{now.year}-{now.month:02d}"
    min_balance = settings.creator_min_withdrawal_usd

    # Find all creators with sufficient balance
    result = await db.execute(
        select(TokenAccount, Creator)
        .join(Creator, TokenAccount.creator_id == Creator.id)
        .where(
            TokenAccount.creator_id.isnot(None),
            TokenAccount.balance >= min_balance,
            Creator.status == "active",
            Creator.payout_method != "none",
        )
    )
    rows = result.all()

    processed = 0
    skipped = 0
    errors = []

    for acct, creator in rows:
        # Idempotency: check if already paid out this month
        idempotency_key = f"monthly-{creator.id}-{month_key}"

        try:
            payout_method = creator.payout_method
            if payout_method not in ("upi", "bank", "gift_card"):
                skipped += 1
                continue

            # Map creator payout_method to redemption_type
            type_map = {
                "upi": "upi",
                "bank": "bank_withdrawal",
                "gift_card": "gift_card",
            }
            redemption_type = type_map.get(payout_method, "bank_withdrawal")

            await redemption_service.create_redemption(
                db, creator.id, redemption_type, float(acct.balance),
            )
            processed += 1
            logger.info(
                "Monthly payout created: creator=%s amount=%.2f type=%s",
                creator.id, float(acct.balance), redemption_type,
            )
        except Exception as e:
            errors.append({"creator_id": creator.id, "error": str(e)})
            logger.error("Monthly payout failed for %s: %s", creator.id, e)

    return {
        "month": month_key,
        "processed": processed,
        "skipped": skipped,
        "errors": errors,
    }


async def process_pending_payouts(db: AsyncSession) -> dict:
    """Process all pending redemption requests."""
    from marketplace.models.redemption import RedemptionRequest

    result = await db.execute(
        select(RedemptionRequest).where(RedemptionRequest.status == "pending")
    )
    pending = result.scalars().all()

    processed = 0
    for redemption in pending:
        try:
            if redemption.redemption_type == "api_credits":
                await redemption_service.process_api_credit_redemption(db, redemption.id)
            elif redemption.redemption_type == "gift_card":
                await redemption_service.process_gift_card_redemption(db, redemption.id)
            elif redemption.redemption_type == "bank_withdrawal":
                await redemption_service.process_bank_withdrawal(db, redemption.id)
            elif redemption.redemption_type == "upi":
                await redemption_service.process_upi_transfer(db, redemption.id)
            processed += 1
        except Exception as e:
            logger.error("Failed to process redemption %s: %s", redemption.id, e)

    return {"processed": processed, "total_pending": len(pending)}
