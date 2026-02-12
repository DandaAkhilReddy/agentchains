"""Deep tests for services/redemption_service.py — 25 tests covering all 11 functions.

Tests:
  1  test_create_api_credits_auto_completes       — api_credits auto-processes to "completed"
  2  test_create_gift_card_pending                 — gift_card stays "pending"
  3  test_create_upi_pending                       — upi stays "pending"
  4  test_create_bank_withdrawal_pending           — bank_withdrawal stays "pending"
  5  test_create_below_minimum_api_credits         — 50 ARD < 100 min -> ValueError
  6  test_create_below_minimum_gift_card           — 500 ARD < 1000 min -> ValueError
  7  test_create_insufficient_balance              — amount > balance -> ValueError
  8  test_create_no_account                        — nonexistent creator -> ValueError
  9  test_create_invalid_type                      — "bitcoin" -> ValueError
  10 test_create_debits_balance                    — balance reduced after creation
  11 test_process_api_credits_upserts              — first creates, second adds to existing
  12 test_process_gift_card_to_processing          — status -> "processing"
  13 test_process_bank_to_processing               — status -> "processing"
  14 test_process_upi_to_processing                — status -> "processing"
  15 test_cancel_refunds_balance                   — balance restored after cancel
  16 test_cancel_creates_refund_ledger             — refund ledger entry created
  17 test_cancel_wrong_status                      — cancel completed -> ValueError
  18 test_cancel_wrong_creator                     — another creator's redemption -> ValueError
  19 test_admin_approve_routes_correctly            — approve gift_card -> processing
  20 test_admin_approve_api_credits                — approve api_credits -> completed
  21 test_admin_reject_refunds                     — balance restored after reject
  22 test_admin_reject_sets_reason                 — rejection_reason populated
  23 test_list_redemptions_pagination              — page/page_size work
  24 test_list_redemptions_status_filter           — filter by "completed"
  25 test_get_redemption_methods                   — returns 4 methods with correct thresholds
"""

import uuid
from decimal import Decimal

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from marketplace.models.token_account import TokenAccount, TokenLedger
from marketplace.models.redemption import RedemptionRequest, ApiCreditBalance
from marketplace.services import redemption_service


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _new_id() -> str:
    return str(uuid.uuid4())


async def _make_creator_with_balance(
    db: AsyncSession,
    make_creator,
    balance: float = 50_000.0,
) -> tuple:
    """Create a Creator + TokenAccount with the given ARD balance.

    Returns (creator, token, token_account).
    """
    creator, token = await make_creator()

    account = TokenAccount(
        id=_new_id(),
        creator_id=creator.id,
        balance=Decimal(str(balance)),
        total_deposited=Decimal(str(balance)),
    )
    db.add(account)
    await db.commit()
    await db.refresh(account)
    return creator, token, account


async def _get_account(db: AsyncSession, creator_id: str) -> TokenAccount:
    """Fetch the TokenAccount for a given creator."""
    result = await db.execute(
        select(TokenAccount).where(TokenAccount.creator_id == creator_id)
    )
    return result.scalar_one()


# ===========================================================================
# 1-4: Create redemption — status checks per type
# ===========================================================================


class TestCreateRedemptionStatus:
    """Verify that each redemption type produces the correct initial status."""

    # 1
    async def test_create_api_credits_auto_completes(self, db, make_creator):
        """api_credits is auto-processed: returned status must be 'completed', not 'pending'."""
        creator, _, _ = await _make_creator_with_balance(db, make_creator, 500.0)

        result = await redemption_service.create_redemption(
            db, creator.id, "api_credits", 200.0,
        )

        assert result["status"] == "completed"
        assert result["redemption_type"] == "api_credits"
        assert result["payout_ref"] == "api_credits_200"
        # amount_fiat should be None for api_credits
        assert result["amount_fiat"] is None

    # 2
    async def test_create_gift_card_pending(self, db, make_creator):
        """gift_card type should remain 'pending' until admin action."""
        creator, _, _ = await _make_creator_with_balance(db, make_creator, 5_000.0)

        result = await redemption_service.create_redemption(
            db, creator.id, "gift_card", 1_000.0,
        )

        assert result["status"] == "pending"
        assert result["redemption_type"] == "gift_card"
        assert result["amount_fiat"] is not None

    # 3
    async def test_create_upi_pending(self, db, make_creator):
        """upi type should remain 'pending' until admin action."""
        creator, _, _ = await _make_creator_with_balance(db, make_creator, 20_000.0)

        result = await redemption_service.create_redemption(
            db, creator.id, "upi", 5_000.0,
        )

        assert result["status"] == "pending"
        assert result["redemption_type"] == "upi"

    # 4
    async def test_create_bank_withdrawal_pending(self, db, make_creator):
        """bank_withdrawal type should remain 'pending' until admin action."""
        creator, _, _ = await _make_creator_with_balance(db, make_creator, 50_000.0)

        result = await redemption_service.create_redemption(
            db, creator.id, "bank_withdrawal", 10_000.0,
        )

        assert result["status"] == "pending"
        assert result["redemption_type"] == "bank_withdrawal"


