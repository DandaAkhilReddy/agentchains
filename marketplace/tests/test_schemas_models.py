"""Unit tests for Pydantic schema validation and SQLAlchemy model defaults.

Covers 18 Pydantic schema tests and 12 SQLAlchemy model default tests (30 total).
"""

from decimal import Decimal

import pytest
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from marketplace.schemas.agent import AgentRegisterRequest, AgentUpdateRequest
from marketplace.schemas.listing import ListingCreateRequest, ListingUpdateRequest
from marketplace.schemas.transaction import TransactionInitiateRequest
from marketplace.schemas.express import ExpressDeliveryResponse
from marketplace.schemas.common import HealthResponse, CacheStats

from marketplace.models.agent import RegisteredAgent
from marketplace.models.listing import DataListing
from marketplace.models.transaction import Transaction
from marketplace.models.token_account import TokenAccount
from marketplace.models.creator import Creator
from marketplace.models.audit_log import AuditLog
from marketplace.models.redemption import RedemptionRequest
from marketplace.models.demand_signal import DemandSignal
from marketplace.models.zkproof import ZKProof
from marketplace.models.seller_webhook import SellerWebhook
from marketplace.models.catalog import CatalogSubscription

from marketplace.tests.conftest import _new_id


# ===========================================================================
# Pydantic Schema Validation (18 tests)
# ===========================================================================


# --- AgentRegisterRequest (7 tests) ----------------------------------------

class TestAgentRegisterRequest:
    """Validate AgentRegisterRequest field constraints and defaults."""

    def test_valid_data_passes(self):
        """A well-formed registration request should construct without error."""
        req = AgentRegisterRequest(
            name="test-agent",
            agent_type="seller",
            public_key="ssh-rsa AAAA_long_key_placeholder",
        )
        assert req.name == "test-agent"
        assert req.agent_type == "seller"
        assert req.public_key == "ssh-rsa AAAA_long_key_placeholder"

    def test_name_too_long_fails(self):
        """name exceeding max_length=100 should raise ValidationError."""
        with pytest.raises(ValidationError):
            AgentRegisterRequest(
                name="x" * 101,
                agent_type="buyer",
                public_key="ssh-rsa AAAA_long_key_placeholder",
            )

    def test_name_empty_fails(self):
        """name with min_length=1 should reject empty string."""
        with pytest.raises(ValidationError):
            AgentRegisterRequest(
                name="",
                agent_type="buyer",
                public_key="ssh-rsa AAAA_long_key_placeholder",
            )

    def test_invalid_agent_type_fails(self):
        """agent_type must match pattern ^(seller|buyer|both)$."""
        with pytest.raises(ValidationError):
            AgentRegisterRequest(
                name="test-agent",
                agent_type="observer",
                public_key="ssh-rsa AAAA_long_key_placeholder",
            )

    def test_public_key_too_short_fails(self):
        """public_key with min_length=10 should reject short strings."""
        with pytest.raises(ValidationError):
            AgentRegisterRequest(
                name="test-agent",
                agent_type="seller",
                public_key="short",
            )

    def test_defaults_capabilities_empty_list(self):
        """capabilities should default to an empty list."""
        req = AgentRegisterRequest(
            name="test-agent",
            agent_type="both",
            public_key="ssh-rsa AAAA_long_key_placeholder",
        )
        assert req.capabilities == []

    def test_defaults_wallet_address_empty(self):
        """wallet_address should default to empty string."""
        req = AgentRegisterRequest(
            name="test-agent",
            agent_type="both",
            public_key="ssh-rsa AAAA_long_key_placeholder",
        )
        assert req.wallet_address == ""


# --- ListingCreateRequest (6 tests) ----------------------------------------

class TestListingCreateRequest:
    """Validate ListingCreateRequest field constraints and defaults."""

    def test_valid_data_passes(self):
        """A well-formed listing creation request should construct without error."""
        req = ListingCreateRequest(
            title="Python tutorial data",
            category="web_search",
            content="eyJkYXRhIjogInRlc3QifQ==",
            price_usdc=0.50,
        )
        assert req.title == "Python tutorial data"
        assert req.price_usdc == 0.50
        assert req.quality_score == 0.5  # default

    def test_price_zero_fails(self):
        """price_usdc with gt=0 should reject zero."""
        with pytest.raises(ValidationError):
            ListingCreateRequest(
                title="Test",
                category="web_search",
                content="data",
                price_usdc=0,
            )

    def test_price_too_high_fails(self):
        """price_usdc with le=1000 should reject values above 1000."""
        with pytest.raises(ValidationError):
            ListingCreateRequest(
                title="Test",
                category="web_search",
                content="data",
                price_usdc=1001,
            )

    def test_invalid_category_fails(self):
        """category must match one of the allowed values."""
        with pytest.raises(ValidationError):
            ListingCreateRequest(
                title="Test",
                category="unknown_category",
                content="data",
                price_usdc=1.0,
            )

    def test_quality_below_zero_fails(self):
        """quality_score with ge=0 should reject negative values."""
        with pytest.raises(ValidationError):
            ListingCreateRequest(
                title="Test",
                category="web_search",
                content="data",
                price_usdc=1.0,
                quality_score=-0.1,
            )

    def test_quality_above_one_fails(self):
        """quality_score with le=1 should reject values above 1."""
        with pytest.raises(ValidationError):
            ListingCreateRequest(
                title="Test",
                category="web_search",
                content="data",
                price_usdc=1.0,
                quality_score=1.01,
            )


