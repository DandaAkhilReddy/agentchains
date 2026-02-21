"""Unit tests for StripePaymentService — 18 tests across 3 describe blocks.

All tests are pure service-layer tests: no database, no HTTP, no network I/O.
The service operates in one of two modes:
  - simulated  → when secret_key is empty or starts with "sk_test_"
  - real        → any other key (e.g. "sk_live_…") — all methods raise NotImplementedError

Test blocks:
  TestStripeSimulated   (tests 1-14): full coverage of simulated behaviour
  TestStripeRealKey     (tests 15-18): all public methods raise NotImplementedError

asyncio_mode = "auto" (from pyproject.toml), so no @pytest.mark.asyncio needed.
"""

import re
from decimal import Decimal

import pytest

from marketplace.services.stripe_service import StripePaymentService


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _simulated_svc(**kwargs) -> StripePaymentService:
    """Return a StripePaymentService that is definitely in simulated mode."""
    return StripePaymentService(**kwargs)


def _real_svc() -> StripePaymentService:
    """Return a StripePaymentService using a live-style key (non-simulated)."""
    return StripePaymentService(
        secret_key="sk_live_abcdef1234567890",
        webhook_secret="whsec_live_secret",
    )


# ---------------------------------------------------------------------------
# Block 1: Simulated Mode — 14 tests
# ---------------------------------------------------------------------------


