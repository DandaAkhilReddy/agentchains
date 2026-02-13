"""Tests for the USD redemption system.

Covers minimum thresholds, creation, cancellation, API credit auto-processing,
insufficient-balance rejection, and available redemption methods.
"""

import pytest
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from marketplace.models.token_account import TokenAccount
from marketplace.models.redemption import ApiCreditBalance, RedemptionRequest
from marketplace.services import creator_service, redemption_service
from marketplace.services.token_service import ensure_platform_account


# ---------------------------------------------------------------------------
# Helper: directly set a creator's USD balance
# ---------------------------------------------------------------------------

async def _fund_creator(db: AsyncSession, creator_id: str, amount: float) -> TokenAccount:
    """Set a creator's token-account balance to *amount* USD."""
    result = await db.execute(
        select(TokenAccount).where(TokenAccount.creator_id == creator_id)
    )
    acct = result.scalar_one()
    acct.balance = Decimal(str(amount))
    await db.commit()
    await db.refresh(acct)
    return acct


async def _register(db: AsyncSession, email: str, name: str = "Tester") -> str:
    """Register a creator and return their creator_id."""
    reg = await creator_service.register_creator(db, email, "pass1234", name)
    return reg["creator"]["id"]


# ---------------------------------------------------------------------------
# 1. Minimum-threshold validation
# ---------------------------------------------------------------------------

class TestRedemptionThresholds:
    """Redemption must be rejected when the amount is below the type's minimum."""

    async def test_api_credits_below_minimum_fails(self, db: AsyncSession):
        await ensure_platform_account(db)
        creator_id = await _register(db, "thresh_api@test.com", "ThreshApi")
        await _fund_creator(db, creator_id, 0.09)  # min is $0.10

        with pytest.raises(ValueError, match="Minimum"):
            await redemption_service.create_redemption(db, creator_id, "api_credits", 0.09)

    async def test_gift_card_below_minimum_fails(self, db: AsyncSession):
        await ensure_platform_account(db)
        creator_id = await _register(db, "thresh_gift@test.com", "ThreshGift")
        await _fund_creator(db, creator_id, 0.99)  # min is $1.00

        with pytest.raises(ValueError, match="Minimum"):
            await redemption_service.create_redemption(db, creator_id, "gift_card", 0.99)

    async def test_upi_below_minimum_fails(self, db: AsyncSession):
        await ensure_platform_account(db)
        creator_id = await _register(db, "thresh_upi@test.com", "ThreshUpi")
        await _fund_creator(db, creator_id, 4.99)  # min is $5.00

        with pytest.raises(ValueError, match="Minimum"):
            await redemption_service.create_redemption(db, creator_id, "upi", 4.99)

    async def test_bank_below_minimum_fails(self, db: AsyncSession):
        await ensure_platform_account(db)
        creator_id = await _register(db, "thresh_bank@test.com", "ThreshBank")
        await _fund_creator(db, creator_id, 9.99)  # min is $10.00

        with pytest.raises(ValueError, match="Minimum"):
            await redemption_service.create_redemption(db, creator_id, "bank_withdrawal", 9.99)

    async def test_invalid_redemption_type_fails(self, db: AsyncSession):
        await ensure_platform_account(db)
        creator_id = await _register(db, "thresh_bad@test.com", "ThreshBad")
        await _fund_creator(db, creator_id, 5.00)

        with pytest.raises(ValueError, match="Invalid redemption type"):
            await redemption_service.create_redemption(db, creator_id, "bitcoin", 5.00)


# ---------------------------------------------------------------------------
# 2. Successful creation
# ---------------------------------------------------------------------------

