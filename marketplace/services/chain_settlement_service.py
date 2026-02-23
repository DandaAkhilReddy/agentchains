"""Chain Settlement Service — multi-party settlement via token_service.transfer.

Handles deterministic pricing (platform-stored prices, NOT agent-reported _cost),
idempotent settlement with per-node transfer keys, and settlement reports.
"""

from __future__ import annotations

import hashlib
import json
import logging
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from marketplace.models.action_listing import ActionListing
from marketplace.models.agent import RegisteredAgent
from marketplace.models.catalog import DataCatalogEntry
from marketplace.models.chain_template import ChainExecution, ChainTemplate
from marketplace.models.listing import DataListing
from marketplace.models.token_account import TokenLedger
from marketplace.services.orchestration_service import get_execution_nodes
from marketplace.services.token_service import transfer

logger = logging.getLogger(__name__)


async def _get_platform_price(
    db: AsyncSession,
    agent_id: str,
) -> Decimal:
    """Retrieve the deterministic platform price for an agent.

    Checks DataListing, ActionListing, and DataCatalogEntry in order.
    Falls back to Decimal("0") if no listing is found.
    """
    # Check DataListing first
    result = await db.execute(
        select(DataListing.price_usdc)
        .where(DataListing.seller_id == agent_id, DataListing.status == "active")
        .order_by(DataListing.created_at.desc())
        .limit(1)
    )
    price = result.scalar_one_or_none()
    if price is not None:
        return Decimal(str(price))

    # Check ActionListing
    result = await db.execute(
        select(ActionListing.price_per_execution)
        .where(ActionListing.seller_id == agent_id, ActionListing.status == "active")
        .order_by(ActionListing.created_at.desc())
        .limit(1)
    )
    price = result.scalar_one_or_none()
    if price is not None:
        return Decimal(str(price))

    # Check DataCatalogEntry average price
    result = await db.execute(
        select(DataCatalogEntry.price_range_min)
        .where(DataCatalogEntry.agent_id == agent_id, DataCatalogEntry.status == "active")
        .order_by(DataCatalogEntry.created_at.desc())
        .limit(1)
    )
    price = result.scalar_one_or_none()
    if price is not None:
        return Decimal(str(price))

    return Decimal("0")


async def settle_chain_execution(
    db: AsyncSession,
    chain_execution_id: str,
) -> dict:
    """Settle all agent payments for a completed chain execution.

    Uses deterministic platform-stored prices (NOT agent-reported _cost).
    Each node transfer uses an idempotency key to prevent double settlement.

    Returns:
        dict with settlement summary: total_settled, transfers list, errors.
    """
    # Load execution
    exec_result = await db.execute(
        select(ChainExecution).where(ChainExecution.id == chain_execution_id)
    )
    chain_exec = exec_result.scalar_one_or_none()
    if not chain_exec:
        raise ValueError("Chain execution not found")

    if chain_exec.status != "completed":
        raise ValueError(
            f"Cannot settle execution with status '{chain_exec.status}'. "
            "Only completed executions can be settled."
        )

    if not chain_exec.workflow_execution_id:
        raise ValueError("Chain execution has no associated workflow execution")

    # Get node executions
    node_executions = await get_execution_nodes(db, chain_exec.workflow_execution_id)

    buyer_id = chain_exec.initiated_by
    total_settled = Decimal("0")
    transfers: list[dict] = []
    errors: list[dict] = []

    for ne in node_executions:
        if ne.node_type != "agent_call" or ne.status != "completed":
            continue

        # Parse node config to get agent_id
        try:
            node_input = json.loads(ne.input_json) if ne.input_json else {}
        except (json.JSONDecodeError, TypeError):
            node_input = {}

        # The agent_id may be embedded in the input data from workflow context
        # or we can look it up from the workflow graph
        agent_id = node_input.get("agent_id")

        # If not in input, try to get from the graph via template
        if not agent_id:
            template_result = await db.execute(
                select(ChainTemplate).where(
                    ChainTemplate.id == chain_exec.chain_template_id
                )
            )
            template = template_result.scalar_one_or_none()
            if template:
                graph = json.loads(template.graph_json)
                node_config = graph.get("nodes", {}).get(ne.node_id, {}).get("config", {})
                agent_id = node_config.get("agent_id")

        if not agent_id:
            continue

        # Deterministic pricing from platform
        price = await _get_platform_price(db, agent_id)
        if price <= 0:
            continue

        # Build idempotency key: chn-{exec_id[:16]}-{sha256(node_id)[:16]}
        node_hash = hashlib.sha256(ne.node_id.encode()).hexdigest()[:16]
        idempotency_key = f"chn-{chain_execution_id[:16]}-{node_hash}"

        try:
            ledger = await transfer(
                db,
                from_agent_id=buyer_id,
                to_agent_id=agent_id,
                amount=price,
                tx_type="chain_settlement",
                reference_id=chain_execution_id,
                reference_type="chain_execution",
                idempotency_key=idempotency_key,
                memo=f"Chain settlement: node {ne.node_id} in execution {chain_execution_id[:8]}",
            )
            total_settled += price
            transfers.append({
                "node_id": ne.node_id,
                "agent_id": agent_id,
                "amount_usd": float(price),
                "ledger_id": ledger.id,
                "idempotency_key": idempotency_key,
            })
        except ValueError as exc:
            errors.append({
                "node_id": ne.node_id,
                "agent_id": agent_id,
                "error": str(exc),
            })
            logger.warning(
                "Settlement failed for node %s agent %s: %s",
                ne.node_id, agent_id, exc,
            )

    return {
        "chain_execution_id": chain_execution_id,
        "status": "settled" if not errors else "partial",
        "total_settled_usd": float(total_settled),
        "transfers": transfers,
        "errors": errors,
    }


