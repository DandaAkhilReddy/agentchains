"""Deep tests for the transaction 5-state machine.

Covers: happy path, dispute path, auth guards, timestamps,
wrong-state errors, list filters, 404s, payment requirements,
access count, and full HTTP happy path.

Exactly 20 tests.
"""

from datetime import datetime, timezone

import pytest
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from marketplace.core.exceptions import (
    InvalidTransactionStateError,
    TransactionNotFoundError,
)
from marketplace.services import transaction_service


# ---------------------------------------------------------------------------
# 1-4  State machine: happy path transitions
# ---------------------------------------------------------------------------

async def test_state_initiate_sets_payment_pending(
    db: AsyncSession, make_agent, make_listing, seed_platform
):
    """initiate_transaction sets status to payment_pending."""
    seller, _ = await make_agent("sm-seller-1", "seller")
    buyer, _ = await make_agent("sm-buyer-1", "buyer")
    listing = await make_listing(seller.id, price_usdc=2.0)

    result = await transaction_service.initiate_transaction(db, listing.id, buyer.id)

    assert result["status"] == "payment_pending"
    tx = await transaction_service.get_transaction(db, result["transaction_id"])
    assert tx.status == "payment_pending"
    assert tx.buyer_id == buyer.id
    assert tx.seller_id == seller.id


async def test_state_confirm_sets_payment_confirmed(
    db: AsyncSession, make_agent, make_listing, seed_platform
):
    """confirm_payment transitions payment_pending -> payment_confirmed."""
    seller, _ = await make_agent("sm-seller-2", "seller")
    buyer, _ = await make_agent("sm-buyer-2", "buyer")
    listing = await make_listing(seller.id, price_usdc=3.0)

    result = await transaction_service.initiate_transaction(db, listing.id, buyer.id)
    tx = await transaction_service.confirm_payment(db, result["transaction_id"])

    assert tx.status == "payment_confirmed"


async def test_state_deliver_sets_delivered(
    db: AsyncSession, make_agent, make_listing, seed_platform
):
    """deliver_content transitions payment_confirmed -> delivered."""
    seller, _ = await make_agent("sm-seller-3", "seller")
    buyer, _ = await make_agent("sm-buyer-3", "buyer")
    listing = await make_listing(seller.id, price_usdc=1.0)

    result = await transaction_service.initiate_transaction(db, listing.id, buyer.id)
    tx_id = result["transaction_id"]
    await transaction_service.confirm_payment(db, tx_id)
    tx = await transaction_service.deliver_content(db, tx_id, "payload", seller.id)

    assert tx.status == "delivered"
    assert tx.delivered_hash is not None
    assert tx.delivered_hash.startswith("sha256:")


async def test_state_verify_matching_sets_completed(
    db: AsyncSession, make_agent, make_listing, seed_platform
):
    """verify_delivery with matching hash transitions delivered -> completed."""
    seller, _ = await make_agent("sm-seller-4", "seller")
    buyer, _ = await make_agent("sm-buyer-4", "buyer")
    content = "state-machine-content"
    listing = await make_listing(seller.id, price_usdc=1.0, content=content)

    result = await transaction_service.initiate_transaction(db, listing.id, buyer.id)
    tx_id = result["transaction_id"]
    await transaction_service.confirm_payment(db, tx_id)
    await transaction_service.deliver_content(db, tx_id, content, seller.id)
    tx = await transaction_service.verify_delivery(db, tx_id, buyer.id)

    assert tx.status == "completed"
    assert tx.verification_status == "verified"


# ---------------------------------------------------------------------------
# 5  Dispute path: hash mismatch -> disputed
# ---------------------------------------------------------------------------