# --- ListingUpdateRequest (1 test) -----------------------------------------

class TestListingUpdateRequest:
    """Validate ListingUpdateRequest partial update behaviour."""

    def test_all_none_valid(self):
        """All fields None (no update) should be accepted as a partial update."""
        req = ListingUpdateRequest()
        assert req.title is None
        assert req.description is None
        assert req.price_usdc is None
        assert req.tags is None
        assert req.quality_score is None
        assert req.status is None


# --- TransactionInitiateRequest (1 test) ------------------------------------

class TestTransactionInitiateRequest:
    """Validate TransactionInitiateRequest."""

    def test_valid_listing_id_passes(self):
        """A valid listing_id string should be accepted."""
        req = TransactionInitiateRequest(listing_id="abc-123-def-456")
        assert req.listing_id == "abc-123-def-456"


# --- ExpressDeliveryResponse (1 test) ---------------------------------------

class TestExpressDeliveryResponse:
    """Validate ExpressDeliveryResponse constructs with all fields."""

    def test_all_fields_construct(self):
        """All fields should be set correctly on construction."""
        resp = ExpressDeliveryResponse(
            transaction_id="tx-001",
            listing_id="lst-001",
            content="base64content",
            content_hash="sha256:abc123",
            price_usdc=0.25,
            seller_id="agent-001",
            delivery_ms=42.5,
            cache_hit=True,
        )
        assert resp.transaction_id == "tx-001"
        assert resp.listing_id == "lst-001"
        assert resp.content == "base64content"
        assert resp.content_hash == "sha256:abc123"
        assert resp.price_usdc == 0.25
        assert resp.seller_id == "agent-001"
        assert resp.delivery_ms == 42.5
        assert resp.cache_hit is True


# --- HealthResponse (1 test) ------------------------------------------------

class TestHealthResponse:
    """Validate HealthResponse schema."""

    def test_constructs_with_required_fields(self):
        """HealthResponse should construct with all required fields."""
        resp = HealthResponse(
            status="ok",
            version="1.0.0",
            agents_count=5,
            listings_count=10,
            transactions_count=3,
        )
        assert resp.status == "ok"
        assert resp.version == "1.0.0"
        assert resp.agents_count == 5
        assert resp.listings_count == 10
        assert resp.transactions_count == 3
        assert resp.cache_stats is None  # optional, default None


# --- AgentUpdateRequest (1 test) --------------------------------------------

class TestAgentUpdateRequest:
    """Validate AgentUpdateRequest partial update behaviour."""

    def test_partial_update_description_only(self):
        """Setting only description should leave other fields as None."""
        req = AgentUpdateRequest(description="Updated bio")
        assert req.description == "Updated bio"
        assert req.wallet_address is None
        assert req.capabilities is None
        assert req.a2a_endpoint is None
        assert req.status is None


# ===========================================================================
# SQLAlchemy Model Defaults (12 tests)
# ===========================================================================


class TestRegisteredAgentDefaults:
    """Verify RegisteredAgent column defaults without persisting to DB."""

    async def test_status_defaults_to_active(self, db: AsyncSession):
        """status column should default to 'active'."""
        agent = RegisteredAgent(
            id=_new_id(),
            name=f"agent-{_new_id()[:8]}",
            agent_type="seller",
            public_key="ssh-rsa AAAA_long_test_key",
        )
        db.add(agent)
        await db.commit()
        await db.refresh(agent)
        assert agent.status == "active"

    async def test_capabilities_defaults_to_empty_json(self, db: AsyncSession):
        """capabilities column should default to '[]' (JSON empty array string)."""
        agent = RegisteredAgent(
            id=_new_id(),
            name=f"agent-{_new_id()[:8]}",
            agent_type="buyer",
            public_key="ssh-rsa AAAA_long_test_key",
        )
        db.add(agent)
        await db.commit()
        await db.refresh(agent)
        assert agent.capabilities == "[]"


class TestDataListingDefaults:
    """Verify DataListing column defaults."""

    async def test_status_defaults_active_and_access_count_zero(self, db: AsyncSession):
        """status should default to 'active' and access_count to 0."""
        listing = DataListing(
            id=_new_id(),
            seller_id=_new_id(),
            title="Test",
            category="web_search",
            content_hash="sha256:" + "a" * 64,
            content_size=100,
            price_usdc=Decimal("1.0"),
        )
        db.add(listing)
        await db.commit()
        await db.refresh(listing)
        assert listing.status == "active"
        assert listing.access_count == 0


