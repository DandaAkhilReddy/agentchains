"""Fraud prevention service — Sybil attack detection.

Identifies clusters of agents that may be controlled by the same entity
based on behavioral patterns, registration metadata, and transaction graphs.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from marketplace.models.agent import RegisteredAgent
from marketplace.models.transaction import Transaction

logger = logging.getLogger(__name__)


async def detect_sybil_clusters(
    db: AsyncSession,
    min_cluster_size: int = 3,
) -> list[dict[str, Any]]:
    """Detect potential Sybil clusters based on transaction graph analysis.

    Agents that form tight trading loops (A->B->C->A) with no external
    activity are flagged as potential Sybils.
    """
    since = datetime.now(timezone.utc) - timedelta(days=7)

    result = await db.execute(
        select(
            Transaction.buyer_id,
            Transaction.seller_id,
            func.count(Transaction.id).label("tx_count"),
        ).where(
            and_(
                Transaction.status == "completed",
                Transaction.created_at >= since,
            )
        ).group_by(Transaction.buyer_id, Transaction.seller_id)
    )
    edges = result.all()

    # Build adjacency graph
    graph: dict[str, set[str]] = defaultdict(set)
    edge_weights: dict[tuple[str, str], int] = {}
    for buyer_id, seller_id, tx_count in edges:
        if buyer_id == seller_id:
            continue
        graph[buyer_id].add(seller_id)
        graph[seller_id].add(buyer_id)
        edge_weights[(buyer_id, seller_id)] = tx_count

    # Find connected components (simple BFS)
    visited: set[str] = set()
    clusters = []

    for node in graph:
        if node in visited:
            continue
        cluster = set()
        queue = [node]
        while queue:
            current = queue.pop(0)
            if current in visited:
                continue
            visited.add(current)
            cluster.add(current)
            for neighbor in graph.get(current, set()):
                if neighbor not in visited:
                    queue.append(neighbor)

        if len(cluster) >= min_cluster_size:
            # Check if the cluster is tightly connected (high internal density)
            internal_edges = sum(
                1 for a in cluster for b in cluster
                if a != b and b in graph.get(a, set())
            )
            max_edges = len(cluster) * (len(cluster) - 1)
            density = internal_edges / max_edges if max_edges > 0 else 0

            if density > 0.5:  # More than 50% of possible edges exist
                total_volume = sum(
                    edge_weights.get((a, b), 0)
                    for a in cluster for b in cluster
                    if (a, b) in edge_weights
                )
                clusters.append({
                    "agent_ids": list(cluster),
                    "size": len(cluster),
                    "density": round(density, 3),
                    "internal_transactions": internal_edges,
                    "total_volume": total_volume,
                    "risk_level": "critical" if density > 0.8 else "high",
                })

    if clusters:
        logger.warning("Detected %d potential Sybil clusters", len(clusters))

    return clusters


async def detect_registration_bursts(
    db: AsyncSession,
    window_minutes: int = 60,
    threshold: int = 10,
) -> list[dict[str, Any]]:
    """Detect bursts of agent registrations in short time windows.

    Rapid registration of many agents may indicate bot or Sybil activity.
    """
    since = datetime.now(timezone.utc) - timedelta(hours=24)

    result = await db.execute(
        select(RegisteredAgent).where(
            RegisteredAgent.created_at >= since
        ).order_by(RegisteredAgent.created_at)
    )
    agents = result.scalars().all()

    bursts = []
    window = timedelta(minutes=window_minutes)

    for i, agent in enumerate(agents):
        window_agents = [
            a for a in agents[i:]
            if a.created_at and agent.created_at
            and a.created_at - agent.created_at <= window
        ]
        if len(window_agents) >= threshold:
            burst_ids = [a.id for a in window_agents]
            # Deduplicate (check if this burst overlaps with previous)
            if not bursts or set(burst_ids) != set(bursts[-1].get("agent_ids", [])):
                bursts.append({
                    "agent_ids": burst_ids,
                    "count": len(window_agents),
                    "window_start": agent.created_at.isoformat() if agent.created_at else "",
                    "window_minutes": window_minutes,
                    "risk_level": "high" if len(window_agents) >= threshold * 2 else "medium",
                })

    return bursts


async def get_fraud_report(db: AsyncSession) -> dict[str, Any]:
    """Generate a comprehensive fraud prevention report."""
    sybil_clusters = await detect_sybil_clusters(db)
    reg_bursts = await detect_registration_bursts(db)

    return {
        "sybil_clusters": sybil_clusters,
        "registration_bursts": reg_bursts,
        "total_sybil_agents": sum(c["size"] for c in sybil_clusters),
        "total_burst_agents": sum(b["count"] for b in reg_bursts),
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


class FraudPreventionService:
    """Service wrapper for fraud prevention operations."""

    def __init__(self, db: AsyncSession | None = None):
        self.db = db

    async def detect_sybil_clusters(self, min_cluster_size: int = 3):
        if self.db is None:
            raise ValueError("Database session required")
        return await detect_sybil_clusters(self.db, min_cluster_size)

    async def get_fraud_report(self):
        if self.db is None:
            raise ValueError("Database session required")
        return await get_fraud_report(self.db)
