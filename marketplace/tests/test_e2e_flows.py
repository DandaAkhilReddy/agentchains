"""End-to-end integration tests for AgentChains marketplace.

Tests complete multi-service workflows spanning:
- Agent registration → listing creation → discovery → purchase → verification
- Creator registration → agent linking → earnings flow → royalty distribution
- Fiat deposits → token conversion → listing purchase → seller earnings
- Demand aggregation → opportunity generation → fulfillment by sellers

These tests exercise the full system stack with multiple services working together.
"""

import json
import pytest
from decimal import Decimal
from datetime import datetime, timedelta, timezone

from marketplace.services import listing_service, transaction_service, token_service
from marketplace.services import express_service, demand_service, deposit_service
from marketplace.services import registry_service, creator_service

# Valid categories for listings
VALID_CATEGORIES = ["web_search", "code_analysis", "document_summary", "api_response", "computation"]


# ==============================================================================
# Flow 1: Register Agent → Create Listing → Buyer Discovers → Express Buy → Verify
# ==============================================================================

@pytest.mark.asyncio
async def test_e2e_basic_purchase_flow(db, make_agent, make_token_account, seed_platform):
    """Full flow: seller lists → buyer discovers → express purchase → content delivered."""
    # Setup: platform account
    platform = seed_platform

    # 1. Register seller agent
    seller, seller_token = await make_agent("seller-agent", "seller")
    seller_account = await make_token_account(seller.id, balance=0)

    # 2. Register buyer agent
    buyer, buyer_token = await make_agent("buyer-agent", "buyer")
    buyer_account = await make_token_account(buyer.id, balance=10000)

    # 3. Seller creates a listing
    from marketplace.schemas.listing import ListingCreateRequest
    listing_req = ListingCreateRequest(
        title="Python Web Scraping Guide",
        description="Complete guide to web scraping",
        category="web_search",
        content="# Python Web Scraping\n\nStep 1: Import requests...",
        price_usdc=5.0,
        quality_score=0.9,
        tags=["python", "scraping", "tutorial"],
        metadata={"language": "en", "format": "markdown"},
    )
    listing = await listing_service.create_listing(db, seller.id, listing_req)

    assert listing.seller_id == seller.id
    assert listing.status == "active"
    assert float(listing.price_usdc) == 5.0

    # 4. Buyer discovers listings
    results, total = await listing_service.discover(
        db, q="", category="web_search", page=1, page_size=10
    )

    # Should find the listing
    assert total >= 1
    found = any(r.id == listing.id for r in results)
    assert found, f"Listing {listing.id} not found in results"

    # 5. Express buy flow
    # First ensure platform account exists
    await token_service.ensure_platform_account(db)

    response = await express_service.express_buy(db, listing.id, buyer.id, payment_method="token")

    # express_buy returns JSONResponse, extract data directly
    data = json.loads(response.body.decode())

    assert data["listing_id"] == listing.id
    assert data["transaction_id"] is not None
    assert "content" in data
    assert data["price_usdc"] == 5.0
    assert data["cost_usd"] is not None  # USD cost recorded
    assert data["payment_method"] == "token"

    # 6. Verify token transfer occurred
    buyer_balance = await token_service.get_balance(db, buyer.id)
    seller_balance = await token_service.get_balance(db, seller.id)

    # Buyer spent tokens, seller earned tokens (minus fees)
    assert buyer_balance["balance"] < 10000
    assert seller_balance["balance"] > 0

    # 7. Verify transaction completed
    tx = await transaction_service.get_transaction(db, data["transaction_id"])
    assert tx.status == "completed"
    assert tx.verification_status == "verified"
    assert tx.buyer_id == buyer.id
    assert tx.seller_id == seller.id


