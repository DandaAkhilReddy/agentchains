"""Chain Registry Service — publish, discover, execute, and trace agent chains.

Provides CRUD for chain templates, SSRF-safe execution via the existing
DAG orchestration engine, idempotent chain execution, and access-controlled
provenance with sensitive-key redaction.
"""

from __future__ import annotations

import copy
import hashlib
import json
import logging
import re
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from marketplace.models.agent import RegisteredAgent
from marketplace.models.chain_template import ChainExecution, ChainTemplate
from marketplace.services.orchestration_service import (
    _topological_sort_layers,
    create_workflow,
    execute_workflow,
    get_execution_nodes,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Sensitive-key patterns for provenance redaction
# ---------------------------------------------------------------------------

_SENSITIVE_PATTERNS: list[re.Pattern] = [
    re.compile(r".*password.*", re.IGNORECASE),
    re.compile(r".*secret.*", re.IGNORECASE),
    re.compile(r".*token.*", re.IGNORECASE),
    re.compile(r".*api_key.*", re.IGNORECASE),
    re.compile(r".*credential.*", re.IGNORECASE),
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _redact_sensitive_keys(data: dict) -> dict:
    """Deep-clone *data*, replacing values whose keys match sensitive patterns."""
    if not isinstance(data, dict):
        return data

    result: dict = {}
    for key, value in data.items():
        if any(pat.match(key) for pat in _SENSITIVE_PATTERNS):
            result[key] = "[REDACTED]"
        elif isinstance(value, dict):
            result[key] = _redact_sensitive_keys(value)
        elif isinstance(value, list):
            result[key] = [
                _redact_sensitive_keys(item) if isinstance(item, dict) else item
                for item in value
            ]
        else:
            result[key] = value
    return result


def _compute_provenance_hash(input_json: str, output_json: str) -> str:
    """SHA-256 of concatenated I/O JSON strings."""
    return hashlib.sha256((input_json + output_json).encode()).hexdigest()


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


async def validate_graph_agents(db: AsyncSession, graph: dict) -> list[str]:
    """Validate that every agent_call node uses agent_id (not raw endpoints).

    Returns a sorted list of unique agent_id values referenced in the graph.

    Raises ``ValueError`` if:
    - Any agent_call node has a raw ``config.endpoint``
    - Any agent_call node is missing ``config.agent_id``
    - Any referenced agent is not found or not active
    - The graph has cycles
    """
    nodes = graph.get("nodes", {})
    agent_ids: set[str] = set()
    errors: list[str] = []

    for node_id, node_def in nodes.items():
        node_type = node_def.get("type", "agent_call")
        if node_type != "agent_call":
            continue

        config = node_def.get("config", {})

        # SSRF: reject raw endpoint URLs
        if config.get("endpoint"):
            errors.append(
                f"Node '{node_id}' has a raw endpoint URL. Use agent_id instead."
            )

        aid = config.get("agent_id")
        if not aid:
            errors.append(f"Node '{node_id}' is missing config.agent_id")
        else:
            agent_ids.add(aid)

    if errors:
        raise ValueError("; ".join(errors))

    # Verify agents exist and are active
    for aid in agent_ids:
        result = await db.execute(
            select(RegisteredAgent).where(RegisteredAgent.id == aid)
        )
        agent = result.scalar_one_or_none()
        if not agent:
            errors.append(f"Agent '{aid}' not found")
        elif agent.status != "active":
            errors.append(f"Agent '{aid}' is not active (status={agent.status})")

    if errors:
        raise ValueError("; ".join(errors))

    # Validate DAG structure (rejects cycles)
    _topological_sort_layers(graph)

    return sorted(agent_ids)


# ---------------------------------------------------------------------------
# CRUD
# ---------------------------------------------------------------------------


async def publish_chain_template(
    db: AsyncSession,
    name: str,
    graph_json: str,
    author_id: str,
    description: str = "",
    category: str = "general",
    tags: list[str] | None = None,
    max_budget_usd: Decimal | None = None,
) -> ChainTemplate:
    """Create and publish a chain template after DAG + SSRF validation.

    Creates a linked WorkflowDefinition for DAG execution.
    """
    try:
        graph = json.loads(graph_json)
    except (json.JSONDecodeError, TypeError) as exc:
        raise ValueError("graph_json must be valid JSON") from exc

    await validate_graph_agents(db, graph)

    workflow = await create_workflow(
        db,
        name=f"chain:{name}",
        graph_json=graph_json,
        owner_id=author_id,
        description=description,
        max_budget_usd=max_budget_usd,
    )

    template = ChainTemplate(
        name=name,
        description=description,
        category=category,
        workflow_id=workflow.id,
        graph_json=graph_json,
        author_id=author_id,
        version=1,
        status="active",
        tags_json=json.dumps(tags or []),
        required_capabilities_json=json.dumps([]),
        max_budget_usd=max_budget_usd,
    )
    db.add(template)
    await db.commit()
    await db.refresh(template)

    logger.info("Published chain template %s (workflow %s)", template.id, workflow.id)
    return template


async def list_chain_templates(
    db: AsyncSession,
    category: str | None = None,
    author_id: str | None = None,
    status: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[ChainTemplate], int]:
    """Paginated list of chain templates with optional filters."""
    base = select(ChainTemplate)

    if category:
        base = base.where(ChainTemplate.category == category)
    if author_id:
        base = base.where(ChainTemplate.author_id == author_id)
    if status:
        base = base.where(ChainTemplate.status == status)

    count_q = select(func.count()).select_from(base.subquery())
    total_result = await db.execute(count_q)
    total = total_result.scalar() or 0

    query = base.order_by(ChainTemplate.created_at.desc()).offset(offset).limit(limit)
    result = await db.execute(query)
    templates = list(result.scalars().all())

    return templates, total


async def get_chain_template(
    db: AsyncSession, template_id: str
) -> ChainTemplate | None:
    """Retrieve a single chain template by ID."""
    result = await db.execute(
        select(ChainTemplate).where(ChainTemplate.id == template_id)
    )
    return result.scalar_one_or_none()


async def fork_chain_template(
    db: AsyncSession,
    source_template_id: str,
    new_author_id: str,
    name: str | None = None,
    graph_json: str | None = None,
) -> ChainTemplate:
    """Fork (clone) a chain template, optionally modifying name or graph.

    Creates a new WorkflowDefinition and ChainTemplate with
    ``forked_from_id`` pointing back to the original.
    """
    source = await get_chain_template(db, source_template_id)
    if not source:
        raise ValueError("Source chain template not found")

    final_graph_json = graph_json or source.graph_json

    # Validate new graph if caller provided one
    if graph_json:
        try:
            graph = json.loads(graph_json)
        except (json.JSONDecodeError, TypeError) as exc:
            raise ValueError("graph_json must be valid JSON") from exc
        await validate_graph_agents(db, graph)

    final_name = name or f"Fork of {source.name}"

    workflow = await create_workflow(
        db,
        name=f"chain:{final_name}",
        graph_json=final_graph_json,
        owner_id=new_author_id,
        description=source.description,
        max_budget_usd=source.max_budget_usd,
    )

    forked = ChainTemplate(
        name=final_name,
        description=source.description,
        category=source.category,
        workflow_id=workflow.id,
        graph_json=final_graph_json,
        author_id=new_author_id,
        forked_from_id=source_template_id,
        version=1,
        status="active",
        tags_json=source.tags_json,
        required_capabilities_json=source.required_capabilities_json,
        max_budget_usd=source.max_budget_usd,
    )
    db.add(forked)
    await db.commit()
    await db.refresh(forked)

    logger.info(
        "Forked chain template %s → %s (author %s)",
        source_template_id,
        forked.id,
        new_author_id,
    )
    return forked
