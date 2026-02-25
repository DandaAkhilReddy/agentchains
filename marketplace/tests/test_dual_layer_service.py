"""Comprehensive tests for dual_layer_service — developer builder and end-user
buyer workflows: registration, login, market listings, builder projects,
order creation, metrics, and featured collections.

Uses in-memory SQLite via conftest fixtures.  asyncio_mode = "auto".
"""

from __future__ import annotations

import json
import uuid
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from marketplace.models.agent import RegisteredAgent
from marketplace.models.creator import Creator
from marketplace.models.dual_layer import (
    BuilderProject,
    ConsumerOrder,
    DeveloperProfile,
    EndUser,
    PlatformFee,
)
from marketplace.models.listing import DataListing
from marketplace.services import dual_layer_service as svc


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _create_end_user(db: AsyncSession, email: str = "buyer@test.com",
                           password: str = "Str0ng!Pass") -> dict:
    return await svc.register_end_user(db, email=email, password=password)


async def _create_listing_for_agent(
    db: AsyncSession, make_listing, agent_id: str, **kwargs
):
    return await make_listing(agent_id, **kwargs)


# ---------------------------------------------------------------------------
# Pure utility functions
# ---------------------------------------------------------------------------

class TestToFloat:
    def test_normal_float(self):
        assert svc._to_float(3.14) == 3.14

    def test_string_float(self):
        assert svc._to_float("1.5") == 1.5

    def test_none_returns_default(self):
        assert svc._to_float(None) == 0.0

    def test_bad_string_returns_default(self):
        assert svc._to_float("not-a-number", 99.0) == 99.0

    def test_integer(self):
        assert svc._to_float(42) == 42.0

    def test_decimal(self):
        assert svc._to_float(Decimal("1.23")) == 1.23


class TestSafeListingCategory:
    def test_valid_category(self):
        assert svc._safe_listing_category("web_search") == "web_search"

    def test_invalid_category_defaults(self):
        assert svc._safe_listing_category("unknown") == "api_response"

    def test_none_defaults(self):
        assert svc._safe_listing_category(None) == "api_response"

    def test_empty_string_defaults(self):
        assert svc._safe_listing_category("") == "api_response"

    def test_all_valid_categories(self):
        for cat in svc._LISTING_CATEGORIES:
            assert svc._safe_listing_category(cat) == cat


class TestListBuilderTemplates:
    def test_returns_list_of_dicts(self):
        templates = svc.list_builder_templates()
        assert isinstance(templates, list)
        assert len(templates) == len(svc._BUILDER_TEMPLATES)

    def test_each_template_has_required_keys(self):
        for t in svc.list_builder_templates():
            assert "key" in t
            assert "name" in t
            assert "description" in t
            assert "default_category" in t
            assert "suggested_price_usd" in t

    def test_returns_copies_not_originals(self):
        templates = svc.list_builder_templates()
        templates[0]["key"] = "mutated"
        assert svc._BUILDER_TEMPLATES[0]["key"] != "mutated"


# ---------------------------------------------------------------------------
# End-user registration and login
# ---------------------------------------------------------------------------

class TestRegisterEndUser:
    async def test_register_success(self, db: AsyncSession, seed_platform):
        result = await svc.register_end_user(db, email="New@Test.com", password="Pass123!")
        assert result["user"]["email"] == "new@test.com"
        assert result["user"]["status"] == "active"
        assert "token" in result
        assert result["user"]["managed_agent_id"] is not None

    async def test_register_duplicate_email_fails(self, db: AsyncSession, seed_platform):
        await svc.register_end_user(db, email="dup@test.com", password="Pass123!")
        with pytest.raises(ValueError, match="Email already registered"):
            await svc.register_end_user(db, email="DUP@TEST.COM", password="Other456!")

    async def test_register_normalizes_email(self, db: AsyncSession, seed_platform):
        result = await svc.register_end_user(db, email="  User@EXAMPLE.com  ", password="Pass!")
        assert result["user"]["email"] == "user@example.com"

    async def test_register_creates_managed_agent(self, db: AsyncSession, seed_platform):
        result = await svc.register_end_user(db, email="agent@test.com", password="Pass!")
        agent_id = result["user"]["managed_agent_id"]
        agent_result = await db.execute(
            select(RegisteredAgent).where(RegisteredAgent.id == agent_id)
        )
        agent = agent_result.scalar_one()
        assert agent.agent_type == "buyer"