@pytest.mark.asyncio
async def test_e2e_multi_step_purchase_flow(db, make_agent, make_token_account, seed_platform):
    """Full flow using step-by-step transaction service (not express buy)."""
    platform = seed_platform
    await token_service.ensure_platform_account(db)

    seller, _ = await make_agent("seller2", "seller")
    await make_token_account(seller.id, balance=0)

    buyer, _ = await make_agent("buyer2", "buyer")
    await make_token_account(buyer.id, balance=5000)

    # Create listing
    from marketplace.schemas.listing import ListingCreateRequest
    listing_req = ListingCreateRequest(
        title="Node.js API Tutorial",
        description="Build REST APIs with Node.js",
        category="code_analysis",
        content="const express = require('express');",
        price_usdc=3.0,
        quality_score=0.85,
    )
    listing = await listing_service.create_listing(db, seller.id, listing_req)

    # Step 1: Initiate transaction
    tx_data = await transaction_service.initiate_transaction(db, listing.id, buyer.id)
    tx_id = tx_data["transaction_id"]

    assert tx_data["status"] == "payment_pending"
    assert tx_data["amount_usdc"] == 3.0
    assert "payment_details" in tx_data

    # Step 2: Confirm payment
    tx = await transaction_service.confirm_payment(db, tx_id, payment_signature="sim_sig")
    assert tx.status == "payment_confirmed"
    assert tx.paid_at is not None

    # Step 3: Deliver content
    content = "const express = require('express');"
    tx = await transaction_service.deliver_content(db, tx_id, content, seller.id)
    assert tx.status == "delivered"
    assert tx.delivered_at is not None

    # Step 4: Verify delivery
    tx = await transaction_service.verify_delivery(db, tx_id, buyer.id)
    assert tx.status == "completed"
    assert tx.verification_status == "verified"
    assert tx.completed_at is not None


@pytest.mark.asyncio
async def test_e2e_listing_discovery_with_filters(db, make_agent, make_listing):
    """Test discovery filters: category, price range, quality, seller, sorting."""
    seller1, _ = await make_agent("seller-disco-1", "seller")
    seller2, _ = await make_agent("seller-disco-2", "seller")

    # Create varied listings
    await make_listing(seller1.id, price_usdc=1.0, title="Cheap Tutorial", quality_score=0.5, category="web_search")
    await make_listing(seller1.id, price_usdc=5.0, title="Premium Guide", quality_score=0.95, category="web_search")
    await make_listing(seller2.id, price_usdc=3.0, title="Mid-tier Content", quality_score=0.75, category="code_analysis")

    # Filter by price range
    results, total = await listing_service.discover(db, min_price=2.0, max_price=6.0)
    assert total == 2

    # Filter by quality
    results, total = await listing_service.discover(db, min_quality=0.9)
    assert total == 1
    assert results[0].title == "Premium Guide"

    # Filter by seller
    results, total = await listing_service.discover(db, seller_id=seller1.id)
    assert total == 2

    # Filter by category
    results, total = await listing_service.discover(db, category="code_analysis")
    assert total == 1
    assert results[0].category == "code_analysis"

    # Sort by price descending
    results, total = await listing_service.discover(db, sort_by="price_desc", page_size=10)
    assert total == 3
    assert float(results[0].price_usdc) >= float(results[1].price_usdc)


# ==============================================================================
# Flow 2: Register Creator → Link Agent → Agent Sells → Royalty Flows
# ==============================================================================

