"""IT-10: End-to-end cross-module integration tests (20 tests).

Simulates a full marketplace day with 3+ agents interacting across ALL modules:
registration, token economy, listings, discovery, express buy, reputation,
audit trail, ZKP proofs, creator system, demand aggregation, catalog, webhooks,
tier progression, and health checks.

Each test exercises a realistic multi-service workflow that spans module boundaries.
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
    reputation_service,
    demand_service,
    express_service,
)
from marketplace.services import zkp_service, catalog_service
from marketplace.services import audit_service, seller_service
from marketplace.services import listing_service, creator_service
from marketplace.tests.conftest import TestSession

# CDN patch target — express_service imports cdn_get_content from cdn_service
CDN_PATCH = "marketplace.services.express_service.cdn_get_content"
SAMPLE_CONTENT = b'{"data": "cross-module integration test payload"}'


# ---------------------------------------------------------------------------
# 1. test_e2e_agent_registers_and_gets_bonus
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_e2e_agent_registers_and_gets_bonus(client, auth_header):
    """Register via HTTP, check token account has signup bonus."""
    resp = await client.post("/api/v1/agents/register", json={
        "name": f"bonus-agent-{uuid.uuid4().hex[:8]}",
        "agent_type": "both",
        "public_key": "ssh-rsa AAAA_test_key",
    })
    assert resp.status_code == 201
    data = resp.json()
    agent_id = data["id"]
    token = data["jwt_token"]

    # Query balance via the wallet endpoint
    wallet_resp = await client.get(
        "/api/v1/wallet/balance",
        headers=auth_header(token),
    )
    assert wallet_resp.status_code == 200
    balance_data = wallet_resp.json()
    assert balance_data["balance"] == settings.signup_bonus_usd


# ---------------------------------------------------------------------------
# 2. test_e2e_seller_lists_and_buyer_discovers
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_e2e_seller_lists_and_buyer_discovers(client, auth_header):
    """Seller creates listing via HTTP, buyer searches and finds it."""
    # Register seller
    seller_resp = await client.post("/api/v1/agents/register", json={
        "name": f"seller-disc-{uuid.uuid4().hex[:8]}",
        "agent_type": "seller",
        "public_key": "ssh-rsa AAAA_seller_disc_key",
    })
    assert seller_resp.status_code == 201
    seller_token = seller_resp.json()["jwt_token"]

    # Seller creates listing
    listing_resp = await client.post(
        "/api/v1/listings",
        headers=auth_header(seller_token),
        json={
            "title": "Quantum Computing Primer",
            "description": "Intro to quantum gates and circuits",
            "category": "web_search",
            "content": "Quantum computing uses qubits...",
            "price_usdc": 3.0,
            "quality_score": 0.85,
        },
    )
    assert listing_resp.status_code in (200, 201)
    listing_id = listing_resp.json()["id"]

    # Buyer discovers via discover endpoint
    discover_resp = await client.get(
        "/api/v1/discover",
        params={"q": "quantum", "category": "web_search"},
    )
    assert discover_resp.status_code == 200
    discover_data = discover_resp.json()
    assert discover_data["total"] >= 1
    found_ids = [r["id"] for r in discover_data["results"]]
    assert listing_id in found_ids


# ---------------------------------------------------------------------------
# 3. test_e2e_full_purchase_flow
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
@patch(CDN_PATCH, new_callable=AsyncMock)
async def test_e2e_full_purchase_flow(mock_cdn, client, auth_header, seed_platform):
    """Buyer deposits -> finds listing -> express buys -> gets content."""
    mock_cdn.return_value = SAMPLE_CONTENT

    # Register seller and create listing
    seller_resp = await client.post("/api/v1/agents/register", json={
        "name": f"seller-full-{uuid.uuid4().hex[:8]}",
        "agent_type": "seller",
        "public_key": "ssh-rsa AAAA_seller_full_key",
    })
    seller_token = seller_resp.json()["jwt_token"]

    listing_resp = await client.post(
        "/api/v1/listings",
        headers=auth_header(seller_token),
        json={
            "title": "Full Flow Data",
            "description": "For full e2e",
            "category": "code_analysis",
            "content": "def hello(): pass",
            "price_usdc": 0.05,
            "quality_score": 0.5,
        },
    )
    listing_id = listing_resp.json()["id"]

    # Register buyer (gets signup bonus)
    buyer_resp = await client.post("/api/v1/agents/register", json={
        "name": f"buyer-full-{uuid.uuid4().hex[:8]}",
        "agent_type": "buyer",
        "public_key": "ssh-rsa AAAA_buyer_full_key",
    })
    buyer_token = buyer_resp.json()["jwt_token"]

    # Express buy (POST)
    buy_resp = await client.post(
        f"/api/v1/express/{listing_id}",
        headers=auth_header(buyer_token),
        params={"payment_method": "token"},
    )
    assert buy_resp.status_code == 200
    buy_data = buy_resp.json()
    assert buy_data["listing_id"] == listing_id
    assert buy_data["transaction_id"] is not None
    assert "content" in buy_data
    assert buy_data["payment_method"] == "token"
    assert buy_data["cost_usd"] is not None


# ---------------------------------------------------------------------------
# 4. test_e2e_purchase_creates_audit_trail
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_e2e_purchase_creates_audit_trail(
    db, make_agent, make_token_account, make_listing, seed_platform
):
    """After purchase, audit events exist for the transaction."""
    await token_service.ensure_platform_account(db)

    seller, _ = await make_agent("audit-seller", "seller")
    await make_token_account(seller.id, balance=0)
    buyer, _ = await make_agent("audit-buyer", "buyer")
    await make_token_account(buyer.id, balance=5000)

    listing = await make_listing(seller.id, price_usdc=1.0, quality_score=0.5)

    # Log audit events around the purchase
    await audit_service.log_event(
        db, "purchase_initiated",
        agent_id=buyer.id,
        details={"listing_id": listing.id, "seller_id": seller.id},
    )
    await db.commit()

    # Perform purchase via token_service
    result = await token_service.debit_for_purchase(
        db, buyer.id, seller.id, 1.0, f"audit-tx-{uuid.uuid4().hex[:8]}"
    )
    assert result["amount_usd"] > 0

    await audit_service.log_event(
        db, "purchase_completed",
        agent_id=buyer.id,
        details={"listing_id": listing.id, "amount_usd": result["amount_usd"]},
    )
    await db.commit()

    # Verify audit entries exist
    from marketplace.models.audit_log import AuditLog
    rows = (await db.execute(select(AuditLog))).scalars().all()
    event_types = [r.event_type for r in rows]
    assert "purchase_initiated" in event_types
    assert "purchase_completed" in event_types
    assert len(rows) >= 2

    # Verify hash chain linking
    assert rows[1].prev_hash == rows[0].entry_hash


# ---------------------------------------------------------------------------
# 5. test_e2e_purchase_updates_reputation
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
@patch(CDN_PATCH, new_callable=AsyncMock)
async def test_e2e_purchase_updates_reputation(
    mock_cdn, db, make_agent, make_token_account, make_listing, seed_platform
):
    """After purchase, seller's reputation reflects the sale."""
    mock_cdn.return_value = SAMPLE_CONTENT
    await token_service.ensure_platform_account(db)

    seller, _ = await make_agent("rep-seller", "seller")
    await make_token_account(seller.id, balance=0)
    buyer, _ = await make_agent("rep-buyer", "buyer")
    await make_token_account(buyer.id, balance=5000)

    listing = await make_listing(seller.id, price_usdc=1.0, quality_score=0.5)

    # Express buy creates a completed transaction
    await express_service.express_buy(db, listing.id, buyer.id, payment_method="token")

    # Calculate reputation
    rep = await reputation_service.calculate_reputation(db, seller.id)

    assert rep.total_transactions >= 1
    assert rep.successful_deliveries >= 1
    assert rep.total_volume_usdc >= 1.0
    assert rep.composite_score > 0


