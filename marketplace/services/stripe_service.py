"""Stripe payment integration.

Provides a Stripe-compatible payment interface that operates in simulated
mode when no secret key is provided, and uses real Stripe SDK when configured.

Requires: STRIPE_SECRET_KEY and STRIPE_WEBHOOK_SECRET env vars for live mode.
"""

import logging
import uuid
from datetime import datetime, timezone
from decimal import Decimal

logger = logging.getLogger(__name__)


class StripePaymentService:
    """Stripe payment operations with real SDK support."""

    def __init__(self, secret_key: str = "", webhook_secret: str = ""):
        self.secret_key = secret_key
        self.webhook_secret = webhook_secret
        self._simulated = not secret_key
        self._stripe = None

        if secret_key and not self._simulated:
            try:
                import stripe

                stripe.api_key = secret_key
                self._stripe = stripe
                logger.info(
                    "Stripe SDK initialized (mode=%s)",
                    "test" if secret_key.startswith("sk_test_") else "live",
                )
            except ImportError:
                logger.warning(
                    "stripe package not installed — falling back to simulated mode. "
                    "Install with: pip install stripe>=8.0"
                )
                self._simulated = True

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

        intent = self._stripe.PaymentIntent.create(
            amount=int(amount_usd * 100),
            currency=currency,
            metadata=metadata or {},
        )
        return {
            "id": intent.id,
            "amount": intent.amount,
            "currency": intent.currency,
            "status": intent.status,
            "metadata": dict(intent.metadata) if intent.metadata else {},
            "created": intent.created,
            "client_secret": intent.client_secret,
            "simulated": False,
        }

    async def confirm_payment(self, payment_intent_id: str) -> dict:
        """Confirm a PaymentIntent."""
        if self._simulated:
            return {
                "id": payment_intent_id,
                "status": "succeeded",
                "simulated": True,
            }

        intent = self._stripe.PaymentIntent.confirm(payment_intent_id)
        return {
            "id": intent.id,
            "status": intent.status,
            "simulated": False,
        }

    async def retrieve_payment_intent(self, payment_intent_id: str) -> dict:
        """Retrieve a PaymentIntent by ID."""
        if self._simulated:
            return {
                "id": payment_intent_id,
                "status": "succeeded",
                "simulated": True,
            }

        intent = self._stripe.PaymentIntent.retrieve(payment_intent_id)
        return {
            "id": intent.id,
            "amount": intent.amount,
            "currency": intent.currency,
            "status": intent.status,
            "metadata": dict(intent.metadata) if intent.metadata else {},
            "simulated": False,
        }

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

        params = {"payment_intent": payment_intent_id}
        if amount_usd is not None:
            params["amount"] = int(amount_usd * 100)
        refund = self._stripe.Refund.create(**params)
        return {
            "id": refund.id,
            "payment_intent": payment_intent_id,
            "amount": refund.amount,
            "status": refund.status,
            "simulated": False,
        }

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

        account = self._stripe.Account.create(
            type="express",
            email=email,
            country=country,
            capabilities={
                "transfers": {"requested": True},
            },
        )
        return {
            "id": account.id,
            "email": email,
            "country": country,
            "payouts_enabled": account.payouts_enabled,
            "simulated": False,
        }

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

        transfer = self._stripe.Transfer.create(
            amount=int(amount_usd * 100),
            currency=currency,
            destination=account_id,
        )
        return {
            "id": transfer.id,
            "account": account_id,
            "amount": transfer.amount,
            "currency": currency,
            "status": "paid",
            "simulated": False,
        }

    def verify_webhook_signature(self, payload: bytes, sig_header: str) -> dict | None:
        """Verify a Stripe webhook signature and return the event."""
        if self._simulated:
            logger.warning("Webhook signature verification skipped (simulated mode)")
            return None

        try:
            event = self._stripe.Webhook.construct_event(
                payload, sig_header, self.webhook_secret
            )
            return {
                "id": event.id,
                "type": event.type,
                "data": event.data.object if event.data else {},
            }
        except self._stripe.error.SignatureVerificationError:
            logger.warning("Invalid Stripe webhook signature")
            return None
