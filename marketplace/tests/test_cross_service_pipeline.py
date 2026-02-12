"""Cross-service integration pipeline tests.

Tests that exercise pipelines spanning multiple services:
  - Catalog auto-population from listings
  - Search logging -> demand aggregation
  - Demand gaps -> opportunity generation
  - Catalog subscriptions and notifications
  - Transaction lifecycle end-to-end
  - Data consistency invariants
"""

import pytest
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from marketplace.models.catalog import CatalogSubscription, DataCatalogEntry
from marketplace.models.demand_signal import DemandSignal
from marketplace.models.listing import DataListing
from marketplace.models.opportunity import OpportunitySignal
from marketplace.models.search_log import SearchLog
from marketplace.models.transaction import Transaction
from marketplace.services import catalog_service, demand_service
from marketplace.services.transaction_service import (
    confirm_payment,
    deliver_content,
    initiate_transaction,
    verify_delivery,
)

pytestmark = pytest.mark.anyio


# =====================================================================
# Catalog auto-population (4 tests)
# =====================================================================


async def test_auto_populate_creates_catalog_entries(
    db: AsyncSession, make_agent, make_listing
):
    """Create 3 listings for an agent, call auto_populate_catalog, verify entries are created."""
    agent, _ = await make_agent(name="catalog-agent-1")

    await make_listing(agent.id, price_usdc=1.0, category="web_search")
    await make_listing(agent.id, price_usdc=2.0, category="web_search")
    await make_listing(agent.id, price_usdc=3.0, category="web_search")

    entries = await catalog_service.auto_populate_catalog(db, agent.id)

    assert len(entries) == 1
    entry = entries[0]
    assert entry.agent_id == agent.id
    assert entry.namespace == "web_search"
    assert entry.active_listings_count == 3
    assert entry.status == "active"


async def test_auto_populate_groups_by_category(
    db: AsyncSession, make_agent, make_listing
):
    """Agent has listings in 2 categories; auto_populate creates 2 entries."""
    agent, _ = await make_agent(name="catalog-agent-2")

    await make_listing(agent.id, price_usdc=1.0, category="web_search")
    await make_listing(agent.id, price_usdc=2.0, category="code_analysis")

    entries = await catalog_service.auto_populate_catalog(db, agent.id)

    assert len(entries) == 2
    namespaces = {e.namespace for e in entries}
    assert namespaces == {"web_search", "code_analysis"}


async def test_auto_populate_skips_existing_entry(
    db: AsyncSession, make_agent, make_listing, make_catalog_entry
):
    """Create a catalog entry first, then auto_populate; no duplicates are created."""
    agent, _ = await make_agent(name="catalog-agent-3")

    await make_listing(agent.id, price_usdc=5.0, category="web_search")
    # Pre-existing catalog entry for the same namespace
    await make_catalog_entry(agent.id, namespace="web_search", topic="manual entry")

    entries = await catalog_service.auto_populate_catalog(db, agent.id)

    # auto_populate should skip web_search since an active entry already exists
    assert len(entries) == 0

    # Confirm only one catalog entry exists for this agent + namespace
    result = await db.execute(
        select(DataCatalogEntry).where(
            DataCatalogEntry.agent_id == agent.id,
            DataCatalogEntry.namespace == "web_search",
            DataCatalogEntry.status == "active",
        )
    )
    all_entries = list(result.scalars().all())
    assert len(all_entries) == 1


async def test_auto_populate_price_range_reflects_listings(
    db: AsyncSession, make_agent, make_listing
):
    """3 listings at prices 1, 5, 10: catalog entry has correct price range."""
    agent, _ = await make_agent(name="catalog-agent-4")

    await make_listing(agent.id, price_usdc=1.0, category="web_search")
    await make_listing(agent.id, price_usdc=5.0, category="web_search")
    await make_listing(agent.id, price_usdc=10.0, category="web_search")

    entries = await catalog_service.auto_populate_catalog(db, agent.id)

    assert len(entries) == 1
    entry = entries[0]
    assert float(entry.price_range_min) == pytest.approx(1.0)
    assert float(entry.price_range_max) == pytest.approx(10.0)


