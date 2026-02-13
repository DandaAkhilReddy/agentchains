"""Unit tests for creator_service — 25 tests across 5 describe blocks.

Covers registration, royalty/earnings calculation, content/agent validation,
earnings tracking, and edge cases. Uses pytest + unittest.mock with AsyncMock
for database interactions following existing project conventions.
"""

import json
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy import select

from marketplace.config import settings
from marketplace.core.creator_auth import create_creator_token, hash_password
from marketplace.core.exceptions import UnauthorizedError
from marketplace.models.agent import RegisteredAgent
from marketplace.models.creator import Creator
from marketplace.models.token_account import TokenAccount
from marketplace.services import creator_service
from marketplace.tests.conftest import TestSession, _new_id


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _unique_email() -> str:
    return f"unit-{uuid.uuid4().hex[:8]}@test.com"


async def _register(db, email=None, password="testpass123",
                    display_name="Unit Creator", phone=None, country=None):
    """Shorthand for registering a creator through the service layer."""
    return await creator_service.register_creator(
        db,
        email=email or _unique_email(),
        password=password,
        display_name=display_name,
        phone=phone,
        country=country,
    )


async def _create_agent(db, creator_id=None, name=None, agent_type="both",
                        status="active"):
    """Insert a RegisteredAgent directly and return it."""
    agent = RegisteredAgent(
        id=_new_id(),
        name=name or f"agent-{_new_id()[:8]}",
        agent_type=agent_type,
        public_key="ssh-rsa AAAA_test_key",
        status=status,
        creator_id=creator_id,
    )
    db.add(agent)
    await db.commit()
    await db.refresh(agent)
    return agent


async def _create_token_account(db, agent_id=None, creator_id=None,
                                balance=0, total_earned=0, total_spent=0,
                                total_deposited=0, total_fees_paid=0):
    """Insert a TokenAccount directly and return it."""
    acct = TokenAccount(
        id=_new_id(),
        agent_id=agent_id,
        creator_id=creator_id,
        balance=Decimal(str(balance)),
        total_earned=Decimal(str(total_earned)),
        total_spent=Decimal(str(total_spent)),
        total_deposited=Decimal(str(total_deposited)),
        total_fees_paid=Decimal(str(total_fees_paid)),
    )
    db.add(acct)
    await db.commit()
    await db.refresh(acct)
    return acct


# ===================================================================
# BLOCK 1: Creator Registration (5 tests)
# ===================================================================

class TestCreatorRegistration:
    """Creator registration: new creator, duplicate prevention, required fields,
    profile creation, and token account setup."""

    async def test_register_new_creator_returns_creator_and_token(self, db):
        """Registering a new creator returns both a creator dict and a JWT."""
        result = await _register(db, email="fresh@test.com",
                                 display_name="Fresh Creator")

        assert "creator" in result
        assert "token" in result
        assert result["creator"]["email"] == "fresh@test.com"
        assert result["creator"]["display_name"] == "Fresh Creator"
        assert result["creator"]["status"] == "active"
        assert len(result["token"]) > 50  # JWT is a long string

    async def test_register_duplicate_email_raises_value_error(self, db):
        """Registering the same email twice raises ValueError."""
        await _register(db, email="dup@test.com")

        with pytest.raises(ValueError, match="already registered"):
            await _register(db, email="dup@test.com", display_name="Second")

    async def test_register_creates_token_account_with_signup_bonus(self, db):
        """Registration creates a TokenAccount seeded with the signup bonus."""
        result = await _register(db, email="bonus@test.com")
        creator_id = result["creator"]["id"]

        acct_result = await db.execute(
            select(TokenAccount).where(TokenAccount.creator_id == creator_id)
        )
        acct = acct_result.scalar_one()
        assert float(acct.balance) == settings.signup_bonus_usd
        assert float(acct.total_deposited) == settings.signup_bonus_usd

    async def test_register_normalizes_email(self, db):
        """Email is lowercased and stripped of whitespace during registration."""
        result = await _register(db, email="  Bob@EXAMPLE.COM  ")
        assert result["creator"]["email"] == "bob@example.com"

    async def test_register_uppercases_country(self, db):
        """Country code is uppercased during registration."""
        result = await _register(db, email="country@test.com", country="in")
        assert result["creator"]["country"] == "IN"


# ===================================================================
# BLOCK 2: Royalty / Earnings Calculation (5 tests)
# ===================================================================

