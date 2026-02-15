"""Role-specific dashboard endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from marketplace.config import settings
from marketplace.core.auth import get_current_agent_id
from marketplace.core.creator_auth import get_current_creator_id
from marketplace.database import get_db
from marketplace.models.agent import RegisteredAgent
from marketplace.schemas.dashboard import (
    AgentDashboardResponse,
    AgentPublicDashboardResponse,
    CreatorDashboardV2Response,
)
from marketplace.services import dashboard_service

router = APIRouter(prefix="/dashboards", tags=["dashboards-v2"])


def _admin_creator_ids() -> set[str]:
    return {value.strip() for value in settings.admin_creator_ids.split(",") if value.strip()}


@router.get("/agent/me", response_model=AgentDashboardResponse)
async def dashboard_agent_me(
    db: AsyncSession = Depends(get_db),
    agent_id: str = Depends(get_current_agent_id),
):
    return await dashboard_service.get_agent_dashboard(db, agent_id)


@router.get("/creator/me", response_model=CreatorDashboardV2Response)
async def dashboard_creator_me(
    db: AsyncSession = Depends(get_db),
    authorization: str | None = Header(default=None),
):
    creator_id = get_current_creator_id(authorization)
    return await dashboard_service.get_creator_dashboard_v2(db, creator_id)


@router.get("/agent/{agent_id}/public", response_model=AgentPublicDashboardResponse)
async def dashboard_agent_public(
    agent_id: str,
    db: AsyncSession = Depends(get_db),
):
    try:
        return await dashboard_service.get_agent_public_dashboard(db, agent_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.get("/agent/{agent_id}", response_model=AgentDashboardResponse)
async def dashboard_agent_private(
    agent_id: str,
    db: AsyncSession = Depends(get_db),
    authorization: str | None = Header(default=None),
):
    current_creator_id = None
    current_agent_id = None
    agent_auth_ok = False
    creator_auth_ok = False

    try:
        current_agent_id = get_current_agent_id(authorization)  # type: ignore[arg-type]
        agent_auth_ok = True
    except Exception:
        agent_auth_ok = False

    if agent_auth_ok and current_agent_id == agent_id:
        return await dashboard_service.get_agent_dashboard(db, agent_id)

    try:
        current_creator_id = get_current_creator_id(authorization)
        creator_auth_ok = True
    except Exception:
        creator_auth_ok = False

    if not creator_auth_ok:
        raise HTTPException(status_code=401, detail="Unauthorized")

    agent_row = await db.execute(
        select(RegisteredAgent).where(RegisteredAgent.id == agent_id)
    )
    agent = agent_row.scalar_one_or_none()
    if agent is None:
        raise HTTPException(status_code=404, detail=f"Agent {agent_id} not found")

    if current_creator_id != agent.creator_id and current_creator_id not in _admin_creator_ids():
        raise HTTPException(status_code=403, detail="Not authorized to view this dashboard")

    return await dashboard_service.get_agent_dashboard(db, agent_id)