class TestLoginEndUser:
    async def test_login_success(self, db: AsyncSession, seed_platform):
        await svc.register_end_user(db, email="login@test.com", password="SecurePass1!")
        result = await svc.login_end_user(db, email="login@test.com", password="SecurePass1!")
        assert "token" in result
        assert result["user"]["email"] == "login@test.com"
        assert result["user"]["last_login_at"] is not None

    async def test_login_wrong_password(self, db: AsyncSession, seed_platform):
        await svc.register_end_user(db, email="login2@test.com", password="RightPass1!")
        with pytest.raises(ValueError, match="Invalid email or password"):
            await svc.login_end_user(db, email="login2@test.com", password="WrongPass!")

    async def test_login_nonexistent_email(self, db: AsyncSession):
        with pytest.raises(ValueError, match="Invalid email or password"):
            await svc.login_end_user(db, email="nobody@test.com", password="x")

    async def test_login_inactive_user(self, db: AsyncSession, seed_platform):
        await svc.register_end_user(db, email="inactive@test.com", password="Pass!")
        user_result = await db.execute(
            select(EndUser).where(EndUser.email == "inactive@test.com")
        )
        user = user_result.scalar_one()
        user.status = "suspended"
        await db.commit()
        with pytest.raises(ValueError, match="not active"):
            await svc.login_end_user(db, email="inactive@test.com", password="Pass!")


# ---------------------------------------------------------------------------
# get_end_user_by_id / get_end_user_payload
# ---------------------------------------------------------------------------

class TestGetEndUser:
    async def test_get_by_id_success(self, db: AsyncSession, seed_platform):
        reg = await svc.register_end_user(db, email="get@test.com", password="Pass!")
        user = await svc.get_end_user_by_id(db, user_id=reg["user"]["id"])
        assert user.email == "get@test.com"

    async def test_get_by_id_not_found(self, db: AsyncSession):
        with pytest.raises(ValueError, match="not found"):
            await svc.get_end_user_by_id(db, user_id="nonexistent")

    async def test_get_payload(self, db: AsyncSession, seed_platform):
        reg = await svc.register_end_user(db, email="payload@test.com", password="Pass!")
        payload = await svc.get_end_user_payload(db, user_id=reg["user"]["id"])
        assert payload["email"] == "payload@test.com"
        assert "id" in payload
        assert "status" in payload


# ---------------------------------------------------------------------------
# Market listings (list + get)
# ---------------------------------------------------------------------------

