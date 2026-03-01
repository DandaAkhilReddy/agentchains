"""Auth event service — log security events and detect brute-force attacks."""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from marketplace.models.auth_event import AuthEvent

logger = logging.getLogger(__name__)


async def log_auth_event(
    db: AsyncSession,
    *,
    actor_id: str | None = None,
    actor_type: str | None = None,
    event_type: str,
    ip_address: str | None = None,
    user_agent: str | None = None,
    details: dict | None = None,
) -> None:
    """Log an authentication/authorization event (fire-and-forget safe)."""
    try:
        event = AuthEvent(
            id=str(uuid.uuid4()),
            actor_id=actor_id,
            actor_type=actor_type,
            event_type=event_type,
            ip_address=ip_address,
            user_agent=user_agent,
            details_json=json.dumps(details or {}),
        )
        db.add(event)
        await db.commit()
    except Exception:
        logger.exception("Failed to log auth event: %s", event_type)


async def get_events(
    db: AsyncSession,
    *,
    actor_id: str | None = None,
    event_type: str | None = None,
    since: datetime | None = None,
    page: int = 1,
    page_size: int = 50,
) -> tuple[list[AuthEvent], int]:
    """Query auth events with optional filters and pagination."""
    base = select(AuthEvent)
    if actor_id:
        base = base.where(AuthEvent.actor_id == actor_id)
    if event_type:
        base = base.where(AuthEvent.event_type == event_type)
    if since:
        base = base.where(AuthEvent.created_at >= since)

    count_q = select(func.count()).select_from(base.subquery())
    total_result = await db.execute(count_q)
    total = total_result.scalar() or 0

    offset = (page - 1) * page_size
    paged = base.order_by(AuthEvent.created_at.desc()).offset(offset).limit(page_size)
    result = await db.execute(paged)
    events = list(result.scalars().all())
    return events, total


async def detect_brute_force(
    db: AsyncSession,
    *,
    actor_id: str | None = None,
    ip_address: str | None = None,
    window_minutes: int = 5,
    threshold: int = 10,
) -> bool:
    """Check if there have been too many login failures in the recent window."""
    since = datetime.now(timezone.utc) - timedelta(minutes=window_minutes)
    base = select(func.count()).select_from(AuthEvent).where(
        AuthEvent.event_type == "login_failure",
        AuthEvent.created_at >= since,
    )
    if actor_id:
        base = base.where(AuthEvent.actor_id == actor_id)
    if ip_address:
        base = base.where(AuthEvent.ip_address == ip_address)

    result = await db.execute(base)
    count = result.scalar() or 0
    return count >= threshold


async def get_event_summary(
    db: AsyncSession,
    period_hours: int = 24,
) -> dict:
    """Get aggregated auth event summary for the given period."""
    since = datetime.now(timezone.utc) - timedelta(hours=period_hours)
    base = select(AuthEvent).where(AuthEvent.created_at >= since)

    result = await db.execute(base)
    events = list(result.scalars().all())

    type_counts: dict[str, int] = {}
    for event in events:
        type_counts[event.event_type] = type_counts.get(event.event_type, 0) + 1

    return {
        "total_events": len(events),
        "login_successes": type_counts.get("login_success", 0),
        "login_failures": type_counts.get("login_failure", 0),
        "token_refreshes": type_counts.get("token_refresh", 0),
        "token_revocations": type_counts.get("token_revoke", 0),
        "brute_force_detections": type_counts.get("brute_force_detected", 0),
        "period_hours": period_hours,
    }


async def cleanup_old_events(
    db: AsyncSession,
    retention_days: int = 30,
) -> int:
    """Purge auth events older than retention period."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=retention_days)
    result = await db.execute(
        delete(AuthEvent).where(AuthEvent.created_at < cutoff)
    )
    await db.commit()
    return result.rowcount or 0
