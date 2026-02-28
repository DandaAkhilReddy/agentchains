"""Comprehensive tests for dual_layer_service and event_subscription_service.

Covers all major functions in both services grouped into themed test classes:

dual_layer_service:
  1. EndUser registration and login
  2. Market listings (list and get)
  3. Builder templates and projects
  4. Builder project publishing
  5. Consumer market orders and fee accounting
  6. Developer profiles
  7. Open and creator metrics

event_subscription_service:
  8. Event envelope building and signature verification
  9. Subscription CRUD (register, list, delete)
  10. Webhook dispatch and delivery
  11. Payload sanitisation and target extraction
  12. Webhook redaction

Uses pytest with async tests (asyncio_mode = auto in pytest.ini/pyproject.toml).
Mocks all external I/O (express_buy, httpx) with unittest.mock.AsyncMock.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from marketplace.models.agent import RegisteredAgent
from marketplace.models.agent_trust import EventSubscription, WebhookDelivery
from marketplace.models.creator import Creator
from marketplace.models.dual_layer import (
    BuilderProject,
    ConsumerOrder,
    DeveloperProfile,
    EndUser,
    PlatformFee,
)
from marketplace.models.listing import DataListing
from marketplace.services import dual_layer_service, event_subscription_service
from marketplace.tests.conftest import _new_id

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

EXPRESS_BUY_PATCH = "marketplace.services.dual_layer_service.express_service.express_buy"
REGISTRY_PATCH = "marketplace.services.dual_layer_service.registry_service.register_agent"
TOKEN_ACCOUNT_PATCH = "marketplace.services.dual_layer_service.create_account"
PLATFORM_ACCOUNT_PATCH = "marketplace.services.dual_layer_service.ensure_platform_account"
LISTING_CREATE_PATCH = "marketplace.services.dual_layer_service.listing_service.create_listing"
LISTING_GET_PATCH = "marketplace.services.dual_layer_service.listing_service.get_listing"

SIGN_SECRET = "dev-event-signing-secret-change-in-production"


def _uid() -> str:
    return str(uuid.uuid4())


def _unique_email() -> str:
    return f"user-{uuid.uuid4().hex[:8]}@test.com"


def _make_registered_agent(
    *,
    agent_id: str | None = None,
    name: str | None = None,
    agent_type: str = "both",
    status: str = "active",
    creator_id: str | None = None,
) -> RegisteredAgent:
    """Build an in-memory RegisteredAgent (not yet persisted)."""
    agent = RegisteredAgent(
        id=agent_id or _uid(),
        name=name or f"test-agent-{uuid.uuid4().hex[:8]}",
        agent_type=agent_type,
        public_key="ssh-rsa AAAA_test",
        status=status,
    )
    if creator_id:
        agent.creator_id = creator_id
    return agent


def _make_listing_model(
    *,
    seller_id: str | None = None,
    price_usdc: float = 0.30,
    status: str = "active",
    trust_status: str = "verified_secure_data",
    category: str = "web_search",
    title: str = "My Listing",
) -> DataListing:
    listing = DataListing(
        id=_uid(),
        seller_id=seller_id or _uid(),
        title=title,
        category=category,
        content_hash="sha256:abc123",
        content_size=100,
        price_usdc=Decimal(str(price_usdc)),
        quality_score=Decimal("0.85"),
        status=status,
    )
    listing.trust_status = trust_status
    listing.trust_score = 90
    return listing


def _make_express_response(
    *,
    price_usdc: float = 0.30,
    transaction_id: str | None = None,
    content: str = "hello world data",
) -> MagicMock:
    """Return a FastAPI JSONResponse mock that dual_layer_service.create_market_order parses."""
    body_dict = {
        "transaction_id": transaction_id or _uid(),
        "price_usdc": price_usdc,
        "content": content,
    }
    body_bytes = json.dumps(body_dict).encode("utf-8")
    mock_resp = MagicMock()
    mock_resp.body = body_bytes
    return mock_resp


def _make_creator(db: AsyncSession) -> Creator:
    creator = Creator(
        id=_uid(),
        email=_unique_email(),
        password_hash="hashed",
        display_name="Dev Creator",
        status="active",
    )
    return creator


async def _insert_creator(db: AsyncSession) -> Creator:
    creator = _make_creator(db)
    db.add(creator)
    await db.commit()
    await db.refresh(creator)
    return creator


async def _register_user_mocked(
    db: AsyncSession,
    *,
    email: str | None = None,
    password: str = "SecurePass1!",
) -> dict:
    """Register an EndUser with all external dependencies mocked."""
    fake_agent = _make_registered_agent()
    with (
        patch(REGISTRY_PATCH, new_callable=AsyncMock, return_value=fake_agent),
        patch(PLATFORM_ACCOUNT_PATCH, new_callable=AsyncMock),
        patch(TOKEN_ACCOUNT_PATCH, new_callable=AsyncMock),
    ):
        return await dual_layer_service.register_end_user(
            db,
            email=email or _unique_email(),
            password=password,
        )


# ===========================================================================
# BLOCK 1: EndUser Registration and Login
# ===========================================================================


class TestEndUserRegistration:
    """Register new users, duplicate prevention, login happy/error paths."""

    async def test_register_returns_user_and_token(self, db: AsyncSession):
        """Successful registration returns a user dict and a JWT token."""
        result = await _register_user_mocked(db, email="reg1@test.com")

        assert "user" in result
        assert "token" in result
        assert result["user"]["email"] == "reg1@test.com"
        assert result["user"]["status"] == "active"
        assert len(result["token"]) > 30

    async def test_register_normalizes_email(self, db: AsyncSession):
        """Email is lowercased and whitespace-stripped before storage."""
        result = await _register_user_mocked(db, email="  Alice@EXAMPLE.COM  ")
        assert result["user"]["email"] == "alice@example.com"

    async def test_register_duplicate_email_raises(self, db: AsyncSession):
        """Registering the same email twice raises ValueError."""
        await _register_user_mocked(db, email="dup@test.com")

        with pytest.raises(ValueError, match="already registered"):
            await _register_user_mocked(db, email="dup@test.com")

    async def test_register_creates_end_user_in_db(self, db: AsyncSession):
        """EndUser row is persisted after registration."""
        result = await _register_user_mocked(db, email="persist@test.com")
        user_id = result["user"]["id"]

        row = await db.execute(select(EndUser).where(EndUser.id == user_id))
        user = row.scalar_one_or_none()
        assert user is not None
        assert user.email == "persist@test.com"

    async def test_login_valid_credentials_returns_token(self, db: AsyncSession):
        """Login with correct credentials returns user payload and fresh token."""
        await _register_user_mocked(db, email="login1@test.com", password="Pass1234!")

        result = await dual_layer_service.login_end_user(
            db, email="login1@test.com", password="Pass1234!"
        )

        assert result["user"]["email"] == "login1@test.com"
        assert len(result["token"]) > 30

    async def test_login_wrong_password_raises(self, db: AsyncSession):
        """Incorrect password raises ValueError."""
        await _register_user_mocked(db, email="wrongpw@test.com", password="Correct1!")

        with pytest.raises(ValueError, match="Invalid email or password"):
            await dual_layer_service.login_end_user(
                db, email="wrongpw@test.com", password="wrong"
            )

    async def test_login_nonexistent_email_raises(self, db: AsyncSession):
        """Login attempt for a nonexistent email raises ValueError."""
        with pytest.raises(ValueError, match="Invalid email or password"):
            await dual_layer_service.login_end_user(
                db, email="ghost@test.com", password="anything"
            )

    async def test_login_inactive_user_raises(self, db: AsyncSession):
        """Login for an inactive user raises ValueError."""
        result = await _register_user_mocked(db, email="inactive@test.com", password="TestPw1!@#")
        user_id = result["user"]["id"]

        row = await db.execute(select(EndUser).where(EndUser.id == user_id))
        user = row.scalar_one()
        user.status = "disabled"
        await db.commit()

        with pytest.raises(ValueError, match="not active"):
            await dual_layer_service.login_end_user(
                db, email="inactive@test.com", password="TestPw1!@#"
            )

    async def test_login_updates_last_login_at(self, db: AsyncSession):
        """Successful login updates last_login_at timestamp."""
        await _register_user_mocked(db, email="lastlogin@test.com", password="TestPw2!@#")

        result = await dual_layer_service.login_end_user(
            db, email="lastlogin@test.com", password="TestPw2!@#"
        )

        row = await db.execute(
            select(EndUser).where(EndUser.email == "lastlogin@test.com")
        )
        user = row.scalar_one()
        assert user.last_login_at is not None

    async def test_get_end_user_by_id_returns_correct_user(self, db: AsyncSession):
        """get_end_user_by_id fetches the EndUser by primary key."""
        result = await _register_user_mocked(db, email="fetch@test.com")
        user_id = result["user"]["id"]

        user = await dual_layer_service.get_end_user_by_id(db, user_id=user_id)
        assert user.id == user_id

    async def test_get_end_user_by_id_missing_raises(self, db: AsyncSession):
        """get_end_user_by_id for a nonexistent ID raises ValueError."""
        with pytest.raises(ValueError, match="not found"):
            await dual_layer_service.get_end_user_by_id(db, user_id="nonexistent-id")

    async def test_get_end_user_payload_returns_dict(self, db: AsyncSession):
        """get_end_user_payload serializes the user into a plain dict."""
        result = await _register_user_mocked(db, email="payload@test.com")
        user_id = result["user"]["id"]

        payload = await dual_layer_service.get_end_user_payload(db, user_id=user_id)
        assert payload["id"] == user_id
        assert payload["email"] == "payload@test.com"
        assert "password_hash" not in payload


# ===========================================================================
# BLOCK 2: Market Listings
# ===========================================================================


class TestMarketListings:
    """list_market_listings, get_market_listing, and featured collections."""

    async def test_list_market_listings_returns_tuple(self, db: AsyncSession):
        """list_market_listings returns (list_of_dicts, total_count) tuple."""
        payloads, total = await dual_layer_service.list_market_listings(db)
        assert isinstance(payloads, list)
        assert isinstance(total, int)

    async def test_list_market_listings_active_only(self, db: AsyncSession):
        """Only active listings appear in the marketplace listing results."""
        agent = _make_registered_agent()
        db.add(agent)
        await db.commit()

        from marketplace.services.storage_service import get_storage

        storage = get_storage()
        content_hash = storage.put(b"active content")

        active = DataListing(
            id=_uid(),
            seller_id=agent.id,
            title="Active Listing",
            category="web_search",
            content_hash=content_hash,
            content_size=14,
            price_usdc=Decimal("0.25"),
            quality_score=Decimal("0.8"),
            status="active",
        )
        inactive = DataListing(
            id=_uid(),
            seller_id=agent.id,
            title="Inactive Listing",
            category="web_search",
            content_hash=content_hash,
            content_size=14,
            price_usdc=Decimal("0.25"),
            quality_score=Decimal("0.8"),
            status="inactive",
        )
        db.add(active)
        db.add(inactive)
        await db.commit()

        payloads, total = await dual_layer_service.list_market_listings(db)
        titles = [p["title"] for p in payloads]
        assert "Active Listing" in titles
        assert "Inactive Listing" not in titles

    async def test_list_market_listings_filters_by_category(self, db: AsyncSession):
        """Category filter narrows results to the specified category."""
        agent = _make_registered_agent()
        db.add(agent)
        await db.commit()

        from marketplace.services.storage_service import get_storage

        storage = get_storage()
        ch = storage.put(b"cat filter data")

        for cat in ("web_search", "code_analysis"):
            listing = DataListing(
                id=_uid(),
                seller_id=agent.id,
                title=f"Listing-{cat}",
                category=cat,
                content_hash=ch,
                content_size=14,
                price_usdc=Decimal("0.20"),
                quality_score=Decimal("0.7"),
                status="active",
            )
            db.add(listing)
        await db.commit()

        payloads, _ = await dual_layer_service.list_market_listings(
            db, category="web_search"
        )
        assert all(p["category"] == "web_search" for p in payloads)

    async def test_list_market_listings_text_search(self, db: AsyncSession):
        """q parameter performs ilike search on title/description/tags."""
        agent = _make_registered_agent()
        db.add(agent)
        await db.commit()

        from marketplace.services.storage_service import get_storage

        storage = get_storage()
        ch = storage.put(b"search data")

        listing = DataListing(
            id=_uid(),
            seller_id=agent.id,
            title="Python Tutorial Dataset",
            category="web_search",
            content_hash=ch,
            content_size=11,
            price_usdc=Decimal("0.10"),
            quality_score=Decimal("0.7"),
            status="active",
        )
        db.add(listing)
        await db.commit()

        payloads, total = await dual_layer_service.list_market_listings(db, q="Python")
        assert total >= 1
        assert any("Python" in p["title"] for p in payloads)

    async def test_get_market_listing_delegates_to_listing_service(
        self, db: AsyncSession
    ):
        """get_market_listing calls listing_service.get_listing and returns a dict."""
        agent = _make_registered_agent()
        listing = _make_listing_model(seller_id=agent.id)

        with (
            patch(LISTING_GET_PATCH, new_callable=AsyncMock, return_value=listing),
            patch(
                "marketplace.services.dual_layer_service.listing_service.get_listing",
                new_callable=AsyncMock,
                return_value=listing,
            ),
        ):
            # Inject the agent so seller name look-up works
            db.add(agent)
            await db.commit()

            result = await dual_layer_service.get_market_listing(
                db, listing_id=listing.id
            )

        assert result["id"] == listing.id
        assert "seller_name" in result

    async def test_get_featured_collections_returns_two_collections(
        self, db: AsyncSession
    ):
        """get_featured_collections always returns exactly 2 collection dicts."""
        collections = await dual_layer_service.get_featured_collections(db)
        assert len(collections) == 2
        keys = {c["key"] for c in collections}
        assert "verified_hot" in keys
        assert "new_builder_releases" in keys


# ===========================================================================
# BLOCK 3: Builder Templates and Projects
# ===========================================================================


class TestBuilderTemplates:
    """list_builder_templates, create_builder_project, list_builder_projects."""

    async def test_list_builder_templates_returns_five_entries(self, db: AsyncSession):
        """list_builder_templates returns the 5 built-in templates."""
        templates = dual_layer_service.list_builder_templates()
        assert len(templates) == 5
        keys = {t["key"] for t in templates}
        assert "firecrawl-web-research" in keys

    async def test_create_builder_project_draft_status(self, db: AsyncSession):
        """A newly created builder project has status='draft'."""
        creator = await _insert_creator(db)
        result = await dual_layer_service.create_builder_project(
            db,
            creator_id=creator.id,
            template_key="firecrawl-web-research",
            title="My First Project",
            config={
                "summary": "Web research dataset on AI trends",
                "price_usd": 0.35,
            },
        )
        assert result["status"] == "draft"
        assert result["creator_id"] == creator.id
        assert result["template_key"] == "firecrawl-web-research"

    async def test_create_builder_project_unknown_template_raises(
        self, db: AsyncSession
    ):
        """Using an invalid template_key raises ValueError."""
        creator = await _insert_creator(db)
        with pytest.raises(ValueError, match="Unknown template_key"):
            await dual_layer_service.create_builder_project(
                db,
                creator_id=creator.id,
                template_key="invalid-key-xyz",
                title="Bad Project",
                config={"summary": "Anything"},
            )

    async def test_create_builder_project_missing_creator_raises(
        self, db: AsyncSession
    ):
        """Creating a project for a nonexistent creator raises ValueError."""
        with pytest.raises(ValueError, match="Creator .* not found"):
            await dual_layer_service.create_builder_project(
                db,
                creator_id="nonexistent-creator-id",
                template_key="api-monitoring-report",
                title="Ghost Project",
                config={"summary": "Anything"},
            )

    async def test_list_builder_projects_returns_owned_projects(
        self, db: AsyncSession
    ):
        """list_builder_projects returns only projects belonging to the creator."""
        creator = await _insert_creator(db)
        other = await _insert_creator(db)

        for i in range(2):
            project = BuilderProject(
                id=_uid(),
                creator_id=creator.id,
                template_key="doc-brief-pack",
                title=f"Doc Project {i}",
                config_json=json.dumps({"summary": f"Summary {i}"}),
                status="draft",
            )
            db.add(project)

        other_project = BuilderProject(
            id=_uid(),
            creator_id=other.id,
            template_key="doc-brief-pack",
            title="Other Creator Project",
            config_json=json.dumps({"summary": "Other summary"}),
            status="draft",
        )
        db.add(other_project)
        await db.commit()

        results = await dual_layer_service.list_builder_projects(
            db, creator_id=creator.id
        )
        assert len(results) == 2
        assert all(r["creator_id"] == creator.id for r in results)

    async def test_list_builder_projects_empty_for_new_creator(
        self, db: AsyncSession
    ):
        """A creator with no projects gets an empty list."""
        creator = await _insert_creator(db)
        results = await dual_layer_service.list_builder_projects(
            db, creator_id=creator.id
        )
        assert results == []


# ===========================================================================
# BLOCK 4: Builder Project Publishing
# ===========================================================================


class TestBuilderProjectPublishing:
    """publish_builder_project: success, idempotency, and config validation."""

    async def _insert_project(
        self, db: AsyncSession, creator_id: str, *, config: dict | None = None
    ) -> BuilderProject:
        cfg = config or {
            "summary": "Useful web research dataset about AI",
            "price_usd": 0.35,
        }
        project = BuilderProject(
            id=_uid(),
            creator_id=creator_id,
            template_key="firecrawl-web-research",
            title="Publish Me",
            config_json=json.dumps(cfg),
            status="draft",
        )
        db.add(project)
        await db.commit()
        await db.refresh(project)
        return project

    async def test_publish_project_sets_status_published(self, db: AsyncSession):
        """Publishing a draft project changes its status to 'published'."""
        creator = await _insert_creator(db)
        project = await self._insert_project(db, creator.id)

        fake_agent = _make_registered_agent(creator_id=creator.id)
        fake_listing = _make_listing_model(seller_id=fake_agent.id)

        with (
            patch(REGISTRY_PATCH, new_callable=AsyncMock, return_value=fake_agent),
            patch(PLATFORM_ACCOUNT_PATCH, new_callable=AsyncMock),
            patch(TOKEN_ACCOUNT_PATCH, new_callable=AsyncMock),
            patch(LISTING_CREATE_PATCH, new_callable=AsyncMock, return_value=fake_listing),
        ):
            result = await dual_layer_service.publish_builder_project(
                db, creator_id=creator.id, project_id=project.id
            )

        assert result["project"]["status"] == "published"
        assert result["listing_id"] == fake_listing.id

    async def test_publish_already_published_project_is_idempotent(
        self, db: AsyncSession
    ):
        """Publishing an already-published project returns existing listing_id."""
        creator = await _insert_creator(db)
        existing_listing_id = _uid()
        project = BuilderProject(
            id=_uid(),
            creator_id=creator.id,
            template_key="firecrawl-web-research",
            title="Already Published",
            config_json=json.dumps({"summary": "Summary"}),
            status="published",
            published_listing_id=existing_listing_id,
        )
        db.add(project)
        await db.commit()

        result = await dual_layer_service.publish_builder_project(
            db, creator_id=creator.id, project_id=project.id
        )
        assert result["listing_id"] == existing_listing_id

    async def test_publish_nonexistent_project_raises(self, db: AsyncSession):
        """Publishing a nonexistent project_id raises ValueError."""
        creator = await _insert_creator(db)
        with pytest.raises(ValueError, match="not found"):
            await dual_layer_service.publish_builder_project(
                db, creator_id=creator.id, project_id="no-such-project"
            )

    async def test_publish_project_config_missing_summary_raises(
        self, db: AsyncSession
    ):
        """Config without summary or sample_output raises ValueError."""
        creator = await _insert_creator(db)
        project = await self._insert_project(
            db, creator.id, config={"price_usd": 0.35}
        )

        fake_agent = _make_registered_agent(creator_id=creator.id)
        fake_listing = _make_listing_model(seller_id=fake_agent.id)

        with (
            patch(REGISTRY_PATCH, new_callable=AsyncMock, return_value=fake_agent),
            patch(PLATFORM_ACCOUNT_PATCH, new_callable=AsyncMock),
            patch(TOKEN_ACCOUNT_PATCH, new_callable=AsyncMock),
            patch(LISTING_CREATE_PATCH, new_callable=AsyncMock, return_value=fake_listing),
        ):
            with pytest.raises(ValueError, match="summary"):
                await dual_layer_service.publish_builder_project(
                    db, creator_id=creator.id, project_id=project.id
                )


# ===========================================================================
# BLOCK 5: Consumer Market Orders and Fee Accounting
# ===========================================================================


class TestConsumerMarketOrders:
    """create_market_order: fee math, trust guard, order payload, listing."""

    async def _make_active_user(self, db: AsyncSession) -> tuple[str, str]:
        """Return (user_id, managed_agent_id) with user persisted."""
        managed_agent = _make_registered_agent()
        db.add(managed_agent)
        await db.commit()

        user = EndUser(
            id=_uid(),
            email=_unique_email(),
            password_hash="hashed",
            managed_agent_id=managed_agent.id,
            status="active",
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)
        return user.id, managed_agent.id

    async def test_create_market_order_fee_math(self, db: AsyncSession):
        """10% platform fee and correct payout computed from express price."""
        user_id, managed_id = await self._make_active_user(db)
        listing = _make_listing_model(price_usdc=0.50)
        express_resp = _make_express_response(price_usdc=0.50)

        with (
            patch(LISTING_GET_PATCH, new_callable=AsyncMock, return_value=listing),
            patch(
                EXPRESS_BUY_PATCH,
                new_callable=AsyncMock,
                return_value=express_resp,
            ),
        ):
            result = await dual_layer_service.create_market_order(
                db,
                user_id=user_id,
                listing_id=listing.id,
                allow_unverified=True,
            )

        gross = Decimal("0.50")
        fee = (gross * Decimal("0.10")).quantize(Decimal("0.000001"))
        payout = (gross - fee).quantize(Decimal("0.000001"))

        assert float(result["amount_usd"]) == pytest.approx(
            float(gross), abs=1e-5
        )
        assert float(result["fee_usd"]) == pytest.approx(
            float(fee), abs=1e-5
        )
        assert float(result["payout_usd"]) == pytest.approx(
            float(payout), abs=1e-5
        )

    async def test_create_market_order_verified_listing_no_flag_needed(
        self, db: AsyncSession
    ):
        """A verified listing can be purchased without allow_unverified=True."""
        user_id, _ = await self._make_active_user(db)
        listing = _make_listing_model(trust_status="verified_secure_data")
        express_resp = _make_express_response(price_usdc=0.30)

        with (
            patch(LISTING_GET_PATCH, new_callable=AsyncMock, return_value=listing),
            patch(EXPRESS_BUY_PATCH, new_callable=AsyncMock, return_value=express_resp),
        ):
            result = await dual_layer_service.create_market_order(
                db,
                user_id=user_id,
                listing_id=listing.id,
                allow_unverified=False,
            )

        assert result["status"] == "completed"

    async def test_create_market_order_unverified_without_flag_raises(
        self, db: AsyncSession
    ):
        """Buying an unverified listing without allow_unverified raises ValueError."""
        user_id, _ = await self._make_active_user(db)
        listing = _make_listing_model(trust_status="pending_verification")

        with patch(LISTING_GET_PATCH, new_callable=AsyncMock, return_value=listing):
            with pytest.raises(ValueError, match="not verified"):
                await dual_layer_service.create_market_order(
                    db,
                    user_id=user_id,
                    listing_id=listing.id,
                    allow_unverified=False,
                )

    async def test_create_market_order_persists_consumer_order(
        self, db: AsyncSession
    ):
        """ConsumerOrder row is written to the database after purchase."""
        user_id, _ = await self._make_active_user(db)
        listing = _make_listing_model(trust_status="verified_secure_data")
        express_resp = _make_express_response(price_usdc=0.20)

        with (
            patch(LISTING_GET_PATCH, new_callable=AsyncMock, return_value=listing),
            patch(EXPRESS_BUY_PATCH, new_callable=AsyncMock, return_value=express_resp),
        ):
            result = await dual_layer_service.create_market_order(
                db,
                user_id=user_id,
                listing_id=listing.id,
                allow_unverified=True,
            )

        row = await db.execute(
            select(ConsumerOrder).where(ConsumerOrder.id == result["id"])
        )
        order = row.scalar_one_or_none()
        assert order is not None
        assert order.end_user_id == user_id

    async def test_create_market_order_persists_platform_fee(self, db: AsyncSession):
        """A PlatformFee row is created alongside the ConsumerOrder."""
        user_id, _ = await self._make_active_user(db)
        listing = _make_listing_model(trust_status="verified_secure_data")
        express_resp = _make_express_response(price_usdc=0.40)

        with (
            patch(LISTING_GET_PATCH, new_callable=AsyncMock, return_value=listing),
            patch(EXPRESS_BUY_PATCH, new_callable=AsyncMock, return_value=express_resp),
        ):
            result = await dual_layer_service.create_market_order(
                db,
                user_id=user_id,
                listing_id=listing.id,
                allow_unverified=True,
            )

        fee_row = await db.execute(
            select(PlatformFee).where(PlatformFee.order_id == result["id"])
        )
        fee = fee_row.scalar_one_or_none()
        assert fee is not None
        assert fee.policy_version == "dual-layer-fee-v1"

    async def test_create_market_order_includes_content_in_payload(
        self, db: AsyncSession
    ):
        """The order payload includes the content returned by express_buy."""
        user_id, _ = await self._make_active_user(db)
        listing = _make_listing_model(trust_status="verified_secure_data")
        express_resp = _make_express_response(price_usdc=0.25, content="secret output")

        with (
            patch(LISTING_GET_PATCH, new_callable=AsyncMock, return_value=listing),
            patch(EXPRESS_BUY_PATCH, new_callable=AsyncMock, return_value=express_resp),
        ):
            result = await dual_layer_service.create_market_order(
                db,
                user_id=user_id,
                listing_id=listing.id,
                allow_unverified=True,
            )

        assert result["content"] == "secret output"

    async def test_create_market_order_nonexistent_user_raises(
        self, db: AsyncSession
    ):
        """Buying with a nonexistent user_id raises ValueError."""
        listing = _make_listing_model(trust_status="verified_secure_data")
        with patch(LISTING_GET_PATCH, new_callable=AsyncMock, return_value=listing):
            with pytest.raises(ValueError, match="not found"):
                await dual_layer_service.create_market_order(
                    db,
                    user_id="nonexistent-user",
                    listing_id=listing.id,
                )

    async def test_list_market_orders_for_user_pagination(self, db: AsyncSession):
        """list_market_orders_for_user returns paginated orders and total count."""
        user_id, _ = await self._make_active_user(db)
        # No orders yet
        orders, total = await dual_layer_service.list_market_orders_for_user(
            db, user_id=user_id
        )
        assert isinstance(orders, list)
        assert total == 0

    async def test_get_market_order_for_user_not_found_raises(self, db: AsyncSession):
        """Fetching a nonexistent order_id raises ValueError."""
        with pytest.raises(ValueError, match="not found"):
            await dual_layer_service.get_market_order_for_user(
                db, user_id=_uid(), order_id="nonexistent-order"
            )


# ===========================================================================
# BLOCK 6: Developer Profiles
# ===========================================================================


class TestDeveloperProfiles:
    """get_developer_profile_payload, update_developer_profile, get_or_create."""

    async def test_get_profile_creates_on_first_access(self, db: AsyncSession):
        """Getting a nonexistent profile auto-creates it with empty defaults."""
        creator = await _insert_creator(db)
        payload = await dual_layer_service.get_developer_profile_payload(
            db, creator_id=creator.id
        )
        assert payload["creator_id"] == creator.id
        assert payload["bio"] == ""
        assert payload["links"] == []
        assert payload["specialties"] == []
        assert payload["featured_flag"] is False

    async def test_update_developer_profile_persists_changes(self, db: AsyncSession):
        """update_developer_profile writes bio, links, specialties, featured_flag."""
        creator = await _insert_creator(db)
        result = await dual_layer_service.update_developer_profile(
            db,
            creator_id=creator.id,
            bio="I build AI data tools.",
            links=["https://github.com/dev"],
            specialties=["web_search", "code_analysis"],
            featured_flag=True,
        )
        assert result["bio"] == "I build AI data tools."
        assert "https://github.com/dev" in result["links"]
        assert "web_search" in result["specialties"]
        assert result["featured_flag"] is True

    async def test_update_developer_profile_idempotent(self, db: AsyncSession):
        """Calling update_developer_profile twice with same data is safe."""
        creator = await _insert_creator(db)
        kwargs = dict(
            creator_id=creator.id,
            bio="Bio",
            links=[],
            specialties=[],
            featured_flag=False,
        )
        await dual_layer_service.update_developer_profile(db, **kwargs)
        result = await dual_layer_service.update_developer_profile(db, **kwargs)
        assert result["bio"] == "Bio"

    async def test_get_or_create_developer_profile_reuses_existing(
        self, db: AsyncSession
    ):
        """get_or_create_developer_profile returns the same row on second call."""
        creator = await _insert_creator(db)
        profile1 = await dual_layer_service.get_or_create_developer_profile(
            db, creator_id=creator.id
        )
        profile2 = await dual_layer_service.get_or_create_developer_profile(
            db, creator_id=creator.id
        )
        assert profile1.creator_id == profile2.creator_id

    async def test_developer_profile_payload_handles_corrupt_json(
        self, db: AsyncSession
    ):
        """Corrupt JSON in links_json/specialties_json falls back to empty lists."""
        creator = await _insert_creator(db)
        profile = DeveloperProfile(
            creator_id=creator.id,
            bio="Test",
            links_json="NOT_JSON!!!",
            specialties_json="ALSO_NOT_JSON",
            featured_flag=False,
        )
        db.add(profile)
        await db.commit()

        payload = await dual_layer_service.get_developer_profile_payload(
            db, creator_id=creator.id
        )
        assert payload["links"] == []
        assert payload["specialties"] == []


# ===========================================================================
# BLOCK 7: Open and Creator Metrics
# ===========================================================================


class TestMetrics:
    """get_dual_layer_open_metrics, get_creator_dual_layer_metrics."""

    async def test_open_metrics_returns_expected_keys(self, db: AsyncSession):
        """get_dual_layer_open_metrics returns the four expected keys."""
        metrics = await dual_layer_service.get_dual_layer_open_metrics(db)
        assert "end_users_count" in metrics
        assert "consumer_orders_count" in metrics
        assert "developer_profiles_count" in metrics
        assert "platform_fee_volume_usd" in metrics

    async def test_open_metrics_counts_end_users(self, db: AsyncSession):
        """end_users_count reflects actual EndUser rows inserted."""
        agent = _make_registered_agent()
        db.add(agent)
        await db.commit()

        user = EndUser(
            id=_uid(),
            email=_unique_email(),
            password_hash="hashed",
            managed_agent_id=agent.id,
            status="active",
        )
        db.add(user)
        await db.commit()

        metrics = await dual_layer_service.get_dual_layer_open_metrics(db)
        assert metrics["end_users_count"] >= 1

    async def test_creator_metrics_no_agents_returns_zeros(self, db: AsyncSession):
        """Creator with no agents returns all-zero revenue metrics."""
        creator = await _insert_creator(db)
        metrics = await dual_layer_service.get_creator_dual_layer_metrics(
            db, creator_id=creator.id
        )
        assert metrics["creator_gross_revenue_usd"] == 0.0
        assert metrics["creator_platform_fees_usd"] == 0.0
        assert metrics["creator_net_revenue_usd"] == 0.0
        assert metrics["creator_pending_payout_usd"] == 0.0

    async def test_creator_metrics_has_all_keys(self, db: AsyncSession):
        """Creator metrics dict always includes all four revenue keys."""
        creator = await _insert_creator(db)
        metrics = await dual_layer_service.get_creator_dual_layer_metrics(
            db, creator_id=creator.id
        )
        for key in (
            "creator_gross_revenue_usd",
            "creator_platform_fees_usd",
            "creator_net_revenue_usd",
            "creator_pending_payout_usd",
        ):
            assert key in metrics


# ===========================================================================
# BLOCK 8: Event Envelope Building and Signature Verification
# ===========================================================================


class TestEventEnvelope:
    """build_event_envelope, verify_event_signature, should_dispatch_event."""

    def test_build_event_envelope_public_event_structure(self):
        """Public event envelope has required top-level keys."""
        event = event_subscription_service.build_event_envelope(
            "demand_spike",
            {"query_pattern": "AI news", "velocity": 5, "category": "web_search"},
        )
        for key in (
            "event_id",
            "seq",
            "event_type",
            "occurred_at",
            "signature",
            "visibility",
            "topic",
        ):
            assert key in event

    def test_build_event_envelope_sanitizes_public_payload(self):
        """Public event strips fields not in public_fields policy."""
        event = event_subscription_service.build_event_envelope(
            "listing_created",
            {
                "listing_id": "abc",
                "title": "Test",
                "category": "web_search",
                "price": 0.25,
                "price_usd": 0.25,
                "price_usdc": 0.25,
                "seller_secret": "do-not-expose",
            },
        )
        assert "seller_secret" not in event["payload"]
        assert "listing_id" in event["payload"]

    def test_build_event_envelope_private_event_not_blocked_with_agent(self):
        """Private event with agent_id in payload is not blocked."""
        agent_id = _uid()
        event = event_subscription_service.build_event_envelope(
            "payment_confirmed",
            {"buyer_id": agent_id, "seller_id": _uid(), "amount": 1.0},
        )
        assert event["blocked"] is False

    def test_build_event_envelope_private_event_blocked_without_targets(self):
        """Private _PRIVATE_TOPIC event without any agent targets is blocked."""
        event = event_subscription_service.build_event_envelope(
            "catalog_update",
            {"some_unrelated_key": "value"},
        )
        assert event["blocked"] is True

    def test_build_event_envelope_seq_increments(self):
        """Each call to build_event_envelope increments the seq counter."""
        e1 = event_subscription_service.build_event_envelope(
            "test_event", {}
        )
        e2 = event_subscription_service.build_event_envelope(
            "test_event", {}
        )
        assert e2["seq"] > e1["seq"]

    def test_verify_event_signature_valid(self):
        """verify_event_signature returns True for a correctly signed payload."""
        secret = SIGN_SECRET
        payload = {
            "event_id": _uid(),
            "seq": 1,
            "event_type": "test_event",
            "occurred_at": "2026-01-01T00:00:00",
            "agent_id": None,
            "payload": {},
            "visibility": "public",
            "topic": "public.market",
            "target_agent_ids": [],
            "target_creator_ids": [],
            "target_user_ids": [],
            "schema_version": "2026-02-15",
            "delivery_attempt": 1,
        }
        data = event_subscription_service._canonical_payload(payload).encode("utf-8")
        sig = "sha256=" + hmac.new(
            secret.encode(), data, hashlib.sha256
        ).hexdigest()

        assert event_subscription_service.verify_event_signature(
            payload=payload, signature=sig, current_secret=secret
        )

    def test_verify_event_signature_invalid(self):
        """verify_event_signature returns False for a tampered payload."""
        payload = {"event_id": _uid(), "event_type": "test_event"}
        assert not event_subscription_service.verify_event_signature(
            payload=payload,
            signature="sha256=badsig",
            current_secret=SIGN_SECRET,
        )

    def test_verify_event_signature_accepts_previous_key(self):
        """Previous secret is also accepted during key rotation."""
        old_secret = "old-signing-secret"
        new_secret = "new-signing-secret"
        payload = {
            "event_id": _uid(),
            "seq": 1,
            "event_type": "test_event",
            "occurred_at": "2026-01-01T00:00:00",
            "agent_id": None,
            "payload": {},
            "visibility": "public",
            "topic": "public.market",
            "target_agent_ids": [],
            "target_creator_ids": [],
            "target_user_ids": [],
            "schema_version": "2026-02-15",
            "delivery_attempt": 1,
        }
        data = event_subscription_service._canonical_payload(payload).encode("utf-8")
        sig = "sha256=" + hmac.new(
            old_secret.encode(), data, hashlib.sha256
        ).hexdigest()

        assert event_subscription_service.verify_event_signature(
            payload=payload,
            signature=sig,
            current_secret=new_secret,
            previous_secret=old_secret,
        )

    def test_should_dispatch_event_not_blocked(self):
        """should_dispatch_event returns True when blocked=False."""
        event = {"blocked": False, "event_type": "test_event"}
        assert event_subscription_service.should_dispatch_event(event) is True

    def test_should_dispatch_event_blocked(self):
        """should_dispatch_event returns False when blocked=True."""
        event = {"blocked": True, "event_type": "test_event"}
        assert event_subscription_service.should_dispatch_event(event) is False

    def test_validate_callback_url_normalizes_path(self):
        """validate_callback_url adds trailing slash when path is absent."""
        result = event_subscription_service.validate_callback_url(
            "http://example.com"
        )
        assert result.endswith("/")

    def test_validate_callback_url_rejects_non_http(self):
        """Non-HTTP/HTTPS schemes raise ValueError."""
        with pytest.raises(ValueError, match="http or https"):
            event_subscription_service.validate_callback_url("ftp://evil.com/hook")

    def test_validate_callback_url_rejects_private_ip(self):
        """A raw private IP address is rejected (disallowed)."""
        with pytest.raises(ValueError):
            event_subscription_service.validate_callback_url("http://192.168.1.5/hook")

    def test_validate_callback_url_rejects_loopback_ip(self):
        """Loopback IP 127.0.0.1 is rejected."""
        with pytest.raises(ValueError):
            event_subscription_service.validate_callback_url("http://127.0.0.1/hook")


# ===========================================================================
# BLOCK 9: Subscription CRUD (register, list, delete)
# ===========================================================================


class TestSubscriptionCRUD:
    """register_subscription, list_subscriptions, delete_subscription."""

    async def _seed_agent(self, db: AsyncSession) -> str:
        agent = _make_registered_agent()
        db.add(agent)
        await db.commit()
        return agent.id

    async def test_register_subscription_creates_new(self, db: AsyncSession):
        """Registering a new subscription returns a dict with id and secret."""
        agent_id = await self._seed_agent(db)
        result = await event_subscription_service.register_subscription(
            db,
            agent_id=agent_id,
            callback_url="https://example.com/webhook",
            event_types=["listing_created", "demand_spike"],
        )
        assert "id" in result
        assert result["agent_id"] == agent_id
        assert result["status"] == "active"
        assert result["secret"].startswith("whsec_")

    async def test_register_subscription_upserts_existing(self, db: AsyncSession):
        """Re-registering the same URL updates event_types and resets failure_count."""
        agent_id = await self._seed_agent(db)
        first = await event_subscription_service.register_subscription(
            db,
            agent_id=agent_id,
            callback_url="https://example.com/hook2",
            event_types=["demand_spike"],
        )
        second = await event_subscription_service.register_subscription(
            db,
            agent_id=agent_id,
            callback_url="https://example.com/hook2",
            event_types=["listing_created"],
        )
        assert first["id"] == second["id"]
        assert second["failure_count"] == 0
        assert "listing_created" in second["event_types"]

    async def test_list_subscriptions_returns_agent_subscriptions(
        self, db: AsyncSession
    ):
        """list_subscriptions returns only subscriptions for the given agent."""
        agent_id = await self._seed_agent(db)
        other_agent_id = await self._seed_agent(db)

        await event_subscription_service.register_subscription(
            db,
            agent_id=agent_id,
            callback_url="https://example.com/hookA",
        )
        await event_subscription_service.register_subscription(
            db,
            agent_id=other_agent_id,
            callback_url="https://other.com/hookB",
        )

        subs = await event_subscription_service.list_subscriptions(
            db, agent_id=agent_id
        )
        assert len(subs) == 1
        assert subs[0]["agent_id"] == agent_id

    async def test_delete_subscription_removes_row(self, db: AsyncSession):
        """delete_subscription returns True and removes the DB row."""
        agent_id = await self._seed_agent(db)
        sub = await event_subscription_service.register_subscription(
            db,
            agent_id=agent_id,
            callback_url="https://example.com/del",
        )
        deleted = await event_subscription_service.delete_subscription(
            db, agent_id=agent_id, subscription_id=sub["id"]
        )
        assert deleted is True

        subs = await event_subscription_service.list_subscriptions(
            db, agent_id=agent_id
        )
        assert len(subs) == 0

    async def test_delete_nonexistent_subscription_returns_false(
        self, db: AsyncSession
    ):
        """delete_subscription for an unknown ID returns False."""
        agent_id = await self._seed_agent(db)
        result = await event_subscription_service.delete_subscription(
            db, agent_id=agent_id, subscription_id="nonexistent-sub-id"
        )
        assert result is False

    async def test_register_subscription_wrong_agent_cannot_delete(
        self, db: AsyncSession
    ):
        """Agent A cannot delete Agent B's subscription (returns False)."""
        agent_a = await self._seed_agent(db)
        agent_b = await self._seed_agent(db)

        sub = await event_subscription_service.register_subscription(
            db,
            agent_id=agent_a,
            callback_url="https://example.com/hookC",
        )
        result = await event_subscription_service.delete_subscription(
            db, agent_id=agent_b, subscription_id=sub["id"]
        )
        assert result is False

    async def test_list_subscriptions_empty_for_new_agent(self, db: AsyncSession):
        """list_subscriptions returns an empty list for an agent with no subscriptions."""
        agent_id = await self._seed_agent(db)
        subs = await event_subscription_service.list_subscriptions(
            db, agent_id=agent_id
        )
        assert subs == []


