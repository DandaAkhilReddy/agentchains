"""Immutable audit logging with SHA-256 hash chain."""

import json
import logging
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from marketplace.core.hashing import compute_audit_hash
from marketplace.models.audit_log import AuditLog

logger = logging.getLogger(__name__)


async def log_event(
    db: AsyncSession,
    event_type: str,
    *,
    agent_id: str | None = None,
    creator_id: str | None = None,
    ip_address: str | None = None,
    user_agent: str = "",
    details: dict | None = None,
    severity: str = "info",
) -> AuditLog:
    latest = await db.execute(
        select(AuditLog.entry_hash).order_by(AuditLog.created_at.desc()).limit(1)
    )
    prev_hash = latest.scalar_one_or_none()

    created_at = datetime.now(timezone.utc)
    details_json = json.dumps(details or {}, sort_keys=True, default=str)

    entry_hash = compute_audit_hash(
        prev_hash, event_type, agent_id or creator_id, details_json, severity, created_at.isoformat(),
    )

    entry = AuditLog(
        event_type=event_type,
        agent_id=agent_id,
        creator_id=creator_id,
        ip_address=ip_address,
        user_agent=user_agent,
        details=details_json,
        severity=severity,
        prev_hash=prev_hash,
        entry_hash=entry_hash,
        created_at=created_at,
    )
    db.add(entry)
    await db.flush()
    return entry
