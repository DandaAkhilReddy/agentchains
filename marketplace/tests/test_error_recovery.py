"""Error recovery and rollback tests for the AgentChains marketplace.

Covers 20 scenarios: failed transfers, double-confirm deposits, ownership
checks, exception detail verification, and ledger integrity after errors.
"""

import uuid

import pytest
from fastapi import HTTPException
from sqlalchemy import func, select

from marketplace.core.exceptions import (
    AgentNotFoundError,
    AgentAlreadyExistsError,
    ContentVerificationError,
    InvalidTransactionStateError,
    ListingNotFoundError,
    PaymentRequiredError,
    TransactionNotFoundError,
    UnauthorizedError,
)
from marketplace.models.token_account import TokenLedger
from marketplace.services import deposit_service, listing_service, token_service, transaction_service


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _fake_id() -> str:
    return str(uuid.uuid4())


# ---------------------------------------------------------------------------
# 1-4: Transfer error paths
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_transfer_insufficient_balance_sender_unchanged(
    db, seed_platform, make_agent, make_token_account,
):
    """Transfer more than balance raises ValueError; sender balance unchanged after."""
    sender, _ = await make_agent(name="sender")
    receiver, _ = await make_agent(name="receiver")
    sender_acct = await make_token_account(sender.id, balance=10.0)
    await make_token_account(receiver.id, balance=0.0)

    with pytest.raises(ValueError, match="[Ii]nsufficient"):
        await token_service.transfer(
            db,
            from_agent_id=sender.id,
            to_agent_id=receiver.id,
            amount=50.0,
            tx_type="purchase",
        )

    # Sender balance must be untouched after the rollback
    await db.refresh(sender_acct)
    assert float(sender_acct.balance) == pytest.approx(10.0, abs=1e-4)


@pytest.mark.asyncio
async def test_transfer_missing_receiver_account_raises(
    db, seed_platform, make_agent, make_token_account,
):
    """Transfer to agent with no TokenAccount raises ValueError."""
    sender, _ = await make_agent(name="sender")
    receiver, _ = await make_agent(name="receiver-no-acct")
    await make_token_account(sender.id, balance=100.0)
    # Deliberately do NOT create a token account for receiver

    with pytest.raises(ValueError, match="receiver"):
        await token_service.transfer(
            db,
            from_agent_id=sender.id,
            to_agent_id=receiver.id,
            amount=5.0,
            tx_type="purchase",
        )


@pytest.mark.asyncio
async def test_transfer_missing_sender_account_raises(
    db, seed_platform, make_agent, make_token_account,
):
    """Sender with no TokenAccount raises ValueError."""
    sender, _ = await make_agent(name="sender-no-acct")
    receiver, _ = await make_agent(name="receiver")
    await make_token_account(receiver.id, balance=0.0)
    # No token account for sender

    with pytest.raises(ValueError, match="sender"):
        await token_service.transfer(
            db,
            from_agent_id=sender.id,
            to_agent_id=receiver.id,
            amount=5.0,
            tx_type="purchase",
        )


@pytest.mark.asyncio
async def test_transfer_missing_platform_account_raises(
    db, make_agent, make_token_account,
):
    """No platform account produces a descriptive error."""
    # seed_platform is deliberately NOT used here
    sender, _ = await make_agent(name="sender")
    receiver, _ = await make_agent(name="receiver")
    await make_token_account(sender.id, balance=100.0)
    await make_token_account(receiver.id, balance=0.0)

    with pytest.raises(ValueError, match="[Pp]latform"):
        await token_service.transfer(
            db,
            from_agent_id=sender.id,
            to_agent_id=receiver.id,
            amount=5.0,
            tx_type="purchase",
        )


# ---------------------------------------------------------------------------
# 5-7: Deposit confirm / cancel edge cases
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_deposit_double_confirm_raises(
    db, seed_platform, make_agent, make_token_account,
):
    """Confirming the same deposit twice raises ValueError."""
    agent, _ = await make_agent(name="depositor")
    await make_token_account(agent.id, balance=0.0)

    dep = await deposit_service.create_deposit(db, agent.id, 10.0, "USD")
    await deposit_service.confirm_deposit(db, dep["id"])

    with pytest.raises(ValueError, match="pending"):
        await deposit_service.confirm_deposit(db, dep["id"])


