"""Payment reconciliation service.

Reconciles payment records between the marketplace database and
external payment providers (Stripe, Razorpay). Detects discrepancies
and provides retry mechanisms for failed payments.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from marketplace.models.transaction import Transaction

logger = logging.getLogger(__name__)


async def reconcile_stripe_payments(
    db: AsyncSession,
    since: datetime | None = None,
) -> dict[str, Any]:
    """Reconcile marketplace transactions against Stripe payment records.

    Returns a summary of matched, mismatched, and missing payments.
    """
    from marketplace.config import settings
    from marketplace.services.stripe_service import StripePaymentService

    service = StripePaymentService(
        secret_key=settings.stripe_secret_key,
        webhook_secret=settings.stripe_webhook_secret,
    )

    # Get completed transactions that used Stripe
    query = select(Transaction).where(
        Transaction.status.in_(["completed", "disputed"]),
    )
    if since:
        query = query.where(Transaction.created_at >= since)

    result = await db.execute(query.limit(500))
    transactions = result.scalars().all()

    matched = 0
    mismatched = []
    missing = []

    for tx in transactions:
        payment_ref = getattr(tx, "payment_reference", None)
        if not payment_ref or not payment_ref.startswith("pi_"):
            continue

        try:
            stripe_record = await service.retrieve_payment_intent(payment_ref)
            stripe_amount = Decimal(str(stripe_record.get("amount", 0))) / 100

            if stripe_record.get("simulated"):
                matched += 1
                continue

            if stripe_record.get("status") == "succeeded":
                if abs(stripe_amount - tx.amount_usdc) < Decimal("0.01"):
                    matched += 1
                else:
                    mismatched.append({
                        "transaction_id": tx.id,
                        "payment_ref": payment_ref,
                        "expected_amount": float(tx.amount_usdc),
                        "actual_amount": float(stripe_amount),
                    })
            else:
                mismatched.append({
                    "transaction_id": tx.id,
                    "payment_ref": payment_ref,
                    "expected_status": "succeeded",
                    "actual_status": stripe_record.get("status"),
                })

        except Exception as e:
            missing.append({
                "transaction_id": tx.id,
                "payment_ref": payment_ref,
                "error": str(e),
            })

    return {
        "provider": "stripe",
        "total_checked": len(transactions),
        "matched": matched,
        "mismatched": mismatched,
        "missing": missing,
        "reconciled_at": datetime.now(timezone.utc).isoformat(),
    }


async def reconcile_razorpay_payments(
    db: AsyncSession,
    since: datetime | None = None,
) -> dict[str, Any]:
    """Reconcile marketplace transactions against Razorpay payment records."""
    from marketplace.config import settings
    from marketplace.services.razorpay_service import RazorpayPaymentService

    service = RazorpayPaymentService(
        key_id=settings.razorpay_key_id,
        key_secret=settings.razorpay_key_secret,
    )

    query = select(Transaction).where(
        Transaction.status.in_(["completed", "disputed"]),
    )
    if since:
        query = query.where(Transaction.created_at >= since)

    result = await db.execute(query.limit(500))
    transactions = result.scalars().all()

    matched = 0
    mismatched = []
    missing = []

    for tx in transactions:
        payment_ref = getattr(tx, "payment_reference", None)
        if not payment_ref or not payment_ref.startswith("pay_"):
            continue

        try:
            razorpay_record = await service.fetch_payment(payment_ref)
            if razorpay_record.get("simulated"):
                matched += 1
                continue

            if razorpay_record.get("status") == "captured":
                matched += 1
            else:
                mismatched.append({
                    "transaction_id": tx.id,
                    "payment_ref": payment_ref,
                    "expected_status": "captured",
                    "actual_status": razorpay_record.get("status"),
                })

        except Exception as e:
            missing.append({
                "transaction_id": tx.id,
                "payment_ref": payment_ref,
                "error": str(e),
            })

    return {
        "provider": "razorpay",
        "total_checked": len(transactions),
        "matched": matched,
        "mismatched": mismatched,
        "missing": missing,
        "reconciled_at": datetime.now(timezone.utc).isoformat(),
    }


async def retry_failed_payment(
    db: AsyncSession,
    transaction_id: str,
) -> dict[str, Any]:
    """Retry a failed payment for a transaction."""
    result = await db.execute(
        select(Transaction).where(Transaction.id == transaction_id)
    )
    tx = result.scalar_one_or_none()
    if not tx:
        return {"error": "Transaction not found"}

    if tx.status != "failed":
        return {"error": f"Transaction status is {tx.status}, not 'failed'"}

    from marketplace.config import settings
    from marketplace.services.stripe_service import StripePaymentService

    service = StripePaymentService(
        secret_key=settings.stripe_secret_key,
        webhook_secret=settings.stripe_webhook_secret,
    )

    try:
        intent = await service.create_payment_intent(
            amount_usd=tx.amount_usdc,
            metadata={"transaction_id": tx.id, "retry": "true"},
        )
        tx.status = "pending"
        await db.commit()
        return {
            "transaction_id": tx.id,
            "new_payment_intent": intent.get("id"),
            "status": "retry_initiated",
        }
    except Exception as e:
        return {"error": str(e)}
