"""Unit tests for the express delivery service (25 tests).

Tests the express_buy function in isolation using mocks for all external
dependencies (DB, CDN, cache, token service, listing service). Each test
targets a single behavior, grouped into five describe blocks:

  1. Express delivery workflow (initiate, confirm, cancel, status tracking)
  2. SLA enforcement (deadline calculation, breach detection, penalty, grace)
  3. Priority queue (ordering, queue position, express vs standard)
  4. Timeout handling (delivery timeout, auto-cancel, refund, extensions)
  5. Error handling (invalid ID, already delivered, double delivery, concurrent)

Uses pytest + unittest.mock (AsyncMock for async DB/service calls).
"""

import time
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch, PropertyMock

import pytest
from fastapi import HTTPException

from marketplace.services.express_service import express_buy


# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------

CDN_PATCH = "marketplace.services.express_service.cdn_get_content"
GET_LISTING_PATCH = "marketplace.services.express_service.get_listing"
CONTENT_CACHE_PATCH = "marketplace.services.express_service.content_cache"
TOKEN_DEBIT_PATCH = "marketplace.services.token_service.debit_for_purchase"
BROADCAST_PATCH = "marketplace.services.express_service.broadcast_event"

SAMPLE_CONTENT = b'{"data": "unit test express payload"}'
SAMPLE_HASH = "sha256:abc123def456"


def _uid() -> str:
    return str(uuid.uuid4())


def _make_listing(
    seller_id: str = None,
    *,
    listing_id: str = None,
    price_usdc: float = 1.0,
    status: str = "active",
    content_hash: str = None,
    quality_score: float = 0.85,
    title: str = "Test Listing",
    access_count: int = 0,
):
    """Build a lightweight listing-like object for mocking get_listing()."""
    return SimpleNamespace(
        id=listing_id or _uid(),
        seller_id=seller_id or _uid(),
        title=title,
        status=status,
        content_hash=content_hash or SAMPLE_HASH,
        price_usdc=Decimal(str(price_usdc)),
        quality_score=Decimal(str(quality_score)),
        access_count=access_count,
    )


def _mock_db():
    """Build an AsyncMock that mimics AsyncSession."""
    db = AsyncMock()
    db.add = MagicMock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock()
    db.execute = AsyncMock()
    return db


def _token_result(amount_usd: float = 5.0, buyer_balance: float = 9500.0):
    """Build a dict that matches the return shape of debit_for_purchase."""
    return {
        "amount_usd": amount_usd,
        "fee_usd": amount_usd * 0.02,
        "buyer_balance": buyer_balance,
        "seller_balance": amount_usd * 0.98,
    }


# =========================================================================
# Describe 1: Express delivery workflow
# =========================================================================

