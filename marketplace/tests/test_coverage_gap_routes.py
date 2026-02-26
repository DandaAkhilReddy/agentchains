"""Targeted tests to close coverage gaps in route files.

Each test is named after the specific lines it covers and exercises
exactly the missing branch (error path, rate-limit, or return statement).
"""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from marketplace.config import settings
from marketplace.models.token_account import TokenAccount
from marketplace.tests.conftest import TestSession, _new_id


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _agent_auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _creator_auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def _seed_creator_balance(creator_id: str, balance: float = 100.0) -> None:
    async with TestSession() as db:
        db.add(TokenAccount(
            id=_new_id(),
            agent_id=None,
            creator_id=creator_id,
            balance=Decimal(str(balance)),
            total_earned=Decimal(str(balance)),
            total_spent=Decimal("0"),
            total_deposited=Decimal(str(balance)),
            total_fees_paid=Decimal("0"),
        ))
        await db.commit()


# ===========================================================================
# marketplace/api/wallet.py — lines 109-110, 140, 158-160
# ===========================================================================

class TestWalletCoverageGaps:
    """Target lines 109-110 (deposit ValueError), 140 (rate-limit 429),
    158-160 (transfer ValueError)."""

    async def test_deposit_service_raises_value_error_returns_400(self, client, make_agent):
        """Lines 109-110: create_deposit raises ValueError -> 400."""
        _, token = await make_agent()

        with patch(
            "marketplace.api.wallet.create_deposit",
            new_callable=AsyncMock,
            side_effect=ValueError("Deposit limit exceeded"),
        ):
            resp = await client.post(
                "/api/v1/wallet/deposit",
                headers=_agent_auth(token),
                json={"amount_usd": 50.0},
            )
        assert resp.status_code == 400
        assert "Deposit limit exceeded" in resp.json()["detail"]

    async def test_transfer_rate_limited_returns_429(self, client, make_agent):
        """Line 140: _transfer_limiter.check returns allowed=False -> 429."""
        _, token = await make_agent()

        with patch(
            "marketplace.api.wallet._transfer_limiter.check",
            return_value=(False, {"Retry-After": "60"}),
        ):
            resp = await client.post(
                "/api/v1/wallet/transfer",
                headers=_agent_auth(token),
                json={"to_agent_id": _new_id(), "amount": 10.0},
            )
        assert resp.status_code == 429
        assert "rate limit" in resp.json()["detail"].lower()
        assert resp.headers.get("Retry-After") == "60"

    async def test_transfer_service_raises_value_error_returns_400(self, client, make_agent):
        """Lines 158-160: transfer raises ValueError -> 400."""
        _, token = await make_agent()
        other_id = _new_id()

        with patch(
            "marketplace.api.wallet._transfer_limiter.check",
            return_value=(True, {}),
        ), patch(
            "marketplace.api.wallet.transfer",
            new_callable=AsyncMock,
            side_effect=ValueError("Insufficient balance"),
        ):
            resp = await client.post(
                "/api/v1/wallet/transfer",
                headers=_agent_auth(token),
                json={"to_agent_id": other_id, "amount": 9999.0},
            )
        assert resp.status_code == 400
        assert "Insufficient balance" in resp.json()["detail"]


# ===========================================================================
# marketplace/api/v2_payouts.py — lines 88-89, 109-110, 130-131
# ===========================================================================

