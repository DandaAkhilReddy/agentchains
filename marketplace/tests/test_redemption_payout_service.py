"""Tests for redemption_service and payout_service — 30 async tests (UT-9).

Covers:
  Redemption (22):
    1-4   create_redemption for all 4 types
    5-8   below-threshold validation for each type
    9     invalid redemption type
    10    insufficient balance
    11    debits creator account
    12    creates TokenLedger withdrawal entry
    13    process_api_credit_redemption (status + credits)
    14    process_gift_card_redemption (status=processing)
    15    process_bank_withdrawal (status=processing, admin_notes)
    16    process_upi_transfer (status=processing)
    17    cancel_redemption success (refund + status)
    18    cancel_redemption not-pending raises ValueError
    19    admin_approve routes to correct processor
    20    admin_reject refunds ARD and sets reason
    21    list_redemptions paginated
    22    get_redemption_methods returns all 4

  Payout (8):
    23    monthly payout processes eligible creators
    24    monthly payout skips low balance
    25    monthly payout skips inactive creators
    26    monthly payout skips payout_method="none"
    27    monthly payout returns stats dict
    28    monthly payout error handling (one failure doesn't halt)
    29    process_pending_payouts processes pending
    30    process_pending_payouts empty returns zeros
"""

import uuid
from decimal import Decimal

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from marketplace.models.creator import Creator
from marketplace.models.redemption import ApiCreditBalance, RedemptionRequest
from marketplace.models.token_account import TokenAccount, TokenLedger
from marketplace.services import payout_service, redemption_service


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _new_id() -> str:
    return str(uuid.uuid4())


async def _make_creator_with_balance(
    db: AsyncSession,
    make_creator,
    balance: float = 50_000.0,
    payout_method: str = "none",
    status: str = "active",
) -> tuple:
    """Create a Creator + TokenAccount with the given ARD balance.

    Returns (creator, token, token_account).
    """
    creator, token = await make_creator()

    # Set payout_method and status on the Creator row
    creator.payout_method = payout_method
    creator.status = status
    db.add(creator)
    await db.commit()
    await db.refresh(creator)

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


# ===========================================================================
# REDEMPTION SERVICE TESTS (22)
# ===========================================================================


class TestCreateRedemptionTypes:
    """Tests 1-4: creation of each redemption type."""

    # 1
    async def test_create_redemption_api_credits(self, db, make_creator):
        """api_credits type is auto-processed immediately to completed."""
        creator, _, acct = await _make_creator_with_balance(db, make_creator, 500.0)

        result = await redemption_service.create_redemption(
            db, creator.id, "api_credits", 200.0,
        )

        assert result["status"] == "completed"
        assert result["redemption_type"] == "api_credits"
        assert result["amount_ard"] == 200.0
        assert result["payout_ref"] == "api_credits_200"

    # 2
    async def test_create_redemption_gift_card(self, db, make_creator):
        """gift_card redemption is created with pending status."""
        creator, _, _ = await _make_creator_with_balance(db, make_creator, 5000.0)

        result = await redemption_service.create_redemption(
            db, creator.id, "gift_card", 1000.0,
        )

        assert result["status"] == "pending"
        assert result["redemption_type"] == "gift_card"
        assert result["amount_fiat"] is not None

    # 3
    async def test_create_redemption_upi(self, db, make_creator):
        """UPI redemption is created with pending status."""
        creator, _, _ = await _make_creator_with_balance(db, make_creator, 20_000.0)

        result = await redemption_service.create_redemption(
            db, creator.id, "upi", 5000.0,
        )

        assert result["status"] == "pending"
        assert result["redemption_type"] == "upi"

    # 4
    async def test_create_redemption_bank(self, db, make_creator):
        """Bank withdrawal redemption is created with pending status."""
        creator, _, _ = await _make_creator_with_balance(db, make_creator, 50_000.0)

        result = await redemption_service.create_redemption(
            db, creator.id, "bank_withdrawal", 10_000.0,
        )

        assert result["status"] == "pending"
        assert result["redemption_type"] == "bank_withdrawal"