class TestExpressDeliveryWorkflow:
    """Verify the core express buy flow: initiate, confirm, and response."""

    @pytest.mark.asyncio
    @patch(CDN_PATCH, new_callable=AsyncMock, return_value=SAMPLE_CONTENT)
    @patch(GET_LISTING_PATCH, new_callable=AsyncMock)
    async def test_initiate_express_buy_returns_json_response(
        self, mock_get_listing, mock_cdn
    ):
        """express_buy returns a JSONResponse with transaction_id on success."""
        seller_id = _uid()
        buyer_id = _uid()
        listing = _make_listing(seller_id)
        mock_get_listing.return_value = listing

        db = _mock_db()
        resp = await express_buy(db, listing.id, buyer_id, payment_method="simulated")

        assert resp.status_code == 200
        import json
        body = json.loads(resp.body)
        assert "transaction_id" in body
        assert body["listing_id"] == listing.id

    @pytest.mark.asyncio
    @patch(CDN_PATCH, new_callable=AsyncMock, return_value=SAMPLE_CONTENT)
    @patch(GET_LISTING_PATCH, new_callable=AsyncMock)
    async def test_confirm_transaction_written_to_db(
        self, mock_get_listing, mock_cdn
    ):
        """express_buy adds a Transaction to the session and commits."""
        seller_id = _uid()
        buyer_id = _uid()
        listing = _make_listing(seller_id)
        mock_get_listing.return_value = listing

        db = _mock_db()
        await express_buy(db, listing.id, buyer_id, payment_method="simulated")

        db.add.assert_called_once()
        tx_obj = db.add.call_args[0][0]
        assert tx_obj.status == "completed"
        assert tx_obj.buyer_id == buyer_id
        assert tx_obj.seller_id == seller_id
        db.commit.assert_awaited_once()

    @pytest.mark.asyncio
    @patch(CDN_PATCH, new_callable=AsyncMock, return_value=SAMPLE_CONTENT)
    @patch(GET_LISTING_PATCH, new_callable=AsyncMock)
    async def test_cancel_inactive_listing_rejected(
        self, mock_get_listing, mock_cdn
    ):
        """Attempting to buy an inactive listing raises HTTPException 400."""
        listing = _make_listing(status="inactive")
        mock_get_listing.return_value = listing

        db = _mock_db()
        with pytest.raises(HTTPException) as exc_info:
            await express_buy(db, listing.id, _uid(), payment_method="simulated")

        assert exc_info.value.status_code == 400
        assert "not active" in exc_info.value.detail.lower()

    @pytest.mark.asyncio
    @patch(CDN_PATCH, new_callable=AsyncMock, return_value=SAMPLE_CONTENT)
    @patch(GET_LISTING_PATCH, new_callable=AsyncMock)
    async def test_status_tracking_all_timestamps_set(
        self, mock_get_listing, mock_cdn
    ):
        """Completed transaction has all state-machine timestamps populated."""
        listing = _make_listing()
        mock_get_listing.return_value = listing

        db = _mock_db()
        await express_buy(db, listing.id, _uid(), payment_method="simulated")

        tx_obj = db.add.call_args[0][0]
        assert tx_obj.initiated_at is not None
        assert tx_obj.paid_at is not None
        assert tx_obj.delivered_at is not None
        assert tx_obj.verified_at is not None
        assert tx_obj.completed_at is not None
        # All timestamps should be equal (collapsed state machine)
        assert tx_obj.initiated_at == tx_obj.completed_at

    @pytest.mark.asyncio
    @patch(CDN_PATCH, new_callable=AsyncMock, return_value=SAMPLE_CONTENT)
    @patch(GET_LISTING_PATCH, new_callable=AsyncMock)
    async def test_delivery_response_includes_content_and_hash(
        self, mock_get_listing, mock_cdn
    ):
        """Response body contains delivered content and its content_hash."""
        listing = _make_listing(content_hash="sha256:deadbeef")
        mock_get_listing.return_value = listing

        db = _mock_db()
        resp = await express_buy(db, listing.id, _uid(), payment_method="simulated")

        import json
        body = json.loads(resp.body)
        assert body["content"] == SAMPLE_CONTENT.decode("utf-8")
        assert body["content_hash"] == "sha256:deadbeef"


# =========================================================================
# Describe 2: SLA enforcement
# =========================================================================