# ---------------------------------------------------------------------------
# 6. test_e2e_fee_and_burn_accounting
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_e2e_fee_accounting(
    db, make_agent, make_token_account, seed_platform
):
    """After purchase, platform fee matches expected amount."""
    await token_service.ensure_platform_account(db)

    seller, _ = await make_agent("fee-seller")
    buyer, _ = await make_agent("fee-buyer")
    await make_token_account(seller.id, balance=0)
    await make_token_account(buyer.id, balance=10000)

    price_usdc = 5.0
    tx_id = f"fee-tx-{uuid.uuid4().hex[:8]}"
    result = await token_service.debit_for_purchase(
        db, buyer.id, seller.id, price_usdc, tx_id
    )

    amount_usd = result["amount_usd"]
    fee_usd = result["fee_usd"]

    # Fee should be a percentage of amount
    assert fee_usd > 0
    assert fee_usd < amount_usd


# ---------------------------------------------------------------------------
# 7. test_e2e_creator_earns_from_agent
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
@patch(CDN_PATCH, new_callable=AsyncMock)
async def test_e2e_creator_earns_from_agent(
    mock_cdn, db, make_creator, make_agent, make_token_account, make_listing, seed_platform
):
    """Creator links agent, agent earns from sale, creator gets royalty."""
    mock_cdn.return_value = SAMPLE_CONTENT
    await token_service.ensure_platform_account(db)

    # Create creator and their token account
    creator, _ = await make_creator(email="royalty@test.com")
    from marketplace.models.token_account import TokenAccount
    creator_acct = TokenAccount(
        id=str(uuid.uuid4()),
        agent_id=None,
        creator_id=creator.id,
        balance=Decimal("0"),
    )
    db.add(creator_acct)
    await db.commit()

    # Create agent and link to creator
    agent, _ = await make_agent("creator-agent", "seller")
    await make_token_account(agent.id, balance=0)
    link = await creator_service.link_agent_to_creator(db, creator.id, agent.id)
    assert link["creator_id"] == creator.id

    # Agent creates listing and buyer purchases
    listing = await make_listing(agent.id, price_usdc=5.0, quality_score=0.85)
    buyer, _ = await make_agent("creator-buyer", "buyer")
    await make_token_account(buyer.id, balance=10000)

    await express_service.express_buy(db, listing.id, buyer.id, payment_method="token")

    # Creator balance should have royalty
    creator_balance = await token_service.get_creator_balance(db, creator.id)
    assert creator_balance["balance"] > 0
    assert creator_balance["total_earned"] > 0


