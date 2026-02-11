"""Unit tests for the transaction service — purchase flow engine.

Tests use in-memory SQLite via conftest fixtures.
broadcast_event is imported lazily inside try/except blocks so no mocking needed.
"""

from datetime import datetime, timezone

import pytest
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from marketplace.core.exceptions import (
    InvalidTransactionStateError,
    TransactionNotFoundError,
)
from marketplace.models.transaction import Transaction
from marketplace.services import transaction_service


# ---------------------------------------------------------------------------
# initiate_transaction() tests
# ---------------------------------------------------------------------------

async def test_initiate_transaction_creates_record(
    db: AsyncSession, make_agent, make_listing, seed_platform
):
    """Initiating a transaction creates a Transaction record in payment_pending state."""
    seller, _ = await make_agent("seller", "seller")
    buyer, _ = await make_agent("buyer", "buyer")
    listing = await make_listing(seller.id, price_usdc=5.0)

    result = await transaction_service.initiate_transaction(db, listing.id, buyer.id)

    assert "transaction_id" in result
    assert result["status"] == "payment_pending"
    assert result["amount_usdc"] == 5.0
    assert "payment_details" in result
    assert "content_hash" in result

    # Verify DB record
    tx = await transaction_service.get_transaction(db, result["transaction_id"])
    assert tx.listing_id == listing.id
    assert tx.buyer_id == buyer.id
    assert tx.seller_id == seller.id
    assert float(tx.amount_usdc) == 5.0
    assert tx.status == "payment_pending"


async def test_initiate_transaction_builds_payment_details(
    db: AsyncSession, make_agent, make_listing, seed_platform
):
    """Payment details include simulated flag when in simulated mode."""
    seller, _ = await make_agent("seller", "seller")
    buyer, _ = await make_agent("buyer", "buyer")
    listing = await make_listing(seller.id, price_usdc=10.0)

    result = await transaction_service.initiate_transaction(db, listing.id, buyer.id)

    payment_details = result["payment_details"]
    assert "amount_usdc" in payment_details
    assert payment_details["amount_usdc"] == 10.0
    assert "network" in payment_details
    assert "asset" in payment_details
    assert payment_details["asset"] == "USDC"
    assert "simulated" in payment_details


async def test_initiate_transaction_broadcasts_event(
    db: AsyncSession, make_agent, make_listing, seed_platform
):
    """Initiating transaction triggers a broadcast (fire-and-forget, no errors raised)."""
    seller, _ = await make_agent("seller", "seller")
    buyer, _ = await make_agent("buyer", "buyer")
    listing = await make_listing(seller.id, price_usdc=2.0)

    # Should not raise even if broadcast fails
    result = await transaction_service.initiate_transaction(db, listing.id, buyer.id)
    assert result["status"] == "payment_pending"


# ---------------------------------------------------------------------------
# confirm_payment() tests
# ---------------------------------------------------------------------------

async def test_confirm_payment_with_signature(
    db: AsyncSession, make_agent, make_listing, seed_platform
):
    """Confirming payment with signature in simulated mode marks payment_confirmed."""
    seller, _ = await make_agent("seller", "seller")
    buyer, _ = await make_agent("buyer", "buyer")
    listing = await make_listing(seller.id, price_usdc=3.0)
    result = await transaction_service.initiate_transaction(db, listing.id, buyer.id)
    tx_id = result["transaction_id"]

    tx = await transaction_service.confirm_payment(
        db, tx_id, payment_signature="dummy_sig"
    )

    assert tx.status == "payment_confirmed"
    assert tx.payment_tx_hash is not None
    assert tx.payment_tx_hash.startswith("sim_0x")
    assert tx.paid_at is not None
    assert isinstance(tx.paid_at, datetime)


async def test_confirm_payment_simulated_mode(
    db: AsyncSession, make_agent, make_listing, seed_platform
):
    """Confirming payment without signature auto-confirms in simulated mode."""
    seller, _ = await make_agent("seller", "seller")
    buyer, _ = await make_agent("buyer", "buyer")
    listing = await make_listing(seller.id, price_usdc=1.0)
    result = await transaction_service.initiate_transaction(db, listing.id, buyer.id)
    tx_id = result["transaction_id"]

    tx = await transaction_service.confirm_payment(db, tx_id)

    assert tx.status == "payment_confirmed"
    assert tx.payment_tx_hash in ["sim_auto", None] or tx.payment_tx_hash.startswith("sim_")
    assert tx.paid_at is not None