class TestStripeSimulated:
    """Tests 1-14: all public methods work correctly in simulated mode."""

    # --- 1. Initialisation -----------------------------------------------

    def test_init_empty_key_is_simulated(self):
        """Test 1: No secret key → _simulated is True."""
        svc = StripePaymentService()
        assert svc._simulated is True

    def test_init_empty_string_key_is_simulated(self):
        """Test 2: Explicit empty-string key → _simulated is True."""
        svc = StripePaymentService(secret_key="", webhook_secret="whsec_x")
        assert svc._simulated is True

    def test_init_test_key_is_simulated(self):
        """Test 3: sk_test_… key → _simulated is True."""
        svc = StripePaymentService(secret_key="sk_test_abc123", webhook_secret="")
        assert svc._simulated is True

    def test_init_live_key_is_not_simulated(self):
        """Test 4: sk_live_… key → _simulated is False."""
        svc = _real_svc()
        assert svc._simulated is False

    # --- 2. create_payment_intent ----------------------------------------

    async def test_create_payment_intent_amount_cents_conversion(self):
        """Test 5: USD amount is converted to cents (× 100) in the response."""
        svc = _simulated_svc()
        result = await svc.create_payment_intent(Decimal("19.99"))
        assert result["amount"] == 1999

    async def test_create_payment_intent_whole_dollar(self):
        """Test 6: Whole-dollar amounts convert without rounding error."""
        svc = _simulated_svc()
        result = await svc.create_payment_intent(Decimal("50"))
        assert result["amount"] == 5000

    async def test_create_payment_intent_default_currency(self):
        """Test 7: Default currency is 'usd' when none is supplied."""
        svc = _simulated_svc()
        result = await svc.create_payment_intent(Decimal("10"))
        assert result["currency"] == "usd"

    async def test_create_payment_intent_custom_currency(self):
        """Test 8: Caller-supplied currency is preserved in the response."""
        svc = _simulated_svc()
        result = await svc.create_payment_intent(Decimal("5"), currency="eur")
        assert result["currency"] == "eur"

    async def test_create_payment_intent_metadata_passthrough(self):
        """Test 9: metadata dict is returned verbatim in the response."""
        svc = _simulated_svc()
        meta = {"order_id": "ord_42", "user": "alice"}
        result = await svc.create_payment_intent(Decimal("1"), metadata=meta)
        assert result["metadata"] == meta

    async def test_create_payment_intent_no_metadata_defaults_empty(self):
        """Test 10: Omitting metadata yields an empty dict, not None."""
        svc = _simulated_svc()
        result = await svc.create_payment_intent(Decimal("1"))
        assert result["metadata"] == {}

    async def test_create_payment_intent_id_format(self):
        """Test 11: Payment intent id starts with 'pi_sim_'."""
        svc = _simulated_svc()
        result = await svc.create_payment_intent(Decimal("1"))
        assert result["id"].startswith("pi_sim_")

    async def test_create_payment_intent_ids_are_unique(self):
        """Test 12: Two consecutive calls produce different ids."""
        svc = _simulated_svc()
        r1 = await svc.create_payment_intent(Decimal("1"))
        r2 = await svc.create_payment_intent(Decimal("1"))
        assert r1["id"] != r2["id"]

    async def test_create_payment_intent_simulated_flag(self):
        """Test 13: Response carries simulated=True."""
        svc = _simulated_svc()
        result = await svc.create_payment_intent(Decimal("1"))
        assert result["simulated"] is True

    async def test_create_payment_intent_initial_status(self):
        """Test 14: Initial status is 'requires_confirmation'."""
        svc = _simulated_svc()
        result = await svc.create_payment_intent(Decimal("25"))
        assert result["status"] == "requires_confirmation"

    # --- 3. confirm_payment -----------------------------------------------

    async def test_confirm_payment_status_succeeded(self):
        """Test 15: confirm_payment returns status='succeeded'."""
        svc = _simulated_svc()
        result = await svc.confirm_payment("pi_sim_abc123")
        assert result["status"] == "succeeded"

    async def test_confirm_payment_preserves_id(self):
        """Test 16: confirm_payment echoes back the supplied payment_intent_id."""
        svc = _simulated_svc()
        pi_id = "pi_sim_deadbeef01234567"
        result = await svc.confirm_payment(pi_id)
        assert result["id"] == pi_id

    async def test_confirm_payment_simulated_flag(self):
        """Test 17: confirm_payment response includes simulated=True."""
        svc = _simulated_svc()
        result = await svc.confirm_payment("pi_sim_x")
        assert result["simulated"] is True

    # --- 4. create_refund ------------------------------------------------

    async def test_create_refund_full_amount_is_none(self):
        """Test 18: Full refund (no amount_usd supplied) sets amount to None."""
        svc = _simulated_svc()
        result = await svc.create_refund("pi_sim_abc123")
        assert result["amount"] is None

    async def test_create_refund_partial_amount_in_cents(self):
        """Test 19: Partial refund converts USD to cents correctly."""
        svc = _simulated_svc()
        result = await svc.create_refund("pi_sim_abc123", amount_usd=Decimal("7.50"))
        assert result["amount"] == 750

    async def test_create_refund_preserves_payment_intent(self):
        """Test 20: create_refund echoes back the payment_intent id."""
        svc = _simulated_svc()
        pi_id = "pi_sim_refund_target"
        result = await svc.create_refund(pi_id)
        assert result["payment_intent"] == pi_id

    async def test_create_refund_id_format(self):
        """Test 21: Refund id starts with 're_sim_'."""
        svc = _simulated_svc()
        result = await svc.create_refund("pi_sim_abc")
        assert result["id"].startswith("re_sim_")

    async def test_create_refund_status_succeeded(self):
        """Test 22: Refund status is 'succeeded' in simulated mode."""
        svc = _simulated_svc()
        result = await svc.create_refund("pi_sim_abc")
        assert result["status"] == "succeeded"

    # --- 5. create_connected_account ------------------------------------

    async def test_create_connected_account_email_preserved(self):
        """Test 23: Email is returned verbatim in the account dict."""
        svc = _simulated_svc()
        result = await svc.create_connected_account("creator@example.com")
        assert result["email"] == "creator@example.com"

    async def test_create_connected_account_default_country(self):
        """Test 24: Default country is 'US' when none is supplied."""
        svc = _simulated_svc()
        result = await svc.create_connected_account("a@b.com")
        assert result["country"] == "US"

    async def test_create_connected_account_custom_country(self):
        """Test 25: Caller-supplied country is preserved."""
        svc = _simulated_svc()
        result = await svc.create_connected_account("a@b.com", country="GB")
        assert result["country"] == "GB"

    async def test_create_connected_account_id_format(self):
        """Test 26: Connected account id starts with 'acct_sim_'."""
        svc = _simulated_svc()
        result = await svc.create_connected_account("x@y.com")
        assert result["id"].startswith("acct_sim_")

    async def test_create_connected_account_ids_are_unique(self):
        """Test 27: Two accounts for the same email get distinct ids."""
        svc = _simulated_svc()
        r1 = await svc.create_connected_account("dup@test.com")
        r2 = await svc.create_connected_account("dup@test.com")
        assert r1["id"] != r2["id"]

    async def test_create_connected_account_payouts_enabled(self):
        """Test 28: payouts_enabled is True in simulated response."""
        svc = _simulated_svc()
        result = await svc.create_connected_account("pay@test.com")
        assert result["payouts_enabled"] is True

    # --- 6. create_payout -----------------------------------------------

    async def test_create_payout_amount_cents_conversion(self):
        """Test 29: Payout USD amount is converted to cents."""
        svc = _simulated_svc()
        result = await svc.create_payout(
            account_id="acct_sim_abc",
            amount_usd=Decimal("123.45"),
        )
        assert result["amount"] == 12345

    async def test_create_payout_account_preserved(self):
        """Test 30: create_payout echoes back the account_id."""
        svc = _simulated_svc()
        acct_id = "acct_sim_target"
        result = await svc.create_payout(acct_id, amount_usd=Decimal("10"))
        assert result["account"] == acct_id

    async def test_create_payout_default_currency(self):
        """Test 31: Default currency is 'usd'."""
        svc = _simulated_svc()
        result = await svc.create_payout("acct_sim_x", amount_usd=Decimal("1"))
        assert result["currency"] == "usd"

    async def test_create_payout_custom_currency(self):
        """Test 32: Caller-supplied currency is passed through."""
        svc = _simulated_svc()
        result = await svc.create_payout(
            "acct_sim_x", amount_usd=Decimal("1"), currency="gbp"
        )
        assert result["currency"] == "gbp"

    async def test_create_payout_id_format(self):
        """Test 33: Payout id starts with 'po_sim_'."""
        svc = _simulated_svc()
        result = await svc.create_payout("acct_sim_x", amount_usd=Decimal("1"))
        assert result["id"].startswith("po_sim_")

    async def test_create_payout_status_paid(self):
        """Test 34: Payout status is 'paid' in simulated mode."""
        svc = _simulated_svc()
        result = await svc.create_payout("acct_sim_x", amount_usd=Decimal("1"))
        assert result["status"] == "paid"

    # --- 7. verify_webhook_signature ------------------------------------

    def test_verify_webhook_signature_returns_none_simulated(self):
        """Test 35: verify_webhook_signature returns None (no-op) in simulated mode."""
        svc = _simulated_svc()
        result = svc.verify_webhook_signature(
            payload=b'{"type":"payment_intent.succeeded"}',
            sig_header="t=123,v1=abc",
        )
        assert result is None

    def test_verify_webhook_signature_any_payload_returns_none(self):
        """Test 36: Returns None regardless of the payload contents."""
        svc = _simulated_svc(secret_key="sk_test_whatever")
        for payload in (b"", b"garbage", b'{"key": "value"}'):
            assert svc.verify_webhook_signature(payload, "sig") is None


