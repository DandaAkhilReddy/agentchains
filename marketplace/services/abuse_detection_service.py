"""Abuse detection service.

Applies rule-based anomaly detection to identify suspicious activity
patterns in the marketplace: rate anomalies, financial abuse, sybil
patterns, and content manipulation.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from marketplace.models.agent import RegisteredAgent
from marketplace.models.transaction import Transaction

logger = logging.getLogger(__name__)


# ── Anomaly rule definitions ──

class AnomalyRule:
    """Base class for anomaly detection rules."""

    name: str = ""
    severity: str = "medium"  # low | medium | high | critical

    async def evaluate(self, db: AsyncSession, agent_id: str) -> list[dict[str, Any]]:
        raise NotImplementedError


class RapidTransactionRule(AnomalyRule):
    """Detects unusually rapid transaction volume."""

    name = "rapid_transactions"
    severity = "high"

    def __init__(self, threshold: int = 50, window_hours: int = 1):
        self.threshold = threshold
        self.window_hours = window_hours

    async def evaluate(self, db: AsyncSession, agent_id: str) -> list[dict[str, Any]]:
        since = datetime.now(timezone.utc) - timedelta(hours=self.window_hours)
        result = await db.execute(
            select(func.count(Transaction.id)).where(
                and_(
                    (Transaction.buyer_id == agent_id) | (Transaction.seller_id == agent_id),
                    Transaction.created_at >= since,
                )
            )
        )
        count = result.scalar() or 0
        if count >= self.threshold:
            return [{
                "rule": self.name,
                "severity": self.severity,
                "agent_id": agent_id,
                "detail": f"{count} transactions in {self.window_hours}h (threshold: {self.threshold})",
                "value": count,
            }]
        return []


class SelfTradingRule(AnomalyRule):
    """Detects agents trading with themselves (wash trading)."""

    name = "self_trading"
    severity = "critical"

    async def evaluate(self, db: AsyncSession, agent_id: str) -> list[dict[str, Any]]:
        result = await db.execute(
            select(func.count(Transaction.id)).where(
                and_(
                    Transaction.buyer_id == agent_id,
                    Transaction.seller_id == agent_id,
                )
            )
        )
        count = result.scalar() or 0
        if count > 0:
            return [{
                "rule": self.name,
                "severity": self.severity,
                "agent_id": agent_id,
                "detail": f"Agent has {count} self-trade transactions",
                "value": count,
            }]
        return []


class LargeTransactionRule(AnomalyRule):
    """Detects unusually large single transactions."""

    name = "large_transaction"
    severity = "medium"

    def __init__(self, threshold_usd: Decimal = Decimal("1000")):
        self.threshold_usd = threshold_usd

    async def evaluate(self, db: AsyncSession, agent_id: str) -> list[dict[str, Any]]:
        since = datetime.now(timezone.utc) - timedelta(hours=24)
        result = await db.execute(
            select(Transaction).where(
                and_(
                    (Transaction.buyer_id == agent_id) | (Transaction.seller_id == agent_id),
                    Transaction.amount_usdc >= self.threshold_usd,
                    Transaction.created_at >= since,
                )
            )
        )
        large_txs = result.scalars().all()
        anomalies = []
        for tx in large_txs:
            anomalies.append({
                "rule": self.name,
                "severity": self.severity,
                "agent_id": agent_id,
                "detail": f"Transaction {tx.id}: ${tx.amount_usdc} exceeds ${self.threshold_usd} threshold",
                "transaction_id": tx.id,
                "value": float(tx.amount_usdc),
            })
        return anomalies


class NewAccountHighVolumeRule(AnomalyRule):
    """Detects new accounts with unusually high transaction volume."""

    name = "new_account_high_volume"
    severity = "high"

    def __init__(self, account_age_hours: int = 24, tx_threshold: int = 10):
        self.account_age_hours = account_age_hours
        self.tx_threshold = tx_threshold

    async def evaluate(self, db: AsyncSession, agent_id: str) -> list[dict[str, Any]]:
        result = await db.execute(
            select(RegisteredAgent).where(RegisteredAgent.id == agent_id)
        )
        agent = result.scalar_one_or_none()
        if not agent:
            return []

        age = datetime.now(timezone.utc) - (agent.created_at or datetime.now(timezone.utc))
        if age.total_seconds() > self.account_age_hours * 3600:
            return []

        tx_result = await db.execute(
            select(func.count(Transaction.id)).where(
                (Transaction.buyer_id == agent_id) | (Transaction.seller_id == agent_id)
            )
        )
        tx_count = tx_result.scalar() or 0
        if tx_count >= self.tx_threshold:
            return [{
                "rule": self.name,
                "severity": self.severity,
                "agent_id": agent_id,
                "detail": f"New account ({age.total_seconds()/3600:.1f}h old) with {tx_count} transactions",
                "value": tx_count,
            }]
        return []


# ── Default rules ──

DEFAULT_RULES: list[AnomalyRule] = [
    RapidTransactionRule(),
    SelfTradingRule(),
    LargeTransactionRule(),
    NewAccountHighVolumeRule(),
]


# ── Service functions ──

async def detect_anomalies(
    db: AsyncSession,
    agent_id: str,
    rules: list[AnomalyRule] | None = None,
) -> list[dict[str, Any]]:
    """Run all anomaly detection rules against an agent.

    Returns a list of detected anomalies.
    """
    rules = rules or DEFAULT_RULES
    all_anomalies = []
    for rule in rules:
        try:
            anomalies = await rule.evaluate(db, agent_id)
            all_anomalies.extend(anomalies)
        except Exception:
            logger.exception("Anomaly rule %s failed for agent %s", rule.name, agent_id)

    if all_anomalies:
        logger.warning(
            "Detected %d anomalies for agent %s: %s",
            len(all_anomalies),
            agent_id,
            [a["rule"] for a in all_anomalies],
        )

    return all_anomalies


async def scan_all_agents(
    db: AsyncSession,
    limit: int = 100,
) -> dict[str, list[dict[str, Any]]]:
    """Scan recently active agents for anomalies.

    Returns a mapping of agent_id -> list of anomalies.
    """
    since = datetime.now(timezone.utc) - timedelta(hours=24)
    result = await db.execute(
        select(RegisteredAgent.id).where(
            RegisteredAgent.status == "active",
        ).limit(limit)
    )
    agent_ids = [row[0] for row in result.all()]

    results = {}
    for agent_id in agent_ids:
        anomalies = await detect_anomalies(db, agent_id)
        if anomalies:
            results[agent_id] = anomalies

    return results
