"""Tests for fraud_prevention_service — Sybil cluster detection, registration bursts.

Covers:
- detect_sybil_clusters: dense trading loops, sparse graphs, self-trades excluded,
  min_cluster_size threshold, density threshold, risk levels
- detect_registration_bursts: burst detection, deduplication, risk levels, thresholds
- get_fraud_report: aggregation of sybil + burst data
- FraudPreventionService: class wrapper, missing db error
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from marketplace.models.agent import RegisteredAgent
from marketplace.models.listing import DataListing
from marketplace.models.transaction import Transaction
from marketplace.services.fraud_prevention_service import (
    FraudPreventionService,
    detect_registration_bursts,
    detect_sybil_clusters,
    get_fraud_report,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _id() -> str:
    return str(uuid.uuid4())


async def _make_agent(
    db: AsyncSession,
    name: str | None = None,
    created_at: datetime | None = None,
) -> RegisteredAgent:
    agent = RegisteredAgent(
        id=_id(),
        name=name or f"agent-{_id()[:8]}",
        agent_type="both",
        public_key="ssh-rsa AAAA_test",
        status="active",
    )
    if created_at:
        agent.created_at = created_at
    db.add(agent)
    await db.commit()
    await db.refresh(agent)
    return agent


async def _make_listing(db: AsyncSession, seller_id: str) -> DataListing:
    listing = DataListing(
        id=_id(),
        seller_id=seller_id,
        title=f"listing-{_id()[:6]}",
        category="web_search",
        content_hash=f"sha256:{_id().replace('-', '')[:64]}",
        content_size=512,
        price_usdc=Decimal("1.00"),
        quality_score=Decimal("0.80"),
        status="active",
    )
    db.add(listing)
    await db.commit()
    await db.refresh(listing)
    return listing


async def _make_tx(
    db: AsyncSession,
    buyer_id: str,
    seller_id: str,
    listing_id: str,
    status: str = "completed",
    initiated_at: datetime | None = None,
) -> Transaction:
    tx = Transaction(
        id=_id(),
        listing_id=listing_id,
        buyer_id=buyer_id,
        seller_id=seller_id,
        amount_usdc=Decimal("1.00"),
        status=status,
        content_hash=f"sha256:{_id().replace('-', '')[:64]}",
    )
    if initiated_at:
        tx.initiated_at = initiated_at
    if status == "completed":
        tx.completed_at = datetime.now(timezone.utc)
    db.add(tx)
    await db.commit()
    await db.refresh(tx)
    return tx


async def _build_dense_cluster(db: AsyncSession, size: int = 3):
    """Create a cluster of agents that all trade with each other (density=1.0)."""
    now = datetime.now(timezone.utc)
    agents = []
    for i in range(size):
        a = await _make_agent(db, name=f"cluster-{_id()[:4]}-{i}")
        agents.append(a)

    # Create a listing for the first agent to use
    listing = await _make_listing(db, agents[0].id)

    # Create completed transactions between all pairs (both directions)
    for i, a in enumerate(agents):
        for j, b in enumerate(agents):
            if i != j:
                await _make_tx(
                    db, buyer_id=a.id, seller_id=b.id,
                    listing_id=listing.id, status="completed",
                    initiated_at=now - timedelta(hours=1),
                )
    return agents


# ---------------------------------------------------------------------------
# detect_sybil_clusters
# ---------------------------------------------------------------------------


class TestDetectSybilClusters:
    async def test_no_transactions_returns_empty(self, db: AsyncSession):
        await _make_agent(db)
        clusters = await detect_sybil_clusters(db)
        assert clusters == []

    async def test_dense_cluster_detected(self, db: AsyncSession):
        """A fully connected cluster of 3+ agents should be detected."""
        agents = await _build_dense_cluster(db, size=3)
        clusters = await detect_sybil_clusters(db, min_cluster_size=3)
        assert len(clusters) >= 1

        cluster = clusters[0]
        assert cluster["size"] >= 3
        assert cluster["density"] > 0.5
        assert cluster["risk_level"] in ("high", "critical")
        assert cluster["internal_transactions"] > 0

    async def test_min_cluster_size_filters_small_groups(self, db: AsyncSession):
        """Two agents trading don't meet min_cluster_size=3."""
        a = await _make_agent(db, name="pair-a")
        b = await _make_agent(db, name="pair-b")
        listing = await _make_listing(db, a.id)

        now = datetime.now(timezone.utc)
        await _make_tx(db, a.id, b.id, listing.id, initiated_at=now - timedelta(hours=1))
        await _make_tx(db, b.id, a.id, listing.id, initiated_at=now - timedelta(hours=1))

        clusters = await detect_sybil_clusters(db, min_cluster_size=3)
        assert clusters == []

    async def test_self_trades_excluded_from_graph(self, db: AsyncSession):
        """Self-trades (buyer_id == seller_id) should not form edges."""
        a = await _make_agent(db, name="self-trader")
        listing = await _make_listing(db, a.id)

        now = datetime.now(timezone.utc)
        await _make_tx(db, a.id, a.id, listing.id, initiated_at=now - timedelta(hours=1))

        clusters = await detect_sybil_clusters(db)
        assert clusters == []

    async def test_only_completed_transactions_counted(self, db: AsyncSession):
        """Pending/failed transactions should not be used for cluster detection."""
        agents = []
        for i in range(3):
            agents.append(await _make_agent(db, name=f"pending-{i}"))
        listing = await _make_listing(db, agents[0].id)

        now = datetime.now(timezone.utc)
        for i, a in enumerate(agents):
            for j, b in enumerate(agents):
                if i != j:
                    await _make_tx(
                        db, a.id, b.id, listing.id,
                        status="initiated",
                        initiated_at=now - timedelta(hours=1),
                    )

        clusters = await detect_sybil_clusters(db)
        assert clusters == []

    async def test_old_transactions_ignored(self, db: AsyncSession):
        """Transactions older than 7 days should not be counted."""
        agents = []
        for i in range(3):
            agents.append(await _make_agent(db, name=f"old-tx-{i}"))
        listing = await _make_listing(db, agents[0].id)

        old_time = datetime.now(timezone.utc) - timedelta(days=10)
        for i, a in enumerate(agents):
            for j, b in enumerate(agents):
                if i != j:
                    await _make_tx(
                        db, a.id, b.id, listing.id,
                        initiated_at=old_time,
                    )

        clusters = await detect_sybil_clusters(db)
        assert clusters == []

    async def test_sparse_cluster_not_flagged(self, db: AsyncSession):
        """A connected component with low density (<= 0.5) should not be flagged."""
        # Create 4 agents in a line: A->B->C->D (not tightly connected)
        agents = []
        for i in range(4):
            agents.append(await _make_agent(db, name=f"sparse-{i}"))
        listing = await _make_listing(db, agents[0].id)

        now = datetime.now(timezone.utc)
        # Only sequential connections: A->B, B->C, C->D
        for i in range(3):
            await _make_tx(
                db, agents[i].id, agents[i + 1].id, listing.id,
                initiated_at=now - timedelta(hours=1),
            )

        clusters = await detect_sybil_clusters(db, min_cluster_size=3)
        # density = 6/(4*3) = 0.5 -- not > 0.5, so should not be flagged
        assert clusters == []

    async def test_critical_risk_level_for_very_dense(self, db: AsyncSession):
        """Density > 0.8 should yield 'critical' risk level."""
        agents = await _build_dense_cluster(db, size=3)
        clusters = await detect_sybil_clusters(db, min_cluster_size=3)
        # Fully connected graph of 3: density = 6/6 = 1.0 > 0.8
        assert len(clusters) >= 1
        assert clusters[0]["risk_level"] == "critical"

    async def test_custom_min_cluster_size(self, db: AsyncSession):
        """Setting min_cluster_size=2 should flag pairs."""
        a = await _make_agent(db, name="pair-x")
        b = await _make_agent(db, name="pair-y")
        listing = await _make_listing(db, a.id)

        now = datetime.now(timezone.utc)
        await _make_tx(db, a.id, b.id, listing.id, initiated_at=now - timedelta(hours=1))
        await _make_tx(db, b.id, a.id, listing.id, initiated_at=now - timedelta(hours=1))

        clusters = await detect_sybil_clusters(db, min_cluster_size=2)
        # 2 agents, fully connected: density = 2/2 = 1.0
        assert len(clusters) >= 1
        assert clusters[0]["size"] == 2