# ===========================================================================
# 5-9: Validation errors
# ===========================================================================


class TestCreateRedemptionValidation:
    """Verify that validation rules reject bad inputs with ValueError."""

    # 5
    async def test_create_below_minimum_api_credits(self, db, make_creator):
        """50 ARD is below the 100 ARD minimum for api_credits."""
        creator, _, _ = await _make_creator_with_balance(db, make_creator, 500.0)

        with pytest.raises(ValueError, match="Minimum for api_credits is 100 ARD"):
            await redemption_service.create_redemption(
                db, creator.id, "api_credits", 50.0,
            )

    # 6
    async def test_create_below_minimum_gift_card(self, db, make_creator):
        """500 ARD is below the 1000 ARD minimum for gift_card."""
        creator, _, _ = await _make_creator_with_balance(db, make_creator, 5_000.0)

        with pytest.raises(ValueError, match="Minimum for gift_card is 1000 ARD"):
            await redemption_service.create_redemption(
                db, creator.id, "gift_card", 500.0,
            )

    # 7
    async def test_create_insufficient_balance(self, db, make_creator):
        """Requesting more ARD than the creator's balance raises ValueError."""
        creator, _, _ = await _make_creator_with_balance(db, make_creator, 50.0)

        with pytest.raises(ValueError, match="Insufficient balance"):
            await redemption_service.create_redemption(
                db, creator.id, "api_credits", 100.0,
            )

    # 8
    async def test_create_no_account(self, db):
        """A creator_id with no TokenAccount row at all raises ValueError."""
        fake_creator_id = _new_id()

        with pytest.raises(ValueError, match="no token account"):
            await redemption_service.create_redemption(
                db, fake_creator_id, "api_credits", 100.0,
            )

    # 9
    async def test_create_invalid_type(self, db, make_creator):
        """An unrecognized redemption type raises ValueError."""
        creator, _, _ = await _make_creator_with_balance(db, make_creator, 50_000.0)

        with pytest.raises(ValueError, match="Invalid redemption type"):
            await redemption_service.create_redemption(
                db, creator.id, "bitcoin", 500.0,
            )


# ===========================================================================
# 10: Balance debit side-effect
# ===========================================================================


class TestCreateRedemptionDebit:
    """Verify that creating a redemption debits the creator's balance."""

    # 10
    async def test_create_debits_balance(self, db, make_creator):
        """Creator's balance should be reduced by the redeemed amount."""
        creator, _, acct = await _make_creator_with_balance(db, make_creator, 5_000.0)

        await redemption_service.create_redemption(
            db, creator.id, "gift_card", 2_000.0,
        )

        await db.refresh(acct)
        assert float(acct.balance) == pytest.approx(3_000.0, abs=0.01)
        assert float(acct.total_spent) == pytest.approx(2_000.0, abs=0.01)


# ===========================================================================
# 11-14: Individual processor functions
# ===========================================================================


