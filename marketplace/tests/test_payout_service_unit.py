"""Unit tests for payout_service — 25 async tests, 5 describe blocks.

Covers:
  Payout Calculations (5):
    1   gross_to_net_upi — UPI payout calculates correct USD amount
    2   gross_to_net_bank — bank_withdrawal produces correct USD amount
    3   gross_to_net_gift_card — gift card USD amount is correct
    4   multi_tier_rate_upi_vs_bank — different types have different min thresholds
    5   fee_deduction_reflected_in_account — balance debited, total_spent credited

  Ledger Double-Entry (5):
    6   ledger_entry_created_on_redemption — withdrawal ledger row exists
    7   ledger_debit_credit_pair — from_account set, to_account NULL for withdrawal
    8   ledger_amount_matches_redemption — ledger.amount == redemption.amount_usd
    9   cancel_creates_refund_ledger — cancellation adds refund entry
    10  balance_consistency_after_cancel — balance restored after cancel

  Minimum Thresholds (5):
    11  below_minimum_upi_rejected — amount < $5.00 rejected for UPI
    12  below_minimum_bank_rejected — amount < $10.00 rejected for bank
    13  below_minimum_gift_card_rejected — amount < $1.00 rejected for gift card
    14  exact_minimum_upi_accepted — exactly $5.00 accepted for UPI
    15  exact_minimum_api_credits_accepted — exactly $0.10 accepted for api_credits

  Batch Payouts (5):
    16  monthly_batch_multiple_recipients — processes all eligible creators
    17  monthly_batch_partial_failure — one error does not block others
    18  monthly_batch_skips_below_minimum — below-threshold creators skipped
    19  monthly_batch_skips_unsupported_method — payout_method not in map is skipped
    20  monthly_batch_idempotent_month_key — returns correct month key

  Error Handling (5):
    21  invalid_redemption_type_raises — unknown type raises ValueError
    22  insufficient_balance_raises — balance < requested raises ValueError
    23  no_token_account_raises — creator without account raises ValueError
    24  process_pending_handles_exception — failed processing does not crash batch
    25  process_pending_routes_all_types — each type dispatched to correct processor
"""

import uuid
from decimal import Decimal
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from marketplace.config import settings
from marketplace.models.creator import Creator
from marketplace.models.redemption import RedemptionRequest
from marketplace.models.token_account import TokenAccount, TokenLedger
from marketplace.services import payout_service, redemption_service
from marketplace.tests.conftest import TestSession, _new_id


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _create_creator_with_balance(
    db: AsyncSession,
    make_creator,
    balance: float,
    payout_method: str = "upi",
    status: str = "active",
) -> tuple:
    """Create a creator configured for payout testing.

    Returns (creator, token_account).
    """
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
        total_earned=Decimal("0"),
        total_spent=Decimal("0"),
        total_fees_paid=Decimal("0"),
    )
    db.add(account)
    await db.commit()
    await db.refresh(account)
    return creator, account


# ===========================================================================
# BLOCK 1: PAYOUT CALCULATIONS (tests 1-5)
# ===========================================================================


