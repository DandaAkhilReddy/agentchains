"""Admin endpoints for platform operations and analytics."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from marketplace.config import settings
from marketplace.core.auth import create_stream_token
from marketplace.core.creator_auth import get_current_creator_id
from marketplace.database import get_db
from marketplace.schemas.dashboard import (
    AdminAgentsResponse,
    AdminFinanceResponse,
    AdminOverviewResponse,
    AdminSecurityEventsResponse,
    AdminUsageResponse,
)
from marketplace.services import admin_dashboard_service, redemption_service

router = APIRouter(prefix="/admin", tags=["admin-v2"])


def _admin_ids() -> set[str]:
    return {value.strip() for value in settings.admin_creator_ids.split(",") if value.strip()}


def _require_admin_creator(authorization: str | None) -> str:
    creator_id = get_current_creator_id(authorization)
    admin_ids = _admin_ids()
    if admin_ids and creator_id not in admin_ids:
        raise HTTPException(status_code=403, detail="Admin access required")
    return creator_id


class AdminRejectRequest(BaseModel):
    reason: str = Field(..., min_length=1)


class AdminApproveRequest(BaseModel):
    admin_notes: str = ""


@router.get("/overview", response_model=AdminOverviewResponse)
async def admin_overview(
    db: AsyncSession = Depends(get_db),
    authorization: str | None = Header(default=None),
):
    _require_admin_creator(authorization)
    return await admin_dashboard_service.get_admin_overview(db)


@router.get("/finance", response_model=AdminFinanceResponse)
async def admin_finance(
    db: AsyncSession = Depends(get_db),
    authorization: str | None = Header(default=None),
):
    _require_admin_creator(authorization)
    return await admin_dashboard_service.get_admin_finance(db)


@router.get("/usage", response_model=AdminUsageResponse)
async def admin_usage(
    db: AsyncSession = Depends(get_db),
    authorization: str | None = Header(default=None),
):
    _require_admin_creator(authorization)
    return await admin_dashboard_service.get_admin_usage(db)


@router.get("/agents", response_model=AdminAgentsResponse)
async def admin_agents(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
    authorization: str | None = Header(default=None),
):
    _require_admin_creator(authorization)
    return await admin_dashboard_service.list_admin_agents(
        db,
        page=page,
        page_size=page_size,
        status=status,
    )


@router.get("/security/events", response_model=AdminSecurityEventsResponse)
async def admin_security_events(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    severity: str | None = Query(default=None),
    event_type: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
    authorization: str | None = Header(default=None),
):
    _require_admin_creator(authorization)
    return await admin_dashboard_service.list_security_events(
        db,
        page=page,
        page_size=page_size,
        severity=severity,
        event_type=event_type,
    )


@router.get("/payouts/pending")
async def admin_pending_payouts(
    limit: int = Query(100, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
    authorization: str | None = Header(default=None),
):
    _require_admin_creator(authorization)
    return await admin_dashboard_service.list_pending_payouts(db, limit=limit)


@router.post("/payouts/{request_id}/approve")
async def admin_approve_payout(
    request_id: str,
    req: AdminApproveRequest,
    db: AsyncSession = Depends(get_db),
    authorization: str | None = Header(default=None),
):
    _require_admin_creator(authorization)
    try:
        return await redemption_service.admin_approve_redemption(
            db,
            request_id,
            req.admin_notes,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/payouts/{request_id}/reject")
async def admin_reject_payout(
    request_id: str,
    req: AdminRejectRequest,
    db: AsyncSession = Depends(get_db),
    authorization: str | None = Header(default=None),
):
    _require_admin_creator(authorization)
    try:
        return await redemption_service.admin_reject_redemption(
            db,
            request_id,
            req.reason,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.get("/events/stream-token")
async def admin_stream_token(
    authorization: str | None = Header(default=None),
):
    creator_id = _require_admin_creator(authorization)
    token = create_stream_token(
        creator_id,
        token_type="stream_admin",
        allowed_topics=["public.market", "private.admin"],
    )
    return {
        "creator_id": creator_id,
        "stream_token": token,
        "ws_url": "/ws/v2/events",
        "allowed_topics": ["public.market", "private.admin"],
    }
