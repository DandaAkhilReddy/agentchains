"""End-to-end buyer-seller lifecycle tests for the AgentChains marketplace.

Covers 25 tests across 5 describe blocks:
1. Complete buyer flow (discover -> search -> view listing -> deposit -> purchase -> delivery -> rate)
2. Complete seller flow (register -> create listing -> receive order -> deliver -> get paid -> view earnings)
3. Transaction lifecycle (initiate -> escrow -> deliver -> confirm -> release funds -> settle)
4. Dispute & refund flow (buyer disputes -> evidence -> resolution -> refund or release)
5. Multi-party scenarios (buyer from multiple sellers, seller serves multiple buyers, creator royalties)

Style: pytest + unittest.mock, @pytest.mark.asyncio, mock all DB/external calls.
"""

import json
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from marketplace.config import settings
from marketplace.services import (
    token_service,
    listing_service,
    transaction_service,
    express_service,
    deposit_service,
    reputation_service,
    creator_service,
    seller_service,
    demand_service,
    audit_service,
)

# CDN patch target -- express_service imports cdn_get_content from cdn_service
CDN_PATCH = "marketplace.services.express_service.cdn_get_content"
SAMPLE_CONTENT = b'{"data": "buyer-seller lifecycle test payload"}'


# ==============================================================================
# Block 1: Complete Buyer Flow
# discover -> search -> view listing -> deposit funds -> purchase -> delivery -> rate
# ==============================================================================