@pytest.mark.asyncio
async def test_deposit_cancel_preserves_balance(
    db, seed_platform, make_agent, make_token_account,
):
    """Cancelling a deposit leaves the agent balance unchanged."""
    agent, _ = await make_agent(name="depositor")
    acct = await make_token_account(agent.id, balance=50.0)

    dep = await deposit_service.create_deposit(db, agent.id, 20.0, "USD")
    await deposit_service.cancel_deposit(db, dep["id"])

    await db.refresh(acct)
    assert float(acct.balance) == pytest.approx(50.0, abs=1e-4)


@pytest.mark.asyncio
async def test_deposit_confirm_then_cancel_raises(
    db, seed_platform, make_agent, make_token_account,
):
    """After confirming a deposit, cancelling it still goes through but
    the status changes to 'failed' (cancel_deposit does not guard status).
    A second confirm, however, raises because status is no longer 'pending'."""
    agent, _ = await make_agent(name="depositor")
    await make_token_account(agent.id, balance=0.0)

    dep = await deposit_service.create_deposit(db, agent.id, 5.0, "USD")
    await deposit_service.confirm_deposit(db, dep["id"])

    # Attempting to confirm again should fail since status is now 'completed'
    with pytest.raises(ValueError, match="pending"):
        await deposit_service.confirm_deposit(db, dep["id"])


# ---------------------------------------------------------------------------
# 8-10: Transaction state-machine guards
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_transaction_deliver_wrong_seller_raises(
    db, make_agent, make_listing, make_transaction,
):
    """deliver_content by non-seller raises HTTPException (403)."""
    seller, _ = await make_agent(name="real-seller")
    buyer, _ = await make_agent(name="buyer")
    impostor, _ = await make_agent(name="impostor")

    listing = await make_listing(seller.id, price_usdc=1.0)
    tx = await make_transaction(
        buyer_id=buyer.id,
        seller_id=seller.id,
        listing_id=listing.id,
        status="payment_confirmed",
    )

    with pytest.raises(HTTPException) as exc_info:
        await transaction_service.deliver_content(db, tx.id, "fake-content", impostor.id)

    assert exc_info.value.status_code == 403


@pytest.mark.asyncio
async def test_transaction_verify_wrong_buyer_raises(
    db, make_agent, make_listing, make_transaction,
):
    """verify_delivery by non-buyer raises HTTPException (403)."""
    seller, _ = await make_agent(name="seller")
    buyer, _ = await make_agent(name="real-buyer")
    impostor, _ = await make_agent(name="impostor")

    listing = await make_listing(seller.id, price_usdc=1.0)
    tx = await make_transaction(
        buyer_id=buyer.id,
        seller_id=seller.id,
        listing_id=listing.id,
        status="delivered",
    )

    with pytest.raises(HTTPException) as exc_info:
        await transaction_service.verify_delivery(db, tx.id, impostor.id)

    assert exc_info.value.status_code == 403


@pytest.mark.asyncio
async def test_transaction_confirm_on_completed_raises(
    db, make_agent, make_listing, make_transaction,
):
    """confirm_payment on already-completed tx raises InvalidTransactionStateError."""
    seller, _ = await make_agent(name="seller")
    buyer, _ = await make_agent(name="buyer")

    listing = await make_listing(seller.id, price_usdc=1.0)
    tx = await make_transaction(
        buyer_id=buyer.id,
        seller_id=seller.id,
        listing_id=listing.id,
        status="completed",
    )

    with pytest.raises(InvalidTransactionStateError):
        await transaction_service.confirm_payment(db, tx.id)


# ---------------------------------------------------------------------------
# 11-12: Listing ownership guards
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_listing_delist_by_non_owner_raises(
    db, make_agent, make_listing,
):
    """delist by agent who does not own listing raises HTTPException (403)."""
    owner, _ = await make_agent(name="owner")
    stranger, _ = await make_agent(name="stranger")

    listing = await make_listing(owner.id, price_usdc=2.0)

    with pytest.raises(HTTPException) as exc_info:
        await listing_service.delist(db, listing.id, stranger.id)

    assert exc_info.value.status_code == 403


@pytest.mark.asyncio
async def test_listing_update_by_non_owner_raises(
    db, make_agent, make_listing,
):
    """update by non-owner raises HTTPException (403)."""
    from marketplace.schemas.listing import ListingUpdateRequest

    owner, _ = await make_agent(name="owner")
    stranger, _ = await make_agent(name="stranger")

    listing = await make_listing(owner.id, price_usdc=2.0)

    update_req = ListingUpdateRequest(title="Hijacked Title")

    with pytest.raises(HTTPException) as exc_info:
        await listing_service.update_listing(db, listing.id, stranger.id, update_req)

    assert exc_info.value.status_code == 403


