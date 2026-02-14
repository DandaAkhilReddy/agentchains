from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from marketplace.core.async_tasks import fire_and_forget
from marketplace.core.exceptions import (
    InvalidTransactionStateError,
    TransactionNotFoundError,
)
from marketplace.models.listing import DataListing
from marketplace.models.transaction import Transaction
from marketplace.services.listing_service import get_listing
from marketplace.services.payment_service import payment_service
from marketplace.services.storage_service import get_storage
from marketplace.services.verification_service import verify_content


def _broadcast(event_type: str, data: dict):
    """Fire-and-forget WebSocket broadcast."""
    try:
        from marketplace.main import broadcast_event

        fire_and_forget(broadcast_event(event_type, data), task_name=f"broadcast_{event_type}")
    except Exception:
        pass


async def initiate_transaction(
    db: AsyncSession, listing_id: str, buyer_id: str
) -> dict:
    """Start a purchase. Returns transaction + payment requirements."""
    listing = await get_listing(db, listing_id)

    # Get seller wallet address
    from marketplace.services.registry_service import get_agent
    seller = await get_agent(db, listing.seller_id)

    tx = Transaction(
        listing_id=listing.id,
        buyer_id=buyer_id,
        seller_id=listing.seller_id,
        amount_usdc=float(listing.price_usdc),
        status="payment_pending",
        content_hash=listing.content_hash,
    )
    db.add(tx)
    await db.commit()
    await db.refresh(tx)

    payment_details = payment_service.build_payment_requirements(
        amount_usdc=float(listing.price_usdc),
        seller_address=seller.wallet_address,
    )

    _broadcast("transaction_initiated", {
        "transaction_id": tx.id,
        "listing_id": listing.id,
        "buyer_id": buyer_id,
        "amount_usdc": float(listing.price_usdc),
    })

    return {
        "transaction_id": tx.id,
        "status": tx.status,
        "amount_usdc": float(tx.amount_usdc),
        "payment_details": payment_details,
        "content_hash": tx.content_hash,
    }


async def confirm_payment(
    db: AsyncSession,
    tx_id: str,
    payment_signature: str = "",
    payment_tx_hash: str = "",
    buyer_id: str | None = None,
) -> Transaction:
    """Confirm payment for a transaction."""
    tx = await _get_transaction(db, tx_id)
    if buyer_id and tx.buyer_id != buyer_id:
        from fastapi import HTTPException
        raise HTTPException(status_code=403, detail="Not the buyer for this transaction")
    if tx.status != "payment_pending":
        raise InvalidTransactionStateError(tx.status, "payment_pending")

    # Build requirements from transaction data
    from marketplace.services.registry_service import get_agent
    seller = await get_agent(db, tx.seller_id)
    requirements = payment_service.build_payment_requirements(
        float(tx.amount_usdc), seller.wallet_address
    )

    if payment_signature:
        result = payment_service.verify_payment(payment_signature, requirements)
        if not result.get("verified"):
            tx.status = "failed"
            tx.error_message = result.get("error", "Payment verification failed")
            await db.commit()
            await db.refresh(tx)
            return tx
        tx.payment_tx_hash = result.get("tx_hash", "")
    elif payment_tx_hash:
        tx.payment_tx_hash = payment_tx_hash
    else:
        # Simulated mode: auto-confirm
        result = payment_service.verify_payment("", requirements)
        tx.payment_tx_hash = result.get("tx_hash", "sim_auto")

    tx.status = "payment_confirmed"
    tx.paid_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(tx)

    _broadcast("payment_confirmed", {
        "transaction_id": tx.id,
        "buyer_id": tx.buyer_id,
        "seller_id": tx.seller_id,
        "amount_usdc": float(tx.amount_usdc),
    })

    return tx


async def deliver_content(
    db: AsyncSession, tx_id: str, content: str, seller_id: str
) -> Transaction:
    """Seller delivers content for a transaction."""
    tx = await _get_transaction(db, tx_id)
    if tx.seller_id != seller_id:
        from fastapi import HTTPException, status
        raise HTTPException(status_code=403, detail="Not the seller for this transaction")
    if tx.status != "payment_confirmed":
        raise InvalidTransactionStateError(tx.status, "payment_confirmed")

    storage = get_storage()
    content_bytes = content.encode("utf-8")
    delivered_hash = storage.compute_hash(content_bytes)

    tx.delivered_hash = delivered_hash
    tx.status = "delivered"
    tx.delivered_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(tx)

    _broadcast("content_delivered", {
        "transaction_id": tx.id,
        "seller_id": seller_id,
        "buyer_id": tx.buyer_id,
    })

    return tx


async def verify_delivery(db: AsyncSession, tx_id: str, buyer_id: str) -> Transaction:
    """Buyer verifies the delivered content matches expected hash."""
    tx = await _get_transaction(db, tx_id)
    if tx.buyer_id != buyer_id:
        from fastapi import HTTPException, status
        raise HTTPException(status_code=403, detail="Not the buyer for this transaction")
    if tx.status != "delivered":
        raise InvalidTransactionStateError(tx.status, "delivered")

    # Get the delivered content from storage
    storage = get_storage()
    if tx.delivered_hash and tx.content_hash:
        matches = tx.delivered_hash == tx.content_hash
    else:
        matches = False

    if matches:
        tx.verification_status = "verified"
        tx.status = "completed"
        tx.verified_at = datetime.now(timezone.utc)
        tx.completed_at = datetime.now(timezone.utc)

        # Increment listing access count
        listing = await get_listing(db, tx.listing_id)
        listing.access_count += 1
    else:
        tx.verification_status = "failed"
        tx.status = "disputed"
        tx.error_message = f"Hash mismatch: expected {tx.content_hash}, got {tx.delivered_hash}"

    await db.commit()
    await db.refresh(tx)

    _broadcast("transaction_completed" if matches else "transaction_disputed", {
        "transaction_id": tx.id,
        "buyer_id": buyer_id,
        "seller_id": tx.seller_id,
        "verified": matches,
        "amount_usdc": float(tx.amount_usdc),
    })

    return tx


async def get_transaction(db: AsyncSession, tx_id: str) -> Transaction:
    """Public getter for a transaction."""
    return await _get_transaction(db, tx_id)


async def list_transactions(
    db: AsyncSession,
    agent_id: str | None = None,
    status_filter: str | None = None,
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[Transaction], int]:
    """List transactions, optionally filtered by agent (as buyer or seller)."""
    query = select(Transaction)
    count_query = select(func.count(Transaction.id))

    if agent_id:
        cond = (Transaction.buyer_id == agent_id) | (Transaction.seller_id == agent_id)
        query = query.where(cond)
        count_query = count_query.where(cond)

    if status_filter:
        query = query.where(Transaction.status == status_filter)
        count_query = count_query.where(Transaction.status == status_filter)

    total = (await db.execute(count_query)).scalar() or 0

    query = query.order_by(Transaction.initiated_at.desc())
    query = query.offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(query)
    txns = list(result.scalars().all())

    return txns, total


async def _get_transaction(db: AsyncSession, tx_id: str) -> Transaction:
    result = await db.execute(
        select(Transaction).where(Transaction.id == tx_id)
    )
    tx = result.scalar_one_or_none()
    if not tx:
        raise TransactionNotFoundError(tx_id)
    return tx