class TestV2PayoutsValueErrorBranches:
    """Target lines 88-89 (cancel ValueError), 109-110 (approve ValueError),
    130-131 (reject ValueError)."""

    async def test_cancel_payout_service_raises_value_error(self, client, make_creator):
        """Lines 88-89: cancel_redemption raises ValueError -> 400."""
        creator, token = await make_creator()

        with patch(
            "marketplace.api.v2_payouts.redemption_service.cancel_redemption",
            new_callable=AsyncMock,
            side_effect=ValueError("Cannot cancel approved payout"),
        ):
            resp = await client.post(
                f"/api/v2/payouts/requests/{_new_id()}/cancel",
                headers=_creator_auth(token),
            )
        assert resp.status_code == 400
        assert "Cannot cancel approved payout" in resp.json()["detail"]

    async def test_approve_payout_service_raises_value_error(self, client, make_creator):
        """Lines 109-110: admin_approve_redemption raises ValueError -> 400."""
        creator, token = await make_creator()
        original = settings.admin_creator_ids

        try:
            object.__setattr__(settings, "admin_creator_ids", creator.id)
            with patch(
                "marketplace.api.v2_payouts.redemption_service.admin_approve_redemption",
                new_callable=AsyncMock,
                side_effect=ValueError("Payout already processed"),
            ):
                resp = await client.post(
                    f"/api/v2/payouts/requests/{_new_id()}/approve",
                    headers=_creator_auth(token),
                    json={"admin_notes": "ok"},
                )
        finally:
            object.__setattr__(settings, "admin_creator_ids", original)

        assert resp.status_code == 400
        assert "Payout already processed" in resp.json()["detail"]

    async def test_reject_payout_service_raises_value_error(self, client, make_creator):
        """Lines 130-131: admin_reject_redemption raises ValueError -> 400."""
        creator, token = await make_creator()
        original = settings.admin_creator_ids

        try:
            object.__setattr__(settings, "admin_creator_ids", creator.id)
            with patch(
                "marketplace.api.v2_payouts.redemption_service.admin_reject_redemption",
                new_callable=AsyncMock,
                side_effect=ValueError("Payout already processed"),
            ):
                resp = await client.post(
                    f"/api/v2/payouts/requests/{_new_id()}/reject",
                    headers=_creator_auth(token),
                    json={"reason": "fraud detected"},
                )
        finally:
            object.__setattr__(settings, "admin_creator_ids", original)

        assert resp.status_code == 400
        assert "Payout already processed" in resp.json()["detail"]


# ===========================================================================
# marketplace/api/v2_dashboards.py — lines 88-95
# ===========================================================================

class TestV2DashboardsPrivateBranches:
    """Target lines 88-95: agent lookup and 404/403 branches in dashboard_agent_private."""

    async def test_private_dashboard_agent_not_found_returns_404(self, client, make_creator):
        """Lines 89-90: agent not in DB -> 404."""
        creator, creator_token = await make_creator()

        # Use a completely non-existent agent_id
        resp = await client.get(
            f"/api/v2/dashboards/agent/{_new_id()}",
            headers=_creator_auth(creator_token),
        )
        assert resp.status_code == 404
        assert "not found" in resp.json()["detail"].lower()

    async def test_private_dashboard_creator_not_owner_not_admin_returns_403(
        self, client, make_agent, make_creator
    ):
        """Lines 92-93: creator does not own agent and is not admin -> 403."""
        creator, creator_token = await make_creator()
        agent, _ = await make_agent()

        with patch(
            "marketplace.api.v2_dashboards._admin_creator_ids",
            return_value=set(),
        ):
            resp = await client.get(
                f"/api/v2/dashboards/agent/{agent.id}",
                headers=_creator_auth(creator_token),
            )
        assert resp.status_code == 403
        assert "not authorized" in resp.json()["detail"].lower()

    async def test_private_dashboard_auth_failed_no_auth_returns_401(
        self, client, make_agent
    ):
        """Lines 82-83: both agent and creator auth fail -> 401."""
        agent, _ = await make_agent()

        resp = await client.get(f"/api/v2/dashboards/agent/{agent.id}")
        assert resp.status_code == 401


# ===========================================================================
# marketplace/api/transactions.py — lines 27, 46, 57, 67, 77, 91
# ===========================================================================

