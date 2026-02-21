"""Unit tests for RazorpayPaymentService — 20 tests across 3 classes.

Covers:
  TestRazorpaySimulated (15 tests):
    1  empty_key_sets_simulated_true — empty key_id → _simulated=True
    2  test_key_prefix_sets_simulated_true — rzp_test_* key → _simulated=True
    3  real_key_sets_simulated_false — rzp_live_* key → _simulated=False
    4  create_order_amount_conversion — INR amount multiplied by 100 (paise)
    5  create_order_default_currency — currency defaults to "INR"
    6  create_order_custom_currency — currency param is respected
    7  create_order_id_prefix — order id starts with "order_sim_"
    8  create_order_status_created — status field equals "created"
    9  create_order_explicit_receipt — provided receipt is echoed back
   10  create_order_auto_receipt — omitted receipt gets an auto-generated value
   11  create_order_ids_are_unique — two orders produce different ids
   12  create_order_simulated_flag — simulated=True present in response
   13  verify_payment_verified_true — returns verified=True
   14  verify_payment_echoes_ids — order_id and payment_id echoed back
   15  verify_payment_simulated_flag — simulated=True present in response
   16  create_payout_amount_conversion — INR amount multiplied by 100
   17  create_payout_default_mode — mode defaults to "NEFT"
   18  create_payout_custom_mode — custom mode is preserved in response
   19  create_payout_status_processed — status field equals "processed"
   20  create_payout_id_prefix — payout id starts with "pout_sim_"
   21  create_upi_payout_vpa_echoed — VPA is returned in response
   22  create_upi_payout_amount_conversion — INR amount multiplied by 100
   23  create_upi_payout_id_prefix — id starts with "pout_upi_sim_"
   24  create_upi_payout_status_processed — status field equals "processed"
   25  create_upi_payout_ids_are_unique — two UPI payouts have different ids

  TestRazorpayRealKey (5 tests):
   26  real_key_create_order_raises — NotImplementedError raised
   27  real_key_verify_payment_raises — NotImplementedError raised
   28  real_key_create_payout_raises — NotImplementedError raised
   29  real_key_create_upi_payout_raises — NotImplementedError raised
   30  real_key_error_message_mentions_integration — error message is descriptive

  TestRazorpayEdgeCases (5 tests):
   31  zero_amount_order — zero INR → zero paise
   32  large_amount_order — large INR converts correctly to paise
   33  zero_amount_payout — zero INR payout → zero paise
   34  large_amount_upi_payout — large UPI payout converts correctly
   35  test_key_no_secret_still_simulated — missing secret does not affect mode
"""

import pytest
from decimal import Decimal

from marketplace.services.razorpay_service import RazorpayPaymentService


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _sim(key_id: str = "", key_secret: str = "test-secret") -> RazorpayPaymentService:
    """Construct a service in simulated mode."""
    return RazorpayPaymentService(key_id=key_id, key_secret=key_secret)


def _real(key_id: str = "rzp_live_TESTKEY123456", key_secret: str = "live-secret") -> RazorpayPaymentService:
    """Construct a service with a non-test, non-empty key (real mode)."""
    return RazorpayPaymentService(key_id=key_id, key_secret=key_secret)


# ============================================================================
# 1. Simulated Mode — Initialization + All Methods (Tests 1-25)
# ============================================================================


