"""Stripe payment integration stub.

Provides a Stripe-compatible payment interface that currently operates
in simulated mode. Replace simulation logic with real Stripe SDK calls
when ready for production.

Requires: STRIPE_SECRET_KEY and STRIPE_WEBHOOK_SECRET env vars.
"""

import logging
import uuid
from datetime import datetime, timezone
from decimal import Decimal

logger = logging.getLogger(__name__)


class StripePaymentService:
    """Stripe payment operations (stubbed for development)."""

    def __init__(self, secret_key: str = "", webhook_secret: str = ""):
        self.secret_key = secret_key
        self.webhook_secret = webhook_secret
        self._simulated = not secret_key or secret_key.startswith("sk_test_")

    async def create_payment_intent(
        self,
        amount_usd: Decimal,
        currency: str = "usd",
        metadata: dict | None = None,
    ) -> dict:
        """Create a Stripe PaymentIntent (or simulate one)."""
        if self._simulated:
            return {
                "id": f"pi_sim_{uuid.uuid4().hex[:16]}",
                "amount": int(amount_usd * 100),
                "currency": currency,
                "status": "requires_confirmation",
                "metadata": metadata or {},
                "created": int(datetime.now(timezone.utc).timestamp()),
                "simulated": True,
            }
        # TODO: Replace with real Stripe SDK call
        # import stripe
        # stripe.api_key = self.secret_key
        # return stripe.PaymentIntent.create(
        #     amount=int(amount_usd * 100),
        #     currency=currency,
        #     metadata=metadata or {},
        # )
        raise NotImplementedError("Real Stripe integration not yet configured")

    async def confirm_payment(self, payment_intent_id: str) -> dict:
        """Confirm a PaymentIntent."""
        if self._simulated:
            return {
                "id": payment_intent_id,
                "status": "succeeded",
                "simulated": True,
            }
        raise NotImplementedError("Real Stripe integration not yet configured")

    async def create_refund(
        self,
        payment_intent_id: str,
        amount_usd: Decimal | None = None,
    ) -> dict:
        """Refund a payment (full or partial)."""
        if self._simulated:
            return {
                "id": f"re_sim_{uuid.uuid4().hex[:16]}",
                "payment_intent": payment_intent_id,
                "amount": int((amount_usd or Decimal("0")) * 100) if amount_usd else None,
                "status": "succeeded",
                "simulated": True,
            }
        raise NotImplementedError("Real Stripe integration not yet configured")

    async def create_connected_account(self, email: str, country: str = "US") -> dict:
        """Create a Stripe Connect account for a creator."""
        if self._simulated:
            return {
                "id": f"acct_sim_{uuid.uuid4().hex[:12]}",
                "email": email,
                "country": country,
                "payouts_enabled": True,
                "simulated": True,
            }
        raise NotImplementedError("Real Stripe integration not yet configured")

    async def create_payout(
        self,
        account_id: str,
        amount_usd: Decimal,
        currency: str = "usd",
    ) -> dict:
        """Create a payout to a connected account."""
        if self._simulated:
            return {
                "id": f"po_sim_{uuid.uuid4().hex[:16]}",
                "account": account_id,
                "amount": int(amount_usd * 100),
                "currency": currency,
                "status": "paid",
                "simulated": True,
            }
        raise NotImplementedError("Real Stripe integration not yet configured")

    def verify_webhook_signature(self, payload: bytes, sig_header: str) -> dict | None:
        """Verify a Stripe webhook signature."""
        if self._simulated:
            logger.warning("Webhook signature verification skipped (simulated mode)")
            return None
        # TODO: stripe.Webhook.construct_event(payload, sig_header, self.webhook_secret)
        raise NotImplementedError("Real Stripe integration not yet configured")