class TestTransactionReturnStatements:
    """Call route functions directly to guarantee the return lines execute."""

    async def test_initiate_transaction_return_line(self, db, make_agent, make_listing):
        """Line 27: TransactionInitiateResponse(...) is returned."""
        from marketplace.api.transactions import initiate_transaction
        from marketplace.schemas.transaction import TransactionInitiateRequest

        seller, _ = await make_agent(name="tx-seller-direct")
        buyer, _ = await make_agent(name="tx-buyer-direct")
        listing = await make_listing(seller.id, price_usdc=1.0)

        req = TransactionInitiateRequest(listing_id=listing.id)
        result = await initiate_transaction(req, db, buyer.id)
        assert result.status == "payment_pending"
        assert result.amount_usdc == 1.0

    async def test_confirm_payment_return_line(self, db, make_agent, make_listing):
        """Line 46: _tx_to_response(tx) in confirm_payment."""
        from marketplace.api.transactions import initiate_transaction, confirm_payment
        from marketplace.schemas.transaction import (
            TransactionInitiateRequest,
            TransactionConfirmPaymentRequest,
        )

        seller, _ = await make_agent(name="cp-seller")
        buyer, _ = await make_agent(name="cp-buyer")
        listing = await make_listing(seller.id, price_usdc=2.0)

        init_req = TransactionInitiateRequest(listing_id=listing.id)
        init_result = await initiate_transaction(init_req, db, buyer.id)
        tx_id = init_result.transaction_id

        conf_req = TransactionConfirmPaymentRequest(payment_signature="", payment_tx_hash="")
        result = await confirm_payment(tx_id, conf_req, db, buyer.id)
        assert result.status == "payment_confirmed"

    async def test_deliver_content_return_line(self, db, make_agent, make_listing):
        """Line 57: _tx_to_response(tx) in deliver_content."""
        from marketplace.api.transactions import (
            initiate_transaction,
            confirm_payment,
            deliver_content,
        )
        from marketplace.schemas.transaction import (
            TransactionInitiateRequest,
            TransactionConfirmPaymentRequest,
            TransactionDeliverRequest,
        )

        seller, _ = await make_agent(name="del-seller")
        buyer, _ = await make_agent(name="del-buyer")
        listing = await make_listing(seller.id, price_usdc=1.5)

        init_req = TransactionInitiateRequest(listing_id=listing.id)
        init_result = await initiate_transaction(init_req, db, buyer.id)
        tx_id = init_result.transaction_id

        await confirm_payment(
            tx_id,
            TransactionConfirmPaymentRequest(payment_signature="", payment_tx_hash=""),
            db,
            buyer.id,
        )
        deliver_req = TransactionDeliverRequest(content="sample payload")
        result = await deliver_content(tx_id, deliver_req, db, seller.id)
        assert result.status == "delivered"

    async def test_verify_delivery_return_line(self, db, make_agent, make_listing):
        """Line 67: _tx_to_response(tx) in verify_delivery."""
        from marketplace.api.transactions import (
            initiate_transaction,
            confirm_payment,
            deliver_content,
            verify_delivery,
        )
        from marketplace.schemas.transaction import (
            TransactionInitiateRequest,
            TransactionConfirmPaymentRequest,
            TransactionDeliverRequest,
        )

        seller, _ = await make_agent(name="vd-seller")
        buyer, _ = await make_agent(name="vd-buyer")
        listing = await make_listing(seller.id, price_usdc=1.0)

        init_req = TransactionInitiateRequest(listing_id=listing.id)
        init_result = await initiate_transaction(init_req, db, buyer.id)
        tx_id = init_result.transaction_id

        await confirm_payment(
            tx_id,
            TransactionConfirmPaymentRequest(payment_signature="", payment_tx_hash=""),
            db,
            buyer.id,
        )
        await deliver_content(
            tx_id, TransactionDeliverRequest(content="data"), db, seller.id
        )
        result = await verify_delivery(tx_id, db, buyer.id)
        assert result.status in ("disputed", "completed")

    async def test_get_transaction_return_line(self, db, make_agent, make_listing):
        """Line 77: _tx_to_response(tx) in get_transaction."""
        from marketplace.api.transactions import initiate_transaction, get_transaction
        from marketplace.schemas.transaction import TransactionInitiateRequest

        seller, _ = await make_agent(name="gt-seller")
        buyer, _ = await make_agent(name="gt-buyer")
        listing = await make_listing(seller.id, price_usdc=2.0)

        init_req = TransactionInitiateRequest(listing_id=listing.id)
        init_result = await initiate_transaction(init_req, db, buyer.id)
        tx_id = init_result.transaction_id

        result = await get_transaction(tx_id, db, buyer.id)
        assert result.id == tx_id

    async def test_list_transactions_return_line(self, db, make_agent, make_listing):
        """Line 91: TransactionListResponse(...) is returned in list_transactions."""
        from marketplace.api.transactions import initiate_transaction, list_transactions
        from marketplace.schemas.transaction import TransactionInitiateRequest

        seller, _ = await make_agent(name="lt-seller")
        buyer, _ = await make_agent(name="lt-buyer")
        listing = await make_listing(seller.id, price_usdc=1.0)

        init_req = TransactionInitiateRequest(listing_id=listing.id)
        await initiate_transaction(init_req, db, buyer.id)

        result = await list_transactions(
            status=None, page=1, page_size=20, db=db, current_agent=buyer.id
        )
        assert result.total == 1
        assert len(result.transactions) == 1