class TestPayoutCalculations:
    """Tests 1-5: gross-to-net calculations, fee deduction, multi-tier rates."""

    # 1
    async def test_gross_to_net_upi(self, db, make_creator):
        """UPI redemption calculates correct USD amount."""
        creator, acct = await _create_creator_with_balance(
            db, make_creator, 100.00, payout_method="upi",
        )

        result = await redemption_service.create_redemption(
            db, creator.id, "upi", 100.00,
        )

        assert result["amount_usd"] == pytest.approx(100.0)

    # 2
    async def test_gross_to_net_bank(self, db, make_creator):
        """Bank withdrawal produces correct USD amount."""
        creator, acct = await _create_creator_with_balance(
            db, make_creator, 500.00, payout_method="bank",
        )

        result = await redemption_service.create_redemption(
            db, creator.id, "bank_withdrawal", 500.00,
        )

        assert result["amount_usd"] == pytest.approx(500.0)

    # 3
    async def test_gross_to_net_gift_card(self, db, make_creator):
        """Gift card USD amount is correct."""
        creator, acct = await _create_creator_with_balance(
            db, make_creator, 50.00, payout_method="gift_card",
        )

        result = await redemption_service.create_redemption(
            db, creator.id, "gift_card", 50.00,
        )

        assert result["amount_usd"] == pytest.approx(50.0)

    # 4
    async def test_multi_tier_rate_upi_vs_bank(self, db, make_creator):
        """UPI and bank have different minimum thresholds ($5 vs $10)."""
        # UPI at $5 should succeed
        c1, _ = await _create_creator_with_balance(
            db, make_creator, 5.00, payout_method="upi",
        )
        upi_result = await redemption_service.create_redemption(
            db, c1.id, "upi", 5.00,
        )
        assert upi_result["status"] == "pending"

        # Bank at $5 should fail (min is $10)
        c2, _ = await _create_creator_with_balance(
            db, make_creator, 5.00, payout_method="bank",
        )
        with pytest.raises(ValueError, match="Minimum for bank_withdrawal"):
            await redemption_service.create_redemption(
                db, c2.id, "bank_withdrawal", 5.00,
            )

    # 5
    async def test_fee_deduction_reflected_in_account(self, db, make_creator):
        """After redemption, creator account balance is debited and total_spent is credited."""
        creator, acct = await _create_creator_with_balance(
            db, make_creator, 200.00, payout_method="upi",
        )
        original_balance = float(acct.balance)

        await redemption_service.create_redemption(
            db, creator.id, "upi", 80.00,
        )

        # Re-read account from DB
        refreshed = (await db.execute(
            select(TokenAccount).where(TokenAccount.creator_id == creator.id)
        )).scalar_one()

        assert float(refreshed.balance) == pytest.approx(original_balance - 80.0)
        assert float(refreshed.total_spent) == pytest.approx(80.0)


# ===========================================================================
# BLOCK 2: LEDGER DOUBLE-ENTRY (tests 6-10)
# ===========================================================================


class TestLedgerDoubleEntry:
    """Tests 6-10: ledger debit/credit pairs, balance consistency."""

    # 6
    async def test_ledger_entry_created_on_redemption(self, db, make_creator):
        """A withdrawal ledger entry is created when a redemption is made."""
        creator, acct = await _create_creator_with_balance(
            db, make_creator, 150.00, payout_method="upi",
        )

        result = await redemption_service.create_redemption(
            db, creator.id, "upi", 100.00,
        )

        # Find the ledger entry referenced by the redemption
        rr = (await db.execute(
            select(RedemptionRequest).where(RedemptionRequest.id == result["id"])
        )).scalar_one()

        ledger = (await db.execute(
            select(TokenLedger).where(TokenLedger.id == rr.ledger_entry_id)
        )).scalar_one()

        assert ledger is not None
        assert ledger.tx_type == "withdrawal"

    # 7
    async def test_ledger_debit_credit_pair(self, db, make_creator):
        """Withdrawal ledger: from_account_id is set, to_account_id is NULL."""
        creator, acct = await _create_creator_with_balance(
            db, make_creator, 150.00, payout_method="upi",
        )

        result = await redemption_service.create_redemption(
            db, creator.id, "upi", 100.00,
        )

        rr = (await db.execute(
            select(RedemptionRequest).where(RedemptionRequest.id == result["id"])
        )).scalar_one()

        ledger = (await db.execute(
            select(TokenLedger).where(TokenLedger.id == rr.ledger_entry_id)
        )).scalar_one()

        # Debit side: from creator's account
        assert ledger.from_account_id == acct.id
        # Credit side: NULL (withdrawal)
        assert ledger.to_account_id is None

    # 8
    async def test_ledger_amount_matches_redemption(self, db, make_creator):
        """Ledger entry amount matches the redemption amount_usd exactly."""
        creator, acct = await _create_creator_with_balance(
            db, make_creator, 200.00, payout_method="bank",
        )
        redeem_amount = 123.456

        result = await redemption_service.create_redemption(
            db, creator.id, "bank_withdrawal", redeem_amount,
        )

        rr = (await db.execute(
            select(RedemptionRequest).where(RedemptionRequest.id == result["id"])
        )).scalar_one()

        ledger = (await db.execute(
            select(TokenLedger).where(TokenLedger.id == rr.ledger_entry_id)
        )).scalar_one()

        assert float(ledger.amount) == pytest.approx(redeem_amount, rel=1e-4)

    # 9
    async def test_cancel_creates_refund_ledger(self, db, make_creator):
        """Cancelling a pending redemption creates a refund ledger entry."""
        creator, acct = await _create_creator_with_balance(
            db, make_creator, 150.00, payout_method="upi",
        )

        result = await redemption_service.create_redemption(
            db, creator.id, "upi", 80.00,
        )

        # Cancel it
        cancelled = await redemption_service.cancel_redemption(
            db, result["id"], creator.id,
        )
        assert cancelled["status"] == "rejected"

        # Find the refund ledger entry
        refund_entries = (await db.execute(
            select(TokenLedger).where(
                TokenLedger.tx_type == "refund",
                TokenLedger.reference_id == result["id"],
            )
        )).scalars().all()

        assert len(refund_entries) == 1
        refund = refund_entries[0]
        assert refund.to_account_id == acct.id
        assert refund.from_account_id is None  # refund comes from "nowhere" (reversal)
        assert float(refund.amount) == pytest.approx(80.0)

    # 10
    async def test_balance_consistency_after_cancel(self, db, make_creator):
        """Balance is fully restored after creating and then cancelling a redemption."""
        initial_balance = 150.00
        creator, acct = await _create_creator_with_balance(
            db, make_creator, initial_balance, payout_method="upi",
        )

        result = await redemption_service.create_redemption(
            db, creator.id, "upi", 80.00,
        )

        # After redemption, balance should be reduced
        acct_mid = (await db.execute(
            select(TokenAccount).where(TokenAccount.creator_id == creator.id)
        )).scalar_one()
        assert float(acct_mid.balance) == pytest.approx(initial_balance - 80.0)

        # Cancel
        await redemption_service.cancel_redemption(db, result["id"], creator.id)

        # After cancel, balance should be restored
        acct_final = (await db.execute(
            select(TokenAccount).where(TokenAccount.creator_id == creator.id)
        )).scalar_one()
        assert float(acct_final.balance) == pytest.approx(initial_balance)
        assert float(acct_final.total_spent) == pytest.approx(0.0)