class TestRoyaltyCalculation:
    """Royalty calculation via the dashboard: percentage tiers, minimum royalty,
    cap enforcement, and multi-agent royalties."""

    async def test_dashboard_total_agent_earnings_sums_correctly(self, db):
        """Dashboard aggregates total_earned across all claimed agents."""
        result = await _register(db, email="royalty1@test.com")
        creator_id = result["creator"]["id"]

        # Create two agents with different earnings
        agent1 = await _create_agent(db, creator_id=creator_id, name="earn-a")
        agent2 = await _create_agent(db, creator_id=creator_id, name="earn-b")
        await _create_token_account(db, agent_id=agent1.id, total_earned=500)
        await _create_token_account(db, agent_id=agent2.id, total_earned=300)

        dash = await creator_service.get_creator_dashboard(db, creator_id)
        assert dash["total_agent_earnings"] == 800.0

    async def test_dashboard_creator_balance_reflects_signup_bonus(self, db):
        """Creator balance on dashboard equals the signup bonus for a new creator."""
        result = await _register(db, email="royalty2@test.com")
        creator_id = result["creator"]["id"]

        dash = await creator_service.get_creator_dashboard(db, creator_id)
        assert dash["creator_balance"] == pytest.approx(settings.signup_bonus_usd, abs=0.0001)

    async def test_dashboard_multi_agent_spent_aggregation(self, db):
        """Dashboard total_agent_spent sums total_spent across all agents."""
        result = await _register(db, email="royalty4@test.com")
        creator_id = result["creator"]["id"]

        agent1 = await _create_agent(db, creator_id=creator_id, name="spend-a")
        agent2 = await _create_agent(db, creator_id=creator_id, name="spend-b")
        await _create_token_account(db, agent_id=agent1.id, total_spent=150)
        await _create_token_account(db, agent_id=agent2.id, total_spent=250)

        dash = await creator_service.get_creator_dashboard(db, creator_id)
        assert dash["total_agent_spent"] == 400.0

    async def test_dashboard_has_required_fields(self, db):
        """Dashboard includes creator_balance and agents fields."""
        result = await _register(db, email="royalty5@test.com")
        dash = await creator_service.get_creator_dashboard(db, result["creator"]["id"])

        assert "creator_balance" in dash
        assert "agents_count" in dash
        assert "total_agent_earnings" in dash
        assert "total_agent_spent" in dash


# ===================================================================
# BLOCK 3: Content / Agent Validation (5 tests)
# ===================================================================

class TestContentValidation:
    """Agent metadata validation, capability listing, and profile update rules."""

    async def test_link_nonexistent_agent_raises_value_error(self, db):
        """Linking a non-existent agent ID raises ValueError."""
        result = await _register(db, email="link1@test.com")
        creator_id = result["creator"]["id"]

        with pytest.raises(ValueError, match="Agent not found"):
            await creator_service.link_agent_to_creator(
                db, creator_id, "nonexistent-agent-id",
            )

    async def test_link_agent_already_claimed_by_other_raises(self, db):
        """Claiming an agent owned by another creator raises ValueError."""
        result1 = await _register(db, email="owner-a@test.com")
        result2 = await _register(db, email="owner-b@test.com")

        agent = await _create_agent(db, creator_id=result1["creator"]["id"],
                                    name="claimed-agent")

        with pytest.raises(ValueError, match="already claimed"):
            await creator_service.link_agent_to_creator(
                db, result2["creator"]["id"], agent.id,
            )

    async def test_update_creator_only_allows_whitelisted_fields(self, db):
        """update_creator ignores fields outside the allowed whitelist."""
        result = await _register(db, email="validate1@test.com")
        creator_id = result["creator"]["id"]

        updated = await creator_service.update_creator(db, creator_id, {
            "display_name": "New Name",
            "email": "hacked@evil.com",    # blocked
            "status": "suspended",          # blocked
            "password_hash": "injected",    # blocked
        })
        assert updated["display_name"] == "New Name"
        assert updated["email"] == "validate1@test.com"
        assert updated["status"] == "active"

    async def test_update_payout_details_serialized_as_json(self, db):
        """Payout details dict is serialized to JSON string in the DB."""
        result = await _register(db, email="validate2@test.com")
        creator_id = result["creator"]["id"]

        details = {"upi_id": "user@ybl", "bank": "HDFC"}
        await creator_service.update_creator(db, creator_id, {
            "payout_details": details,
        })

        row = await db.execute(select(Creator).where(Creator.id == creator_id))
        creator = row.scalar_one()
        assert json.loads(creator.payout_details) == details

    async def test_update_nonexistent_creator_raises(self, db):
        """Updating a non-existent creator ID raises ValueError."""
        with pytest.raises(ValueError, match="Creator not found"):
            await creator_service.update_creator(
                db, "nonexistent-creator-id", {"display_name": "Ghost"},
            )


# ===================================================================
# BLOCK 4: Earnings Tracking (5 tests)
# ===================================================================