class TestMarketListings:
    async def test_list_empty(self, db: AsyncSession):
        listings, total = await svc.list_market_listings(db)
        assert listings == []
        assert total == 0

    async def test_list_with_active_listings(
        self, db: AsyncSession, make_agent, make_listing, seed_platform,
    ):
        agent, _ = await make_agent()
        await make_listing(agent.id, price_usdc=0.5)
        await make_listing(agent.id, price_usdc=1.0)

        listings, total = await svc.list_market_listings(db)
        assert total == 2
        assert len(listings) == 2

    async def test_list_filters_by_category(
        self, db: AsyncSession, make_agent, make_listing, seed_platform,
    ):
        agent, _ = await make_agent()
        await make_listing(agent.id, category="web_search")
        await make_listing(agent.id, category="code_analysis")

        listings, total = await svc.list_market_listings(db, category="web_search")
        assert total == 1
        assert listings[0]["category"] == "web_search"

    async def test_list_search_by_query(
        self, db: AsyncSession, make_agent, make_listing, seed_platform,
    ):
        agent, _ = await make_agent()
        await make_listing(agent.id, title="Python Tutorial Data")
        await make_listing(agent.id, title="Rust Compiler Output")

        listings, total = await svc.list_market_listings(db, q="Python")
        assert total == 1
        assert "Python" in listings[0]["title"]

    async def test_list_pagination(
        self, db: AsyncSession, make_agent, make_listing, seed_platform,
    ):
        agent, _ = await make_agent()
        for i in range(5):
            await make_listing(agent.id, title=f"Listing {i}")

        page1, total = await svc.list_market_listings(db, page=1, page_size=2)
        assert total == 5
        assert len(page1) == 2

        page2, _ = await svc.list_market_listings(db, page=2, page_size=2)
        assert len(page2) == 2

    async def test_list_includes_seller_name(
        self, db: AsyncSession, make_agent, make_listing, seed_platform,
    ):
        agent, _ = await make_agent("seller-agent")
        await make_listing(agent.id)

        listings, _ = await svc.list_market_listings(db)
        assert listings[0]["seller_name"] == "seller-agent"

    async def test_get_market_listing_success(
        self, db: AsyncSession, make_agent, make_listing, seed_platform,
    ):
        agent, _ = await make_agent("get-seller")
        listing = await make_listing(agent.id, title="Specific Listing")

        result = await svc.get_market_listing(db, listing_id=listing.id)
        assert result["title"] == "Specific Listing"
        assert result["seller_name"] == "get-seller"

    async def test_market_listing_payload_structure(
        self, db: AsyncSession, make_agent, make_listing, seed_platform,
    ):
        agent, _ = await make_agent()
        listing = await make_listing(agent.id)

        result = await svc.get_market_listing(db, listing_id=listing.id)
        assert "id" in result
        assert "title" in result
        assert "price_usd" in result
        assert "trust_status" in result
        assert "requires_unverified_confirmation" in result


# ---------------------------------------------------------------------------
# Developer profile CRUD
# ---------------------------------------------------------------------------

class TestDeveloperProfile:
    async def test_get_or_create_new(self, db: AsyncSession, make_creator):
        creator, _ = await make_creator()
        profile = await svc.get_or_create_developer_profile(db, creator_id=creator.id)
        assert profile.creator_id == creator.id
        assert profile.bio == ""

    async def test_get_or_create_idempotent(self, db: AsyncSession, make_creator):
        creator, _ = await make_creator()
        p1 = await svc.get_or_create_developer_profile(db, creator_id=creator.id)
        p2 = await svc.get_or_create_developer_profile(db, creator_id=creator.id)
        assert p1.creator_id == p2.creator_id

    async def test_get_payload(self, db: AsyncSession, make_creator):
        creator, _ = await make_creator()
        payload = await svc.get_developer_profile_payload(db, creator_id=creator.id)
        assert payload["creator_id"] == creator.id
        assert payload["bio"] == ""
        assert payload["links"] == []
        assert payload["specialties"] == []
        assert payload["featured_flag"] is False

    async def test_update_profile(self, db: AsyncSession, make_creator):
        creator, _ = await make_creator()
        updated = await svc.update_developer_profile(
            db,
            creator_id=creator.id,
            bio="Full-stack AI engineer",
            links=["https://github.com/test"],
            specialties=["ML", "backend"],
            featured_flag=True,
        )
        assert updated["bio"] == "Full-stack AI engineer"
        assert updated["links"] == ["https://github.com/test"]
        assert updated["specialties"] == ["ML", "backend"]
        assert updated["featured_flag"] is True

    async def test_update_overwrites_previous(self, db: AsyncSession, make_creator):
        creator, _ = await make_creator()
        await svc.update_developer_profile(
            db, creator_id=creator.id,
            bio="v1", links=[], specialties=[], featured_flag=False,
        )
        updated = await svc.update_developer_profile(
            db, creator_id=creator.id,
            bio="v2", links=["new"], specialties=["new"], featured_flag=True,
        )
        assert updated["bio"] == "v2"


# ---------------------------------------------------------------------------
# Builder project CRUD
# ---------------------------------------------------------------------------