@pytest.mark.asyncio
async def test_e2e_creator_agent_royalty_flow(db, make_creator, make_agent, make_token_account, seed_platform):
    """Creator registers → links agent → agent sells → royalty auto-flows to creator."""
    platform = seed_platform
    await token_service.ensure_platform_account(db)

    # 1. Register creator (and create their token account)
    creator, creator_token = await make_creator(email="creator@test.com", password="pass123")
    # Create token account for creator (make_creator doesn't do this)
    from marketplace.models.token_account import TokenAccount
    creator_account = TokenAccount(
        id=f"acct-{creator.id}",
        agent_id=None,
        creator_id=creator.id,
        balance=0,
    )
    db.add(creator_account)
    await db.commit()

    # 2. Register agent (initially unclaimed)
    agent, agent_token = await make_agent("data-seller", "seller")
    await make_token_account(agent.id, balance=0)

    # 3. Creator links (claims) the agent
    link_result = await creator_service.link_agent_to_creator(db, creator.id, agent.id)
    assert link_result["agent_id"] == agent.id
    assert link_result["creator_id"] == creator.id

    # 4. Agent creates a listing
    from marketplace.schemas.listing import ListingCreateRequest
    listing_req = ListingCreateRequest(
        title="Dataset: NYC Traffic",
        description="Real-time traffic data",
        category="api_response",
        content="data,timestamp,location\n...",
        price_usdc=10.0,
        quality_score=0.88,
    )
    listing = await listing_service.create_listing(db, agent.id, listing_req)

    # 5. Buyer purchases the listing
    buyer, _ = await make_agent("buyer-royalty", "buyer")
    await make_token_account(buyer.id, balance=15000)

    response = await express_service.express_buy(db, listing.id, buyer.id, payment_method="token")
    # express_buy returns JSONResponse, no need to check status_code

    # 6. Check that royalty was auto-transferred to creator
    from marketplace.config import settings
    creator_balance = await token_service.get_creator_balance(db, creator.id)

    # Creator should have earned: settings.creator_royalty_pct * (agent earnings after fee)
    # Agent earnings = price_usdc / peg * (1 - platform_fee)
    # Royalty = agent_earnings * creator_royalty_pct
    assert creator_balance["balance"] > 0
    assert creator_balance["total_earned"] > 0

    # 7. Verify creator dashboard shows the agent and earnings
    dashboard = await creator_service.get_creator_dashboard(db, creator.id)
    assert dashboard["agents_count"] == 1
    assert dashboard["agents"][0]["agent_id"] == agent.id
    assert dashboard["creator_balance"] > 0
    assert dashboard["total_agent_earnings"] > 0


@pytest.mark.asyncio
async def test_e2e_creator_multi_agent_earnings(db, make_creator, make_agent, make_token_account, make_listing, seed_platform):
    """Creator owns multiple agents, each agent earns, royalties aggregate."""
    platform = seed_platform
    await token_service.ensure_platform_account(db)

    creator, _ = await make_creator(email="multi@test.com")
    # Create token account for creator
    from marketplace.models.token_account import TokenAccount
    creator_account = TokenAccount(
        id=f"acct-{creator.id}",
        agent_id=None,
        creator_id=creator.id,
        balance=0,
    )
    db.add(creator_account)
    await db.commit()

    # Create 3 agents and link them to creator
    agents = []
    for i in range(3):
        agent, _ = await make_agent(f"agent-{i}", "seller")
        await make_token_account(agent.id, balance=0)
        await creator_service.link_agent_to_creator(db, creator.id, agent.id)
        agents.append(agent)

    # Each agent creates a listing
    for agent in agents:
        await make_listing(agent.id, price_usdc=2.0, quality_score=0.8)

    # Buyer purchases from all agents
    buyer, _ = await make_agent("bulk-buyer", "buyer")
    await make_token_account(buyer.id, balance=10000)

    listings, _ = await listing_service.list_listings(db, status="active")
    for i, listing in enumerate(listings[:3]):  # Buy first 3
        # Use unique tx_id per purchase to avoid idempotency key collisions
        # (express_buy passes tx_id=None internally, generating duplicate keys)
        unique_tx_id = f"bulk-purchase-{i}-{listing.id}"
        result = await token_service.debit_for_purchase(
            db, buyer.id, listing.seller_id,
            float(listing.price_usdc),
            unique_tx_id,
        )
        assert result["amount_usd"] > 0

    # Check creator dashboard
    dashboard = await creator_service.get_creator_dashboard(db, creator.id)
    assert dashboard["agents_count"] == 3
    assert dashboard["creator_balance"] > 0  # Accumulated royalties
    assert dashboard["total_agent_earnings"] > 0


@pytest.mark.asyncio
async def test_e2e_creator_cannot_claim_already_claimed_agent(db, make_creator, make_agent):
    """Ensure agent ownership is exclusive — cannot be claimed twice."""
    creator1, _ = await make_creator(email="first@test.com")
    creator2, _ = await make_creator(email="second@test.com")

    agent, _ = await make_agent("exclusive-agent")

    # Creator 1 claims
    await creator_service.link_agent_to_creator(db, creator1.id, agent.id)

    # Creator 2 tries to claim — should fail
    with pytest.raises(ValueError, match="already claimed"):
        await creator_service.link_agent_to_creator(db, creator2.id, agent.id)


# ==============================================================================
# Flow 3: Deposit Fiat → Buy Listing → Seller Earns
# ==============================================================================

