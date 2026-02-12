"""Deep tests for reputation formula, leaderboard types, and earnings analytics.

20 tests covering:
- Reputation score calculation (baseline, all-completed, mixed, formula weights, volume saturation, upsert)
- Leaderboard ordering, limit, empty DB
- Earnings category grouping, timeline by day, net revenue
- AgentStats creation, helpfulness formula, capped at 1.0
- Multi-leaderboard types: helpfulness, earnings, contributors
- Primary specialization from listings
- API routes: GET /reputation/{agent_id}, GET /leaderboard
"""

import uuid
from decimal import Decimal

import pytest

from marketplace.services.reputation_service import (
    calculate_reputation,
    get_leaderboard,
    get_reputation,
)
from marketplace.services.analytics_service import (
    get_agent_stats,
    get_earnings_breakdown,
    get_multi_leaderboard,
)
from marketplace.models.transaction import Transaction


# ---------------------------------------------------------------------------
# Helper: insert a raw transaction with explicit verification_status
# ---------------------------------------------------------------------------

async def _insert_tx(db, buyer_id, seller_id, listing_id, amount=1.0,
                     status="completed", verification_status="pending"):
    from datetime import datetime, timezone
    tx = Transaction(
        id=str(uuid.uuid4()),
        listing_id=listing_id,
        buyer_id=buyer_id,
        seller_id=seller_id,
        amount_usdc=Decimal(str(amount)),
        status=status,
        verification_status=verification_status,
        content_hash=f"sha256:{'a' * 64}",
    )
    if status == "completed":
        tx.completed_at = datetime.now(timezone.utc)
    db.add(tx)
    await db.commit()
    await db.refresh(tx)
    return tx


# =============================================================================
# 1. Reputation: no-transactions baseline
# =============================================================================

async def test_reputation_no_transactions_baseline(db, make_agent):
    """Agent with zero transactions gets composite = 0.4*0 + 0.3*0 + 0.2*0.8 + 0.1*0 = 0.16."""
    agent, _ = await make_agent(name="fresh-agent")
    rep = await calculate_reputation(db, agent.id)

    assert rep.total_transactions == 0
    assert rep.successful_deliveries == 0
    assert rep.failed_deliveries == 0
    assert rep.verified_count == 0
    # delivery_rate=0/1=0, verification_rate=0/1=0, response=0.8, volume=0
    expected = round(0.4 * 0 + 0.3 * 0 + 0.2 * 0.8 + 0.1 * 0, 3)
    assert float(rep.composite_score) == expected  # 0.16


# =============================================================================
# 2. Reputation: all-completed seller
# =============================================================================

async def test_reputation_all_completed_seller(db, make_agent, make_listing):
    """Seller with all-completed, all-verified transactions gets high composite."""
    seller, _ = await make_agent(name="perfect-seller")
    buyer, _ = await make_agent(name="buyer")
    listing = await make_listing(seller.id, price_usdc=5.0)

    for _ in range(4):
        await _insert_tx(db, buyer.id, seller.id, listing.id,
                         amount=5.0, status="completed",
                         verification_status="verified")

    rep = await calculate_reputation(db, seller.id)

    assert rep.successful_deliveries == 4
    assert rep.failed_deliveries == 0
    assert rep.verified_count == 4
    assert rep.total_transactions == 4

    delivery_rate = 4 / 4  # 1.0
    verification_rate = 4 / 4  # 1.0
    volume_score = min(4 / 100, 1.0)  # 0.04
    expected = round(0.4 * delivery_rate + 0.3 * verification_rate
                     + 0.2 * 0.8 + 0.1 * volume_score, 3)
    assert float(rep.composite_score) == expected


# =============================================================================
# 3. Reputation: mixed success/failure
# =============================================================================

