"""Deep coverage tests for payout_service and creator_service — 25 async tests.

Covers:
  Creator Service (20):
    1   register_creator_success — creates creator + token account with signup bonus
    2   register_creator_duplicate_email — raises ValueError
    3   register_creator_email_lowercased — email stored lowercase
    4   register_creator_country_uppercased — country stored uppercase
    5   login_creator_success — returns token and creator dict
    6   login_creator_wrong_password — raises UnauthorizedError
    7   login_creator_wrong_email — raises UnauthorizedError
    8   login_creator_suspended — status="suspended" raises UnauthorizedError
    9   update_creator_display_name — updates correctly
    10  update_creator_payout_details_json — dict converted to JSON string
    11  update_creator_country_uppercased — country uppercased on update
    12  update_creator_disallowed_field — ignores fields not in allowed_fields
    13  link_agent_success — agent.creator_id set
    14  link_agent_not_found — raises ValueError
    15  link_agent_already_claimed — claimed by another creator raises ValueError
    16  link_agent_same_creator_ok — re-linking to same creator succeeds
    17  get_creator_agents_with_earnings — shows agent balance/earnings
    18  get_dashboard_aggregation — totals across agents
    19  get_wallet_with_account — returns all fields
    20  get_wallet_no_account — returns defaults (balance=0)

  Payout Service (5):
    21  monthly_payout_processes_eligible — creates redemption for eligible creator
    22  monthly_payout_skips_inactive — inactive creator skipped
    23  monthly_payout_skips_no_method — payout_method="none" skipped
    24  monthly_payout_type_mapping — upi->upi, bank->bank_withdrawal, gift_card->gift_card
    25  process_pending_payouts — processes pending redemptions
"""

import json
import uuid
from decimal import Decimal

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from marketplace.core.exceptions import UnauthorizedError
from marketplace.models.agent import RegisteredAgent
from marketplace.models.creator import Creator
from marketplace.models.redemption import RedemptionRequest
from marketplace.models.token_account import TokenAccount
from marketplace.services import creator_service, payout_service, redemption_service
from marketplace.tests.conftest import TestSession, _new_id


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _setup_creator_for_payout(
    db: AsyncSession,
    make_creator,
    balance: float,
    payout_method: str = "upi",
    status: str = "active",
) -> tuple:
    """Create a creator configured for monthly payout with the given balance.

    Returns (creator, token_account).
    """
    creator, token = await make_creator()

    # Update payout method and status
    creator.payout_method = payout_method
    creator.status = status
    db.add(creator)
    await db.commit()
    await db.refresh(creator)

    # Create a separate token account with the desired balance
    # (make_creator from conftest does NOT create a token account)
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


# ===========================================================================
# CREATOR SERVICE TESTS (1-20)
# ===========================================================================


class TestRegisterCreator:
    """Tests 1-4: creator registration edge cases."""

    # 1
    async def test_register_creator_success(self, db):
        """register_creator creates a Creator row and a TokenAccount with signup bonus."""
        result = await creator_service.register_creator(
            db, "new@example.com", "strongpass123", "New Creator",
            phone="+919999999999", country="in",
        )

        assert result["creator"]["email"] == "new@example.com"
        assert result["creator"]["display_name"] == "New Creator"
        assert result["token"]

        # Verify Creator row exists
        row = (await db.execute(
            select(Creator).where(Creator.id == result["creator"]["id"])
        )).scalar_one()
        assert row.email == "new@example.com"

        # Verify TokenAccount was created with signup bonus
        acct = (await db.execute(
            select(TokenAccount).where(
                TokenAccount.creator_id == result["creator"]["id"]
            )
        )).scalar_one()
        assert float(acct.balance) == 0.10  # $0.10 signup bonus

    # 2
    async def test_register_creator_duplicate_email(self, db):
        """Registering with an already-used email raises ValueError."""
        await creator_service.register_creator(
            db, "dup@example.com", "pass1234", "First Creator",
        )
        with pytest.raises(ValueError, match="Email already registered"):
            await creator_service.register_creator(
                db, "dup@example.com", "pass5678", "Second Creator",
            )

    # 3
    async def test_register_creator_email_lowercased(self, db):
        """Email is stored in lowercase regardless of input casing."""
        result = await creator_service.register_creator(
            db, "  UPPER@Example.COM  ", "pass1234", "Case Tester",
        )

        # The service does email.lower().strip()
        assert result["creator"]["email"] == "upper@example.com"

        # Verify in the database directly
        row = (await db.execute(
            select(Creator).where(Creator.id == result["creator"]["id"])
        )).scalar_one()
        assert row.email == "upper@example.com"

    # 4
    async def test_register_creator_country_uppercased(self, db):
        """Country code is stored in uppercase."""
        result = await creator_service.register_creator(
            db, "country@example.com", "pass1234", "Country Tester",
            country="in",
        )

        assert result["creator"]["country"] == "IN"

        row = (await db.execute(
            select(Creator).where(Creator.id == result["creator"]["id"])
        )).scalar_one()
        assert row.country == "IN"