# ===========================================================================
# BLOCK 10: Webhook Dispatch and Delivery
# ===========================================================================


class TestWebhookDispatch:
    """dispatch_event_to_subscriptions and _deliver_to_subscription."""

    async def _seed_subscription(
        self,
        db: AsyncSession,
        *,
        event_types: list[str] | None = None,
        callback_url: str = "https://example.com/receive",
    ) -> tuple[str, EventSubscription]:
        """Return (agent_id, subscription) for a fresh agent."""
        agent = _make_registered_agent()
        db.add(agent)
        await db.commit()

        sub = EventSubscription(
            id=_uid(),
            agent_id=agent.id,
            callback_url=callback_url,
            event_types_json=json.dumps(event_types or ["*"]),
            secret="whsec_testhook",
            status="active",
            failure_count=0,
        )
        db.add(sub)
        await db.commit()
        await db.refresh(sub)
        return agent.id, sub

    async def test_dispatch_blocked_event_skips_delivery(self, db: AsyncSession):
        """Blocked events are not dispatched to any subscription."""
        agent_id, sub = await self._seed_subscription(db)

        blocked_event = {
            "blocked": True,
            "visibility": "private",
            "event_type": "payment_confirmed",
            "target_agent_ids": [agent_id],
        }

        with patch(
            "marketplace.services.event_subscription_service._deliver_to_subscription",
            new_callable=AsyncMock,
        ) as mock_deliver:
            await event_subscription_service.dispatch_event_to_subscriptions(
                db, event=blocked_event
            )

        mock_deliver.assert_not_awaited()

    async def test_dispatch_public_event_calls_deliver(self, db: AsyncSession):
        """A non-blocked public event triggers _deliver_to_subscription."""
        agent_id, sub = await self._seed_subscription(db)
        event = event_subscription_service.build_event_envelope(
            "listing_created",
            {"listing_id": _uid(), "title": "T", "category": "web_search",
             "price": 0.1, "price_usd": 0.1, "price_usdc": 0.1},
            agent_id=agent_id,
        )

        with patch(
            "marketplace.services.event_subscription_service._deliver_to_subscription",
            new_callable=AsyncMock,
        ) as mock_deliver:
            await event_subscription_service.dispatch_event_to_subscriptions(
                db, event=event
            )

        mock_deliver.assert_awaited_once()

    async def test_dispatch_private_event_delivers_to_target_agent(
        self, db: AsyncSession
    ):
        """Private event is delivered to subscription for the targeted agent."""
        agent_id, sub = await self._seed_subscription(db)
        event = event_subscription_service.build_event_envelope(
            "payment_confirmed",
            {"buyer_id": agent_id, "seller_id": _uid(), "amount": 0.5},
        )
        assert not event["blocked"]

        with patch(
            "marketplace.services.event_subscription_service._deliver_to_subscription",
            new_callable=AsyncMock,
        ) as mock_deliver:
            await event_subscription_service.dispatch_event_to_subscriptions(
                db, event=event
            )

        mock_deliver.assert_awaited_once()

    async def test_dispatch_private_event_no_targets_skips_all(
        self, db: AsyncSession
    ):
        """Private event with no target_agent_ids skips all subscriptions."""
        _, sub = await self._seed_subscription(db)
        blocked_event = {
            "blocked": False,
            "visibility": "private",
            "topic": "private.agent",
            "event_type": "catalog_update",
            "target_agent_ids": [],
        }

        with patch(
            "marketplace.services.event_subscription_service._deliver_to_subscription",
            new_callable=AsyncMock,
        ) as mock_deliver:
            await event_subscription_service.dispatch_event_to_subscriptions(
                db, event=blocked_event
            )

        mock_deliver.assert_not_awaited()

    async def test_deliver_to_subscription_success_sets_delivered_status(
        self, db: AsyncSession
    ):
        """A 200 HTTP response creates a WebhookDelivery with status='delivered'."""
        agent_id, sub = await self._seed_subscription(db)
        event = event_subscription_service.build_event_envelope(
            "listing_created",
            {"listing_id": _uid(), "title": "T", "category": "web_search",
             "price": 0.1, "price_usd": 0.1, "price_usdc": 0.1},
            agent_id=agent_id,
        )

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = "ok"

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = AsyncMock(return_value=mock_response)

        with patch(
            "marketplace.services.event_subscription_service.httpx.AsyncClient",
            return_value=mock_client,
        ):
            await event_subscription_service._deliver_to_subscription(
                db, subscription=sub, event=event
            )

        delivery_row = await db.execute(
            select(WebhookDelivery).where(WebhookDelivery.subscription_id == sub.id)
        )
        delivery = delivery_row.scalar_one_or_none()
        assert delivery is not None
        assert delivery.status == "delivered"
        assert delivery.response_code == 200

    async def test_deliver_to_subscription_failure_increments_count(
        self, db: AsyncSession
    ):
        """A 500 HTTP response increments the subscription failure_count."""
        agent_id, sub = await self._seed_subscription(db)
        event = event_subscription_service.build_event_envelope(
            "listing_created",
            {"listing_id": _uid(), "title": "T", "category": "web_search",
             "price": 0.1, "price_usd": 0.1, "price_usdc": 0.1},
            agent_id=agent_id,
        )

        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = AsyncMock(return_value=mock_response)

        with (
            patch(
                "marketplace.services.event_subscription_service.httpx.AsyncClient",
                return_value=mock_client,
            ),
            patch(
                "marketplace.services.event_subscription_service.asyncio.sleep",
                new_callable=AsyncMock,
            ),
        ):
            await event_subscription_service._deliver_to_subscription(
                db, subscription=sub, event=event
            )

        await db.refresh(sub)
        assert sub.failure_count > 0

    async def test_deliver_pauses_subscription_on_max_failures(
        self, db: AsyncSession
    ):
        """Subscription is paused when failure_count reaches trust_webhook_max_failures."""
        from marketplace.config import settings

        agent_id, sub = await self._seed_subscription(db)
        # Set failure count to one below the threshold so one more failure pauses it
        sub.failure_count = settings.trust_webhook_max_failures - 1
        await db.commit()

        event = event_subscription_service.build_event_envelope(
            "listing_created",
            {"listing_id": _uid(), "title": "T", "category": "web_search",
             "price": 0.1, "price_usd": 0.1, "price_usdc": 0.1},
            agent_id=agent_id,
        )

        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.text = "Error"

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = AsyncMock(return_value=mock_response)

        with (
            patch(
                "marketplace.services.event_subscription_service.httpx.AsyncClient",
                return_value=mock_client,
            ),
            patch(
                "marketplace.services.event_subscription_service.asyncio.sleep",
                new_callable=AsyncMock,
            ),
        ):
            await event_subscription_service._deliver_to_subscription(
                db, subscription=sub, event=event
            )

        await db.refresh(sub)
        assert sub.status == "paused"

    async def test_deliver_network_exception_logs_failed_delivery(
        self, db: AsyncSession
    ):
        """A connection error creates a WebhookDelivery with status='failed'."""
        agent_id, sub = await self._seed_subscription(db)
        event = event_subscription_service.build_event_envelope(
            "listing_created",
            {"listing_id": _uid(), "title": "T", "category": "web_search",
             "price": 0.1, "price_usd": 0.1, "price_usdc": 0.1},
            agent_id=agent_id,
        )

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = AsyncMock(side_effect=ConnectionError("timeout"))

        with (
            patch(
                "marketplace.services.event_subscription_service.httpx.AsyncClient",
                return_value=mock_client,
            ),
            patch(
                "marketplace.services.event_subscription_service.asyncio.sleep",
                new_callable=AsyncMock,
            ),
        ):
            await event_subscription_service._deliver_to_subscription(
                db, subscription=sub, event=event
            )

        delivery_row = await db.execute(
            select(WebhookDelivery).where(WebhookDelivery.subscription_id == sub.id)
        )
        delivery = delivery_row.scalars().first()
        assert delivery is not None
        assert delivery.status == "failed"


