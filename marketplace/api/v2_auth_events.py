"""Auth event audit trail API — admin-only endpoints."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from marketplace.core.auth_context import AuthContext
from marketplace.core.auth_dependencies import require_role
from marketplace.database import get_db
from marketplace.schemas.auth import AuthEventResponse, AuthEventSummaryResponse
from marketplace.services import auth_event_service

router = APIRouter(prefix="/auth", tags=["auth-events"])


@router.get("/events", response_model=dict)
async def list_auth_events(
    actor_id: str | None = None,
    event_type: str | None = None,
    hours: int = Query(default=24, ge=1, le=720),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    ctx: AuthContext = Depends(require_role("admin")),
):
    since = datetime.now(timezone.utc) - timedelta(hours=hours)
    events, total = await auth_event_service.get_events(
        db,
        actor_id=actor_id,
        event_type=event_type,
        since=since,
        page=page,
        page_size=page_size,
    )
    return {
        "items": [
            AuthEventResponse(
                id=e.id,
                actor_id=e.actor_id,
                actor_type=e.actor_type,
                event_type=e.event_type,
                ip_address=e.ip_address,
                details=json.loads(e.details_json or "{}"),
                created_at=e.created_at.isoformat() if e.created_at else "",
            )
            for e in events
        ],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.get("/events/summary", response_model=AuthEventSummaryResponse)
async def auth_event_summary(
    hours: int = Query(default=24, ge=1, le=720),
    db: AsyncSession = Depends(get_db),
    ctx: AuthContext = Depends(require_role("admin")),
) -> AuthEventSummaryResponse:
    summary = await auth_event_service.get_event_summary(db, period_hours=hours)
    return AuthEventSummaryResponse(**summary)