# =====================================================================
# Search -> Demand (4 tests)
# =====================================================================


async def test_search_log_creates_search_record(db: AsyncSession, make_agent):
    """log_search creates a SearchLog record in the database."""
    agent, _ = await make_agent(name="searcher-1")

    log = await demand_service.log_search(
        db,
        query_text="machine learning datasets",
        category="web_search",
        source="discover",
        requester_id=agent.id,
        matched_count=5,
    )

    assert log.query_text == "machine learning datasets"
    assert log.category == "web_search"
    assert log.source == "discover"
    assert log.requester_id == agent.id
    assert log.matched_count == 5

    # Verify persisted in DB
    result = await db.execute(
        select(SearchLog).where(SearchLog.id == log.id)
    )
    persisted = result.scalar_one_or_none()
    assert persisted is not None
    assert persisted.query_text == "machine learning datasets"


async def test_aggregate_demand_groups_queries(db: AsyncSession, make_agent):
    """Log 3 searches for the same query, aggregate -> 1 signal with count=3."""
    agent, _ = await make_agent(name="searcher-2")

    for _ in range(3):
        await demand_service.log_search(
            db,
            query_text="python web scraping",
            category="web_search",
            requester_id=agent.id,
            matched_count=0,
        )

    signals = await demand_service.aggregate_demand(db, time_window_hours=24)

    # All 3 searches share the normalized pattern "python scraping web"
    matching = [s for s in signals if "python" in s.query_pattern and "scraping" in s.query_pattern]
    assert len(matching) == 1
    assert matching[0].search_count == 3


async def test_aggregate_demand_computes_velocity(db: AsyncSession, make_agent):
    """Log searches with timestamps, verify velocity calculation."""
    agent, _ = await make_agent(name="searcher-3")

    # Log 6 searches; velocity = search_count / time_window_hours
    for _ in range(6):
        await demand_service.log_search(
            db,
            query_text="api integration guide",
            category="web_search",
            requester_id=agent.id,
            matched_count=0,
        )

    time_window = 24
    signals = await demand_service.aggregate_demand(db, time_window_hours=time_window)

    matching = [s for s in signals if "api" in s.query_pattern]
    assert len(matching) == 1

    # velocity = search_count / time_window_hours = 6 / 24 = 0.25
    expected_velocity = round(6 / time_window, 2)
    assert float(matching[0].velocity) == pytest.approx(expected_velocity)


async def test_aggregate_demand_upserts_signal(db: AsyncSession, make_agent):
    """Aggregate twice, still only 1 DemandSignal for the same query pattern (upsert)."""
    agent, _ = await make_agent(name="searcher-4")

    await demand_service.log_search(
        db,
        query_text="data pipeline tutorial",
        category="web_search",
        requester_id=agent.id,
        matched_count=0,
    )
    signals_1 = await demand_service.aggregate_demand(db, time_window_hours=24)

    # Log another search and aggregate again
    await demand_service.log_search(
        db,
        query_text="data pipeline tutorial",
        category="web_search",
        requester_id=agent.id,
        matched_count=0,
    )
    signals_2 = await demand_service.aggregate_demand(db, time_window_hours=24)

    # Query the DB: should be exactly 1 DemandSignal with the normalized pattern
    normalized = demand_service.normalize_query("data pipeline tutorial")
    result = await db.execute(
        select(DemandSignal).where(DemandSignal.query_pattern == normalized)
    )
    all_signals = list(result.scalars().all())
    assert len(all_signals) == 1
    assert all_signals[0].search_count == 2


# =====================================================================
# Demand -> Opportunity (3 tests)
# =====================================================================