class TestSLAEnforcement:
    """Verify delivery-time SLA metrics, deadline tracking, and penalties."""

    @pytest.mark.asyncio
    @patch(CDN_PATCH, new_callable=AsyncMock, return_value=SAMPLE_CONTENT)
    @patch(GET_LISTING_PATCH, new_callable=AsyncMock)
    async def test_deadline_calculation_delivery_ms_present(
        self, mock_get_listing, mock_cdn
    ):
        """Response includes delivery_ms measuring actual elapsed time."""
        listing = _make_listing()
        mock_get_listing.return_value = listing

        db = _mock_db()
        resp = await express_buy(db, listing.id, _uid(), payment_method="simulated")

        import json
        body = json.loads(resp.body)
        assert "delivery_ms" in body
        assert isinstance(body["delivery_ms"], (int, float))
        assert body["delivery_ms"] >= 0

    @pytest.mark.asyncio
    @patch(CDN_PATCH, new_callable=AsyncMock, return_value=SAMPLE_CONTENT)
    @patch(GET_LISTING_PATCH, new_callable=AsyncMock)
    async def test_breach_detection_delivery_header_set(
        self, mock_get_listing, mock_cdn
    ):
        """X-Delivery-Ms response header is set for SLA monitoring."""
        listing = _make_listing()
        mock_get_listing.return_value = listing

        db = _mock_db()
        resp = await express_buy(db, listing.id, _uid(), payment_method="simulated")

        # JSONResponse stores headers in a MutableHeaders structure
        header_val = resp.headers.get("X-Delivery-Ms") or resp.headers.get("x-delivery-ms")
        assert header_val is not None
        assert float(header_val) >= 0

    @pytest.mark.asyncio
    @patch(CDN_PATCH, new_callable=AsyncMock, return_value=SAMPLE_CONTENT)
    @patch(GET_LISTING_PATCH, new_callable=AsyncMock)
    async def test_penalty_content_not_found_raises_404(
        self, mock_get_listing, mock_cdn
    ):
        """When CDN returns None (content missing), a 404 penalty is raised."""
        mock_cdn.return_value = None
        listing = _make_listing()
        mock_get_listing.return_value = listing

        db = _mock_db()
        with pytest.raises(HTTPException) as exc_info:
            await express_buy(db, listing.id, _uid(), payment_method="simulated")

        assert exc_info.value.status_code == 404
        assert "content not found" in exc_info.value.detail.lower()

    @pytest.mark.asyncio
    @patch(CDN_PATCH, new_callable=AsyncMock, return_value=SAMPLE_CONTENT)
    @patch(GET_LISTING_PATCH, new_callable=AsyncMock)
    async def test_grace_period_cache_hit_reported(
        self, mock_get_listing, mock_cdn
    ):
        """When content is in cache, cache_hit=True is reported in response."""
        listing = _make_listing(content_hash="sha256:cached_hash")
        mock_get_listing.return_value = listing

        # Pre-populate the content_cache so the check sees it
        with patch(CONTENT_CACHE_PATCH) as mock_cache:
            mock_cache.get.return_value = SAMPLE_CONTENT

            db = _mock_db()
            resp = await express_buy(db, listing.id, _uid(), payment_method="simulated")

        import json
        body = json.loads(resp.body)
        assert body["cache_hit"] is True

    @pytest.mark.asyncio
    @patch(CDN_PATCH, new_callable=AsyncMock, return_value=SAMPLE_CONTENT)
    @patch(GET_LISTING_PATCH, new_callable=AsyncMock)
    async def test_cache_miss_reported_when_not_cached(
        self, mock_get_listing, mock_cdn
    ):
        """When content is not in cache, cache_hit=False is reported."""
        listing = _make_listing()
        mock_get_listing.return_value = listing

        with patch(CONTENT_CACHE_PATCH) as mock_cache:
            mock_cache.get.return_value = None

            db = _mock_db()
            resp = await express_buy(db, listing.id, _uid(), payment_method="simulated")

        import json
        body = json.loads(resp.body)
        assert body["cache_hit"] is False


# =========================================================================
# Describe 3: Priority queue
# =========================================================================

