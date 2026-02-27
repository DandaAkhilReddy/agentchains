"""Unit tests for the admin_dashboard_service module.

30 tests across 6 describe blocks:
  - get_admin_overview (1-6)
  - get_admin_finance (7-12)
  - get_admin_usage (13-18)
  - list_admin_agents (19-23)
  - list_security_events (24-27)
  - list_pending_payouts (28-30)

Written as direct service-layer tests using the in-memory SQLite backend.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from decimal import Decimal

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from marketplace.models.audit_log import AuditLog
from marketplace.models.dual_layer import ConsumerOrder, PlatformFee
from marketplace.models.listing import DataListing
from marketplace.models.redemption import RedemptionRequest
from marketplace.services.admin_dashboard_service import (
    get_admin_finance,
    get_admin_overview,
    get_admin_usage,
    list_admin_agents,
    list_pending_payouts,
    list_security_events,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _uid() -> str:
    return str(uuid.uuid4())


async def _create_audit_log(
    db: AsyncSession,
    event_type: str = "agent.registered",
    severity: str = "info",
    agent_id: str | None = None,
    details: dict | None = None,
) -> AuditLog:
    """Insert an AuditLog entry directly."""
    log = AuditLog(
        id=_uid(),
        event_type=event_type,
        severity=severity,
        agent_id=agent_id or _uid(),
        details=json.dumps(details or {"action": "test"}),
    )
    db.add(log)
    await db.commit()
    await db.refresh(log)
    return log


async def _create_redemption_request(
    db: AsyncSession,
    creator_id: str,
    amount_usd: float = 10.0,
    status: str = "pending",
    redemption_type: str = "bank_withdrawal",
) -> RedemptionRequest:
    """Insert a RedemptionRequest directly."""
    req = RedemptionRequest(
        id=_uid(),
        creator_id=creator_id,
        amount_usd=Decimal(str(amount_usd)),
        status=status,
        redemption_type=redemption_type,
        currency="USD",
    )
    db.add(req)
    await db.commit()
    await db.refresh(req)
    return req


# ===========================================================================
# 1. GET_ADMIN_OVERVIEW (tests 1-6)
# ===========================================================================


class TestGetAdminOverview:
    """Verify admin overview aggregation."""

    async def test_empty_database_returns_zeros(self, db: AsyncSession):
        """1. Overview with empty database returns all zero counters."""
        result = await get_admin_overview(db)
        assert result["total_agents"] == 0
        assert result["active_agents"] == 0
        assert result["total_listings"] == 0
        assert result["active_listings"] == 0
        assert result["total_transactions"] == 0
        assert result["completed_transactions"] == 0
        assert result["platform_volume_usd"] == 0.0
        assert result["trust_weighted_revenue_usd"] == 0.0

    async def test_overview_counts_agents(self, db: AsyncSession, make_agent):
        """2. Overview counts total and active agents."""
        await make_agent(name="active-1")
        await make_agent(name="active-2")
        result = await get_admin_overview(db)
        assert result["total_agents"] == 2
        assert result["active_agents"] == 2

    async def test_overview_counts_listings(
        self, db: AsyncSession, make_agent, make_listing
    ):
        """3. Overview counts total and active listings."""
        agent, _ = await make_agent()
        await make_listing(agent.id, title="Active Listing")
        await make_listing(agent.id, title="Suspended", status="suspended")
        result = await get_admin_overview(db)
        assert result["total_listings"] == 2
        assert result["active_listings"] == 1

    async def test_overview_counts_transactions(
        self, db: AsyncSession, make_agent, make_listing, make_transaction
    ):
        """4. Overview counts total and completed transactions."""
        seller, _ = await make_agent(name="seller")
        buyer, _ = await make_agent(name="buyer")
        listing = await make_listing(seller.id, price_usdc=5.0)

        await make_transaction(buyer.id, seller.id, listing.id, amount_usdc=5.0)
        await make_transaction(buyer.id, seller.id, listing.id, amount_usdc=3.0, status="pending")

        result = await get_admin_overview(db)
        assert result["total_transactions"] == 2
        assert result["completed_transactions"] == 1

    async def test_overview_platform_volume(
        self, db: AsyncSession, make_agent, make_listing, make_transaction
    ):
        """5. Overview sums completed transaction amounts as platform volume."""
        seller, _ = await make_agent(name="seller")
        buyer, _ = await make_agent(name="buyer")
        listing = await make_listing(seller.id, price_usdc=10.0)

        await make_transaction(buyer.id, seller.id, listing.id, amount_usdc=10.0)
        await make_transaction(buyer.id, seller.id, listing.id, amount_usdc=5.0)

        result = await get_admin_overview(db)
        assert result["platform_volume_usd"] == 15.0

    async def test_overview_trust_weighted_revenue(
        self, db: AsyncSession, make_agent, make_listing, make_transaction
    ):
        """5b. Overview computes trust-weighted revenue based on listing trust_status."""
        seller, _ = await make_agent(name="seller")
        buyer, _ = await make_agent(name="buyer")
        listing = await make_listing(seller.id, price_usdc=10.0)

        # Set listing trust_status to verified_secure_data (weight 1.0)
        listing.trust_status = "verified_secure_data"
        await db.commit()

        await make_transaction(buyer.id, seller.id, listing.id, amount_usdc=10.0)

        result = await get_admin_overview(db)
        # verified_secure_data has weight 1.0, so trust_weighted == 10.0
        assert result["trust_weighted_revenue_usd"] == 10.0

    async def test_overview_has_environment_and_timestamp(self, db: AsyncSession):
        """6. Overview includes environment and updated_at fields."""
        result = await get_admin_overview(db)
        assert "environment" in result
        assert "updated_at" in result
        assert isinstance(result["updated_at"], datetime)


# ===========================================================================
# 2. GET_ADMIN_FINANCE (tests 7-12)
# ===========================================================================


class TestGetAdminFinance:
    """Verify admin finance metrics."""

    async def test_finance_empty_database(self, db: AsyncSession):
        """7. Finance with empty database returns zeros."""
        result = await get_admin_finance(db)
        assert result["platform_volume_usd"] == 0.0
        assert result["completed_transaction_count"] == 0
        assert result["consumer_orders_count"] == 0
        assert result["platform_fee_volume_usd"] == 0.0
        assert result["payout_pending_count"] == 0
        assert result["payout_pending_usd"] == 0.0

    async def test_finance_transaction_volume(
        self, db: AsyncSession, make_agent, make_listing, make_transaction
    ):
        """8. Finance sums completed transaction amounts."""
        seller, _ = await make_agent(name="seller")
        buyer, _ = await make_agent(name="buyer")
        listing = await make_listing(seller.id, price_usdc=8.0)

        await make_transaction(buyer.id, seller.id, listing.id, amount_usdc=8.0)
        await make_transaction(buyer.id, seller.id, listing.id, amount_usdc=4.0)

        result = await get_admin_finance(db)
        assert result["platform_volume_usd"] == 12.0
        assert result["completed_transaction_count"] == 2

    async def test_finance_top_sellers(
        self, db: AsyncSession, make_agent, make_listing, make_transaction
    ):
        """9. Finance returns top sellers ranked by revenue."""
        seller1, _ = await make_agent(name="top-seller")
        seller2, _ = await make_agent(name="mid-seller")
        buyer, _ = await make_agent(name="buyer")

        listing1 = await make_listing(seller1.id, price_usdc=20.0)
        listing2 = await make_listing(seller2.id, price_usdc=5.0)

        await make_transaction(buyer.id, seller1.id, listing1.id, amount_usdc=20.0)
        await make_transaction(buyer.id, seller2.id, listing2.id, amount_usdc=5.0)

        result = await get_admin_finance(db)
        sellers = result["top_sellers_by_revenue"]
        assert len(sellers) == 2
        # Top seller should come first
        assert sellers[0]["money_received_usd"] >= sellers[1]["money_received_usd"]
        assert sellers[0]["agent_name"] == "top-seller"

    async def test_finance_payout_pending(
        self, db: AsyncSession, make_creator
    ):
        """10. Finance counts pending payouts."""
        creator, _ = await make_creator()
        await _create_redemption_request(db, creator.id, amount_usd=25.0, status="pending")
        await _create_redemption_request(db, creator.id, amount_usd=15.0, status="pending")

        result = await get_admin_finance(db)
        assert result["payout_pending_count"] == 2
        assert result["payout_pending_usd"] == 40.0

    async def test_finance_payout_processing(
        self, db: AsyncSession, make_creator
    ):
        """11. Finance counts processing payouts."""
        creator, _ = await make_creator()
        await _create_redemption_request(db, creator.id, amount_usd=50.0, status="processing")

        result = await get_admin_finance(db)
        assert result["payout_processing_count"] == 1
        assert result["payout_processing_usd"] == 50.0

    async def test_finance_has_timestamp(self, db: AsyncSession):
        """12. Finance includes updated_at timestamp."""
        result = await get_admin_finance(db)
        assert "updated_at" in result
        assert isinstance(result["updated_at"], datetime)


# ===========================================================================
# 3. GET_ADMIN_USAGE (tests 13-18)
# ===========================================================================


class TestGetAdminUsage:
    """Verify admin usage metrics."""

    async def test_usage_empty_database(self, db: AsyncSession):
        """13. Usage with empty database returns zeros."""
        result = await get_admin_usage(db)
        assert result["info_used_count"] == 0
        assert result["data_served_bytes"] == 0
        assert result["unique_buyers_count"] == 0
        assert result["unique_sellers_count"] == 0
        assert result["money_saved_for_others_usd"] == 0.0
        assert result["category_breakdown"] == []

    async def test_usage_counts_transactions(
        self, db: AsyncSession, make_agent, make_listing, make_transaction
    ):
        """14. Usage counts completed transactions as info_used_count."""
        seller, _ = await make_agent(name="seller")
        buyer, _ = await make_agent(name="buyer")
        listing = await make_listing(seller.id, price_usdc=1.0)

        await make_transaction(buyer.id, seller.id, listing.id, amount_usdc=1.0)
        await make_transaction(buyer.id, seller.id, listing.id, amount_usdc=1.0)

        result = await get_admin_usage(db)
        assert result["info_used_count"] == 2

    async def test_usage_unique_buyers_sellers(
        self, db: AsyncSession, make_agent, make_listing, make_transaction
    ):
        """15. Usage counts unique buyers and sellers."""
        seller1, _ = await make_agent(name="seller1")
        seller2, _ = await make_agent(name="seller2")
        buyer1, _ = await make_agent(name="buyer1")
        buyer2, _ = await make_agent(name="buyer2")

        listing1 = await make_listing(seller1.id)
        listing2 = await make_listing(seller2.id)

        await make_transaction(buyer1.id, seller1.id, listing1.id)
        await make_transaction(buyer2.id, seller2.id, listing2.id)

        result = await get_admin_usage(db)
        assert result["unique_buyers_count"] == 2
        assert result["unique_sellers_count"] == 2

    async def test_usage_category_breakdown(
        self, db: AsyncSession, make_agent, make_listing, make_transaction
    ):
        """16. Usage returns category breakdown of transactions."""
        seller, _ = await make_agent(name="seller")
        buyer, _ = await make_agent(name="buyer")

        listing_web = await make_listing(seller.id, category="web_search", price_usdc=2.0)
        listing_api = await make_listing(seller.id, category="api_data", price_usdc=3.0)

        await make_transaction(buyer.id, seller.id, listing_web.id, amount_usdc=2.0)
        await make_transaction(buyer.id, seller.id, listing_api.id, amount_usdc=3.0)

        result = await get_admin_usage(db)
        categories = {entry["category"] for entry in result["category_breakdown"]}
        assert "web_search" in categories
        assert "api_data" in categories

    async def test_usage_data_served_bytes(
        self, db: AsyncSession, make_agent, make_listing, make_transaction
    ):
        """17. Usage sums data_served_bytes from listing content_size."""
        seller, _ = await make_agent(name="seller")
        buyer, _ = await make_agent(name="buyer")
        listing = await make_listing(seller.id, content_size=1024)

        await make_transaction(buyer.id, seller.id, listing.id, amount_usdc=1.0)

        result = await get_admin_usage(db)
        assert result["data_served_bytes"] == 1024

    async def test_usage_money_saved_calculation(
        self, db: AsyncSession, make_agent, make_listing, make_transaction
    ):
        """17b. Usage computes money_saved_for_others_usd from listing metadata."""
        seller, _ = await make_agent(name="seller")
        buyer, _ = await make_agent(name="buyer")
        listing = await make_listing(seller.id, price_usdc=0.50)

        await make_transaction(buyer.id, seller.id, listing.id, amount_usdc=0.50)

        result = await get_admin_usage(db)
        # money_saved depends on _fresh_cost_estimate_usd from dashboard_service
        assert "money_saved_for_others_usd" in result
        assert isinstance(result["money_saved_for_others_usd"], float)

    async def test_usage_has_timestamp(self, db: AsyncSession):
        """18. Usage includes updated_at timestamp."""
        result = await get_admin_usage(db)
        assert "updated_at" in result


# ===========================================================================
# 4. LIST_ADMIN_AGENTS (tests 19-23)
# ===========================================================================


class TestListAdminAgents:
    """Verify paginated agent listing for admin dashboard."""

    async def test_list_agents_empty(self, db: AsyncSession):
        """19. list_admin_agents with no agents returns empty list."""
        result = await list_admin_agents(db)
        assert result["total"] == 0
        assert result["entries"] == []

    async def test_list_agents_returns_all(self, db: AsyncSession, make_agent):
        """20. list_admin_agents returns all agents."""
        await make_agent(name="agent-a")
        await make_agent(name="agent-b")
        result = await list_admin_agents(db)
        assert result["total"] == 2
        assert len(result["entries"]) == 2

    async def test_list_agents_status_filter(self, db: AsyncSession, make_agent):
        """21. list_admin_agents filters by status."""
        await make_agent(name="active-agent")
        result = await list_admin_agents(db, status="active")
        assert result["total"] >= 1
        for entry in result["entries"]:
            assert entry["status"] == "active"

    async def test_list_agents_pagination(self, db: AsyncSession, make_agent):
        """22. list_admin_agents supports pagination."""
        for i in range(5):
            await make_agent(name=f"agent-{i}")

        page1 = await list_admin_agents(db, page=1, page_size=2)
        assert len(page1["entries"]) == 2
        assert page1["total"] == 5

        page2 = await list_admin_agents(db, page=2, page_size=2)
        assert len(page2["entries"]) == 2

        page3 = await list_admin_agents(db, page=3, page_size=2)
        assert len(page3["entries"]) == 1

    async def test_list_agents_includes_trust_info(self, db: AsyncSession, make_agent):
        """23. list_admin_agents includes trust status and tier per agent."""
        await make_agent(name="trust-test-agent")
        result = await list_admin_agents(db)
        entry = result["entries"][0]
        assert "trust_status" in entry
        assert "trust_tier" in entry
        assert "trust_score" in entry
        # Default for unverified
        assert entry["trust_status"] == "unverified"
        assert entry["trust_tier"] == "T0"

    async def test_list_agents_includes_transaction_metrics(
        self, db: AsyncSession, make_agent, make_listing, make_transaction
    ):
        """23b. list_admin_agents includes money_received and info_used_count."""
        seller, _ = await make_agent(name="seller-metrics")
        buyer, _ = await make_agent(name="buyer-metrics")
        listing = await make_listing(seller.id, price_usdc=5.0)
        await make_transaction(buyer.id, seller.id, listing.id, amount_usdc=5.0)

        result = await list_admin_agents(db)
        seller_entry = next(e for e in result["entries"] if e["agent_name"] == "seller-metrics")
        assert seller_entry["money_received_usd"] == 5.0
        assert seller_entry["info_used_count"] == 1


# ===========================================================================
# 5. LIST_SECURITY_EVENTS (tests 24-27)
# ===========================================================================


class TestListSecurityEvents:
    """Verify security event listing with filtering."""

    async def test_list_events_empty(self, db: AsyncSession):
        """24. list_security_events with no events returns empty."""
        result = await list_security_events(db)
        assert result["total"] == 0
        assert result["events"] == []

    async def test_list_events_returns_entries(self, db: AsyncSession):
        """25. list_security_events returns inserted audit logs."""
        await _create_audit_log(db, event_type="agent.registered", severity="info")
        await _create_audit_log(db, event_type="auth.failed", severity="warning")

        result = await list_security_events(db)
        assert result["total"] == 2
        assert len(result["events"]) == 2

    async def test_list_events_filter_severity(self, db: AsyncSession):
        """26. list_security_events filters by severity."""
        await _create_audit_log(db, severity="info")
        await _create_audit_log(db, severity="critical")
        await _create_audit_log(db, severity="critical")

        result = await list_security_events(db, severity="critical")
        assert result["total"] == 2
        for event in result["events"]:
            assert event["severity"] == "critical"

    async def test_list_events_filter_event_type(self, db: AsyncSession):
        """27. list_security_events filters by event_type."""
        await _create_audit_log(db, event_type="auth.failed")
        await _create_audit_log(db, event_type="agent.registered")

        result = await list_security_events(db, event_type="auth.failed")
        assert result["total"] == 1
        assert result["events"][0]["event_type"] == "auth.failed"

    async def test_list_events_pagination(self, db: AsyncSession):
        """27b. list_security_events supports pagination."""
        for i in range(10):
            await _create_audit_log(db, event_type=f"event-{i}")

        page1 = await list_security_events(db, page=1, page_size=3)
        assert len(page1["events"]) == 3
        assert page1["total"] == 10

    async def test_list_events_parses_json_details(self, db: AsyncSession):
        """27c. list_security_events parses JSON details from audit log."""
        await _create_audit_log(db, details={"ip": "192.168.1.1", "reason": "brute_force"})

        result = await list_security_events(db)
        event = result["events"][0]
        assert isinstance(event["details"], dict)
        assert event["details"]["ip"] == "192.168.1.1"

    async def test_list_events_handles_invalid_json_details(self, db: AsyncSession):
        """27d. list_security_events gracefully handles invalid JSON in details."""
        log = AuditLog(
            id=_uid(),
            event_type="test.event",
            severity="info",
            details="not valid json {{{",
        )
        db.add(log)
        await db.commit()

        result = await list_security_events(db)
        assert len(result["events"]) == 1
        # Should return empty dict for unparseable details
        assert result["events"][0]["details"] == {}


# ===========================================================================
# 6. LIST_PENDING_PAYOUTS (tests 28-30)
# ===========================================================================


class TestListPendingPayouts:
    """Verify pending payout listing."""

    async def test_no_pending_payouts(self, db: AsyncSession):
        """28. list_pending_payouts returns empty when no pending requests."""
        result = await list_pending_payouts(db)
        assert result["count"] == 0
        assert result["total_pending_usd"] == 0.0
        assert result["requests"] == []

    async def test_pending_payouts_returned(self, db: AsyncSession, make_creator):
        """29. list_pending_payouts returns pending redemption requests."""
        creator, _ = await make_creator()
        await _create_redemption_request(db, creator.id, amount_usd=10.0, status="pending")
        await _create_redemption_request(db, creator.id, amount_usd=25.0, status="pending")
        # This one should NOT be included (completed)
        await _create_redemption_request(db, creator.id, amount_usd=100.0, status="completed")

        result = await list_pending_payouts(db)
        assert result["count"] == 2
        assert result["total_pending_usd"] == 35.0
        for req in result["requests"]:
            assert req["status"] == "pending"

    async def test_pending_payouts_limit(self, db: AsyncSession, make_creator):
        """30. list_pending_payouts respects the limit parameter."""
        creator, _ = await make_creator()
        for i in range(5):
            await _create_redemption_request(db, creator.id, amount_usd=1.0, status="pending")

        result = await list_pending_payouts(db, limit=3)
        assert result["count"] == 3

    async def test_pending_payouts_limit_clamped(self, db: AsyncSession, make_creator):
        """30b. list_pending_payouts clamps limit to range [1, 500]."""
        creator, _ = await make_creator()
        await _create_redemption_request(db, creator.id, amount_usd=5.0, status="pending")

        # limit=0 should be clamped to 1
        result = await list_pending_payouts(db, limit=0)
        assert result["count"] == 1

    async def test_pending_payouts_request_fields(self, db: AsyncSession, make_creator):
        """30c. list_pending_payouts returns expected fields per request."""
        creator, _ = await make_creator()
        await _create_redemption_request(
            db, creator.id, amount_usd=15.0,
            redemption_type="upi", status="pending",
        )

        result = await list_pending_payouts(db)
        req = result["requests"][0]
        assert "id" in req
        assert req["creator_id"] == creator.id
        assert req["redemption_type"] == "upi"
        assert req["amount_usd"] == 15.0
        assert req["currency"] == "USD"
        assert req["status"] == "pending"