async def test_reputation_mixed_success_failure(db, make_agent, make_listing):
    """Seller with 3 completed and 2 failed gets appropriate delivery rate."""
    seller, _ = await make_agent(name="mixed-seller")
    buyer, _ = await make_agent(name="buyer")
    listing = await make_listing(seller.id, price_usdc=1.0)

    for _ in range(3):
        await _insert_tx(db, buyer.id, seller.id, listing.id,
                         status="completed", verification_status="verified")
    for _ in range(2):
        await _insert_tx(db, buyer.id, seller.id, listing.id,
                         status="failed", verification_status="failed")

    rep = await calculate_reputation(db, seller.id)

    assert rep.successful_deliveries == 3
    assert rep.failed_deliveries == 2
    # delivery_rate = 3/5 = 0.6
    # verification: 3 verified out of 5 total => 3/5 = 0.6
    # volume = 5/100 = 0.05
    expected = round(0.4 * 0.6 + 0.3 * 0.6 + 0.2 * 0.8 + 0.1 * 0.05, 3)
    assert float(rep.composite_score) == expected


# =============================================================================
# 4. Formula weights: 0.4*delivery + 0.3*verification + 0.2*response + 0.1*volume
# =============================================================================

async def test_reputation_formula_weights(db, make_agent, make_listing):
    """Verify the exact weight breakdown for a known scenario."""
    seller, _ = await make_agent(name="weight-test-seller")
    buyer, _ = await make_agent(name="weight-buyer")
    listing = await make_listing(seller.id, price_usdc=2.0)

    # 2 completed (1 verified, 1 not), 1 failed
    await _insert_tx(db, buyer.id, seller.id, listing.id,
                     status="completed", verification_status="verified")
    await _insert_tx(db, buyer.id, seller.id, listing.id,
                     status="completed", verification_status="pending")
    await _insert_tx(db, buyer.id, seller.id, listing.id,
                     status="failed", verification_status="failed")

    rep = await calculate_reputation(db, seller.id)

    # seller_list has all 3, delivery_rate = 2/3
    delivery_rate = 2 / 3
    # all_txns = 3, verified=1 => verification_rate = 1/3
    verification_rate = 1 / 3
    volume_score = min(3 / 100, 1.0)  # 0.03

    expected = round(0.4 * delivery_rate + 0.3 * verification_rate
                     + 0.2 * 0.8 + 0.1 * volume_score, 3)
    assert float(rep.composite_score) == expected


# =============================================================================
# 5. Volume saturates at 100 txns
# =============================================================================

async def test_reputation_volume_saturates_at_100(db, make_agent, make_listing):
    """Volume score caps at 1.0 once total transactions reach 100."""
    seller, _ = await make_agent(name="volume-seller")
    buyer, _ = await make_agent(name="volume-buyer")
    listing = await make_listing(seller.id, price_usdc=0.01)

    # Create 110 completed + verified transactions
    for _ in range(110):
        await _insert_tx(db, buyer.id, seller.id, listing.id,
                         status="completed", verification_status="verified")

    rep = await calculate_reputation(db, seller.id)

    assert rep.total_transactions == 110
    # volume_score = min(110/100, 1.0) = 1.0
    delivery_rate = 110 / 110  # 1.0
    verification_rate = 110 / 110  # 1.0
    expected = round(0.4 * 1.0 + 0.3 * 1.0 + 0.2 * 0.8 + 0.1 * 1.0, 3)
    assert float(rep.composite_score) == expected  # 0.96


# =============================================================================
# 6. Upsert: calculate twice = 1 row
# =============================================================================

async def test_reputation_upsert_idempotent(db, make_agent, make_listing):
    """Calling calculate_reputation twice produces only one DB row."""
    agent, _ = await make_agent(name="upsert-agent")
    buyer, _ = await make_agent(name="upsert-buyer")
    listing = await make_listing(agent.id, price_usdc=1.0)

    await _insert_tx(db, buyer.id, agent.id, listing.id, status="completed")

    rep1 = await calculate_reputation(db, agent.id)
    rep2 = await calculate_reputation(db, agent.id)

    # Same row
    assert rep1.id == rep2.id
    assert rep1.agent_id == rep2.agent_id

    # Verify only 1 row exists
    from sqlalchemy import select, func
    from marketplace.models.reputation import ReputationScore
    count_result = await db.execute(
        select(func.count()).where(ReputationScore.agent_id == agent.id)
    )
    assert count_result.scalar() == 1


# =============================================================================
# 7. Leaderboard: ordered by composite desc
# =============================================================================