class TestTransactionDefaults:
    """Verify Transaction column defaults."""

    async def test_status_and_verification_defaults(self, db: AsyncSession):
        """status should default to 'initiated', verification_status to 'pending'."""
        tx = Transaction(
            id=_new_id(),
            listing_id=_new_id(),
            buyer_id=_new_id(),
            seller_id=_new_id(),
            amount_usdc=Decimal("1.0"),
            content_hash="sha256:" + "b" * 64,
        )
        db.add(tx)
        await db.commit()
        await db.refresh(tx)
        assert tx.status == "initiated"
        assert tx.verification_status == "pending"


class TestTokenAccountDefaults:
    """Verify TokenAccount column defaults."""

    async def test_balance_zero_and_tier_bronze(self, db: AsyncSession):
        """balance should default to 0, tier to 'bronze'."""
        account = TokenAccount(id=_new_id(), agent_id=_new_id())
        db.add(account)
        await db.commit()
        await db.refresh(account)
        assert float(account.balance) == 0.0
        assert account.tier == "bronze"


class TestCreatorDefaults:
    """Verify Creator column defaults."""

    async def test_payout_method_none_and_status_active(self, db: AsyncSession):
        """payout_method should default to 'none', status to 'active'."""
        creator = Creator(
            id=_new_id(),
            email=f"test-{_new_id()[:8]}@example.com",
            password_hash="hashed_password_placeholder_value",
            display_name="Test Creator",
        )
        db.add(creator)
        await db.commit()
        await db.refresh(creator)
        assert creator.payout_method == "none"
        assert creator.status == "active"


class TestAuditLogDefaults:
    """Verify AuditLog column defaults."""

    async def test_severity_defaults_to_info(self, db: AsyncSession):
        """severity column should default to 'info'."""
        log = AuditLog(
            id=_new_id(),
            event_type="agent.registered",
        )
        db.add(log)
        await db.commit()
        await db.refresh(log)
        assert log.severity == "info"


class TestRedemptionRequestDefaults:
    """Verify RedemptionRequest column defaults."""

    async def test_status_defaults_to_pending(self, db: AsyncSession):
        """status column should default to 'pending'."""
        # Create a creator first to satisfy FK constraint
        creator = Creator(
            id=_new_id(),
            email=f"redeem-{_new_id()[:8]}@example.com",
            password_hash="hashed_password_placeholder_value",
            display_name="Redeemer",
        )
        db.add(creator)
        await db.commit()

        req = RedemptionRequest(
            id=_new_id(),
            creator_id=creator.id,
            redemption_type="api_credits",
            amount_ard=Decimal("100.0"),
        )
        db.add(req)
        await db.commit()
        await db.refresh(req)
        assert req.status == "pending"


class TestDemandSignalDefaults:
    """Verify DemandSignal column defaults."""

    async def test_is_gap_zero_and_velocity_default(self, db: AsyncSession):
        """is_gap should default to 0, velocity to 0.0."""
        signal = DemandSignal(
            id=_new_id(),
            query_pattern=f"test-pattern-{_new_id()[:8]}",
        )
        db.add(signal)
        await db.commit()
        await db.refresh(signal)
        assert signal.is_gap == 0
        assert float(signal.velocity) == 0.0


class TestZKProofDefaults:
    """Verify ZKProof column defaults."""

    async def test_proof_data_defaults_to_empty_json(self, db: AsyncSession):
        """proof_data should default to '{}'."""
        proof = ZKProof(
            id=_new_id(),
            listing_id=_new_id(),
            proof_type="merkle_root",
            commitment="a" * 64,
        )
        db.add(proof)
        await db.commit()
        await db.refresh(proof)
        assert proof.proof_data == "{}"


class TestSellerWebhookDefaults:
    """Verify SellerWebhook column defaults."""

    async def test_status_active_and_failure_count_zero(self, db: AsyncSession):
        """status should default to 'active', failure_count to 0."""
        webhook = SellerWebhook(
            id=_new_id(),
            seller_id=_new_id(),
            url="https://example.com/webhook",
        )
        db.add(webhook)
        await db.commit()
        await db.refresh(webhook)
        assert webhook.status == "active"
        assert webhook.failure_count == 0


class TestCatalogSubscriptionDefaults:
    """Verify CatalogSubscription column defaults."""

    async def test_topic_pattern_star_and_status_active(self, db: AsyncSession):
        """topic_pattern should default to '*', status to 'active'."""
        sub = CatalogSubscription(
            id=_new_id(),
            subscriber_id=_new_id(),
            namespace_pattern="web_search.*",
        )
        db.add(sub)
        await db.commit()
        await db.refresh(sub)
        assert sub.topic_pattern == "*"
        assert sub.status == "active"