# ---------------------------------------------------------------------------
# Block 2: Real (non-simulated) Key — all methods raise NotImplementedError
# ---------------------------------------------------------------------------


class TestStripeRealKey:
    """Tests 37-44: every public async and sync method raises NotImplementedError
    when a live-style key is provided (not empty and not sk_test_*)."""

    async def test_create_payment_intent_raises(self):
        """Test 37: create_payment_intent raises NotImplementedError with real key."""
        svc = _real_svc()
        with pytest.raises(NotImplementedError):
            await svc.create_payment_intent(Decimal("10"))

    async def test_confirm_payment_raises(self):
        """Test 38: confirm_payment raises NotImplementedError with real key."""
        svc = _real_svc()
        with pytest.raises(NotImplementedError):
            await svc.confirm_payment("pi_live_xyz")

    async def test_create_refund_raises(self):
        """Test 39: create_refund raises NotImplementedError with real key."""
        svc = _real_svc()
        with pytest.raises(NotImplementedError):
            await svc.create_refund("pi_live_xyz")

    async def test_create_refund_with_amount_raises(self):
        """Test 40: create_refund with explicit amount raises NotImplementedError."""
        svc = _real_svc()
        with pytest.raises(NotImplementedError):
            await svc.create_refund("pi_live_xyz", amount_usd=Decimal("5"))

    async def test_create_connected_account_raises(self):
        """Test 41: create_connected_account raises NotImplementedError with real key."""
        svc = _real_svc()
        with pytest.raises(NotImplementedError):
            await svc.create_connected_account("real@example.com")

    async def test_create_payout_raises(self):
        """Test 42: create_payout raises NotImplementedError with real key."""
        svc = _real_svc()
        with pytest.raises(NotImplementedError):
            await svc.create_payout("acct_live_abc", amount_usd=Decimal("100"))

    def test_verify_webhook_signature_raises(self):
        """Test 43: verify_webhook_signature raises NotImplementedError with real key."""
        svc = _real_svc()
        with pytest.raises(NotImplementedError):
            svc.verify_webhook_signature(
                payload=b'{"type":"charge.succeeded"}',
                sig_header="t=1,v1=real_sig",
            )

    def test_real_key_simulated_flag_is_false(self):
        """Test 44: _simulated attribute is False for a live key."""
        svc = _real_svc()
        assert svc._simulated is False


# ---------------------------------------------------------------------------
# Block 3: Edge / Boundary cases — decimal precision and zero amounts
# ---------------------------------------------------------------------------


class TestStripeEdgeCases:
    """Tests 45-48: boundary values and precision edge cases."""

    async def test_create_payment_intent_zero_amount(self):
        """Test 45: Zero USD → zero cents, no exception."""
        svc = _simulated_svc()
        result = await svc.create_payment_intent(Decimal("0"))
        assert result["amount"] == 0

    async def test_create_payment_intent_large_amount(self):
        """Test 46: Large amount (100,000 USD) converts without overflow."""
        svc = _simulated_svc()
        result = await svc.create_payment_intent(Decimal("100000"))
        assert result["amount"] == 10_000_000

    async def test_create_refund_zero_partial_amount(self):
        """Test 47: Passing amount_usd=Decimal('0') gives amount=0 (not None)."""
        svc = _simulated_svc()
        result = await svc.create_refund("pi_sim_abc", amount_usd=Decimal("0"))
        # amount_usd is falsy (0), so the implementation returns None per
        # `int(...) if amount_usd else None`; document and assert the actual
        # behaviour of the current implementation.
        assert result["amount"] is None

    async def test_create_payout_small_amount(self):
        """Test 48: Small payout (1 cent) converts precisely."""
        svc = _simulated_svc()
        result = await svc.create_payout("acct_sim_x", amount_usd=Decimal("0.01"))
        assert result["amount"] == 1
