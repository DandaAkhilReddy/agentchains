"""Tests for Creator accounts, agent linking, royalty auto-flow, and dashboard."""
import pytest
import uuid
from decimal import Decimal

from marketplace.core.creator_auth import create_creator_token, hash_password, verify_password
from marketplace.models.creator import Creator
from marketplace.models.token_account import TokenAccount
from marketplace.services import creator_service
from marketplace.services.token_service import (
    create_account,
    deposit,
    ensure_platform_account,
    transfer,
    get_balance,
    _get_account_by_creator,
)


def _id():
    return str(uuid.uuid4())


# ---------------------------------------------------------------------------
# Creator Auth
# ---------------------------------------------------------------------------

class TestCreatorAuth:
    def test_password_hash_verify(self):
        hashed = hash_password("MySecurePass123")
        assert verify_password("MySecurePass123", hashed)
        assert not verify_password("WrongPassword", hashed)

    def test_create_creator_token(self):
        token = create_creator_token("creator-123", "test@example.com")
        assert isinstance(token, str)
        assert len(token) > 50  # JWT is long


# ---------------------------------------------------------------------------
# Creator Registration
# ---------------------------------------------------------------------------

class TestCreatorRegistration:
    async def test_register_creator(self, db):
        await ensure_platform_account(db)
        result = await creator_service.register_creator(
            db, "test@creator.com", "password123", "Test Creator", phone="+919876543210", country="IN"
        )
        assert result["creator"]["email"] == "test@creator.com"
        assert result["creator"]["display_name"] == "Test Creator"
        assert result["token"]

    async def test_register_duplicate_email_fails(self, db):
        await ensure_platform_account(db)
        await creator_service.register_creator(db, "dup@test.com", "pass1234", "First")
        with pytest.raises(ValueError, match="Email already registered"):
            await creator_service.register_creator(db, "dup@test.com", "pass5678", "Second")

    async def test_creator_gets_signup_bonus(self, db):
        await ensure_platform_account(db)
        result = await creator_service.register_creator(db, "bonus@test.com", "pass1234", "Bonus User")
        creator_id = result["creator"]["id"]
        acct = await _get_account_by_creator(db, creator_id)
        assert acct is not None
        assert float(acct.balance) == 100.0  # signup bonus


# ---------------------------------------------------------------------------
# Creator Login
# ---------------------------------------------------------------------------

class TestCreatorLogin:
    async def test_login_success(self, db):
        await ensure_platform_account(db)
        await creator_service.register_creator(db, "login@test.com", "secure123", "Login User")
        result = await creator_service.login_creator(db, "login@test.com", "secure123")
        assert result["token"]
        assert result["creator"]["email"] == "login@test.com"

    async def test_login_wrong_password(self, db):
        await ensure_platform_account(db)
        await creator_service.register_creator(db, "wrong@test.com", "correct123", "User")
        from marketplace.core.exceptions import UnauthorizedError
        with pytest.raises(UnauthorizedError):
            await creator_service.login_creator(db, "wrong@test.com", "incorrect")


# ---------------------------------------------------------------------------
# Agent Linking
# ---------------------------------------------------------------------------

class TestAgentLinking:
    async def test_link_agent_to_creator(self, db, make_agent):
        await ensure_platform_account(db)
        result = await creator_service.register_creator(db, "link@test.com", "pass1234", "Linker")
        creator_id = result["creator"]["id"]

        agent, _token = await make_agent("my-agent")
        link = await creator_service.link_agent_to_creator(db, creator_id, agent.id)
        assert link["creator_id"] == creator_id
        assert link["agent_id"] == agent.id

    async def test_link_already_claimed_fails(self, db, make_agent):
        await ensure_platform_account(db)
        r1 = await creator_service.register_creator(db, "first@test.com", "pass1234", "First")
        r2 = await creator_service.register_creator(db, "second@test.com", "pass1234", "Second")

        agent, _ = await make_agent("claimed-agent")
        await creator_service.link_agent_to_creator(db, r1["creator"]["id"], agent.id)

        with pytest.raises(ValueError, match="already claimed"):
            await creator_service.link_agent_to_creator(db, r2["creator"]["id"], agent.id)


# ---------------------------------------------------------------------------
# Creator Royalty Auto-Flow
# ---------------------------------------------------------------------------

class TestCreatorRoyalty:
    async def test_royalty_flows_on_purchase(self, db, make_agent, make_token_account):
        """When a seller agent earns ARD from a purchase, earnings should auto-flow to creator."""
        platform = await ensure_platform_account(db)

        # Create creator and link an agent
        reg = await creator_service.register_creator(db, "royalty@test.com", "pass1234", "Royalty Tester")
        creator_id = reg["creator"]["id"]

        seller, _ = await make_agent("seller-agent")
        await creator_service.link_agent_to_creator(db, creator_id, seller.id)
        seller_acct = await create_account(db, seller.id)

        buyer, _ = await make_agent("buyer-agent")
        buyer_acct = await make_token_account(buyer.id, 10000)

        # Transfer (simulating a purchase)
        await transfer(db, buyer.id, seller.id, 1000, "purchase", reference_id="tx-123")

        # Creator should have received royalty (100% of net earnings)
        creator_acct = await _get_account_by_creator(db, creator_id)
        assert creator_acct is not None
        # Net earnings to seller: 1000 - 2% fee = 980 ARD
        # Creator royalty: 100% of 980 = 980 ARD
        # But creator also had signup bonus of 100
        assert float(creator_acct.balance) >= 1000  # 100 bonus + 980 royalty


# ---------------------------------------------------------------------------
# Creator Dashboard
# ---------------------------------------------------------------------------

class TestCreatorDashboard:
    async def test_dashboard_data(self, db, make_agent):
        await ensure_platform_account(db)
        reg = await creator_service.register_creator(db, "dash@test.com", "pass1234", "Dashboard User")
        creator_id = reg["creator"]["id"]

        agent, _ = await make_agent("dash-agent")
        await creator_service.link_agent_to_creator(db, creator_id, agent.id)

        dashboard = await creator_service.get_creator_dashboard(db, creator_id)
        assert dashboard["agents_count"] == 1
        assert dashboard["token_name"] == "ARD"

    async def test_wallet_shows_balance(self, db):
        await ensure_platform_account(db)
        reg = await creator_service.register_creator(db, "wallet@test.com", "pass1234", "Wallet User")
        creator_id = reg["creator"]["id"]

        wallet = await creator_service.get_creator_wallet(db, creator_id)
        assert wallet["balance"] == 100.0  # signup bonus
        assert wallet["token_name"] == "ARD"