class TestRazorpaySimulated:
    """Tests 1-25: simulated mode — init, create_order, verify_payment,
    create_payout, create_upi_payout."""

    # --- Initialization (Tests 1-3) ---

    def test_empty_key_sets_simulated_true(self):
        """Test 1: An empty key_id triggers simulated mode."""
        svc = RazorpayPaymentService(key_id="", key_secret="anything")
        assert svc._simulated is True

    def test_test_key_prefix_sets_simulated_true(self):
        """Test 2: A key starting with 'rzp_test_' triggers simulated mode."""
        svc = RazorpayPaymentService(key_id="rzp_test_ABC123", key_secret="sec")
        assert svc._simulated is True

    def test_real_key_sets_simulated_false(self):
        """Test 3: A non-empty, non-test key disables simulated mode."""
        svc = RazorpayPaymentService(key_id="rzp_live_PRODKEY", key_secret="sec")
        assert svc._simulated is False

    # --- create_order (Tests 4-12) ---

    async def test_create_order_amount_conversion(self):
        """Test 4: Amount in INR is multiplied by 100 to produce paise."""
        svc = _sim()
        result = await svc.create_order(amount_inr=Decimal("499.00"))
        assert result["amount"] == 49900

    async def test_create_order_default_currency(self):
        """Test 5: Currency defaults to 'INR' when not supplied."""
        svc = _sim()
        result = await svc.create_order(amount_inr=Decimal("100"))
        assert result["currency"] == "INR"

    async def test_create_order_custom_currency(self):
        """Test 6: An explicitly supplied currency is returned as-is."""
        svc = _sim()
        result = await svc.create_order(amount_inr=Decimal("100"), currency="USD")
        assert result["currency"] == "USD"

    async def test_create_order_id_prefix(self):
        """Test 7: Simulated order id always starts with 'order_sim_'."""
        svc = _sim()
        result = await svc.create_order(amount_inr=Decimal("10"))
        assert result["id"].startswith("order_sim_")

    async def test_create_order_status_created(self):
        """Test 8: Status field in a new order is always 'created'."""
        svc = _sim()
        result = await svc.create_order(amount_inr=Decimal("250"))
        assert result["status"] == "created"

    async def test_create_order_explicit_receipt(self):
        """Test 9: An explicitly supplied receipt value is echoed back unchanged."""
        svc = _sim()
        result = await svc.create_order(
            amount_inr=Decimal("200"), receipt="inv_2026_001"
        )
        assert result["receipt"] == "inv_2026_001"

    async def test_create_order_auto_receipt(self):
        """Test 10: When receipt is omitted, an auto-generated receipt is provided."""
        svc = _sim()
        result = await svc.create_order(amount_inr=Decimal("150"))
        assert result["receipt"] is not None
        assert len(result["receipt"]) > 0

    async def test_create_order_ids_are_unique(self):
        """Test 11: Two successive create_order calls produce different ids."""
        svc = _sim()
        r1 = await svc.create_order(amount_inr=Decimal("100"))
        r2 = await svc.create_order(amount_inr=Decimal("100"))
        assert r1["id"] != r2["id"]

    async def test_create_order_simulated_flag(self):
        """Test 12: Response includes simulated=True in simulated mode."""
        svc = _sim()
        result = await svc.create_order(amount_inr=Decimal("50"))
        assert result.get("simulated") is True

    # --- verify_payment (Tests 13-15) ---

    async def test_verify_payment_verified_true(self):
        """Test 13: verify_payment always returns verified=True in simulated mode."""
        svc = _sim()
        result = await svc.verify_payment(
            order_id="order_sim_abc",
            payment_id="pay_sim_xyz",
            signature="fake_sig",
        )
        assert result["verified"] is True

    async def test_verify_payment_echoes_ids(self):
        """Test 14: order_id and payment_id are echoed back in the response."""
        svc = _sim()
        result = await svc.verify_payment(
            order_id="order_sim_test123",
            payment_id="pay_sim_test456",
            signature="sig",
        )
        assert result["order_id"] == "order_sim_test123"
        assert result["payment_id"] == "pay_sim_test456"

    async def test_verify_payment_simulated_flag(self):
        """Test 15: Response includes simulated=True in simulated mode."""
        svc = _sim()
        result = await svc.verify_payment("o1", "p1", "s1")
        assert result.get("simulated") is True

    # --- create_payout (Tests 16-20) ---

    async def test_create_payout_amount_conversion(self):
        """Test 16: create_payout converts INR to paise (x100)."""
        svc = _sim()
        result = await svc.create_payout(
            account_number="1234567890",
            ifsc="HDFC0001234",
            amount_inr=Decimal("1000.50"),
        )
        assert result["amount"] == 100050

    async def test_create_payout_default_mode(self):
        """Test 17: Default transfer mode is 'NEFT' when not specified."""
        svc = _sim()
        result = await svc.create_payout(
            account_number="9876543210",
            ifsc="SBIN0001234",
            amount_inr=Decimal("500"),
        )
        assert result["mode"] == "NEFT"

    async def test_create_payout_custom_mode(self):
        """Test 18: A custom mode (e.g. 'IMPS') is preserved in the response."""
        svc = _sim()
        result = await svc.create_payout(
            account_number="1111222233",
            ifsc="ICIC0001234",
            amount_inr=Decimal("750"),
            mode="IMPS",
        )
        assert result["mode"] == "IMPS"

    async def test_create_payout_status_processed(self):
        """Test 19: Simulated payout always returns status 'processed'."""
        svc = _sim()
        result = await svc.create_payout(
            account_number="4444555566",
            ifsc="AXIS0001234",
            amount_inr=Decimal("300"),
        )
        assert result["status"] == "processed"

    async def test_create_payout_id_prefix(self):
        """Test 20: Simulated payout id starts with 'pout_sim_'."""
        svc = _sim()
        result = await svc.create_payout(
            account_number="7777888899",
            ifsc="KOTAK001234",
            amount_inr=Decimal("200"),
        )
        assert result["id"].startswith("pout_sim_")

    # --- create_upi_payout (Tests 21-25) ---

    async def test_create_upi_payout_vpa_echoed(self):
        """Test 21: The VPA address is included in the response."""
        svc = _sim()
        result = await svc.create_upi_payout(
            vpa="creator@upi", amount_inr=Decimal("100")
        )
        assert result["vpa"] == "creator@upi"

    async def test_create_upi_payout_amount_conversion(self):
        """Test 22: create_upi_payout converts INR to paise (x100)."""
        svc = _sim()
        result = await svc.create_upi_payout(
            vpa="artist@paytm", amount_inr=Decimal("299.99")
        )
        assert result["amount"] == 29999

    async def test_create_upi_payout_id_prefix(self):
        """Test 23: UPI payout id starts with 'pout_upi_sim_'."""
        svc = _sim()
        result = await svc.create_upi_payout(
            vpa="user@ybl", amount_inr=Decimal("50")
        )
        assert result["id"].startswith("pout_upi_sim_")

    async def test_create_upi_payout_status_processed(self):
        """Test 24: Simulated UPI payout always returns status 'processed'."""
        svc = _sim()
        result = await svc.create_upi_payout(
            vpa="writer@oksbi", amount_inr=Decimal("80")
        )
        assert result["status"] == "processed"

    async def test_create_upi_payout_ids_are_unique(self):
        """Test 25: Two successive UPI payout calls produce different ids."""
        svc = _sim()
        r1 = await svc.create_upi_payout("a@upi", Decimal("10"))
        r2 = await svc.create_upi_payout("a@upi", Decimal("10"))
        assert r1["id"] != r2["id"]