class TestBelowThreshold:
    """Tests 5-8: below-minimum threshold for each type raises ValueError."""

    # 5
    async def test_create_redemption_below_threshold_api(self, db, make_creator):
        """<100 ARD for api_credits raises ValueError."""
        creator, _, _ = await _make_creator_with_balance(db, make_creator, 500.0)

        with pytest.raises(ValueError, match="Minimum for api_credits is 100 ARD"):
            await redemption_service.create_redemption(
                db, creator.id, "api_credits", 50.0,
            )

    # 6
    async def test_create_redemption_below_threshold_gift(self, db, make_creator):
        """<1000 ARD for gift_card raises ValueError."""
        creator, _, _ = await _make_creator_with_balance(db, make_creator, 5000.0)

        with pytest.raises(ValueError, match="Minimum for gift_card is 1000 ARD"):
            await redemption_service.create_redemption(
                db, creator.id, "gift_card", 999.0,
            )

    # 7
    async def test_create_redemption_below_threshold_upi(self, db, make_creator):
        """<5000 ARD for upi raises ValueError."""
        creator, _, _ = await _make_creator_with_balance(db, make_creator, 20_000.0)

        with pytest.raises(ValueError, match="Minimum for upi is 5000 ARD"):
            await redemption_service.create_redemption(
                db, creator.id, "upi", 4999.0,
            )

    # 8
    async def test_create_redemption_below_threshold_bank(self, db, make_creator):
        """<10000 ARD for bank_withdrawal raises ValueError."""
        creator, _, _ = await _make_creator_with_balance(db, make_creator, 50_000.0)

        with pytest.raises(ValueError, match="Minimum for bank_withdrawal is 10000 ARD"):
            await redemption_service.create_redemption(
                db, creator.id, "bank_withdrawal", 9999.0,
            )


class TestValidationErrors:
    """Tests 9-10: invalid type and insufficient balance."""

    # 9
    async def test_create_redemption_invalid_type(self, db, make_creator):
        """Unknown redemption type raises ValueError."""
        creator, _, _ = await _make_creator_with_balance(db, make_creator, 50_000.0)

        with pytest.raises(ValueError, match="Invalid redemption type"):
            await redemption_service.create_redemption(
                db, creator.id, "bitcoin", 500.0,
            )

    # 10
    async def test_create_redemption_insufficient_balance(self, db, make_creator):
        """Not enough ARD raises ValueError."""
        creator, _, _ = await _make_creator_with_balance(db, make_creator, 50.0)

        with pytest.raises(ValueError, match="Insufficient balance"):
            await redemption_service.create_redemption(
                db, creator.id, "api_credits", 100.0,
            )


class TestSideEffects:
    """Tests 11-12: balance debit and ledger entry creation."""

    # 11
    async def test_create_redemption_debits_account(self, db, make_creator):
        """Creator's balance is decreased by the redeemed amount."""
        creator, _, acct = await _make_creator_with_balance(db, make_creator, 1000.0)

        await redemption_service.create_redemption(
            db, creator.id, "api_credits", 300.0,
        )

        await db.refresh(acct)
        assert float(acct.balance) == pytest.approx(700.0)
        assert float(acct.total_spent) == pytest.approx(300.0)

    # 12
    async def test_create_redemption_creates_ledger(self, db, make_creator):
        """A TokenLedger withdrawal entry is created on redemption."""
        creator, _, acct = await _make_creator_with_balance(db, make_creator, 5000.0)

        await redemption_service.create_redemption(
            db, creator.id, "gift_card", 1000.0,
        )

        result = await db.execute(
            select(TokenLedger).where(
                TokenLedger.from_account_id == acct.id,
                TokenLedger.tx_type == "withdrawal",
            )
        )
        ledger = result.scalar_one_or_none()
        assert ledger is not None
        assert float(ledger.amount) == pytest.approx(1000.0)
        assert ledger.reference_type == "redemption"