# ===========================================================================
# marketplace/api/redemptions.py — lines 137-138, 162-163
# ===========================================================================

class TestRedemptionsValueErrorBranches:
    """Target lines 137-138 (admin_approve ValueError) and 162-163 (admin_reject ValueError)."""

    async def test_admin_approve_service_raises_value_error(
        self, client, make_creator, monkeypatch
    ):
        """Lines 137-138: admin_approve_redemption raises ValueError -> 400."""
        admin_creator, admin_token = await make_creator()
        monkeypatch.setattr(settings, "admin_creator_ids", admin_creator.id)

        with patch(
            "marketplace.api.redemptions.redemption_service.admin_approve_redemption",
            new_callable=AsyncMock,
            side_effect=ValueError("Redemption already approved"),
        ):
            resp = await client.post(
                f"/api/v1/redemptions/admin/{_new_id()}/approve",
                headers=_creator_auth(admin_token),
                json={"admin_notes": "ok"},
            )
        assert resp.status_code == 400
        assert "Redemption already approved" in resp.json()["detail"]

    async def test_admin_reject_service_raises_value_error(
        self, client, make_creator, monkeypatch
    ):
        """Lines 162-163: admin_reject_redemption raises ValueError -> 400."""
        admin_creator, admin_token = await make_creator()
        monkeypatch.setattr(settings, "admin_creator_ids", admin_creator.id)

        with patch(
            "marketplace.api.redemptions.redemption_service.admin_reject_redemption",
            new_callable=AsyncMock,
            side_effect=ValueError("Redemption already rejected"),
        ):
            resp = await client.post(
                f"/api/v1/redemptions/admin/{_new_id()}/reject",
                headers=_creator_auth(admin_token),
                json={"reason": "test rejection"},
            )
        assert resp.status_code == 400
        assert "Redemption already rejected" in resp.json()["detail"]


# ===========================================================================
# marketplace/api/v2_admin.py — lines 33, 134-135, 152-153
# ===========================================================================

class TestV2AdminValueErrorBranches:
    """Target line 33 (_require_admin_creator no-admin-config path),
    lines 134-135 (approve ValueError), and 152-153 (reject ValueError)."""

    async def test_require_admin_creator_no_admin_ids_configured(
        self, client, make_creator, monkeypatch
    ):
        """Line 33: admin_creator_ids is empty -> 403 'No admin accounts configured'."""
        _, token = await make_creator()
        monkeypatch.setattr(settings, "admin_creator_ids", "")

        resp = await client.get(
            "/api/v2/admin/overview",
            headers=_creator_auth(token),
        )
        assert resp.status_code == 403
        assert "No admin accounts configured" in resp.json()["detail"]

    async def test_admin_approve_payout_service_raises_value_error(
        self, client, make_creator, monkeypatch
    ):
        """Lines 134-135: admin_approve_redemption raises ValueError -> 400."""
        admin_creator, admin_token = await make_creator()
        monkeypatch.setattr(settings, "admin_creator_ids", admin_creator.id)

        with patch(
            "marketplace.api.v2_admin.redemption_service.admin_approve_redemption",
            new_callable=AsyncMock,
            side_effect=ValueError("Payout not in pending state"),
        ):
            resp = await client.post(
                f"/api/v2/admin/payouts/{_new_id()}/approve",
                headers=_creator_auth(admin_token),
                json={"admin_notes": ""},
            )
        assert resp.status_code == 400
        assert "Payout not in pending state" in resp.json()["detail"]

    async def test_admin_reject_payout_service_raises_value_error(
        self, client, make_creator, monkeypatch
    ):
        """Lines 152-153: admin_reject_redemption raises ValueError -> 400."""
        admin_creator, admin_token = await make_creator()
        monkeypatch.setattr(settings, "admin_creator_ids", admin_creator.id)

        with patch(
            "marketplace.api.v2_admin.redemption_service.admin_reject_redemption",
            new_callable=AsyncMock,
            side_effect=ValueError("Payout already processed"),
        ):
            resp = await client.post(
                f"/api/v2/admin/payouts/{_new_id()}/reject",
                headers=_creator_auth(admin_token),
                json={"reason": "suspicious"},
            )
        assert resp.status_code == 400
        assert "Payout already processed" in resp.json()["detail"]