async def test_dispute_path_wrong_content(
    db: AsyncSession, make_agent, make_listing, seed_platform
):
    """Delivering wrong content then verifying transitions to disputed."""
    seller, _ = await make_agent("disp-seller", "seller")
    buyer, _ = await make_agent("disp-buyer", "buyer")
    # Force a content hash that will never match delivered content
    listing = await make_listing(
        seller.id, price_usdc=1.0,
        content_hash="sha256:" + "f" * 64,
    )

    result = await transaction_service.initiate_transaction(db, listing.id, buyer.id)
    tx_id = result["transaction_id"]
    await transaction_service.confirm_payment(db, tx_id)
    await transaction_service.deliver_content(db, tx_id, "totally wrong data", seller.id)
    tx = await transaction_service.verify_delivery(db, tx_id, buyer.id)

    assert tx.status == "disputed"
    assert tx.verification_status == "failed"
    assert "Hash mismatch" in tx.error_message


# ---------------------------------------------------------------------------
# 6-7  Auth guards: deliver by non-seller 403, verify by non-buyer 403
# ---------------------------------------------------------------------------

async def test_deliver_by_non_seller_raises_403(
    db: AsyncSession, make_agent, make_listing, seed_platform
):
    """Only the actual seller can deliver content -- others get 403."""
    seller, _ = await make_agent("auth-seller-1", "seller")
    buyer, _ = await make_agent("auth-buyer-1", "buyer")
    impostor, _ = await make_agent("auth-impostor-1", "seller")
    listing = await make_listing(seller.id, price_usdc=1.0)

    result = await transaction_service.initiate_transaction(db, listing.id, buyer.id)
    tx_id = result["transaction_id"]
    await transaction_service.confirm_payment(db, tx_id)

    with pytest.raises(HTTPException) as exc_info:
        await transaction_service.deliver_content(db, tx_id, "impostor data", impostor.id)

    assert exc_info.value.status_code == 403
    assert "Not the seller" in exc_info.value.detail


async def test_verify_by_non_buyer_raises_403(
    db: AsyncSession, make_agent, make_listing, seed_platform
):
    """Only the actual buyer can verify -- others get 403."""
    seller, _ = await make_agent("auth-seller-2", "seller")
    buyer, _ = await make_agent("auth-buyer-2", "buyer")
    impostor, _ = await make_agent("auth-impostor-2", "buyer")
    listing = await make_listing(seller.id, price_usdc=1.0)

    result = await transaction_service.initiate_transaction(db, listing.id, buyer.id)
    tx_id = result["transaction_id"]
    await transaction_service.confirm_payment(db, tx_id)
    await transaction_service.deliver_content(db, tx_id, "data", seller.id)

    with pytest.raises(HTTPException) as exc_info:
        await transaction_service.verify_delivery(db, tx_id, impostor.id)

    assert exc_info.value.status_code == 403
    assert "Not the buyer" in exc_info.value.detail


# ---------------------------------------------------------------------------
# 8-10  Timestamps: paid_at, delivered_at, completed_at set at right step
# ---------------------------------------------------------------------------

async def test_timestamp_paid_at_set_on_confirm(
    db: AsyncSession, make_agent, make_listing, seed_platform
):
    """paid_at is None until confirm_payment, then is a UTC datetime."""
    seller, _ = await make_agent("ts-seller-1", "seller")
    buyer, _ = await make_agent("ts-buyer-1", "buyer")
    listing = await make_listing(seller.id, price_usdc=1.0)

    result = await transaction_service.initiate_transaction(db, listing.id, buyer.id)
    tx_id = result["transaction_id"]

    tx_before = await transaction_service.get_transaction(db, tx_id)
    assert tx_before.paid_at is None

    tx_after = await transaction_service.confirm_payment(db, tx_id)
    assert tx_after.paid_at is not None
    assert isinstance(tx_after.paid_at, datetime)


async def test_timestamp_delivered_at_set_on_deliver(
    db: AsyncSession, make_agent, make_listing, seed_platform
):
    """delivered_at is None until deliver_content, then is a UTC datetime."""
    seller, _ = await make_agent("ts-seller-2", "seller")
    buyer, _ = await make_agent("ts-buyer-2", "buyer")
    listing = await make_listing(seller.id, price_usdc=1.0)

    result = await transaction_service.initiate_transaction(db, listing.id, buyer.id)
    tx_id = result["transaction_id"]
    await transaction_service.confirm_payment(db, tx_id)

    tx_before = await transaction_service.get_transaction(db, tx_id)
    assert tx_before.delivered_at is None

    tx_after = await transaction_service.deliver_content(db, tx_id, "data", seller.id)
    assert tx_after.delivered_at is not None
    assert isinstance(tx_after.delivered_at, datetime)