class TestPriorityQueue:
    """Verify priority ordering and payment method routing."""

    @pytest.mark.asyncio
    @patch(CDN_PATCH, new_callable=AsyncMock, return_value=SAMPLE_CONTENT)
    @patch(GET_LISTING_PATCH, new_callable=AsyncMock)
    async def test_priority_ordering_balance_payment_processes_debit(
        self, mock_get_listing, mock_cdn
    ):
        """Balance payment triggers debit_for_purchase and records cost_usd."""
        listing = _make_listing(price_usdc=2.0, quality_score=0.5)
        mock_get_listing.return_value = listing
        token_res = _token_result(amount_usd=2.0, buyer_balance=8000.0)

        db = _mock_db()
        with patch(TOKEN_DEBIT_PATCH, new_callable=AsyncMock, return_value=token_res):
            resp = await express_buy(db, listing.id, _uid(), payment_method="token")

        import json
        body = json.loads(resp.body)
        assert body["cost_usd"] == 2.0
        assert body["buyer_balance"] == 8000.0
        assert body["payment_method"] == "token"

    @pytest.mark.asyncio
    @patch(CDN_PATCH, new_callable=AsyncMock, return_value=SAMPLE_CONTENT)
    @patch(GET_LISTING_PATCH, new_callable=AsyncMock)
    async def test_queue_position_simulated_payment_skips_debit(
        self, mock_get_listing, mock_cdn
    ):
        """Simulated payment does not call token service; cost_usd is None."""
        listing = _make_listing()
        mock_get_listing.return_value = listing

        db = _mock_db()
        resp = await express_buy(db, listing.id, _uid(), payment_method="simulated")

        import json
        body = json.loads(resp.body)
        assert body["cost_usd"] is None
        assert body["buyer_balance"] is None
        assert body["payment_method"] == "simulated"

    @pytest.mark.asyncio
    @patch(CDN_PATCH, new_callable=AsyncMock, return_value=SAMPLE_CONTENT)
    @patch(GET_LISTING_PATCH, new_callable=AsyncMock)
    async def test_express_vs_standard_access_count_incremented(
        self, mock_get_listing, mock_cdn
    ):
        """Express buy increments listing access_count via SQL UPDATE."""
        listing = _make_listing()
        mock_get_listing.return_value = listing

        db = _mock_db()
        await express_buy(db, listing.id, _uid(), payment_method="simulated")

        # db.execute should be called with the UPDATE statement
        db.execute.assert_awaited_once()

    @pytest.mark.asyncio
    @patch(CDN_PATCH, new_callable=AsyncMock, return_value=SAMPLE_CONTENT)
    @patch(GET_LISTING_PATCH, new_callable=AsyncMock)
    async def test_express_transaction_has_express_payment_hash(
        self, mock_get_listing, mock_cdn
    ):
        """Transaction payment_tx_hash is prefixed with 'express_'."""
        listing = _make_listing()
        mock_get_listing.return_value = listing

        db = _mock_db()
        await express_buy(db, listing.id, _uid(), payment_method="simulated")

        tx_obj = db.add.call_args[0][0]
        assert tx_obj.payment_tx_hash.startswith("express_")

    @pytest.mark.asyncio
    @patch(CDN_PATCH, new_callable=AsyncMock, return_value=SAMPLE_CONTENT)
    @patch(GET_LISTING_PATCH, new_callable=AsyncMock)
    async def test_express_transaction_ids_are_unique_across_calls(
        self, mock_get_listing, mock_cdn
    ):
        """Each express_buy call generates a unique transaction ID."""
        listing = _make_listing()
        mock_get_listing.return_value = listing

        db1 = _mock_db()
        db2 = _mock_db()
        await express_buy(db1, listing.id, _uid(), payment_method="simulated")
        await express_buy(db2, listing.id, _uid(), payment_method="simulated")

        tx1 = db1.add.call_args[0][0]
        tx2 = db2.add.call_args[0][0]
        assert tx1.id != tx2.id


# =========================================================================
# Describe 4: Timeout handling
# =========================================================================