# ===========================================================================
# marketplace/api/v2_builder.py — lines 55, 71-74
# ===========================================================================

class TestV2BuilderReturnAndErrorBranches:
    """Target line 55 (list projects return), lines 71-74 (publish ValueError branches)."""

    async def test_list_projects_return_line(self, db, make_creator):
        """Line 55: {'total': len(projects), 'projects': projects} is returned."""
        from marketplace.api.v2_builder import list_builder_projects_v2

        creator, token = await make_creator()

        result = await list_builder_projects_v2(db=db, authorization=f"Bearer {token}")
        assert "total" in result
        assert "projects" in result
        assert isinstance(result["projects"], list)
        assert result["total"] == len(result["projects"])

    async def test_publish_project_not_found_returns_404(self, client, make_creator):
        """Lines 71-74: ValueError with 'not found' in message -> 404."""
        _, creator_token = await make_creator()

        with patch(
            "marketplace.api.v2_builder.dual_layer_service.publish_builder_project",
            new_callable=AsyncMock,
            side_effect=ValueError("Project not found"),
        ):
            resp = await client.post(
                f"/api/v2/builder/projects/{_new_id()}/publish",
                headers=_creator_auth(creator_token),
            )
        assert resp.status_code == 404
        assert "not found" in resp.json()["detail"].lower()

    async def test_publish_project_non_not_found_value_error_returns_400(
        self, client, make_creator
    ):
        """Lines 71-74: ValueError without 'not found' in message -> 400."""
        _, creator_token = await make_creator()

        with patch(
            "marketplace.api.v2_builder.dual_layer_service.publish_builder_project",
            new_callable=AsyncMock,
            side_effect=ValueError("Missing required config field: summary"),
        ):
            resp = await client.post(
                f"/api/v2/builder/projects/{_new_id()}/publish",
                headers=_creator_auth(creator_token),
            )
        assert resp.status_code == 400
        assert "Missing required config field" in resp.json()["detail"]


# ===========================================================================
# marketplace/api/listings.py — lines 25, 37, 51, 62, 72
# ===========================================================================

class TestListingsReturnStatements:
    """Call listing route functions directly to guarantee return lines execute."""

    async def test_create_listing_return_line(self, db, make_agent):
        """Line 25: _listing_to_response(listing) returned from create_listing."""
        from marketplace.api.listings import create_listing
        from marketplace.schemas.listing import ListingCreateRequest

        agent, _ = await make_agent(name="lst-create")
        req = ListingCreateRequest(
            title="Direct Create Test",
            category="web_search",
            content="test content payload",
            price_usdc=1.0,
        )
        result = await create_listing(req, db, agent.id)
        assert result.title == "Direct Create Test"
        assert result.seller_id == agent.id

    async def test_list_listings_return_line(self, db, make_agent, make_listing):
        """Line 37: ListingListResponse(...) returned from list_listings."""
        from marketplace.api.listings import list_listings

        agent, _ = await make_agent(name="lst-list")
        await make_listing(agent.id, title="Listed Item")

        result = await list_listings(
            category=None, status="active", page=1, page_size=20, db=db
        )
        assert result.total >= 1
        assert len(result.results) >= 1

    async def test_get_listing_return_line(self, db, make_agent, make_listing):
        """Line 51: _listing_to_response(listing) returned from get_listing."""
        from marketplace.api.listings import get_listing

        agent, _ = await make_agent(name="lst-get")
        listing = await make_listing(agent.id, title="Get Target")

        result = await get_listing(listing.id, db)
        assert result.id == listing.id
        assert result.title == "Get Target"

    async def test_update_listing_return_line(self, db, make_agent, make_listing):
        """Line 62: _listing_to_response(listing) returned from update_listing."""
        from marketplace.api.listings import update_listing
        from marketplace.schemas.listing import ListingUpdateRequest

        agent, _ = await make_agent(name="lst-update")
        listing = await make_listing(agent.id, title="Before Update", price_usdc=1.0)

        req = ListingUpdateRequest(price_usdc=2.5)
        result = await update_listing(listing.id, req, db, agent.id)
        assert result.price_usdc == 2.5

    async def test_delist_return_line(self, db, make_agent, make_listing):
        """Line 72: {'status': 'delisted'} returned from delist."""
        from marketplace.api.listings import delist

        agent, _ = await make_agent(name="lst-delist")
        listing = await make_listing(agent.id)

        result = await delist(listing.id, db, agent.id)
        assert result == {"status": "delisted"}