async def test_confirm_payment_with_tx_hash(
    db: AsyncSession, make_agent, make_listing, seed_platform
):
    """Can confirm payment by providing tx_hash directly."""
    seller, _ = await make_agent("seller", "seller")
    buyer, _ = await make_agent("buyer", "buyer")
    listing = await make_listing(seller.id, price_usdc=2.5)
    result = await transaction_service.initiate_transaction(db, listing.id, buyer.id)
    tx_id = result["transaction_id"]

    tx = await transaction_service.confirm_payment(
        db, tx_id, payment_tx_hash="0xabcdef123456"
    )

    assert tx.status == "payment_confirmed"
    assert tx.payment_tx_hash == "0xabcdef123456"


async def test_confirm_payment_invalid_state(
    db: AsyncSession, make_agent, make_listing, seed_platform
):
    """Confirming payment on non-payment_pending transaction raises error."""
    seller, _ = await make_agent("seller", "seller")
    buyer, _ = await make_agent("buyer", "buyer")
    listing = await make_listing(seller.id, price_usdc=1.0)
    result = await transaction_service.initiate_transaction(db, listing.id, buyer.id)
    tx_id = result["transaction_id"]

    # Confirm once
    await transaction_service.confirm_payment(db, tx_id)

    # Try to confirm again
    with pytest.raises(InvalidTransactionStateError) as exc_info:
        await transaction_service.confirm_payment(db, tx_id)

    assert "payment_confirmed" in str(exc_info.value.detail)
    assert "payment_pending" in str(exc_info.value.detail)


# ---------------------------------------------------------------------------
# deliver_content() tests
# ---------------------------------------------------------------------------

async def test_deliver_content_seller_only(
    db: AsyncSession, make_agent, make_listing, seed_platform
):
    """Only the seller can deliver content for a transaction."""
    seller, _ = await make_agent("seller", "seller")
    buyer, _ = await make_agent("buyer", "buyer")
    listing = await make_listing(seller.id, price_usdc=2.0)
    result = await transaction_service.initiate_transaction(db, listing.id, buyer.id)
    tx_id = result["transaction_id"]
    await transaction_service.confirm_payment(db, tx_id)

    content = "This is the delivered content"
    tx = await transaction_service.deliver_content(db, tx_id, content, seller.id)

    assert tx.status == "delivered"
    assert tx.delivered_hash is not None
    assert tx.delivered_hash.startswith("sha256:")
    assert tx.delivered_at is not None


async def test_deliver_content_non_seller_403(
    db: AsyncSession, make_agent, make_listing, seed_platform
):
    """Non-seller cannot deliver content — raises 403."""
    seller, _ = await make_agent("seller", "seller")
    buyer, _ = await make_agent("buyer", "buyer")
    other, _ = await make_agent("other", "seller")
    listing = await make_listing(seller.id, price_usdc=2.0)
    result = await transaction_service.initiate_transaction(db, listing.id, buyer.id)
    tx_id = result["transaction_id"]
    await transaction_service.confirm_payment(db, tx_id)

    with pytest.raises(HTTPException) as exc_info:
        await transaction_service.deliver_content(
            db, tx_id, "content", other.id
        )

    assert exc_info.value.status_code == 403
    assert "Not the seller" in exc_info.value.detail


async def test_deliver_content_invalid_state(
    db: AsyncSession, make_agent, make_listing, seed_platform
):
    """Cannot deliver content before payment is confirmed."""
    seller, _ = await make_agent("seller", "seller")
    buyer, _ = await make_agent("buyer", "buyer")
    listing = await make_listing(seller.id, price_usdc=1.0)
    result = await transaction_service.initiate_transaction(db, listing.id, buyer.id)
    tx_id = result["transaction_id"]

    with pytest.raises(InvalidTransactionStateError) as exc_info:
        await transaction_service.deliver_content(db, tx_id, "content", seller.id)

    assert "payment_pending" in str(exc_info.value.detail)
    assert "payment_confirmed" in str(exc_info.value.detail)


# ---------------------------------------------------------------------------
# verify_delivery() tests
# ---------------------------------------------------------------------------

async def test_verify_delivery_hash_match_completed(
    db: AsyncSession, make_agent, make_listing, seed_platform
):
    """When delivered hash matches expected hash, transaction moves to completed."""
    seller, _ = await make_agent("seller", "seller")
    buyer, _ = await make_agent("buyer", "buyer")

    # Create listing with known content — hash is auto-computed by fixture
    content = "Test content"
    listing = await make_listing(seller.id, price_usdc=1.0, content=content)
    result = await transaction_service.initiate_transaction(db, listing.id, buyer.id)
    tx_id = result["transaction_id"]
    await transaction_service.confirm_payment(db, tx_id)
    await transaction_service.deliver_content(db, tx_id, content, seller.id)

    # Verify delivery
    tx = await transaction_service.verify_delivery(db, tx_id, buyer.id)

    assert tx.status == "completed"
    assert tx.verification_status == "verified"
    assert tx.verified_at is not None
    assert tx.completed_at is not None