async def test_timestamp_completed_at_set_on_verify(
    db: AsyncSession, make_agent, make_listing, seed_platform
):
    """completed_at is None until successful verify_delivery."""
    seller, _ = await make_agent("ts-seller-3", "seller")
    buyer, _ = await make_agent("ts-buyer-3", "buyer")
    content = "timestamp-test-content"
    listing = await make_listing(seller.id, price_usdc=1.0, content=content)

    result = await transaction_service.initiate_transaction(db, listing.id, buyer.id)
    tx_id = result["transaction_id"]
    await transaction_service.confirm_payment(db, tx_id)
    await transaction_service.deliver_content(db, tx_id, content, seller.id)

    tx_before = await transaction_service.get_transaction(db, tx_id)
    assert tx_before.completed_at is None

    tx_after = await transaction_service.verify_delivery(db, tx_id, buyer.id)
    assert tx_after.completed_at is not None
    assert tx_after.verified_at is not None
    assert isinstance(tx_after.completed_at, datetime)


# ---------------------------------------------------------------------------
# 11-13  Wrong state errors
# ---------------------------------------------------------------------------

async def test_confirm_on_already_confirmed_raises(
    db: AsyncSession, make_agent, make_listing, seed_platform
):
    """Calling confirm_payment twice raises InvalidTransactionStateError."""
    seller, _ = await make_agent("ws-seller-1", "seller")
    buyer, _ = await make_agent("ws-buyer-1", "buyer")
    listing = await make_listing(seller.id, price_usdc=1.0)

    result = await transaction_service.initiate_transaction(db, listing.id, buyer.id)
    tx_id = result["transaction_id"]
    await transaction_service.confirm_payment(db, tx_id)

    with pytest.raises(InvalidTransactionStateError) as exc_info:
        await transaction_service.confirm_payment(db, tx_id)

    assert exc_info.value.status_code == 400
    assert "payment_confirmed" in str(exc_info.value.detail)


async def test_deliver_on_pending_raises(
    db: AsyncSession, make_agent, make_listing, seed_platform
):
    """Cannot deliver content while transaction is still payment_pending."""
    seller, _ = await make_agent("ws-seller-2", "seller")
    buyer, _ = await make_agent("ws-buyer-2", "buyer")
    listing = await make_listing(seller.id, price_usdc=1.0)

    result = await transaction_service.initiate_transaction(db, listing.id, buyer.id)
    tx_id = result["transaction_id"]

    with pytest.raises(InvalidTransactionStateError) as exc_info:
        await transaction_service.deliver_content(db, tx_id, "early data", seller.id)

    assert exc_info.value.status_code == 400
    assert "payment_pending" in str(exc_info.value.detail)
    assert "payment_confirmed" in str(exc_info.value.detail)


async def test_verify_on_pending_raises(
    db: AsyncSession, make_agent, make_listing, seed_platform
):
    """Cannot verify delivery when transaction is still payment_pending."""
    seller, _ = await make_agent("ws-seller-3", "seller")
    buyer, _ = await make_agent("ws-buyer-3", "buyer")
    listing = await make_listing(seller.id, price_usdc=1.0)

    result = await transaction_service.initiate_transaction(db, listing.id, buyer.id)
    tx_id = result["transaction_id"]

    with pytest.raises(InvalidTransactionStateError) as exc_info:
        await transaction_service.verify_delivery(db, tx_id, buyer.id)

    assert exc_info.value.status_code == 400
    assert "payment_pending" in str(exc_info.value.detail)
    assert "delivered" in str(exc_info.value.detail)


# ---------------------------------------------------------------------------
# 14-15  List: filter by status, filter by agent_id, pagination
# ---------------------------------------------------------------------------

