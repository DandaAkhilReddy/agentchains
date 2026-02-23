"""Chain Policy Service — policy evaluation for chain execution.

Provides functions to create, list, and evaluate policies against chain
templates before or during execution. Supports jurisdiction, data residency,
and cost limit policy types.
"""

from __future__ import annotations

import json
import logging
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from marketplace.models.agent import RegisteredAgent
from marketplace.models.chain_policy import ChainPolicy
from marketplace.models.chain_template import ChainTemplate
from marketplace.services.chain_registry_service import validate_graph_agents

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# CRUD
# ---------------------------------------------------------------------------


async def create_policy(
    db: AsyncSession,
    name: str,
    policy_type: str,
    rules_json: str,
    owner_id: str,
    description: str = "",
    enforcement: str = "block",
    scope: str = "chain",
) -> ChainPolicy:
    """Create a new chain policy."""
    try:
        json.loads(rules_json)
    except (json.JSONDecodeError, TypeError) as exc:
        raise ValueError("rules_json must be valid JSON") from exc

    if policy_type not in ("jurisdiction", "data_residency", "cost_limit"):
        raise ValueError(
            f"Invalid policy_type: {policy_type}. "
            "Must be 'jurisdiction', 'data_residency', or 'cost_limit'"
        )

    if enforcement not in ("block", "warn", "log"):
        raise ValueError(
            f"Invalid enforcement: {enforcement}. Must be 'block', 'warn', or 'log'"
        )

    policy = ChainPolicy(
        name=name,
        description=description,
        policy_type=policy_type,
        rules_json=rules_json,
        enforcement=enforcement,
        owner_id=owner_id,
        scope=scope,
        status="active",
    )
    db.add(policy)
    await db.commit()
    await db.refresh(policy)

    logger.info("Created policy %s (%s) for owner %s", policy.id, policy_type, owner_id)
    return policy


async def list_policies(
    db: AsyncSession,
    owner_id: str | None = None,
    policy_type: str | None = None,
    status: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[ChainPolicy], int]:
    """List policies with optional filters."""
    base = select(ChainPolicy)

    if owner_id:
        base = base.where(ChainPolicy.owner_id == owner_id)
    if policy_type:
        base = base.where(ChainPolicy.policy_type == policy_type)
    if status:
        base = base.where(ChainPolicy.status == status)

    count_q = select(func.count()).select_from(base.subquery())
    total_result = await db.execute(count_q)
    total = total_result.scalar() or 0

    query = base.order_by(ChainPolicy.created_at.desc()).offset(offset).limit(limit)
    result = await db.execute(query)
    policies = list(result.scalars().all())

    return policies, total


async def get_policy(db: AsyncSession, policy_id: str) -> ChainPolicy | None:
    """Retrieve a single policy by ID."""
    result = await db.execute(
        select(ChainPolicy).where(ChainPolicy.id == policy_id)
    )
    return result.scalar_one_or_none()


# ---------------------------------------------------------------------------
# Policy evaluation
# ---------------------------------------------------------------------------


def check_jurisdiction_policy(
    chain_agents: list[dict],
    allowed_jurisdictions: list[str],
) -> dict:
    """Check if all agents in a chain operate within allowed jurisdictions.

    Args:
        chain_agents: List of agent dicts with optional 'jurisdictions' field.
        allowed_jurisdictions: List of allowed jurisdiction codes (e.g. ["CH", "IN"]).

    Returns:
        dict with 'passed', 'violations' keys.
    """
    violations: list[dict] = []

    for agent in chain_agents:
        agent_jurisdictions = agent.get("jurisdictions", [])
        if not agent_jurisdictions:
            continue

        disallowed = [
            j for j in agent_jurisdictions
            if j not in allowed_jurisdictions
        ]
        if disallowed:
            violations.append({
                "agent_id": agent.get("id", "unknown"),
                "agent_name": agent.get("name", "unknown"),
                "disallowed_jurisdictions": disallowed,
            })

    return {
        "passed": len(violations) == 0,
        "violations": violations,
    }