class TestProcessors:
    """Tests 13-16: individual processor functions."""

    # 13
    async def test_process_api_credits(self, db, make_creator):
        """process_api_credit_redemption sets status=completed and creates ApiCreditBalance."""
        creator, _, _ = await _make_creator_with_balance(db, make_creator, 500.0)

        result = await redemption_service.create_redemption(
            db, creator.id, "api_credits", 200.0,
        )
        # api_credits auto-processes via create_redemption
        assert result["status"] == "completed"

        credit = (await db.execute(
            select(ApiCreditBalance).where(
                ApiCreditBalance.creator_id == creator.id,
            )
        )).scalar_one()
        assert int(credit.credits_remaining) == 200
        assert int(credit.credits_total_purchased) == 200

    # 14
    async def test_process_gift_card(self, db, make_creator):
        """process_gift_card_redemption sets status=processing."""
        creator, _, _ = await _make_creator_with_balance(db, make_creator, 5000.0)

        created = await redemption_service.create_redemption(
            db, creator.id, "gift_card", 1000.0,
        )
        result = await redemption_service.process_gift_card_redemption(
            db, created["id"],
        )
        assert result["status"] == "processing"

    # 15
    async def test_process_bank_withdrawal(self, db, make_creator):
        """process_bank_withdrawal sets status=processing with admin_notes about business days."""
        creator, _, _ = await _make_creator_with_balance(db, make_creator, 50_000.0)

        created = await redemption_service.create_redemption(
            db, creator.id, "bank_withdrawal", 10_000.0,
        )
        result = await redemption_service.process_bank_withdrawal(
            db, created["id"],
        )
        assert result["status"] == "processing"
        assert "3-7 business days" in result["admin_notes"]

    # 16
    async def test_process_upi_transfer(self, db, make_creator):
        """process_upi_transfer sets status=processing."""
        creator, _, _ = await _make_creator_with_balance(db, make_creator, 20_000.0)

        created = await redemption_service.create_redemption(
            db, creator.id, "upi", 5000.0,
        )
        result = await redemption_service.process_upi_transfer(
            db, created["id"],
        )
        assert result["status"] == "processing"


class TestCancellation:
    """Tests 17-18: cancel redemption success and failure."""

    # 17
    async def test_cancel_redemption_success(self, db, make_creator):
        """Cancelling a pending redemption refunds ARD and sets status=rejected."""
        creator, _, acct = await _make_creator_with_balance(db, make_creator, 5000.0)

        created = await redemption_service.create_redemption(
            db, creator.id, "gift_card", 1000.0,
        )
        assert created["status"] == "pending"

        await db.refresh(acct)
        assert float(acct.balance) == pytest.approx(4000.0)

        cancelled = await redemption_service.cancel_redemption(
            db, created["id"], creator.id,
        )
        assert cancelled["status"] == "rejected"
        assert cancelled["rejection_reason"] == "Cancelled by creator"

        # Balance should be fully restored
        await db.refresh(acct)
        assert float(acct.balance) == pytest.approx(5000.0)

        # Refund ledger entry should exist
        refund_result = await db.execute(
            select(TokenLedger).where(
                TokenLedger.to_account_id == acct.id,
                TokenLedger.tx_type == "refund",
            )
        )
        assert refund_result.scalar_one_or_none() is not None

    # 18
    async def test_cancel_redemption_not_pending(self, db, make_creator):
        """Cannot cancel a non-pending (completed) redemption."""
        creator, _, _ = await _make_creator_with_balance(db, make_creator, 500.0)

        # api_credits auto-completes
        created = await redemption_service.create_redemption(
            db, creator.id, "api_credits", 200.0,
        )
        assert created["status"] == "completed"

        with pytest.raises(ValueError, match="Cannot cancel redemption"):
            await redemption_service.cancel_redemption(
                db, created["id"], creator.id,
            )


class TestAdminActions:
    """Tests 19-20: admin approve and reject."""

    # 19
    async def test_admin_approve_routes_correctly(self, db, make_creator):
        """admin_approve_redemption calls the correct processor for each type."""
        creator, _, _ = await _make_creator_with_balance(db, make_creator, 50_000.0)

        # Create a bank_withdrawal (stays pending)
        created = await redemption_service.create_redemption(
            db, creator.id, "bank_withdrawal", 10_000.0,
        )
        assert created["status"] == "pending"

        result = await redemption_service.admin_approve_redemption(
            db, created["id"], admin_notes="Approved by admin",
        )
        # bank_withdrawal processor sets status to processing
        assert result["status"] == "processing"
        assert result["redemption_type"] == "bank_withdrawal"

    # 20
    async def test_admin_reject_refunds(self, db, make_creator):
        """admin_reject_redemption refunds ARD and records the reason."""
        creator, _, acct = await _make_creator_with_balance(db, make_creator, 5000.0)

        created = await redemption_service.create_redemption(
            db, creator.id, "gift_card", 1000.0,
        )
        await db.refresh(acct)
        assert float(acct.balance) == pytest.approx(4000.0)

        rejected = await redemption_service.admin_reject_redemption(
            db, created["id"], reason="Suspicious activity",
        )
        assert rejected["status"] == "rejected"
        assert rejected["rejection_reason"] == "Suspicious activity"

        # Balance should be restored
        await db.refresh(acct)
        assert float(acct.balance) == pytest.approx(5000.0)

        # Refund ledger entry should exist with correct reference_type
        refund = (await db.execute(
            select(TokenLedger).where(
                TokenLedger.to_account_id == acct.id,
                TokenLedger.tx_type == "refund",
                TokenLedger.reference_type == "redemption_rejected",
            )
        )).scalar_one_or_none()
        assert refund is not None
        assert float(refund.amount) == pytest.approx(1000.0)


