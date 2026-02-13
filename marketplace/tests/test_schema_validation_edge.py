"""Edge-case unit tests for Pydantic schema validation.

Covers 25 tests across 5 describe blocks:
 - Malformed inputs (null where required, wrong types, extra fields, empty objects)
 - Missing required fields (each schema's required fields individually)
 - Type coercion edge cases (string numbers, boolean strings, float vs int, negatives)
 - Nested validation (deeply nested objects, invalid nested fields, array of items)
 - Boundary values (max lengths, min/max numeric ranges, unicode, special chars)
"""

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from marketplace.schemas.agent import (
    AgentListResponse,
    AgentRegisterRequest,
    AgentResponse,
    AgentUpdateRequest,
)
from marketplace.schemas.listing import (
    ListingCreateRequest,
    ListingListResponse,
    ListingResponse,
    ListingUpdateRequest,
    SellerSummary,
)
from marketplace.schemas.transaction import (
    PaymentDetails,
    TransactionConfirmPaymentRequest,
    TransactionDeliverRequest,
    TransactionInitiateRequest,
    TransactionInitiateResponse,
    TransactionResponse,
    TransactionVerifyRequest,
)
from marketplace.schemas.analytics import (
    AgentStatsResponse,
    DemandGapResponse,
    EarningsResponse,
    EarningsTimelineEntry,
    MultiLeaderboardEntry,
    OpportunityResponse,
    TrendingQueryResponse,
)
from marketplace.schemas.reputation import (
    LeaderboardEntry,
    ReputationResponse,
)
from marketplace.schemas.common import (
    CacheStats,
    ErrorResponse,
    HealthResponse,
    PaginatedResponse,
)
from marketplace.schemas.express import ExpressDeliveryResponse


# ===========================================================================
# 1. Malformed Inputs (5 tests)
# ===========================================================================


class TestMalformedInputs:
    """Validate schemas reject fundamentally malformed data."""

    def test_null_required_name_raises(self):
        """Passing None for a required str field (name) must raise ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            AgentRegisterRequest(
                name=None,
                agent_type="seller",
                public_key="ssh-rsa AAAA_long_key_placeholder",
            )
        errors = exc_info.value.errors()
        assert any(e["loc"] == ("name",) for e in errors)

    def test_wrong_type_price_list_instead_of_float(self):
        """Supplying a list where a float is expected must raise ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            ListingCreateRequest(
                title="Test",
                category="web_search",
                content="data",
                price_usdc=[1.0, 2.0],
            )
        errors = exc_info.value.errors()
        assert any(e["loc"] == ("price_usdc",) for e in errors)

    def test_extra_unexpected_fields_are_ignored_by_default(self):
        """Pydantic v2 models ignore extra fields by default (no forbid config).
        The model should construct successfully, dropping the extra field."""
        req = AgentRegisterRequest(
            name="agent-extra",
            agent_type="buyer",
            public_key="ssh-rsa AAAA_long_key_placeholder",
            totally_fake_field="surprise",
        )
        assert req.name == "agent-extra"
        assert not hasattr(req, "totally_fake_field")

    def test_empty_dict_for_agent_register_raises(self):
        """An empty dict (no required fields) must raise ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            AgentRegisterRequest()
        errors = exc_info.value.errors()
        missing_fields = {e["loc"][0] for e in errors if e["type"] == "missing"}
        assert "name" in missing_fields
        assert "agent_type" in missing_fields
        assert "public_key" in missing_fields

    def test_dict_value_where_str_expected_raises(self):
        """Passing a dict where a plain str is expected must raise ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            TransactionDeliverRequest(content={"key": "value"})
        errors = exc_info.value.errors()
        assert any(e["loc"] == ("content",) for e in errors)


# ===========================================================================
# 2. Missing Required Fields (5 tests)
# ===========================================================================


