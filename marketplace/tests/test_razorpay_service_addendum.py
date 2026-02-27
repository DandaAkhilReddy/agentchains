"""Addendum tests for razorpay_service.py: fetch_payment."""

import pytest

from marketplace.services.razorpay_service import RazorpayPaymentService


class TestFetchPayment:
    async def test_simulated(self):
        svc = RazorpayPaymentService()
        result = await svc.fetch_payment("pay_test_456")
        assert result["id"] == "pay_test_456"
        assert result["status"] == "captured"
        assert result["simulated"] is True

    async def test_real_raises(self):
        svc = RazorpayPaymentService(key_id="rzp_live_x", key_secret="secret")
        with pytest.raises(NotImplementedError):
            await svc.fetch_payment("pay_test_456")