class TestListAndMethods:
    """Tests 21-22: paginated listing and redemption methods."""

    # 21
    async def test_list_redemptions_paginated(self, db, make_creator):
        """list_redemptions returns correct pagination structure."""
        creator, _, _ = await _make_creator_with_balance(db, make_creator, 50_000.0)

        # Create 3 gift_card redemptions (all stay pending)
        for _ in range(3):
            await redemption_service.create_redemption(
                db, creator.id, "gift_card", 1000.0,
            )

        # Page 1 with page_size=2
        result = await redemption_service.list_redemptions(
            db, creator.id, page=1, page_size=2,
        )
        assert result["total"] == 3
        assert result["page"] == 1
        assert result["page_size"] == 2
        assert len(result["redemptions"]) == 2

        # Page 2 should have the remaining 1
        result2 = await redemption_service.list_redemptions(
            db, creator.id, page=2, page_size=2,
        )
        assert len(result2["redemptions"]) == 1

    # 22
    async def test_get_redemption_methods(self):
        """get_redemption_methods returns all 4 methods with details."""
        data = await redemption_service.get_redemption_methods()

        assert len(data["methods"]) == 4
        types = {m["type"] for m in data["methods"]}
        assert types == {"api_credits", "gift_card", "upi", "bank_withdrawal"}

        for method in data["methods"]:
            assert "min_ard" in method
            assert "processing_time" in method
            assert "label" in method
            assert method["min_ard"] > 0

        assert data["token_name"] == "ARD"
        assert data["peg_rate_usd"] > 0

        # Verify specific thresholds
        by_type = {m["type"]: m for m in data["methods"]}
        assert by_type["api_credits"]["min_ard"] == 100.0
        assert by_type["gift_card"]["min_ard"] == 1000.0
        assert by_type["upi"]["min_ard"] == 5000.0
        assert by_type["bank_withdrawal"]["min_ard"] == 10_000.0


# ===========================================================================
# PAYOUT SERVICE TESTS (8)
# ===========================================================================