# ============================================================================
# 2. Real Key Mode — All Methods Raise NotImplementedError (Tests 26-30)
# ============================================================================


class TestRazorpayRealKey:
    """Tests 26-30: when a live (non-test) key is supplied, every method
    raises NotImplementedError because production SDK is not yet wired up."""

    async def test_real_key_create_order_raises(self):
        """Test 26: create_order raises NotImplementedError with a real key."""
        svc = _real()
        with pytest.raises(NotImplementedError):
            await svc.create_order(amount_inr=Decimal("100"))

    async def test_real_key_verify_payment_raises(self):
        """Test 27: verify_payment raises NotImplementedError with a real key."""
        svc = _real()
        with pytest.raises(NotImplementedError):
            await svc.verify_payment("order_1", "pay_1", "sig_1")

    async def test_real_key_create_payout_raises(self):
        """Test 28: create_payout raises NotImplementedError with a real key."""
        svc = _real()
        with pytest.raises(NotImplementedError):
            await svc.create_payout(
                account_number="000111222",
                ifsc="HDFC0000001",
                amount_inr=Decimal("500"),
            )

    async def test_real_key_create_upi_payout_raises(self):
        """Test 29: create_upi_payout raises NotImplementedError with a real key."""
        svc = _real()
        with pytest.raises(NotImplementedError):
            await svc.create_upi_payout(vpa="someone@upi", amount_inr=Decimal("50"))

    async def test_real_key_error_message_mentions_integration(self):
        """Test 30: NotImplementedError message is informative, not a bare stub."""
        svc = _real()
        with pytest.raises(NotImplementedError, match="(?i)razorpay"):
            await svc.create_order(amount_inr=Decimal("1"))


# ============================================================================
# 3. Edge Cases (Tests 31-35)
# ============================================================================


class TestRazorpayEdgeCases:
    """Tests 31-35: zero amounts, very large amounts, missing secret."""

    async def test_zero_amount_order(self):
        """Test 31: A zero-rupee order correctly produces zero paise."""
        svc = _sim()
        result = await svc.create_order(amount_inr=Decimal("0"))
        assert result["amount"] == 0
        assert result["status"] == "created"

    async def test_large_amount_order(self):
        """Test 32: A large rupee amount (e.g. 10 lakh) converts correctly to paise."""
        svc = _sim()
        amount_inr = Decimal("100000")  # ₹1,00,000
        result = await svc.create_order(amount_inr=amount_inr)
        assert result["amount"] == 10_000_000  # 1 crore paise

    async def test_zero_amount_payout(self):
        """Test 33: A zero-rupee bank payout produces zero paise."""
        svc = _sim()
        result = await svc.create_payout(
            account_number="0000000000",
            ifsc="TEST0000001",
            amount_inr=Decimal("0"),
        )
        assert result["amount"] == 0
        assert result["status"] == "processed"

    async def test_large_amount_upi_payout(self):
        """Test 34: A large UPI payout (50 lakh INR) converts correctly to paise."""
        svc = _sim()
        amount_inr = Decimal("500000")  # ₹5,00,000
        result = await svc.create_upi_payout(vpa="bigcreator@upi", amount_inr=amount_inr)
        assert result["amount"] == 50_000_000  # 5 crore paise
        assert result["vpa"] == "bigcreator@upi"

    def test_test_key_no_secret_still_simulated(self):
        """Test 35: A test key with an empty secret still triggers simulated mode."""
        svc = RazorpayPaymentService(key_id="rzp_test_NoSecret", key_secret="")
        assert svc._simulated is True