class TestLoginCreator:
    """Tests 5-8: creator login scenarios."""

    # 5
    async def test_login_creator_success(self, db):
        """Successful login returns a JWT token and creator dict."""
        await creator_service.register_creator(
            db, "login@example.com", "correctpass", "Login User",
        )

        result = await creator_service.login_creator(
            db, "login@example.com", "correctpass",
        )

        assert result["token"]
        assert isinstance(result["token"], str)
        assert len(result["token"]) > 50  # JWTs are long
        assert result["creator"]["email"] == "login@example.com"
        assert result["creator"]["status"] == "active"

    # 6
    async def test_login_creator_wrong_password(self, db):
        """Wrong password raises UnauthorizedError."""
        await creator_service.register_creator(
            db, "wrongpw@example.com", "realpass", "PW User",
        )

        with pytest.raises(UnauthorizedError):
            await creator_service.login_creator(
                db, "wrongpw@example.com", "wrongpass",
            )

    # 7
    async def test_login_creator_wrong_email(self, db):
        """Non-existent email raises UnauthorizedError."""
        with pytest.raises(UnauthorizedError):
            await creator_service.login_creator(
                db, "nonexistent@example.com", "anypassword",
            )

    # 8
    async def test_login_creator_suspended(self, db):
        """Suspended creator cannot log in — raises UnauthorizedError."""
        result = await creator_service.register_creator(
            db, "suspended@example.com", "pass1234", "Suspended User",
        )
        creator_id = result["creator"]["id"]

        # Suspend the creator directly in the database
        row = (await db.execute(
            select(Creator).where(Creator.id == creator_id)
        )).scalar_one()
        row.status = "suspended"
        db.add(row)
        await db.commit()

        with pytest.raises(UnauthorizedError, match="Account is suspended"):
            await creator_service.login_creator(
                db, "suspended@example.com", "pass1234",
            )


class TestUpdateCreator:
    """Tests 9-12: update_creator field handling."""

    # 9
    async def test_update_creator_display_name(self, db):
        """Updating display_name changes it correctly."""
        reg = await creator_service.register_creator(
            db, "update@example.com", "pass1234", "Original Name",
        )
        creator_id = reg["creator"]["id"]

        updated = await creator_service.update_creator(
            db, creator_id, {"display_name": "Updated Name"},
        )

        assert updated["display_name"] == "Updated Name"

        # Verify in DB
        row = (await db.execute(
            select(Creator).where(Creator.id == creator_id)
        )).scalar_one()
        assert row.display_name == "Updated Name"

    # 10
    async def test_update_creator_payout_details_json(self, db):
        """payout_details dict is converted to a JSON string."""
        reg = await creator_service.register_creator(
            db, "payout@example.com", "pass1234", "Payout Creator",
        )
        creator_id = reg["creator"]["id"]

        details = {"upi_id": "user@oksbi", "name": "Test User"}
        await creator_service.update_creator(
            db, creator_id, {"payout_details": details},
        )

        # Read raw from DB — should be a JSON string
        row = (await db.execute(
            select(Creator).where(Creator.id == creator_id)
        )).scalar_one()
        assert isinstance(row.payout_details, str)
        parsed = json.loads(row.payout_details)
        assert parsed["upi_id"] == "user@oksbi"
        assert parsed["name"] == "Test User"

    # 11
    async def test_update_creator_country_uppercased(self, db):
        """country is uppercased when set via update_creator."""
        reg = await creator_service.register_creator(
            db, "countryupd@example.com", "pass1234", "Country Updater",
        )
        creator_id = reg["creator"]["id"]

        updated = await creator_service.update_creator(
            db, creator_id, {"country": "us"},
        )

        assert updated["country"] == "US"

        row = (await db.execute(
            select(Creator).where(Creator.id == creator_id)
        )).scalar_one()
        assert row.country == "US"

    # 12
    async def test_update_creator_disallowed_field(self, db):
        """Fields not in allowed_fields are silently ignored."""
        reg = await creator_service.register_creator(
            db, "disallowed@example.com", "pass1234", "Disallowed Tester",
        )
        creator_id = reg["creator"]["id"]
        original_email = reg["creator"]["email"]

        # Try to update email and status (both disallowed) + display_name (allowed)
        updated = await creator_service.update_creator(
            db, creator_id, {
                "email": "hacked@evil.com",
                "status": "suspended",
                "password_hash": "injected_hash",
                "display_name": "Allowed Change",
            },
        )

        # display_name should change, but email and status should NOT
        assert updated["display_name"] == "Allowed Change"
        assert updated["email"] == original_email  # unchanged
        assert updated["status"] == "active"  # unchanged

        # Verify in DB that password_hash was not modified
        row = (await db.execute(
            select(Creator).where(Creator.id == creator_id)
        )).scalar_one()
        assert row.password_hash != "injected_hash"