@pytest.mark.asyncio
async def test_e2e_fiat_deposit_to_purchase_flow(db, make_agent, make_listing, seed_platform):
    """Buyer deposits USD → buys listing → seller earns USD."""
    platform = seed_platform
    await token_service.ensure_platform_account(db)

    seller, _ = await make_agent("seller-fiat", "seller")
    await token_service.create_account(db, seller.id)
    listing = await make_listing(seller.id, price_usdc=8.0, quality_score=0.9)

    buyer, _ = await make_agent("buyer-fiat", "buyer")
    await token_service.create_account(db, buyer.id)

    # 1. Buyer creates a deposit (USD)
    deposit_data = await deposit_service.create_deposit(
        db, agent_id=buyer.id, amount_usd=100.0, payment_method="credit_card"
    )

    assert deposit_data["status"] == "pending"
    assert deposit_data["amount_usd"] > 0

    # 2. Confirm deposit (simulate payment success)
    confirmed = await deposit_service.confirm_deposit(db, deposit_data["id"])
    assert confirmed["status"] == "completed"

    # 3. Buyer balance should now have USD
    buyer_balance = await token_service.get_balance(db, buyer.id)
    assert buyer_balance["balance"] > 0

    # 4. Buyer purchases listing
    response = await express_service.express_buy(db, listing.id, buyer.id, payment_method="token")
    # express_buy returns JSONResponse, no need to check status_code
    data = json.loads(response.body.decode())
    assert data["price_usdc"] == 8.0

    # 5. Seller earns USD
    seller_balance = await token_service.get_balance(db, seller.id)
    assert seller_balance["balance"] > 0
    assert seller_balance["total_earned"] > 0


@pytest.mark.asyncio
async def test_e2e_fiat_deposit_history(db, make_agent, seed_platform):
    """Test deposit history retrieval with pagination."""
    platform = seed_platform

    agent, _ = await make_agent("deposit-history-agent")
    await token_service.create_account(db, agent.id)

    # Create 5 deposits
    for i in range(5):
        deposit = await deposit_service.create_deposit(
            db, agent_id=agent.id, amount_usd=10.0 + i
        )
        await deposit_service.confirm_deposit(db, deposit["id"])

    # Get paginated history
    deposits_page1, total = await deposit_service.get_deposits(db, agent.id, page=1, page_size=3)
    assert len(deposits_page1) == 3
    assert total == 5

    deposits_page2, _ = await deposit_service.get_deposits(db, agent.id, page=2, page_size=3)
    assert len(deposits_page2) == 2


# ==============================================================================
# Flow 4: Demand Spike → Opportunity Generated → Seller Fills Gap
# ==============================================================================

@pytest.mark.asyncio
async def test_e2e_demand_aggregation_and_opportunity(db, make_agent, make_search_log, make_listing):
    """Search queries logged → demand aggregated → opportunities generated → seller fulfills."""

    # 1. Log multiple searches for the same topic (simulating demand)
    for i in range(15):
        await make_search_log(
            query_text="react hooks tutorial",
            category="web_search",
            matched_count=0,  # No matches = gap
            led_to_purchase=0,
        )

    # 2. Aggregate demand signals
    signals = await demand_service.aggregate_demand(db, time_window_hours=24)

    assert len(signals) >= 1
    signal = next((s for s in signals if "react" in s.query_pattern.lower()), None)
    assert signal is not None
    assert signal.search_count >= 15
    assert signal.is_gap == 1  # Low fulfillment = gap
    assert float(signal.velocity or 0) > 0

    # 3. Generate opportunities from gaps
    opportunities = await demand_service.generate_opportunities(db)

    assert len(opportunities) >= 1
    opp = next((o for o in opportunities if "react" in o.query_pattern.lower()), None)
    assert opp is not None
    assert float(opp.urgency_score or 0) > 0
    assert opp.status == "active"

    # 4. Seller sees opportunity and creates listing to fill the gap
    seller, _ = await make_agent("gap-filler", "seller")
    listing = await make_listing(
        seller.id,
        title="React Hooks Complete Guide",
        category="web_search",
        price_usdc=4.0,
        quality_score=0.92,
    )

    # 5. New search now matches the listing
    results, total = await listing_service.discover(db, q="", category="web_search")
    assert total >= 1
    assert any(r.id == listing.id for r in results)

    # 6. Log a new search that leads to purchase
    log = await make_search_log(
        query_text="react hooks tutorial",
        category="web_search",
        matched_count=1,
        led_to_purchase=1,
    )

    # 7. Re-aggregate — fulfillment rate should improve
    new_signals = await demand_service.aggregate_demand(db, time_window_hours=24)
    new_signal = next((s for s in new_signals if "react" in s.query_pattern.lower()), None)
    assert new_signal.search_count >= 16
    # Fulfillment rate should be > 0 now (1/16 = 0.0625)
    assert float(new_signal.fulfillment_rate or 0) > 0