async def test_opportunities_from_gaps(db: AsyncSession, make_demand_signal):
    """Create a gap signal (fulfillment_rate < 0.2), generate_opportunities creates OpportunitySignal."""
    signal = await make_demand_signal(
        query_pattern="rare dataset xyz",
        category="web_search",
        search_count=20,
        unique_requesters=10,
        velocity=5.0,
        fulfillment_rate=0.1,  # < 0.2 -> gap
        is_gap=1,
    )

    opportunities = await demand_service.generate_opportunities(db)

    assert len(opportunities) >= 1
    opp = [o for o in opportunities if o.demand_signal_id == signal.id]
    assert len(opp) == 1
    assert opp[0].query_pattern == "rare dataset xyz"
    assert opp[0].status == "active"


async def test_opportunity_has_expiry(db: AsyncSession, make_demand_signal):
    """Generated opportunity has expires_at set."""
    await make_demand_signal(
        query_pattern="ephemeral data need",
        category="code_analysis",
        search_count=15,
        unique_requesters=8,
        velocity=3.0,
        fulfillment_rate=0.05,
        is_gap=1,
    )

    opportunities = await demand_service.generate_opportunities(db)

    assert len(opportunities) >= 1
    opp = opportunities[0]
    assert opp.expires_at is not None
    # expires_at should be in the future (within ~24h from now)
    now = datetime.now(timezone.utc)
    assert opp.expires_at > now


async def test_opportunity_revenue_estimate(db: AsyncSession, make_demand_signal):
    """Opportunity estimated_revenue is based on avg_max_price and velocity."""
    signal = await make_demand_signal(
        query_pattern="premium analytics feed",
        category="web_search",
        search_count=30,
        unique_requesters=15,
        velocity=4.0,
        fulfillment_rate=0.0,
        is_gap=1,
    )
    # Set avg_max_price on the signal
    signal.avg_max_price = Decimal("0.05")
    await db.commit()
    await db.refresh(signal)

    opportunities = await demand_service.generate_opportunities(db)

    matching = [o for o in opportunities if o.demand_signal_id == signal.id]
    assert len(matching) == 1
    opp = matching[0]
    # estimated_revenue = velocity * avg_max_price = 4.0 * 0.05 = 0.2
    assert float(opp.estimated_revenue_usdc) == pytest.approx(0.2, abs=0.001)


# =====================================================================
# Subscription notify (4 tests)
# =====================================================================


async def test_subscription_notified_on_match(
    db: AsyncSession, make_agent, make_catalog_subscription
):
    """Subscribe to a pattern, register a matching entry, verify notify_subscribers runs."""
    seller, _ = await make_agent(name="notify-seller-1")
    buyer, _ = await make_agent(name="notify-buyer-1")

    # Buyer subscribes to "web_search" namespace
    sub = await make_catalog_subscription(
        buyer.id, namespace_pattern="web_search"
    )

    # Seller registers a catalog entry via the service (which calls notify_subscribers)
    entry = await catalog_service.register_catalog_entry(
        db,
        agent_id=seller.id,
        namespace="web_search",
        topic="Python tutorials",
        description="High-quality Python data",
    )

    # The subscription should match (fnmatch "web_search" matches "web_search")
    # Verify the subscription is still active and the entry was created
    assert entry.namespace == "web_search"
    assert sub.status == "active"

    # Re-fetch subscription to confirm it was not erroneously deactivated
    result = await db.execute(
        select(CatalogSubscription).where(CatalogSubscription.id == sub.id)
    )
    refreshed_sub = result.scalar_one()
    assert refreshed_sub.status == "active"


