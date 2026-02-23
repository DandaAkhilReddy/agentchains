"""Chain Provenance Service — persistent provenance entries and timeline queries.

Provides a callback factory for the orchestration engine to write provenance
entries as nodes start, complete, or fail, plus query helpers for retrieval.
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Coroutine
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from marketplace.models.chain_provenance import ChainProvenanceEntry
from marketplace.services.chain_registry_service import (
    _compute_provenance_hash,
    _redact_sensitive_keys,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Callback factory
# ---------------------------------------------------------------------------


def make_provenance_callback(
    chain_execution_id: str,
) -> Callable[..., Coroutine[Any, Any, None]]:
    """Return an ``on_node_event`` callback that writes ChainProvenanceEntry rows.

    The callback creates its own DB session via ``async_session`` so it is
    safe to call after the request session has been closed (background tasks).
    """

    async def _on_node_event(
        event_type: str,
        node_id: str,
        node_type: str,
        *,
        agent_id: str | None = None,
        input_json: str | None = None,
        output_json: str | None = None,
        cost_usd: Decimal | None = None,
        duration_ms: int | None = None,
        error_message: str | None = None,
    ) -> None:
        from marketplace.database import async_session as session_factory

        status_map = {
            "node_started": "running",
            "node_completed": "completed",
            "node_failed": "failed",
        }
        status = status_map.get(event_type, event_type)

        input_hash = _compute_provenance_hash(input_json or "", "") if input_json else None
        output_hash = _compute_provenance_hash("", output_json or "") if output_json else None

        entry = ChainProvenanceEntry(
            chain_execution_id=chain_execution_id,
            node_id=node_id,
            event_type=event_type,
            event_timestamp=datetime.now(timezone.utc),
            node_type=node_type,
            agent_id=agent_id,
            input_hash_sha256=input_hash,
            output_hash_sha256=output_hash,
            duration_ms=duration_ms,
            cost_usd=cost_usd or Decimal("0"),
            status=status,
            error_message=error_message,
        )

        try:
            async with session_factory() as db:
                db.add(entry)
                await db.commit()
        except Exception:
            logger.exception(
                "Failed to write provenance entry for chain %s node %s",
                chain_execution_id,
                node_id,
            )

    return _on_node_event


# ---------------------------------------------------------------------------
# Query helpers
# ---------------------------------------------------------------------------


async def get_provenance_entries(
    db: AsyncSession,
    chain_execution_id: str,
    event_type: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> tuple[list[ChainProvenanceEntry], int]:
    """Paginated query for provenance entries with optional event_type filter."""
    base = select(ChainProvenanceEntry).where(
        ChainProvenanceEntry.chain_execution_id == chain_execution_id
    )
    if event_type:
        base = base.where(ChainProvenanceEntry.event_type == event_type)

    count_q = select(func.count()).select_from(base.subquery())
    total_result = await db.execute(count_q)
    total = total_result.scalar() or 0

    query = (
        base.order_by(ChainProvenanceEntry.event_timestamp)
        .offset(offset)
        .limit(limit)
    )
    result = await db.execute(query)
    entries = list(result.scalars().all())

    return entries, total


async def get_provenance_timeline(
    db: AsyncSession,
    chain_execution_id: str,
) -> list[dict]:
    """Return all provenance events for an execution, ordered chronologically.

    Sensitive keys in metadata are redacted before returning.
    """
    result = await db.execute(
        select(ChainProvenanceEntry)
        .where(ChainProvenanceEntry.chain_execution_id == chain_execution_id)
        .order_by(ChainProvenanceEntry.event_timestamp)
    )
    entries = list(result.scalars().all())

    timeline: list[dict] = []
    for e in entries:
        import json

        try:
            meta = json.loads(e.metadata_json) if e.metadata_json else {}
        except (json.JSONDecodeError, TypeError):
            meta = {}

        timeline.append({
            "id": e.id,
            "node_id": e.node_id,
            "event_type": e.event_type,
            "event_timestamp": (
                e.event_timestamp.isoformat() if e.event_timestamp else None
            ),
            "node_type": e.node_type,
            "agent_id": e.agent_id,
            "input_hash_sha256": e.input_hash_sha256,
            "output_hash_sha256": e.output_hash_sha256,
            "duration_ms": e.duration_ms,
            "cost_usd": float(e.cost_usd) if e.cost_usd else 0.0,
            "status": e.status,
            "error_message": e.error_message,
            "attempt_number": e.attempt_number,
            "metadata": _redact_sensitive_keys(meta),
            "created_at": e.created_at.isoformat() if e.created_at else None,
        })

    return timeline
