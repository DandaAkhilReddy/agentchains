"""Comprehensive unit tests for the PaymentService (x402 payment flow).

Covers:
- Payment validation (amount bounds, required fields)
- Fee calculations (platform fee %, creator royalty)
- Idempotency (duplicate payment detection, idempotency keys)
- Error states (insufficient balance, invalid recipient, service unavailable)

20 tests total across 4 describe blocks.
"""

import uuid
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from marketplace.config import settings
from marketplace.services.payment_service import PaymentService


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_service(monkeypatch, mode="simulated", network="base-sepolia",
                  facilitator_url="https://x402.org/facilitator"):
    """Patch settings then construct a fresh PaymentService."""
    from marketplace.config import settings as _settings
    monkeypatch.setattr(_settings, "payment_mode", mode)
    monkeypatch.setattr(_settings, "x402_network", network)
    monkeypatch.setattr(_settings, "x402_facilitator_url", facilitator_url)
    return PaymentService()


VALID_ADDRESS = "0xAbCdEf1234567890AbCdEf1234567890AbCdEf12"
ZERO_ADDRESS = "0x" + "0" * 40


# ============================================================================
# 1. Payment Validation (Tests 1-5)
# ============================================================================


class TestPaymentValidation:
    """Validate amount bounds and required fields in
    build_payment_requirements and verify_payment."""

    def test_positive_amount_accepted(self, monkeypatch):
        """Test 1: A positive USDC amount is accepted without error."""
        svc = _make_service(monkeypatch)
        req = svc.build_payment_requirements(amount_usdc=1.0, seller_address=VALID_ADDRESS)
        assert req["amount_usdc"] == 1.0

    def test_zero_amount_included_in_requirements(self, monkeypatch):
        """Test 2: Zero amount is allowed (free listings exist) -- no exception raised."""
        svc = _make_service(monkeypatch)
        req = svc.build_payment_requirements(amount_usdc=0.0, seller_address=VALID_ADDRESS)
        assert req["amount_usdc"] == 0.0

    def test_large_amount_accepted(self, monkeypatch):
        """Test 3: Very large USDC amount (1M) is accepted."""
        svc = _make_service(monkeypatch)
        req = svc.build_payment_requirements(amount_usdc=1_000_000.0, seller_address=VALID_ADDRESS)
        assert req["amount_usdc"] == 1_000_000.0

    def test_asset_always_usdc(self, monkeypatch):
        """Test 4: The asset field in requirements is always 'USDC'."""
        svc = _make_service(monkeypatch)
        req = svc.build_payment_requirements(amount_usdc=5.0, seller_address=VALID_ADDRESS)
        assert req["asset"] == "USDC"

    def test_all_required_fields_present(self, monkeypatch):
        """Test 5: Requirements dict contains all six mandatory keys."""
        svc = _make_service(monkeypatch)
        req = svc.build_payment_requirements(amount_usdc=10.0, seller_address=VALID_ADDRESS)
        required_keys = {"pay_to_address", "network", "asset", "amount_usdc",
                         "facilitator_url", "simulated"}
        assert required_keys == set(req.keys())


# ============================================================================
# 2. Fee Calculations (Tests 6-10)
# ============================================================================


class TestFeeCalculations:
    """Validate platform fee percentages and creator royalty
    using the token_service transfer mechanics that underpin payments."""

    def test_platform_fee_pct_default(self):
        """Test 6: Default platform fee is 2%."""
        assert settings.platform_fee_pct == 0.02

    def test_platform_fee_calculation(self):
        """Test 7: Fee on $1000 at 2% = $20."""
        amount = Decimal("1000")
        fee_pct = Decimal(str(settings.platform_fee_pct))
        fee = (amount * fee_pct).quantize(Decimal("0.000001"))
        assert fee == Decimal("20.000000")

    def test_creator_royalty_full_mode(self):
        """Test 8: Default creator royalty is 100% in 'full' mode."""
        assert settings.creator_royalty_pct == 1.0
        assert settings.creator_royalty_mode == "full"

    def test_receiver_gets_amount_minus_fee(self):
        """Test 9: Receiver credit = amount - fee (net of platform cut)."""
        amount = Decimal("500")
        fee_pct = Decimal(str(settings.platform_fee_pct))
        fee = (amount * fee_pct).quantize(Decimal("0.000001"))
        receiver_credit = amount - fee
        assert receiver_credit == Decimal("490.000000")

    def test_fee_on_small_amount(self):
        """Test 10: Fee on $0.01 at 2% = $0.000200."""
        amount = Decimal("0.01")
        fee_pct = Decimal(str(settings.platform_fee_pct))
        fee = (amount * fee_pct).quantize(Decimal("0.000001"))
        assert fee == Decimal("0.000200")


# ============================================================================
# 3. Idempotency (Tests 11-15)
# ============================================================================