# ===========================================================================
# BLOCK 3: MINIMUM THRESHOLDS (tests 11-15)
# ===========================================================================


class TestMinimumThresholds:
    """Tests 11-15: below-minimum rejection, exact-minimum edge cases."""

    # 11
    async def test_below_minimum_upi_rejected(self, db, make_creator):
        """UPI redemption below $5.00 minimum is rejected with ValueError."""
        creator, acct = await _create_creator_with_balance(
            db, make_creator, 100.00, payout_method="upi",
        )

        with pytest.raises(ValueError, match="Minimum for upi"):
            await redemption_service.create_redemption(
                db, creator.id, "upi", 4.99,
            )

        # Account balance should remain unchanged
        refreshed = (await db.execute(
            select(TokenAccount).where(TokenAccount.creator_id == creator.id)
        )).scalar_one()
        assert float(refreshed.balance) == pytest.approx(100.0)

    # 12
    async def test_below_minimum_bank_rejected(self, db, make_creator):
        """Bank withdrawal below $10.00 minimum is rejected."""
        creator, acct = await _create_creator_with_balance(
            db, make_creator, 200.00, payout_method="bank",
        )

        with pytest.raises(ValueError, match="Minimum for bank_withdrawal"):
            await redemption_service.create_redemption(
                db, creator.id, "bank_withdrawal", 9.99,
            )

    # 13
    async def test_below_minimum_gift_card_rejected(self, db, make_creator):
        """Gift card below $1.00 minimum is rejected."""
        creator, acct = await _create_creator_with_balance(
            db, make_creator, 50.00, payout_method="gift_card",
        )

        with pytest.raises(ValueError, match="Minimum for gift_card"):
            await redemption_service.create_redemption(
                db, creator.id, "gift_card", 0.99,
            )

    # 14
    async def test_exact_minimum_upi_accepted(self, db, make_creator):
        """Exactly $5.00 is accepted for UPI redemption (boundary test)."""
        creator, acct = await _create_creator_with_balance(
            db, make_creator, 100.00, payout_method="upi",
        )

        result = await redemption_service.create_redemption(
            db, creator.id, "upi", 5.00,
        )

        assert result["status"] == "pending"
        assert result["amount_usd"] == pytest.approx(5.0)

    # 15
    async def test_exact_minimum_api_credits_accepted(self, db, make_creator):
        """Exactly $0.10 is accepted for api_credits (lowest threshold)."""
        creator, acct = await _create_creator_with_balance(
            db, make_creator, 10.00, payout_method="upi",
        )

        result = await redemption_service.create_redemption(
            db, creator.id, "api_credits", 0.10,
        )

        # api_credits auto-completes
        assert result["status"] == "completed"
        assert result["amount_usd"] == pytest.approx(0.10)


