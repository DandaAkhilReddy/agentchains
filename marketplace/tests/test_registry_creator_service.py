"""UT-8: Comprehensive tests for registry_service and creator_service.

Covers agent registration, lookup, listing/filtering, update, heartbeat,
deactivation, caching, and the full creator lifecycle: registration, login,
profile updates, agent linking, dashboard, and wallet.

30 tests total (15 registry + 15 creator).
"""

import uuid
from datetime import datetime, timezone
from decimal import Decimal

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from marketplace.config import settings
from marketplace.core.exceptions import (
    AgentAlreadyExistsError,
    AgentNotFoundError,
    UnauthorizedError,
)
from marketplace.models.agent import RegisteredAgent
from marketplace.models.creator import Creator
from marketplace.models.reputation import ReputationScore
from marketplace.models.token_account import TokenAccount
from marketplace.schemas.agent import AgentRegisterRequest, AgentUpdateRequest
from marketplace.services import creator_service, registry_service
from marketplace.services.cache_service import agent_cache
from marketplace.services.token_service import ensure_platform_account


def _id() -> str:
    return str(uuid.uuid4())


def _make_register_request(
    name: str | None = None,
    agent_type: str = "both",
    **overrides,
) -> AgentRegisterRequest:
    """Build an AgentRegisterRequest with sensible defaults."""
    return AgentRegisterRequest(
        name=name or f"agent-{_id()[:8]}",
        description=overrides.get("description", "A test agent"),
        agent_type=agent_type,
        public_key=overrides.get("public_key", "ssh-rsa AAAA_placeholder_test_key"),
        wallet_address=overrides.get("wallet_address", ""),
        capabilities=overrides.get("capabilities", ["search", "summarise"]),
        a2a_endpoint=overrides.get("a2a_endpoint", "https://agent.example.com"),
    )


# ==========================================================================
# Registry Service  (15 tests)
# ==========================================================================


class TestRegisterAgent:
    """Tests 1-3: register_agent full flow, duplicate, reputation."""

    async def test_register_agent_success(self, db: AsyncSession):
        """1. Full registration flow returns id, name, jwt_token, agent_card_url, created_at."""
        req = _make_register_request(name="alpha-agent")
        resp = await registry_service.register_agent(db, req)

        assert resp.id  # non-empty UUID string
        assert resp.name == "alpha-agent"
        assert resp.jwt_token  # JWT string present
        assert len(resp.jwt_token) > 50  # valid JWT length
        assert resp.agent_card_url == "https://agent.example.com/.well-known/agent.json"
        assert resp.created_at is not None

    async def test_register_agent_duplicate_name(self, db: AsyncSession):
        """2. Registering the same name twice raises AgentAlreadyExistsError."""
        req = _make_register_request(name="duplicate-name")
        await registry_service.register_agent(db, req)

        with pytest.raises(AgentAlreadyExistsError) as exc_info:
            await registry_service.register_agent(db, req)
        assert exc_info.value.status_code == 409

    async def test_register_agent_creates_reputation(self, db: AsyncSession):
        """3. Registration creates a ReputationScore row for the new agent."""
        req = _make_register_request(name="rep-agent")
        resp = await registry_service.register_agent(db, req)

        result = await db.execute(
            select(ReputationScore).where(ReputationScore.agent_id == resp.id)
        )
        rep = result.scalar_one_or_none()
        assert rep is not None
        assert rep.agent_id == resp.id
        assert rep.total_transactions == 0
        assert float(rep.composite_score) == pytest.approx(0.5, abs=0.01)


class TestGetAgent:
    """Tests 4-6: get_agent from DB, cached, not found."""

    async def test_get_agent_from_db(self, db: AsyncSession, make_agent):
        """4. get_agent fetches the correct agent from the database."""
        agent, _ = await make_agent("findable-agent")
        found = await registry_service.get_agent(db, agent.id)

        assert isinstance(found, RegisteredAgent)
        assert found.id == agent.id
        assert found.name == "findable-agent"

    async def test_get_agent_cached(self, db: AsyncSession, make_agent):
        """5. Second call to get_agent uses cache (cache hit)."""
        agent, _ = await make_agent("cached-agent")
        cache_key = f"agent:{agent.id}"

        # Before first call, cache should be empty for this key
        assert agent_cache.get(cache_key) is None

        # First call: populates cache
        await registry_service.get_agent(db, agent.id)
        assert agent_cache.get(cache_key) is not None

        # Second call: cache hit (verify via hit counter)
        hits_before = agent_cache._hits
        result = await registry_service.get_agent(db, agent.id)
        assert agent_cache._hits == hits_before + 1
        assert result.id == agent.id

    async def test_get_agent_not_found(self, db: AsyncSession):
        """6. get_agent raises AgentNotFoundError for a non-existent ID."""
        fake_id = _id()
        with pytest.raises(AgentNotFoundError) as exc_info:
            await registry_service.get_agent(db, fake_id)
        assert exc_info.value.status_code == 404