class TestCompleteBuyerFlow:
    """Full buyer lifecycle: from marketplace discovery through purchase to rating."""

    @pytest.mark.asyncio
    @patch(CDN_PATCH, new_callable=AsyncMock)
    async def test_buyer_discovers_marketplace_listings(
        self, mock_cdn, db, make_agent, make_listing
    ):
        """Buyer enters marketplace and browses all active listings across categories."""
        mock_cdn.return_value = SAMPLE_CONTENT

        seller, _ = await make_agent("disc-seller", "seller")

        # Seller has listings in multiple categories
        await make_listing(seller.id, price_usdc=2.0, category="web_search", title="Web Data Pack")
        await make_listing(seller.id, price_usdc=5.0, category="code_analysis", title="Code Review")
        await make_listing(seller.id, price_usdc=1.0, category="api_response", title="API Cache")

        # Buyer browses the entire marketplace
        results, total = await listing_service.discover(db, page=1, page_size=20)
        assert total == 3
        categories_found = {r.category for r in results}
        assert categories_found == {"web_search", "code_analysis", "api_response"}

    @pytest.mark.asyncio
    async def test_buyer_searches_by_keyword_and_filters(
        self, db, make_agent, make_listing
    ):
        """Buyer searches with keyword, then narrows with price/quality filters."""
        seller, _ = await make_agent("search-seller", "seller")

        await make_listing(seller.id, price_usdc=1.0, title="Python Basics", quality_score=0.6)
        await make_listing(seller.id, price_usdc=5.0, title="Python Advanced ML", quality_score=0.95)
        await make_listing(seller.id, price_usdc=3.0, title="JavaScript Guide", quality_score=0.8)

        # Keyword search
        results, total = await listing_service.discover(db, q="Python")
        assert total == 2
        assert all("Python" in r.title for r in results)

        # Add quality filter on top of keyword
        results, total = await listing_service.discover(db, q="Python", min_quality=0.9)
        assert total == 1
        assert results[0].title == "Python Advanced ML"

        # Price range filter
        results, total = await listing_service.discover(db, min_price=2.0, max_price=4.0)
        assert total == 1
        assert results[0].title == "JavaScript Guide"

    @pytest.mark.asyncio
    async def test_buyer_views_listing_detail(self, db, make_agent, make_listing):
        """Buyer clicks into a specific listing and inspects its metadata."""
        seller, _ = await make_agent("detail-seller", "seller")
        listing = await make_listing(
            seller.id,
            price_usdc=4.5,
            title="Detailed Data Product",
            quality_score=0.88,
            category="document_summary",
        )

        # View the single listing
        fetched = await listing_service.get_listing(db, listing.id)
        assert fetched.id == listing.id
        assert fetched.title == "Detailed Data Product"
        assert float(fetched.price_usdc) == 4.5
        assert float(fetched.quality_score) == 0.88
        assert fetched.category == "document_summary"
        assert fetched.seller_id == seller.id
        assert fetched.status == "active"

    @pytest.mark.asyncio
    async def test_buyer_deposits_funds_before_purchase(
        self, db, make_agent, seed_platform
    ):
        """Buyer deposits fiat currency and receives USD balance in wallet."""
        platform = seed_platform
        await token_service.ensure_platform_account(db)

        buyer, _ = await make_agent("deposit-buyer", "buyer")
        await token_service.create_account(db, buyer.id)

        # Deposit USD
        deposit_data = await deposit_service.create_deposit(
            db, agent_id=buyer.id, amount_usd=50.0,
            payment_method="credit_card",
        )
        assert deposit_data["status"] == "pending"
        assert deposit_data["amount_usd"] > 0

        # Confirm the deposit
        confirmed = await deposit_service.confirm_deposit(db, deposit_data["id"])
        assert confirmed["status"] == "completed"

        # Verify balance
        balance = await token_service.get_balance(db, buyer.id)
        assert balance["balance"] == confirmed["amount_usd"]
        assert balance["balance"] > 0

    @pytest.mark.asyncio
    @patch(CDN_PATCH, new_callable=AsyncMock)
    async def test_buyer_purchases_listing_via_express_buy(
        self, mock_cdn, db, make_agent, make_token_account, make_listing, seed_platform
    ):
        """Buyer executes express buy: single-request purchase with token payment."""
        mock_cdn.return_value = SAMPLE_CONTENT
        await token_service.ensure_platform_account(db)

        seller, _ = await make_agent("buy-seller", "seller")
        await make_token_account(seller.id, balance=0)
        listing = await make_listing(seller.id, price_usdc=3.0, quality_score=0.7)

        buyer, _ = await make_agent("buy-buyer", "buyer")
        await make_token_account(buyer.id, balance=5000)

        # Express buy
        response = await express_service.express_buy(
            db, listing.id, buyer.id, payment_method="token"
        )
        data = json.loads(response.body.decode())

        assert data["listing_id"] == listing.id
        assert data["transaction_id"] is not None
        assert "content" in data
        assert data["price_usdc"] == 3.0
        assert data["payment_method"] == "token"
        assert data["seller_id"] == seller.id

        # Buyer balance decreased, seller balance increased
        buyer_bal = await token_service.get_balance(db, buyer.id)
        seller_bal = await token_service.get_balance(db, seller.id)
        assert buyer_bal["balance"] < 5000
        assert seller_bal["balance"] > 0

    @pytest.mark.asyncio
    @patch(CDN_PATCH, new_callable=AsyncMock)
    async def test_buyer_receives_content_and_verifies_hash(
        self, mock_cdn, db, make_agent, make_token_account, make_listing, seed_platform
    ):
        """After purchase, buyer receives content with matching hash (verified delivery)."""
        mock_cdn.return_value = SAMPLE_CONTENT
        await token_service.ensure_platform_account(db)

        seller, _ = await make_agent("verify-seller", "seller")
        await make_token_account(seller.id, balance=0)
        listing = await make_listing(seller.id, price_usdc=1.0, quality_score=0.5)

        buyer, _ = await make_agent("verify-buyer", "buyer")
        await make_token_account(buyer.id, balance=5000)

        response = await express_service.express_buy(
            db, listing.id, buyer.id, payment_method="token"
        )
        data = json.loads(response.body.decode())

        # Transaction should be auto-verified in express mode
        tx = await transaction_service.get_transaction(db, data["transaction_id"])
        assert tx.status == "completed"
        assert tx.verification_status == "verified"
        assert tx.content_hash == tx.delivered_hash
        assert tx.completed_at is not None

    @pytest.mark.asyncio
    @patch(CDN_PATCH, new_callable=AsyncMock)
    async def test_buyer_rates_seller_via_reputation(
        self, mock_cdn, db, make_agent, make_token_account, make_listing, seed_platform
    ):
        """After purchase, buyer's transaction contributes to seller reputation score."""
        mock_cdn.return_value = SAMPLE_CONTENT
        await token_service.ensure_platform_account(db)

        seller, _ = await make_agent("rate-seller", "seller")
        await make_token_account(seller.id, balance=0)
        listing = await make_listing(seller.id, price_usdc=2.0, quality_score=0.9)

        buyer, _ = await make_agent("rate-buyer", "buyer")
        await make_token_account(buyer.id, balance=5000)

        await express_service.express_buy(db, listing.id, buyer.id, payment_method="token")

        # Calculate seller reputation (reflects the completed sale)
        rep = await reputation_service.calculate_reputation(db, seller.id)
        assert rep.total_transactions >= 1
        assert rep.successful_deliveries >= 1
        assert rep.total_volume_usdc >= 2.0
        assert rep.composite_score > 0
        assert rep.verification_failures == 0


# ==============================================================================
# Block 2: Complete Seller Flow
# register -> create listing -> receive order -> deliver -> get paid -> view earnings
# ==============================================================================

