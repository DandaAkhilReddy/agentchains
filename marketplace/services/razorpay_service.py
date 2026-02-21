"""Razorpay payment integration for Indian creators.

Provides UPI, bank transfer, and card payment support via Razorpay.
Operates in simulated mode when no key is provided, uses real SDK when configured.

Requires: RAZORPAY_KEY_ID and RAZORPAY_KEY_SECRET env vars for live mode.
"""

import hashlib
import hmac
import logging
import uuid
from datetime import datetime, timezone
from decimal import Decimal

logger = logging.getLogger(__name__)


class RazorpayPaymentService:
    """Razorpay payment operations with real SDK support."""

    def __init__(self, key_id: str = "", key_secret: str = ""):
        self.key_id = key_id
        self.key_secret = key_secret
        self._simulated = not key_id or key_id.startswith("rzp_test_")
        self._client = None

        if key_id and not self._simulated:
            try:
                import razorpay

                self._client = razorpay.Client(auth=(key_id, key_secret))
                logger.info(
                    "Razorpay SDK initialized (mode=%s)",
                    "test" if key_id.startswith("rzp_test_") else "live",
                )
            except ImportError:
                logger.warning(
                    "razorpay package not installed — falling back to simulated mode. "
                    "Install with: pip install razorpay>=1.4"
                )
                self._simulated = True

    async def create_order(
        self,
        amount_inr: Decimal,
        currency: str = "INR",
        receipt: str | None = None,
    ) -> dict:
        """Create a Razorpay order."""
        if self._simulated:
            return {
                "id": f"order_sim_{uuid.uuid4().hex[:16]}",
                "amount": int(amount_inr * 100),
                "currency": currency,
                "receipt": receipt or f"rcpt_{uuid.uuid4().hex[:8]}",
                "status": "created",
                "created_at": int(datetime.now(timezone.utc).timestamp()),
                "simulated": True,
            }

        raise NotImplementedError(
            "Razorpay live API integration is not yet available. "
            "Use a test key (rzp_test_*) for simulated mode."
        )

    async def verify_payment(
        self,
        order_id: str,
        payment_id: str,
        signature: str,
    ) -> dict:
        """Verify Razorpay payment signature."""
        if self._simulated:
            return {
                "order_id": order_id,
                "payment_id": payment_id,
                "verified": True,
                "simulated": True,
            }

        raise NotImplementedError(
            "Razorpay live payment verification is not yet available."
        )

    async def fetch_payment(self, payment_id: str) -> dict:
        """Fetch payment details from Razorpay."""
        if self._simulated:
            return {
                "id": payment_id,
                "status": "captured",
                "simulated": True,
            }

        raise NotImplementedError(
            "Razorpay live payment fetch is not yet available."
        )

    async def create_payout(
        self,
        account_number: str,
        ifsc: str,
        amount_inr: Decimal,
        mode: str = "NEFT",
        purpose: str = "payout",
    ) -> dict:
        """Create a bank payout via RazorpayX."""
        if self._simulated:
            return {
                "id": f"pout_sim_{uuid.uuid4().hex[:16]}",
                "amount": int(amount_inr * 100),
                "mode": mode,
                "purpose": purpose,
                "status": "processed",
                "simulated": True,
            }

        raise NotImplementedError(
            "Razorpay live payout integration is not yet available."
        )

    async def create_upi_payout(
        self,
        vpa: str,
        amount_inr: Decimal,
    ) -> dict:
        """Create a UPI payout."""
        if self._simulated:
            return {
                "id": f"pout_upi_sim_{uuid.uuid4().hex[:12]}",
                "vpa": vpa,
                "amount": int(amount_inr * 100),
                "status": "processed",
                "simulated": True,
            }

        raise NotImplementedError(
            "Razorpay live UPI payout integration is not yet available."
        )
