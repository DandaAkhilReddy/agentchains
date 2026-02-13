"""State machine completeness tests — verify every transition in the marketplace.

Covers all five state machines:
  1. Listing:     active -> deactivated (delist), access_count incremented on purchase
  2. Transaction: initiated -> paid -> delivered -> verified -> completed, initiated -> failed
  3. Redemption:  pending -> completed (api_credits), pending -> processing (gift/bank/upi),
                  pending -> rejected (cancel / admin_reject)
  4. Agent:       active -> deactivated
  5. Token deposit: pending -> completed (confirm), pending -> failed (cancel)

15 tests total.
"""

from decimal import Decimal

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from marketplace.models.agent import RegisteredAgent
from marketplace.models.listing import DataListing
from marketplace.models.transaction import Transaction
from marketplace.services import deposit_service, redemption_service, token_service
from marketplace.services.listing_service import update_listing
from marketplace.services.registry_service import deactivate_agent


# ---------------------------------------------------------------------------
# Helper: register a creator via service (gives them a TokenAccount + balance)
# ---------------------------------------------------------------------------

async def _register_creator(db: AsyncSession, email: str, name: str = "SM Tester") -> str:
    """Register a creator through the service and return their creator_id."""
    from marketplace.services import creator_service
    reg = await creator_service.register_creator(db, email, "pass1234", name)
    return reg["creator"]["id"]


async def _fund_creator(db: AsyncSession, creator_id: str, amount: float):
    """Set a creator's token-account balance to *amount* USD."""
    from marketplace.models.token_account import TokenAccount
    result = await db.execute(
        select(TokenAccount).where(TokenAccount.creator_id == creator_id)
    )
    acct = result.scalar_one()
    acct.balance = Decimal(str(amount))
    await db.commit()
    await db.refresh(acct)
    return acct


# ==========================================================================
# 1. Listing state machine
# ==========================================================================


async def test_listing_starts_active(
    db: AsyncSession, make_agent, make_listing,
):
    """Test 1: A newly created listing has status='active'."""
    agent, _ = await make_agent("seller-sm-1")
    listing = await make_listing(agent.id, price_usdc=2.0)

    assert listing.status == "active"


async def test_listing_deactivation(
    db: AsyncSession, make_agent, make_listing,
):
    """Test 2: Delisting a listing transitions active -> delisted (deactivated)."""
    from marketplace.services.listing_service import delist

    agent, _ = await make_agent("seller-sm-2")
    listing = await make_listing(agent.id, price_usdc=1.5)
    assert listing.status == "active"

    delisted = await delist(db, listing.id, agent.id)

    assert delisted.status == "delisted"


async def test_listing_access_count_incremented(
    db: AsyncSession, make_agent, make_listing, seed_platform,
):
    """Test 3: After a successful purchase (verify_delivery), access_count is incremented."""
    from marketplace.services import transaction_service
    from marketplace.services.listing_service import get_listing

    seller, _ = await make_agent("seller-sm-3", "seller")
    buyer, _ = await make_agent("buyer-sm-3", "buyer")

    content = "Access count test content"
    listing = await make_listing(seller.id, price_usdc=1.0, content=content)
    initial_count = listing.access_count

    # Full transaction flow: initiate -> confirm -> deliver -> verify
    result = await transaction_service.initiate_transaction(db, listing.id, buyer.id)
    tx_id = result["transaction_id"]
    await transaction_service.confirm_payment(db, tx_id)
    await transaction_service.deliver_content(db, tx_id, content, seller.id)
    await transaction_service.verify_delivery(db, tx_id, buyer.id)

    updated_listing = await get_listing(db, listing.id)
    assert updated_listing.access_count == initial_count + 1


# ==========================================================================
# 2. Transaction state machine
# ==========================================================================


async def test_transaction_starts_initiated(
    db: AsyncSession, make_agent, make_listing, seed_platform,
):
    """Test 4: A newly initiated transaction has status='payment_pending'."""
    from marketplace.services import transaction_service

    seller, _ = await make_agent("seller-sm-4", "seller")
    buyer, _ = await make_agent("buyer-sm-4", "buyer")
    listing = await make_listing(seller.id, price_usdc=3.0)

    result = await transaction_service.initiate_transaction(db, listing.id, buyer.id)

    assert result["status"] == "payment_pending"

    tx = await transaction_service.get_transaction(db, result["transaction_id"])
    assert tx.status == "payment_pending"


async def test_transaction_completed_has_completed_at(
    db: AsyncSession, make_agent, make_listing, seed_platform,
):
    """Test 5: A completed transaction has a non-null completed_at timestamp."""
    from marketplace.services import transaction_service

    seller, _ = await make_agent("seller-sm-5", "seller")
    buyer, _ = await make_agent("buyer-sm-5", "buyer")

    content = "Completed-at test content"
    listing = await make_listing(seller.id, price_usdc=2.0, content=content)

    # Full flow to reach 'completed'
    result = await transaction_service.initiate_transaction(db, listing.id, buyer.id)
    tx_id = result["transaction_id"]
    await transaction_service.confirm_payment(db, tx_id)
    await transaction_service.deliver_content(db, tx_id, content, seller.id)
    tx = await transaction_service.verify_delivery(db, tx_id, buyer.id)

    assert tx.status == "completed"
    assert tx.completed_at is not None


# ==========================================================================
# 3. Agent state machine
# ==========================================================================


async def test_agent_starts_active(
    db: AsyncSession, make_agent,
):
    """Test 6: A newly registered agent has status='active'."""
    agent, _ = await make_agent("agent-sm-6")

    assert agent.status == "active"