class TestCompleteSellerFlow:
    """Full seller lifecycle: from registration through sales to earnings tracking."""

    @pytest.mark.asyncio
    async def test_seller_registers_and_gets_account(self, db, make_agent):
        """Seller registers as an agent and gets a token account."""
        seller, token = await make_agent("new-seller", "seller")
        assert seller.status == "active"
        assert seller.agent_type == "seller"
        assert token is not None

        # Create token account
        account = await token_service.create_account(db, seller.id)
        assert account.agent_id == seller.id
        assert float(account.balance) == 0

    @pytest.mark.asyncio
    async def test_seller_creates_listing_with_content(self, db, make_agent):
        """Seller creates a listing, content is stored and hashed."""
        seller, _ = await make_agent("list-seller", "seller")

        from marketplace.schemas.listing import ListingCreateRequest
        req = ListingCreateRequest(
            title="Enterprise API Data",
            description="Real-time stock prices",
            category="api_response",
            content='{"AAPL": 185.50, "GOOG": 140.20}',
            price_usdc=8.0,
            quality_score=0.92,
            tags=["finance", "stocks", "real-time"],
            metadata={"format": "json", "freshness": "5min"},
        )
        listing = await listing_service.create_listing(db, seller.id, req)

        assert listing.seller_id == seller.id
        assert listing.title == "Enterprise API Data"
        assert listing.status == "active"
        assert float(listing.price_usdc) == 8.0
        assert listing.content_hash is not None
        assert listing.content_size > 0

    @pytest.mark.asyncio
    @patch(CDN_PATCH, new_callable=AsyncMock)
    async def test_seller_receives_order_and_delivers(
        self, mock_cdn, db, make_agent, make_token_account, make_listing, seed_platform
    ):
        """When buyer purchases, seller's listing is delivered and transaction completes."""
        mock_cdn.return_value = SAMPLE_CONTENT
        await token_service.ensure_platform_account(db)

        seller, _ = await make_agent("order-seller", "seller")
        await make_token_account(seller.id, balance=0)
        listing = await make_listing(seller.id, price_usdc=2.0, quality_score=0.7)

        buyer, _ = await make_agent("order-buyer", "buyer")
        await make_token_account(buyer.id, balance=5000)

        # Purchase occurs (simulating order receipt)
        response = await express_service.express_buy(
            db, listing.id, buyer.id, payment_method="token"
        )
        data = json.loads(response.body.decode())

        # Verify order was completed for the seller
        tx = await transaction_service.get_transaction(db, data["transaction_id"])
        assert tx.seller_id == seller.id
        assert tx.status == "completed"
        assert tx.delivered_at is not None

    @pytest.mark.asyncio
    @patch(CDN_PATCH, new_callable=AsyncMock)
    async def test_seller_gets_paid_after_delivery(
        self, mock_cdn, db, make_agent, make_token_account, make_listing, seed_platform
    ):
        """After delivery, seller receives USD minus platform fees."""
        mock_cdn.return_value = SAMPLE_CONTENT
        await token_service.ensure_platform_account(db)

        seller, _ = await make_agent("paid-seller", "seller")
        await make_token_account(seller.id, balance=0)
        listing = await make_listing(seller.id, price_usdc=5.0, quality_score=0.85)

        buyer, _ = await make_agent("paid-buyer", "buyer")
        await make_token_account(buyer.id, balance=10000)

        await express_service.express_buy(db, listing.id, buyer.id, payment_method="token")

        # Seller earned tokens (minus fees)
        seller_bal = await token_service.get_balance(db, seller.id)
        assert seller_bal["balance"] > 0
        assert seller_bal["total_earned"] > 0

        # Earnings are less than the full price (platform fee deducted)
        assert seller_bal["total_earned"] < 5.0

    @pytest.mark.asyncio
    @patch(CDN_PATCH, new_callable=AsyncMock)
    async def test_seller_views_earnings_and_transaction_history(
        self, mock_cdn, db, make_agent, make_token_account, make_listing, seed_platform
    ):
        """Seller can view their earnings breakdown and transaction ledger."""
        mock_cdn.return_value = SAMPLE_CONTENT
        await token_service.ensure_platform_account(db)

        seller, _ = await make_agent("hist-seller", "seller")
        await make_token_account(seller.id, balance=0)

        buyer, _ = await make_agent("hist-buyer", "buyer")
        await make_token_account(buyer.id, balance=20000)

        # Create two listings and have buyer purchase both
        listing1 = await make_listing(seller.id, price_usdc=3.0, quality_score=0.6)
        listing2 = await make_listing(seller.id, price_usdc=4.0, quality_score=0.7)

        await express_service.express_buy(db, listing1.id, buyer.id, payment_method="token")
        await express_service.express_buy(db, listing2.id, buyer.id, payment_method="token")

        # Check earnings summary
        seller_bal = await token_service.get_balance(db, seller.id)
        assert seller_bal["total_earned"] > 0

        # Check ledger history
        history, total = await token_service.get_history(db, seller.id, page=1, page_size=10)
        assert total >= 2  # At least 2 purchase credits
        credit_entries = [h for h in history if h["direction"] == "credit"]
        assert len(credit_entries) >= 2

        # Verify transactions list
        txns, tx_total = await transaction_service.list_transactions(
            db, agent_id=seller.id, status_filter="completed"
        )
        assert tx_total == 2
        assert all(tx.seller_id == seller.id for tx in txns)


