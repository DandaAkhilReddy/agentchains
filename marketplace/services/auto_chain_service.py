"""Auto-Chaining Service — NL task description to agent DAG composition.

Given a natural-language task description, this service:
1. Extracts required capabilities using keyword matching against a taxonomy.
2. Discovers candidate agents per capability via catalog + agent search.
3. Ranks candidates by reputation, quality, and cost.
4. Builds a DAG (graph_json) ordered by capability flow.
5. Validates the DAG and returns a draft ChainTemplate for user review.
"""

from __future__ import annotations

import json
import logging
import re

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from marketplace.models.agent import RegisteredAgent
from marketplace.models.catalog import DataCatalogEntry
from marketplace.models.reputation import ReputationScore
from marketplace.services.chain_registry_service import (
    validate_graph_agents,
)
from marketplace.services.orchestration_service import _topological_sort_layers

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Capability taxonomy
# ---------------------------------------------------------------------------

CAPABILITY_TAXONOMY: dict[str, list[str]] = {
    "compliance": [
        "regulatory-check", "kyc", "aml", "gdpr", "finma",
        "compliance", "regulation", "audit", "legal",
    ],
    "analysis": [
        "market-analysis", "sentiment", "statistical", "financial",
        "analysis", "analytics", "forecast", "predict", "evaluate",
    ],
    "data": [
        "web-search", "database-query", "api-fetch", "scraping",
        "data", "search", "fetch", "crawl", "retrieve", "lookup",
    ],
    "transform": [
        "translation", "summarization", "formatting", "extraction",
        "transform", "summarize", "translate", "parse", "convert", "extract",
    ],
    "output": [
        "report-generation", "visualization", "notification",
        "report", "generate", "notify", "email", "dashboard", "export",
    ],
}

# Ordered capability flow: data → transform → analysis → compliance → output
CAPABILITY_FLOW_ORDER: list[str] = [
    "data",
    "transform",
    "analysis",
    "compliance",
    "output",
]


# ---------------------------------------------------------------------------
# Capability extraction
# ---------------------------------------------------------------------------


def extract_capabilities(task_description: str) -> list[str]:
    """Match a task description against the capability taxonomy.

    Returns a list of capability categories in flow order
    (data → transform → analysis → compliance → output).
    """
    text = task_description.lower()
    matched: set[str] = set()

    for category, keywords in CAPABILITY_TAXONOMY.items():
        for keyword in keywords:
            if re.search(r"\b" + re.escape(keyword) + r"\b", text):
                matched.add(category)
                break

    # Return in flow order
    return [cap for cap in CAPABILITY_FLOW_ORDER if cap in matched]


# ---------------------------------------------------------------------------
# Agent discovery and ranking
# ---------------------------------------------------------------------------


