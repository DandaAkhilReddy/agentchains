import uuid

from marketplace.config import settings


class PaymentService:
    """Handles x402 payment flow with dual-mode: simulated and real."""

    def __init__(self):
        self.mode = settings.payment_mode
        self.facilitator_url = settings.x402_facilitator_url
        self.network = settings.x402_network

    def build_payment_requirements(self, amount_usdc: float, seller_address: str) -> dict:
        """Build the payment requirements object returned with HTTP 402."""
        if self.mode == "simulated":
            return {
                "pay_to_address": seller_address or "0x" + "0" * 40,
                "network": self.network,
                "asset": "USDC",
                "amount_usdc": amount_usdc,
                "facilitator_url": self.facilitator_url,
                "simulated": True,
            }
        # Real x402 mode (testnet/mainnet)
        return {
            "pay_to_address": seller_address,
            "network": self.network,
            "asset": "USDC",
            "amount_usdc": amount_usdc,
            "facilitator_url": self.facilitator_url,
            "simulated": False,
        }

    def verify_payment(self, payment_signature: str, requirements: dict) -> dict:
        """Verify a payment signature against requirements."""
        if self.mode == "simulated" or requirements.get("simulated"):
            return {
                "verified": True,
                "tx_hash": f"sim_0x{uuid.uuid4().hex}",
                "simulated": True,
            }
        # Real verification would call x402 facilitator here
        # For now, return unverified for non-simulated mode without SDK
        return {
            "verified": False,
            "error": "Real x402 verification requires x402 SDK. Set PAYMENT_MODE=simulated for demo.",
        }


# Singleton
payment_service = PaymentService()