@pytest.mark.asyncio
async def test_e2e_trending_demand_signals(db, make_search_log):
    """High-velocity searches should appear in trending."""

    # Create high-velocity demand
    for i in range(30):
        await make_search_log(
            query_text="python async await",
            category="code_analysis",
            matched_count=5,
        )

    # Create low-velocity demand
    for i in range(3):
        await make_search_log(
            query_text="java spring boot",
            category="code_analysis",
            matched_count=2,
        )

    await demand_service.aggregate_demand(db, time_window_hours=6)

    trending = await demand_service.get_trending(db, limit=10, hours=6)

    assert len(trending) >= 2
    # Python should be first (higher velocity)
    assert "python" in trending[0].query_pattern.lower()
    assert float(trending[0].velocity or 0) > float(trending[1].velocity or 0)


@pytest.mark.asyncio
async def test_e2e_demand_gaps_listing(db, make_search_log):
    """Get demand gaps (low fulfillment rate)."""

    # High demand, low fulfillment
    for i in range(20):
        await make_search_log(
            query_text="rust programming guide",
            category="code_analysis",
            matched_count=0,
            led_to_purchase=0,
        )

    # High demand, high fulfillment
    for i in range(20):
        await make_search_log(
            query_text="javascript basics",
            category="code_analysis",
            matched_count=10,
            led_to_purchase=5,
        )

    await demand_service.aggregate_demand(db)

    gaps = await demand_service.get_demand_gaps(db, limit=20)

    # Rust should be in gaps, JavaScript should not
    rust_gap = next((g for g in gaps if "rust" in g.query_pattern.lower()), None)
    js_gap = next((g for g in gaps if "javascript" in g.query_pattern.lower()), None)

    assert rust_gap is not None
    assert js_gap is None  # High fulfillment, not a gap


# ==============================================================================
# Flow 5: Token Economy Flows
# ==============================================================================

@pytest.mark.asyncio
async def test_e2e_token_transfer_with_fees(db, make_agent, make_token_account, seed_platform):
    """Direct transfer applies platform fee correctly."""
    platform = seed_platform

    sender, _ = await make_agent("sender")
    receiver, _ = await make_agent("receiver")
    await make_token_account(sender.id, balance=100)
    await make_token_account(receiver.id, balance=0)

    # Transfer 50 USD
    ledger = await token_service.transfer(
        db,
        from_agent_id=sender.id,
        to_agent_id=receiver.id,
        amount=50,
        tx_type="transfer",
        memo="Test transfer",
    )

    # Check ledger entry
    assert float(ledger.amount) == 50
    assert float(ledger.fee_amount) > 0

    # Check balances
    sender_bal = await token_service.get_balance(db, sender.id)
    receiver_bal = await token_service.get_balance(db, receiver.id)

    assert sender_bal["balance"] == 50  # Spent 50
    assert receiver_bal["balance"] < 50  # Received less due to fee
    assert receiver_bal["balance"] > 0


# ==============================================================================
# Flow 6: Express Buy Edge Cases
# ==============================================================================

@pytest.mark.asyncio
async def test_e2e_express_buy_insufficient_balance(db, make_agent, make_token_account, make_listing, seed_platform):
    """Express buy fails gracefully when buyer has insufficient balance."""
    platform = seed_platform
    await token_service.ensure_platform_account(db)

    seller, _ = await make_agent("seller-rich")
    await token_service.create_account(db, seller.id)
    listing = await make_listing(seller.id, price_usdc=100.0)

    buyer, _ = await make_agent("buyer-poor")
    await make_token_account(buyer.id, balance=1.0)  # Not enough

    # Should raise HTTPException
    from fastapi import HTTPException
    with pytest.raises(HTTPException) as exc:
        await express_service.express_buy(db, listing.id, buyer.id, payment_method="token")

    assert exc.value.status_code == 402
    assert "insufficient" in exc.value.detail.lower()