async def suggest_agents_for_capability(
    db: AsyncSession,
    capability: str,
    *,
    max_results: int = 10,
    max_price: float | None = None,
    min_quality: float | None = None,
) -> list[dict]:
    """Discover and rank active agents that match a given capability.

    Searches both RegisteredAgent.capabilities (JSON array) and
    DataCatalogEntry descriptions/namespaces. Results are ranked by a
    composite of reputation score and catalog quality.
    """
    candidates: dict[str, dict] = {}  # agent_id -> info

    keywords = CAPABILITY_TAXONOMY.get(capability, [capability])

    # 1. Search RegisteredAgent.capabilities JSON field
    agents_q = select(RegisteredAgent).where(RegisteredAgent.status == "active")
    agents_result = await db.execute(agents_q)
    all_agents = list(agents_result.scalars().all())

    for agent in all_agents:
        try:
            caps = json.loads(agent.capabilities) if agent.capabilities else []
        except (json.JSONDecodeError, TypeError):
            caps = []

        cap_text = " ".join(str(c).lower() for c in caps)
        agent_desc = (agent.description or "").lower()

        for kw in keywords:
            if kw in cap_text or kw in agent_desc:
                candidates[agent.id] = {
                    "agent_id": agent.id,
                    "name": agent.name,
                    "description": agent.description or "",
                    "a2a_endpoint": agent.a2a_endpoint,
                    "match_source": "capabilities",
                    "reputation_score": 0.5,
                    "catalog_quality": 0.0,
                    "avg_price": 0.0,
                }
                break

    # 2. Search DataCatalogEntry
    for kw in keywords:
        pattern = f"%{kw}%"
        catalog_q = select(DataCatalogEntry).where(
            DataCatalogEntry.status == "active",
            (
                DataCatalogEntry.topic.ilike(pattern)
                | DataCatalogEntry.description.ilike(pattern)
                | DataCatalogEntry.namespace.ilike(pattern)
            ),
        )
        catalog_result = await db.execute(catalog_q)
        entries = list(catalog_result.scalars().all())

        for entry in entries:
            aid = entry.agent_id
            if aid in candidates:
                candidates[aid]["catalog_quality"] = max(
                    candidates[aid]["catalog_quality"],
                    float(entry.quality_avg or 0),
                )
                candidates[aid]["avg_price"] = float(entry.price_range_min or 0)
                candidates[aid]["match_source"] = "catalog"
            else:
                # Verify agent is active
                agent_r = await db.execute(
                    select(RegisteredAgent).where(
                        RegisteredAgent.id == aid,
                        RegisteredAgent.status == "active",
                    )
                )
                agent_obj = agent_r.scalar_one_or_none()
                if not agent_obj:
                    continue

                candidates[aid] = {
                    "agent_id": aid,
                    "name": agent_obj.name,
                    "description": agent_obj.description or "",
                    "a2a_endpoint": agent_obj.a2a_endpoint,
                    "match_source": "catalog",
                    "reputation_score": 0.5,
                    "catalog_quality": float(entry.quality_avg or 0),
                    "avg_price": float(entry.price_range_min or 0),
                }

    # 3. Enrich with reputation scores
    if candidates:
        rep_q = select(ReputationScore).where(
            ReputationScore.agent_id.in_(list(candidates.keys()))
        )
        rep_result = await db.execute(rep_q)
        reps = list(rep_result.scalars().all())
        for rep in reps:
            if rep.agent_id in candidates:
                candidates[rep.agent_id]["reputation_score"] = float(
                    rep.composite_score or 0.5
                )

    # 4. Apply filters
    filtered = list(candidates.values())

    if max_price is not None:
        filtered = [c for c in filtered if c["avg_price"] <= max_price]

    if min_quality is not None:
        filtered = [
            c for c in filtered
            if c["catalog_quality"] >= min_quality or c["reputation_score"] >= min_quality
        ]

    # 5. Rank: 0.5 * reputation + 0.3 * quality - 0.2 * normalized_price
    max_p = max((c["avg_price"] for c in filtered), default=1.0) or 1.0
    for c in filtered:
        norm_price = c["avg_price"] / max_p if max_p > 0 else 0
        c["rank_score"] = round(
            0.5 * c["reputation_score"]
            + 0.3 * c["catalog_quality"]
            - 0.2 * norm_price,
            4,
        )

    filtered.sort(key=lambda c: c["rank_score"], reverse=True)
    return filtered[:max_results]


# ---------------------------------------------------------------------------
# Chain composition
# ---------------------------------------------------------------------------


def _build_graph(agent_assignments: list[dict]) -> dict:
    """Build a DAG graph_json from an ordered list of agent assignments.

    Each assignment is ``{"capability": str, "agent_id": str}``.
    Nodes are chained linearly in capability-flow order.
    """
    nodes: dict[str, dict] = {}
    prev_id: str | None = None

    for i, assignment in enumerate(agent_assignments):
        node_id = f"node_{assignment['capability']}_{i}"
        node_def: dict = {
            "type": "agent_call",
            "config": {"agent_id": assignment["agent_id"]},
        }
        if prev_id:
            node_def["depends_on"] = [prev_id]
        nodes[node_id] = node_def
        prev_id = node_id

    return {"nodes": nodes, "edges": []}