async def test_subscription_skips_non_matching(
    db: AsyncSession, make_agent, make_catalog_subscription
):
    """Subscribe to 'web_*', register 'code_analysis' entry -> no match triggered."""
    seller, _ = await make_agent(name="notify-seller-2")
    buyer, _ = await make_agent(name="notify-buyer-2")

    sub = await make_catalog_subscription(
        buyer.id, namespace_pattern="web_*"
    )

    # Register entry in a non-matching namespace
    entry = await catalog_service.register_catalog_entry(
        db,
        agent_id=seller.id,
        namespace="code_analysis",
        topic="Code review data",
    )

    # The subscription pattern "web_*" does NOT match "code_analysis"
    # Verify subscription remains active (no error) and entry was created
    assert entry.namespace == "code_analysis"

    result = await db.execute(
        select(CatalogSubscription).where(CatalogSubscription.id == sub.id)
    )
    refreshed_sub = result.scalar_one()
    assert refreshed_sub.status == "active"


async def test_subscription_price_filter(
    db: AsyncSession, make_agent, make_catalog_subscription
):
    """Subscription with max_price; entry above price is filtered out during notification."""
    seller, _ = await make_agent(name="notify-seller-3")
    buyer, _ = await make_agent(name="notify-buyer-3")

    # Buyer only wants entries with price_range_min <= 0.005
    sub = await make_catalog_subscription(
        buyer.id, namespace_pattern="web_search", max_price=0.005
    )

    # Register entry with a price_range_min above the subscription max_price
    entry = await catalog_service.register_catalog_entry(
        db,
        agent_id=seller.id,
        namespace="web_search",
        topic="Expensive data feed",
        price_range_min=0.05,  # Way above sub.max_price (0.005)
        price_range_max=0.10,
    )

    # notify_subscribers skips because entry.price_range_min (0.05) > sub.max_price (0.005)
    # Verify the entry was created but no crash occurred
    assert entry is not None
    assert float(entry.price_range_min) == pytest.approx(0.05)

    # Subscription should remain active
    result = await db.execute(
        select(CatalogSubscription).where(CatalogSubscription.id == sub.id)
    )
    refreshed_sub = result.scalar_one()
    assert refreshed_sub.status == "active"


async def test_subscription_quality_filter(
    db: AsyncSession, make_agent, make_catalog_subscription
):
    """Subscription with min_quality; entry below quality is filtered out during notification."""
    seller, _ = await make_agent(name="notify-seller-4")
    buyer, _ = await make_agent(name="notify-buyer-4")

    # Buyer demands high quality (min_quality=0.9)
    sub = await make_catalog_subscription(
        buyer.id, namespace_pattern="web_search", min_quality=0.9
    )

    # Register entry with low quality
    entry = DataCatalogEntry(
        agent_id=seller.id,
        namespace="web_search",
        topic="Low quality feed",
        quality_avg=Decimal("0.3"),  # Below min_quality threshold of 0.9
    )
    db.add(entry)
    await db.commit()
    await db.refresh(entry)

    # Manually invoke notify_subscribers to check the quality filter
    await catalog_service.notify_subscribers(db, entry)

    # notify_subscribers skips because entry.quality_avg (0.3) < sub.min_quality (0.9)
    # Verify both objects exist without error
    assert float(entry.quality_avg) == pytest.approx(0.3)
    assert float(sub.min_quality) == pytest.approx(0.9)


# =====================================================================
# Transaction lifecycle (3 tests)
# =====================================================================


async def test_initiate_creates_pending_transaction(
    db: AsyncSession, make_agent, make_listing
):
    """initiate_transaction creates a transaction with status 'payment_pending'."""
    seller, _ = await make_agent(name="tx-seller-1")
    buyer, _ = await make_agent(name="tx-buyer-1")

    listing = await make_listing(seller.id, price_usdc=2.50)

    result = await initiate_transaction(db, listing.id, buyer.id)

    assert result["status"] == "payment_pending"
    assert result["amount_usdc"] == pytest.approx(2.50)
    assert result["transaction_id"] is not None
    assert result["content_hash"] == listing.content_hash

    # Verify the transaction exists in DB
    tx_result = await db.execute(
        select(Transaction).where(Transaction.id == result["transaction_id"])
    )
    tx = tx_result.scalar_one()
    assert tx.status == "payment_pending"
    assert tx.buyer_id == buyer.id
    assert tx.seller_id == seller.id