class TestProcessors:
    """Verify each processor function transitions the redemption correctly."""

    # 11
    async def test_process_api_credits_upserts(self, db, make_creator):
        """First redemption creates ApiCreditBalance; second adds to existing row."""
        creator, _, _ = await _make_creator_with_balance(db, make_creator, 1_000.0)

        # First api_credits redemption (auto-completes via create_redemption)
        r1 = await redemption_service.create_redemption(
            db, creator.id, "api_credits", 200.0,
        )
        assert r1["status"] == "completed"

        # Verify first credit balance
        credit = (await db.execute(
            select(ApiCreditBalance).where(
                ApiCreditBalance.creator_id == creator.id,
            )
        )).scalar_one()
        assert int(credit.credits_remaining) == 200
        assert int(credit.credits_total_purchased) == 200

        # Second api_credits redemption — should upsert (add to existing)
        r2 = await redemption_service.create_redemption(
            db, creator.id, "api_credits", 300.0,
        )
        assert r2["status"] == "completed"

        await db.refresh(credit)
        assert int(credit.credits_remaining) == 500
        assert int(credit.credits_total_purchased) == 500

    # 12
    async def test_process_gift_card_to_processing(self, db, make_creator):
        """process_gift_card_redemption moves status from pending to processing."""
        creator, _, _ = await _make_creator_with_balance(db, make_creator, 5_000.0)

        created = await redemption_service.create_redemption(
            db, creator.id, "gift_card", 1_000.0,
        )
        assert created["status"] == "pending"

        result = await redemption_service.process_gift_card_redemption(
            db, created["id"],
        )

        assert result["status"] == "processing"
        assert "Amazon" in (result["admin_notes"] or "")

    # 13
    async def test_process_bank_to_processing(self, db, make_creator):
        """process_bank_withdrawal moves status to processing with admin_notes."""
        creator, _, _ = await _make_creator_with_balance(db, make_creator, 50_000.0)

        created = await redemption_service.create_redemption(
            db, creator.id, "bank_withdrawal", 10_000.0,
        )
        assert created["status"] == "pending"

        result = await redemption_service.process_bank_withdrawal(
            db, created["id"],
        )

        assert result["status"] == "processing"
        assert "3-7 business days" in (result["admin_notes"] or "")

    # 14
    async def test_process_upi_to_processing(self, db, make_creator):
        """process_upi_transfer moves status to processing."""
        creator, _, _ = await _make_creator_with_balance(db, make_creator, 20_000.0)

        created = await redemption_service.create_redemption(
            db, creator.id, "upi", 5_000.0,
        )
        assert created["status"] == "pending"

        result = await redemption_service.process_upi_transfer(
            db, created["id"],
        )

        assert result["status"] == "processing"
        assert "UPI" in (result["admin_notes"] or "")


# ===========================================================================
# 15-18: Cancel redemption
# ===========================================================================


class TestCancelRedemption:
    """Verify cancel_redemption refund logic and error conditions."""

    # 15
    async def test_cancel_refunds_balance(self, db, make_creator):
        """Cancelling a pending redemption fully restores the creator's balance."""
        creator, _, acct = await _make_creator_with_balance(db, make_creator, 5_000.0)

        created = await redemption_service.create_redemption(
            db, creator.id, "gift_card", 2_000.0,
        )
        assert created["status"] == "pending"

        # Balance should be debited
        await db.refresh(acct)
        assert float(acct.balance) == pytest.approx(3_000.0, abs=0.01)

        # Cancel the redemption
        cancelled = await redemption_service.cancel_redemption(
            db, created["id"], creator.id,
        )
        assert cancelled["status"] == "rejected"
        assert cancelled["rejection_reason"] == "Cancelled by creator"

        # Balance should be fully restored
        await db.refresh(acct)
        assert float(acct.balance) == pytest.approx(5_000.0, abs=0.01)

    # 16
    async def test_cancel_creates_refund_ledger(self, db, make_creator):
        """Cancelling a pending redemption creates a refund TokenLedger entry."""
        creator, _, acct = await _make_creator_with_balance(db, make_creator, 5_000.0)

        created = await redemption_service.create_redemption(
            db, creator.id, "gift_card", 1_000.0,
        )

        await redemption_service.cancel_redemption(
            db, created["id"], creator.id,
        )

        # Query for refund ledger entries
        refund_result = await db.execute(
            select(TokenLedger).where(
                TokenLedger.to_account_id == acct.id,
                TokenLedger.tx_type == "refund",
                TokenLedger.reference_type == "redemption_cancel",
            )
        )
        refund = refund_result.scalar_one_or_none()
        assert refund is not None
        assert float(refund.amount) == pytest.approx(1_000.0, abs=0.01)
        assert refund.reference_id == created["id"]

    # 17
    async def test_cancel_wrong_status(self, db, make_creator):
        """Cannot cancel a completed (api_credits auto-processed) redemption."""
        creator, _, _ = await _make_creator_with_balance(db, make_creator, 500.0)

        created = await redemption_service.create_redemption(
            db, creator.id, "api_credits", 200.0,
        )
        assert created["status"] == "completed"

        with pytest.raises(ValueError, match="Cannot cancel redemption"):
            await redemption_service.cancel_redemption(
                db, created["id"], creator.id,
            )

    # 18
    async def test_cancel_wrong_creator(self, db, make_creator):
        """A different creator cannot cancel someone else's redemption."""
        creator_a, _, _ = await _make_creator_with_balance(db, make_creator, 5_000.0)
        creator_b, _, _ = await _make_creator_with_balance(db, make_creator, 5_000.0)

        created = await redemption_service.create_redemption(
            db, creator_a.id, "gift_card", 1_000.0,
        )
        assert created["status"] == "pending"

        # Creator B tries to cancel Creator A's redemption
        with pytest.raises(ValueError, match="Redemption not found"):
            await redemption_service.cancel_redemption(
                db, created["id"], creator_b.id,
            )