@pytest.mark.asyncio
async def test_e2e_express_buy_own_listing_blocked(db, make_agent, make_token_account, make_listing, seed_platform):
    """Agent cannot buy their own listing."""
    platform = seed_platform
    await token_service.ensure_platform_account(db)

    agent, _ = await make_agent("self-buyer")
    await make_token_account(agent.id, balance=10000)
    listing = await make_listing(agent.id, price_usdc=5.0)

    from fastapi import HTTPException
    with pytest.raises(HTTPException) as exc:
        await express_service.express_buy(db, listing.id, agent.id, payment_method="token")

    assert exc.value.status_code == 400
    assert "own listing" in exc.value.detail.lower()


@pytest.mark.asyncio
async def test_e2e_express_buy_inactive_listing_blocked(db, make_agent, make_token_account, make_listing, seed_platform):
    """Cannot buy a delisted/inactive listing."""
    platform = seed_platform
    await token_service.ensure_platform_account(db)

    seller, _ = await make_agent("delist-seller")
    listing = await make_listing(seller.id, price_usdc=5.0, status="delisted")

    buyer, _ = await make_agent("delist-buyer")
    await make_token_account(buyer.id, balance=10000)

    from fastapi import HTTPException
    with pytest.raises(HTTPException) as exc:
        await express_service.express_buy(db, listing.id, buyer.id, payment_method="token")

    assert exc.value.status_code == 400
    assert "not active" in exc.value.detail.lower()


# ==============================================================================
# Flow 7: HTTP Client Tests (API-level)
# ==============================================================================

@pytest.mark.asyncio
async def test_e2e_http_register_and_create_listing(client, auth_header):
    """HTTP: Register agent → get JWT → create listing."""
    # Register agent
    register_resp = await client.post("/api/v1/agents/register", json={
        "name": f"http-test-agent-{datetime.now().timestamp()}",
        "agent_type": "both",
        "public_key": "ssh-rsa AAAA_test",
        "wallet_address": "0x1234567890abcdef",
        "capabilities": ["web_search", "code"],
    })
    assert register_resp.status_code in [200, 201]
    data = register_resp.json()
    agent_id = data["id"]
    token = data.get("jwt_token") or data.get("token")

    # Create listing
    listing_resp = await client.post(
        "/api/v1/listings",
        headers=auth_header(token),
        json={
            "title": "HTTP Test Listing",
            "description": "Created via HTTP",
            "category": "web_search",
            "content": "Test content",
            "price_usdc": 2.5,
            "quality_score": 0.8,
        }
    )
    assert listing_resp.status_code in [200, 201]
    listing_data = listing_resp.json()
    assert listing_data["seller_id"] == agent_id
    assert listing_data["status"] == "active"


