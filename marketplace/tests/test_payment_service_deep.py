"""Comprehensive tests for PaymentService — 20 tests covering simulated mode,
real mode, build_requirements, verify_payment, edge cases, and singleton.

All tests are synchronous (PaymentService is synchronous).
Uses monkeypatch for mode switching since PaymentService reads settings.payment_mode
in __init__, so a new instance must be created after patching.
"""

import pytest

from marketplace.config import Settings, settings
from marketplace.services.payment_service import PaymentService, payment_service


# ---------------------------------------------------------------------------
# 1. Simulated mode — build_payment_requirements sets simulated: True
# ---------------------------------------------------------------------------

class TestSimulatedModeBuildRequirements:
    """Tests for build_payment_requirements when mode == 'simulated'."""

    def test_simulated_flag_is_true(self, monkeypatch):
        """In simulated mode, the requirements dict must contain simulated: True."""
        monkeypatch.setattr(settings, "payment_mode", "simulated")
        svc = PaymentService()
        req = svc.build_payment_requirements(5.0, "0xABC123")
        assert req["simulated"] is True

    def test_zero_address_fallback_when_seller_is_none(self, monkeypatch):
        """When seller_address is None in simulated mode, pay_to_address falls
        back to the zero address '0x' + '0'*40."""
        monkeypatch.setattr(settings, "payment_mode", "simulated")
        svc = PaymentService()
        req = svc.build_payment_requirements(1.0, None)
        expected_zero = "0x" + "0" * 40
        assert req["pay_to_address"] == expected_zero

    def test_zero_address_fallback_when_seller_is_empty(self, monkeypatch):
        """When seller_address is '' (empty string) in simulated mode,
        pay_to_address falls back to the zero address."""
        monkeypatch.setattr(settings, "payment_mode", "simulated")
        svc = PaymentService()
        req = svc.build_payment_requirements(2.5, "")
        expected_zero = "0x" + "0" * 40
        assert req["pay_to_address"] == expected_zero


# ---------------------------------------------------------------------------
# 2. Real mode — build_payment_requirements sets simulated: False
# ---------------------------------------------------------------------------

class TestRealModeBuildRequirements:
    """Tests for build_payment_requirements when mode != 'simulated'."""

    def test_real_mode_simulated_flag_is_false(self, monkeypatch):
        """In real mode (e.g. 'testnet'), requirements must have simulated: False."""
        monkeypatch.setattr(settings, "payment_mode", "testnet")
        svc = PaymentService()
        req = svc.build_payment_requirements(10.0, "0xSELLER")
        assert req["simulated"] is False

    def test_real_mode_preserves_seller_address(self, monkeypatch):
        """In real mode, seller_address is passed through as-is (no fallback)."""
        monkeypatch.setattr(settings, "payment_mode", "mainnet")
        svc = PaymentService()
        addr = "0xRealSellerAddress1234567890abcdef12345678"
        req = svc.build_payment_requirements(7.5, addr)
        assert req["pay_to_address"] == addr


# ---------------------------------------------------------------------------
# 3. build_payment_requirements — field correctness
# ---------------------------------------------------------------------------

class TestBuildRequirementsFields:
    """Verify that amount, network, asset, and facilitator_url are correct."""

    def test_amount_matches_input(self, monkeypatch):
        """amount_usdc in requirements must exactly match the input value."""
        monkeypatch.setattr(settings, "payment_mode", "simulated")
        svc = PaymentService()
        req = svc.build_payment_requirements(42.99, "0xABC")
        assert req["amount_usdc"] == 42.99

    def test_network_from_settings(self, monkeypatch):
        """network must come from settings.x402_network."""
        monkeypatch.setattr(settings, "payment_mode", "simulated")
        monkeypatch.setattr(settings, "x402_network", "base-mainnet")
        svc = PaymentService()
        req = svc.build_payment_requirements(1.0, "0xABC")
        assert req["network"] == "base-mainnet"

    def test_asset_is_usdc(self, monkeypatch):
        """asset must always be 'USDC'."""
        monkeypatch.setattr(settings, "payment_mode", "simulated")
        svc = PaymentService()
        req = svc.build_payment_requirements(1.0, "0xABC")
        assert req["asset"] == "USDC"

    def test_facilitator_url_from_settings(self, monkeypatch):
        """facilitator_url must come from settings.x402_facilitator_url."""
        monkeypatch.setattr(settings, "payment_mode", "simulated")
        monkeypatch.setattr(settings, "x402_facilitator_url", "https://custom.facilitator/v2")
        svc = PaymentService()
        req = svc.build_payment_requirements(1.0, "0xABC")
        assert req["facilitator_url"] == "https://custom.facilitator/v2"


# ---------------------------------------------------------------------------
# 4. verify_payment — simulated mode
# ---------------------------------------------------------------------------