async def test_leaderboard_ordered_by_composite_desc(db, make_agent, make_listing):
    """Leaderboard entries come back sorted by composite_score descending."""
    agents = []
    for i in range(3):
        agent, _ = await make_agent(name=f"lb-agent-{i}")
        agents.append(agent)

    buyer, _ = await make_agent(name="lb-buyer")

    # Agent 0: 0 completed (lowest), Agent 1: 2 completed, Agent 2: 5 completed
    listing0 = await make_listing(agents[0].id, price_usdc=1.0)
    listing1 = await make_listing(agents[1].id, price_usdc=1.0)
    listing2 = await make_listing(agents[2].id, price_usdc=1.0)

    for _ in range(2):
        await _insert_tx(db, buyer.id, agents[1].id, listing1.id,
                         status="completed", verification_status="verified")
    for _ in range(5):
        await _insert_tx(db, buyer.id, agents[2].id, listing2.id,
                         status="completed", verification_status="verified")

    # Calculate reputation for all
    await calculate_reputation(db, agents[0].id)
    await calculate_reputation(db, agents[1].id)
    await calculate_reputation(db, agents[2].id)

    board = await get_leaderboard(db, limit=10)

    assert len(board) == 3
    scores = [float(r.composite_score) for r in board]
    assert scores == sorted(scores, reverse=True)
    # Top should be agents[2]
    assert board[0].agent_id == agents[2].id


# =============================================================================
# 8. Leaderboard: limit param
# =============================================================================

async def test_leaderboard_limit_param(db, make_agent):
    """Leaderboard respects the limit parameter."""
    for i in range(5):
        agent, _ = await make_agent(name=f"limit-agent-{i}")
        await calculate_reputation(db, agent.id)

    board = await get_leaderboard(db, limit=2)
    assert len(board) == 2


# =============================================================================
# 9. Leaderboard: empty DB
# =============================================================================

async def test_leaderboard_empty_db(db):
    """Leaderboard returns empty list when no reputation rows exist."""
    board = await get_leaderboard(db, limit=20)
    assert board == []


# =============================================================================
# 10. Earnings: category grouping
# =============================================================================

async def test_earnings_category_grouping(db, make_agent, make_listing, make_transaction):
    """Earnings breakdown correctly groups by listing category."""
    seller, _ = await make_agent(name="cat-seller")
    buyer, _ = await make_agent(name="cat-buyer")

    l_web = await make_listing(seller.id, price_usdc=10.0, category="web_search")
    l_ml = await make_listing(seller.id, price_usdc=7.0, category="ml_models")
    l_web2 = await make_listing(seller.id, price_usdc=3.0, category="web_search")

    await make_transaction(buyer.id, seller.id, l_web.id, amount_usdc=10.0, status="completed")
    await make_transaction(buyer.id, seller.id, l_ml.id, amount_usdc=7.0, status="completed")
    await make_transaction(buyer.id, seller.id, l_web2.id, amount_usdc=3.0, status="completed")

    result = await get_earnings_breakdown(db, seller.id)

    assert result["earnings_by_category"]["web_search"] == 13.0
    assert result["earnings_by_category"]["ml_models"] == 7.0
    assert len(result["earnings_by_category"]) == 2


# =============================================================================
# 11. Earnings: timeline by day
# =============================================================================

async def test_earnings_timeline_by_day(db, make_agent, make_listing, make_transaction):
    """Timeline entries aggregate amounts for the same day."""
    seller, _ = await make_agent(name="timeline-seller")
    buyer, _ = await make_agent(name="timeline-buyer")

    listing = await make_listing(seller.id, price_usdc=5.0)

    await make_transaction(buyer.id, seller.id, listing.id, amount_usdc=5.0, status="completed")
    await make_transaction(buyer.id, seller.id, listing.id, amount_usdc=8.0, status="completed")

    result = await get_earnings_breakdown(db, seller.id)

    # Both transactions happen on the same day
    assert len(result["earnings_timeline"]) == 1
    entry = result["earnings_timeline"][0]
    assert entry["earned"] == 13.0
    assert entry["spent"] == 0.0
    assert "date" in entry


# =============================================================================
# 12. Earnings: net revenue
# =============================================================================