# ---------------------------------------------------------------------------
# detect_registration_bursts
# ---------------------------------------------------------------------------


class TestDetectRegistrationBursts:
    async def test_no_agents_returns_empty(self, db: AsyncSession):
        bursts = await detect_registration_bursts(db)
        assert bursts == []

    async def test_burst_detected(self, db: AsyncSession):
        """Creating many agents in a short window triggers burst detection."""
        now = datetime.now(timezone.utc)
        for i in range(12):
            await _make_agent(
                db,
                name=f"burst-{_id()[:4]}-{i}",
                created_at=now - timedelta(minutes=5 + i),
            )

        bursts = await detect_registration_bursts(db, window_minutes=60, threshold=10)
        assert len(bursts) >= 1
        assert bursts[0]["count"] >= 10
        assert bursts[0]["risk_level"] in ("medium", "high")

    async def test_below_threshold_no_burst(self, db: AsyncSession):
        """Fewer agents than threshold should not trigger."""
        now = datetime.now(timezone.utc)
        for i in range(5):
            await _make_agent(
                db,
                name=f"no-burst-{i}",
                created_at=now - timedelta(minutes=i),
            )

        bursts = await detect_registration_bursts(db, window_minutes=60, threshold=10)
        assert bursts == []

    async def test_high_risk_level_at_double_threshold(self, db: AsyncSession):
        """Count >= threshold * 2 should yield 'high' risk level."""
        now = datetime.now(timezone.utc)
        for i in range(22):
            await _make_agent(
                db,
                name=f"high-risk-{_id()[:4]}-{i}",
                created_at=now - timedelta(minutes=i),
            )

        bursts = await detect_registration_bursts(db, window_minutes=60, threshold=10)
        assert len(bursts) >= 1
        high_bursts = [b for b in bursts if b["risk_level"] == "high"]
        assert len(high_bursts) >= 1

    async def test_old_registrations_ignored(self, db: AsyncSession):
        """Registrations older than 24 hours should not be counted."""
        old_time = datetime.now(timezone.utc) - timedelta(hours=48)
        for i in range(15):
            await _make_agent(
                db,
                name=f"old-reg-{_id()[:4]}-{i}",
                created_at=old_time + timedelta(minutes=i),
            )

        bursts = await detect_registration_bursts(db, window_minutes=60, threshold=10)
        assert bursts == []

    async def test_custom_window_minutes(self, db: AsyncSession):
        """Narrow window should detect tighter bursts."""
        now = datetime.now(timezone.utc)
        # 10 agents within 5 minutes
        for i in range(10):
            await _make_agent(
                db,
                name=f"tight-{_id()[:4]}-{i}",
                created_at=now - timedelta(seconds=30 * i),
            )

        bursts = await detect_registration_bursts(db, window_minutes=10, threshold=10)
        assert len(bursts) >= 1