async def compose_chain_from_task(
    db: AsyncSession,
    task_description: str,
    author_id: str,
    *,
    max_price: float | None = None,
    min_quality: float | None = None,
) -> dict:
    """Compose a draft chain template from a natural-language task description.

    Returns a dict with the draft template fields and agent assignments.
    Does NOT persist anything — the caller can review and then call
    ``publish_chain_template`` to persist.

    Raises ``ValueError`` if no capabilities or agents are found.
    """
    # 1. Extract capabilities
    capabilities = extract_capabilities(task_description)
    if not capabilities:
        raise ValueError(
            "Could not identify any capabilities from the task description. "
            "Try including keywords like: search, analyze, summarize, report, compliance."
        )

    # 2. Find best agent per capability
    assignments: list[dict] = []
    capability_agents: dict[str, list[dict]] = {}

    for cap in capabilities:
        agents = await suggest_agents_for_capability(
            db,
            cap,
            max_results=5,
            max_price=max_price,
            min_quality=min_quality,
        )
        capability_agents[cap] = agents

        if not agents:
            raise ValueError(
                f"No active agents found for capability '{cap}'. "
                f"Register agents with matching capabilities first."
            )

        # Pick the top-ranked agent
        best = agents[0]
        assignments.append({
            "capability": cap,
            "agent_id": best["agent_id"],
            "agent_name": best["name"],
            "rank_score": best["rank_score"],
        })

    # 3. Build graph
    graph = _build_graph(assignments)

    # 4. Validate DAG structure
    _topological_sort_layers(graph)

    # 5. Build draft template response
    graph_json = json.dumps(graph)
    name = f"Auto: {task_description[:80]}"

    return {
        "name": name,
        "description": f"Auto-composed chain for: {task_description}",
        "category": "auto",
        "graph_json": graph_json,
        "status": "draft",
        "capabilities": capabilities,
        "assignments": assignments,
        "alternatives": capability_agents,
    }


# ---------------------------------------------------------------------------
# Chain validation
# ---------------------------------------------------------------------------


async def validate_chain_compatibility(
    db: AsyncSession,
    chain_template_id: str,
) -> dict:
    """Validate that all agents in a chain template are active and reachable.

    Returns a dict with validation status and per-agent details.
    """
    from marketplace.services.chain_registry_service import get_chain_template

    template = await get_chain_template(db, chain_template_id)
    if not template:
        raise ValueError("Chain template not found")

    try:
        graph = json.loads(template.graph_json)
    except (json.JSONDecodeError, TypeError) as exc:
        return {
            "valid": False,
            "template_id": chain_template_id,
            "errors": [f"Invalid graph_json: {exc}"],
            "agents": [],
        }

    agent_details: list[dict] = []
    errors: list[str] = []

    nodes = graph.get("nodes", {})
    for node_id, node_def in nodes.items():
        if node_def.get("type") != "agent_call":
            continue

        config = node_def.get("config", {})
        aid = config.get("agent_id")
        if not aid:
            errors.append(f"Node '{node_id}' missing agent_id")
            continue

        result = await db.execute(
            select(RegisteredAgent).where(RegisteredAgent.id == aid)
        )
        agent = result.scalar_one_or_none()

        if not agent:
            errors.append(f"Agent '{aid}' not found")
            agent_details.append({
                "agent_id": aid,
                "node_id": node_id,
                "status": "not_found",
                "has_endpoint": False,
            })
        elif agent.status != "active":
            errors.append(f"Agent '{aid}' is not active (status={agent.status})")
            agent_details.append({
                "agent_id": aid,
                "node_id": node_id,
                "name": agent.name,
                "status": agent.status,
                "has_endpoint": bool(agent.a2a_endpoint),
            })
        else:
            agent_details.append({
                "agent_id": aid,
                "node_id": node_id,
                "name": agent.name,
                "status": "active",
                "has_endpoint": bool(agent.a2a_endpoint),
            })
            if not agent.a2a_endpoint:
                errors.append(f"Agent '{aid}' has no A2A endpoint configured")

    # Validate DAG structure
    try:
        _topological_sort_layers(graph)
    except ValueError as exc:
        errors.append(str(exc))

    return {
        "valid": len(errors) == 0,
        "template_id": chain_template_id,
        "errors": errors,
        "agents": agent_details,
    }