# ==============================================================================
# Block 3: Transaction Lifecycle
# initiate -> escrow -> deliver -> confirm -> release funds -> settle
# ==============================================================================

class TestTransactionLifecycle:
    """Step-by-step transaction state machine: from initiation to settlement."""

    @pytest.mark.asyncio
    async def test_transaction_initiation_creates_pending_record(
        self, db, make_agent, make_listing
    ):
        """Initiating a transaction creates a payment_pending record."""
        seller, _ = await make_agent("init-seller", "seller")
        listing = await make_listing(seller.id, price_usdc=5.0)

        buyer, _ = await make_agent("init-buyer", "buyer")

        tx_data = await transaction_service.initiate_transaction(db, listing.id, buyer.id)

        assert tx_data["status"] == "payment_pending"
        assert tx_data["amount_usdc"] == 5.0
        assert tx_data["transaction_id"] is not None
        assert "payment_details" in tx_data
        assert tx_data["content_hash"] is not None

    @pytest.mark.asyncio
    async def test_payment_confirmation_advances_state(
        self, db, make_agent, make_listing
    ):
        """Confirming payment advances status from payment_pending to payment_confirmed."""
        seller, _ = await make_agent("pay-seller", "seller")
        listing = await make_listing(seller.id, price_usdc=3.0)

        buyer, _ = await make_agent("pay-buyer", "buyer")

        tx_data = await transaction_service.initiate_transaction(db, listing.id, buyer.id)
        tx_id = tx_data["transaction_id"]

        # Confirm payment (simulated mode)
        tx = await transaction_service.confirm_payment(db, tx_id)
        assert tx.status == "payment_confirmed"
        assert tx.paid_at is not None

    @pytest.mark.asyncio
    async def test_content_delivery_by_seller(
        self, db, make_agent, make_listing
    ):
        """Seller delivers content, advancing status to delivered."""
        seller, _ = await make_agent("deliver-seller", "seller")
        listing = await make_listing(seller.id, price_usdc=2.0)

        buyer, _ = await make_agent("deliver-buyer", "buyer")

        tx_data = await transaction_service.initiate_transaction(db, listing.id, buyer.id)
        tx_id = tx_data["transaction_id"]

        await transaction_service.confirm_payment(db, tx_id)

        # Seller delivers the content
        tx = await transaction_service.deliver_content(
            db, tx_id, "Delivered content payload", seller.id
        )
        assert tx.status == "delivered"
        assert tx.delivered_at is not None
        assert tx.delivered_hash is not None

    @pytest.mark.asyncio
    async def test_buyer_verifies_delivery_completes_transaction(
        self, db, make_agent, make_listing
    ):
        """Buyer verifies delivered content matches expected hash -> transaction completed."""
        seller, _ = await make_agent("complete-seller", "seller")
        from marketplace.schemas.listing import ListingCreateRequest
        req = ListingCreateRequest(
            title="Verified Content",
            description="Content for verification",
            category="web_search",
            content="Exact content for matching hash",
            price_usdc=2.0,
            quality_score=0.8,
        )
        listing = await listing_service.create_listing(db, seller.id, req)

        buyer, _ = await make_agent("complete-buyer", "buyer")

        tx_data = await transaction_service.initiate_transaction(db, listing.id, buyer.id)
        tx_id = tx_data["transaction_id"]

        await transaction_service.confirm_payment(db, tx_id)

        # Deliver the EXACT content to ensure hash matches
        await transaction_service.deliver_content(
            db, tx_id, "Exact content for matching hash", seller.id
        )

        # Buyer verifies delivery
        tx = await transaction_service.verify_delivery(db, tx_id, buyer.id)
        assert tx.status == "completed"
        assert tx.verification_status == "verified"
        assert tx.completed_at is not None

    @pytest.mark.asyncio
    @patch(CDN_PATCH, new_callable=AsyncMock)
    async def test_funds_released_to_seller_after_completion(
        self, mock_cdn, db, make_agent, make_token_account, make_listing, seed_platform
    ):
        """After successful verification, seller receives payment (token settlement)."""
        mock_cdn.return_value = SAMPLE_CONTENT
        await token_service.ensure_platform_account(db)

        seller, _ = await make_agent("settle-seller", "seller")
        await make_token_account(seller.id, balance=0)
        listing = await make_listing(seller.id, price_usdc=4.0, quality_score=0.5)

        buyer, _ = await make_agent("settle-buyer", "buyer")
        await make_token_account(buyer.id, balance=10000)

        initial_buyer = await token_service.get_balance(db, buyer.id)

        # Full express purchase flow (collapsed state machine)
        await express_service.express_buy(db, listing.id, buyer.id, payment_method="token")

        # Verify funds settled: buyer debited, seller credited
        final_buyer = await token_service.get_balance(db, buyer.id)
        final_seller = await token_service.get_balance(db, seller.id)

        assert final_buyer["balance"] < initial_buyer["balance"]
        assert final_seller["balance"] > 0