class TestBuilderProject:
    async def test_create_project_success(self, db: AsyncSession, make_creator):
        creator, _ = await make_creator()
        result = await svc.create_builder_project(
            db,
            creator_id=creator.id,
            template_key="firecrawl-web-research",
            title="My Research Project",
            config={"summary": "Test summary"},
        )
        assert result["title"] == "My Research Project"
        assert result["template_key"] == "firecrawl-web-research"
        assert result["status"] == "draft"
        assert result["published_listing_id"] is None

    async def test_create_project_invalid_template(self, db: AsyncSession, make_creator):
        creator, _ = await make_creator()
        with pytest.raises(ValueError, match="Unknown template_key"):
            await svc.create_builder_project(
                db,
                creator_id=creator.id,
                template_key="nonexistent-template",
                title="Bad Project",
                config={},
            )

    async def test_create_project_nonexistent_creator(self, db: AsyncSession):
        with pytest.raises(ValueError, match="Creator .* not found"):
            await svc.create_builder_project(
                db,
                creator_id="nonexistent-id",
                template_key="firecrawl-web-research",
                title="Orphan",
                config={},
            )

    async def test_list_projects_empty(self, db: AsyncSession, make_creator):
        creator, _ = await make_creator()
        projects = await svc.list_builder_projects(db, creator_id=creator.id)
        assert projects == []

    async def test_list_projects_returns_creator_projects(self, db: AsyncSession, make_creator):
        creator, _ = await make_creator()
        await svc.create_builder_project(
            db, creator_id=creator.id,
            template_key="firecrawl-web-research",
            title="P1", config={"summary": "s1"},
        )
        await svc.create_builder_project(
            db, creator_id=creator.id,
            template_key="code-quality-audit",
            title="P2", config={"summary": "s2"},
        )
        projects = await svc.list_builder_projects(db, creator_id=creator.id)
        assert len(projects) == 2

    async def test_list_projects_isolated_by_creator(self, db: AsyncSession, make_creator):
        c1, _ = await make_creator(email="c1@test.com")
        c2, _ = await make_creator(email="c2@test.com")
        await svc.create_builder_project(
            db, creator_id=c1.id,
            template_key="firecrawl-web-research",
            title="C1 Project", config={"summary": "s"},
        )
        await svc.create_builder_project(
            db, creator_id=c2.id,
            template_key="firecrawl-web-research",
            title="C2 Project", config={"summary": "s"},
        )
        projects = await svc.list_builder_projects(db, creator_id=c1.id)
        assert len(projects) == 1
        assert projects[0]["title"] == "C1 Project"


# ---------------------------------------------------------------------------
# _build_listing_request
# ---------------------------------------------------------------------------

class TestBuildListingRequest:
    def test_valid_config_with_summary(self):
        project = BuilderProject(
            id="proj-1",
            creator_id="c-1",
            template_key="firecrawl-web-research",
            title="Test Project",
            config_json=json.dumps({
                "summary": "A valid summary",
                "price_usd": 0.50,
                "category": "web_search",
            }),
        )
        req = svc._build_listing_request(project)
        assert req.price_usd == 0.50
        assert req.category == "web_search"
        assert req.title == "Test Project"

    def test_valid_config_with_sample_output(self):
        project = BuilderProject(
            id="proj-2",
            creator_id="c-1",
            template_key="code-quality-audit",
            title="Audit",
            config_json=json.dumps({"sample_output": "Lint results: all clean"}),
        )
        req = svc._build_listing_request(project)
        assert req.price_usdc > 0

    def test_empty_config_raises(self):
        project = BuilderProject(
            id="proj-3",
            creator_id="c-1",
            template_key="firecrawl-web-research",
            title="Empty",
            config_json="{}",
        )
        with pytest.raises(ValueError, match="summary.*sample_output"):
            svc._build_listing_request(project)

    def test_invalid_config_json_treated_as_empty(self):
        project = BuilderProject(
            id="proj-4",
            creator_id="c-1",
            template_key="firecrawl-web-research",
            title="Bad JSON",
            config_json="not-valid-json",
        )
        with pytest.raises(ValueError, match="summary.*sample_output"):
            svc._build_listing_request(project)

    def test_zero_price_uses_template_default(self):
        project = BuilderProject(
            id="proj-5",
            creator_id="c-1",
            template_key="doc-brief-pack",
            title="Free?",
            config_json=json.dumps({
                "summary": "Brief pack",
                "price_usd": 0,
            }),
        )
        req = svc._build_listing_request(project)
        assert req.price_usd == 0.18  # doc-brief-pack suggested price

    def test_invalid_category_defaults_to_api_response(self):
        project = BuilderProject(
            id="proj-6",
            creator_id="c-1",
            template_key="computation-snapshot",
            title="Compute",
            config_json=json.dumps({
                "summary": "Compute output",
                "category": "invalid_category",
            }),
        )
        req = svc._build_listing_request(project)
        assert req.category == "api_response"

    def test_custom_tags(self):
        project = BuilderProject(
            id="proj-7",
            creator_id="c-1",
            template_key="firecrawl-web-research",
            title="Tagged",
            config_json=json.dumps({
                "summary": "Tagged project",
                "tags": ["custom", "tags"],
            }),
        )
        req = svc._build_listing_request(project)
        assert req.tags == ["custom", "tags"]