async def test_list_filter_by_status(
    db: AsyncSession, make_agent, make_listing, seed_platform
):
    """list_transactions with status_filter returns only matching status."""
    seller, _ = await make_agent("lf-seller", "seller")
    buyer, _ = await make_agent("lf-buyer", "buyer")
    listing = await make_listing(seller.id, price_usdc=1.0)

    r1 = await transaction_service.initiate_transaction(db, listing.id, buyer.id)
    r2 = await transaction_service.initiate_transaction(db, listing.id, buyer.id)
    # Confirm only one
    await transaction_service.confirm_payment(db, r1["transaction_id"])

    pending, total_pending = await transaction_service.list_transactions(
        db, status_filter="payment_pending"
    )
    assert total_pending == 1
    assert pending[0].id == r2["transaction_id"]

    confirmed, total_confirmed = await transaction_service.list_transactions(
        db, status_filter="payment_confirmed"
    )
    assert total_confirmed == 1
    assert confirmed[0].id == r1["transaction_id"]


async def test_list_filter_by_agent_and_pagination(
    db: AsyncSession, make_agent, make_listing, seed_platform
):
    """list_transactions supports agent_id filter and page/page_size pagination."""
    seller, _ = await make_agent("lp-seller", "seller")
    buyer_a, _ = await make_agent("lp-buyer-a", "buyer")
    buyer_b, _ = await make_agent("lp-buyer-b", "buyer")
    listing = await make_listing(seller.id, price_usdc=1.0)

    # buyer_a initiates 3, buyer_b initiates 1
    for _ in range(3):
        await transaction_service.initiate_transaction(db, listing.id, buyer_a.id)
    await transaction_service.initiate_transaction(db, listing.id, buyer_b.id)

    # Agent filter
    txns_a, total_a = await transaction_service.list_transactions(db, agent_id=buyer_a.id)
    assert total_a == 3

    txns_b, total_b = await transaction_service.list_transactions(db, agent_id=buyer_b.id)
    assert total_b == 1

    # Pagination: page_size 2 for buyer_a
    page1, _ = await transaction_service.list_transactions(
        db, agent_id=buyer_a.id, page=1, page_size=2
    )
    assert len(page1) == 2

    page2, _ = await transaction_service.list_transactions(
        db, agent_id=buyer_a.id, page=2, page_size=2
    )
    assert len(page2) == 1


# ---------------------------------------------------------------------------
# 16  Get nonexistent -> 404
# ---------------------------------------------------------------------------

async def test_get_nonexistent_transaction_raises_404(db: AsyncSession):
    """Getting a non-existent transaction raises TransactionNotFoundError (404)."""
    with pytest.raises(TransactionNotFoundError) as exc_info:
        await transaction_service.get_transaction(db, "does-not-exist-123")

    assert exc_info.value.status_code == 404
    assert "does-not-exist-123" in str(exc_info.value.detail)


# ---------------------------------------------------------------------------
# 17  Payment: requirements include seller wallet, simulated auto-confirms
# ---------------------------------------------------------------------------

async def test_payment_requirements_and_auto_confirm(
    db: AsyncSession, make_agent, make_listing, seed_platform
):
    """Initiate returns payment requirements with seller address; auto-confirm works."""
    seller, _ = await make_agent("pay-seller", "seller")
    buyer, _ = await make_agent("pay-buyer", "buyer")
    listing = await make_listing(seller.id, price_usdc=7.5)

    result = await transaction_service.initiate_transaction(db, listing.id, buyer.id)

    pd = result["payment_details"]
    assert "pay_to_address" in pd
    assert pd["amount_usdc"] == 7.5
    assert pd["asset"] == "USDC"
    assert pd["simulated"] is True
    # Seller wallet_address defaults to "" -- the service fills 0x0...0 for simulated
    assert "pay_to_address" in pd

    # Simulated auto-confirm (no signature)
    tx = await transaction_service.confirm_payment(db, result["transaction_id"])
    assert tx.status == "payment_confirmed"
    assert tx.payment_tx_hash is not None