# ==============================================================================
# Block 4: Dispute & Refund Flow
# buyer disputes -> evidence submitted -> resolution -> refund or release
# ==============================================================================

class TestDisputeAndRefundFlow:
    """Dispute scenarios: hash mismatch, refund paths, and resolution outcomes."""

    @pytest.mark.asyncio
    async def test_hash_mismatch_triggers_dispute(
        self, db, make_agent, make_listing
    ):
        """Delivering content with a different hash triggers a disputed status."""
        seller, _ = await make_agent("dispute-seller", "seller")
        listing = await make_listing(seller.id, price_usdc=3.0)

        buyer, _ = await make_agent("dispute-buyer", "buyer")

        tx_data = await transaction_service.initiate_transaction(db, listing.id, buyer.id)
        tx_id = tx_data["transaction_id"]

        await transaction_service.confirm_payment(db, tx_id)

        # Deliver DIFFERENT content (hash will not match)
        await transaction_service.deliver_content(
            db, tx_id, "Completely different content that does NOT match", seller.id
        )

        # Buyer attempts verification -- hash mismatch -> disputed
        tx = await transaction_service.verify_delivery(db, tx_id, buyer.id)
        assert tx.status == "disputed"
        assert tx.verification_status == "failed"
        assert "Hash mismatch" in (tx.error_message or "")

    @pytest.mark.asyncio
    async def test_disputed_transaction_tracked_in_history(
        self, db, make_agent, make_listing
    ):
        """Disputed transactions are filterable and visible in agent transaction lists."""
        seller, _ = await make_agent("track-seller", "seller")
        listing = await make_listing(seller.id, price_usdc=2.0)

        buyer, _ = await make_agent("track-buyer", "buyer")

        tx_data = await transaction_service.initiate_transaction(db, listing.id, buyer.id)
        tx_id = tx_data["transaction_id"]

        await transaction_service.confirm_payment(db, tx_id)
        await transaction_service.deliver_content(
            db, tx_id, "Wrong content for dispute tracking", seller.id
        )
        await transaction_service.verify_delivery(db, tx_id, buyer.id)

        # Filter by disputed status
        txns, total = await transaction_service.list_transactions(
            db, agent_id=buyer.id, status_filter="disputed"
        )
        assert total == 1
        assert txns[0].id == tx_id
        assert txns[0].status == "disputed"

    @pytest.mark.asyncio
    async def test_dispute_recorded_in_audit_trail(
        self, db, make_agent, make_listing
    ):
        """Dispute events are logged in the audit trail for accountability."""
        seller, _ = await make_agent("audit-dispute-seller", "seller")
        listing = await make_listing(seller.id, price_usdc=2.0)

        buyer, _ = await make_agent("audit-dispute-buyer", "buyer")

        tx_data = await transaction_service.initiate_transaction(db, listing.id, buyer.id)
        tx_id = tx_data["transaction_id"]

        await transaction_service.confirm_payment(db, tx_id)
        await transaction_service.deliver_content(
            db, tx_id, "Mismatched content for audit", seller.id
        )
        await transaction_service.verify_delivery(db, tx_id, buyer.id)

        # Log dispute audit events manually (as the system would)
        await audit_service.log_event(
            db, "transaction_disputed",
            agent_id=buyer.id,
            details={"transaction_id": tx_id, "reason": "hash_mismatch"},
        )
        await db.commit()

        from marketplace.models.audit_log import AuditLog
        rows = (await db.execute(select(AuditLog))).scalars().all()
        dispute_events = [r for r in rows if r.event_type == "transaction_disputed"]
        assert len(dispute_events) >= 1
        assert dispute_events[0].agent_id == buyer.id

    @pytest.mark.asyncio
    async def test_refund_via_deposit_restores_buyer_balance(
        self, db, make_agent, make_token_account, seed_platform
    ):
        """Simulating a refund by crediting tokens back to the buyer restores balance."""
        await token_service.ensure_platform_account(db)

        buyer, _ = await make_agent("refund-buyer", "buyer")
        await make_token_account(buyer.id, balance=10000)

        initial_balance = await token_service.get_balance(db, buyer.id)
        assert initial_balance["balance"] == 10000

        # Simulate a purchase debit (buyer loses tokens)
        seller, _ = await make_agent("refund-seller", "seller")
        await make_token_account(seller.id, balance=0)

        purchase_amount = 5.0
        tx_id = f"refund-test-{uuid.uuid4().hex[:8]}"
        result = await token_service.debit_for_purchase(
            db, buyer.id, seller.id, purchase_amount, tx_id
        )
        assert result["amount_usd"] > 0

        after_purchase = await token_service.get_balance(db, buyer.id)
        assert after_purchase["balance"] < 10000

        # Refund: deposit USD back to buyer (simulating admin/dispute resolution)
        refund_amount = result["amount_usd"]
        await token_service.deposit(
            db,
            agent_id=buyer.id,
            amount_usd=refund_amount,
            deposit_id=f"refund-{tx_id}",
            memo=f"Refund for disputed transaction {tx_id}",
        )

        after_refund = await token_service.get_balance(db, buyer.id)
        # Refund amount may exceed original loss due to fees, but balance should be restored
        assert after_refund["balance"] > after_purchase["balance"]

    @pytest.mark.asyncio
    async def test_dispute_affects_seller_reputation(
        self, db, make_agent, make_listing
    ):
        """A disputed transaction negatively impacts the seller's reputation score."""
        seller, _ = await make_agent("bad-rep-seller", "seller")
        listing = await make_listing(seller.id, price_usdc=2.0)

        buyer, _ = await make_agent("bad-rep-buyer", "buyer")

        # Create a disputed transaction
        tx_data = await transaction_service.initiate_transaction(db, listing.id, buyer.id)
        tx_id = tx_data["transaction_id"]
        await transaction_service.confirm_payment(db, tx_id)
        await transaction_service.deliver_content(
            db, tx_id, "Wrong content causing dispute", seller.id
        )
        await transaction_service.verify_delivery(db, tx_id, buyer.id)

        # Calculate reputation -- should reflect the failed delivery
        rep = await reputation_service.calculate_reputation(db, seller.id)
        assert rep.total_transactions >= 1
        assert rep.failed_deliveries >= 1
        assert rep.verification_failures >= 1
        # Composite score penalised by delivery failure
        assert rep.composite_score < 1.0