# ===========================================================================
# BLOCK 11: Payload Sanitisation and Target Extraction
# ===========================================================================


class TestPayloadAndTargetExtraction:
    """_sanitize_payload, _extract_target_agent_ids, _extract_target_creator_ids,
    _extract_target_user_ids, _event_matches."""

    def test_sanitize_payload_private_returns_full_payload(self):
        """Private visibility returns the full payload unchanged."""
        payload = {"buyer_id": "a", "amount": 1.5, "secret": "xyz"}
        policy = {"public_fields": ["buyer_id"]}
        result = event_subscription_service._sanitize_payload(payload, policy, "private")
        assert result == payload

    def test_sanitize_payload_public_with_fields_filters(self):
        """Public visibility with public_fields returns only those fields."""
        payload = {"listing_id": "abc", "title": "T", "hidden": "no"}
        policy = {"public_fields": ["listing_id", "title"]}
        result = event_subscription_service._sanitize_payload(payload, policy, "public")
        assert set(result.keys()) == {"listing_id", "title"}

    def test_sanitize_payload_public_no_fields_returns_full(self):
        """Public visibility with empty public_fields returns the full payload."""
        payload = {"a": 1, "b": 2}
        policy = {"public_fields": []}
        result = event_subscription_service._sanitize_payload(payload, policy, "public")
        assert result == payload

    def test_extract_target_agent_ids_from_payload_keys(self):
        """Standard agent-related payload keys are extracted automatically."""
        payload = {"buyer_id": "agent-A", "seller_id": "agent-B"}
        policy = {"target_keys": []}
        result = event_subscription_service._extract_target_agent_ids(payload, policy)
        assert "agent-A" in result
        assert "agent-B" in result

    def test_extract_target_agent_ids_includes_explicit_targets(self):
        """Explicitly passed target_agent_ids are merged with payload extractions."""
        payload = {}
        policy = {"target_keys": []}
        result = event_subscription_service._extract_target_agent_ids(
            payload, policy, explicit_targets=["explicit-agent"]
        )
        assert "explicit-agent" in result

    def test_extract_target_creator_ids_from_payload(self):
        """creator_id field in payload is captured as a target."""
        payload = {"creator_id": "creator-X"}
        policy = {"target_keys": []}
        result = event_subscription_service._extract_target_creator_ids(payload, policy)
        assert "creator-X" in result

    def test_extract_target_user_ids_from_payload(self):
        """user_id field in payload is captured as a target."""
        payload = {"user_id": "user-Y"}
        policy = {"target_keys": []}
        result = event_subscription_service._extract_target_user_ids(payload, policy)
        assert "user-Y" in result

    def test_event_matches_wildcard_subscription(self):
        """A wildcard subscription matches any event type for the targeted agent."""
        agent_id = _uid()
        sub = EventSubscription(
            id=_uid(),
            agent_id=agent_id,
            callback_url="https://example.com/wc",
            event_types_json='["*"]',
            secret="whsec_x",
            status="active",
        )
        event = {
            "event_type": "payment_confirmed",
            "visibility": "private",
            "target_agent_ids": [agent_id],
        }
        assert event_subscription_service._event_matches(sub, event) is True

    def test_event_matches_specific_type(self):
        """A subscription for a specific event_type matches only that type."""
        agent_id = _uid()
        sub = EventSubscription(
            id=_uid(),
            agent_id=agent_id,
            callback_url="https://example.com/sp",
            event_types_json='["listing_created"]',
            secret="whsec_y",
            status="active",
        )
        event_match = {
            "event_type": "listing_created",
            "visibility": "public",
            "target_agent_ids": [],
            "agent_id": agent_id,
        }
        event_no_match = {
            "event_type": "demand_spike",
            "visibility": "public",
            "target_agent_ids": [],
            "agent_id": agent_id,
        }
        assert event_subscription_service._event_matches(sub, event_match) is True
        assert event_subscription_service._event_matches(sub, event_no_match) is False

    def test_event_matches_private_wrong_agent_returns_false(self):
        """Private event does not match a subscription for a different agent."""
        sub = EventSubscription(
            id=_uid(),
            agent_id="agent-A",
            callback_url="https://example.com/priv",
            event_types_json='["*"]',
            secret="whsec_z",
            status="active",
        )
        event = {
            "event_type": "payment_confirmed",
            "visibility": "private",
            "target_agent_ids": ["agent-B"],  # Different agent
        }
        assert event_subscription_service._event_matches(sub, event) is False


