"""Addendum tests for stripe_service.py: retrieve_payment_intent."""

import pytest

from marketplace.services.stripe_service import StripePaymentService


class TestRetrievePaymentIntent:
    async def test_simulated(self):
        svc = StripePaymentService()
        result = await svc.retrieve_payment_intent("pi_test_123")
        assert result["id"] == "pi_test_123"
        assert result["status"] == "succeeded"
        assert result["simulated"] is True

    async def test_real_raises(self):
        svc = StripePaymentService(secret_key="sk_live_real")
        with pytest.raises(NotImplementedError):
            await svc.retrieve_payment_intent("pi_test_123")

