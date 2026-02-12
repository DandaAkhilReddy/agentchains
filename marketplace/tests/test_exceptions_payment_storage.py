"""Tests for custom exceptions, PaymentService, and HashFS storage.

Covers:
- 11 tests for marketplace.core.exceptions (all 8 custom HTTPException subclasses)
- 8 tests for marketplace.services.payment_service (PaymentService)
- 11 tests for marketplace.storage.hashfs (HashFS content-addressed storage)

Total: 30 tests
"""

import os
import shutil
import tempfile
import uuid

import pytest
from fastapi import HTTPException

from marketplace.core.exceptions import (
    AgentAlreadyExistsError,
    AgentNotFoundError,
    ContentVerificationError,
    InvalidTransactionStateError,
    ListingNotFoundError,
    PaymentRequiredError,
    TransactionNotFoundError,
    UnauthorizedError,
)
from marketplace.storage.hashfs import HashFS


# ============================================================================
# Exception Tests (11)
# ============================================================================


class TestAgentNotFoundError:
    def test_status_404_and_detail_contains_agent_id(self):
        agent_id = "agent-abc-123"
        err = AgentNotFoundError(agent_id)
        assert err.status_code == 404
        assert agent_id in err.detail


class TestAgentAlreadyExistsError:
    def test_status_code_is_409(self):
        err = AgentAlreadyExistsError("my-agent")
        assert err.status_code == 409


class TestListingNotFoundError:
    def test_status_code_is_404(self):
        err = ListingNotFoundError("listing-xyz")
        assert err.status_code == 404


class TestTransactionNotFoundError:
    def test_status_code_is_404(self):
        err = TransactionNotFoundError("tx-999")
        assert err.status_code == 404


class TestInvalidTransactionStateError:
    def test_status_400_and_detail_contains_both_states(self):
        err = InvalidTransactionStateError(current="pending", expected="completed")
        assert err.status_code == 400
        assert "pending" in err.detail
        assert "completed" in err.detail


class TestPaymentRequiredError:
    def test_status_code_is_402(self):
        details = {"amount": 10.0, "currency": "USDC"}
        err = PaymentRequiredError(details)
        assert err.status_code == 402

    def test_detail_is_dict(self):
        details = {"amount": 10.0, "currency": "USDC"}
        err = PaymentRequiredError(details)
        assert isinstance(err.detail, dict)
        assert err.detail == details


class TestUnauthorizedError:
    def test_status_401_with_default_detail(self):
        err = UnauthorizedError()
        assert err.status_code == 401
        assert err.detail == "Invalid or missing authentication"

    def test_status_401_with_custom_detail(self):
        err = UnauthorizedError(detail="Token expired")
        assert err.status_code == 401
        assert err.detail == "Token expired"


class TestContentVerificationError:
    def test_status_code_is_400(self):
        err = ContentVerificationError()
        assert err.status_code == 400


class TestExceptionInheritance:
    def test_all_exceptions_inherit_from_http_exception(self):
        exceptions = [
            AgentNotFoundError("id"),
            AgentAlreadyExistsError("name"),
            ListingNotFoundError("id"),
            TransactionNotFoundError("id"),
            InvalidTransactionStateError("a", "b"),
            PaymentRequiredError({}),
            UnauthorizedError(),
            ContentVerificationError(),
        ]
        for exc in exceptions:
            assert isinstance(exc, HTTPException), (
                f"{type(exc).__name__} does not inherit from HTTPException"
            )


# ============================================================================
# PaymentService Tests (8)
# ============================================================================