class TestListAgents:
    """Tests 7-10: list_agents all, filter type, filter status, pagination."""

    async def test_list_agents_all(self, db: AsyncSession, make_agent):
        """7. list_agents with no filters returns all agents and correct total count."""
        await make_agent("list-a")
        await make_agent("list-b")
        await make_agent("list-c")

        agents, total = await registry_service.list_agents(db)
        assert total == 3
        assert len(agents) == 3

    async def test_list_agents_filter_type(self, db: AsyncSession, make_agent):
        """8. list_agents filters by agent_type correctly."""
        await make_agent("seller-1", agent_type="seller")
        await make_agent("buyer-1", agent_type="buyer")
        await make_agent("both-1", agent_type="both")

        sellers, total = await registry_service.list_agents(db, agent_type="seller")
        assert total == 1
        assert len(sellers) == 1
        assert sellers[0].agent_type == "seller"

    async def test_list_agents_filter_status(self, db: AsyncSession, make_agent):
        """9. list_agents can filter by status (active vs deactivated)."""
        agent_a, _ = await make_agent("active-agent")
        agent_b, _ = await make_agent("deact-agent")
        await registry_service.deactivate_agent(db, agent_b.id)

        active_agents, total = await registry_service.list_agents(db, status="active")
        assert total == 1
        assert active_agents[0].name == "active-agent"

    async def test_list_agents_pagination(self, db: AsyncSession, make_agent):
        """10. list_agents respects page and page_size parameters."""
        for i in range(5):
            await make_agent(f"page-agent-{i}")

        page1, total = await registry_service.list_agents(db, page=1, page_size=2)
        assert total == 5
        assert len(page1) == 2

        page3, _ = await registry_service.list_agents(db, page=3, page_size=2)
        assert len(page3) == 1  # 5 items, page_size 2: pages are [2, 2, 1]


class TestUpdateAgent:
    """Tests 11-12: update_agent fields and cache invalidation."""

    async def test_update_agent_fields(self, db: AsyncSession, make_agent):
        """11. update_agent changes description and sets updated_at."""
        agent, _ = await make_agent("update-me")
        original_updated_at = agent.updated_at

        req = AgentUpdateRequest(description="New description here")
        updated = await registry_service.update_agent(db, agent.id, req)

        assert updated.description == "New description here"
        assert updated.updated_at is not None
        # updated_at should be at or after the original timestamp
        assert updated.updated_at >= original_updated_at

    async def test_update_agent_invalidates_cache(self, db: AsyncSession, make_agent):
        """12. After update_agent, the cache entry for that agent is invalidated."""
        agent, _ = await make_agent("cache-inval-agent")
        cache_key = f"agent:{agent.id}"

        # Populate the cache
        await registry_service.get_agent(db, agent.id)
        assert agent_cache.get(cache_key) is not None

        # Update the agent
        req = AgentUpdateRequest(description="changed")
        await registry_service.update_agent(db, agent.id, req)

        # Cache should be cleared for this key
        assert agent_cache.get(cache_key) is None


class TestHeartbeat:
    """Test 13: heartbeat updates last_seen_at."""

    async def test_heartbeat_updates_last_seen(self, db: AsyncSession, make_agent):
        """13. heartbeat sets last_seen_at to a recent timestamp."""
        agent, _ = await make_agent("heartbeat-agent")
        assert agent.last_seen_at is None  # Not set initially

        updated = await registry_service.heartbeat(db, agent.id)

        assert updated.last_seen_at is not None


class TestDeactivateAgent:
    """Tests 14-15: deactivate_agent status and cache invalidation."""

    async def test_deactivate_agent(self, db: AsyncSession, make_agent):
        """14. deactivate_agent changes status to 'deactivated'."""
        agent, _ = await make_agent("deact-agent")
        assert agent.status == "active"

        deactivated = await registry_service.deactivate_agent(db, agent.id)
        assert deactivated.status == "deactivated"

    async def test_deactivate_agent_invalidates_cache(self, db: AsyncSession, make_agent):
        """15. After deactivate_agent, the cache entry is invalidated."""
        agent, _ = await make_agent("deact-cache-agent")
        cache_key = f"agent:{agent.id}"

        # Populate the cache
        await registry_service.get_agent(db, agent.id)
        assert agent_cache.get(cache_key) is not None

        # Deactivate the agent
        await registry_service.deactivate_agent(db, agent.id)

        # Cache should be cleared for this key
        assert agent_cache.get(cache_key) is None