class TestMissingRequiredFields:
    """Validate that omitting required fields raises clear errors."""

    def test_listing_create_missing_title(self):
        """ListingCreateRequest requires title; omitting it must fail."""
        with pytest.raises(ValidationError) as exc_info:
            ListingCreateRequest(
                category="web_search",
                content="data",
                price_usdc=1.0,
            )
        errors = exc_info.value.errors()
        assert any(e["loc"] == ("title",) for e in errors)

    def test_listing_create_missing_category(self):
        """ListingCreateRequest requires category; omitting it must fail."""
        with pytest.raises(ValidationError) as exc_info:
            ListingCreateRequest(
                title="Test",
                content="data",
                price_usdc=1.0,
            )
        errors = exc_info.value.errors()
        assert any(e["loc"] == ("category",) for e in errors)

    def test_listing_create_missing_content(self):
        """ListingCreateRequest requires content; omitting it must fail."""
        with pytest.raises(ValidationError) as exc_info:
            ListingCreateRequest(
                title="Test",
                category="web_search",
                price_usdc=1.0,
            )
        errors = exc_info.value.errors()
        assert any(e["loc"] == ("content",) for e in errors)

    def test_listing_create_missing_price(self):
        """ListingCreateRequest requires price_usdc; omitting it must fail."""
        with pytest.raises(ValidationError) as exc_info:
            ListingCreateRequest(
                title="Test",
                category="web_search",
                content="data",
            )
        errors = exc_info.value.errors()
        assert any(e["loc"] == ("price_usdc",) for e in errors)

    def test_listing_create_all_required_missing_reports_all(self):
        """Omitting every required field should report errors for all of them."""
        with pytest.raises(ValidationError) as exc_info:
            ListingCreateRequest()
        errors = exc_info.value.errors()
        missing_locs = {e["loc"][0] for e in errors if e["type"] == "missing"}
        assert {"title", "category", "content", "price_usdc"} <= missing_locs


# ===========================================================================
# 3. Type Coercion Edge Cases (5 tests)
# ===========================================================================


class TestTypeCoercionEdgeCases:
    """Validate Pydantic's type coercion and rejection behaviour."""

    def test_string_number_coerced_to_float_for_price(self):
        """Pydantic v2 coerces numeric strings to float for float fields."""
        req = ListingCreateRequest(
            title="Test",
            category="web_search",
            content="data",
            price_usdc="5.5",
        )
        assert req.price_usdc == 5.5
        assert isinstance(req.price_usdc, float)

    def test_int_coerced_to_float_for_price(self):
        """An int value for a float field should be silently coerced."""
        req = ListingCreateRequest(
            title="Test",
            category="web_search",
            content="data",
            price_usdc=10,
        )
        assert req.price_usdc == 10.0
        assert isinstance(req.price_usdc, float)

    def test_negative_price_rejected(self):
        """price_usdc (gt=0) must reject negative values."""
        with pytest.raises(ValidationError) as exc_info:
            ListingCreateRequest(
                title="Test",
                category="web_search",
                content="data",
                price_usdc=-1.0,
            )
        errors = exc_info.value.errors()
        assert any(e["loc"] == ("price_usdc",) for e in errors)

    def test_boolean_true_coerced_to_int_for_integer_field(self):
        """Pydantic v2 coerces True to 1 for int fields (e.g. PaginatedResponse.total)."""
        resp = PaginatedResponse(total=True, page=1, page_size=10)
        assert resp.total == 1

    def test_float_quality_boundary_zero_accepted(self):
        """quality_score at exactly 0.0 (ge=0) should be accepted."""
        req = ListingCreateRequest(
            title="Test",
            category="web_search",
            content="data",
            price_usdc=1.0,
            quality_score=0.0,
        )
        assert req.quality_score == 0.0


# ===========================================================================
# 4. Nested Validation (5 tests)
# ===========================================================================