class TestRedemptionCreation:
    """Redemption requests should be created when balance and minimums are met."""

    async def test_create_api_credit_redemption_auto_completes(self, db: AsyncSession):
        """api_credits type is auto-processed: returned status should be 'completed'."""
        await ensure_platform_account(db)
        creator_id = await _register(db, "redeem_api@test.com", "RedeemApi")
        await _fund_creator(db, creator_id, 10.00)

        result = await redemption_service.create_redemption(
            db, creator_id, "api_credits", 5.00
        )

        assert result["status"] == "completed"
        assert result["amount_usd"] == 5.0
        assert result["redemption_type"] == "api_credits"

        # Verify API credit balance was created
        credit_result = await db.execute(
            select(ApiCreditBalance).where(ApiCreditBalance.creator_id == creator_id)
        )
        credit_bal = credit_result.scalar_one()
        assert int(credit_bal.credits_remaining) > 0
        assert int(credit_bal.credits_total_purchased) > 0

    async def test_create_gift_card_redemption_stays_pending(self, db: AsyncSession):
        """Non-api_credits types remain 'pending' until admin action."""
        await ensure_platform_account(db)
        creator_id = await _register(db, "redeem_gift@test.com", "RedeemGift")
        await _fund_creator(db, creator_id, 50.00)

        result = await redemption_service.create_redemption(
            db, creator_id, "gift_card", 20.00
        )

        assert result["status"] == "pending"
        assert result["amount_usd"] == 20.0
        assert result["redemption_type"] == "gift_card"

    async def test_create_upi_redemption(self, db: AsyncSession):
        await ensure_platform_account(db)
        creator_id = await _register(db, "redeem_upi@test.com", "RedeemUpi")
        await _fund_creator(db, creator_id, 100.00)

        result = await redemption_service.create_redemption(
            db, creator_id, "upi", 50.00
        )

        assert result["status"] == "pending"
        assert result["amount_usd"] == 50.0

    async def test_create_bank_redemption(self, db: AsyncSession):
        await ensure_platform_account(db)
        creator_id = await _register(db, "redeem_bank@test.com", "RedeemBank")
        await _fund_creator(db, creator_id, 200.00)

        result = await redemption_service.create_redemption(
            db, creator_id, "bank_withdrawal", 100.00
        )

        assert result["status"] == "pending"
        assert result["amount_usd"] == 100.0

    async def test_balance_debited_after_creation(self, db: AsyncSession):
        """Creator's balance should be reduced by the redeemed amount."""
        await ensure_platform_account(db)
        creator_id = await _register(db, "debit@test.com", "DebitCheck")
        await _fund_creator(db, creator_id, 50.00)

        await redemption_service.create_redemption(
            db, creator_id, "gift_card", 20.00
        )

        acct_result = await db.execute(
            select(TokenAccount).where(TokenAccount.creator_id == creator_id)
        )
        acct = acct_result.scalar_one()
        assert float(acct.balance) == pytest.approx(30.0, abs=0.01)


# ---------------------------------------------------------------------------
# 3. Cancellation
# ---------------------------------------------------------------------------

class TestRedemptionCancellation:
    """Pending redemptions can be cancelled with full USD refund."""

    async def test_cancel_pending_refunds_balance(self, db: AsyncSession):
        await ensure_platform_account(db)
        creator_id = await _register(db, "cancel@test.com", "Canceller")
        await _fund_creator(db, creator_id, 50.00)

        created = await redemption_service.create_redemption(
            db, creator_id, "gift_card", 20.00
        )
        assert created["status"] == "pending"

        # Balance should be 30 after debit
        acct_result = await db.execute(
            select(TokenAccount).where(TokenAccount.creator_id == creator_id)
        )
        acct = acct_result.scalar_one()
        assert float(acct.balance) == pytest.approx(30.0, abs=0.01)

        # Cancel
        cancelled = await redemption_service.cancel_redemption(
            db, created["id"], creator_id
        )
        assert cancelled["status"] == "rejected"
        assert cancelled["rejection_reason"] == "Cancelled by creator"

        # Balance should be fully restored to 50
        await db.refresh(acct)
        assert float(acct.balance) == pytest.approx(50.0, abs=0.01)

    async def test_cancel_completed_fails(self, db: AsyncSession):
        """Cannot cancel an already-completed (api_credits auto-processed) redemption."""
        await ensure_platform_account(db)
        creator_id = await _register(db, "cancel_done@test.com", "CancelDone")
        await _fund_creator(db, creator_id, 10.00)

        created = await redemption_service.create_redemption(
            db, creator_id, "api_credits", 5.00
        )
        assert created["status"] == "completed"

        with pytest.raises(ValueError, match="Cannot cancel"):
            await redemption_service.cancel_redemption(db, created["id"], creator_id)

    async def test_cancel_nonexistent_fails(self, db: AsyncSession):
        await ensure_platform_account(db)
        creator_id = await _register(db, "cancel_ghost@test.com", "Ghost")

        with pytest.raises(ValueError, match="Redemption not found"):
            await redemption_service.cancel_redemption(
                db, "nonexistent-id", creator_id
            )