# ===========================================================================
# BLOCK 4: BATCH PAYOUTS (tests 16-20)
# ===========================================================================


class TestBatchPayouts:
    """Tests 16-20: monthly batch payout with multiple recipients, partial failures."""

    # 16
    async def test_monthly_batch_multiple_recipients(self, db, make_creator):
        """run_monthly_payout processes all eligible creators in a single batch."""
        c1, _ = await _create_creator_with_balance(
            db, make_creator, 20.00, payout_method="upi",
        )
        c2, _ = await _create_creator_with_balance(
            db, make_creator, 30.00, payout_method="bank",
        )
        c3, _ = await _create_creator_with_balance(
            db, make_creator, 15.00, payout_method="gift_card",
        )

        result = await payout_service.run_monthly_payout(db)

        assert result["processed"] == 3
        assert result["skipped"] == 0
        assert result["errors"] == []

        # Verify each creator got a redemption request
        for creator in (c1, c2, c3):
            rr = (await db.execute(
                select(RedemptionRequest).where(
                    RedemptionRequest.creator_id == creator.id,
                )
            )).scalar_one()
            assert rr.status == "pending"

    # 17
    async def test_monthly_batch_partial_failure(self, db, make_creator):
        """If one creator's payout fails, others still get processed."""
        c1, _ = await _create_creator_with_balance(
            db, make_creator, 20.00, payout_method="upi",
        )
        c2, _ = await _create_creator_with_balance(
            db, make_creator, 25.00, payout_method="bank",
        )

        # Patch create_redemption to fail for the first creator only
        original_create = redemption_service.create_redemption

        call_count = 0

        async def _failing_create(db_session, creator_id, rtype, amount):
            nonlocal call_count
            call_count += 1
            if creator_id == c1.id:
                raise RuntimeError("Simulated payment gateway timeout")
            return await original_create(db_session, creator_id, rtype, amount)

        with patch.object(redemption_service, "create_redemption", side_effect=_failing_create):
            result = await payout_service.run_monthly_payout(db)

        # c1 failed, c2 succeeded
        assert result["processed"] == 1
        assert len(result["errors"]) == 1
        assert result["errors"][0]["creator_id"] == c1.id
        assert "Simulated payment gateway timeout" in result["errors"][0]["error"]

    # 18
    async def test_monthly_batch_skips_below_minimum(self, db, make_creator):
        """Creators with balance below creator_min_withdrawal_usd are not selected."""
        min_balance = settings.creator_min_withdrawal_usd  # $10.00

        # Below threshold
        await _create_creator_with_balance(
            db, make_creator, min_balance - 0.01, payout_method="upi",
        )
        # Above threshold
        c_eligible, _ = await _create_creator_with_balance(
            db, make_creator, min_balance + 10.00, payout_method="upi",
        )

        result = await payout_service.run_monthly_payout(db)

        # Only the eligible creator should be processed
        assert result["processed"] == 1

        # Verify only one redemption exists
        all_rr = (await db.execute(select(RedemptionRequest))).scalars().all()
        assert len(all_rr) == 1
        assert all_rr[0].creator_id == c_eligible.id

    # 19
    async def test_monthly_batch_skips_unsupported_method(self, db, make_creator):
        """A creator with payout_method not in the type_map is skipped (counted in skipped)."""
        # "none" is filtered by SQL WHERE clause, but test an unexpected value
        creator, acct = await _create_creator_with_balance(
            db, make_creator, 20.00, payout_method="crypto_wallet",
        )

        result = await payout_service.run_monthly_payout(db)

        # "crypto_wallet" is not in ("upi", "bank", "gift_card") -> skipped in loop
        # But first it must pass the SQL filter (payout_method != "none")
        # The SQL filter allows it through, then the loop skips it
        assert result["skipped"] == 1
        assert result["processed"] == 0
        assert result["errors"] == []

    # 20
    async def test_monthly_batch_idempotent_month_key(self, db, make_creator):
        """run_monthly_payout returns the correct YYYY-MM month key."""
        await _create_creator_with_balance(
            db, make_creator, 20.00, payout_method="upi",
        )

        result = await payout_service.run_monthly_payout(db)

        now = datetime.now(timezone.utc)
        expected_key = f"{now.year}-{now.month:02d}"
        assert result["month"] == expected_key