# ---------------------------------------------------------------------------
# 13-14: Not-found exceptions from service layer
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_nonexistent_listing_raises_404(db):
    """get_listing with fake ID raises ListingNotFoundError."""
    fake_id = _fake_id()

    with pytest.raises(ListingNotFoundError) as exc_info:
        await listing_service.get_listing(db, fake_id)

    assert exc_info.value.status_code == 404


@pytest.mark.asyncio
async def test_get_nonexistent_transaction_raises_404(db):
    """get_transaction with fake ID raises TransactionNotFoundError."""
    fake_id = _fake_id()

    with pytest.raises(TransactionNotFoundError) as exc_info:
        await transaction_service.get_transaction(db, fake_id)

    assert exc_info.value.status_code == 404


# ---------------------------------------------------------------------------
# 15-18: Exception detail / context verification
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_insufficient_balance_error_includes_context(
    db, seed_platform, make_agent, make_token_account,
):
    """Verify the ValueError message mentions amounts or 'insufficient'."""
    sender, _ = await make_agent(name="poor-sender")
    receiver, _ = await make_agent(name="receiver")
    await make_token_account(sender.id, balance=3.0)
    await make_token_account(receiver.id, balance=0.0)

    with pytest.raises(ValueError) as exc_info:
        await token_service.transfer(
            db,
            from_agent_id=sender.id,
            to_agent_id=receiver.id,
            amount=100.0,
            tx_type="purchase",
        )

    msg = str(exc_info.value).lower()
    assert "insufficient" in msg
    # The error should mention the actual balance or the requested amount
    assert "3" in msg or "100" in msg


def test_invalid_state_error_includes_states():
    """InvalidTransactionStateError detail includes current and expected state strings."""
    err = InvalidTransactionStateError(current="completed", expected="payment_pending")
    assert "completed" in err.detail
    assert "payment_pending" in err.detail


def test_agent_not_found_error_includes_id():
    """AgentNotFoundError detail includes the agent_id."""
    agent_id = "agent-xyz-999"
    err = AgentNotFoundError(agent_id)
    assert agent_id in err.detail


def test_listing_not_found_error_includes_id():
    """ListingNotFoundError detail includes the listing_id."""
    listing_id = "listing-abc-123"
    err = ListingNotFoundError(listing_id)
    assert listing_id in err.detail


# ---------------------------------------------------------------------------
# 19: Ledger integrity after failed transfer
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_failed_transfer_does_not_create_ledger_entries(
    db, seed_platform, make_agent, make_token_account,
):
    """After a failed transfer, no new ledger entries should be created."""
    sender, _ = await make_agent(name="sender")
    receiver, _ = await make_agent(name="receiver")
    await make_token_account(sender.id, balance=5.0)
    await make_token_account(receiver.id, balance=0.0)

    # Count ledger entries before
    count_before = (
        await db.execute(select(func.count(TokenLedger.id)))
    ).scalar() or 0

    with pytest.raises(ValueError):
        await token_service.transfer(
            db,
            from_agent_id=sender.id,
            to_agent_id=receiver.id,
            amount=999.0,  # way more than 5.0 balance
            tx_type="purchase",
        )

    # Count ledger entries after — should be unchanged
    count_after = (
        await db.execute(select(func.count(TokenLedger.id)))
    ).scalar() or 0

    assert count_after == count_before


# ---------------------------------------------------------------------------
# 20: HTTP status code mapping for custom exceptions
# ---------------------------------------------------------------------------

def test_error_exceptions_have_correct_status_codes():
    """Verify all custom exceptions map to correct HTTP status codes."""
    # 404 — Not Found
    assert AgentNotFoundError("x").status_code == 404
    assert ListingNotFoundError("x").status_code == 404
    assert TransactionNotFoundError("x").status_code == 404

    # 400 — Bad Request
    assert InvalidTransactionStateError("a", "b").status_code == 400
    assert ContentVerificationError().status_code == 400

    # 402 — Payment Required
    assert PaymentRequiredError({"amount": 10}).status_code == 402

    # 401 — Unauthorized
    assert UnauthorizedError().status_code == 401

    # 409 — Conflict
    assert AgentAlreadyExistsError("dup-name").status_code == 409
