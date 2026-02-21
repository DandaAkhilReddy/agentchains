"""Fraud prevention service — Sybil detection and wash trading prevention.

Detects patterns indicating fake agent networks, self-trading,
and other forms of marketplace manipulation.
"""

import logging
from collections import defaultdict
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


class FraudPreventionService:
    """Detects and prevents marketplace fraud."""

    # Thresholds
    SELF_TRADE_WINDOW_HOURS = 24
    MIN_TRANSACTIONS_FOR_SYBIL_CHECK = 5
    SYBIL_OVERLAP_THRESHOLD = 0.8  # 80% transaction overlap = suspicious
    MAX_SAME_IP_AGENTS = 5

    async def check_self_trading(
        self, db: AsyncSession, agent_id: str
    ) -> dict:
        """Detect if an agent is trading with itself or closely linked agents."""
        from marketplace.models.transaction import Transaction

        window_start = datetime.now(timezone.utc) - timedelta(
            hours=self.SELF_TRADE_WINDOW_HOURS
        )

        # Get recent transactions where agent is buyer or seller
        result = await db.execute(
            select(Transaction).where(
                and_(
                    Transaction.created_at > window_start,
                    (Transaction.buyer_id == agent_id)
                    | (Transaction.seller_id == agent_id),
                )
            )
        )
        transactions = result.scalars().all()

        if len(transactions) < self.MIN_TRANSACTIONS_FOR_SYBIL_CHECK:
            return {"suspicious": False, "reason": "insufficient_data"}

        # Check for direct self-trading (same agent as buyer and seller)
        self_trades = [
            t for t in transactions if t.buyer_id == t.seller_id
        ]
        if self_trades:
            return {
                "suspicious": True,
                "reason": "direct_self_trading",
                "count": len(self_trades),
                "severity": "critical",
            }

        # Check for circular trading (A->B->A pattern)
        counterparties = defaultdict(int)
        for t in transactions:
            other = t.seller_id if t.buyer_id == agent_id else t.buyer_id
            counterparties[other] += 1

        total = len(transactions)
        for other_id, count in counterparties.items():
            if count / total > self.SYBIL_OVERLAP_THRESHOLD:
                return {
                    "suspicious": True,
                    "reason": "concentrated_counterparty",
                    "counterparty_id": other_id,
                    "transaction_ratio": round(count / total, 2),
                    "severity": "high",
                }

        return {"suspicious": False, "reason": "normal_trading"}

    async def detect_sybil_cluster(
        self, db: AsyncSession, agent_id: str
    ) -> dict:
        """Detect Sybil attack patterns — groups of fake agents."""
        from marketplace.models.agent import RegisteredAgent
        from marketplace.models.transaction import Transaction

        # Find all agents the target has transacted with
        result = await db.execute(
            select(Transaction).where(
                (Transaction.buyer_id == agent_id)
                | (Transaction.seller_id == agent_id)
            )
        )
        transactions = result.scalars().all()

        if not transactions:
            return {"sybil_detected": False, "cluster_size": 0}

        # Build a counterparty graph
        counterparties = set()
        for t in transactions:
            counterparties.add(t.buyer_id)
            counterparties.add(t.seller_id)
        counterparties.discard(agent_id)

        if not counterparties:
            return {"sybil_detected": False, "cluster_size": 0}

        # Check registration timestamps — Sybil agents often register close together
        result = await db.execute(
            select(RegisteredAgent).where(
                RegisteredAgent.id.in_(list(counterparties))
            )
        )
        agents = result.scalars().all()

        if len(agents) < 3:
            return {"sybil_detected": False, "cluster_size": len(agents)}

        # Check for burst registration (multiple agents in short window)
        sorted_agents = sorted(agents, key=lambda a: a.created_at or datetime.min)
        burst_groups = []
        current_group = [sorted_agents[0]]

        for agent in sorted_agents[1:]:
            if agent.created_at and current_group[-1].created_at:
                delta = abs((agent.created_at - current_group[-1].created_at).total_seconds())
                if delta < 300:  # 5-minute window
                    current_group.append(agent)
                else:
                    if len(current_group) >= 3:
                        burst_groups.append(current_group)
                    current_group = [agent]
            else:
                current_group = [agent]

        if len(current_group) >= 3:
            burst_groups.append(current_group)

        if burst_groups:
            largest = max(burst_groups, key=len)
            return {
                "sybil_detected": True,
                "cluster_size": len(largest),
                "suspect_agent_ids": [a.id for a in largest],
                "severity": "critical" if len(largest) >= 5 else "high",
            }

        return {"sybil_detected": False, "cluster_size": len(agents)}

    async def check_price_manipulation(
        self, db: AsyncSession, listing_id: str
    ) -> dict:
        """Detect price manipulation on a listing."""
        from marketplace.models.transaction import Transaction

        result = await db.execute(
            select(Transaction)
            .where(Transaction.listing_id == listing_id)
            .order_by(Transaction.created_at)
        )
        transactions = result.scalars().all()

        if len(transactions) < 3:
            return {"manipulation_detected": False, "reason": "insufficient_data"}

        # Check for sudden price spikes (>200% increase)
        amounts = [float(t.amount_usdc) for t in transactions]
        for i in range(1, len(amounts)):
            if amounts[i - 1] > 0 and amounts[i] / amounts[i - 1] > 3.0:
                return {
                    "manipulation_detected": True,
                    "reason": "sudden_price_spike",
                    "spike_ratio": round(amounts[i] / amounts[i - 1], 2),
                    "severity": "high",
                }

        return {"manipulation_detected": False, "reason": "normal_pricing"}


# Singleton
fraud_prevention_service = FraudPreventionService()