async def test_verify_delivery_hash_mismatch_disputed(
    db: AsyncSession, make_agent, make_listing, seed_platform
):
    """When hashes don't match, transaction moves to disputed."""
    seller, _ = await make_agent("seller", "seller")
    buyer, _ = await make_agent("buyer", "buyer")

    # Create listing with one hash
    listing = await make_listing(
        seller.id,
        price_usdc=1.0,
        content_hash="sha256:" + "a" * 64
    )
    result = await transaction_service.initiate_transaction(db, listing.id, buyer.id)
    tx_id = result["transaction_id"]
    await transaction_service.confirm_payment(db, tx_id)

    # Deliver different content
    await transaction_service.deliver_content(db, tx_id, "Wrong content", seller.id)

    # Verify delivery
    tx = await transaction_service.verify_delivery(db, tx_id, buyer.id)

    assert tx.status == "disputed"
    assert tx.verification_status == "failed"
    assert tx.error_message is not None
    assert "Hash mismatch" in tx.error_message


async def test_verify_delivery_increments_access_count(
    db: AsyncSession, make_agent, make_listing, seed_platform
):
    """Successful verification increments listing access_count."""
    seller, _ = await make_agent("seller", "seller")
    buyer, _ = await make_agent("buyer", "buyer")

    # Create listing with matching content — hash is auto-computed by fixture
    content = "Valid content"
    listing = await make_listing(seller.id, price_usdc=1.0, content=content)
    initial_count = listing.access_count

    result = await transaction_service.initiate_transaction(db, listing.id, buyer.id)
    tx_id = result["transaction_id"]
    await transaction_service.confirm_payment(db, tx_id)
    await transaction_service.deliver_content(db, tx_id, content, seller.id)
    await transaction_service.verify_delivery(db, tx_id, buyer.id)

    # Check listing access count increased
    from marketplace.services.listing_service import get_listing
    updated_listing = await get_listing(db, listing.id)
    assert updated_listing.access_count == initial_count + 1


async def test_verify_delivery_buyer_only(
    db: AsyncSession, make_agent, make_listing, seed_platform
):
    """Only the buyer can verify delivery — raises 403."""
    seller, _ = await make_agent("seller", "seller")
    buyer, _ = await make_agent("buyer", "buyer")
    other, _ = await make_agent("other", "buyer")

    listing = await make_listing(seller.id, price_usdc=1.0)
    result = await transaction_service.initiate_transaction(db, listing.id, buyer.id)
    tx_id = result["transaction_id"]
    await transaction_service.confirm_payment(db, tx_id)
    await transaction_service.deliver_content(db, tx_id, "content", seller.id)

    with pytest.raises(HTTPException) as exc_info:
        await transaction_service.verify_delivery(db, tx_id, other.id)

    assert exc_info.value.status_code == 403
    assert "Not the buyer" in exc_info.value.detail


async def test_verify_delivery_invalid_state(
    db: AsyncSession, make_agent, make_listing, seed_platform
):
    """Cannot verify before content is delivered."""
    seller, _ = await make_agent("seller", "seller")
    buyer, _ = await make_agent("buyer", "buyer")
    listing = await make_listing(seller.id, price_usdc=1.0)
    result = await transaction_service.initiate_transaction(db, listing.id, buyer.id)
    tx_id = result["transaction_id"]
    await transaction_service.confirm_payment(db, tx_id)

    with pytest.raises(InvalidTransactionStateError) as exc_info:
        await transaction_service.verify_delivery(db, tx_id, buyer.id)

    assert "payment_confirmed" in str(exc_info.value.detail)
    assert "delivered" in str(exc_info.value.detail)


# ---------------------------------------------------------------------------
# list_transactions() tests
# ---------------------------------------------------------------------------

async def test_list_transactions_by_agent(
    db: AsyncSession, make_agent, make_listing, seed_platform
):
    """Listing by agent returns transactions where agent is buyer or seller."""
    seller, _ = await make_agent("seller", "seller")
    buyer1, _ = await make_agent("buyer1", "buyer")
    buyer2, _ = await make_agent("buyer2", "buyer")

    listing = await make_listing(seller.id, price_usdc=1.0)

    # Create transactions
    r1 = await transaction_service.initiate_transaction(db, listing.id, buyer1.id)
    r2 = await transaction_service.initiate_transaction(db, listing.id, buyer2.id)

    # List seller's transactions
    txns, total = await transaction_service.list_transactions(db, agent_id=seller.id)
    assert total == 2
    assert len(txns) == 2

    # List buyer1's transactions
    txns, total = await transaction_service.list_transactions(db, agent_id=buyer1.id)
    assert total == 1
    assert len(txns) == 1
    assert txns[0].buyer_id == buyer1.id