class TestLinkAgent:
    """Tests 13-16: agent linking scenarios."""

    # 13
    async def test_link_agent_success(self, db, make_agent):
        """Linking an unclaimed agent sets agent.creator_id correctly."""
        reg = await creator_service.register_creator(
            db, "linker@example.com", "pass1234", "Linker",
        )
        creator_id = reg["creator"]["id"]

        agent, _ = await make_agent("linkable-agent")
        result = await creator_service.link_agent_to_creator(db, creator_id, agent.id)

        assert result["agent_id"] == agent.id
        assert result["creator_id"] == creator_id
        assert result["agent_name"] == "linkable-agent"

        # Verify in DB
        agent_row = (await db.execute(
            select(RegisteredAgent).where(RegisteredAgent.id == agent.id)
        )).scalar_one()
        assert agent_row.creator_id == creator_id

    # 14
    async def test_link_agent_not_found(self, db):
        """Linking a non-existent agent_id raises ValueError."""
        reg = await creator_service.register_creator(
            db, "notfound@example.com", "pass1234", "Not Found Tester",
        )
        creator_id = reg["creator"]["id"]

        with pytest.raises(ValueError, match="Agent not found"):
            await creator_service.link_agent_to_creator(
                db, creator_id, "nonexistent-agent-id",
            )

    # 15
    async def test_link_agent_already_claimed(self, db, make_agent):
        """Linking an agent already claimed by another creator raises ValueError."""
        r1 = await creator_service.register_creator(
            db, "owner@example.com", "pass1234", "Owner",
        )
        r2 = await creator_service.register_creator(
            db, "thief@example.com", "pass1234", "Thief",
        )

        agent, _ = await make_agent("claimed-agent")
        await creator_service.link_agent_to_creator(
            db, r1["creator"]["id"], agent.id,
        )

        with pytest.raises(ValueError, match="already claimed by another creator"):
            await creator_service.link_agent_to_creator(
                db, r2["creator"]["id"], agent.id,
            )

    # 16
    async def test_link_agent_same_creator_ok(self, db, make_agent):
        """Re-linking an agent to the same creator succeeds (idempotent)."""
        reg = await creator_service.register_creator(
            db, "relinker@example.com", "pass1234", "ReLinker",
        )
        creator_id = reg["creator"]["id"]

        agent, _ = await make_agent("relink-agent")

        # Link twice
        first = await creator_service.link_agent_to_creator(
            db, creator_id, agent.id,
        )
        second = await creator_service.link_agent_to_creator(
            db, creator_id, agent.id,
        )

        assert first["creator_id"] == creator_id
        assert second["creator_id"] == creator_id
        assert first["agent_id"] == second["agent_id"]