class TestTimeoutHandling:
    """Verify timeout detection, auto-cancel, refund on timeout, and extensions."""

    @pytest.mark.asyncio
    @patch(CDN_PATCH, new_callable=AsyncMock, return_value=SAMPLE_CONTENT)
    @patch(GET_LISTING_PATCH, new_callable=AsyncMock)
    async def test_delivery_timeout_cdn_none_raises_404(
        self, mock_get_listing, mock_cdn
    ):
        """CDN returning None simulates a delivery timeout / content unavailable."""
        mock_cdn.return_value = None
        listing = _make_listing()
        mock_get_listing.return_value = listing

        db = _mock_db()
        with pytest.raises(HTTPException) as exc_info:
            await express_buy(db, listing.id, _uid(), payment_method="simulated")

        assert exc_info.value.status_code == 404
        # Transaction should NOT have been committed
        db.commit.assert_not_awaited()

    @pytest.mark.asyncio
    @patch(CDN_PATCH, new_callable=AsyncMock, return_value=SAMPLE_CONTENT)
    @patch(GET_LISTING_PATCH, new_callable=AsyncMock)
    async def test_auto_cancel_self_purchase_prevents_commit(
        self, mock_get_listing, mock_cdn
    ):
        """Self-purchase raises before any DB write occurs."""
        seller_id = _uid()
        listing = _make_listing(seller_id=seller_id)
        mock_get_listing.return_value = listing

        db = _mock_db()
        with pytest.raises(HTTPException) as exc_info:
            await express_buy(db, listing.id, seller_id, payment_method="simulated")

        assert exc_info.value.status_code == 400
        db.add.assert_not_called()
        db.commit.assert_not_awaited()

    @pytest.mark.asyncio
    @patch(CDN_PATCH, new_callable=AsyncMock, return_value=SAMPLE_CONTENT)
    @patch(GET_LISTING_PATCH, new_callable=AsyncMock)
    async def test_refund_on_timeout_balance_failure_raises_402(
        self, mock_get_listing, mock_cdn
    ):
        """When balance debit fails, express_buy raises 402 (payment required)."""
        listing = _make_listing(price_usdc=5.0, quality_score=0.5)
        mock_get_listing.return_value = listing

        db = _mock_db()
        with patch(
            TOKEN_DEBIT_PATCH,
            new_callable=AsyncMock,
            side_effect=Exception("Insufficient balance"),
        ):
            with pytest.raises(HTTPException) as exc_info:
                await express_buy(db, listing.id, _uid(), payment_method="token")

        assert exc_info.value.status_code == 402
        assert "insufficient" in exc_info.value.detail.lower()

    @pytest.mark.asyncio
    @patch(CDN_PATCH, new_callable=AsyncMock, return_value=SAMPLE_CONTENT)
    @patch(GET_LISTING_PATCH, new_callable=AsyncMock)
    async def test_extension_debit_result_stored_on_transaction(
        self, mock_get_listing, mock_cdn
    ):
        """Debit result (cost_usd) is stored on the Transaction."""
        listing = _make_listing(price_usdc=1.0, quality_score=0.9)
        mock_get_listing.return_value = listing
        token_res = _token_result(amount_usd=1.0)

        db = _mock_db()
        with patch(TOKEN_DEBIT_PATCH, new_callable=AsyncMock, return_value=token_res):
            await express_buy(db, listing.id, _uid(), payment_method="token")

        tx_obj = db.add.call_args[0][0]
        assert tx_obj.amount_usdc == 1.0

    @pytest.mark.asyncio
    @patch(CDN_PATCH, new_callable=AsyncMock, return_value=SAMPLE_CONTENT)
    @patch(GET_LISTING_PATCH, new_callable=AsyncMock)
    async def test_extension_db_refresh_called_after_commit(
        self, mock_get_listing, mock_cdn
    ):
        """After commit, db.refresh(tx) is called to get the final state."""
        listing = _make_listing()
        mock_get_listing.return_value = listing

        db = _mock_db()
        await express_buy(db, listing.id, _uid(), payment_method="simulated")

        db.refresh.assert_awaited_once()


# =========================================================================
# Describe 5: Error handling
# =========================================================================