async def test_list_transactions_by_status(
    db: AsyncSession, make_agent, make_listing, seed_platform
):
    """Can filter transactions by status."""
    seller, _ = await make_agent("seller", "seller")
    buyer1, _ = await make_agent("buyer1", "buyer")
    buyer2, _ = await make_agent("buyer2", "buyer")

    listing = await make_listing(seller.id, price_usdc=1.0)

    r1 = await transaction_service.initiate_transaction(db, listing.id, buyer1.id)
    r2 = await transaction_service.initiate_transaction(db, listing.id, buyer2.id)

    # Confirm one
    await transaction_service.confirm_payment(db, r1["transaction_id"])

    # Filter by payment_pending
    txns, total = await transaction_service.list_transactions(
        db, status_filter="payment_pending"
    )
    assert total == 1
    assert txns[0].id == r2["transaction_id"]

    # Filter by payment_confirmed
    txns, total = await transaction_service.list_transactions(
        db, status_filter="payment_confirmed"
    )
    assert total == 1
    assert txns[0].id == r1["transaction_id"]


async def test_list_transactions_pagination(
    db: AsyncSession, make_agent, make_listing, seed_platform
):
    """Pagination works correctly."""
    seller, _ = await make_agent("seller", "seller")
    buyer, _ = await make_agent("buyer", "buyer")
    listing = await make_listing(seller.id, price_usdc=1.0)

    # Create 5 transactions
    for _ in range(5):
        await transaction_service.initiate_transaction(db, listing.id, buyer.id)

    # Page 1: 2 items
    txns, total = await transaction_service.list_transactions(
        db, agent_id=seller.id, page=1, page_size=2
    )
    assert total == 5
    assert len(txns) == 2

    # Page 2: 2 items
    txns, total = await transaction_service.list_transactions(
        db, agent_id=seller.id, page=2, page_size=2
    )
    assert total == 5
    assert len(txns) == 2

    # Page 3: 1 item
    txns, total = await transaction_service.list_transactions(
        db, agent_id=seller.id, page=3, page_size=2
    )
    assert total == 5
    assert len(txns) == 1


async def test_list_transactions_all(
    db: AsyncSession, make_agent, make_listing, seed_platform
):
    """Without filters, returns all transactions."""
    seller, _ = await make_agent("seller", "seller")
    buyer1, _ = await make_agent("buyer1", "buyer")
    buyer2, _ = await make_agent("buyer2", "buyer")

    listing = await make_listing(seller.id, price_usdc=1.0)

    await transaction_service.initiate_transaction(db, listing.id, buyer1.id)
    await transaction_service.initiate_transaction(db, listing.id, buyer2.id)

    txns, total = await transaction_service.list_transactions(db)
    assert total == 2
    assert len(txns) == 2


# ---------------------------------------------------------------------------
# get_transaction() and error cases
# ---------------------------------------------------------------------------

async def test_get_transaction_not_found(db: AsyncSession):
    """Getting non-existent transaction raises TransactionNotFoundError."""
    with pytest.raises(TransactionNotFoundError) as exc_info:
        await transaction_service.get_transaction(db, "nonexistent-id")

    assert "nonexistent-id" in str(exc_info.value.detail)


async def test_transaction_flow_end_to_end(
    db: AsyncSession, make_agent, make_listing, seed_platform
):
    """Complete happy path: initiate -> confirm -> deliver -> verify -> completed."""
    seller, _ = await make_agent("seller", "seller")
    buyer, _ = await make_agent("buyer", "buyer")

    # Create listing with known content — hash is auto-computed by fixture
    content = "End to end test content"
    listing = await make_listing(seller.id, price_usdc=5.0, content=content)

    # 1. Initiate
    result = await transaction_service.initiate_transaction(db, listing.id, buyer.id)
    tx_id = result["transaction_id"]
    tx = await transaction_service.get_transaction(db, tx_id)
    assert tx.status == "payment_pending"

    # 2. Confirm payment
    tx = await transaction_service.confirm_payment(db, tx_id)
    assert tx.status == "payment_confirmed"
    assert tx.paid_at is not None

    # 3. Deliver content
    tx = await transaction_service.deliver_content(db, tx_id, content, seller.id)
    assert tx.status == "delivered"
    assert tx.delivered_at is not None
    assert tx.delivered_hash == listing.content_hash

    # 4. Verify delivery
    tx = await transaction_service.verify_delivery(db, tx_id, buyer.id)
    assert tx.status == "completed"
    assert tx.verification_status == "verified"
    assert tx.verified_at is not None
    assert tx.completed_at is not None

    # Check final state
    final_tx = await transaction_service.get_transaction(db, tx_id)
    assert final_tx.status == "completed"
    assert final_tx.verification_status == "verified"
