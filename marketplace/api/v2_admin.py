"""Admin endpoints for platform operations and analytics."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from marketplace.core.auth import create_stream_token
from marketplace.core.auth_context import AuthContext
from marketplace.core.auth_dependencies import require_role
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


class AdminRejectRequest(BaseModel):
    reason: str = Field(..., min_length=1)


class AdminApproveRequest(BaseModel):
    admin_notes: str = ""


@router.get("/overview", response_model=AdminOverviewResponse)
async def admin_overview(
    db: AsyncSession = Depends(get_db),
    ctx: AuthContext = Depends(require_role("admin")),
):
    return await admin_dashboard_service.get_admin_overview(db)


@router.get("/finance", response_model=AdminFinanceResponse)
async def admin_finance(
    db: AsyncSession = Depends(get_db),
    ctx: AuthContext = Depends(require_role("admin")),
):
    return await admin_dashboard_service.get_admin_finance(db)


@router.get("/usage", response_model=AdminUsageResponse)
async def admin_usage(
    db: AsyncSession = Depends(get_db),
    ctx: AuthContext = Depends(require_role("admin")),
):
    return await admin_dashboard_service.get_admin_usage(db)


@router.get("/agents", response_model=AdminAgentsResponse)
async def admin_agents(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
    ctx: AuthContext = Depends(require_role("admin")),
):
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
    ctx: AuthContext = Depends(require_role("admin")),
):
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
    ctx: AuthContext = Depends(require_role("admin")),
):
    return await admin_dashboard_service.list_pending_payouts(db, limit=limit)


@router.post("/payouts/{request_id}/approve")
async def admin_approve_payout(
    request_id: str,
    req: AdminApproveRequest,
    db: AsyncSession = Depends(get_db),
    ctx: AuthContext = Depends(require_role("admin")),
):
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
    ctx: AuthContext = Depends(require_role("admin")),
):
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
    ctx: AuthContext = Depends(require_role("admin")),
):
    token = create_stream_token(
        ctx.actor_id,
        token_type="stream_admin",
        allowed_topics=["public.market", "private.admin"],
    )
    return {
        "creator_id": ctx.actor_id,
        "stream_token": token,
        "ws_url": "/ws/v2/events",
        "allowed_topics": ["public.market", "private.admin"],
    }
