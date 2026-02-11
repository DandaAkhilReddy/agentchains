"""Audit log query endpoints."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from marketplace.core.auth import get_current_agent_id
from marketplace.core.hashing import compute_audit_hash
from marketplace.database import get_db
from marketplace.models.audit_log import AuditLog

router = APIRouter(prefix="/audit", tags=["audit"])


@router.get("/events")
async def list_audit_events(
    event_type: str | None = None,
    severity: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    _agent_id: str = Depends(get_current_agent_id),
):
    stmt = select(AuditLog).order_by(AuditLog.created_at.desc())
    if event_type:
        stmt = stmt.where(AuditLog.event_type == event_type)
    if severity:
        stmt = stmt.where(AuditLog.severity == severity)
    stmt = stmt.offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(stmt)
    entries = result.scalars().all()

    count_stmt = select(func.count(AuditLog.id))
    if event_type:
        count_stmt = count_stmt.where(AuditLog.event_type == event_type)
    if severity:
        count_stmt = count_stmt.where(AuditLog.severity == severity)
    total = (await db.execute(count_stmt)).scalar() or 0

    return {
        "events": [
            {
                "id": e.id, "event_type": e.event_type, "agent_id": e.agent_id,
                "severity": e.severity, "details": e.details,
                "entry_hash": e.entry_hash, "created_at": str(e.created_at),
            }
            for e in entries
        ],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.get("/events/verify")
async def verify_audit_chain(
    limit: int = Query(1000, ge=1, le=10000),
    db: AsyncSession = Depends(get_db),
    _agent_id: str = Depends(get_current_agent_id),
):
    entries = await db.execute(
        select(AuditLog).order_by(AuditLog.created_at.asc()).limit(limit)
    )
    entries = entries.scalars().all()

    prev_hash = None
    checked = 0
    for entry in entries:
        if entry.entry_hash is None:
            continue
        expected = compute_audit_hash(
            prev_hash, entry.event_type, entry.agent_id or entry.creator_id,
            entry.details, entry.severity, entry.created_at.isoformat(),
        )
        if expected != entry.entry_hash:
            return {"valid": False, "broken_at": entry.id, "entry_number": checked + 1}
        prev_hash = entry.entry_hash
        checked += 1

    return {"valid": True, "entries_checked": checked}