class TestPaymentService:
    """Test PaymentService behaviour.

    We import and construct PaymentService directly, monkeypatching
    `marketplace.config.settings` attributes to control mode/network.
    """

    def _make_service(self, monkeypatch, mode="simulated", network="base-sepolia",
                      facilitator_url="https://x402.org/facilitator"):
        """Helper: patch settings then construct a fresh PaymentService."""
        from marketplace.config import settings as _settings
        monkeypatch.setattr(_settings, "payment_mode", mode)
        monkeypatch.setattr(_settings, "x402_network", network)
        monkeypatch.setattr(_settings, "x402_facilitator_url", facilitator_url)

        from marketplace.services.payment_service import PaymentService
        return PaymentService()

    # -- mode --

    def test_simulated_mode_from_settings(self, monkeypatch):
        svc = self._make_service(monkeypatch, mode="simulated")
        assert svc.mode == "simulated"

    # -- build_payment_requirements --

    def test_build_payment_requirements_simulated_flag_and_fallback_address(self, monkeypatch):
        svc = self._make_service(monkeypatch, mode="simulated")
        req = svc.build_payment_requirements(amount_usdc=5.0, seller_address="")
        assert req["simulated"] is True
        assert req["pay_to_address"] == "0x" + "0" * 40

    def test_build_payment_requirements_with_real_address(self, monkeypatch):
        svc = self._make_service(monkeypatch, mode="simulated")
        addr = "0xAbCdEf1234567890AbCdEf1234567890AbCdEf12"
        req = svc.build_payment_requirements(amount_usdc=2.5, seller_address=addr)
        assert req["pay_to_address"] == addr
        assert req["amount_usdc"] == 2.5

    def test_build_payment_requirements_includes_network(self, monkeypatch):
        svc = self._make_service(monkeypatch, network="base-mainnet")
        req = svc.build_payment_requirements(amount_usdc=1.0, seller_address="0xABC")
        assert req["network"] == "base-mainnet"

    # -- verify_payment --

    def test_verify_payment_simulated_returns_verified(self, monkeypatch):
        svc = self._make_service(monkeypatch, mode="simulated")
        result = svc.verify_payment("fake-sig", {"simulated": True})
        assert result["verified"] is True
        assert result["tx_hash"].startswith("sim_0x")

    def test_verify_payment_real_mode_returns_unverified(self, monkeypatch):
        svc = self._make_service(monkeypatch, mode="mainnet")
        result = svc.verify_payment("real-sig", {"simulated": False})
        assert result["verified"] is False
        assert "error" in result

    def test_verify_payment_simulated_from_requirements_overrides(self, monkeypatch):
        """Even if service mode is 'mainnet', simulated=True in requirements
        should make verify_payment return a simulated success."""
        svc = self._make_service(monkeypatch, mode="mainnet")
        result = svc.verify_payment("any-sig", {"simulated": True})
        assert result["verified"] is True
        assert result["simulated"] is True

    def test_verify_payment_simulated_tx_hash_is_unique(self, monkeypatch):
        svc = self._make_service(monkeypatch, mode="simulated")
        r1 = svc.verify_payment("sig1", {})
        r2 = svc.verify_payment("sig2", {})
        assert r1["tx_hash"] != r2["tx_hash"]


# ============================================================================
# HashFS Storage Tests (11)
# ============================================================================


class TestHashFS:
    """Test the content-addressed file storage (HashFS).

    All tests use a fresh temporary directory created via tempfile.mkdtemp
    so they are fully isolated and leave no artifacts on disk.
    """

    @pytest.fixture
    def storage(self):
        root = tempfile.mkdtemp()
        store_path = os.path.join(root, "store")
        yield HashFS(store_path)
        shutil.rmtree(root, ignore_errors=True)

    # -- put / get --

    def test_put_returns_sha256_prefixed_hash(self, storage):
        content = b"hello world"
        h = storage.put(content)
        assert h.startswith("sha256:")
        # hex hash should be 64 chars
        hex_part = h.replace("sha256:", "")
        assert len(hex_part) == 64

    def test_put_then_get_returns_identical_bytes(self, storage):
        content = b"some binary \x00\x01\x02 data"
        h = storage.put(content)
        retrieved = storage.get(h)
        assert retrieved == content

    def test_get_missing_hash_returns_none(self, storage):
        fake_hash = "sha256:" + "ab" * 32
        assert storage.get(fake_hash) is None

    # -- exists --

    def test_exists_after_put_returns_true(self, storage):
        h = storage.put(b"exists-check")
        assert storage.exists(h) is True

    def test_exists_before_put_returns_false(self, storage):
        fake_hash = "sha256:" + "cd" * 32
        assert storage.exists(fake_hash) is False

    # -- delete --

    def test_delete_existing_returns_true_and_content_gone(self, storage):
        h = storage.put(b"delete-me")
        assert storage.delete(h) is True
        assert storage.get(h) is None
        assert storage.exists(h) is False

    def test_delete_missing_returns_false(self, storage):
        fake_hash = "sha256:" + "ef" * 32
        assert storage.delete(fake_hash) is False

    # -- verify --

    def test_verify_matching_content_returns_true(self, storage):
        content = b"verify this"
        h = storage.put(content)
        assert storage.verify(content, h) is True

    def test_verify_mismatched_content_returns_false(self, storage):
        content = b"original"
        h = storage.put(content)
        assert storage.verify(b"tampered", h) is False

    # -- compute_hash --

    def test_compute_hash_without_storing(self, storage):
        content = b"no storage"
        h = storage.compute_hash(content)
        assert h.startswith("sha256:")
        # The content should NOT be stored
        assert storage.exists(h) is False
        # But if we put the same content, hash must match
        stored_h = storage.put(content)
        assert h == stored_h

    # -- size --

    def test_size_counts_files_correctly(self, storage):
        assert storage.size() == 0
        storage.put(b"file-one")
        assert storage.size() == 1
        storage.put(b"file-two")
        assert storage.size() == 2
        # Putting duplicate content should NOT increase count
        storage.put(b"file-one")
        assert storage.size() == 2