# ===========================================================================
# BLOCK 12: Webhook Redaction
# ===========================================================================


class TestWebhookRedaction:
    """redact_old_webhook_deliveries clears stale payload/response_body data."""

    async def _insert_delivery(
        self,
        db: AsyncSession,
        subscription_id: str,
        *,
        days_old: int = 0,
    ) -> WebhookDelivery:
        created = datetime.now(timezone.utc) - timedelta(days=days_old)
        delivery = WebhookDelivery(
            id=_uid(),
            subscription_id=subscription_id,
            event_id=_uid(),
            event_type="listing_created",
            payload_json='{"secret": "data"}',
            signature="sha256:abc",
            status="delivered",
            response_code=200,
            response_body="OK",
            delivery_attempt=1,
            created_at=created,
        )
        db.add(delivery)
        await db.commit()
        await db.refresh(delivery)
        return delivery

    async def _seed_subscription_row(self, db: AsyncSession) -> str:
        """Create the minimum required rows for a WebhookDelivery FK to work."""
        agent = _make_registered_agent()
        db.add(agent)
        await db.commit()

        sub = EventSubscription(
            id=_uid(),
            agent_id=agent.id,
            callback_url="https://example.com/rd",
            event_types_json='["*"]',
            secret="whsec_rd",
            status="active",
        )
        db.add(sub)
        await db.commit()
        return sub.id

    async def test_redact_old_deliveries_clears_payload_and_body(
        self, db: AsyncSession
    ):
        """Deliveries older than retention_days have payload_json and response_body redacted."""
        sub_id = await self._seed_subscription_row(db)
        old_delivery = await self._insert_delivery(db, sub_id, days_old=40)

        count = await event_subscription_service.redact_old_webhook_deliveries(
            db, retention_days=30
        )
        assert count >= 1

        await db.refresh(old_delivery)
        assert old_delivery.payload_json == "{}"
        assert old_delivery.response_body == "[redacted]"

    async def test_redact_skips_recent_deliveries(self, db: AsyncSession):
        """Recent deliveries within the retention window are not redacted."""
        sub_id = await self._seed_subscription_row(db)
        recent = await self._insert_delivery(db, sub_id, days_old=5)

        count = await event_subscription_service.redact_old_webhook_deliveries(
            db, retention_days=30
        )
        assert count == 0

        await db.refresh(recent)
        assert recent.payload_json == '{"secret": "data"}'
        assert recent.response_body == "OK"

    async def test_redact_already_redacted_not_counted_again(
        self, db: AsyncSession
    ):
        """A delivery that is already redacted is not counted as a new redaction."""
        sub_id = await self._seed_subscription_row(db)
        delivery = await self._insert_delivery(db, sub_id, days_old=50)
        delivery.payload_json = "{}"
        delivery.response_body = "[redacted]"
        await db.commit()

        count = await event_subscription_service.redact_old_webhook_deliveries(
            db, retention_days=30
        )
        assert count == 0

    async def test_redact_returns_correct_count(self, db: AsyncSession):
        """redact_old_webhook_deliveries returns exactly the number of rows it modifies."""
        sub_id = await self._seed_subscription_row(db)
        await self._insert_delivery(db, sub_id, days_old=60)
        await self._insert_delivery(db, sub_id, days_old=45)
        await self._insert_delivery(db, sub_id, days_old=2)  # recent; skipped

        count = await event_subscription_service.redact_old_webhook_deliveries(
            db, retention_days=30
        )
        assert count == 2
