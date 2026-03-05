"""Payment webhook handlers for Stripe and Razorpay.

Receives and processes payment event notifications from payment providers.
Validates signatures before processing to prevent spoofing.
"""

import json
import logging
import time

from fastapi import APIRouter, Depends, Header, Request
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from marketplace.config import settings
from marketplace.database import get_db
from marketplace.services.stripe_service import StripePaymentService

# Maximum age for webhook events (5 minutes) to prevent replay attacks
_WEBHOOK_TIMESTAMP_TOLERANCE_SECONDS = 300

router = APIRouter(tags=["webhooks"])
logger = logging.getLogger(__name__)


@router.post("/webhooks/stripe")
async def stripe_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db),
    stripe_signature: str = Header(None, alias="Stripe-Signature"),
):
    """Handle Stripe webhook events."""
    payload = await request.body()
    service = StripePaymentService(
        secret_key=settings.stripe_secret_key,
        webhook_secret=settings.stripe_webhook_secret,
    )

    if not service._simulated:
        # In live mode, signature verification is mandatory.
        # Note: Stripe's construct_event() already validates timestamps
        # with a default tolerance of 300 seconds, preventing replay attacks.
        if not stripe_signature:
            logger.warning("Stripe webhook rejected: missing Stripe-Signature header")
            return JSONResponse(
                status_code=401,
                content={"error": "Missing Stripe-Signature header"},
            )
        event = service.verify_webhook_signature(payload, stripe_signature)
        if event is None:
            return JSONResponse(
                status_code=400,
                content={"error": "Invalid webhook signature"},
            )
    else:
        try:
            event = json.loads(payload)
        except (json.JSONDecodeError, ValueError):
            return JSONResponse(
                status_code=400,
                content={"error": "Invalid JSON payload"},
            )

    event_type = event.get("type", "")
    logger.info("Stripe webhook received: %s", event_type)

    handlers = {
        "payment_intent.succeeded": lambda: _handle_stripe_payment_succeeded(event),
        "payment_intent.payment_failed": lambda: _handle_stripe_payment_failed(event),
        "charge.refunded": lambda: _handle_stripe_refund(event),
        "checkout.session.completed": lambda: _handle_stripe_checkout_completed(event, db),
        "account.updated": lambda: _handle_stripe_account_updated(event),
        "customer.subscription.created": lambda: _handle_subscription_created(event, db),
        "customer.subscription.updated": lambda: _handle_subscription_updated(event, db),
        "customer.subscription.deleted": lambda: _handle_subscription_deleted(event, db),
        "invoice.payment_succeeded": lambda: _handle_invoice_payment_succeeded(event, db),
        "invoice.payment_failed": lambda: _handle_invoice_payment_failed(event, db),
    }

    handler = handlers.get(event_type)
    if handler:
        await handler()
    else:
        logger.debug("Unhandled Stripe event type: %s", event_type)

    return {"status": "ok"}


@router.post("/webhooks/razorpay")
async def razorpay_webhook(
    request: Request,
    x_razorpay_signature: str = Header(None, alias="X-Razorpay-Signature"),
):
    """Handle Razorpay webhook events."""
    import hashlib
    import hmac

    payload = await request.body()

    # Verify signature — mandatory when secret is configured
    if settings.razorpay_key_secret:
        if not x_razorpay_signature:
            logger.warning("Razorpay webhook rejected: missing X-Razorpay-Signature header")
            return JSONResponse(
                status_code=401,
                content={"error": "Missing X-Razorpay-Signature header"},
            )
        expected = hmac.new(
            settings.razorpay_key_secret.encode("utf-8"),
            payload,
            hashlib.sha256,
        ).hexdigest()
        if not hmac.compare_digest(expected, x_razorpay_signature):
            return JSONResponse(
                status_code=400,
                content={"error": "Invalid webhook signature"},
            )

    try:
        event = json.loads(payload)
    except (json.JSONDecodeError, ValueError):
        return JSONResponse(
            status_code=400,
            content={"error": "Invalid JSON payload"},
        )

    # Replay protection: reject events with stale timestamps
    event_timestamp = event.get("created_at") or event.get("timestamp")
    if event_timestamp is not None:
        try:
            ts = int(event_timestamp)
            age = abs(time.time() - ts)
            if age > _WEBHOOK_TIMESTAMP_TOLERANCE_SECONDS:
                logger.warning(
                    "Razorpay webhook rejected: stale timestamp (age=%ds)", age,
                )
                return JSONResponse(
                    status_code=400,
                    content={"error": "Webhook event timestamp too old"},
                )
        except (ValueError, TypeError):
            pass  # Non-integer timestamps are not validated

    event_type = event.get("event", "")
    logger.info("Razorpay webhook received: %s", event_type)

    if event_type == "payment.captured":
        await _handle_razorpay_payment_captured(event)
    elif event_type == "payment.failed":
        await _handle_razorpay_payment_failed(event)
    elif event_type == "order.paid":
        await _handle_razorpay_order_paid(event)
    elif event_type == "payout.processed":
        await _handle_razorpay_payout_processed(event)
    else:
        logger.debug("Unhandled Razorpay event type: %s", event_type)

    return {"status": "ok"}


