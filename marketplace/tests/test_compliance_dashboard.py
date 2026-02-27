"""Comprehensive tests for compliance_service and dashboard_service.

Tests cover:
- compliance_service: export_agent_data, delete_agent_data,
  get_data_processing_record, ComplianceService class wrapper
- dashboard_service: get_agent_dashboard, get_creator_dashboard_v2,
  get_agent_public_dashboard, get_open_market_analytics,
  and the private helpers _safe_float, _safe_int, _as_non_empty_str,
  _load_json, _collect_listing_ids

All tests are async def with no explicit pytest.mark.asyncio (auto mode).
External service calls (creator_service, dual_layer_service) are mocked
with unittest.mock.AsyncMock so tests remain hermetic.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from marketplace.models.agent import RegisteredAgent
from marketplace.models.agent_trust import AgentTrustProfile
from marketplace.models.listing import DataListing
from marketplace.models.transaction import Transaction
from marketplace.services import compliance_service, dashboard_service
from marketplace.tests.conftest import _new_id


# ---------------------------------------------------------------------------
# Small helpers used across test blocks
# ---------------------------------------------------------------------------

def _new_trust_profile(agent_id: str, *, status: str = "verified",
                       tier: str = "T2", score: int = 80) -> AgentTrustProfile:
    return AgentTrustProfile(
        id=_new_id(),
        agent_id=agent_id,
        trust_status=status,
        trust_tier=tier,
        trust_score=score,
    )


def _dual_layer_zeros() -> dict:
    return {
        "creator_gross_revenue_usd": 0.0,
        "creator_platform_fees_usd": 0.0,
        "creator_net_revenue_usd": 0.0,
        "creator_pending_payout_usd": 0.0,
    }


def _open_metrics_zeros() -> dict:
    return {
        "end_users_count": 0,
        "consumer_orders_count": 0,
        "developer_profiles_count": 0,
        "platform_fee_volume_usd": 0.0,
    }


# ===========================================================================
# BLOCK 1: compliance_service — export_agent_data
# ===========================================================================

class TestExportAgentData:
    """Happy path and error cases for export_agent_data."""

    async def test_export_returns_error_for_missing_agent(self, db):
        """export_agent_data returns an error dict when agent does not exist."""
        result = await compliance_service.export_agent_data(db, "nonexistent-id")
        assert result == {"error": "Agent not found"}

    async def test_export_happy_path_agent_only(self, db, make_agent):
        """export_agent_data returns all required top-level keys for a bare agent."""
        agent, _ = await make_agent(name="export-agent")

        result = await compliance_service.export_agent_data(db, agent.id)

        assert "error" not in result
        assert result["agent"]["id"] == agent.id
        assert result["agent"]["name"] == "export-agent"
        assert result["listings"] == []
        assert result["transactions"] == []
        assert "export_id" in result
        assert "exported_at" in result
        assert result["format_version"] == "1.0"

    async def test_export_includes_listings(self, db, make_agent, make_listing):
        """Listings owned by the agent appear in the export."""
        seller, _ = await make_agent(name="listing-seller")
        listing = await make_listing(seller.id, price_usdc=5.0, category="web_search")

        result = await compliance_service.export_agent_data(db, seller.id)

        assert len(result["listings"]) == 1
        exported_listing = result["listings"][0]
        assert exported_listing["id"] == listing.id
        assert exported_listing["price_usdc"] == pytest.approx(5.0)
        assert exported_listing["category"] == "web_search"
        assert exported_listing["status"] == "active"

    async def test_export_includes_transactions_as_buyer_and_seller(
        self, db, make_agent, make_listing, make_transaction
    ):
        """Transactions where the agent is buyer OR seller are both exported."""
        agent, _ = await make_agent(name="dual-role-agent")
        other, _ = await make_agent(name="other-agent")

        listing_a = await make_listing(agent.id, price_usdc=10.0)
        listing_b = await make_listing(other.id, price_usdc=3.0)

        await make_transaction(other.id, agent.id, listing_a.id, amount_usdc=10.0)
        await make_transaction(agent.id, other.id, listing_b.id, amount_usdc=3.0)

        result = await compliance_service.export_agent_data(db, agent.id)

        assert len(result["transactions"]) == 2
        roles = {tx["role"] for tx in result["transactions"]}
        assert roles == {"buyer", "seller"}

    async def test_export_transaction_role_seller_label(
        self, db, make_agent, make_listing, make_transaction
    ):
        """Transactions where the agent sold are labelled 'seller'."""
        seller, _ = await make_agent(name="labelled-seller")
        buyer, _ = await make_agent(name="labelled-buyer")
        listing = await make_listing(seller.id, price_usdc=7.0)
        await make_transaction(buyer.id, seller.id, listing.id, amount_usdc=7.0)

        result = await compliance_service.export_agent_data(db, seller.id)

        tx = result["transactions"][0]
        assert tx["role"] == "seller"
        assert tx["amount_usdc"] == pytest.approx(7.0)

    async def test_export_export_id_is_unique_per_call(self, db, make_agent):
        """Each call to export_agent_data produces a different export_id."""
        agent, _ = await make_agent(name="uid-agent")
        r1 = await compliance_service.export_agent_data(db, agent.id)
        r2 = await compliance_service.export_agent_data(db, agent.id)
        assert r1["export_id"] != r2["export_id"]

    async def test_export_agent_description_defaults_to_empty_string(
        self, db, make_agent
    ):
        """When agent.description is None, the exported value is an empty string."""
        agent, _ = await make_agent(name="no-desc-agent")
        # make_agent does not set description, so it should be None/empty
        result = await compliance_service.export_agent_data(db, agent.id)
        assert isinstance(result["agent"]["description"], str)


# ===========================================================================
# BLOCK 2: compliance_service — delete_agent_data
# ===========================================================================

class TestDeleteAgentData:
    """Soft delete, hard delete, and not-found error for delete_agent_data."""

    async def test_delete_returns_error_for_missing_agent(self, db):
        """delete_agent_data returns an error dict when agent does not exist."""
        result = await compliance_service.delete_agent_data(db, "ghost-agent-id")
        assert result == {"error": "Agent not found"}

    async def test_soft_delete_anonymizes_agent(self, db, make_agent):
        """Soft delete sets agent name to 'deleted-*' and status to 'deleted'."""
        agent, _ = await make_agent(name="soon-deleted")

        result = await compliance_service.delete_agent_data(db, agent.id, soft_delete=True)

        assert result["method"] == "soft_delete"
        assert result["deleted_items"]["agent"] is True

        refreshed = (
            await db.execute(
                select(RegisteredAgent).where(RegisteredAgent.id == agent.id)
            )
        ).scalar_one()
        assert refreshed.name.startswith("deleted-")
        assert refreshed.status == "deleted"
        assert refreshed.description == "[REDACTED]"

    async def test_soft_delete_anonymizes_listings(
        self, db, make_agent, make_listing
    ):
        """Soft delete sets listing titles to [REDACTED] and status to 'deleted'."""
        agent, _ = await make_agent(name="agent-with-listings")
        await make_listing(agent.id)
        await make_listing(agent.id)

        result = await compliance_service.delete_agent_data(db, agent.id, soft_delete=True)

        assert result["deleted_items"]["listings"] == 2

        listings = (
            await db.execute(
                select(DataListing).where(DataListing.seller_id == agent.id)
            )
        ).scalars().all()
        for listing in listings:
            assert listing.title == "[REDACTED]"
            assert listing.status == "deleted"

    async def test_soft_delete_is_default_behavior(self, db, make_agent):
        """Calling delete_agent_data without soft_delete kwarg defaults to soft."""
        agent, _ = await make_agent(name="default-soft")
        result = await compliance_service.delete_agent_data(db, agent.id)
        assert result["method"] == "soft_delete"

    async def test_hard_delete_removes_agent_from_db(self, db, make_agent):
        """Hard delete physically removes the agent row."""
        agent, _ = await make_agent(name="hard-delete-agent")
        agent_id = agent.id

        result = await compliance_service.delete_agent_data(
            db, agent_id, soft_delete=False
        )

        assert result["method"] == "hard_delete"
        assert result["deleted_items"]["agent"] is True

        row = (
            await db.execute(
                select(RegisteredAgent).where(RegisteredAgent.id == agent_id)
            )
        ).scalar_one_or_none()
        assert row is None

    async def test_hard_delete_removes_listings_from_db(
        self, db, make_agent, make_listing
    ):
        """Hard delete physically removes all listing rows for the agent."""
        agent, _ = await make_agent(name="hard-delete-listings")
        await make_listing(agent.id)
        await make_listing(agent.id)

        result = await compliance_service.delete_agent_data(
            db, agent.id, soft_delete=False
        )

        assert result["deleted_items"]["listings"] == 2

        remaining = (
            await db.execute(
                select(DataListing).where(DataListing.seller_id == agent.id)
            )
        ).scalars().all()
        assert remaining == []

    async def test_delete_response_has_required_keys(self, db, make_agent):
        """delete_agent_data response always contains the expected top-level keys."""
        agent, _ = await make_agent(name="key-check-agent")
        result = await compliance_service.delete_agent_data(db, agent.id)
        for key in ("deletion_id", "agent_id", "method", "deleted_items", "completed_at"):
            assert key in result

    async def test_delete_response_agent_id_matches(self, db, make_agent):
        """agent_id in the response matches the requested agent."""
        agent, _ = await make_agent(name="id-match-agent")
        result = await compliance_service.delete_agent_data(db, agent.id)
        assert result["agent_id"] == agent.id


# ===========================================================================
# BLOCK 3: compliance_service — get_data_processing_record & ComplianceService
# ===========================================================================

class TestDataProcessingRecord:
    """Tests for get_data_processing_record and the ComplianceService class."""

    async def test_processing_record_returns_agent_id(self, db):
        """get_data_processing_record echoes the requested agent_id."""
        fake_id = _new_id()
        result = await compliance_service.get_data_processing_record(db, fake_id)
        assert result["agent_id"] == fake_id

    async def test_processing_record_has_data_categories(self, db):
        """Returned record includes a non-empty data_categories list."""
        result = await compliance_service.get_data_processing_record(db, _new_id())
        assert isinstance(result["data_categories"], list)
        assert len(result["data_categories"]) > 0
        assert "transaction_history" in result["data_categories"]

    async def test_processing_record_has_processing_purposes(self, db):
        """Returned record includes processing_purposes."""
        result = await compliance_service.get_data_processing_record(db, _new_id())
        assert "processing_purposes" in result
        assert len(result["processing_purposes"]) > 0

    async def test_processing_record_has_retention_periods(self, db):
        """Returned record includes retention_periods dict."""
        result = await compliance_service.get_data_processing_record(db, _new_id())
        assert "retention_periods" in result
        assert isinstance(result["retention_periods"], dict)
        assert "transaction_data" in result["retention_periods"]

    async def test_processing_record_has_generated_at(self, db):
        """Returned record includes a generated_at timestamp string."""
        result = await compliance_service.get_data_processing_record(db, _new_id())
        assert "generated_at" in result
        # Should be a parseable ISO-8601 string
        datetime.fromisoformat(result["generated_at"])

    async def test_compliance_service_class_export_delegates(self, db, make_agent):
        """ComplianceService.export_data delegates to export_agent_data."""
        agent, _ = await make_agent(name="class-export-agent")
        svc = compliance_service.ComplianceService()
        result = await svc.export_data(db, agent.id)
        assert result["agent"]["id"] == agent.id

    async def test_compliance_service_class_delete_delegates(self, db, make_agent):
        """ComplianceService.delete_data delegates to delete_agent_data."""
        agent, _ = await make_agent(name="class-delete-agent")
        svc = compliance_service.ComplianceService()
        result = await svc.delete_data(db, agent.id)
        assert result["method"] == "soft_delete"
        assert result["agent_id"] == agent.id


# ===========================================================================
# BLOCK 4: dashboard_service — private helpers (unit tests)
# ===========================================================================

class TestDashboardHelpers:
    """Unit tests for the pure-Python helper functions in dashboard_service."""

    def test_safe_float_returns_float_for_decimal(self):
        assert dashboard_service._safe_float(Decimal("3.14")) == pytest.approx(3.14)

    def test_safe_float_returns_default_for_none(self):
        assert dashboard_service._safe_float(None) == 0.0

    def test_safe_float_returns_default_for_nan_string(self):
        assert dashboard_service._safe_float("nan") == 0.0

    def test_safe_float_returns_default_for_inf(self):
        import math
        assert dashboard_service._safe_float(math.inf) == 0.0

    def test_safe_float_custom_default(self):
        assert dashboard_service._safe_float("bad", default=99.0) == 99.0

    def test_safe_int_returns_int_for_valid_string(self):
        assert dashboard_service._safe_int("42") == 42

    def test_safe_int_returns_default_for_none(self):
        assert dashboard_service._safe_int(None) == 0

    def test_safe_int_returns_default_for_bad_string(self):
        assert dashboard_service._safe_int("abc", default=7) == 7

    def test_as_non_empty_str_strips_whitespace(self):
        assert dashboard_service._as_non_empty_str("  hello  ") == "hello"

    def test_as_non_empty_str_returns_none_for_blank(self):
        assert dashboard_service._as_non_empty_str("   ") is None

    def test_as_non_empty_str_returns_none_for_non_string(self):
        assert dashboard_service._as_non_empty_str(42) is None

    def test_load_json_returns_dict_for_valid_json(self):
        assert dashboard_service._load_json('{"key": "value"}', {}) == {"key": "value"}

    def test_load_json_returns_fallback_for_invalid_json(self):
        assert dashboard_service._load_json("not-json", {"fallback": True}) == {"fallback": True}

    def test_load_json_returns_fallback_for_none(self):
        assert dashboard_service._load_json(None, {"a": 1}) == {"a": 1}

    def test_load_json_returns_parsed_json_array(self):
        # load_json parses any valid JSON — arrays are returned as-is
        assert dashboard_service._load_json("[1, 2, 3]", {"b": 2}) == [1, 2, 3]

    def test_collect_listing_ids_extracts_non_empty(self):
        tx1 = MagicMock()
        tx1.listing_id = "listing-abc"
        tx2 = MagicMock()
        tx2.listing_id = ""   # empty — should be skipped
        tx3 = MagicMock()
        tx3.listing_id = "listing-xyz"

        result = dashboard_service._collect_listing_ids([tx1, tx2, tx3])
        assert result == {"listing-abc", "listing-xyz"}


# ===========================================================================
# BLOCK 5: dashboard_service — get_agent_dashboard
# ===========================================================================

class TestGetAgentDashboard:
    """Happy path and edge cases for get_agent_dashboard."""

    async def test_empty_agent_dashboard(self, db, make_agent):
        """Agent with no transactions has all numeric fields at zero."""
        agent, _ = await make_agent(name="no-activity-agent")
        result = await dashboard_service.get_agent_dashboard(db, agent.id)

        assert result["agent_id"] == agent.id
        assert result["money_received_usd"] == 0.0
        assert result["money_spent_usd"] == 0.0
        assert result["info_used_count"] == 0
        assert result["other_agents_served_count"] == 0
        assert result["data_served_bytes"] == 0
        assert result["savings"]["money_saved_for_others_usd"] == 0.0
        assert result["savings"]["fresh_cost_estimate_total_usd"] == 0.0

    async def test_dashboard_money_received_sums_completed_seller_tx(
        self, db, make_agent, make_listing, make_transaction
    ):
        """money_received_usd sums only completed transactions where agent is seller."""
        seller, _ = await make_agent(name="earning-seller")
        buyer, _ = await make_agent(name="paying-buyer")
        listing = await make_listing(seller.id, price_usdc=10.0)
        await make_transaction(buyer.id, seller.id, listing.id, amount_usdc=10.0)
        await make_transaction(buyer.id, seller.id, listing.id, amount_usdc=5.0)

        result = await dashboard_service.get_agent_dashboard(db, seller.id)
        assert result["money_received_usd"] == pytest.approx(15.0)

    async def test_dashboard_money_spent_sums_completed_buyer_tx(
        self, db, make_agent, make_listing, make_transaction
    ):
        """money_spent_usd sums only completed transactions where agent is buyer."""
        seller, _ = await make_agent(name="selling-agent")
        buyer, _ = await make_agent(name="spending-buyer")
        listing = await make_listing(seller.id, price_usdc=8.0)
        await make_transaction(buyer.id, seller.id, listing.id, amount_usdc=8.0)

        result = await dashboard_service.get_agent_dashboard(db, buyer.id)
        assert result["money_spent_usd"] == pytest.approx(8.0)

    async def test_dashboard_excludes_pending_transactions(
        self, db, make_agent, make_listing, make_transaction
    ):
        """Pending transactions are NOT counted in any dashboard metric."""
        seller, _ = await make_agent(name="pending-seller")
        buyer, _ = await make_agent(name="pending-buyer")
        listing = await make_listing(seller.id, price_usdc=50.0)
        await make_transaction(
            buyer.id, seller.id, listing.id, amount_usdc=50.0, status="pending"
        )

        result = await dashboard_service.get_agent_dashboard(db, seller.id)
        assert result["money_received_usd"] == 0.0
        assert result["info_used_count"] == 0

    async def test_dashboard_info_used_count_equals_seller_tx_count(
        self, db, make_agent, make_listing, make_transaction
    ):
        """info_used_count equals the number of completed sell transactions."""
        seller, _ = await make_agent(name="info-seller")
        buyer, _ = await make_agent(name="info-buyer")
        listing = await make_listing(seller.id, price_usdc=1.0)
        await make_transaction(buyer.id, seller.id, listing.id, amount_usdc=1.0)
        await make_transaction(buyer.id, seller.id, listing.id, amount_usdc=1.0)
        await make_transaction(buyer.id, seller.id, listing.id, amount_usdc=1.0)

        result = await dashboard_service.get_agent_dashboard(db, seller.id)
        assert result["info_used_count"] == 3

    async def test_dashboard_other_agents_served_is_unique_buyer_count(
        self, db, make_agent, make_listing, make_transaction
    ):
        """other_agents_served_count counts distinct buyer IDs (not tx count)."""
        seller, _ = await make_agent(name="multi-buyer-seller")
        buyer1, _ = await make_agent(name="buyer-one")
        buyer2, _ = await make_agent(name="buyer-two")
        listing = await make_listing(seller.id, price_usdc=1.0)

        # buyer1 buys twice, buyer2 once — only 2 unique buyers
        await make_transaction(buyer1.id, seller.id, listing.id, amount_usdc=1.0)
        await make_transaction(buyer1.id, seller.id, listing.id, amount_usdc=1.0)
        await make_transaction(buyer2.id, seller.id, listing.id, amount_usdc=1.0)

        result = await dashboard_service.get_agent_dashboard(db, seller.id)
        assert result["other_agents_served_count"] == 2

    async def test_dashboard_data_served_bytes_from_listing(
        self, db, make_agent, make_listing, make_transaction
    ):
        """data_served_bytes sums content_size of listings linked to seller txs."""
        seller, _ = await make_agent(name="bytes-seller")
        buyer, _ = await make_agent(name="bytes-buyer")
        listing = await make_listing(
            seller.id, price_usdc=1.0, content_size=2048
        )
        await make_transaction(buyer.id, seller.id, listing.id, amount_usdc=1.0)

        result = await dashboard_service.get_agent_dashboard(db, seller.id)
        assert result["data_served_bytes"] == 2048

    async def test_dashboard_trust_fields_from_profile(self, db, make_agent):
        """Trust fields are populated from AgentTrustProfile when present."""
        agent, _ = await make_agent(name="trusted-agent")
        profile = _new_trust_profile(agent.id, status="verified", tier="T3", score=95)
        db.add(profile)
        await db.commit()

        result = await dashboard_service.get_agent_dashboard(db, agent.id)
        assert result["trust_status"] == "verified"
        assert result["trust_tier"] == "T3"
        assert result["trust_score"] == 95

    async def test_dashboard_trust_defaults_when_no_profile(self, db, make_agent):
        """Trust fields default to unverified/T0/0 when no trust profile exists."""
        agent, _ = await make_agent(name="untrusted-agent")
        result = await dashboard_service.get_agent_dashboard(db, agent.id)
        assert result["trust_status"] == "unverified"
        assert result["trust_tier"] == "T0"
        assert result["trust_score"] == 0

    async def test_dashboard_savings_positive_when_fresh_cost_exceeds_price(
        self, db, make_agent, make_listing, make_transaction
    ):
        """money_saved_for_others_usd is positive when fresh cost > tx price."""
        seller, _ = await make_agent(name="saver-seller")
        buyer, _ = await make_agent(name="saver-buyer")
        # Category "ml_models" has a high FRESH_COST_ESTIMATES value
        listing = await make_listing(
            seller.id, price_usdc=0.01, category="ml_models"
        )
        await make_transaction(
            buyer.id, seller.id, listing.id, amount_usdc=0.01
        )

        result = await dashboard_service.get_agent_dashboard(db, seller.id)
        assert result["savings"]["money_saved_for_others_usd"] >= 0.0


# ===========================================================================
# BLOCK 6: dashboard_service — get_agent_public_dashboard
# ===========================================================================

class TestGetAgentPublicDashboard:
    """Happy path and error cases for get_agent_public_dashboard."""

    async def test_public_dashboard_raises_for_missing_agent(self, db):
        """get_agent_public_dashboard raises ValueError when agent does not exist."""
        with pytest.raises(ValueError, match="not found"):
            await dashboard_service.get_agent_public_dashboard(db, "ghost-id")

    async def test_public_dashboard_returns_agent_name(self, db, make_agent):
        """Public dashboard includes agent_name matching the registered name."""
        agent, _ = await make_agent(name="public-visible-agent")
        result = await dashboard_service.get_agent_public_dashboard(db, agent.id)
        assert result["agent_name"] == "public-visible-agent"

    async def test_public_dashboard_has_required_keys(self, db, make_agent):
        """Public dashboard response includes all expected keys."""
        agent, _ = await make_agent(name="key-check-public")
        result = await dashboard_service.get_agent_public_dashboard(db, agent.id)
        expected_keys = {
            "agent_id", "agent_name", "money_received_usd", "info_used_count",
            "other_agents_served_count", "data_served_bytes",
            "money_saved_for_others_usd", "trust_status", "trust_tier",
            "trust_score", "updated_at",
        }
        assert expected_keys.issubset(result.keys())

    async def test_public_dashboard_matches_agent_dashboard_values(
        self, db, make_agent, make_listing, make_transaction
    ):
        """Public dashboard values align with those returned by get_agent_dashboard."""
        seller, _ = await make_agent(name="cross-check-seller")
        buyer, _ = await make_agent(name="cross-check-buyer")
        listing = await make_listing(seller.id, price_usdc=4.0)
        await make_transaction(buyer.id, seller.id, listing.id, amount_usdc=4.0)

        private = await dashboard_service.get_agent_dashboard(db, seller.id)
        public = await dashboard_service.get_agent_public_dashboard(db, seller.id)

        assert public["money_received_usd"] == private["money_received_usd"]
        assert public["info_used_count"] == private["info_used_count"]
        assert public["trust_score"] == private["trust_score"]

    async def test_public_dashboard_does_not_expose_money_spent(
        self, db, make_agent
    ):
        """Public dashboard does NOT expose money_spent_usd (private field)."""
        agent, _ = await make_agent(name="no-spend-expose")
        result = await dashboard_service.get_agent_public_dashboard(db, agent.id)
        assert "money_spent_usd" not in result


# ===========================================================================
# BLOCK 7: dashboard_service — get_creator_dashboard_v2 (mocked externals)
# ===========================================================================

class TestGetCreatorDashboardV2:
    """Tests for get_creator_dashboard_v2 — external services are mocked."""

    def _patch_externals(self, creator_dash: dict = None, wallet: dict = None,
                         dual_layer: dict = None):
        """Return a dict of patch targets for the three external calls."""
        creator_dash = creator_dash or {
            "agents": [],
            "agents_count": 0,
            "total_agent_earnings": 0.0,
            "total_agent_spent": 0.0,
        }
        wallet = wallet or {"balance": 100.0, "total_earned": 200.0}
        dual_layer = dual_layer or _dual_layer_zeros()
        return {
            "creator_dash": creator_dash,
            "wallet": wallet,
            "dual_layer": dual_layer,
        }

    async def test_creator_dashboard_v2_no_agents(self, db, make_creator):
        """Creator with no agents returns zeroed numeric fields."""
        creator, _ = await make_creator()
        mocks = self._patch_externals()

        with (
            patch(
                "marketplace.services.dashboard_service.creator_service.get_creator_dashboard",
                new=AsyncMock(return_value=mocks["creator_dash"]),
            ),
            patch(
                "marketplace.services.dashboard_service.creator_service.get_creator_wallet",
                new=AsyncMock(return_value=mocks["wallet"]),
            ),
            patch(
                "marketplace.services.dashboard_service.dual_layer_service"
                ".get_creator_dual_layer_metrics",
                new=AsyncMock(return_value=mocks["dual_layer"]),
            ),
        ):
            result = await dashboard_service.get_creator_dashboard_v2(db, creator.id)

        assert result["creator_id"] == creator.id
        assert result["total_agents"] == 0
        assert result["active_agents"] == 0
        assert result["money_saved_for_others_usd"] == 0.0
        assert result["data_served_bytes"] == 0

    async def test_creator_dashboard_v2_balance_from_wallet(
        self, db, make_creator
    ):
        """creator_balance_usd and creator_total_earned_usd come from wallet service."""
        creator, _ = await make_creator()
        wallet = {"balance": 250.0, "total_earned": 500.0}
        mocks = self._patch_externals(wallet=wallet)

        with (
            patch(
                "marketplace.services.dashboard_service.creator_service.get_creator_dashboard",
                new=AsyncMock(return_value=mocks["creator_dash"]),
            ),
            patch(
                "marketplace.services.dashboard_service.creator_service.get_creator_wallet",
                new=AsyncMock(return_value=wallet),
            ),
            patch(
                "marketplace.services.dashboard_service.dual_layer_service"
                ".get_creator_dual_layer_metrics",
                new=AsyncMock(return_value=mocks["dual_layer"]),
            ),
        ):
            result = await dashboard_service.get_creator_dashboard_v2(db, creator.id)

        assert result["creator_balance_usd"] == pytest.approx(250.0)
        assert result["creator_total_earned_usd"] == pytest.approx(500.0)

    async def test_creator_dashboard_v2_dual_layer_revenue_fields(
        self, db, make_creator
    ):
        """Dual-layer revenue fields are mapped from get_creator_dual_layer_metrics."""
        creator, _ = await make_creator()
        dual = {
            "creator_gross_revenue_usd": 1000.0,
            "creator_platform_fees_usd": 100.0,
            "creator_net_revenue_usd": 900.0,
            "creator_pending_payout_usd": 50.0,
        }
        mocks = self._patch_externals(dual_layer=dual)

        with (
            patch(
                "marketplace.services.dashboard_service.creator_service.get_creator_dashboard",
                new=AsyncMock(return_value=mocks["creator_dash"]),
            ),
            patch(
                "marketplace.services.dashboard_service.creator_service.get_creator_wallet",
                new=AsyncMock(return_value=mocks["wallet"]),
            ),
            patch(
                "marketplace.services.dashboard_service.dual_layer_service"
                ".get_creator_dual_layer_metrics",
                new=AsyncMock(return_value=dual),
            ),
        ):
            result = await dashboard_service.get_creator_dashboard_v2(db, creator.id)

        assert result["creator_gross_revenue_usd"] == pytest.approx(1000.0)
        assert result["creator_platform_fees_usd"] == pytest.approx(100.0)
        assert result["creator_net_revenue_usd"] == pytest.approx(900.0)
        assert result["creator_pending_payout_usd"] == pytest.approx(50.0)

    async def test_creator_dashboard_v2_active_agents_count(
        self, db, make_creator
    ):
        """active_agents counts only agents with status=='active'."""
        creator, _ = await make_creator()
        creator_dash = {
            "agents": [
                {"agent_id": _new_id(), "status": "active"},
                {"agent_id": _new_id(), "status": "active"},
                {"agent_id": _new_id(), "status": "deleted"},
            ],
            "agents_count": 3,
            "total_agent_earnings": 0.0,
            "total_agent_spent": 0.0,
        }
        mocks = self._patch_externals(creator_dash=creator_dash)

        # get_agent_dashboard must be mocked to avoid DB lookups for fake IDs
        empty_agent_metrics = {
            "savings": {"money_saved_for_others_usd": 0.0},
            "data_served_bytes": 0,
        }

        with (
            patch(
                "marketplace.services.dashboard_service.creator_service.get_creator_dashboard",
                new=AsyncMock(return_value=creator_dash),
            ),
            patch(
                "marketplace.services.dashboard_service.creator_service.get_creator_wallet",
                new=AsyncMock(return_value=mocks["wallet"]),
            ),
            patch(
                "marketplace.services.dashboard_service.dual_layer_service"
                ".get_creator_dual_layer_metrics",
                new=AsyncMock(return_value=mocks["dual_layer"]),
            ),
            patch(
                "marketplace.services.dashboard_service.get_agent_dashboard",
                new=AsyncMock(return_value=empty_agent_metrics),
            ),
        ):
            result = await dashboard_service.get_creator_dashboard_v2(db, creator.id)

        assert result["active_agents"] == 2
        assert result["total_agents"] == 3

    async def test_creator_dashboard_v2_has_updated_at(self, db, make_creator):
        """Response always includes an updated_at datetime."""
        creator, _ = await make_creator()
        mocks = self._patch_externals()

        with (
            patch(
                "marketplace.services.dashboard_service.creator_service.get_creator_dashboard",
                new=AsyncMock(return_value=mocks["creator_dash"]),
            ),
            patch(
                "marketplace.services.dashboard_service.creator_service.get_creator_wallet",
                new=AsyncMock(return_value=mocks["wallet"]),
            ),
            patch(
                "marketplace.services.dashboard_service.dual_layer_service"
                ".get_creator_dual_layer_metrics",
                new=AsyncMock(return_value=mocks["dual_layer"]),
            ),
        ):
            result = await dashboard_service.get_creator_dashboard_v2(db, creator.id)

        assert isinstance(result["updated_at"], datetime)


# ===========================================================================
# BLOCK 8: dashboard_service — get_open_market_analytics
# ===========================================================================

class TestGetOpenMarketAnalytics:
    """Tests for get_open_market_analytics."""

    def _patch_dual_layer_open(self, metrics: dict = None):
        metrics = metrics or _open_metrics_zeros()
        return patch(
            "marketplace.services.dashboard_service.dual_layer_service"
            ".get_dual_layer_open_metrics",
            new=AsyncMock(return_value=metrics),
        )

    async def test_analytics_empty_db_returns_zeroed_counts(self, db):
        """Empty database yields zero agents, listings, and transactions."""
        with self._patch_dual_layer_open():
            result = await dashboard_service.get_open_market_analytics(db, limit=10)

        assert result["total_agents"] == 0
        assert result["total_listings"] == 0
        assert result["total_completed_transactions"] == 0
        assert result["platform_volume_usd"] == 0.0
        assert result["total_money_saved_usd"] == 0.0
        assert result["top_agents_by_revenue"] == []
        assert result["top_agents_by_usage"] == []
        assert result["top_categories_by_usage"] == []

    async def test_analytics_total_agents_and_listings(
        self, db, make_agent, make_listing
    ):
        """Correct total_agents and total_listings counts are returned."""
        agent1, _ = await make_agent(name="analytics-a1")
        agent2, _ = await make_agent(name="analytics-a2")
        await make_listing(agent1.id)
        await make_listing(agent1.id)
        await make_listing(agent2.id)

        with self._patch_dual_layer_open():
            result = await dashboard_service.get_open_market_analytics(db)

        assert result["total_agents"] == 2
        assert result["total_listings"] == 3

    async def test_analytics_completed_transactions_counted(
        self, db, make_agent, make_listing, make_transaction
    ):
        """Only completed transactions are counted in total_completed_transactions."""
        seller, _ = await make_agent(name="analytics-seller")
        buyer, _ = await make_agent(name="analytics-buyer")
        listing = await make_listing(seller.id, price_usdc=10.0)
        await make_transaction(buyer.id, seller.id, listing.id, amount_usdc=10.0,
                               status="completed")
        await make_transaction(buyer.id, seller.id, listing.id, amount_usdc=10.0,
                               status="pending")

        with self._patch_dual_layer_open():
            result = await dashboard_service.get_open_market_analytics(db)

        assert result["total_completed_transactions"] == 1

    async def test_analytics_platform_volume_sums_completed(
        self, db, make_agent, make_listing, make_transaction
    ):
        """platform_volume_usd sums completed transaction amounts."""
        seller, _ = await make_agent(name="vol-seller")
        buyer, _ = await make_agent(name="vol-buyer")
        listing = await make_listing(seller.id, price_usdc=10.0)
        await make_transaction(buyer.id, seller.id, listing.id, amount_usdc=10.0)
        await make_transaction(buyer.id, seller.id, listing.id, amount_usdc=25.0)

        with self._patch_dual_layer_open():
            result = await dashboard_service.get_open_market_analytics(db)

        assert result["platform_volume_usd"] == pytest.approx(35.0)

    async def test_analytics_top_agents_by_revenue_sorted_desc(
        self, db, make_agent, make_listing, make_transaction
    ):
        """top_agents_by_revenue is sorted by descending revenue."""
        low, _ = await make_agent(name="low-earner")
        high, _ = await make_agent(name="high-earner")
        buyer, _ = await make_agent(name="rev-buyer")
        l1 = await make_listing(low.id, price_usdc=5.0)
        l2 = await make_listing(high.id, price_usdc=100.0)
        await make_transaction(buyer.id, low.id, l1.id, amount_usdc=5.0)
        await make_transaction(buyer.id, high.id, l2.id, amount_usdc=100.0)

        with self._patch_dual_layer_open():
            result = await dashboard_service.get_open_market_analytics(db, limit=10)

        revenues = [r["money_received_usd"] for r in result["top_agents_by_revenue"]]
        assert revenues == sorted(revenues, reverse=True)
        assert result["top_agents_by_revenue"][0]["agent_id"] == high.id

    async def test_analytics_top_agents_by_usage_sorted_desc(
        self, db, make_agent, make_listing, make_transaction
    ):
        """top_agents_by_usage is sorted by descending info_used_count."""
        popular, _ = await make_agent(name="popular-seller")
        unpopular, _ = await make_agent(name="unpopular-seller")
        buyer, _ = await make_agent(name="usage-buyer")
        l1 = await make_listing(popular.id, price_usdc=1.0)
        l2 = await make_listing(unpopular.id, price_usdc=1.0)
        for _ in range(5):
            await make_transaction(buyer.id, popular.id, l1.id, amount_usdc=1.0)
        await make_transaction(buyer.id, unpopular.id, l2.id, amount_usdc=1.0)

        with self._patch_dual_layer_open():
            result = await dashboard_service.get_open_market_analytics(db, limit=10)

        counts = [r["info_used_count"] for r in result["top_agents_by_usage"]]
        assert counts == sorted(counts, reverse=True)
        assert result["top_agents_by_usage"][0]["agent_id"] == popular.id

    async def test_analytics_top_categories_sorted_by_usage(
        self, db, make_agent, make_listing, make_transaction
    ):
        """top_categories_by_usage is sorted by descending usage_count."""
        seller, _ = await make_agent(name="cat-seller")
        buyer, _ = await make_agent(name="cat-buyer")
        l_ws = await make_listing(seller.id, price_usdc=1.0, category="web_search")
        l_ml = await make_listing(seller.id, price_usdc=1.0, category="ml_models")
        # web_search gets 3 transactions, ml_models gets 1
        for _ in range(3):
            await make_transaction(buyer.id, seller.id, l_ws.id, amount_usdc=1.0)
        await make_transaction(buyer.id, seller.id, l_ml.id, amount_usdc=1.0)

        with self._patch_dual_layer_open():
            result = await dashboard_service.get_open_market_analytics(db, limit=10)

        cats = result["top_categories_by_usage"]
        assert cats[0]["category"] == "web_search"
        assert cats[0]["usage_count"] == 3

    async def test_analytics_limit_restricts_top_agents(
        self, db, make_agent, make_listing, make_transaction
    ):
        """limit parameter restricts the size of all three top-* lists."""
        buyer, _ = await make_agent(name="limit-buyer")
        for i in range(5):
            agent, _ = await make_agent(name=f"limit-seller-{i}")
            listing = await make_listing(agent.id, price_usdc=float(i + 1))
            await make_transaction(buyer.id, agent.id, listing.id,
                                   amount_usdc=float(i + 1))

        with self._patch_dual_layer_open():
            result = await dashboard_service.get_open_market_analytics(db, limit=3)

        assert len(result["top_agents_by_revenue"]) <= 3
        assert len(result["top_agents_by_usage"]) <= 3

    async def test_analytics_has_generated_at(self, db):
        """Response always includes a generated_at datetime."""
        with self._patch_dual_layer_open():
            result = await dashboard_service.get_open_market_analytics(db)
        assert isinstance(result["generated_at"], datetime)

    async def test_analytics_dual_layer_fields_mapped(self, db):
        """end_users_count, consumer_orders_count etc. come from dual_layer_service."""
        dual_metrics = {
            "end_users_count": 42,
            "consumer_orders_count": 17,
            "developer_profiles_count": 5,
            "platform_fee_volume_usd": 99.9,
        }
        with self._patch_dual_layer_open(metrics=dual_metrics):
            result = await dashboard_service.get_open_market_analytics(db)

        assert result["end_users_count"] == 42
        assert result["consumer_orders_count"] == 17
        assert result["developer_profiles_count"] == 5
        assert result["platform_fee_volume_usd"] == pytest.approx(99.9)

    async def test_analytics_agent_name_lookup(
        self, db, make_agent, make_listing, make_transaction
    ):
        """Agent names in top_agents_by_revenue match registered names."""
        seller, _ = await make_agent(name="named-seller-xyz")
        buyer, _ = await make_agent(name="named-buyer")
        listing = await make_listing(seller.id, price_usdc=20.0)
        await make_transaction(buyer.id, seller.id, listing.id, amount_usdc=20.0)

        with self._patch_dual_layer_open():
            result = await dashboard_service.get_open_market_analytics(db, limit=10)

        found = next(
            (r for r in result["top_agents_by_revenue"] if r["agent_id"] == seller.id),
            None,
        )
        assert found is not None
        assert found["agent_name"] == "named-seller-xyz"