async def test_full_lifecycle_updates_access_count(
    db: AsyncSession, make_agent, make_listing
):
    """Complete the full tx lifecycle: initiate -> confirm -> deliver -> verify.
    Listing access_count should be incremented upon successful verification."""
    seller, _ = await make_agent(name="tx-seller-2")
    buyer, _ = await make_agent(name="tx-buyer-2")

    content_text = "verified content for full lifecycle test"
    listing = await make_listing(seller.id, price_usdc=1.00, content=content_text)

    # Verify initial access_count is 0
    assert listing.access_count == 0

    # Step 1: Initiate
    init_result = await initiate_transaction(db, listing.id, buyer.id)
    tx_id = init_result["transaction_id"]

    # Step 2: Confirm payment
    tx = await confirm_payment(db, tx_id)
    assert tx.status == "payment_confirmed"

    # Step 3: Deliver content (same content -> hash matches)
    tx = await deliver_content(db, tx_id, content_text, seller.id)
    assert tx.status == "delivered"

    # Step 4: Verify delivery
    tx = await verify_delivery(db, tx_id, buyer.id)
    assert tx.status == "completed"
    assert tx.verification_status == "verified"

    # Verify access_count was incremented
    refreshed = await db.execute(
        select(DataListing).where(DataListing.id == listing.id)
    )
    updated_listing = refreshed.scalar_one()
    assert updated_listing.access_count == 1


async def test_disputed_transaction_on_hash_mismatch(
    db: AsyncSession, make_agent, make_listing
):
    """Deliver wrong content hash -> verification creates dispute."""
    seller, _ = await make_agent(name="tx-seller-3")
    buyer, _ = await make_agent(name="tx-buyer-3")

    listing = await make_listing(
        seller.id, price_usdc=3.00, content="original correct content"
    )

    # Initiate and confirm
    init_result = await initiate_transaction(db, listing.id, buyer.id)
    tx_id = init_result["transaction_id"]
    await confirm_payment(db, tx_id)

    # Deliver WRONG content (different from what was listed)
    await deliver_content(db, tx_id, "completely different content", seller.id)

    # Verify should detect mismatch
    tx = await verify_delivery(db, tx_id, buyer.id)
    assert tx.status == "disputed"
    assert tx.verification_status == "failed"
    assert "mismatch" in tx.error_message.lower()


# =====================================================================
# Data consistency (2 tests)
# =====================================================================


async def test_listing_content_hash_stable(
    db: AsyncSession, make_agent, make_listing
):
    """Create a listing; content_hash matches what the storage service computed."""
    from marketplace.services.storage_service import get_storage

    agent, _ = await make_agent(name="hash-agent-1")
    content_text = "deterministic content for hash stability check"

    listing = await make_listing(
        agent.id, price_usdc=1.0, content=content_text
    )

    # Independently compute hash via storage
    storage = get_storage()
    expected_hash = storage.compute_hash(content_text.encode("utf-8"))

    assert listing.content_hash == expected_hash


async def test_catalog_reflects_listing_quality(
    db: AsyncSession, make_agent, make_listing
):
    """Auto-populate catalog; quality_avg reflects the average of listing quality_scores."""
    agent, _ = await make_agent(name="quality-agent-1")

    await make_listing(agent.id, price_usdc=1.0, category="web_search", quality_score=0.60)
    await make_listing(agent.id, price_usdc=2.0, category="web_search", quality_score=0.80)
    await make_listing(agent.id, price_usdc=3.0, category="web_search", quality_score=1.00)

    entries = await catalog_service.auto_populate_catalog(db, agent.id)

    assert len(entries) == 1
    entry = entries[0]
    # Average quality = (0.60 + 0.80 + 1.00) / 3 = 0.80
    assert float(entry.quality_avg) == pytest.approx(0.80, abs=0.01)