# ---------------------------------------------------------------------------
# publish_builder_project
# ---------------------------------------------------------------------------

class TestPublishBuilderProject:
    async def test_publish_creates_listing(self, db: AsyncSession, make_creator, seed_platform):
        creator, _ = await make_creator()
        project = await svc.create_builder_project(
            db, creator_id=creator.id,
            template_key="firecrawl-web-research",
            title="Publish Me",
            config={"summary": "Research output summary"},
        )
        result = await svc.publish_builder_project(
            db, creator_id=creator.id, project_id=project["id"],
        )
        assert result["listing_id"] is not None
        assert result["project"]["status"] == "published"

    async def test_publish_idempotent(self, db: AsyncSession, make_creator, seed_platform):
        creator, _ = await make_creator()
        project = await svc.create_builder_project(
            db, creator_id=creator.id,
            template_key="firecrawl-web-research",
            title="Publish Once",
            config={"summary": "Research output"},
        )
        r1 = await svc.publish_builder_project(
            db, creator_id=creator.id, project_id=project["id"],
        )
        r2 = await svc.publish_builder_project(
            db, creator_id=creator.id, project_id=project["id"],
        )
        assert r1["listing_id"] == r2["listing_id"]

    async def test_publish_nonexistent_project_fails(self, db: AsyncSession, make_creator):
        creator, _ = await make_creator()
        with pytest.raises(ValueError, match="not found"):
            await svc.publish_builder_project(
                db, creator_id=creator.id, project_id="nonexistent",
            )

    async def test_publish_wrong_creator_fails(
        self, db: AsyncSession, make_creator, seed_platform,
    ):
        c1, _ = await make_creator(email="c1@pub.com")
        c2, _ = await make_creator(email="c2@pub.com")
        project = await svc.create_builder_project(
            db, creator_id=c1.id,
            template_key="firecrawl-web-research",
            title="C1 Project",
            config={"summary": "test"},
        )
        with pytest.raises(ValueError, match="not found"):
            await svc.publish_builder_project(
                db, creator_id=c2.id, project_id=project["id"],
            )


# ---------------------------------------------------------------------------
# Consumer orders
# ---------------------------------------------------------------------------

class TestConsumerOrders:
    async def test_list_orders_empty(self, db: AsyncSession, seed_platform):
        user = await svc.register_end_user(db, email="orders@test.com", password="Pass!")
        orders, total = await svc.list_market_orders_for_user(
            db, user_id=user["user"]["id"],
        )
        assert orders == []
        assert total == 0

    async def test_get_order_not_found(self, db: AsyncSession, seed_platform):
        user = await svc.register_end_user(db, email="noorder@test.com", password="Pass!")
        with pytest.raises(ValueError, match="not found"):
            await svc.get_market_order_for_user(
                db, user_id=user["user"]["id"], order_id="nonexistent",
            )

    async def test_order_payload_structure(self):
        order = ConsumerOrder(
            id="ord-1",
            end_user_id="u-1",
            listing_id="l-1",
            tx_id="tx-1",
            amount_usd=Decimal("1.00"),
            fee_usd=Decimal("0.10"),
            payout_usd=Decimal("0.90"),
            status="completed",
            trust_status="verified_secure_data",
            warning_acknowledged=False,
        )
        payload = svc._order_payload(order)
        assert payload["id"] == "ord-1"
        assert payload["amount_usd"] == 1.0
        assert payload["fee_usd"] == 0.1
        assert payload["payout_usd"] == 0.9
        assert payload["trust_status"] == "verified_secure_data"
        assert payload["warning_acknowledged"] is False
        assert payload["content"] is None

    async def test_order_payload_with_content(self):
        order = ConsumerOrder(
            id="ord-2", end_user_id="u", listing_id="l", tx_id="t",
            amount_usd=Decimal("0"), fee_usd=Decimal("0"),
            payout_usd=Decimal("0"), status="completed",
            trust_status="pending_verification", warning_acknowledged=True,
        )
        payload = svc._order_payload(order, include_content="the content")
        assert payload["content"] == "the content"