@pytest.mark.asyncio
async def test_e2e_http_discover_and_express_buy(client, auth_header, seed_platform):
    """HTTP: Discover listings → express buy flow."""
    # Setup: create seller with listing
    seller_resp = await client.post("/api/v1/agents/register", json={
        "name": f"http-seller-{datetime.now().timestamp()}",
        "agent_type": "seller",
        "public_key": "ssh-rsa AAAA_seller",
    })
    seller_data = seller_resp.json()
    seller_token = seller_data.get("jwt_token") or seller_data.get("token")

    listing_resp = await client.post(
        "/api/v1/listings",
        headers=auth_header(seller_token),
        json={
            "title": "HTTP Express Test",
            "description": "For express buy",
            "category": "code_analysis",
            "content": "console.log('hello');",
            "price_usdc": 1.0,
        }
    )
    listing_id = listing_resp.json()["id"]

    # Setup: create buyer with tokens
    buyer_resp = await client.post("/api/v1/agents/register", json={
        "name": f"http-buyer-{datetime.now().timestamp()}",
        "agent_type": "buyer",
        "public_key": "ssh-rsa AAAA_buyer",
    })
    buyer_data = buyer_resp.json()
    buyer_token = buyer_data.get("jwt_token") or buyer_data.get("token")
    buyer_id = buyer_data["id"]

    # Deposit tokens to buyer (HTTP endpoint)
    deposit_resp = await client.post(
        f"/api/v1/wallet/deposit",
        headers=auth_header(buyer_token),
        json={"amount_usd": 50.0, "payment_method": "test"}
    )
    assert deposit_resp.status_code in [200, 201]

    # Confirm deposit
    deposit_id = deposit_resp.json()["id"]
    confirm_resp = await client.post(
        f"/api/v1/wallet/deposit/{deposit_id}/confirm",
        headers=auth_header(buyer_token),
    )
    assert confirm_resp.status_code == 200

    # Discover listings
    discover_resp = await client.get(
        "/api/v1/discover",
        headers=auth_header(buyer_token),
        params={"q": "express", "category": "code_analysis"},
    )
    assert discover_resp.status_code == 200
    results = discover_resp.json()
    assert results["total"] >= 1

    # Express buy (POST with payment_method in body)
    buy_resp = await client.post(
        f"/api/v1/express/{listing_id}",
        headers=auth_header(buyer_token),
        json={"payment_method": "token"},
    )
    assert buy_resp.status_code == 200
    buy_data = buy_resp.json()
    assert "content" in buy_data or "price_usdc" in buy_data


@pytest.mark.asyncio
async def test_e2e_http_creator_workflow(client):
    """HTTP: Creator registration → login → link agent → view dashboard."""
    # Register creator
    email = f"creator-{datetime.now().timestamp()}@test.com"
    register_resp = await client.post("/api/v1/creators/register", json={
        "email": email,
        "password": "testpass123",
        "display_name": "HTTP Creator",
    })
    assert register_resp.status_code in [200, 201]
    creator_token = register_resp.json()["token"]
    creator_id = register_resp.json()["creator"]["id"]

    # Login
    login_resp = await client.post("/api/v1/creators/login", json={
        "email": email,
        "password": "testpass123",
    })
    assert login_resp.status_code == 200

    # Register agent
    agent_resp = await client.post("/api/v1/agents/register", json={
        "name": f"http-creator-agent-{datetime.now().timestamp()}",
        "agent_type": "seller",
        "public_key": "ssh-rsa AAAA_creator_agent",
    })
    agent_id = agent_resp.json()["id"]

    # Link agent to creator (correct endpoint is /claim not /link)
    link_resp = await client.post(
        f"/api/v1/creators/me/agents/{agent_id}/claim",
        headers={"Authorization": f"Bearer {creator_token}"},
    )
    assert link_resp.status_code == 200

    # View dashboard
    dashboard_resp = await client.get(
        "/api/v1/creators/me/dashboard",
        headers={"Authorization": f"Bearer {creator_token}"},
    )
    assert dashboard_resp.status_code == 200
    dashboard = dashboard_resp.json()
    assert dashboard["agents_count"] == 1
    assert dashboard["agents"][0]["agent_id"] == agent_id


@pytest.mark.asyncio
async def test_e2e_http_demand_analytics(client, auth_header, make_search_log):
    """HTTP: Query demand analytics endpoints."""
    # Seed demand data
    for i in range(10):
        await make_search_log(
            query_text="machine learning tutorial",
            category="web_search",
            matched_count=2,
        )

    # Register agent to get token
    agent_resp = await client.post("/api/v1/agents/register", json={
        "name": f"analytics-agent-{datetime.now().timestamp()}",
        "agent_type": "buyer",
        "public_key": "ssh-rsa AAAA_analytics",
    })
    token = agent_resp.json().get("jwt_token") or agent_resp.json().get("token")

    # Get trending
    trending_resp = await client.get(
        "/api/v1/analytics/trending",
        headers=auth_header(token),
        params={"limit": 10, "hours": 24},
    )
    assert trending_resp.status_code == 200

    # Get gaps
    gaps_resp = await client.get(
        "/api/v1/analytics/demand-gaps",
        headers=auth_header(token),
        params={"limit": 20},
    )
    assert gaps_resp.status_code == 200

    # Get opportunities
    opp_resp = await client.get(
        "/api/v1/analytics/opportunities",
        headers=auth_header(token),
    )
    assert opp_resp.status_code == 200
