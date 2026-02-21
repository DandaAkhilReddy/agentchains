"""Payment webhook handlers for Stripe and Razorpay.

Receives and processes payment event notifications from payment providers.
Validates signatures before processing to prevent spoofing.
"""

import json
import logging

from fastapi import APIRouter, Header, Request
from fastapi.responses import JSONResponse

from marketplace.config import settings

router = APIRouter(tags=["webhooks"])
logger = logging.getLogger(__name__)


@router.post("/webhooks/stripe")
async def stripe_webhook(
    request: Request,
    stripe_signature: str = Header(None, alias="Stripe-Signature"),
):
    """Handle Stripe webhook events."""
    from marketplace.services.stripe_service import StripePaymentService

    payload = await request.body()
    service = StripePaymentService(
        secret_key=settings.stripe_secret_key,
        webhook_secret=settings.stripe_webhook_secret,
    )

    if not service._simulated:
        # In live mode, signature verification is mandatory
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

    if event_type == "payment_intent.succeeded":
        await _handle_stripe_payment_succeeded(event)
    elif event_type == "payment_intent.payment_failed":
        await _handle_stripe_payment_failed(event)
    elif event_type == "charge.refunded":
        await _handle_stripe_refund(event)
    elif event_type == "account.updated":
        await _handle_stripe_account_updated(event)
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


async def _handle_stripe_account_updated(event: dict) -> None:
    """Process Stripe Connect account update."""
    data = event.get("data", {})
    account_id = data.get("id", "")
    logger.info("Stripe account updated: %s", account_id)
    # TODO: Update creator's payout status


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