async def test_earnings_net_revenue(db, make_agent, make_listing, make_transaction):
    """Net revenue = total_earned - total_spent."""
    agent1, _ = await make_agent(name="net-agent1")
    agent2, _ = await make_agent(name="net-agent2")

    # agent1 sells for 20
    l1 = await make_listing(agent1.id, price_usdc=20.0)
    await make_transaction(agent2.id, agent1.id, l1.id, amount_usdc=20.0, status="completed")

    # agent1 buys for 12
    l2 = await make_listing(agent2.id, price_usdc=12.0)
    await make_transaction(agent1.id, agent2.id, l2.id, amount_usdc=12.0, status="completed")

    result = await get_earnings_breakdown(db, agent1.id)

    assert result["total_earned_usdc"] == 20.0
    assert result["total_spent_usdc"] == 12.0
    assert result["net_revenue_usdc"] == 8.0


# =============================================================================
# 13. AgentStats: creates if missing
# =============================================================================

async def test_agent_stats_creates_if_missing(db, make_agent):
    """get_agent_stats creates a new row when none exists."""
    agent, _ = await make_agent(name="stats-new")

    stats = await get_agent_stats(db, agent.id)

    assert stats.agent_id == agent.id
    assert stats.unique_buyers_served == 0
    assert stats.total_listings_created == 0
    assert stats.total_cache_hits == 0
    assert stats.last_calculated_at is not None


# =============================================================================
# 14. AgentStats: helpfulness formula
# =============================================================================

async def test_agent_stats_helpfulness_formula_exact(
    db, make_agent, make_listing, make_transaction
):
    """Verify exact helpfulness formula: 0.3*buyers + 0.3*listings + 0.2*quality + 0.2*cache."""
    seller, _ = await make_agent(name="help-seller")

    # 3 listings, quality 0.90 each
    listings = []
    for _ in range(3):
        l = await make_listing(seller.id, price_usdc=1.0,
                               quality_score=0.90, content_size=500)
        listings.append(l)

    # 2 unique buyers
    buyer1, _ = await make_agent(name="hb1")
    buyer2, _ = await make_agent(name="hb2")
    await make_transaction(buyer1.id, seller.id, listings[0].id,
                           amount_usdc=1.0, status="completed")
    await make_transaction(buyer2.id, seller.id, listings[0].id,
                           amount_usdc=1.0, status="completed")

    # Set cache hits on first listing
    listings[0].access_count = 30
    db.add(listings[0])
    await db.commit()

    stats = await get_agent_stats(db, seller.id)

    expected = min(
        0.3 * min(2 / 10, 1.0)      # buyers: 0.06
        + 0.3 * min(3 / 20, 1.0)    # listings: 0.045
        + 0.2 * 0.90                 # quality: 0.18
        + 0.2 * min(30 / 50, 1.0),  # cache: 0.12
        1.0,
    )
    assert abs(float(stats.helpfulness_score) - expected) < 0.01


# =============================================================================
# 15. AgentStats: helpfulness capped at 1.0
# =============================================================================

async def test_agent_stats_helpfulness_capped_at_one(
    db, make_agent, make_listing, make_transaction
):
    """Even with extreme inputs, helpfulness never exceeds 1.0."""
    seller, _ = await make_agent(name="cap-seller")

    # 30 listings with perfect quality
    for _ in range(30):
        l = await make_listing(seller.id, price_usdc=1.0,
                               quality_score=0.99, content_size=5000)
        l.access_count = 200
        db.add(l)
    await db.commit()

    # 20 unique buyers
    for i in range(20):
        b, _ = await make_agent(name=f"cap-buyer-{i}")
        listing_for_tx = await make_listing(seller.id, price_usdc=0.5)
        await make_transaction(b.id, seller.id, listing_for_tx.id,
                               amount_usdc=0.5, status="completed")

    stats = await get_agent_stats(db, seller.id)

    assert float(stats.helpfulness_score) <= 1.0


# =============================================================================
# 16. Multi-leaderboard: helpfulness type
# =============================================================================

async def test_multi_leaderboard_helpfulness_type(db, make_agent, make_listing):
    """Helpfulness leaderboard ranks by helpfulness_score desc."""
    a1, _ = await make_agent(name="help-high")
    a2, _ = await make_agent(name="help-low")

    # a1 gets more listings => higher helpfulness
    for _ in range(8):
        await make_listing(a1.id, quality_score=0.9, content_size=1000)
    for _ in range(2):
        await make_listing(a2.id, quality_score=0.5, content_size=100)

    await get_agent_stats(db, a1.id)
    await get_agent_stats(db, a2.id)

    board = await get_multi_leaderboard(db, "helpfulness", limit=10)

    assert len(board) == 2
    assert board[0]["agent_id"] == a1.id
    assert board[0]["rank"] == 1
    assert board[0]["helpfulness_score"] >= board[1]["helpfulness_score"]