# ===========================================================================
# marketplace/api/v2_memory.py — remaining uncovered lines
# ===========================================================================

class TestV2MemoryRemainingLines:
    """Cover remaining missing lines in v2_memory.py."""

    async def test_import_snapshot_agent_has_no_creator_id(self, client, make_agent):
        """Lines 43 (creator_id = None when agent has no creator_id): agent without
        a creator gets creator_id=None passed to import_snapshot."""
        agent, token = await make_agent()

        with patch(
            "marketplace.api.v2_memory.memory_service.import_snapshot",
            new_callable=AsyncMock,
            return_value={
                "snapshot": {
                    "snapshot_id": "snap-direct",
                    "agent_id": agent.id,
                    "source_type": "sdk",
                    "label": "direct",
                    "manifest": {},
                    "merkle_root": "sha256:abc",
                    "status": "imported",
                    "total_records": 1,
                    "total_chunks": 1,
                    "created_at": None,
                    "verified_at": None,
                },
                "chunk_hashes": ["sha256:abc"],
                "trust_profile": {},
            },
        ) as mock_import:
            resp = await client.post(
                "/api/v2/memory/snapshots/import",
                headers=_agent_auth(token),
                json={
                    "source_type": "sdk",
                    "label": "no-creator",
                    "records": [{"id": "r1"}],
                },
            )
        assert resp.status_code == 201
        # creator_id passed should be None (agent has no creator_id by default)
        call_kwargs = mock_import.call_args.kwargs
        assert call_kwargs["creator_id"] is None

    async def test_import_snapshot_value_error_raises_400(self, client, make_agent):
        """Lines 56-57: ValueError in import_snapshot -> 400."""
        agent, token = await make_agent()

        with patch(
            "marketplace.api.v2_memory.memory_service.import_snapshot",
            new_callable=AsyncMock,
            side_effect=ValueError("Invalid record format"),
        ):
            resp = await client.post(
                "/api/v2/memory/snapshots/import",
                headers=_agent_auth(token),
                json={
                    "source_type": "sdk",
                    "label": "bad-record",
                    "records": [{"bad": "format"}],
                },
            )
        assert resp.status_code == 400
        assert "Invalid record format" in resp.json()["detail"]

    async def test_verify_snapshot_value_error_raises_404(self, client, make_agent):
        """Lines 76-77: ValueError in verify_snapshot -> 404."""
        agent, token = await make_agent()

        with patch(
            "marketplace.api.v2_memory.memory_service.verify_snapshot",
            new_callable=AsyncMock,
            side_effect=ValueError("Snapshot xyz not found"),
        ):
            resp = await client.post(
                f"/api/v2/memory/snapshots/{_new_id()}/verify",
                headers=_agent_auth(token),
                json={"sample_size": 5},
            )
        assert resp.status_code == 404
        assert "not found" in resp.json()["detail"].lower()

    async def test_get_snapshot_value_error_raises_404(self, client, make_agent):
        """Lines 92-93: ValueError in get_snapshot -> 404."""
        agent, token = await make_agent()

        with patch(
            "marketplace.api.v2_memory.memory_service.get_snapshot",
            new_callable=AsyncMock,
            side_effect=ValueError("Snapshot does not exist"),
        ):
            resp = await client.get(
                f"/api/v2/memory/snapshots/{_new_id()}",
                headers=_agent_auth(token),
            )
        assert resp.status_code == 404
        assert "not exist" in resp.json()["detail"].lower()

    async def test_import_snapshot_with_creator_id(self, client, make_agent, make_creator, db):
        """Line 43: agent.creator_id is set -> creator_id passed to import_snapshot."""
        from marketplace.models.agent import RegisteredAgent
        from sqlalchemy import select

        creator, _ = await make_creator()
        agent, token = await make_agent()

        # Assign creator_id to the agent directly
        result = await db.execute(
            select(RegisteredAgent).where(RegisteredAgent.id == agent.id)
        )
        agent_row = result.scalar_one()
        agent_row.creator_id = creator.id
        await db.commit()

        with patch(
            "marketplace.api.v2_memory.memory_service.import_snapshot",
            new_callable=AsyncMock,
            return_value={
                "snapshot": {
                    "snapshot_id": "snap-creator",
                    "agent_id": agent.id,
                    "source_type": "sdk",
                    "label": "creator-import",
                    "manifest": {},
                    "merkle_root": "sha256:def",
                    "status": "imported",
                    "total_records": 1,
                    "total_chunks": 1,
                    "created_at": None,
                    "verified_at": None,
                },
                "chunk_hashes": ["sha256:def"],
                "trust_profile": {},
            },
        ) as mock_import:
            resp = await client.post(
                "/api/v2/memory/snapshots/import",
                headers=_agent_auth(token),
                json={
                    "source_type": "sdk",
                    "label": "creator-import",
                    "records": [{"id": "r1"}],
                },
            )
        assert resp.status_code == 201
        call_kwargs = mock_import.call_args.kwargs
        assert call_kwargs["creator_id"] == creator.id