def check_cost_policy(
    estimated_cost: float | Decimal,
    max_allowed: float | Decimal,
) -> dict:
    """Check if estimated chain cost is within budget limits.

    Returns:
        dict with 'passed', 'estimated_cost', 'max_allowed' keys.
    """
    est = float(estimated_cost)
    cap = float(max_allowed)

    return {
        "passed": est <= cap,
        "estimated_cost": est,
        "max_allowed": cap,
    }


async def evaluate_chain_policies(
    db: AsyncSession,
    chain_template_id: str,
    policy_ids: list[str],
) -> dict:
    """Evaluate a chain template against a set of policies.

    Returns a report with overall pass/fail and per-policy results.
    """
    template_result = await db.execute(
        select(ChainTemplate).where(ChainTemplate.id == chain_template_id)
    )
    template = template_result.scalar_one_or_none()
    if not template:
        raise ValueError("Chain template not found")

    graph = json.loads(template.graph_json)

    # Collect agent info for policy checks
    agent_ids: list[str] = []
    for node_id, node_def in graph.get("nodes", {}).items():
        if node_def.get("type", "agent_call") == "agent_call":
            aid = node_def.get("config", {}).get("agent_id")
            if aid:
                agent_ids.append(aid)

    chain_agents: list[dict] = []
    for aid in set(agent_ids):
        result = await db.execute(
            select(RegisteredAgent).where(RegisteredAgent.id == aid)
        )
        agent = result.scalar_one_or_none()
        if agent:
            # Parse agent_card_json for jurisdiction info
            card = {}
            if agent.agent_card_json:
                try:
                    card = json.loads(agent.agent_card_json)
                except (json.JSONDecodeError, TypeError):
                    pass

            jurisdictions = []
            extensions = card.get("capabilities", {}).get("extensions", [])
            for ext in extensions:
                params = ext.get("params", {})
                jurisdictions = params.get("jurisdictions", [])

            chain_agents.append({
                "id": agent.id,
                "name": agent.name,
                "jurisdictions": jurisdictions,
            })

    # Evaluate each policy
    results: list[dict] = []
    all_passed = True
    block_reasons: list[str] = []

    for pid in policy_ids:
        policy = await get_policy(db, pid)
        if not policy:
            results.append({
                "policy_id": pid,
                "status": "not_found",
                "passed": False,
            })
            all_passed = False
            continue

        if policy.status != "active":
            results.append({
                "policy_id": pid,
                "name": policy.name,
                "status": "disabled",
                "passed": True,
            })
            continue

        rules = json.loads(policy.rules_json)
        passed = True
        details: dict = {}

        if policy.policy_type == "jurisdiction":
            allowed = rules.get("allowed_jurisdictions", [])
            check = check_jurisdiction_policy(chain_agents, allowed)
            passed = check["passed"]
            details = check

        elif policy.policy_type == "cost_limit":
            max_cost = rules.get("max_cost_usd", 0)
            # Estimate from template budget or average cost
            estimated = float(template.max_budget_usd or template.avg_cost_usd or 0)
            check = check_cost_policy(estimated, max_cost)
            passed = check["passed"]
            details = check

        elif policy.policy_type == "data_residency":
            allowed_regions = rules.get("allowed_regions", [])
            check = check_jurisdiction_policy(chain_agents, allowed_regions)
            passed = check["passed"]
            details = check

        if not passed and policy.enforcement == "block":
            all_passed = False
            block_reasons.append(f"Policy '{policy.name}' ({policy.policy_type}) failed")

        results.append({
            "policy_id": pid,
            "name": policy.name,
            "policy_type": policy.policy_type,
            "enforcement": policy.enforcement,
            "passed": passed,
            "details": details,
        })

    return {
        "chain_template_id": chain_template_id,
        "overall_passed": all_passed,
        "block_reasons": block_reasons,
        "policy_results": results,
    }