# ---------------------------------------------------------------------------
# 18  Access count incremented on verification
# ---------------------------------------------------------------------------

async def test_access_count_incremented_on_successful_verification(
    db: AsyncSession, make_agent, make_listing, seed_platform
):
    """Successful verification increments listing.access_count by 1."""
    seller, _ = await make_agent("ac-seller", "seller")
    buyer, _ = await make_agent("ac-buyer", "buyer")
    content = "access-count-content"
    listing = await make_listing(seller.id, price_usdc=1.0, content=content)

    initial_count = listing.access_count
    assert initial_count == 0

    result = await transaction_service.initiate_transaction(db, listing.id, buyer.id)
    tx_id = result["transaction_id"]
    await transaction_service.confirm_payment(db, tx_id)
    await transaction_service.deliver_content(db, tx_id, content, seller.id)
    await transaction_service.verify_delivery(db, tx_id, buyer.id)

    from marketplace.services.listing_service import get_listing
    updated = await get_listing(db, listing.id)
    assert updated.access_count == initial_count + 1


# ---------------------------------------------------------------------------
# 19  Dispute does NOT increment access count
# ---------------------------------------------------------------------------

async def test_dispute_does_not_increment_access_count(
    db: AsyncSession, make_agent, make_listing, seed_platform
):
    """Disputed verification does not increment listing.access_count."""
    seller, _ = await make_agent("ac-seller-d", "seller")
    buyer, _ = await make_agent("ac-buyer-d", "buyer")
    listing = await make_listing(
        seller.id, price_usdc=1.0,
        content_hash="sha256:" + "b" * 64,
    )
    initial_count = listing.access_count

    result = await transaction_service.initiate_transaction(db, listing.id, buyer.id)
    tx_id = result["transaction_id"]
    await transaction_service.confirm_payment(db, tx_id)
    await transaction_service.deliver_content(db, tx_id, "wrong stuff", seller.id)
    tx = await transaction_service.verify_delivery(db, tx_id, buyer.id)

    assert tx.status == "disputed"

    from marketplace.services.listing_service import get_listing
    updated = await get_listing(db, listing.id)
    assert updated.access_count == initial_count


# ---------------------------------------------------------------------------
# 20  Full happy path via HTTP client
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_full_happy_path_via_http(
    client, make_agent, make_listing, auth_header
):
    """End-to-end via HTTP: initiate -> confirm -> deliver -> verify -> completed."""
    seller, seller_token = await make_agent(name="http-seller", agent_type="seller")
    buyer, buyer_token = await make_agent(name="http-buyer", agent_type="buyer")
    content = "http-happy-path-content"
    listing = await make_listing(seller.id, price_usdc=4.0, content=content)

    # 1. Initiate
    resp = await client.post(
        "/api/v1/transactions/initiate",
        json={"listing_id": listing.id},
        headers=auth_header(buyer_token),
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["status"] == "payment_pending"
    tx_id = data["transaction_id"]

    # 2. Confirm payment
    resp = await client.post(
        f"/api/v1/transactions/{tx_id}/confirm-payment",
        json={"payment_signature": "", "payment_tx_hash": ""},
        headers=auth_header(buyer_token),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "payment_confirmed"
    assert data["paid_at"] is not None

    # 3. Deliver content (same content so hash matches)
    resp = await client.post(
        f"/api/v1/transactions/{tx_id}/deliver",
        json={"content": content},
        headers=auth_header(seller_token),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "delivered"
    assert data["delivered_at"] is not None
    assert data["delivered_hash"] == listing.content_hash

    # 4. Verify delivery
    resp = await client.post(
        f"/api/v1/transactions/{tx_id}/verify",
        headers=auth_header(buyer_token),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "completed"
    assert data["verification_status"] == "verified"
    assert data["completed_at"] is not None
    assert data["verified_at"] is not None

    # 5. GET confirms final state
    resp = await client.get(
        f"/api/v1/transactions/{tx_id}",
        headers=auth_header(buyer_token),
    )
    assert resp.status_code == 200
    final = resp.json()
    assert final["status"] == "completed"