# ==========================================================================
# Creator Service  (15 tests)
# ==========================================================================


class TestRegisterCreator:
    """Tests 16-19: register_creator success, duplicate, email normalization, country uppercase."""

    async def test_register_creator_success(self, db: AsyncSession, seed_platform):
        """16. register_creator creates creator + TokenAccount with signup bonus and returns JWT."""
        result = await creator_service.register_creator(
            db, "new@creator.io", "StrongP@ss1", "New Creator",
            phone="+14155551234", country="us",
        )

        assert result["creator"]["email"] == "new@creator.io"
        assert result["creator"]["display_name"] == "New Creator"
        assert result["creator"]["country"] == "US"
        assert isinstance(result["token"], str)
        assert len(result["token"]) > 50

        # Verify TokenAccount was created with signup bonus
        creator_id = result["creator"]["id"]
        acct_result = await db.execute(
            select(TokenAccount).where(TokenAccount.creator_id == creator_id)
        )
        acct = acct_result.scalar_one_or_none()
        assert acct is not None
        assert float(acct.balance) == pytest.approx(settings.signup_bonus_usd)

    async def test_register_creator_duplicate_email(self, db: AsyncSession, seed_platform):
        """17. Registering with the same email twice raises ValueError."""
        await creator_service.register_creator(db, "dup@example.com", "pass1", "First")
        with pytest.raises(ValueError, match="Email already registered"):
            await creator_service.register_creator(db, "dup@example.com", "pass2", "Second")

    async def test_register_creator_email_normalized(self, db: AsyncSession, seed_platform):
        """18. Email is lowercased and stripped during registration."""
        result = await creator_service.register_creator(
            db, "  MiXeD@CaSe.COM  ", "pass1234", "Normalizer",
        )
        assert result["creator"]["email"] == "mixed@case.com"

    async def test_register_creator_country_uppercase(self, db: AsyncSession, seed_platform):
        """19. Country code 'in' is stored as 'IN' (uppercased)."""
        result = await creator_service.register_creator(
            db, "india@creator.io", "pass1234", "India Creator",
            country="in",
        )
        assert result["creator"]["country"] == "IN"


class TestLoginCreator:
    """Tests 20-22: login_creator success, wrong password, inactive account."""

    async def test_login_creator_success(self, db: AsyncSession, seed_platform):
        """20. Correct credentials return creator dict and JWT token."""
        await creator_service.register_creator(
            db, "login@ok.com", "correcthorse", "Login OK",
        )
        result = await creator_service.login_creator(db, "login@ok.com", "correcthorse")

        assert result["creator"]["email"] == "login@ok.com"
        assert isinstance(result["token"], str)
        assert len(result["token"]) > 50

    async def test_login_creator_wrong_password(self, db: AsyncSession, seed_platform):
        """21. Wrong password raises UnauthorizedError."""
        await creator_service.register_creator(
            db, "bad@pass.com", "rightpass", "User",
        )
        with pytest.raises(UnauthorizedError):
            await creator_service.login_creator(db, "bad@pass.com", "wrongpass")

    async def test_login_creator_inactive(self, db: AsyncSession, seed_platform):
        """22. Inactive/suspended account raises UnauthorizedError."""
        await creator_service.register_creator(
            db, "suspended@test.com", "pass1234", "Soon Suspended",
        )
        # Manually suspend the creator
        result = await db.execute(
            select(Creator).where(Creator.email == "suspended@test.com")
        )
        creator = result.scalar_one()
        creator.status = "suspended"
        await db.commit()

        with pytest.raises(UnauthorizedError):
            await creator_service.login_creator(db, "suspended@test.com", "pass1234")


class TestGetCreator:
    """Tests 23-24: get_creator exists and not found."""

    async def test_get_creator_exists(self, db: AsyncSession, make_creator):
        """23. get_creator returns a dict with creator data when the ID exists."""
        creator, _ = await make_creator(email="found@test.com", display_name="Findable")
        result = await creator_service.get_creator(db, creator.id)

        assert result is not None
        assert result["id"] == creator.id
        assert result["email"] == "found@test.com"
        assert result["display_name"] == "Findable"

    async def test_get_creator_not_found(self, db: AsyncSession):
        """24. get_creator returns None for a non-existent creator ID."""
        result = await creator_service.get_creator(db, _id())
        assert result is None