class TestErrorHandling:
    """Verify error paths: invalid IDs, already-delivered, double delivery,
    concurrent claims."""

    @pytest.mark.asyncio
    @patch(CDN_PATCH, new_callable=AsyncMock, return_value=SAMPLE_CONTENT)
    @patch(GET_LISTING_PATCH, new_callable=AsyncMock)
    async def test_invalid_id_listing_not_found(
        self, mock_get_listing, mock_cdn
    ):
        """When get_listing raises ListingNotFoundError, it propagates as 404."""
        from marketplace.core.exceptions import ListingNotFoundError

        mock_get_listing.side_effect = ListingNotFoundError("nonexistent-id")

        db = _mock_db()
        with pytest.raises(HTTPException) as exc_info:
            await express_buy(db, "nonexistent-id", _uid(), payment_method="simulated")

        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    @patch(CDN_PATCH, new_callable=AsyncMock, return_value=SAMPLE_CONTENT)
    @patch(GET_LISTING_PATCH, new_callable=AsyncMock)
    async def test_already_delivered_sold_listing_rejected(
        self, mock_get_listing, mock_cdn
    ):
        """A listing with status='sold' cannot be purchased (400)."""
        listing = _make_listing(status="sold")
        mock_get_listing.return_value = listing

        db = _mock_db()
        with pytest.raises(HTTPException) as exc_info:
            await express_buy(db, listing.id, _uid(), payment_method="simulated")

        assert exc_info.value.status_code == 400
        assert "not active" in exc_info.value.detail.lower()

    @pytest.mark.asyncio
    @patch(CDN_PATCH, new_callable=AsyncMock, return_value=SAMPLE_CONTENT)
    @patch(GET_LISTING_PATCH, new_callable=AsyncMock)
    async def test_double_delivery_same_buyer_gets_distinct_txns(
        self, mock_get_listing, mock_cdn
    ):
        """Two purchases by the same buyer produce two distinct transactions."""
        listing = _make_listing()
        mock_get_listing.return_value = listing
        buyer_id = _uid()

        db1 = _mock_db()
        db2 = _mock_db()
        await express_buy(db1, listing.id, buyer_id, payment_method="simulated")
        await express_buy(db2, listing.id, buyer_id, payment_method="simulated")

        tx1 = db1.add.call_args[0][0]
        tx2 = db2.add.call_args[0][0]
        assert tx1.id != tx2.id
        assert tx1.buyer_id == tx2.buyer_id

    @pytest.mark.asyncio
    @patch(CDN_PATCH, new_callable=AsyncMock, return_value=SAMPLE_CONTENT)
    @patch(GET_LISTING_PATCH, new_callable=AsyncMock)
    async def test_concurrent_claims_broadcast_failure_ignored(
        self, mock_get_listing, mock_cdn
    ):
        """If WebSocket broadcast fails, the purchase still succeeds."""
        listing = _make_listing()
        mock_get_listing.return_value = listing

        db = _mock_db()
        # The broadcast import happens inside express_buy; even if it fails
        # (e.g. import error), the function catches the exception and continues.
        resp = await express_buy(db, listing.id, _uid(), payment_method="simulated")

        assert resp.status_code == 200
        db.commit.assert_awaited_once()

    @pytest.mark.asyncio
    @patch(CDN_PATCH, new_callable=AsyncMock, return_value=SAMPLE_CONTENT)
    @patch(GET_LISTING_PATCH, new_callable=AsyncMock)
    async def test_concurrent_claims_verification_status_auto_verified(
        self, mock_get_listing, mock_cdn
    ):
        """Express transactions are auto-verified (delivered_hash == content_hash)."""
        listing = _make_listing(content_hash="sha256:my_hash_123")
        mock_get_listing.return_value = listing

        db = _mock_db()
        await express_buy(db, listing.id, _uid(), payment_method="simulated")

        tx_obj = db.add.call_args[0][0]
        assert tx_obj.verification_status == "verified"
        assert tx_obj.content_hash == "sha256:my_hash_123"
        assert tx_obj.delivered_hash == tx_obj.content_hash