class TestCreatorAgentsAndDashboard:
    """Tests 17-18: get_creator_agents and get_creator_dashboard."""

    # 17
    async def test_get_creator_agents_with_earnings(self, db, make_agent, make_token_account):
        """get_creator_agents returns agent info including balance and earnings."""
        reg = await creator_service.register_creator(
            db, "agents@example.com", "pass1234", "Agent Owner",
        )
        creator_id = reg["creator"]["id"]

        # Create and link two agents
        agent1, _ = await make_agent("earnings-agent-1")
        agent2, _ = await make_agent("earnings-agent-2")
        await creator_service.link_agent_to_creator(db, creator_id, agent1.id)
        await creator_service.link_agent_to_creator(db, creator_id, agent2.id)

        # Create token accounts with balances for the agents
        acct1 = await make_token_account(agent1.id, 500.0)
        acct1.total_earned = Decimal("750.0")
        acct1.total_spent = Decimal("250.0")
        db.add(acct1)

        acct2 = await make_token_account(agent2.id, 300.0)
        acct2.total_earned = Decimal("400.0")
        acct2.total_spent = Decimal("100.0")
        db.add(acct2)
        await db.commit()

        agents = await creator_service.get_creator_agents(db, creator_id)

        assert len(agents) == 2

        # Find each agent in the result
        by_id = {a["agent_id"]: a for a in agents}

        assert by_id[agent1.id]["balance"] == 500.0
        assert by_id[agent1.id]["total_earned"] == 750.0
        assert by_id[agent1.id]["total_spent"] == 250.0
        assert by_id[agent1.id]["agent_name"] == "earnings-agent-1"

        assert by_id[agent2.id]["balance"] == 300.0
        assert by_id[agent2.id]["total_earned"] == 400.0
        assert by_id[agent2.id]["total_spent"] == 100.0

    # 18
    async def test_get_dashboard_aggregation(self, db, make_agent, make_token_account):
        """get_creator_dashboard aggregates earnings across all linked agents."""
        reg = await creator_service.register_creator(
            db, "dashboard@example.com", "pass1234", "Dashboard Creator",
        )
        creator_id = reg["creator"]["id"]

        # Link two agents with token accounts
        agent1, _ = await make_agent("dash-agent-1")
        agent2, _ = await make_agent("dash-agent-2")
        await creator_service.link_agent_to_creator(db, creator_id, agent1.id)
        await creator_service.link_agent_to_creator(db, creator_id, agent2.id)

        acct1 = await make_token_account(agent1.id, 1000.0)
        acct1.total_earned = Decimal("2000.0")
        acct1.total_spent = Decimal("500.0")
        db.add(acct1)

        acct2 = await make_token_account(agent2.id, 800.0)
        acct2.total_earned = Decimal("1500.0")
        acct2.total_spent = Decimal("300.0")
        db.add(acct2)
        await db.commit()

        dashboard = await creator_service.get_creator_dashboard(db, creator_id)

        assert dashboard["agents_count"] == 2
        assert dashboard["total_agent_earnings"] == pytest.approx(3500.0)  # 2000 + 1500
        assert dashboard["total_agent_spent"] == pytest.approx(800.0)  # 500 + 300

        # Creator's own balance ($0.10 signup bonus)
        assert dashboard["creator_balance"] == pytest.approx(0.10)

        # Agents list should be included
        assert len(dashboard["agents"]) == 2


class TestCreatorWallet:
    """Tests 19-20: get_creator_wallet."""

    # 19
    async def test_get_wallet_with_account(self, db):
        """get_creator_wallet returns full wallet fields when account exists."""
        reg = await creator_service.register_creator(
            db, "wallet@example.com", "pass1234", "Wallet Creator",
        )
        creator_id = reg["creator"]["id"]

        wallet = await creator_service.get_creator_wallet(db, creator_id)

        assert wallet["balance"] == 0.10  # $0.10 signup bonus
        assert wallet["total_earned"] == 0.0
        assert wallet["total_spent"] == 0.0
        assert wallet["total_deposited"] == 0.10  # signup bonus counts as deposit
        assert wallet["total_fees_paid"] == 0.0

    # 20
    async def test_get_wallet_no_account(self, db):
        """get_creator_wallet returns sensible defaults when no TokenAccount exists."""
        # Create a creator manually without a token account
        from marketplace.core.creator_auth import hash_password

        creator = Creator(
            id=_new_id(),
            email="noacct@example.com",
            password_hash=hash_password("pass1234"),
            display_name="No Account",
            status="active",
        )
        db.add(creator)
        await db.commit()

        wallet = await creator_service.get_creator_wallet(db, creator.id)

        assert wallet["balance"] == 0
        assert wallet["total_earned"] == 0
        assert wallet["total_spent"] == 0


# ===========================================================================
# PAYOUT SERVICE TESTS (21-25)
# ===========================================================================