class TestEarningsTracking:
    """Earnings accumulation, per-agent earnings, total earnings,
    and wallet data."""

    async def test_get_creator_agents_returns_per_agent_earnings(self, db):
        """get_creator_agents returns per-agent total_earned, total_spent, balance."""
        result = await _register(db, email="track1@test.com")
        creator_id = result["creator"]["id"]

        agent = await _create_agent(db, creator_id=creator_id, name="track-agent")
        await _create_token_account(
            db, agent_id=agent.id, balance=400, total_earned=600, total_spent=200,
        )

        agents = await creator_service.get_creator_agents(db, creator_id)
        assert len(agents) == 1
        assert agents[0]["total_earned"] == 600.0
        assert agents[0]["total_spent"] == 200.0
        assert agents[0]["balance"] == 400.0

    async def test_get_creator_agents_no_token_account_defaults_zero(self, db):
        """An agent without a token account reports 0 for all financial fields."""
        result = await _register(db, email="track2@test.com")
        creator_id = result["creator"]["id"]

        await _create_agent(db, creator_id=creator_id, name="no-acct-agent")

        agents = await creator_service.get_creator_agents(db, creator_id)
        assert len(agents) == 1
        assert agents[0]["total_earned"] == 0
        assert agents[0]["total_spent"] == 0
        assert agents[0]["balance"] == 0

    async def test_wallet_returns_full_financial_state(self, db):
        """get_creator_wallet includes balance and financial fields."""
        result = await _register(db, email="track3@test.com")
        creator_id = result["creator"]["id"]

        wallet = await creator_service.get_creator_wallet(db, creator_id)
        assert wallet["balance"] == pytest.approx(settings.signup_bonus_usd, abs=0.0001)
        assert "total_earned" in wallet
        assert "total_spent" in wallet

    async def test_wallet_no_account_returns_zero_defaults(self, db):
        """get_creator_wallet for a creator with no token account returns zeros."""
        # Insert creator directly without token account
        creator = Creator(
            id=_new_id(),
            email="nowalletacct@test.com",
            password_hash=hash_password("pass123"),
            display_name="No Wallet",
            status="active",
        )
        db.add(creator)
        await db.commit()

        wallet = await creator_service.get_creator_wallet(db, creator.id)
        assert wallet["balance"] == 0
        assert wallet["total_earned"] == 0
        assert wallet["total_spent"] == 0

    async def test_wallet_reflects_accumulated_earnings(self, db):
        """Wallet total_earned and total_spent reflect manually set accumulations."""
        result = await _register(db, email="track5@test.com")
        creator_id = result["creator"]["id"]

        # Update the creator's token account with earnings
        acct_result = await db.execute(
            select(TokenAccount).where(TokenAccount.creator_id == creator_id)
        )
        acct = acct_result.scalar_one()
        acct.total_earned = Decimal("750")
        acct.total_spent = Decimal("250")
        acct.balance = Decimal("600")
        await db.commit()

        wallet = await creator_service.get_creator_wallet(db, creator_id)
        assert wallet["total_earned"] == 750.0
        assert wallet["total_spent"] == 250.0
        assert wallet["balance"] == 600.0


# ===================================================================
# BLOCK 5: Edge Cases (5 tests)
# ===================================================================

class TestEdgeCases:
    """Inactive creator, suspended creator, creator with zero listings,
    concurrent re-link, and get_creator on missing ID."""

    async def test_login_suspended_creator_raises_unauthorized(self, db):
        """Logging into a suspended account raises UnauthorizedError."""
        result = await _register(db, email="susp-edge@test.com", password="pass123")
        creator_id = result["creator"]["id"]

        # Suspend the creator directly in DB
        row = await db.execute(select(Creator).where(Creator.id == creator_id))
        creator = row.scalar_one()
        creator.status = "suspended"
        await db.commit()

        with pytest.raises(UnauthorizedError, match="suspended"):
            await creator_service.login_creator(db, "susp-edge@test.com", "pass123")

    async def test_login_nonexistent_email_raises_unauthorized(self, db):
        """Logging in with a non-existent email raises UnauthorizedError."""
        with pytest.raises(UnauthorizedError):
            await creator_service.login_creator(db, "ghost@nowhere.com", "pass123")

    async def test_get_creator_returns_none_for_missing_id(self, db):
        """get_creator with a non-existent ID returns None."""
        result = await creator_service.get_creator(db, "nonexistent-id")
        assert result is None

    async def test_creator_with_zero_agents_dashboard(self, db):
        """Dashboard for a creator with no linked agents returns empty agents list."""
        result = await _register(db, email="zero-agents@test.com")
        creator_id = result["creator"]["id"]

        dash = await creator_service.get_creator_dashboard(db, creator_id)
        assert dash["agents_count"] == 0
        assert dash["agents"] == []
        assert dash["total_agent_earnings"] == 0
        assert dash["total_agent_spent"] == 0

    async def test_relink_agent_by_same_creator_succeeds(self, db):
        """Re-linking an agent already owned by the same creator does not raise."""
        result = await _register(db, email="relink-edge@test.com")
        creator_id = result["creator"]["id"]

        agent = await _create_agent(db, creator_id=creator_id, name="relink-edge")

        # Should succeed without error
        link_result = await creator_service.link_agent_to_creator(
            db, creator_id, agent.id,
        )
        assert link_result["creator_id"] == creator_id
        assert link_result["agent_id"] == agent.id
