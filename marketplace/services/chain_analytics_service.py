"""Chain Analytics Service — performance aggregation and leaderboards.

Provides functions for analysing chain execution performance, discovering
popular chains, and computing per-agent chain participation statistics.
"""

from __future__ import annotations

import json
import logging
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from marketplace.models.chain_template import ChainExecution, ChainTemplate
from marketplace.models.chain_provenance import ChainProvenanceEntry

logger = logging.getLogger(__name__)


async def get_chain_performance(
    db: AsyncSession,
    template_id: str,
) -> dict:
    """Aggregate performance metrics for a chain template.

    Returns execution_count, success_rate, avg_cost_usd, avg_duration_ms,
    and unique_initiators.
    """
    # Total executions
    total_q = select(func.count()).where(
        ChainExecution.chain_template_id == template_id
    )
    total_result = await db.execute(total_q)
    execution_count = total_result.scalar() or 0

    if execution_count == 0:
        return {
            "template_id": template_id,
            "execution_count": 0,
            "success_rate": 0.0,
            "avg_cost_usd": 0.0,
            "avg_duration_ms": 0,
            "unique_initiators": 0,
        }

    # Successful executions
    success_q = select(func.count()).where(
        ChainExecution.chain_template_id == template_id,
        ChainExecution.status == "completed",
    )
    success_result = await db.execute(success_q)
    success_count = success_result.scalar() or 0

    # Average cost
    avg_cost_q = select(func.avg(ChainExecution.total_cost_usd)).where(
        ChainExecution.chain_template_id == template_id,
        ChainExecution.status == "completed",
    )
    avg_cost_result = await db.execute(avg_cost_q)
    avg_cost = avg_cost_result.scalar()

    # Unique initiators
    unique_q = select(func.count(func.distinct(ChainExecution.initiated_by))).where(
        ChainExecution.chain_template_id == template_id,
    )
    unique_result = await db.execute(unique_q)
    unique_initiators = unique_result.scalar() or 0

    # Average duration from provenance entries
    avg_duration_ms = 0
    duration_q = (
        select(func.avg(ChainProvenanceEntry.duration_ms))
        .join(
            ChainExecution,
            ChainExecution.id == ChainProvenanceEntry.chain_execution_id,
        )
        .where(
            ChainExecution.chain_template_id == template_id,
            ChainProvenanceEntry.event_type == "node_completed",
            ChainProvenanceEntry.duration_ms.isnot(None),
        )
    )
    duration_result = await db.execute(duration_q)
    avg_node_duration = duration_result.scalar()
    if avg_node_duration is not None:
        avg_duration_ms = int(avg_node_duration)

    success_rate = (success_count / execution_count * 100) if execution_count else 0.0

    return {
        "template_id": template_id,
        "execution_count": execution_count,
        "success_rate": round(success_rate, 2),
        "avg_cost_usd": float(avg_cost) if avg_cost else 0.0,
        "avg_duration_ms": avg_duration_ms,
        "unique_initiators": unique_initiators,
    }


async def get_popular_chains(
    db: AsyncSession,
    category: str | None = None,
    limit: int = 20,
) -> list[dict]:
    """Return the most-executed chain templates, ordered by execution_count desc."""
    base = select(ChainTemplate).where(ChainTemplate.status == "active")

    if category:
        base = base.where(ChainTemplate.category == category)

    query = (
        base.order_by(ChainTemplate.execution_count.desc())
        .limit(limit)
    )
    result = await db.execute(query)
    templates = list(result.scalars().all())

    popular: list[dict] = []
    for t in templates:
        popular.append({
            "template_id": t.id,
            "name": t.name,
            "description": t.description,
            "category": t.category,
            "author_id": t.author_id,
            "execution_count": t.execution_count or 0,
            "avg_cost_usd": float(t.avg_cost_usd) if t.avg_cost_usd else 0.0,
            "trust_score": t.trust_score or 0,
        })

    return popular


async def get_agent_chain_stats(
    db: AsyncSession,
    agent_id: str,
) -> dict:
    """Compute chain participation statistics for an agent.

    Returns the number of chains the agent participates in, total executions,
    and total earnings from chains.
    """
    # Chains authored by agent
    authored_q = select(func.count()).where(
        ChainTemplate.author_id == agent_id,
        ChainTemplate.status == "active",
    )
    authored_result = await db.execute(authored_q)
    chains_authored = authored_result.scalar() or 0

    # Chains where agent participates (search participant_agents_json)
    # Since SQLite doesn't support JSON array contains, we do a LIKE search
    participant_q = select(func.count()).where(
        ChainExecution.participant_agents_json.contains(agent_id)
    )
    participant_result = await db.execute(participant_q)
    executions_as_participant = participant_result.scalar() or 0

    # Executions initiated by agent
    initiated_q = select(func.count()).where(
        ChainExecution.initiated_by == agent_id
    )
    initiated_result = await db.execute(initiated_q)
    executions_initiated = initiated_result.scalar() or 0

    # Total earnings from provenance entries where agent_id matches
    earnings_q = select(func.sum(ChainProvenanceEntry.cost_usd)).where(
        ChainProvenanceEntry.agent_id == agent_id,
        ChainProvenanceEntry.event_type == "node_completed",
    )
    earnings_result = await db.execute(earnings_q)
    total_earnings = earnings_result.scalar()

    return {
        "agent_id": agent_id,
        "chains_authored": chains_authored,
        "executions_as_participant": executions_as_participant,
        "executions_initiated": executions_initiated,
        "total_earnings_usd": float(total_earnings) if total_earnings else 0.0,
    }