# ── Stripe event handlers ──

async def _handle_stripe_payment_succeeded(event: dict) -> None:
    """Process successful Stripe payment."""
    data = event.get("data", {})
    payment_intent_id = data.get("id", "")
    metadata = data.get("metadata", {})
    logger.info(
        "Stripe payment succeeded: %s, metadata=%s",
        payment_intent_id, metadata,
    )
    # TODO: Update transaction status, credit seller account


async def _handle_stripe_payment_failed(event: dict) -> None:
    """Process failed Stripe payment."""
    data = event.get("data", {})
    payment_intent_id = data.get("id", "")
    logger.warning("Stripe payment failed: %s", payment_intent_id)
    # TODO: Update transaction status to failed


async def _handle_stripe_refund(event: dict) -> None:
    """Process Stripe refund."""
    data = event.get("data", {})
    charge_id = data.get("id", "")
    logger.info("Stripe refund processed: %s", charge_id)
    # TODO: Update transaction, reverse credit


async def _handle_stripe_checkout_completed(event: dict, db: AsyncSession) -> None:
    """Confirm a deposit when Stripe Checkout Session is paid."""
    session_obj = event.get("data", {}).get("object", {})
    metadata = session_obj.get("metadata", {})
    deposit_id = metadata.get("deposit_id")
    payment_status = session_obj.get("payment_status", "")

    if not deposit_id:
        logger.warning("checkout.session.completed missing deposit_id in metadata")
        return

    if payment_status != "paid":
        logger.info(
            "checkout.session.completed skipped: payment_status=%s (deposit=%s)",
            payment_status, deposit_id,
        )
        return

    from marketplace.services.deposit_service import confirm_deposit

    try:
        await confirm_deposit(db, deposit_id)
        logger.info("Stripe checkout confirmed deposit %s", deposit_id)
    except ValueError:
        # Already confirmed (idempotent) or invalid state — skip
        logger.info("Deposit %s already confirmed or invalid, skipping", deposit_id)


async def _handle_stripe_account_updated(event: dict) -> None:
    """Process Stripe Connect account update."""
    data = event.get("data", {})
    account_id = data.get("id", "")
    logger.info("Stripe account updated: %s", account_id)
    # TODO: Update creator's payout status


# ── Subscription lifecycle handlers ──


async def _handle_subscription_created(event: dict, db: AsyncSession) -> None:
    """Handle customer.subscription.created — activate subscription in DB."""
    sub_obj = event.get("data", {}).get("object", {})
    metadata = sub_obj.get("metadata", {})
    agent_id = metadata.get("agent_id")
    plan_id = metadata.get("plan_id")
    stripe_sub_id = sub_obj.get("id", "")

    if not agent_id or not plan_id:
        logger.warning("subscription.created missing agent_id/plan_id in metadata")
        return

    from marketplace.models.billing import Subscription
    from sqlalchemy import select

    # Look for a pending subscription from checkout, or an active one without stripe_id
    result = await db.execute(
        select(Subscription)
        .where(
            Subscription.agent_id == agent_id,
            Subscription.plan_id == plan_id,
            Subscription.status.in_(["pending", "active"]),
        )
        .order_by(Subscription.created_at.desc())
    )
    existing = result.scalar_one_or_none()

    if existing and not existing.stripe_subscription_id:
        existing.stripe_subscription_id = stripe_sub_id
        existing.status = "active"
        await db.commit()
        logger.info("Activated subscription %s with stripe_id=%s", existing.id, stripe_sub_id)
        return

    # No pending sub found — create new one
    from marketplace.services.billing_v2_service import subscribe

    sub = await subscribe(db, agent_id, plan_id)
    result = await db.execute(
        select(Subscription).where(Subscription.id == sub.id)
    )
    db_sub = result.scalar_one_or_none()
    if db_sub:
        db_sub.stripe_subscription_id = stripe_sub_id
        await db.commit()
    logger.info("Subscription created for agent=%s plan=%s stripe=%s", agent_id, plan_id, stripe_sub_id)


async def _handle_subscription_updated(event: dict, db: AsyncSession) -> None:
    """Handle customer.subscription.updated — sync period dates and status."""
    from datetime import datetime, timezone

    from marketplace.models.billing import Subscription
    from sqlalchemy import select

    sub_obj = event.get("data", {}).get("object", {})
    stripe_sub_id = sub_obj.get("id", "")
    status = sub_obj.get("status", "")

    result = await db.execute(
        select(Subscription).where(Subscription.stripe_subscription_id == stripe_sub_id)
    )
    sub = result.scalar_one_or_none()
    if not sub:
        logger.warning("subscription.updated: no local subscription for stripe_id=%s", stripe_sub_id)
        return

    # Map Stripe statuses to our statuses
    status_map = {
        "active": "active",
        "past_due": "past_due",
        "canceled": "cancelled",
        "trialing": "trialing",
        "incomplete": "past_due",
        "incomplete_expired": "cancelled",
        "unpaid": "past_due",
    }
    sub.status = status_map.get(status, sub.status)

    # Update period dates
    period_start = sub_obj.get("current_period_start")
    period_end = sub_obj.get("current_period_end")
    if period_start:
        sub.current_period_start = datetime.fromtimestamp(period_start, tz=timezone.utc)
    if period_end:
        sub.current_period_end = datetime.fromtimestamp(period_end, tz=timezone.utc)

    sub.cancel_at_period_end = sub_obj.get("cancel_at_period_end", False)
    await db.commit()
    logger.info("Subscription updated: stripe_id=%s status=%s", stripe_sub_id, sub.status)