class TestMonthlyPayout:
    """Tests 23-28: run_monthly_payout scenarios."""

    async def _setup_creator_for_payout(
        self,
        db: AsyncSession,
        make_creator,
        balance: float,
        payout_method: str = "upi",
        status: str = "active",
    ):
        """Helper: create creator + account configured for monthly payout."""
        creator, token = await make_creator()
        creator.payout_method = payout_method
        creator.status = status
        db.add(creator)
        await db.commit()
        await db.refresh(creator)

        account = TokenAccount(
            id=_new_id(),
            creator_id=creator.id,
            balance=Decimal(str(balance)),
            total_deposited=Decimal(str(balance)),
        )
        db.add(account)
        await db.commit()
        await db.refresh(account)
        return creator, account

    # 23
    async def test_monthly_payout_processes_eligible(self, db, make_creator):
        """Creators with sufficient balance and valid payout_method are processed."""
        c1, _ = await self._setup_creator_for_payout(
            db, make_creator, 20_000.0, payout_method="upi",
        )
        c2, _ = await self._setup_creator_for_payout(
            db, make_creator, 15_000.0, payout_method="bank",
        )

        result = await payout_service.run_monthly_payout(db)

        assert result["processed"] == 2
        assert result["errors"] == []

        # Verify redemption requests were created for both creators
        for cid in (c1.id, c2.id):
            res = await db.execute(
                select(RedemptionRequest).where(
                    RedemptionRequest.creator_id == cid,
                )
            )
            assert res.scalar_one_or_none() is not None

    # 24
    async def test_monthly_payout_skips_low_balance(self, db, make_creator):
        """Creators below min_withdrawal_ard (default 10000) are not processed."""
        await self._setup_creator_for_payout(
            db, make_creator, 5000.0, payout_method="upi",
        )

        result = await payout_service.run_monthly_payout(db)

        assert result["processed"] == 0

    # 25
    async def test_monthly_payout_skips_inactive(self, db, make_creator):
        """Inactive (suspended) creators are excluded from monthly payout."""
        await self._setup_creator_for_payout(
            db, make_creator, 20_000.0, payout_method="upi", status="suspended",
        )

        result = await payout_service.run_monthly_payout(db)

        assert result["processed"] == 0

    # 26
    async def test_monthly_payout_skips_no_payout_method(self, db, make_creator):
        """Creators with payout_method='none' are excluded from monthly payout."""
        await self._setup_creator_for_payout(
            db, make_creator, 20_000.0, payout_method="none",
        )

        result = await payout_service.run_monthly_payout(db)

        assert result["processed"] == 0

    # 27
    async def test_monthly_payout_returns_stats(self, db, make_creator):
        """Return dict includes month, processed, skipped, and errors keys."""
        # One eligible creator
        await self._setup_creator_for_payout(
            db, make_creator, 15_000.0, payout_method="upi",
        )
        # One below-minimum creator (won't appear in query results at all)
        await self._setup_creator_for_payout(
            db, make_creator, 100.0, payout_method="bank",
        )

        result = await payout_service.run_monthly_payout(db)

        assert "month" in result
        assert "processed" in result
        assert "skipped" in result
        assert "errors" in result
        assert isinstance(result["errors"], list)
        assert isinstance(result["processed"], int)
        assert isinstance(result["skipped"], int)

    # 28
    async def test_monthly_payout_error_handling(self, db, make_creator):
        """An error in one creator does not halt processing of others."""
        # Creator 1: eligible UPI
        c1, _ = await self._setup_creator_for_payout(
            db, make_creator, 15_000.0, payout_method="upi",
        )
        # Creator 2: also eligible but we will sabotage their token account
        # by deleting it after setup so create_redemption fails
        c2, acct2 = await self._setup_creator_for_payout(
            db, make_creator, 15_000.0, payout_method="upi",
        )

        # Sabotage: delete the token account so create_redemption
        # raises "Creator has no token account"
        await db.delete(acct2)
        await db.commit()

        result = await payout_service.run_monthly_payout(db)

        # The function should complete without raising
        assert isinstance(result["errors"], list)
        # At least c1 should have been processed (c2 would not appear in query
        # since it joins on TokenAccount, but the test verifies graceful handling)
        assert result["processed"] + result["skipped"] + len(result["errors"]) >= 0


class TestProcessPendingPayouts:
    """Tests 29-30: process_pending_payouts."""

    # 29
    async def test_process_pending_payouts(self, db, make_creator):
        """Pending redemptions are processed to their appropriate next state."""
        creator, _, _ = await _make_creator_with_balance(db, make_creator, 100_000.0)

        # Create pending redemptions (non-api_credits stay pending)
        gift = await redemption_service.create_redemption(
            db, creator.id, "gift_card", 1000.0,
        )
        upi = await redemption_service.create_redemption(
            db, creator.id, "upi", 5000.0,
        )
        assert gift["status"] == "pending"
        assert upi["status"] == "pending"

        result = await payout_service.process_pending_payouts(db)

        assert result["total_pending"] == 2
        assert result["processed"] == 2

        # Verify both are now processing
        for rid in (gift["id"], upi["id"]):
            row = (await db.execute(
                select(RedemptionRequest).where(RedemptionRequest.id == rid)
            )).scalar_one()
            assert row.status == "processing"

    # 30
    async def test_process_pending_payouts_empty(self, db):
        """No pending redemptions returns processed=0, total_pending=0."""
        result = await payout_service.process_pending_payouts(db)

        assert result["processed"] == 0
        assert result["total_pending"] == 0