# ===========================================================================
# marketplace/api/v2_integrations.py — remaining uncovered lines
# ===========================================================================

class TestV2IntegrationsRemainingLines:
    """Cover remaining missing lines in v2_integrations.py."""

    async def test_create_webhook_value_error_raises_400(self, client, make_agent):
        """Lines 34-35: ValueError in register_subscription -> 400."""
        agent, token = await make_agent(agent_type="seller")

        with patch(
            "marketplace.api.v2_integrations.event_subscription_service.register_subscription",
            new_callable=AsyncMock,
            side_effect=ValueError("Duplicate callback URL"),
        ):
            resp = await client.post(
                "/api/v2/integrations/webhooks",
                headers=_agent_auth(token),
                json={"callback_url": "https://example.com/hooks/dup"},
            )
        assert resp.status_code == 400
        assert "Duplicate callback URL" in resp.json()["detail"]

    async def test_list_webhooks_returns_count(self, db, make_agent):
        """Line 47: {'subscriptions': ..., 'count': ...} returned."""
        from marketplace.api.v2_integrations import list_webhook_subscriptions_v2

        agent, _ = await make_agent(agent_type="seller")

        result = await list_webhook_subscriptions_v2(db=db, agent_id=agent.id)
        assert "subscriptions" in result
        assert "count" in result
        assert result["count"] == len(result["subscriptions"])

    async def test_delete_webhook_not_found_raises_404(self, db, make_agent):
        """Lines 61-62: delete_subscription returns False -> HTTPException 404."""
        from marketplace.api.v2_integrations import delete_webhook_subscription_v2
        from fastapi import HTTPException

        agent, _ = await make_agent(agent_type="seller")

        with pytest.raises(HTTPException) as exc_info:
            await delete_webhook_subscription_v2(
                subscription_id=_new_id(),
                db=db,
                agent_id=agent.id,
            )
        assert exc_info.value.status_code == 404
        assert "not found" in exc_info.value.detail.lower()

    async def test_delete_webhook_success_returns_deleted_true(self, db, make_agent):
        """Line 63: {'deleted': True} returned when deletion succeeds."""
        from marketplace.api.v2_integrations import (
            create_webhook_subscription_v2,
            delete_webhook_subscription_v2,
            WebhookSubscriptionRequest,
        )

        agent, _ = await make_agent(agent_type="seller")
        req = WebhookSubscriptionRequest(
            callback_url="https://example.com/del-success",
            event_types=["*"],
        )
        sub = await create_webhook_subscription_v2(req, db, agent.id)
        result = await delete_webhook_subscription_v2(sub["id"], db, agent.id)
        assert result == {"deleted": True}

    async def test_create_webhook_no_auth_returns_401(self, client):
        """Confirm unauthenticated webhook create is rejected."""
        resp = await client.post(
            "/api/v2/integrations/webhooks",
            json={"callback_url": "https://example.com/no-auth"},
        )
        assert resp.status_code == 401

    async def test_list_webhooks_no_auth_returns_401(self, client):
        """Confirm unauthenticated webhook list is rejected."""
        resp = await client.get("/api/v2/integrations/webhooks")
        assert resp.status_code == 401