async def _handle_subscription_deleted(event: dict, db: AsyncSession) -> None:
    """Handle customer.subscription.deleted — mark as cancelled."""
    from marketplace.models.billing import Subscription
    from sqlalchemy import select

    sub_obj = event.get("data", {}).get("object", {})
    stripe_sub_id = sub_obj.get("id", "")

    result = await db.execute(
        select(Subscription).where(Subscription.stripe_subscription_id == stripe_sub_id)
    )
    sub = result.scalar_one_or_none()
    if not sub:
        logger.warning("subscription.deleted: no local subscription for stripe_id=%s", stripe_sub_id)
        return

    sub.status = "cancelled"
    await db.commit()
    logger.info("Subscription cancelled: stripe_id=%s agent=%s", stripe_sub_id, sub.agent_id)


async def _handle_invoice_payment_succeeded(event: dict, db: AsyncSession) -> None:
    """Handle invoice.payment_succeeded — mark invoice as paid."""
    invoice_obj = event.get("data", {}).get("object", {})
    stripe_invoice_id = invoice_obj.get("id", "")
    stripe_sub_id = invoice_obj.get("subscription", "")

    from marketplace.models.billing import Invoice
    from sqlalchemy import select

    # Try to find invoice by stripe_invoice_id
    result = await db.execute(
        select(Invoice).where(Invoice.stripe_invoice_id == stripe_invoice_id)
    )
    invoice = result.scalar_one_or_none()
    if invoice:
        from marketplace.services.invoice_service import mark_invoice_paid
        await mark_invoice_paid(db, invoice.id, stripe_invoice_id)
        logger.info("Invoice marked paid: stripe_id=%s", stripe_invoice_id)
    else:
        logger.debug(
            "invoice.payment_succeeded: no local invoice for stripe_id=%s (may be Stripe-managed)",
            stripe_invoice_id,
        )

    # Update subscription to active if it was past_due
    if stripe_sub_id:
        from marketplace.models.billing import Subscription

        result = await db.execute(
            select(Subscription).where(Subscription.stripe_subscription_id == stripe_sub_id)
        )
        sub = result.scalar_one_or_none()
        if sub and sub.status == "past_due":
            sub.status = "active"
            await db.commit()
            logger.info("Subscription reactivated after payment: stripe_sub=%s", stripe_sub_id)


async def _handle_invoice_payment_failed(event: dict, db: AsyncSession) -> None:
    """Handle invoice.payment_failed — mark subscription as past_due."""
    invoice_obj = event.get("data", {}).get("object", {})
    stripe_sub_id = invoice_obj.get("subscription", "")

    if not stripe_sub_id:
        return

    from marketplace.models.billing import Subscription
    from sqlalchemy import select

    result = await db.execute(
        select(Subscription).where(Subscription.stripe_subscription_id == stripe_sub_id)
    )
    sub = result.scalar_one_or_none()
    if not sub:
        logger.warning("invoice.payment_failed: no subscription for stripe_sub=%s", stripe_sub_id)
        return

    sub.status = "past_due"
    await db.commit()
    logger.warning("Subscription set to past_due after payment failure: stripe_sub=%s", stripe_sub_id)


# ── Razorpay event handlers ──

async def _handle_razorpay_payment_captured(event: dict) -> None:
    """Process captured Razorpay payment."""
    payload = event.get("payload", {}).get("payment", {}).get("entity", {})
    payment_id = payload.get("id", "")
    logger.info("Razorpay payment captured: %s", payment_id)
    # TODO: Update transaction status, credit seller


async def _handle_razorpay_payment_failed(event: dict) -> None:
    """Process failed Razorpay payment."""
    payload = event.get("payload", {}).get("payment", {}).get("entity", {})
    payment_id = payload.get("id", "")
    logger.warning("Razorpay payment failed: %s", payment_id)
    # TODO: Update transaction status to failed


async def _handle_razorpay_order_paid(event: dict) -> None:
    """Process Razorpay order paid event."""
    payload = event.get("payload", {}).get("order", {}).get("entity", {})
    order_id = payload.get("id", "")
    logger.info("Razorpay order paid: %s", order_id)


async def _handle_razorpay_payout_processed(event: dict) -> None:
    """Process Razorpay payout completion."""
    payload = event.get("payload", {}).get("payout", {}).get("entity", {})
    payout_id = payload.get("id", "")
    logger.info("Razorpay payout processed: %s", payout_id)
    # TODO: Update creator payout record