class TestNestedValidation:
    """Validate schemas with nested models and lists of models."""

    def test_health_response_with_valid_cache_stats(self):
        """HealthResponse should accept a properly nested CacheStats object."""
        resp = HealthResponse(
            status="ok",
            version="2.0.0",
            agents_count=10,
            listings_count=20,
            transactions_count=5,
            cache_stats=CacheStats(
                listings={"size": 100, "hits": 50},
                content={"size": 200, "hits": 75},
                agents={"size": 50, "hits": 30},
            ),
        )
        assert resp.cache_stats is not None
        assert resp.cache_stats.listings["size"] == 100
        assert resp.cache_stats.content["hits"] == 75

    def test_health_response_invalid_cache_stats_type_raises(self):
        """Passing a plain string for cache_stats (expects CacheStats) must fail."""
        with pytest.raises(ValidationError) as exc_info:
            HealthResponse(
                status="ok",
                version="2.0.0",
                agents_count=10,
                listings_count=20,
                transactions_count=5,
                cache_stats="not a CacheStats object",
            )
        errors = exc_info.value.errors()
        assert any("cache_stats" in str(e["loc"]) for e in errors)

    def test_agent_list_response_with_invalid_agent_in_list(self):
        """AgentListResponse with an invalid agent dict in the list must raise."""
        now = datetime.now(timezone.utc)
        valid_agent = {
            "id": "a1",
            "name": "Agent1",
            "description": "desc",
            "agent_type": "seller",
            "wallet_address": "",
            "capabilities": [],
            "a2a_endpoint": "",
            "status": "active",
            "created_at": now,
            "updated_at": now,
        }
        invalid_agent = {"id": "a2"}  # missing many required fields
        with pytest.raises(ValidationError):
            AgentListResponse(
                total=2,
                page=1,
                page_size=10,
                agents=[valid_agent, invalid_agent],
            )

    def test_transaction_initiate_response_nested_payment_details(self):
        """TransactionInitiateResponse with valid nested PaymentDetails succeeds."""
        resp = TransactionInitiateResponse(
            transaction_id="tx-001",
            status="initiated",
            amount_usdc=5.0,
            payment_details=PaymentDetails(
                pay_to_address="0xABC123",
                network="base-sepolia",
                asset="USDC",
                amount_usdc=5.0,
                facilitator_url="https://pay.example.com",
                simulated=True,
            ),
            content_hash="sha256:abcdef1234567890",
        )
        assert resp.payment_details.pay_to_address == "0xABC123"
        assert resp.payment_details.simulated is True
        assert resp.payment_details.asset == "USDC"

    def test_listing_response_nested_seller_summary_optional(self):
        """ListingResponse should accept None for the optional seller field."""
        now = datetime.now(timezone.utc)
        resp = ListingResponse(
            id="lst-001",
            seller_id="agent-001",
            seller=None,
            title="Test Listing",
            description="",
            category="web_search",
            content_hash="sha256:abc",
            content_size=100,
            content_type="application/json",
            price_usdc=1.0,
            currency="USDC",
            metadata={},
            tags=[],
            quality_score=0.85,
            freshness_at=now,
            expires_at=None,
            status="active",
            access_count=0,
            created_at=now,
            updated_at=now,
        )
        assert resp.seller is None

        # Now set a valid SellerSummary
        resp2 = ListingResponse(
            id="lst-002",
            seller_id="agent-002",
            seller=SellerSummary(id="agent-002", name="TopSeller", reputation_score=0.95),
            title="Test Listing 2",
            description="desc",
            category="code_analysis",
            content_hash="sha256:def",
            content_size=200,
            content_type="text/plain",
            price_usdc=2.5,
            currency="USDC",
            metadata={"key": "val"},
            tags=["python"],
            quality_score=0.9,
            freshness_at=now,
            status="active",
            access_count=3,
            created_at=now,
            updated_at=now,
        )
        assert resp2.seller.name == "TopSeller"
        assert resp2.seller.reputation_score == 0.95


# ===========================================================================
# 5. Boundary Values (5 tests)
# ===========================================================================


class TestBoundaryValues:
    """Validate field length limits, numeric boundaries, and special characters."""

    def test_agent_name_exactly_100_chars_accepted(self):
        """name at max_length=100 should be accepted."""
        name = "a" * 100
        req = AgentRegisterRequest(
            name=name,
            agent_type="seller",
            public_key="ssh-rsa AAAA_long_key_placeholder",
        )
        assert len(req.name) == 100

    def test_listing_title_exactly_255_chars_accepted(self):
        """title at max_length=255 should be accepted."""
        title = "T" * 255
        req = ListingCreateRequest(
            title=title,
            category="computation",
            content="data",
            price_usdc=1.0,
        )
        assert len(req.title) == 255

    def test_listing_title_256_chars_rejected(self):
        """title exceeding max_length=255 should raise ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            ListingCreateRequest(
                title="T" * 256,
                category="computation",
                content="data",
                price_usdc=1.0,
            )
        errors = exc_info.value.errors()
        assert any(e["loc"] == ("title",) for e in errors)

    def test_unicode_and_special_chars_in_string_fields(self):
        """Unicode characters (emoji, CJK, accented) should be valid in str fields."""
        req = AgentRegisterRequest(
            name="Agent-\u00e9l\u00e8ve-\u6d4b\u8bd5",
            agent_type="both",
            public_key="ssh-rsa AAAA_long_key_placeholder",
        )
        assert "\u00e9" in req.name  # accented e
        assert "\u6d4b" in req.name  # CJK character

        listing = ListingCreateRequest(
            title="Data \u2014 \u00bfSpecial? \u2603\ufe0f",
            category="api_response",
            content="\u4f60\u597d\u4e16\u754c",
            price_usdc=0.01,
        )
        assert "\u2014" in listing.title  # em dash
        assert listing.content == "\u4f60\u597d\u4e16\u754c"

    def test_price_at_exact_upper_bound_1000_accepted(self):
        """price_usdc at le=1000 boundary should be accepted."""
        req = ListingCreateRequest(
            title="Max Price",
            category="document_summary",
            content="data",
            price_usdc=1000,
        )
        assert req.price_usdc == 1000.0

        # Just over should fail
        with pytest.raises(ValidationError):
            ListingCreateRequest(
                title="Over Max",
                category="document_summary",
                content="data",
                price_usdc=1000.01,
            )