# ===========================================================================
# 19-22: Admin approve / reject
# ===========================================================================


class TestAdminActions:
    """Verify admin_approve_redemption and admin_reject_redemption."""

    # 19
    async def test_admin_approve_routes_correctly(self, db, make_creator):
        """admin_approve on a gift_card routes to process_gift_card -> 'processing'."""
        creator, _, _ = await _make_creator_with_balance(db, make_creator, 5_000.0)

        created = await redemption_service.create_redemption(
            db, creator.id, "gift_card", 1_000.0,
        )
        assert created["status"] == "pending"

        result = await redemption_service.admin_approve_redemption(
            db, created["id"], admin_notes="Approved by admin",
        )

        assert result["status"] == "processing"
        assert result["redemption_type"] == "gift_card"

    # 20
    async def test_admin_approve_api_credits(self, db, make_creator):
        """admin_approve on an api_credits type routes to process_api_credit -> 'completed'."""
        creator, _, _ = await _make_creator_with_balance(db, make_creator, 500.0)

        # Manually create a pending api_credits redemption by creating gift_card first
        # then changing type — but simpler: just create api_credits which auto-completes.
        # Instead, we create a pending redemption record directly.
        redemption = RedemptionRequest(
            id=_new_id(),
            creator_id=creator.id,
            redemption_type="api_credits",
            amount_ard=Decimal("200"),
            amount_fiat=None,
            currency="USD",
            status="pending",
        )
        db.add(redemption)

        # Also debit the account manually to simulate the hold
        acct = await _get_account(db, creator.id)
        acct.balance = Decimal(str(float(acct.balance) - 200.0))
        await db.commit()
        await db.refresh(redemption)

        result = await redemption_service.admin_approve_redemption(
            db, redemption.id,
        )

        assert result["status"] == "completed"
        assert result["payout_ref"] == "api_credits_200"

    # 21
    async def test_admin_reject_refunds(self, db, make_creator):
        """admin_reject refunds the ARD to the creator's balance."""
        creator, _, acct = await _make_creator_with_balance(db, make_creator, 5_000.0)

        created = await redemption_service.create_redemption(
            db, creator.id, "gift_card", 1_000.0,
        )

        await db.refresh(acct)
        assert float(acct.balance) == pytest.approx(4_000.0, abs=0.01)

        rejected = await redemption_service.admin_reject_redemption(
            db, created["id"], reason="Policy violation",
        )
        assert rejected["status"] == "rejected"

        # Balance should be restored
        await db.refresh(acct)
        assert float(acct.balance) == pytest.approx(5_000.0, abs=0.01)

    # 22
    async def test_admin_reject_sets_reason(self, db, make_creator):
        """admin_reject populates the rejection_reason field."""
        creator, _, _ = await _make_creator_with_balance(db, make_creator, 5_000.0)

        created = await redemption_service.create_redemption(
            db, creator.id, "gift_card", 1_000.0,
        )

        rejected = await redemption_service.admin_reject_redemption(
            db, created["id"], reason="Suspicious activity detected",
        )

        assert rejected["rejection_reason"] == "Suspicious activity detected"
        assert rejected["status"] == "rejected"

        # Verify in the database as well
        row = (await db.execute(
            select(RedemptionRequest).where(
                RedemptionRequest.id == created["id"],
            )
        )).scalar_one()
        assert row.rejection_reason == "Suspicious activity detected"