class TestVerifyPaymentSimulated:
    """Tests for verify_payment when running in simulated mode."""

    def test_simulated_returns_verified_true(self, monkeypatch):
        """In simulated mode, verify_payment always returns verified: True."""
        monkeypatch.setattr(settings, "payment_mode", "simulated")
        svc = PaymentService()
        result = svc.verify_payment("any_sig", {"simulated": True})
        assert result["verified"] is True

    def test_simulated_tx_hash_prefix(self, monkeypatch):
        """The tx_hash in simulated verification starts with 'sim_0x'."""
        monkeypatch.setattr(settings, "payment_mode", "simulated")
        svc = PaymentService()
        result = svc.verify_payment("sig", {"simulated": True})
        assert result["tx_hash"].startswith("sim_0x")

    def test_simulated_response_has_simulated_true(self, monkeypatch):
        """The verify_payment response in simulated mode contains simulated: True."""
        monkeypatch.setattr(settings, "payment_mode", "simulated")
        svc = PaymentService()
        result = svc.verify_payment("sig", {})
        assert result["simulated"] is True

    def test_simulated_unique_tx_hashes(self, monkeypatch):
        """Each call to verify_payment in simulated mode must produce a unique tx_hash."""
        monkeypatch.setattr(settings, "payment_mode", "simulated")
        svc = PaymentService()
        hashes = {svc.verify_payment("sig", {})["tx_hash"] for _ in range(50)}
        assert len(hashes) == 50, "Expected 50 unique tx_hashes, got duplicates"


# ---------------------------------------------------------------------------
# 5. verify_payment — real mode
# ---------------------------------------------------------------------------

class TestVerifyPaymentReal:
    """Tests for verify_payment when mode is not simulated."""

    def test_real_mode_returns_verified_false(self, monkeypatch):
        """In real mode (no SDK), verify_payment returns verified: False."""
        monkeypatch.setattr(settings, "payment_mode", "testnet")
        svc = PaymentService()
        result = svc.verify_payment("real_sig", {"simulated": False})
        assert result["verified"] is False

    def test_real_mode_has_error_message(self, monkeypatch):
        """In real mode, the response includes an error message about the SDK."""
        monkeypatch.setattr(settings, "payment_mode", "mainnet")
        svc = PaymentService()
        result = svc.verify_payment("real_sig", {"simulated": False})
        assert "error" in result
        assert "x402 SDK" in result["error"]


# ---------------------------------------------------------------------------
# 6. verify_payment — simulated flag in requirements overrides mode
# ---------------------------------------------------------------------------

class TestVerifyPaymentSimulatedFlagOverride:
    """When requirements dict contains simulated: True, it overrides real mode."""

    def test_requirements_simulated_flag_overrides_real_mode(self, monkeypatch):
        """Even in real mode, if requirements['simulated'] is True, verification
        succeeds as simulated."""
        monkeypatch.setattr(settings, "payment_mode", "mainnet")
        svc = PaymentService()
        result = svc.verify_payment("any_sig", {"simulated": True})
        assert result["verified"] is True
        assert result["simulated"] is True
        assert result["tx_hash"].startswith("sim_0x")


# ---------------------------------------------------------------------------
# 7. Edge cases — zero and fractional amounts
# ---------------------------------------------------------------------------

class TestEdgeCaseAmounts:
    """Zero amount and fractional precision amounts."""

    def test_zero_amount(self, monkeypatch):
        """build_payment_requirements accepts 0.0 as amount without error."""
        monkeypatch.setattr(settings, "payment_mode", "simulated")
        svc = PaymentService()
        req = svc.build_payment_requirements(0.0, "0xABC")
        assert req["amount_usdc"] == 0.0

    def test_fractional_precision_amount(self, monkeypatch):
        """build_payment_requirements preserves high-precision fractional amounts."""
        monkeypatch.setattr(settings, "payment_mode", "simulated")
        svc = PaymentService()
        amount = 0.000001
        req = svc.build_payment_requirements(amount, "0xABC")
        assert req["amount_usdc"] == amount


# ---------------------------------------------------------------------------
# 8. Default mode and singleton
# ---------------------------------------------------------------------------

class TestDefaultsAndSingleton:
    """Default mode is 'simulated'; module-level singleton exists."""

    def test_default_mode_is_simulated(self):
        """Settings.payment_mode defaults to 'simulated', so a fresh service
        should pick that up (unless env overrides it)."""
        # We test against the default in the Settings class itself
        defaults = Settings()
        assert defaults.payment_mode == "simulated"

    def test_singleton_instance_exists(self):
        """The module exposes a pre-built payment_service singleton."""
        assert payment_service is not None
        assert isinstance(payment_service, PaymentService)