# ---------------------------------------------------------------------------
# get_fraud_report
# ---------------------------------------------------------------------------


class TestGetFraudReport:
    async def test_empty_report(self, db: AsyncSession):
        report = await get_fraud_report(db)
        assert report["sybil_clusters"] == []
        assert report["registration_bursts"] == []
        assert report["total_sybil_agents"] == 0
        assert report["total_burst_agents"] == 0
        assert "generated_at" in report

    async def test_report_aggregates_sybil_counts(self, db: AsyncSession):
        await _build_dense_cluster(db, size=3)
        report = await get_fraud_report(db)
        assert report["total_sybil_agents"] >= 3

    async def test_report_aggregates_burst_counts(self, db: AsyncSession):
        now = datetime.now(timezone.utc)
        for i in range(12):
            await _make_agent(
                db,
                name=f"report-burst-{_id()[:4]}-{i}",
                created_at=now - timedelta(minutes=i),
            )

        report = await get_fraud_report(db)
        assert report["total_burst_agents"] >= 10


# ---------------------------------------------------------------------------
# FraudPreventionService class wrapper
# ---------------------------------------------------------------------------


class TestFraudPreventionServiceClass:
    async def test_detect_sybil_clusters_delegates(self, db: AsyncSession):
        service = FraudPreventionService(db=db)
        clusters = await service.detect_sybil_clusters()
        assert isinstance(clusters, list)

    async def test_detect_sybil_clusters_no_db_raises(self):
        service = FraudPreventionService(db=None)
        with pytest.raises(ValueError, match="Database session required"):
            await service.detect_sybil_clusters()

    async def test_get_fraud_report_delegates(self, db: AsyncSession):
        service = FraudPreventionService(db=db)
        report = await service.get_fraud_report()
        assert "sybil_clusters" in report
        assert "generated_at" in report

    async def test_get_fraud_report_no_db_raises(self):
        service = FraudPreventionService(db=None)
        with pytest.raises(ValueError, match="Database session required"):
            await service.get_fraud_report()

    async def test_custom_min_cluster_size(self, db: AsyncSession):
        service = FraudPreventionService(db=db)
        clusters = await service.detect_sybil_clusters(min_cluster_size=5)
        assert isinstance(clusters, list)