# ---------------------------------------------------------------------------
# Featured collections
# ---------------------------------------------------------------------------

class TestFeaturedCollections:
    async def test_returns_two_collections(self, db: AsyncSession):
        collections = await svc.get_featured_collections(db)
        assert len(collections) == 2
        assert collections[0]["key"] == "verified_hot"
        assert collections[1]["key"] == "new_builder_releases"

    async def test_collections_include_listings(
        self, db: AsyncSession, make_agent, make_listing, seed_platform,
    ):
        agent, _ = await make_agent()
        await make_listing(agent.id, title="Featured Item")

        collections = await svc.get_featured_collections(db)
        # new_builder_releases should have the listing
        new_releases = collections[1]
        assert len(new_releases["listings"]) >= 1


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------

class TestDualLayerMetrics:
    async def test_open_metrics_empty(self, db: AsyncSession):
        metrics = await svc.get_dual_layer_open_metrics(db)
        assert metrics["end_users_count"] == 0
        assert metrics["consumer_orders_count"] == 0
        assert metrics["developer_profiles_count"] == 0
        assert metrics["platform_fee_volume_usd"] == 0.0

    async def test_open_metrics_with_data(self, db: AsyncSession, seed_platform):
        await svc.register_end_user(db, email="m1@test.com", password="Pass!")
        await svc.register_end_user(db, email="m2@test.com", password="Pass!")
        metrics = await svc.get_dual_layer_open_metrics(db)
        assert metrics["end_users_count"] == 2

    async def test_creator_metrics_no_agents(self, db: AsyncSession, make_creator):
        creator, _ = await make_creator()
        metrics = await svc.get_creator_dual_layer_metrics(db, creator_id=creator.id)
        assert metrics["creator_gross_revenue_usd"] == 0.0
        assert metrics["creator_platform_fees_usd"] == 0.0
        assert metrics["creator_net_revenue_usd"] == 0.0

    async def test_creator_metrics_with_agents_no_listings(
        self, db: AsyncSession, make_creator, make_agent, seed_platform,
    ):
        creator, _ = await make_creator()
        agent, _ = await make_agent()
        # Assign agent to creator
        agent_result = await db.execute(
            select(RegisteredAgent).where(RegisteredAgent.id == agent.id)
        )
        a = agent_result.scalar_one()
        a.creator_id = creator.id
        await db.commit()

        metrics = await svc.get_creator_dual_layer_metrics(db, creator_id=creator.id)
        assert metrics["creator_gross_revenue_usd"] == 0.0


# ---------------------------------------------------------------------------
# _market_listing_payload
# ---------------------------------------------------------------------------

