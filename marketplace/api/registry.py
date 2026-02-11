import json

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from marketplace.core.auth import get_current_agent_id
from marketplace.database import get_db
from marketplace.schemas.agent import (
    AgentListResponse,
    AgentRegisterRequest,
    AgentRegisterResponse,
    AgentResponse,
    AgentUpdateRequest,
)
from marketplace.services import registry_service
from marketplace.services.token_service import create_account, ensure_platform_account
from marketplace.services.deposit_service import credit_signup_bonus

router = APIRouter(prefix="/agents", tags=["agents"])


@router.post("/register", response_model=AgentRegisterResponse, status_code=201)
async def register_agent(
    req: AgentRegisterRequest,
    db: AsyncSession = Depends(get_db),
):
    result = await registry_service.register_agent(db, req)

    # Create ARD token account + signup bonus
    try:
        await ensure_platform_account(db)
        await create_account(db, result.id)
        await credit_signup_bonus(db, result.id)
    except Exception:
        pass  # Don't fail registration if token setup fails

    return result


@router.get("", response_model=AgentListResponse)
async def list_agents(
    agent_type: str | None = Query(None, pattern="^(seller|buyer|both)$"),
    status: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    agents, total = await registry_service.list_agents(db, agent_type, status, page, page_size)
    return AgentListResponse(
        total=total,
        page=page,
        page_size=page_size,
        agents=[_agent_to_response(a) for a in agents],
    )


@router.get("/{agent_id}", response_model=AgentResponse)
async def get_agent(
    agent_id: str,
    db: AsyncSession = Depends(get_db),
):
    agent = await registry_service.get_agent(db, agent_id)
    return _agent_to_response(agent)


@router.put("/{agent_id}", response_model=AgentResponse)
async def update_agent(
    agent_id: str,
    req: AgentUpdateRequest,
    db: AsyncSession = Depends(get_db),
    current_agent: str = Depends(get_current_agent_id),
):
    if current_agent != agent_id:
        from fastapi import HTTPException
        raise HTTPException(status_code=403, detail="Can only update your own agent")
    agent = await registry_service.update_agent(db, agent_id, req)
    return _agent_to_response(agent)


@router.post("/{agent_id}/heartbeat")
async def heartbeat(
    agent_id: str,
    db: AsyncSession = Depends(get_db),
    current_agent: str = Depends(get_current_agent_id),
):
    if current_agent != agent_id:
        from fastapi import HTTPException
        raise HTTPException(status_code=403, detail="Can only heartbeat your own agent")
    agent = await registry_service.heartbeat(db, agent_id)
    return {"status": "ok", "last_seen_at": agent.last_seen_at}


@router.delete("/{agent_id}")
async def deactivate_agent(
    agent_id: str,
    db: AsyncSession = Depends(get_db),
    current_agent: str = Depends(get_current_agent_id),
):
    if current_agent != agent_id:
        from fastapi import HTTPException
        raise HTTPException(status_code=403, detail="Can only deactivate your own agent")
    await registry_service.deactivate_agent(db, agent_id)
    return {"status": "deactivated"}


def _agent_to_response(agent) -> AgentResponse:
    caps = agent.capabilities
    if isinstance(caps, str):
        caps = json.loads(caps)
    return AgentResponse(
        id=agent.id,
        name=agent.name,
        description=agent.description,
        agent_type=agent.agent_type,
        wallet_address=agent.wallet_address,
        capabilities=caps,
        a2a_endpoint=agent.a2a_endpoint,
        status=agent.status,
        created_at=agent.created_at,
        updated_at=agent.updated_at,
        last_seen_at=agent.last_seen_at,
    )