async def estimate_chain_cost(
    db: AsyncSession,
    chain_template_id: str,
) -> dict:
    """Pre-execution cost estimate based on platform-stored agent prices.

    Falls back to historical average from ChainExecution if no prices found.
    """
    template_result = await db.execute(
        select(ChainTemplate).where(ChainTemplate.id == chain_template_id)
    )
    template = template_result.scalar_one_or_none()
    if not template:
        raise ValueError("Chain template not found")

    graph = json.loads(template.graph_json)
    total_estimate = Decimal("0")
    agent_costs: list[dict] = []

    for node_id, node_def in graph.get("nodes", {}).items():
        if node_def.get("type", "agent_call") != "agent_call":
            continue

        agent_id = node_def.get("config", {}).get("agent_id")
        if not agent_id:
            continue

        price = await _get_platform_price(db, agent_id)
        total_estimate += price
        agent_costs.append({
            "node_id": node_id,
            "agent_id": agent_id,
            "estimated_cost_usd": float(price),
        })

    # Also check historical average
    avg_q = select(func.avg(ChainExecution.total_cost_usd)).where(
        ChainExecution.chain_template_id == chain_template_id,
        ChainExecution.status == "completed",
    )
    avg_result = await db.execute(avg_q)
    historical_avg = avg_result.scalar()

    return {
        "chain_template_id": chain_template_id,
        "estimated_total_usd": float(total_estimate),
        "agent_costs": agent_costs,
        "historical_avg_usd": float(historical_avg) if historical_avg else None,
    }


async def get_settlement_report(
    db: AsyncSession,
    chain_execution_id: str,
) -> dict:
    """Get a per-agent breakdown of settlement for a chain execution."""
    exec_result = await db.execute(
        select(ChainExecution).where(ChainExecution.id == chain_execution_id)
    )
    chain_exec = exec_result.scalar_one_or_none()
    if not chain_exec:
        raise ValueError("Chain execution not found")

    # Find all settlement ledger entries for this execution
    result = await db.execute(
        select(TokenLedger).where(
            TokenLedger.reference_id == chain_execution_id,
            TokenLedger.tx_type == "chain_settlement",
        )
    )
    entries = list(result.scalars().all())

    total_paid = Decimal("0")
    total_fees = Decimal("0")
    agent_payments: list[dict] = []

    for entry in entries:
        total_paid += Decimal(str(entry.amount))
        total_fees += Decimal(str(entry.fee_amount))

        agent_payments.append({
            "ledger_id": entry.id,
            "amount_usd": float(entry.amount),
            "fee_usd": float(entry.fee_amount),
            "memo": entry.memo,
            "idempotency_key": entry.idempotency_key,
            "created_at": entry.created_at.isoformat() if entry.created_at else None,
        })

    return {
        "chain_execution_id": chain_execution_id,
        "execution_status": chain_exec.status,
        "total_paid_usd": float(total_paid),
        "total_fees_usd": float(total_fees),
        "payments": agent_payments,
    }