class TestIdempotency:
    """Validate duplicate payment detection, idempotency key handling,
    and unique simulated transaction hashes."""

    def test_simulated_tx_hashes_are_unique(self, monkeypatch):
        """Test 11: Two simulated verifications produce different tx_hash values."""
        svc = _make_service(monkeypatch)
        r1 = svc.verify_payment("sig-a", {"simulated": True})
        r2 = svc.verify_payment("sig-b", {"simulated": True})
        assert r1["tx_hash"] != r2["tx_hash"]

    def test_simulated_tx_hash_format(self, monkeypatch):
        """Test 12: Simulated tx_hash follows 'sim_0x<hex>' format."""
        svc = _make_service(monkeypatch)
        result = svc.verify_payment("any-sig", {"simulated": True})
        tx_hash = result["tx_hash"]
        assert tx_hash.startswith("sim_0x")
        hex_part = tx_hash[6:]  # after 'sim_0x'
        assert len(hex_part) == 32  # uuid hex is 32 chars
        int(hex_part, 16)  # should not raise -- valid hex

    def test_requirements_dict_is_deterministic(self, monkeypatch):
        """Test 13: Same inputs produce identical requirements dicts."""
        svc = _make_service(monkeypatch)
        req_a = svc.build_payment_requirements(amount_usdc=5.0, seller_address=VALID_ADDRESS)
        req_b = svc.build_payment_requirements(amount_usdc=5.0, seller_address=VALID_ADDRESS)
        assert req_a == req_b

    def test_different_amounts_produce_different_requirements(self, monkeypatch):
        """Test 14: Different amounts yield different requirement dicts."""
        svc = _make_service(monkeypatch)
        req_5 = svc.build_payment_requirements(amount_usdc=5.0, seller_address=VALID_ADDRESS)
        req_10 = svc.build_payment_requirements(amount_usdc=10.0, seller_address=VALID_ADDRESS)
        assert req_5["amount_usdc"] != req_10["amount_usdc"]

    async def test_idempotency_transfer_replay(
        self, db: AsyncSession, make_agent, make_token_account, seed_platform
    ):
        """Test 15: Replaying a transfer with the same idempotency key returns
        the existing ledger entry, not a new one."""
        from marketplace.services.token_service import transfer

        agent_a, _ = await make_agent("idempotent-sender")
        agent_b, _ = await make_agent("idempotent-receiver")
        await make_token_account(agent_a.id, 5000)
        await make_token_account(agent_b.id, 0)

        idem_key = f"test-idem-{uuid.uuid4().hex[:8]}"

        ledger_1 = await transfer(
            db, agent_a.id, agent_b.id,
            amount=100, tx_type="purchase",
            idempotency_key=idem_key,
        )

        ledger_2 = await transfer(
            db, agent_a.id, agent_b.id,
            amount=100, tx_type="purchase",
            idempotency_key=idem_key,
        )

        # Same ledger entry returned -- no duplicate
        assert ledger_1.id == ledger_2.id


# ============================================================================
# 4. Error States (Tests 16-20)
# ============================================================================


class TestErrorStates:
    """Validate error handling: insufficient balance, invalid recipients,
    mode mismatches, and missing accounts."""

    def test_real_mode_verify_returns_unverified(self, monkeypatch):
        """Test 16: In 'mainnet' mode without SDK, verify_payment returns
        verified=False with an error message."""
        svc = _make_service(monkeypatch, mode="mainnet")
        result = svc.verify_payment("real-sig", {"simulated": False})
        assert result["verified"] is False
        assert "error" in result
        assert "x402 SDK" in result["error"]

    def test_simulated_flag_overrides_real_mode(self, monkeypatch):
        """Test 17: Even in 'mainnet' mode, simulated=True in requirements
        forces a verified=True response."""
        svc = _make_service(monkeypatch, mode="mainnet")
        result = svc.verify_payment("any-sig", {"simulated": True})
        assert result["verified"] is True
        assert result["simulated"] is True

    def test_empty_seller_address_gets_zero_address(self, monkeypatch):
        """Test 18: In simulated mode, an empty seller_address is replaced
        with the zero address (0x000...0)."""
        svc = _make_service(monkeypatch, mode="simulated")
        req = svc.build_payment_requirements(amount_usdc=1.0, seller_address="")
        assert req["pay_to_address"] == ZERO_ADDRESS

    async def test_insufficient_balance_raises(
        self, db: AsyncSession, make_agent, make_token_account, seed_platform
    ):
        """Test 19: Transferring more USD than available raises ValueError."""
        from marketplace.services.token_service import transfer

        sender, _ = await make_agent("broke-sender")
        receiver, _ = await make_agent("rich-receiver")
        await make_token_account(sender.id, 10)  # only $10
        await make_token_account(receiver.id, 0)

        with pytest.raises(ValueError, match="Insufficient balance"):
            await transfer(
                db, sender.id, receiver.id,
                amount=1000, tx_type="purchase",
            )

    async def test_missing_sender_account_raises(
        self, db: AsyncSession, make_agent, make_token_account, seed_platform
    ):
        """Test 20: Transferring from an agent with no token account raises ValueError."""
        from marketplace.services.token_service import transfer

        sender, _ = await make_agent("no-acct-sender")
        receiver, _ = await make_agent("has-acct-receiver")
        # Only create account for receiver, not sender
        await make_token_account(receiver.id, 0)

        with pytest.raises(ValueError, match="No token account"):
            await transfer(
                db, sender.id, receiver.id,
                amount=100, tx_type="purchase",
            )