class TestUpdateCreator:
    """Test 25: update_creator allowed fields."""

    async def test_update_creator_allowed_fields(self, db: AsyncSession, make_creator):
        """25. update_creator changes display_name, phone, country; ignores disallowed fields."""
        creator, _ = await make_creator(display_name="Old Name")
        result = await creator_service.update_creator(
            db,
            creator.id,
            {
                "display_name": "New Name",
                "phone": "+919876543210",
                "country": "in",
                # email is not in allowed_fields; should be silently ignored
                "email": "hacked@evil.com",
            },
        )
        assert result["display_name"] == "New Name"
        assert result["phone"] == "+919876543210"
        assert result["country"] == "IN"  # uppercased
        # email should remain unchanged
        assert result["email"] == creator.email


class TestLinkAgentToCreator:
    """Tests 26-27: link_agent_to_creator success and already claimed."""

    async def test_link_agent_to_creator(
        self, db: AsyncSession, make_agent, make_creator,
    ):
        """26. link_agent_to_creator sets creator_id on the agent row."""
        creator, _ = await make_creator()
        agent, _ = await make_agent("linkable-agent")

        result = await creator_service.link_agent_to_creator(db, creator.id, agent.id)
        assert result["creator_id"] == creator.id
        assert result["agent_id"] == agent.id
        assert result["agent_name"] == "linkable-agent"

        # Verify persistence
        row = await db.execute(
            select(RegisteredAgent).where(RegisteredAgent.id == agent.id)
        )
        assert row.scalar_one().creator_id == creator.id

    async def test_link_agent_already_claimed(
        self, db: AsyncSession, make_agent, make_creator,
    ):
        """27. Claiming an agent already owned by another creator raises ValueError."""
        creator_a, _ = await make_creator(email="owner-a@test.com")
        creator_b, _ = await make_creator(email="owner-b@test.com")
        agent, _ = await make_agent("contested-agent")

        await creator_service.link_agent_to_creator(db, creator_a.id, agent.id)
        with pytest.raises(ValueError, match="already claimed"):
            await creator_service.link_agent_to_creator(db, creator_b.id, agent.id)


class TestCreatorDashboard:
    """Test 28: get_creator_dashboard aggregated data."""

    async def test_get_creator_dashboard(
        self, db: AsyncSession, seed_platform, make_agent,
    ):
        """28. Dashboard includes agents_count and balances."""
        reg = await creator_service.register_creator(
            db, "dashboard@test.com", "pass1234", "Dashboard Creator",
        )
        creator_id = reg["creator"]["id"]

        agent, _ = await make_agent("dash-agent-1")
        await creator_service.link_agent_to_creator(db, creator_id, agent.id)

        dashboard = await creator_service.get_creator_dashboard(db, creator_id)

        assert dashboard["agents_count"] == 1
        assert dashboard["creator_balance"] == pytest.approx(settings.signup_bonus_usd)
        assert isinstance(dashboard["agents"], list)
        assert dashboard["agents"][0]["agent_name"] == "dash-agent-1"
        assert "total_agent_earnings" in dashboard
        assert "total_agent_spent" in dashboard
        assert "creator_total_earned" in dashboard


class TestCreatorWallet:
    """Tests 29-30: get_creator_wallet with and without account."""

    async def test_get_creator_wallet_with_account(
        self, db: AsyncSession, seed_platform,
    ):
        """29. Wallet returns balance and totals when account exists."""
        reg = await creator_service.register_creator(
            db, "wallet@test.com", "pass1234", "Wallet Creator",
        )
        creator_id = reg["creator"]["id"]

        wallet = await creator_service.get_creator_wallet(db, creator_id)

        assert wallet["balance"] == pytest.approx(settings.signup_bonus_usd)
        assert "total_earned" in wallet
        assert "total_spent" in wallet
        assert "total_deposited" in wallet
        assert "total_fees_paid" in wallet

    async def test_get_creator_wallet_no_account(self, db: AsyncSession, make_creator):
        """30. When creator has no TokenAccount, wallet returns zero defaults."""
        creator, _ = await make_creator()
        wallet = await creator_service.get_creator_wallet(db, creator.id)

        assert wallet["balance"] == 0
        assert wallet["total_earned"] == 0
        assert wallet["total_spent"] == 0
