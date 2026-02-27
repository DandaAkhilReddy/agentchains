"""Tests for marketplace.services.payment_reconciliation_service —
Stripe/Razorpay reconciliation and failed payment retry.

Uses in-memory SQLite via conftest fixtures.  asyncio_mode = "auto".

Note: The Transaction model does not have a `payment_reference` column.
The reconciliation functions use `getattr(tx, "payment_reference", None)`,
which returns None for real Transaction rows. Tests for the reconciliation
loop logic mock the DB query to return stub objects with `payment_reference`.
The retry_failed_payment function only uses `status` and `amount_usdc`, so
real Transaction rows work fine there.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from marketplace.models.transaction import Transaction
from marketplace.services import payment_reconciliation_service as svc


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _uid() -> str:
    return str(uuid.uuid4())


def _make_tx_stub(
    tx_id: str | None = None,
    amount: float = 10.0,
    status: str = "completed",
    payment_reference: str | None = None,
) -> SimpleNamespace:
    """Build a lightweight Transaction-like stub with payment_reference."""
    return SimpleNamespace(
        id=tx_id or _uid(),
        amount_usdc=Decimal(str(amount)),
        status=status,
        payment_reference=payment_reference,
        initiated_at=datetime.now(timezone.utc),
    )


async def _create_real_tx(
    db: AsyncSession,
    buyer_id: str,
    seller_id: str,
    listing_id: str,
    amount: float = 10.0,
    status: str = "failed",
) -> Transaction:
    """Create a real Transaction row (no payment_reference column)."""
    tx = Transaction(
        id=_uid(),
        listing_id=listing_id,
        buyer_id=buyer_id,
        seller_id=seller_id,
        amount_usdc=Decimal(str(amount)),
        status=status,
        content_hash=f"sha256:{'a' * 64}",
    )
    db.add(tx)
    await db.commit()
    await db.refresh(tx)
    return tx


# ---------------------------------------------------------------------------
# reconcile_stripe_payments — no transactions
# ---------------------------------------------------------------------------


@patch("marketplace.services.payment_reconciliation_service.StripePaymentService")
async def test_reconcile_stripe_no_transactions(
    mock_stripe_cls: MagicMock, db: AsyncSession,
):
    """Reconciliation with no transactions returns zeros."""
    result = await svc.reconcile_stripe_payments(db)

    assert result["provider"] == "stripe"
    assert result["total_checked"] == 0
    assert result["matched"] == 0
    assert result["mismatched"] == []
    assert result["missing"] == []
    assert "reconciled_at" in result


# ---------------------------------------------------------------------------
# reconcile_stripe_payments — with mocked query results
# ---------------------------------------------------------------------------


@patch("marketplace.services.payment_reconciliation_service.StripePaymentService")
async def test_reconcile_stripe_simulated_match(
    mock_stripe_cls: MagicMock, db: AsyncSession,
):
    """Simulated Stripe payment (simulated=True) counts as matched."""
    stub = _make_tx_stub(payment_reference="pi_test_123", amount=10.0)

    mock_instance = mock_stripe_cls.return_value
    mock_instance.retrieve_payment_intent = AsyncMock(return_value={
        "id": "pi_test_123",
        "status": "succeeded",
        "amount": 1000,
        "simulated": True,
    })

    # Mock the DB execute to return our stub
    mock_result = MagicMock()
    mock_scalars = MagicMock()
    mock_scalars.all.return_value = [stub]
    mock_result.scalars.return_value = mock_scalars

    original_execute = db.execute

    async def patched_execute(stmt, *args, **kwargs):
        stmt_str = str(stmt)
        if "transactions" in stmt_str.lower():
            return mock_result
        return await original_execute(stmt, *args, **kwargs)

    with patch.object(db, "execute", side_effect=patched_execute):
        result = await svc.reconcile_stripe_payments(db)

    assert result["total_checked"] == 1
    assert result["matched"] == 1
    assert result["mismatched"] == []


@patch("marketplace.services.payment_reconciliation_service.StripePaymentService")
async def test_reconcile_stripe_amount_mismatch(
    mock_stripe_cls: MagicMock, db: AsyncSession,
):
    """Amount mismatch between DB and Stripe is flagged."""
    stub = _make_tx_stub(payment_reference="pi_mismatch", amount=10.0)

    mock_instance = mock_stripe_cls.return_value
    mock_instance.retrieve_payment_intent = AsyncMock(return_value={
        "id": "pi_mismatch",
        "status": "succeeded",
        "amount": 2000,  # $20 from Stripe vs $10 in DB
    })

    mock_result = MagicMock()
    mock_scalars = MagicMock()
    mock_scalars.all.return_value = [stub]
    mock_result.scalars.return_value = mock_scalars

    original_execute = db.execute

    async def patched_execute(stmt, *args, **kwargs):
        stmt_str = str(stmt)
        if "transactions" in stmt_str.lower():
            return mock_result
        return await original_execute(stmt, *args, **kwargs)

    with patch.object(db, "execute", side_effect=patched_execute):
        result = await svc.reconcile_stripe_payments(db)

    assert result["matched"] == 0
    assert len(result["mismatched"]) == 1
    assert result["mismatched"][0]["expected_amount"] == 10.0
    assert result["mismatched"][0]["actual_amount"] == 20.0


@patch("marketplace.services.payment_reconciliation_service.StripePaymentService")
async def test_reconcile_stripe_status_mismatch(
    mock_stripe_cls: MagicMock, db: AsyncSession,
):
    """Stripe status != 'succeeded' is flagged as a mismatch."""
    stub = _make_tx_stub(payment_reference="pi_status", amount=5.0)

    mock_instance = mock_stripe_cls.return_value
    mock_instance.retrieve_payment_intent = AsyncMock(return_value={
        "id": "pi_status",
        "status": "requires_capture",
        "amount": 500,
    })

    mock_result = MagicMock()
    mock_scalars = MagicMock()
    mock_scalars.all.return_value = [stub]
    mock_result.scalars.return_value = mock_scalars

    original_execute = db.execute

    async def patched_execute(stmt, *args, **kwargs):
        stmt_str = str(stmt)
        if "transactions" in stmt_str.lower():
            return mock_result
        return await original_execute(stmt, *args, **kwargs)

    with patch.object(db, "execute", side_effect=patched_execute):
        result = await svc.reconcile_stripe_payments(db)

    assert len(result["mismatched"]) == 1
    assert result["mismatched"][0]["actual_status"] == "requires_capture"


@patch("marketplace.services.payment_reconciliation_service.StripePaymentService")
async def test_reconcile_stripe_retrieve_error(
    mock_stripe_cls: MagicMock, db: AsyncSession,
):
    """When Stripe retrieval raises an exception, tx goes into missing."""
    stub = _make_tx_stub(payment_reference="pi_error", amount=5.0)

    mock_instance = mock_stripe_cls.return_value
    mock_instance.retrieve_payment_intent = AsyncMock(
        side_effect=RuntimeError("Stripe API timeout"),
    )

    mock_result = MagicMock()
    mock_scalars = MagicMock()
    mock_scalars.all.return_value = [stub]
    mock_result.scalars.return_value = mock_scalars

    original_execute = db.execute

    async def patched_execute(stmt, *args, **kwargs):
        stmt_str = str(stmt)
        if "transactions" in stmt_str.lower():
            return mock_result
        return await original_execute(stmt, *args, **kwargs)

    with patch.object(db, "execute", side_effect=patched_execute):
        result = await svc.reconcile_stripe_payments(db)

    assert len(result["missing"]) == 1
    assert "Stripe API timeout" in result["missing"][0]["error"]


@patch("marketplace.services.payment_reconciliation_service.StripePaymentService")
async def test_reconcile_stripe_skips_non_stripe_refs(
    mock_stripe_cls: MagicMock, db: AsyncSession,
):
    """Transactions without pi_ prefix or without payment_reference are skipped."""
    stubs = [
        _make_tx_stub(payment_reference="pay_razorpay_1"),  # Razorpay
        _make_tx_stub(payment_reference=None),              # No ref
        _make_tx_stub(payment_reference=""),                 # Empty ref
    ]

    mock_result = MagicMock()
    mock_scalars = MagicMock()
    mock_scalars.all.return_value = stubs
    mock_result.scalars.return_value = mock_scalars

    original_execute = db.execute

    async def patched_execute(stmt, *args, **kwargs):
        stmt_str = str(stmt)
        if "transactions" in stmt_str.lower():
            return mock_result
        return await original_execute(stmt, *args, **kwargs)

    with patch.object(db, "execute", side_effect=patched_execute):
        result = await svc.reconcile_stripe_payments(db)

    assert result["total_checked"] == 3
    assert result["matched"] == 0
    assert result["mismatched"] == []
    assert result["missing"] == []


@patch("marketplace.services.payment_reconciliation_service.StripePaymentService")
async def test_reconcile_stripe_exact_amount_match(
    mock_stripe_cls: MagicMock, db: AsyncSession,
):
    """Amounts within $0.01 tolerance match successfully."""
    stub = _make_tx_stub(payment_reference="pi_close", amount=9.995)

    mock_instance = mock_stripe_cls.return_value
    mock_instance.retrieve_payment_intent = AsyncMock(return_value={
        "id": "pi_close",
        "status": "succeeded",
        "amount": 1000,  # $10.00 vs $9.995 = diff of $0.005 < $0.01
    })

    mock_result = MagicMock()
    mock_scalars = MagicMock()
    mock_scalars.all.return_value = [stub]
    mock_result.scalars.return_value = mock_scalars

    original_execute = db.execute

    async def patched_execute(stmt, *args, **kwargs):
        stmt_str = str(stmt)
        if "transactions" in stmt_str.lower():
            return mock_result
        return await original_execute(stmt, *args, **kwargs)

    with patch.object(db, "execute", side_effect=patched_execute):
        result = await svc.reconcile_stripe_payments(db)

    assert result["matched"] == 1


@patch("marketplace.services.payment_reconciliation_service.StripePaymentService")
async def test_reconcile_stripe_multiple_transactions(
    mock_stripe_cls: MagicMock, db: AsyncSession,
):
    """Reconciliation processes multiple transactions correctly."""
    stubs = [
        _make_tx_stub(payment_reference="pi_multi_1", amount=10.0),
        _make_tx_stub(payment_reference="pi_multi_2", amount=20.0),
        _make_tx_stub(payment_reference="pay_rp_1", amount=5.0),  # skipped
    ]

    mock_instance = mock_stripe_cls.return_value
    mock_instance.retrieve_payment_intent = AsyncMock(side_effect=[
        {"id": "pi_multi_1", "status": "succeeded", "amount": 1000, "simulated": True},
        {"id": "pi_multi_2", "status": "succeeded", "amount": 2000, "simulated": True},
    ])

    mock_result = MagicMock()
    mock_scalars = MagicMock()
    mock_scalars.all.return_value = stubs
    mock_result.scalars.return_value = mock_scalars

    original_execute = db.execute

    async def patched_execute(stmt, *args, **kwargs):
        stmt_str = str(stmt)
        if "transactions" in stmt_str.lower():
            return mock_result
        return await original_execute(stmt, *args, **kwargs)

    with patch.object(db, "execute", side_effect=patched_execute):
        result = await svc.reconcile_stripe_payments(db)

    assert result["total_checked"] == 3
    assert result["matched"] == 2


# ---------------------------------------------------------------------------
# reconcile_stripe_payments — since filter (uses real DB)
# ---------------------------------------------------------------------------


async def test_reconcile_stripe_no_matching_transactions_real_db(db: AsyncSession):
    """With real DB and no completed transactions, reconciliation returns zeros."""
    result = await svc.reconcile_stripe_payments(db)
    assert result["total_checked"] == 0


async def test_reconcile_stripe_with_since_filter_real_db(
    db: AsyncSession, make_agent, make_listing,
):
    """Since filter set to the future excludes all transactions."""
    buyer, _ = await make_agent()
    seller, _ = await make_agent()
    listing = await make_listing(seller.id, price_usdc=5.0)
    await _create_real_tx(db, buyer.id, seller.id, listing.id, 5.0, "completed")

    future_since = datetime.now(timezone.utc) + timedelta(hours=1)
    result = await svc.reconcile_stripe_payments(db, since=future_since)

    assert result["total_checked"] == 0


# ---------------------------------------------------------------------------
# reconcile_razorpay_payments
# ---------------------------------------------------------------------------


@patch("marketplace.services.payment_reconciliation_service.RazorpayPaymentService")
async def test_reconcile_razorpay_no_transactions(
    mock_rp_cls: MagicMock, db: AsyncSession,
):
    """Razorpay reconciliation with no transactions returns zeros."""
    result = await svc.reconcile_razorpay_payments(db)

    assert result["provider"] == "razorpay"
    assert result["total_checked"] == 0
    assert result["matched"] == 0


@patch("marketplace.services.payment_reconciliation_service.RazorpayPaymentService")
async def test_reconcile_razorpay_simulated_match(
    mock_rp_cls: MagicMock, db: AsyncSession,
):
    """Simulated Razorpay payment counts as matched."""
    stub = _make_tx_stub(payment_reference="pay_sim_123", amount=7.0)

    mock_instance = mock_rp_cls.return_value
    mock_instance.fetch_payment = AsyncMock(return_value={
        "id": "pay_sim_123",
        "status": "captured",
        "simulated": True,
    })

    mock_result = MagicMock()
    mock_scalars = MagicMock()
    mock_scalars.all.return_value = [stub]
    mock_result.scalars.return_value = mock_scalars

    original_execute = db.execute

    async def patched_execute(stmt, *args, **kwargs):
        stmt_str = str(stmt)
        if "transactions" in stmt_str.lower():
            return mock_result
        return await original_execute(stmt, *args, **kwargs)

    with patch.object(db, "execute", side_effect=patched_execute):
        result = await svc.reconcile_razorpay_payments(db)

    assert result["matched"] == 1


@patch("marketplace.services.payment_reconciliation_service.RazorpayPaymentService")
async def test_reconcile_razorpay_captured_match(
    mock_rp_cls: MagicMock, db: AsyncSession,
):
    """Razorpay status='captured' (non-simulated) counts as matched."""
    stub = _make_tx_stub(payment_reference="pay_real_456", amount=7.0)

    mock_instance = mock_rp_cls.return_value
    mock_instance.fetch_payment = AsyncMock(return_value={
        "id": "pay_real_456",
        "status": "captured",
    })

    mock_result = MagicMock()
    mock_scalars = MagicMock()
    mock_scalars.all.return_value = [stub]
    mock_result.scalars.return_value = mock_scalars

    original_execute = db.execute

    async def patched_execute(stmt, *args, **kwargs):
        stmt_str = str(stmt)
        if "transactions" in stmt_str.lower():
            return mock_result
        return await original_execute(stmt, *args, **kwargs)

    with patch.object(db, "execute", side_effect=patched_execute):
        result = await svc.reconcile_razorpay_payments(db)

    assert result["matched"] == 1


@patch("marketplace.services.payment_reconciliation_service.RazorpayPaymentService")
async def test_reconcile_razorpay_status_mismatch(
    mock_rp_cls: MagicMock, db: AsyncSession,
):
    """Razorpay status != 'captured' is flagged as mismatch."""
    stub = _make_tx_stub(payment_reference="pay_fail_789", amount=7.0)

    mock_instance = mock_rp_cls.return_value
    mock_instance.fetch_payment = AsyncMock(return_value={
        "id": "pay_fail_789",
        "status": "failed",
    })

    mock_result = MagicMock()
    mock_scalars = MagicMock()
    mock_scalars.all.return_value = [stub]
    mock_result.scalars.return_value = mock_scalars

    original_execute = db.execute

    async def patched_execute(stmt, *args, **kwargs):
        stmt_str = str(stmt)
        if "transactions" in stmt_str.lower():
            return mock_result
        return await original_execute(stmt, *args, **kwargs)

    with patch.object(db, "execute", side_effect=patched_execute):
        result = await svc.reconcile_razorpay_payments(db)

    assert len(result["mismatched"]) == 1
    assert result["mismatched"][0]["actual_status"] == "failed"


@patch("marketplace.services.payment_reconciliation_service.RazorpayPaymentService")
async def test_reconcile_razorpay_fetch_error(
    mock_rp_cls: MagicMock, db: AsyncSession,
):
    """When Razorpay fetch raises exception, tx goes into missing."""
    stub = _make_tx_stub(payment_reference="pay_err_999", amount=7.0)

    mock_instance = mock_rp_cls.return_value
    mock_instance.fetch_payment = AsyncMock(
        side_effect=ConnectionError("Razorpay unreachable"),
    )

    mock_result = MagicMock()
    mock_scalars = MagicMock()
    mock_scalars.all.return_value = [stub]
    mock_result.scalars.return_value = mock_scalars

    original_execute = db.execute

    async def patched_execute(stmt, *args, **kwargs):
        stmt_str = str(stmt)
        if "transactions" in stmt_str.lower():
            return mock_result
        return await original_execute(stmt, *args, **kwargs)

    with patch.object(db, "execute", side_effect=patched_execute):
        result = await svc.reconcile_razorpay_payments(db)

    assert len(result["missing"]) == 1
    assert "Razorpay unreachable" in result["missing"][0]["error"]


@patch("marketplace.services.payment_reconciliation_service.RazorpayPaymentService")
async def test_reconcile_razorpay_skips_stripe_refs(
    mock_rp_cls: MagicMock, db: AsyncSession,
):
    """Transactions with pi_ prefix are ignored by Razorpay reconciliation."""
    stub = _make_tx_stub(payment_reference="pi_stripe_1", amount=5.0)

    mock_result = MagicMock()
    mock_scalars = MagicMock()
    mock_scalars.all.return_value = [stub]
    mock_result.scalars.return_value = mock_scalars

    original_execute = db.execute

    async def patched_execute(stmt, *args, **kwargs):
        stmt_str = str(stmt)
        if "transactions" in stmt_str.lower():
            return mock_result
        return await original_execute(stmt, *args, **kwargs)

    with patch.object(db, "execute", side_effect=patched_execute):
        result = await svc.reconcile_razorpay_payments(db)

    assert result["matched"] == 0
    assert result["mismatched"] == []
    assert result["missing"] == []


# ---------------------------------------------------------------------------
# retry_failed_payment (uses real DB — Transaction rows work fine here)
# ---------------------------------------------------------------------------


@patch("marketplace.services.payment_reconciliation_service.StripePaymentService")
async def test_retry_failed_payment_success(
    mock_stripe_cls: MagicMock,
    db: AsyncSession, make_agent, make_listing,
):
    """Retry creates a new payment intent and sets tx status to pending."""
    buyer, _ = await make_agent()
    seller, _ = await make_agent()
    listing = await make_listing(seller.id, price_usdc=5.0)
    tx = await _create_real_tx(db, buyer.id, seller.id, listing.id, 5.0, "failed")

    mock_instance = mock_stripe_cls.return_value
    mock_instance.create_payment_intent = AsyncMock(return_value={
        "id": "pi_retry_new",
        "status": "requires_confirmation",
    })

    result = await svc.retry_failed_payment(db, tx.id)

    assert result["status"] == "retry_initiated"
    assert result["new_payment_intent"] == "pi_retry_new"
    assert result["transaction_id"] == tx.id

    # Verify tx status changed
    await db.refresh(tx)
    assert tx.status == "pending"


async def test_retry_failed_payment_not_found(db: AsyncSession):
    """retry_failed_payment returns error for non-existent transaction."""
    result = await svc.retry_failed_payment(db, "nonexistent-tx-id")
    assert result["error"] == "Transaction not found"


async def test_retry_failed_payment_wrong_status(
    db: AsyncSession, make_agent, make_listing,
):
    """retry_failed_payment returns error when tx status is not 'failed'."""
    buyer, _ = await make_agent()
    seller, _ = await make_agent()
    listing = await make_listing(seller.id, price_usdc=5.0)
    tx = await _create_real_tx(db, buyer.id, seller.id, listing.id, 5.0, "completed")

    result = await svc.retry_failed_payment(db, tx.id)

    assert "not 'failed'" in result["error"]


@patch("marketplace.services.payment_reconciliation_service.StripePaymentService")
async def test_retry_failed_payment_stripe_error(
    mock_stripe_cls: MagicMock,
    db: AsyncSession, make_agent, make_listing,
):
    """When Stripe create_payment_intent fails, error is returned."""
    buyer, _ = await make_agent()
    seller, _ = await make_agent()
    listing = await make_listing(seller.id, price_usdc=5.0)
    tx = await _create_real_tx(db, buyer.id, seller.id, listing.id, 5.0, "failed")

    mock_instance = mock_stripe_cls.return_value
    mock_instance.create_payment_intent = AsyncMock(
        side_effect=RuntimeError("Stripe card declined"),
    )

    result = await svc.retry_failed_payment(db, tx.id)

    assert "Stripe card declined" in result["error"]


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


@patch("marketplace.services.payment_reconciliation_service.StripePaymentService")
async def test_reconcile_stripe_disputed_transaction(
    mock_stripe_cls: MagicMock, db: AsyncSession,
):
    """Disputed transactions are included in reconciliation."""
    stub = _make_tx_stub(
        payment_reference="pi_disputed", amount=15.0, status="disputed",
    )

    mock_instance = mock_stripe_cls.return_value
    mock_instance.retrieve_payment_intent = AsyncMock(return_value={
        "id": "pi_disputed",
        "status": "succeeded",
        "amount": 1500,
        "simulated": True,
    })

    mock_result = MagicMock()
    mock_scalars = MagicMock()
    mock_scalars.all.return_value = [stub]
    mock_result.scalars.return_value = mock_scalars

    original_execute = db.execute

    async def patched_execute(stmt, *args, **kwargs):
        stmt_str = str(stmt)
        if "transactions" in stmt_str.lower():
            return mock_result
        return await original_execute(stmt, *args, **kwargs)

    with patch.object(db, "execute", side_effect=patched_execute):
        result = await svc.reconcile_stripe_payments(db)

    assert result["total_checked"] == 1
    assert result["matched"] == 1


async def test_retry_failed_payment_changes_only_status(
    db: AsyncSession, make_agent, make_listing,
):
    """After retry, only the status changes; amount stays the same."""
    buyer, _ = await make_agent()
    seller, _ = await make_agent()
    listing = await make_listing(seller.id, price_usdc=42.0)
    tx = await _create_real_tx(db, buyer.id, seller.id, listing.id, 42.0, "failed")

    with patch(
        "marketplace.services.payment_reconciliation_service.StripePaymentService"
    ) as mock_cls:
        mock_cls.return_value.create_payment_intent = AsyncMock(return_value={
            "id": "pi_retry_42",
        })
        await svc.retry_failed_payment(db, tx.id)

    await db.refresh(tx)
    assert tx.status == "pending"
    assert float(tx.amount_usdc) == 42.0