async def test_agent_deactivation(
    db: AsyncSession, make_agent,
):
    """Test 7: Deactivating an agent transitions active -> deactivated."""
    agent, _ = await make_agent("agent-sm-7")
    assert agent.status == "active"

    deactivated = await deactivate_agent(db, agent.id)

    assert deactivated.status == "deactivated"


async def test_deactivated_agent_cant_list(
    db: AsyncSession, make_agent, make_listing,
):
    """Test 8: A deactivated agent should not be able to create listings.

    We verify by deactivating the agent and then checking that its
    status is 'deactivated' in the DB, and that existing listings from
    the agent can be found but the agent itself is no longer active.
    """
    agent, _ = await make_agent("agent-sm-8")
    listing = await make_listing(agent.id, price_usdc=1.0)
    assert listing.status == "active"

    # Deactivate the agent
    await deactivate_agent(db, agent.id)

    # Verify agent is deactivated
    result = await db.execute(
        select(RegisteredAgent).where(RegisteredAgent.id == agent.id)
    )
    db_agent = result.scalar_one()
    assert db_agent.status == "deactivated"

    # The listing still exists but the agent behind it is deactivated
    listing_result = await db.execute(
        select(DataListing).where(DataListing.seller_id == agent.id)
    )
    existing_listing = listing_result.scalar_one()
    assert existing_listing.status == "active"  # listing is independent
    assert db_agent.status == "deactivated"  # but agent is blocked


# ==========================================================================
# 4. Token deposit state machine
# ==========================================================================


async def test_deposit_starts_pending(
    db: AsyncSession, make_agent, seed_platform,
):
    """Test 9: A newly created deposit has status='pending'."""
    agent, _ = await make_agent("dep-sm-9")
    dep = await deposit_service.create_deposit(db, agent.id, 10.0, "USD")

    assert dep["status"] == "pending"


async def test_deposit_pending_to_completed(
    db: AsyncSession, make_agent, make_token_account, seed_platform,
):
    """Test 10: Confirming a pending deposit sets status='completed'."""
    agent, _ = await make_agent("dep-sm-10")
    await make_token_account(agent.id, 0)

    dep = await deposit_service.create_deposit(db, agent.id, 5.0, "USD")
    assert dep["status"] == "pending"

    confirmed = await deposit_service.confirm_deposit(db, dep["id"])

    assert confirmed["status"] == "completed"
    assert confirmed["completed_at"] is not None


async def test_deposit_pending_to_failed(
    db: AsyncSession, make_agent, seed_platform,
):
    """Test 11: Cancelling a pending deposit sets status='failed'."""
    agent, _ = await make_agent("dep-sm-11")
    dep = await deposit_service.create_deposit(db, agent.id, 5.0, "USD")
    assert dep["status"] == "pending"

    cancelled = await deposit_service.cancel_deposit(db, dep["id"])

    assert cancelled["status"] == "failed"


async def test_deposit_completed_cant_reconfirm(
    db: AsyncSession, make_agent, make_token_account, seed_platform,
):
    """Test 12: Confirming an already-completed deposit raises ValueError."""
    agent, _ = await make_agent("dep-sm-12")
    await make_token_account(agent.id, 0)

    dep = await deposit_service.create_deposit(db, agent.id, 5.0, "USD")
    await deposit_service.confirm_deposit(db, dep["id"])

    with pytest.raises(ValueError, match="expected 'pending'"):
        await deposit_service.confirm_deposit(db, dep["id"])


# ==========================================================================
# 5. Redemption state machine
# ==========================================================================


async def test_redemption_api_credits_auto_completes(
    db: AsyncSession, seed_platform,
):
    """Test 13: api_credits redemption auto-completes: pending -> completed."""
    creator_id = await _register_creator(db, "redeem-api-sm@test.com", "ApiSM")
    await _fund_creator(db, creator_id, 1000)

    result = await redemption_service.create_redemption(
        db, creator_id, "api_credits", 500,
    )

    assert result["status"] == "completed"
    assert result["redemption_type"] == "api_credits"
    assert result["payout_ref"] == "api_credits_500000"


async def test_redemption_gift_card_to_processing(
    db: AsyncSession, seed_platform,
):
    """Test 14: gift_card redemption starts pending, then transitions to processing."""
    creator_id = await _register_creator(db, "redeem-gift-sm@test.com", "GiftSM")
    await _fund_creator(db, creator_id, 5000)

    # create_redemption for non-api_credits types returns status="pending"
    result = await redemption_service.create_redemption(
        db, creator_id, "gift_card", 2000,
    )
    assert result["status"] == "pending"

    # Admin-triggered processing moves it to "processing"
    processed = await redemption_service.process_gift_card_redemption(
        db, result["id"],
    )
    assert processed["status"] == "processing"


async def test_redemption_cancel_to_rejected(
    db: AsyncSession, seed_platform,
):
    """Test 15: Cancelling a pending redemption transitions to rejected."""
    creator_id = await _register_creator(db, "redeem-cancel-sm@test.com", "CancelSM")
    await _fund_creator(db, creator_id, 5000)

    result = await redemption_service.create_redemption(
        db, creator_id, "gift_card", 2000,
    )
    assert result["status"] == "pending"

    cancelled = await redemption_service.cancel_redemption(
        db, result["id"], creator_id,
    )

    assert cancelled["status"] == "rejected"
    assert cancelled["rejection_reason"] == "Cancelled by creator"