# =============================================================================
# 17. Multi-leaderboard: earnings type
# =============================================================================

async def test_multi_leaderboard_earnings_type(db, make_agent, make_listing, make_transaction):
    """Earnings leaderboard ranks by total_earned_usdc desc."""
    s1, _ = await make_agent(name="earn-high")
    s2, _ = await make_agent(name="earn-low")
    buyer, _ = await make_agent(name="earn-buyer")

    l1 = await make_listing(s1.id, price_usdc=50.0)
    l2 = await make_listing(s2.id, price_usdc=5.0)

    await make_transaction(buyer.id, s1.id, l1.id, amount_usdc=50.0, status="completed")
    await make_transaction(buyer.id, s2.id, l2.id, amount_usdc=5.0, status="completed")

    await get_agent_stats(db, s1.id)
    await get_agent_stats(db, s2.id)

    board = await get_multi_leaderboard(db, "earnings", limit=10)

    assert len(board) == 2
    assert board[0]["agent_id"] == s1.id
    assert board[0]["total_earned_usdc"] == 50.0
    assert board[1]["total_earned_usdc"] == 5.0
    assert "$" in board[0]["secondary_label"]


# =============================================================================
# 18. Multi-leaderboard: contributors type
# =============================================================================

async def test_multi_leaderboard_contributors_type(db, make_agent, make_listing):
    """Contributors leaderboard ranks by total_data_bytes_contributed desc."""
    big, _ = await make_agent(name="big-data")
    small, _ = await make_agent(name="small-data")

    await make_listing(big.id, content_size=20000)
    await make_listing(big.id, content_size=15000)
    await make_listing(small.id, content_size=500)

    await get_agent_stats(db, big.id)
    await get_agent_stats(db, small.id)

    board = await get_multi_leaderboard(db, "contributors", limit=10)

    assert len(board) == 2
    assert board[0]["agent_id"] == big.id
    assert board[0]["primary_score"] == 35000
    assert "bytes" in board[0]["secondary_label"]


# =============================================================================
# 19. Primary specialization set from listings
# =============================================================================

async def test_primary_specialization_from_listings(db, make_agent, make_listing):
    """Primary specialization is set to first distinct category from active listings."""
    agent, _ = await make_agent(name="spec-agent")

    await make_listing(agent.id, category="ml_models")
    await make_listing(agent.id, category="web_search")

    stats = await get_agent_stats(db, agent.id)

    # primary_specialization is categories[0]
    assert stats.primary_specialization is not None
    assert stats.primary_specialization in ["ml_models", "web_search"]
    assert stats.category_count == 2

    import json
    cats = json.loads(stats.categories_json)
    assert set(cats) == {"ml_models", "web_search"}


# =============================================================================
# 20. API route: GET /reputation/{agent_id} and GET /reputation/leaderboard
# =============================================================================

@pytest.mark.asyncio
async def test_api_reputation_and_leaderboard(
    client, db, make_agent, make_listing
):
    """GET /reputation/{agent_id} returns score; GET /reputation/leaderboard returns entries."""
    seller, token = await make_agent(name="api-seller")
    buyer, _ = await make_agent(name="api-buyer")
    listing = await make_listing(seller.id, price_usdc=2.0)

    await _insert_tx(db, buyer.id, seller.id, listing.id,
                     status="completed", verification_status="verified")

    # Precalculate so the row exists
    await calculate_reputation(db, seller.id)

    # GET /api/v1/reputation/{agent_id}
    resp = await client.get(f"/api/v1/reputation/{seller.id}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["agent_id"] == seller.id
    assert data["total_transactions"] == 1
    assert data["composite_score"] > 0

    # GET /api/v1/reputation/leaderboard
    resp2 = await client.get("/api/v1/reputation/leaderboard?limit=5")
    assert resp2.status_code == 200
    lb = resp2.json()
    assert "entries" in lb
    assert len(lb["entries"]) >= 1
    assert lb["entries"][0]["agent_id"] == seller.id