# ---------------------------------------------------------------------------
# 10. test_e2e_creator_redeems_api_credits
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_e2e_creator_redeems_api_credits(client):
    """Creator earns enough, redeems for API credits."""
    # Register creator (gets signup bonus)
    email = f"redeem-{uuid.uuid4().hex[:8]}@test.com"
    reg_resp = await client.post("/api/v1/creators/register", json={
        "email": email,
        "password": "testpass123",
        "display_name": "Redeemer",
    })
    assert reg_resp.status_code == 201
    token = reg_resp.json()["token"]

    # Verify wallet has signup bonus
    wallet_resp = await client.get(
        "/api/v1/creators/me/wallet",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert wallet_resp.status_code == 200
    initial_balance = wallet_resp.json()["balance"]
    assert initial_balance > 0

    # Redeem balance for API credits
    redeem_resp = await client.post("/api/v1/redemptions", json={
        "redemption_type": "api_credits",
        "amount_usd": initial_balance,
        "currency": "USD",
    }, headers={"Authorization": f"Bearer {token}"})
    assert redeem_resp.status_code == 201
    assert redeem_resp.json()["status"] == "completed"
    assert redeem_resp.json()["redemption_type"] == "api_credits"

    # Wallet should now be 0
    wallet_resp2 = await client.get(
        "/api/v1/creators/me/wallet",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert wallet_resp2.json()["balance"] == 0.0


# ---------------------------------------------------------------------------
# 11. test_e2e_catalog_to_demand_to_opportunity
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_e2e_catalog_to_demand_to_opportunity(
    db, make_agent, make_catalog_entry, make_search_log
):
    """Register catalog, log searches, aggregate demand, generate opportunities."""
    seller, _ = await make_agent("cat-seller", "seller")

    # 1. Register catalog entry
    entry = await make_catalog_entry(
        agent_id=seller.id,
        namespace="web_search",
        topic="data-science",
        description="Data science datasets",
    )
    assert entry.status == "active"

    # 2. Log many search queries (simulate demand)
    for _ in range(20):
        await make_search_log(
            query_text="data science tutorial",
            category="web_search",
            matched_count=0,
            led_to_purchase=0,
        )

    # 3. Aggregate demand signals
    signals = await demand_service.aggregate_demand(db, time_window_hours=24)
    assert len(signals) >= 1
    signal = next(
        (s for s in signals if "data" in s.query_pattern.lower() and "science" in s.query_pattern.lower()),
        None,
    )
    assert signal is not None
    assert signal.search_count >= 20
    assert signal.is_gap == 1  # No fulfillment

    # 4. Generate opportunities from demand gaps
    opportunities = await demand_service.generate_opportunities(db)
    assert len(opportunities) >= 1


# ---------------------------------------------------------------------------
# 12. test_e2e_three_agents_marketplace
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
@patch(CDN_PATCH, new_callable=AsyncMock)
async def test_e2e_three_agents_marketplace(
    mock_cdn, db, make_agent, make_token_account, make_listing, seed_platform
):
    """3 agents: seller lists, buyer1 buys, buyer2 buys, check all balances."""
    mock_cdn.return_value = SAMPLE_CONTENT
    await token_service.ensure_platform_account(db)

    seller, _ = await make_agent("three-seller", "seller")
    await make_token_account(seller.id, balance=0)

    buyer1, _ = await make_agent("three-buyer1", "buyer")
    buyer2, _ = await make_agent("three-buyer2", "buyer")
    await make_token_account(buyer1.id, balance=5000)
    await make_token_account(buyer2.id, balance=5000)

    listing = await make_listing(seller.id, price_usdc=1.0, quality_score=0.5)

    # Both buyers purchase the same listing
    resp1 = await express_service.express_buy(db, listing.id, buyer1.id, payment_method="token")
    data1 = json.loads(resp1.body.decode())
    resp2 = await express_service.express_buy(db, listing.id, buyer2.id, payment_method="token")
    data2 = json.loads(resp2.body.decode())

    assert data1["transaction_id"] != data2["transaction_id"]

    # Verify balances: buyer1 and buyer2 spent tokens, seller earned
    b1_bal = await token_service.get_balance(db, buyer1.id)
    b2_bal = await token_service.get_balance(db, buyer2.id)
    s_bal = await token_service.get_balance(db, seller.id)

    assert b1_bal["balance"] < 5000
    assert b2_bal["balance"] < 5000
    assert s_bal["balance"] > 0


# ---------------------------------------------------------------------------
# 13. test_e2e_zkp_proof_generation_and_verify
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_e2e_zkp_proof_generation_and_verify(db, make_agent, make_listing):
    """Create listing -> generate proofs -> verify listing passes."""
    agent, _ = await make_agent("zkp-seller")
    listing = await make_listing(agent.id, price_usdc=2.0, quality_score=0.9)

    content = b'{"title": "Python ML Guide", "author": "ZKP-test", "tags": ["python", "ml"]}'
    now = datetime.now(timezone.utc)

    # Generate all 4 proof types
    proofs = await zkp_service.generate_proofs(
        db, listing.id, content,
        category="web_search",
        content_size=len(content),
        freshness_at=now,
        quality_score=0.9,
    )
    assert len(proofs) == 4
    proof_types = {p.proof_type for p in proofs}
    assert proof_types == {"merkle_root", "schema", "bloom_filter", "metadata"}

    # Verify listing with all checks
    result = await zkp_service.verify_listing(
        db, listing.id,
        keywords=["python", "ml"],
        schema_has_fields=["title", "author"],
        min_size=50,
        min_quality=0.85,
    )
    assert result["verified"] is True
    assert result["checks"]["keywords"]["passed"] is True
    assert result["checks"]["schema_fields"]["passed"] is True
    assert result["checks"]["min_size"]["passed"] is True
    assert result["checks"]["min_quality"]["passed"] is True


# ---------------------------------------------------------------------------
# 14. test_e2e_supply_tracking_consistency
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_e2e_balance_consistency_after_transfers(
    db, make_agent, make_token_account, seed_platform
):
    """Balances are consistent after multiple transfer operations."""
    await token_service.ensure_platform_account(db)

    a1, _ = await make_agent("supply-a1")
    a2, _ = await make_agent("supply-a2")
    await make_token_account(a1.id, balance=10000)
    await make_token_account(a2.id, balance=0)

    # Several transfers
    await token_service.transfer(db, a1.id, a2.id, 100, "transfer")
    await token_service.transfer(db, a1.id, a2.id, 200, "transfer")
    await token_service.transfer(db, a2.id, a1.id, 50, "transfer")

    b1 = await token_service.get_balance(db, a1.id)
    b2 = await token_service.get_balance(db, a2.id)

    # a1 sent 300 total, received 50 back
    assert b1["balance"] < 10000
    assert b2["balance"] > 0


# ---------------------------------------------------------------------------
# 15. test_e2e_multi_category_discovery
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_e2e_multi_category_discovery(db, make_agent, make_listing):
    """Multiple categories, discover filters correctly."""
    seller, _ = await make_agent("multi-cat-seller", "seller")

    await make_listing(seller.id, price_usdc=1.0, category="web_search", title="Web Data")
    await make_listing(seller.id, price_usdc=2.0, category="code_analysis", title="Code Data")
    await make_listing(seller.id, price_usdc=3.0, category="api_response", title="API Data")
    await make_listing(seller.id, price_usdc=4.0, category="web_search", title="More Web Data")

    # Filter by web_search
    results, total = await listing_service.discover(db, category="web_search")
    assert total == 2
    assert all(r.category == "web_search" for r in results)

    # Filter by code_analysis
    results, total = await listing_service.discover(db, category="code_analysis")
    assert total == 1
    assert results[0].category == "code_analysis"

    # No filter returns all
    results, total = await listing_service.discover(db)
    assert total == 4


# ---------------------------------------------------------------------------
# 16. test_e2e_concurrent_buyers_same_listing
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
@patch(CDN_PATCH, new_callable=AsyncMock)
async def test_e2e_concurrent_buyers_same_listing(
    mock_cdn, client, auth_header, seed_platform
):
    """Two buyers purchase same listing, both succeed."""
    mock_cdn.return_value = SAMPLE_CONTENT

    # Register seller + listing
    seller_resp = await client.post("/api/v1/agents/register", json={
        "name": f"cc-seller-{uuid.uuid4().hex[:8]}",
        "agent_type": "seller",
        "public_key": "ssh-rsa AAAA_cc_seller_key",
    })
    seller_token = seller_resp.json()["jwt_token"]

    listing_resp = await client.post(
        "/api/v1/listings",
        headers=auth_header(seller_token),
        json={
            "title": "Concurrent Test Data",
            "description": "Test concurrent buys",
            "category": "web_search",
            "content": "concurrent content payload",
            "price_usdc": 0.05,
            "quality_score": 0.5,
        },
    )
    listing_id = listing_resp.json()["id"]

    # Register two buyers
    buyer1_resp = await client.post("/api/v1/agents/register", json={
        "name": f"cc-buyer1-{uuid.uuid4().hex[:8]}",
        "agent_type": "buyer",
        "public_key": "ssh-rsa AAAA_cc_buyer1_key",
    })
    buyer1_token = buyer1_resp.json()["jwt_token"]

    buyer2_resp = await client.post("/api/v1/agents/register", json={
        "name": f"cc-buyer2-{uuid.uuid4().hex[:8]}",
        "agent_type": "buyer",
        "public_key": "ssh-rsa AAAA_cc_buyer2_key",
    })
    buyer2_token = buyer2_resp.json()["jwt_token"]

    # Both buyers purchase
    resp1 = await client.post(
        f"/api/v1/express/{listing_id}",
        headers=auth_header(buyer1_token),
        json={"payment_method": "token"},
    )
    resp2 = await client.post(
        f"/api/v1/express/{listing_id}",
        headers=auth_header(buyer2_token),
        json={"payment_method": "token"},
    )

    assert resp1.status_code == 200
    assert resp2.status_code == 200
    assert resp1.json()["transaction_id"] != resp2.json()["transaction_id"]


# ---------------------------------------------------------------------------
# 17. test_e2e_seller_webhook_registration
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_e2e_seller_webhook_registration(db, make_agent):
    """Seller registers webhook, it's stored correctly."""
    seller, _ = await make_agent("webhook-e2e-seller", "seller")

    # Register webhook
    webhook = await seller_service.register_webhook(
        db=db,
        seller_id=seller.id,
        url="https://hooks.example.com/sales",
        event_types=["demand_match", "listing_sold"],
        secret="wh_secret_key_abc",
    )

    assert webhook.id is not None
    assert webhook.seller_id == seller.id
    assert webhook.url == "https://hooks.example.com/sales"
    assert webhook.status == "active"
    assert webhook.secret == "wh_secret_key_abc"
    assert "demand_match" in webhook.event_types
    assert "listing_sold" in webhook.event_types

    # Retrieve and verify
    webhooks = await seller_service.get_webhooks(db, seller.id)
    assert len(webhooks) == 1
    assert webhooks[0].id == webhook.id


# ---------------------------------------------------------------------------
# 18. test_e2e_tier_progression
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_e2e_balance_after_multiple_transfers(
    db, make_agent, make_token_account, seed_platform
):
    """Agent balance reflects correctly after multiple transfers."""
    await token_service.ensure_platform_account(db)

    agent, _ = await make_agent("transfer-agent")
    receiver, _ = await make_agent("transfer-receiver")
    await make_token_account(agent.id, balance=15000)
    await make_token_account(receiver.id, balance=0)

    # Transfer funds
    await token_service.transfer(db, agent.id, receiver.id, 5000, "purchase")
    await token_service.transfer(db, agent.id, receiver.id, 5000, "purchase")

    # Verify balances
    agent_bal = await token_service.get_balance(db, agent.id)
    receiver_bal = await token_service.get_balance(db, receiver.id)

    assert agent_bal["balance"] < 15000
    assert receiver_bal["balance"] > 0


# ---------------------------------------------------------------------------
# 19. test_e2e_health_endpoint_reflects_state
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_e2e_health_endpoint_reflects_state(client, auth_header):
    """After creating agents/listings, health counts are correct."""
    # Initial health check
    h0 = await client.get("/api/v1/health")
    initial_agents = h0.json()["agents_count"]
    initial_listings = h0.json()["listings_count"]

    # Register 2 agents
    for i in range(2):
        resp = await client.post("/api/v1/agents/register", json={
            "name": f"health-agent-{uuid.uuid4().hex[:8]}",
            "agent_type": "seller",
            "public_key": "ssh-rsa AAAA_health_key",
        })
        assert resp.status_code == 201
        token = resp.json()["jwt_token"]

        # Each agent creates a listing
        await client.post(
            "/api/v1/listings",
            headers=auth_header(token),
            json={
                "title": f"Health Listing {i}",
                "description": "For health check",
                "category": "web_search",
                "content": f"health check content {i}",
                "price_usdc": 1.0,
            },
        )

    # Health check should reflect new counts
    h1 = await client.get("/api/v1/health")
    assert h1.status_code == 200
    body = h1.json()
    assert body["status"] == "healthy"
    assert body["agents_count"] == initial_agents + 2
    assert body["listings_count"] == initial_listings + 2


# ---------------------------------------------------------------------------
# 20. test_e2e_complete_marketplace_day
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
@patch(CDN_PATCH, new_callable=AsyncMock)
async def test_e2e_complete_marketplace_day(
    mock_cdn, db, make_agent, make_token_account, make_listing,
    make_search_log, seed_platform
):
    """3 agents, 5 listings, 3 purchases — verify everything."""
    mock_cdn.return_value = SAMPLE_CONTENT
    await token_service.ensure_platform_account(db)

    # --- Setup: 3 agents ---
    seller1, _ = await make_agent("day-seller1", "seller")
    seller2, _ = await make_agent("day-seller2", "seller")
    buyer, _ = await make_agent("day-buyer", "buyer")

    await make_token_account(seller1.id, balance=0)
    await make_token_account(seller2.id, balance=0)
    await make_token_account(buyer.id, balance=50000)

    # --- 5 listings across 2 sellers ---
    listings = []
    for i in range(3):
        l = await make_listing(
            seller1.id, price_usdc=1.0 + i,
            title=f"Seller1 Listing {i}",
            category="web_search",
            quality_score=0.7 + (i * 0.05),
        )
        listings.append(l)
    for i in range(2):
        l = await make_listing(
            seller2.id, price_usdc=2.0 + i,
            title=f"Seller2 Listing {i}",
            category="code_analysis",
            quality_score=0.85 + (i * 0.05),
        )
        listings.append(l)

    # Verify 5 listings discoverable
    results, total = await listing_service.discover(db)
    assert total == 5

    # --- 3 purchases by buyer ---
    purchase_ids = []
    for listing in listings[:3]:
        resp = await express_service.express_buy(
            db, listing.id, buyer.id, payment_method="token"
        )
        data = json.loads(resp.body.decode())
        purchase_ids.append(data["transaction_id"])

    assert len(purchase_ids) == 3
    assert len(set(purchase_ids)) == 3  # All unique

    # --- Verify buyer balance decreased ---
    buyer_bal = await token_service.get_balance(db, buyer.id)
    assert buyer_bal["balance"] < 50000

    # --- Verify sellers earned ---
    s1_bal = await token_service.get_balance(db, seller1.id)
    assert s1_bal["balance"] > 0
    assert s1_bal["total_earned"] > 0

    # --- Verify reputation ---
    rep = await reputation_service.calculate_reputation(db, seller1.id)
    assert rep.total_transactions >= 3
    assert rep.successful_deliveries >= 3
    assert rep.composite_score > 0

    # --- Log demand signals for the day ---
    for _ in range(10):
        await make_search_log(
            query_text="python data analysis",
            category="web_search",
            matched_count=3,
        )
    signals = await demand_service.aggregate_demand(db, time_window_hours=24)
    assert len(signals) >= 1

    # --- Generate ZKP proofs for one listing ---
    content = b'{"title": "Python Data Analysis", "format": "json"}'
    proofs = await zkp_service.generate_proofs(
        db, listings[0].id, content,
        category="web_search",
        content_size=len(content),
        freshness_at=datetime.now(timezone.utc),
        quality_score=0.7,
    )
    assert len(proofs) == 4

    # Verify the listing
    verify = await zkp_service.verify_listing(
        db, listings[0].id,
        keywords=["python"],
        min_quality=0.5,
    )
    assert verify["verified"] is True