class TestMarketListingPayload:
    def test_verified_listing(self):
        listing = MagicMock(spec=DataListing)
        listing.id = "l-1"
        listing.title = "Test"
        listing.description = "Desc"
        listing.category = "web_search"
        listing.seller_id = "s-1"
        listing.price_usdc = Decimal("0.50")
        listing.currency = "USD"
        listing.trust_status = "verified_secure_data"
        listing.trust_score = 85
        listing.freshness_at = None
        listing.created_at = None

        payload = svc._market_listing_payload(listing, seller_name="TestSeller")
        assert payload["requires_unverified_confirmation"] is False
        assert payload["trust_score"] == 85
        assert payload["seller_name"] == "TestSeller"

    def test_unverified_listing_requires_confirmation(self):
        listing = MagicMock(spec=DataListing)
        listing.id = "l-2"
        listing.title = "Unverified"
        listing.description = "D"
        listing.category = "api_response"
        listing.seller_id = "s-2"
        listing.price_usdc = Decimal("0.25")
        listing.currency = "USD"
        listing.trust_status = "pending_verification"
        listing.trust_score = None
        listing.freshness_at = None
        listing.created_at = None

        payload = svc._market_listing_payload(listing, seller_name="Seller")
        assert payload["requires_unverified_confirmation"] is True
        assert payload["trust_score"] == 0

    def test_null_trust_status_requires_confirmation(self):
        listing = MagicMock(spec=DataListing)
        listing.id = "l-3"
        listing.title = "Null Trust"
        listing.description = "D"
        listing.category = "computation"
        listing.seller_id = "s-3"
        listing.price_usdc = Decimal("0.10")
        listing.currency = "USD"
        listing.trust_status = None
        listing.trust_score = None
        listing.freshness_at = None
        listing.created_at = None

        payload = svc._market_listing_payload(listing, seller_name="Seller")
        assert payload["requires_unverified_confirmation"] is True
        assert payload["trust_status"] == "pending_verification"


# ---------------------------------------------------------------------------
# _user_to_payload
# ---------------------------------------------------------------------------

class TestUserToPayload:
    def test_includes_all_fields(self):
        user = MagicMock(spec=EndUser)
        user.id = "u-1"
        user.email = "test@test.com"
        user.status = "active"
        user.managed_agent_id = "agent-1"
        user.created_at = None
        user.updated_at = None
        user.last_login_at = None

        payload = svc._user_to_payload(user)
        assert payload["id"] == "u-1"
        assert payload["email"] == "test@test.com"
        assert payload["status"] == "active"
        assert payload["managed_agent_id"] == "agent-1"


# ---------------------------------------------------------------------------
# _developer_profile_payload edge cases
# ---------------------------------------------------------------------------

class TestDeveloperProfilePayload:
    def test_handles_invalid_links_json(self):
        profile = MagicMock(spec=DeveloperProfile)
        profile.creator_id = "c-1"
        profile.bio = "Bio"
        profile.links_json = '"not-a-list"'
        profile.specialties_json = '"also-not-a-list"'
        profile.featured_flag = False
        profile.created_at = None
        profile.updated_at = None

        payload = svc._developer_profile_payload(profile)
        assert payload["links"] == []
        assert payload["specialties"] == []

    def test_handles_none_json(self):
        profile = MagicMock(spec=DeveloperProfile)
        profile.creator_id = "c-2"
        profile.bio = None
        profile.links_json = None
        profile.specialties_json = None
        profile.featured_flag = None
        profile.created_at = None
        profile.updated_at = None

        payload = svc._developer_profile_payload(profile)
        assert payload["bio"] == ""
        assert payload["links"] == []
        assert payload["specialties"] == []
        assert payload["featured_flag"] is False


# ---------------------------------------------------------------------------
# _get_or_create_creator_seller_agent
# ---------------------------------------------------------------------------

class TestGetOrCreateCreatorSellerAgent:
    async def test_creates_new_seller_agent(self, db: AsyncSession, make_creator, seed_platform):
        creator, _ = await make_creator()
        agent_id = await svc._get_or_create_creator_seller_agent(db, creator_id=creator.id)
        assert agent_id is not None

        agent_result = await db.execute(
            select(RegisteredAgent).where(RegisteredAgent.id == agent_id)
        )
        agent = agent_result.scalar_one()
        assert agent.creator_id == creator.id
        assert agent.agent_type == "both"

    async def test_returns_existing_seller_agent(
        self, db: AsyncSession, make_creator, make_agent, seed_platform,
    ):
        creator, _ = await make_creator()
        agent, _ = await make_agent("existing-seller")
        # Assign as seller for this creator
        agent_result = await db.execute(
            select(RegisteredAgent).where(RegisteredAgent.id == agent.id)
        )
        a = agent_result.scalar_one()
        a.creator_id = creator.id
        a.agent_type = "seller"
        await db.commit()

        result_id = await svc._get_or_create_creator_seller_agent(db, creator_id=creator.id)
        assert result_id == agent.id