# ===========================================================================
# BLOCK 5: ERROR HANDLING (tests 21-25)
# ===========================================================================


class TestErrorHandling:
    """Tests 21-25: invalid wallet, network failure, retry logic."""

    # 21
    async def test_invalid_redemption_type_raises(self, db, make_creator):
        """An unknown redemption type raises ValueError immediately."""
        creator, acct = await _create_creator_with_balance(
            db, make_creator, 200.00, payout_method="upi",
        )

        with pytest.raises(ValueError, match="Invalid redemption type"):
            await redemption_service.create_redemption(
                db, creator.id, "bitcoin_withdrawal", 50.00,
            )

    # 22
    async def test_insufficient_balance_raises(self, db, make_creator):
        """Requesting more USD than available balance raises ValueError."""
        creator, acct = await _create_creator_with_balance(
            db, make_creator, 5.00, payout_method="upi",
        )

        with pytest.raises(ValueError, match="Insufficient balance"):
            await redemption_service.create_redemption(
                db, creator.id, "upi", 100.00,
            )

        # Balance unchanged
        refreshed = (await db.execute(
            select(TokenAccount).where(TokenAccount.creator_id == creator.id)
        )).scalar_one()
        assert float(refreshed.balance) == pytest.approx(5.0)

    # 23
    async def test_no_token_account_raises(self, db):
        """A creator with no TokenAccount gets a clear ValueError."""
        from marketplace.core.creator_auth import hash_password

        creator = Creator(
            id=_new_id(),
            email=f"noaccount-{_new_id()[:8]}@test.com",
            password_hash=hash_password("pass1234"),
            display_name="No Account Creator",
            status="active",
            payout_method="upi",
        )
        db.add(creator)
        await db.commit()

        with pytest.raises(ValueError, match="Creator has no token account"):
            await redemption_service.create_redemption(
                db, creator.id, "upi", 5.00,
            )

    # 24
    async def test_process_pending_handles_exception(self, db, make_creator):
        """process_pending_payouts catches per-redemption exceptions gracefully."""
        creator, acct = await _create_creator_with_balance(
            db, make_creator, 500.00, payout_method="upi",
        )

        # Create two pending redemptions
        r1 = await redemption_service.create_redemption(
            db, creator.id, "upi", 60.00,
        )
        r2 = await redemption_service.create_redemption(
            db, creator.id, "upi", 70.00,
        )

        # Patch process_upi_transfer to fail on the first one
        original_upi = redemption_service.process_upi_transfer

        call_count = 0

        async def _flaky_upi(db_session, redemption_id):
            nonlocal call_count
            call_count += 1
            if redemption_id == r1["id"]:
                raise ConnectionError("Razorpay API timeout")
            return await original_upi(db_session, redemption_id)

        with patch.object(redemption_service, "process_upi_transfer", side_effect=_flaky_upi):
            result = await payout_service.process_pending_payouts(db)

        # Both were attempted, but only one succeeded
        assert result["total_pending"] == 2
        assert result["processed"] == 1  # only r2 succeeded

    # 25
    async def test_process_pending_routes_all_types(self, db, make_creator):
        """process_pending_payouts routes each redemption_type to its correct processor."""
        creator, acct = await _create_creator_with_balance(
            db, make_creator, 1000.00, payout_method="upi",
        )

        # Create one of each pending type (except api_credits which auto-completes)
        r_gift = await redemption_service.create_redemption(
            db, creator.id, "gift_card", 20.00,
        )
        r_upi = await redemption_service.create_redemption(
            db, creator.id, "upi", 60.00,
        )
        r_bank = await redemption_service.create_redemption(
            db, creator.id, "bank_withdrawal", 150.00,
        )

        assert r_gift["status"] == "pending"
        assert r_upi["status"] == "pending"
        assert r_bank["status"] == "pending"

        result = await payout_service.process_pending_payouts(db)

        assert result["total_pending"] == 3
        assert result["processed"] == 3

        # All should now be in "processing" state
        for rid in (r_gift["id"], r_upi["id"], r_bank["id"]):
            row = (await db.execute(
                select(RedemptionRequest).where(RedemptionRequest.id == rid)
            )).scalar_one()
            assert row.status == "processing", (
                f"Redemption {rid} expected 'processing', got '{row.status}'"
            )