# ---------------------------------------------------------------------------
# 4. Redemption methods listing
# ---------------------------------------------------------------------------

class TestRedemptionMethods:
    """get_redemption_methods() returns all 4 types with correct minimums."""

    async def test_get_methods_returns_all_types(self):
        methods_data = await redemption_service.get_redemption_methods()
        assert "methods" in methods_data
        assert len(methods_data["methods"]) == 4

        types = [m["type"] for m in methods_data["methods"]]
        assert "api_credits" in types
        assert "gift_card" in types
        assert "upi" in types
        assert "bank_withdrawal" in types

    async def test_methods_have_correct_minimums(self):
        methods_data = await redemption_service.get_redemption_methods()
        by_type = {m["type"]: m for m in methods_data["methods"]}

        assert by_type["api_credits"]["min_usd"] == 0.10
        assert by_type["gift_card"]["min_usd"] == 1.00
        assert by_type["upi"]["min_usd"] == 5.00
        assert by_type["bank_withdrawal"]["min_usd"] == 10.00

    async def test_each_method_has_required_fields(self):
        methods_data = await redemption_service.get_redemption_methods()
        for method in methods_data["methods"]:
            assert "type" in method
            assert "label" in method
            assert "description" in method
            assert "min_usd" in method
            assert "processing_time" in method


# ---------------------------------------------------------------------------
# 5. Insufficient balance
# ---------------------------------------------------------------------------

class TestRedemptionInsufficientBalance:
    """Redemption should fail when creator balance < requested amount."""

    async def test_insufficient_balance_fails(self, db: AsyncSession):
        await ensure_platform_account(db)
        creator_id = await _register(db, "poor@test.com", "Poor")
        # Creator has $0.10 from signup bonus; try to redeem $5 via UPI
        with pytest.raises(ValueError, match="Insufficient balance"):
            await redemption_service.create_redemption(
                db, creator_id, "upi", 5.00
            )

    async def test_exact_balance_succeeds(self, db: AsyncSession):
        """Redeeming exactly the full balance should work."""
        await ensure_platform_account(db)
        creator_id = await _register(db, "exact@test.com", "Exact")
        await _fund_creator(db, creator_id, 5.00)

        result = await redemption_service.create_redemption(
            db, creator_id, "upi", 5.00
        )
        assert result["amount_usd"] == 5.0

        # Balance should now be 0
        acct_result = await db.execute(
            select(TokenAccount).where(TokenAccount.creator_id == creator_id)
        )
        acct = acct_result.scalar_one()
        assert float(acct.balance) == pytest.approx(0.0, abs=0.01)

    async def test_no_token_account_fails(self, db: AsyncSession):
        """A creator_id with no TokenAccount row at all should fail."""
        await ensure_platform_account(db)
        with pytest.raises(ValueError, match="no token account"):
            await redemption_service.create_redemption(
                db, "nonexistent-creator-id", "api_credits", 0.10
            )