# ===========================================================================
# 23-24: List redemptions
# ===========================================================================


class TestListRedemptions:
    """Verify list_redemptions pagination and status filtering."""

    # 23
    async def test_list_redemptions_pagination(self, db, make_creator):
        """Pagination returns correct page, page_size, total, and entry counts."""
        creator, _, _ = await _make_creator_with_balance(db, make_creator, 50_000.0)

        # Create 5 gift_card redemptions (all stay pending)
        for _ in range(5):
            await redemption_service.create_redemption(
                db, creator.id, "gift_card", 1_000.0,
            )

        # Page 1 with page_size=2
        page1 = await redemption_service.list_redemptions(
            db, creator.id, page=1, page_size=2,
        )
        assert page1["total"] == 5
        assert page1["page"] == 1
        assert page1["page_size"] == 2
        assert len(page1["redemptions"]) == 2

        # Page 3 with page_size=2 should have 1 remaining entry
        page3 = await redemption_service.list_redemptions(
            db, creator.id, page=3, page_size=2,
        )
        assert len(page3["redemptions"]) == 1

    # 24
    async def test_list_redemptions_status_filter(self, db, make_creator):
        """Filtering by status='completed' returns only completed redemptions."""
        creator, _, _ = await _make_creator_with_balance(db, make_creator, 50_000.0)

        # Create 2 api_credits (auto-completed) and 2 gift_cards (pending)
        for _ in range(2):
            r = await redemption_service.create_redemption(
                db, creator.id, "api_credits", 200.0,
            )
            assert r["status"] == "completed"

        for _ in range(2):
            r = await redemption_service.create_redemption(
                db, creator.id, "gift_card", 1_000.0,
            )
            assert r["status"] == "pending"

        # Filter by completed
        completed = await redemption_service.list_redemptions(
            db, creator.id, status="completed",
        )
        assert completed["total"] == 2
        assert len(completed["redemptions"]) == 2
        assert all(r["status"] == "completed" for r in completed["redemptions"])

        # Filter by pending
        pending = await redemption_service.list_redemptions(
            db, creator.id, status="pending",
        )
        assert pending["total"] == 2
        assert all(r["status"] == "pending" for r in pending["redemptions"])


# ===========================================================================
# 25: get_redemption_methods
# ===========================================================================


class TestGetRedemptionMethods:
    """Verify get_redemption_methods returns complete, correct data."""

    # 25
    async def test_get_redemption_methods(self):
        """Returns all 4 methods with correct thresholds and metadata."""
        data = await redemption_service.get_redemption_methods()

        assert "methods" in data
        assert len(data["methods"]) == 4

        # Verify all types are present
        types = {m["type"] for m in data["methods"]}
        assert types == {"api_credits", "gift_card", "upi", "bank_withdrawal"}

        # Verify thresholds
        by_type = {m["type"]: m for m in data["methods"]}
        assert by_type["api_credits"]["min_ard"] == 100.0
        assert by_type["gift_card"]["min_ard"] == 1_000.0
        assert by_type["upi"]["min_ard"] == 5_000.0
        assert by_type["bank_withdrawal"]["min_ard"] == 10_000.0

        # Verify each method has required fields
        for method in data["methods"]:
            assert "type" in method
            assert "label" in method
            assert "description" in method
            assert "min_ard" in method
            assert "min_usd" in method
            assert "processing_time" in method
            assert method["min_ard"] > 0
            assert method["min_usd"] >= 0

        # Verify token metadata
        assert "token_name" in data
        assert "peg_rate_usd" in data
        assert data["peg_rate_usd"] > 0