class TestMonthlyPayoutDeep:
    """Tests 21-24: run_monthly_payout deep coverage."""

    # 21
    async def test_monthly_payout_processes_eligible(self, db, make_creator):
        """An eligible creator (active, payout_method set, balance >= min) gets a redemption."""
        creator, acct = await _setup_creator_for_payout(
            db, make_creator, 20.00, payout_method="upi",
        )

        result = await payout_service.run_monthly_payout(db)

        assert result["processed"] == 1
        assert result["errors"] == []

        # Verify a RedemptionRequest was created for this creator
        rr = (await db.execute(
            select(RedemptionRequest).where(
                RedemptionRequest.creator_id == creator.id,
            )
        )).scalar_one()
        assert rr.redemption_type == "upi"
        assert float(rr.amount_usd) == pytest.approx(20.0)

    # 22
    async def test_monthly_payout_skips_inactive(self, db, make_creator):
        """Creators with status != 'active' are excluded from payout."""
        await _setup_creator_for_payout(
            db, make_creator, 20.00, payout_method="upi", status="suspended",
        )

        result = await payout_service.run_monthly_payout(db)

        assert result["processed"] == 0
        assert result["skipped"] == 0  # filtered out by SQL WHERE, not loop skip

        # No redemption requests should exist
        count = (await db.execute(select(RedemptionRequest))).scalars().all()
        assert len(count) == 0

    # 23
    async def test_monthly_payout_skips_no_method(self, db, make_creator):
        """Creators with payout_method='none' are excluded by SQL filter."""
        await _setup_creator_for_payout(
            db, make_creator, 20.00, payout_method="none",
        )

        result = await payout_service.run_monthly_payout(db)

        assert result["processed"] == 0

        # No redemption requests created
        all_rr = (await db.execute(select(RedemptionRequest))).scalars().all()
        assert len(all_rr) == 0

    # 24
    async def test_monthly_payout_type_mapping(self, db, make_creator):
        """payout_method is correctly mapped to redemption_type:
        upi -> upi, bank -> bank_withdrawal, gift_card -> gift_card.
        """
        c_upi, _ = await _setup_creator_for_payout(
            db, make_creator, 20.00, payout_method="upi",
        )
        c_bank, _ = await _setup_creator_for_payout(
            db, make_creator, 20.00, payout_method="bank",
        )
        c_gift, _ = await _setup_creator_for_payout(
            db, make_creator, 20.00, payout_method="gift_card",
        )

        result = await payout_service.run_monthly_payout(db)

        assert result["processed"] == 3
        assert result["errors"] == []

        # Verify each creator's redemption type
        for creator_id, expected_type in [
            (c_upi.id, "upi"),
            (c_bank.id, "bank_withdrawal"),
            (c_gift.id, "gift_card"),
        ]:
            rr = (await db.execute(
                select(RedemptionRequest).where(
                    RedemptionRequest.creator_id == creator_id,
                )
            )).scalar_one()
            assert rr.redemption_type == expected_type, (
                f"Expected {expected_type} for creator {creator_id}, got {rr.redemption_type}"
            )


class TestProcessPendingPayoutsDeep:
    """Test 25: process_pending_payouts."""

    # 25
    async def test_process_pending_payouts(self, db, make_creator):
        """process_pending_payouts finds and processes all pending RedemptionRequests."""
        # Create a creator with enough balance for multiple redemptions
        creator, acct = await _setup_creator_for_payout(
            db, make_creator, 1000.00, payout_method="upi",
        )

        # Create some pending redemptions directly
        # (gift_card and bank_withdrawal stay pending; api_credits auto-completes)
        gift = await redemption_service.create_redemption(
            db, creator.id, "gift_card", 10.00,
        )
        upi = await redemption_service.create_redemption(
            db, creator.id, "upi", 50.00,
        )
        bank = await redemption_service.create_redemption(
            db, creator.id, "bank_withdrawal", 100.00,
        )

        assert gift["status"] == "pending"
        assert upi["status"] == "pending"
        assert bank["status"] == "pending"

        result = await payout_service.process_pending_payouts(db)

        assert result["total_pending"] == 3
        assert result["processed"] == 3

        # All should now be in "processing" state
        for rid in (gift["id"], upi["id"], bank["id"]):
            row = (await db.execute(
                select(RedemptionRequest).where(RedemptionRequest.id == rid)
            )).scalar_one()
            assert row.status == "processing", (
                f"Redemption {rid} expected 'processing', got '{row.status}'"
            )