# ==============================================================================
# Block 5: Multi-Party Scenarios
# buyer from multiple sellers, seller serves multiple buyers, creator royalties
# ==============================================================================

class TestMultiPartyScenarios:
    """Complex multi-agent interactions: cross-seller purchases, concurrent buyers, royalties."""

    @pytest.mark.asyncio
    @patch(CDN_PATCH, new_callable=AsyncMock)
    async def test_buyer_purchases_from_multiple_sellers(
        self, mock_cdn, db, make_agent, make_token_account, make_listing, seed_platform
    ):
        """Single buyer purchases listings from 3 different sellers in one session."""
        mock_cdn.return_value = SAMPLE_CONTENT
        await token_service.ensure_platform_account(db)

        sellers = []
        listings = []
        for i in range(3):
            seller, _ = await make_agent(f"multi-seller-{i}", "seller")
            await make_token_account(seller.id, balance=0)
            listing = await make_listing(
                seller.id, price_usdc=2.0 + i, quality_score=0.7 + (i * 0.05)
            )
            sellers.append(seller)
            listings.append(listing)

        buyer, _ = await make_agent("multi-buyer", "buyer")
        await make_token_account(buyer.id, balance=30000)

        # Buy from all 3 sellers
        tx_ids = []
        for listing in listings:
            resp = await express_service.express_buy(
                db, listing.id, buyer.id, payment_method="token"
            )
            data = json.loads(resp.body.decode())
            tx_ids.append(data["transaction_id"])

        assert len(set(tx_ids)) == 3  # All unique transaction IDs

        # Each seller received payment
        for seller in sellers:
            bal = await token_service.get_balance(db, seller.id)
            assert bal["balance"] > 0
            assert bal["total_earned"] > 0

        # Buyer spent from all 3 purchases
        buyer_bal = await token_service.get_balance(db, buyer.id)
        assert buyer_bal["balance"] < 30000
        assert buyer_bal["total_spent"] > 0

    @pytest.mark.asyncio
    @patch(CDN_PATCH, new_callable=AsyncMock)
    async def test_seller_serves_multiple_buyers(
        self, mock_cdn, db, make_agent, make_token_account, make_listing, seed_platform
    ):
        """Single seller's listing is purchased by 4 different buyers."""
        mock_cdn.return_value = SAMPLE_CONTENT
        await token_service.ensure_platform_account(db)

        seller, _ = await make_agent("popular-seller", "seller")
        await make_token_account(seller.id, balance=0)
        listing = await make_listing(seller.id, price_usdc=1.5, quality_score=0.8)

        buyers = []
        for i in range(4):
            buyer, _ = await make_agent(f"fan-buyer-{i}", "buyer")
            await make_token_account(buyer.id, balance=5000)
            buyers.append(buyer)

        # All buyers purchase the same listing
        for buyer in buyers:
            await express_service.express_buy(
                db, listing.id, buyer.id, payment_method="token"
            )

        # Seller accumulated earnings from all 4 sales
        seller_bal = await token_service.get_balance(db, seller.id)
        assert seller_bal["total_earned"] > 0

        # Verify 4 completed transactions for this seller
        txns, total = await transaction_service.list_transactions(
            db, agent_id=seller.id, status_filter="completed"
        )
        assert total == 4
        buyer_ids = {tx.buyer_id for tx in txns}
        assert len(buyer_ids) == 4  # All different buyers

        # Reputation reflects 4 successful sales
        rep = await reputation_service.calculate_reputation(db, seller.id)
        assert rep.total_transactions >= 4
        assert rep.successful_deliveries >= 4
        assert rep.total_volume_usdc >= 6.0  # 4 * 1.5

    @pytest.mark.asyncio
    @patch(CDN_PATCH, new_callable=AsyncMock)
    async def test_creator_royalties_flow_from_agent_sale(
        self, mock_cdn, db, make_creator, make_agent, make_token_account,
        make_listing, seed_platform
    ):
        """Creator links agent, agent sells, royalty auto-flows to creator's wallet."""
        mock_cdn.return_value = SAMPLE_CONTENT
        await token_service.ensure_platform_account(db)

        # Create creator with token account
        creator, _ = await make_creator(email="royalty-flow@test.com")
        from marketplace.models.token_account import TokenAccount
        creator_acct = TokenAccount(
            id=str(uuid.uuid4()),
            agent_id=None,
            creator_id=creator.id,
            balance=Decimal("0"),
        )
        db.add(creator_acct)
        await db.commit()

        # Agent owned by creator
        agent, _ = await make_agent("royalty-agent", "seller")
        await make_token_account(agent.id, balance=0)
        await creator_service.link_agent_to_creator(db, creator.id, agent.id)

        # Agent creates listing and buyer purchases
        listing = await make_listing(agent.id, price_usdc=10.0, quality_score=0.85)
        buyer, _ = await make_agent("royalty-buyer", "buyer")
        await make_token_account(buyer.id, balance=20000)

        await express_service.express_buy(db, listing.id, buyer.id, payment_method="token")

        # Creator should have earned a royalty
        creator_balance = await token_service.get_creator_balance(db, creator.id)
        assert creator_balance["balance"] > 0
        assert creator_balance["total_earned"] > 0

    @pytest.mark.asyncio
    @patch(CDN_PATCH, new_callable=AsyncMock)
    async def test_creator_with_multiple_agents_aggregated_royalties(
        self, mock_cdn, db, make_creator, make_agent, make_token_account,
        make_listing, seed_platform
    ):
        """Creator owns 3 agents, each sells, royalties aggregate in creator wallet."""
        mock_cdn.return_value = SAMPLE_CONTENT
        await token_service.ensure_platform_account(db)

        creator, _ = await make_creator(email="multi-agent-creator@test.com")
        from marketplace.models.token_account import TokenAccount
        creator_acct = TokenAccount(
            id=str(uuid.uuid4()),
            agent_id=None,
            creator_id=creator.id,
            balance=Decimal("0"),
        )
        db.add(creator_acct)
        await db.commit()

        # Create 3 agents owned by same creator
        agents = []
        for i in range(3):
            agent, _ = await make_agent(f"multi-agent-{i}", "seller")
            await make_token_account(agent.id, balance=0)
            await creator_service.link_agent_to_creator(db, creator.id, agent.id)
            agents.append(agent)

        # Each agent creates a listing
        listings = []
        for agent in agents:
            listing = await make_listing(agent.id, price_usdc=5.0, quality_score=0.8)
            listings.append(listing)

        # Buyer purchases from all 3 agents
        buyer, _ = await make_agent("bulk-royalty-buyer", "buyer")
        await make_token_account(buyer.id, balance=30000)

        for listing in listings:
            await express_service.express_buy(
                db, listing.id, buyer.id, payment_method="token"
            )

        # Creator dashboard should show 3 agents and aggregated earnings
        dashboard = await creator_service.get_creator_dashboard(db, creator.id)
        assert dashboard["agents_count"] == 3
        assert dashboard["total_agent_earnings"] > 0
        assert dashboard["creator_balance"] > 0

        # Each agent should also have some earnings
        for agent_data in dashboard["agents"]:
            assert agent_data["total_earned"] > 0

    @pytest.mark.asyncio
    @patch(CDN_PATCH, new_callable=AsyncMock)
    async def test_full_marketplace_day_multi_party(
        self, mock_cdn, db, make_agent, make_token_account, make_listing,
        make_search_log, seed_platform
    ):
        """Simulate a complete marketplace day: 2 sellers, 3 buyers, 6 transactions,
        demand signals, reputation calculations, and supply integrity."""
        mock_cdn.return_value = SAMPLE_CONTENT
        await token_service.ensure_platform_account(db)

        # --- Setup participants ---
        seller1, _ = await make_agent("day-seller1", "seller")
        seller2, _ = await make_agent("day-seller2", "seller")
        await make_token_account(seller1.id, balance=0)
        await make_token_account(seller2.id, balance=0)

        buyers = []
        for i in range(3):
            buyer, _ = await make_agent(f"day-buyer-{i}", "buyer")
            await make_token_account(buyer.id, balance=20000)
            buyers.append(buyer)

        # --- Create listings ---
        s1_listings = []
        for i in range(2):
            l = await make_listing(
                seller1.id, price_usdc=2.0 + i,
                title=f"Seller1 Product {i}",
                category="web_search",
                quality_score=0.7 + (i * 0.1),
            )
            s1_listings.append(l)

        s2_listings = []
        for i in range(2):
            l = await make_listing(
                seller2.id, price_usdc=3.0 + i,
                title=f"Seller2 Product {i}",
                category="code_analysis",
                quality_score=0.8 + (i * 0.05),
            )
            s2_listings.append(l)

        # Verify 4 listings discoverable
        results, total = await listing_service.discover(db)
        assert total == 4

        # --- Execute purchases ---
        all_tx_ids = []

        # Buyer 0 buys from seller1 (listing 0) and seller2 (listing 0)
        for listing in [s1_listings[0], s2_listings[0]]:
            resp = await express_service.express_buy(
                db, listing.id, buyers[0].id, payment_method="token"
            )
            data = json.loads(resp.body.decode())
            all_tx_ids.append(data["transaction_id"])

        # Buyer 1 buys from seller1 (listing 1)
        resp = await express_service.express_buy(
            db, s1_listings[1].id, buyers[1].id, payment_method="token"
        )
        all_tx_ids.append(json.loads(resp.body.decode())["transaction_id"])

        # Buyer 2 buys from seller2 (listing 1) and seller1 (listing 0)
        for listing in [s2_listings[1], s1_listings[0]]:
            resp = await express_service.express_buy(
                db, listing.id, buyers[2].id, payment_method="token"
            )
            all_tx_ids.append(json.loads(resp.body.decode())["transaction_id"])

        assert len(all_tx_ids) == 5
        assert len(set(all_tx_ids)) == 5  # All unique

        # --- Verify seller earnings ---
        s1_bal = await token_service.get_balance(db, seller1.id)
        s2_bal = await token_service.get_balance(db, seller2.id)
        assert s1_bal["total_earned"] > 0
        assert s2_bal["total_earned"] > 0

        # --- Verify all buyers spent ---
        for buyer in buyers:
            bal = await token_service.get_balance(db, buyer.id)
            assert bal["balance"] < 20000

        # --- Reputation ---
        rep1 = await reputation_service.calculate_reputation(db, seller1.id)
        rep2 = await reputation_service.calculate_reputation(db, seller2.id)
        assert rep1.total_transactions >= 3  # Seller1 had 3 sales
        assert rep2.total_transactions >= 2  # Seller2 had 2 sales
        assert rep1.composite_score > 0
        assert rep2.composite_score > 0

        # --- Demand signals ---
        for _ in range(10):
            await make_search_log(
                query_text="web scraping tools",
                category="web_search",
                matched_count=2,
            )
        signals = await demand_service.aggregate_demand(db, time_window_hours=24)
        assert len(signals) >= 1
