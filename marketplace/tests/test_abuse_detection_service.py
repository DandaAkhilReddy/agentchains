"""Tests for abuse_detection_service — anomaly rules and scan functions.

Covers:
- RapidTransactionRule: threshold hit, below threshold, custom params
- SelfTradingRule: self-trades detected, no self-trades
- LargeTransactionRule: above threshold, below threshold, custom threshold
- NewAccountHighVolumeRule: new account with high volume, old account skipped,
  missing agent
- detect_anomalies: default rules, custom rules, exception handling in rules
- scan_all_agents: scans active agents, returns only anomalous ones
- AbuseDetectionService: class wrapper, missing db error
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from unittest.mock import AsyncMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from marketplace.models.agent import RegisteredAgent
from marketplace.models.listing import DataListing
from marketplace.models.transaction import Transaction
from marketplace.services.abuse_detection_service import (
    AbuseDetectionService,
    AnomalyRule,
    LargeTransactionRule,
    NewAccountHighVolumeRule,
    RapidTransactionRule,
    SelfTradingRule,
    detect_anomalies,
    scan_all_agents,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _id() -> str:
    return str(uuid.uuid4())


async def _make_agent(
    db: AsyncSession,
    name: str | None = None,
    status: str = "active",
    created_at: datetime | None = None,
) -> RegisteredAgent:
    agent = RegisteredAgent(
        id=_id(),
        name=name or f"agent-{_id()[:8]}",
        agent_type="both",
        public_key="ssh-rsa AAAA_test",
        status=status,
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
    amount: float = 1.0,
    status: str = "completed",
    initiated_at: datetime | None = None,
) -> Transaction:
    tx = Transaction(
        id=_id(),
        listing_id=listing_id,
        buyer_id=buyer_id,
        seller_id=seller_id,
        amount_usdc=Decimal(str(amount)),
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


# ---------------------------------------------------------------------------
# RapidTransactionRule
# ---------------------------------------------------------------------------


class TestRapidTransactionRule:
    async def test_no_transactions_passes(self, db: AsyncSession):
        agent = await _make_agent(db)
        rule = RapidTransactionRule(threshold=5, window_hours=1)
        anomalies = await rule.evaluate(db, agent.id)
        assert anomalies == []

    async def test_below_threshold_passes(self, db: AsyncSession):
        agent = await _make_agent(db)
        other = await _make_agent(db, name="other-rapid")
        listing = await _make_listing(db, other.id)

        now = datetime.now(timezone.utc)
        for _ in range(3):
            await _make_tx(
                db, agent.id, other.id, listing.id,
                initiated_at=now - timedelta(minutes=10),
            )

        rule = RapidTransactionRule(threshold=5, window_hours=1)
        anomalies = await rule.evaluate(db, agent.id)
        assert anomalies == []

    async def test_threshold_hit_flags(self, db: AsyncSession):
        agent = await _make_agent(db)
        other = await _make_agent(db, name="rapid-seller")
        listing = await _make_listing(db, other.id)

        now = datetime.now(timezone.utc)
        for _ in range(6):
            await _make_tx(
                db, agent.id, other.id, listing.id,
                initiated_at=now - timedelta(minutes=5),
            )

        rule = RapidTransactionRule(threshold=5, window_hours=1)
        anomalies = await rule.evaluate(db, agent.id)
        assert len(anomalies) == 1
        assert anomalies[0]["rule"] == "rapid_transactions"
        assert anomalies[0]["severity"] == "high"
        assert anomalies[0]["value"] == 6

    async def test_old_transactions_not_counted(self, db: AsyncSession):
        agent = await _make_agent(db)
        other = await _make_agent(db, name="rapid-old")
        listing = await _make_listing(db, other.id)

        old_time = datetime.now(timezone.utc) - timedelta(hours=3)
        for _ in range(10):
            await _make_tx(
                db, agent.id, other.id, listing.id,
                initiated_at=old_time,
            )

        rule = RapidTransactionRule(threshold=5, window_hours=1)
        anomalies = await rule.evaluate(db, agent.id)
        assert anomalies == []

    async def test_rule_attributes(self):
        rule = RapidTransactionRule()
        assert rule.name == "rapid_transactions"
        assert rule.severity == "high"
        assert rule.threshold == 50
        assert rule.window_hours == 1


# ---------------------------------------------------------------------------
# SelfTradingRule
# ---------------------------------------------------------------------------


class TestSelfTradingRule:
    async def test_no_self_trades_passes(self, db: AsyncSession):
        agent = await _make_agent(db)
        other = await _make_agent(db, name="no-self")
        listing = await _make_listing(db, other.id)
        await _make_tx(db, agent.id, other.id, listing.id)

        rule = SelfTradingRule()
        anomalies = await rule.evaluate(db, agent.id)
        assert anomalies == []

    async def test_self_trade_detected(self, db: AsyncSession):
        agent = await _make_agent(db)
        listing = await _make_listing(db, agent.id)
        await _make_tx(db, agent.id, agent.id, listing.id)

        rule = SelfTradingRule()
        anomalies = await rule.evaluate(db, agent.id)
        assert len(anomalies) == 1
        assert anomalies[0]["rule"] == "self_trading"
        assert anomalies[0]["severity"] == "critical"
        assert anomalies[0]["value"] == 1

    async def test_multiple_self_trades(self, db: AsyncSession):
        agent = await _make_agent(db)
        listing = await _make_listing(db, agent.id)
        await _make_tx(db, agent.id, agent.id, listing.id)
        await _make_tx(db, agent.id, agent.id, listing.id)
        await _make_tx(db, agent.id, agent.id, listing.id)

        rule = SelfTradingRule()
        anomalies = await rule.evaluate(db, agent.id)
        assert len(anomalies) == 1
        assert anomalies[0]["value"] == 3

    async def test_rule_attributes(self):
        rule = SelfTradingRule()
        assert rule.name == "self_trading"
        assert rule.severity == "critical"


# ---------------------------------------------------------------------------
# LargeTransactionRule
# ---------------------------------------------------------------------------


class TestLargeTransactionRule:
    async def test_no_large_transactions_passes(self, db: AsyncSession):
        agent = await _make_agent(db)
        other = await _make_agent(db, name="small-tx")
        listing = await _make_listing(db, other.id)
        await _make_tx(db, agent.id, other.id, listing.id, amount=5.0)

        rule = LargeTransactionRule(threshold_usd=Decimal("1000"))
        anomalies = await rule.evaluate(db, agent.id)
        assert anomalies == []

    async def test_large_transaction_flagged(self, db: AsyncSession):
        agent = await _make_agent(db)
        other = await _make_agent(db, name="big-tx")
        listing = await _make_listing(db, other.id)
        tx = await _make_tx(db, agent.id, other.id, listing.id, amount=5000.0)

        rule = LargeTransactionRule(threshold_usd=Decimal("1000"))
        anomalies = await rule.evaluate(db, agent.id)
        assert len(anomalies) == 1
        assert anomalies[0]["rule"] == "large_transaction"
        assert anomalies[0]["severity"] == "medium"
        assert anomalies[0]["transaction_id"] == tx.id
        assert anomalies[0]["value"] == 5000.0

    async def test_multiple_large_transactions(self, db: AsyncSession):
        agent = await _make_agent(db)
        other = await _make_agent(db, name="multi-big")
        listing = await _make_listing(db, other.id)
        await _make_tx(db, agent.id, other.id, listing.id, amount=2000.0)
        await _make_tx(db, agent.id, other.id, listing.id, amount=3000.0)

        rule = LargeTransactionRule(threshold_usd=Decimal("1000"))
        anomalies = await rule.evaluate(db, agent.id)
        assert len(anomalies) == 2

    async def test_custom_threshold(self, db: AsyncSession):
        agent = await _make_agent(db)
        other = await _make_agent(db, name="custom-thresh")
        listing = await _make_listing(db, other.id)
        await _make_tx(db, agent.id, other.id, listing.id, amount=50.0)

        rule = LargeTransactionRule(threshold_usd=Decimal("10"))
        anomalies = await rule.evaluate(db, agent.id)
        assert len(anomalies) == 1

    async def test_old_transactions_not_counted(self, db: AsyncSession):
        agent = await _make_agent(db)
        other = await _make_agent(db, name="old-big")
        listing = await _make_listing(db, other.id)

        old_time = datetime.now(timezone.utc) - timedelta(hours=48)
        await _make_tx(
            db, agent.id, other.id, listing.id,
            amount=5000.0, initiated_at=old_time,
        )

        rule = LargeTransactionRule(threshold_usd=Decimal("1000"))
        anomalies = await rule.evaluate(db, agent.id)
        assert anomalies == []

    async def test_rule_attributes(self):
        rule = LargeTransactionRule()
        assert rule.name == "large_transaction"
        assert rule.severity == "medium"
        assert rule.threshold_usd == Decimal("1000")


# ---------------------------------------------------------------------------
# NewAccountHighVolumeRule
# ---------------------------------------------------------------------------


class TestNewAccountHighVolumeRule:
    async def test_old_account_skipped(self, db: AsyncSession):
        """Accounts older than the age threshold are not checked."""
        old_time = datetime.now(timezone.utc) - timedelta(hours=48)
        agent = await _make_agent(db, created_at=old_time)
        other = await _make_agent(db, name="old-partner")
        listing = await _make_listing(db, other.id)

        for _ in range(15):
            await _make_tx(db, agent.id, other.id, listing.id)

        rule = NewAccountHighVolumeRule(account_age_hours=24, tx_threshold=10)
        anomalies = await rule.evaluate(db, agent.id)
        assert anomalies == []

    async def test_new_account_high_volume_flagged(self, db: AsyncSession):
        """A newly created account with many transactions is flagged."""
        now = datetime.now(timezone.utc)
        agent = await _make_agent(db, created_at=now - timedelta(hours=1))
        other = await _make_agent(db, name="new-partner")
        listing = await _make_listing(db, other.id)

        for _ in range(12):
            await _make_tx(db, agent.id, other.id, listing.id)

        rule = NewAccountHighVolumeRule(account_age_hours=24, tx_threshold=10)
        anomalies = await rule.evaluate(db, agent.id)
        assert len(anomalies) == 1
        assert anomalies[0]["rule"] == "new_account_high_volume"
        assert anomalies[0]["severity"] == "high"
        assert anomalies[0]["value"] == 12

    async def test_new_account_low_volume_passes(self, db: AsyncSession):
        now = datetime.now(timezone.utc)
        agent = await _make_agent(db, created_at=now - timedelta(hours=1))
        other = await _make_agent(db, name="new-low")
        listing = await _make_listing(db, other.id)

        for _ in range(3):
            await _make_tx(db, agent.id, other.id, listing.id)

        rule = NewAccountHighVolumeRule(account_age_hours=24, tx_threshold=10)
        anomalies = await rule.evaluate(db, agent.id)
        assert anomalies == []

    async def test_missing_agent_returns_empty(self, db: AsyncSession):
        rule = NewAccountHighVolumeRule()
        anomalies = await rule.evaluate(db, _id())
        assert anomalies == []

    async def test_rule_attributes(self):
        rule = NewAccountHighVolumeRule()
        assert rule.name == "new_account_high_volume"
        assert rule.severity == "high"
        assert rule.account_age_hours == 24
        assert rule.tx_threshold == 10


# ---------------------------------------------------------------------------
# detect_anomalies
# ---------------------------------------------------------------------------


class TestDetectAnomalies:
    async def test_clean_agent_no_anomalies(self, db: AsyncSession):
        agent = await _make_agent(db)
        anomalies = await detect_anomalies(db, agent.id)
        assert anomalies == []

    async def test_self_trade_detected_via_default_rules(self, db: AsyncSession):
        agent = await _make_agent(db)
        listing = await _make_listing(db, agent.id)
        await _make_tx(db, agent.id, agent.id, listing.id)

        anomalies = await detect_anomalies(db, agent.id)
        self_trade_anomalies = [a for a in anomalies if a["rule"] == "self_trading"]
        assert len(self_trade_anomalies) == 1

    async def test_custom_rules(self, db: AsyncSession):
        agent = await _make_agent(db)
        # Only run SelfTradingRule
        anomalies = await detect_anomalies(db, agent.id, rules=[SelfTradingRule()])
        assert anomalies == []

    async def test_exception_in_rule_logged_not_raised(self, db: AsyncSession):
        """A failing rule should not crash the full anomaly scan."""
        agent = await _make_agent(db)

        class BrokenRule(AnomalyRule):
            name = "broken"
            severity = "low"

            async def evaluate(self, db, agent_id):
                raise RuntimeError("Rule crashed")

        anomalies = await detect_anomalies(
            db, agent.id, rules=[BrokenRule(), SelfTradingRule()],
        )
        # BrokenRule fails silently, SelfTradingRule runs normally
        # No self-trades, so should be empty
        assert anomalies == []

    async def test_multiple_anomalies_combined(self, db: AsyncSession):
        """An agent with both self-trades and large transactions gets both flagged."""
        now = datetime.now(timezone.utc)
        agent = await _make_agent(db, created_at=now - timedelta(hours=1))
        listing = await _make_listing(db, agent.id)

        # Self-trade
        await _make_tx(db, agent.id, agent.id, listing.id)
        # Large transaction with another agent
        other = await _make_agent(db, name="multi-anomaly")
        await _make_tx(db, agent.id, other.id, listing.id, amount=5000.0)

        anomalies = await detect_anomalies(
            db, agent.id,
            rules=[SelfTradingRule(), LargeTransactionRule(threshold_usd=Decimal("1000"))],
        )
        rule_names = {a["rule"] for a in anomalies}
        assert "self_trading" in rule_names
        assert "large_transaction" in rule_names


# ---------------------------------------------------------------------------
# scan_all_agents
# ---------------------------------------------------------------------------


class TestScanAllAgents:
    async def test_no_agents_returns_empty(self, db: AsyncSession):
        results = await scan_all_agents(db)
        assert results == {}

    async def test_clean_agents_not_in_results(self, db: AsyncSession):
        await _make_agent(db)
        await _make_agent(db, name="clean-2")

        results = await scan_all_agents(db)
        assert results == {}

    async def test_anomalous_agent_returned(self, db: AsyncSession):
        agent = await _make_agent(db)
        listing = await _make_listing(db, agent.id)
        await _make_tx(db, agent.id, agent.id, listing.id)

        results = await scan_all_agents(db)
        assert agent.id in results
        assert any(a["rule"] == "self_trading" for a in results[agent.id])

    async def test_inactive_agents_excluded(self, db: AsyncSession):
        agent = await _make_agent(db, status="inactive")
        listing = await _make_listing(db, agent.id)
        await _make_tx(db, agent.id, agent.id, listing.id)

        results = await scan_all_agents(db)
        assert agent.id not in results

    async def test_limit_parameter(self, db: AsyncSession):
        """Limit controls how many agents are scanned."""
        for i in range(5):
            a = await _make_agent(db, name=f"limit-{i}")
            listing = await _make_listing(db, a.id)
            await _make_tx(db, a.id, a.id, listing.id)

        results = await scan_all_agents(db, limit=2)
        # Should only scan up to 2 agents
        assert len(results) <= 2


# ---------------------------------------------------------------------------
# AbuseDetectionService class wrapper
# ---------------------------------------------------------------------------


class TestAbuseDetectionServiceClass:
    async def test_detect_anomalies_delegates(self, db: AsyncSession):
        agent = await _make_agent(db)
        service = AbuseDetectionService(db=db)
        anomalies = await service.detect_anomalies(agent.id)
        assert isinstance(anomalies, list)

    async def test_detect_anomalies_no_db_raises(self):
        service = AbuseDetectionService(db=None)
        with pytest.raises(ValueError, match="Database session required"):
            await service.detect_anomalies("some-id")

    async def test_scan_all_agents_delegates(self, db: AsyncSession):
        service = AbuseDetectionService(db=db)
        results = await service.scan_all_agents()
        assert isinstance(results, dict)

    async def test_scan_all_agents_no_db_raises(self):
        service = AbuseDetectionService(db=None)
        with pytest.raises(ValueError, match="Database session required"):
            await service.scan_all_agents()

    async def test_detect_anomalies_with_custom_rules(self, db: AsyncSession):
        agent = await _make_agent(db)
        service = AbuseDetectionService(db=db)
        anomalies = await service.detect_anomalies(agent.id, rules=[SelfTradingRule()])
        assert anomalies == []

    async def test_scan_all_agents_with_limit(self, db: AsyncSession):
        service = AbuseDetectionService(db=db)
        results = await service.scan_all_agents(limit=5)
        assert isinstance(results, dict)


# ---------------------------------------------------------------------------
# AnomalyRule base class
# ---------------------------------------------------------------------------


class TestAnomalyRuleBase:
    async def test_base_evaluate_raises(self, db: AsyncSession):
        rule = AnomalyRule()
        with pytest.raises(NotImplementedError):
            await rule.evaluate(db, "agent-id")

    def test_base_attributes(self):
        rule = AnomalyRule()
        assert rule.name == ""
        assert rule.severity == "medium"
