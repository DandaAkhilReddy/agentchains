import json
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from marketplace.core.auth import create_access_token
from marketplace.core.exceptions import AgentAlreadyExistsError, AgentNotFoundError
from marketplace.models.agent import RegisteredAgent
from marketplace.models.reputation import ReputationScore
from marketplace.schemas.agent import AgentRegisterRequest, AgentRegisterResponse, AgentUpdateRequest


async def register_agent(db: AsyncSession, req: AgentRegisterRequest) -> AgentRegisterResponse:
    """Register a new agent and return its ID + JWT token."""
    # Check uniqueness
    existing = await db.execute(
        select(RegisteredAgent).where(RegisteredAgent.name == req.name)
    )
    if existing.scalar_one_or_none():
        raise AgentAlreadyExistsError(req.name)

    agent = RegisteredAgent(
        name=req.name,
        description=req.description,
        agent_type=req.agent_type,
        public_key=req.public_key,
        wallet_address=req.wallet_address,
        capabilities=json.dumps(req.capabilities),
        a2a_endpoint=req.a2a_endpoint,
        agent_card_json=json.dumps({
            "name": req.name,
            "description": req.description,
            "url": req.a2a_endpoint,
            "capabilities": req.capabilities,
        }),
    )
    db.add(agent)
    await db.flush()  # Ensure agent.id is populated

    # Initialize reputation score
    reputation = ReputationScore(agent_id=agent.id)
    db.add(reputation)

    await db.commit()
    await db.refresh(agent)

    token = create_access_token(agent.id, agent.name)
    a2a_url = f"{req.a2a_endpoint}/.well-known/agent.json" if req.a2a_endpoint else ""

    return AgentRegisterResponse(
        id=agent.id,
        name=agent.name,
        jwt_token=token,
        agent_card_url=a2a_url,
        created_at=agent.created_at,
    )


async def get_agent(db: AsyncSession, agent_id: str) -> RegisteredAgent:
    """Get an agent by ID or raise 404."""
    result = await db.execute(
        select(RegisteredAgent).where(RegisteredAgent.id == agent_id)
    )
    agent = result.scalar_one_or_none()
    if not agent:
        raise AgentNotFoundError(agent_id)
    return agent


async def list_agents(
    db: AsyncSession,
    agent_type: str | None = None,
    status: str | None = None,
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[RegisteredAgent], int]:
    """List agents with optional filters. Returns (agents, total_count)."""
    query = select(RegisteredAgent)
    count_query = select(func.count(RegisteredAgent.id))

    if agent_type:
        query = query.where(RegisteredAgent.agent_type == agent_type)
        count_query = count_query.where(RegisteredAgent.agent_type == agent_type)
    if status:
        query = query.where(RegisteredAgent.status == status)
        count_query = count_query.where(RegisteredAgent.status == status)

    total = (await db.execute(count_query)).scalar() or 0

    query = query.offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(query)
    agents = list(result.scalars().all())

    return agents, total


async def update_agent(
    db: AsyncSession, agent_id: str, req: AgentUpdateRequest
) -> RegisteredAgent:
    """Update agent fields."""
    agent = await get_agent(db, agent_id)
    update_data = req.model_dump(exclude_unset=True)

    if "capabilities" in update_data and update_data["capabilities"] is not None:
        update_data["capabilities"] = json.dumps(update_data["capabilities"])

    for field, value in update_data.items():
        setattr(agent, field, value)

    agent.updated_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(agent)
    return agent


async def heartbeat(db: AsyncSession, agent_id: str) -> RegisteredAgent:
    """Update the agent's last_seen_at timestamp."""
    agent = await get_agent(db, agent_id)
    agent.last_seen_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(agent)
    return agent


async def deactivate_agent(db: AsyncSession, agent_id: str) -> RegisteredAgent:
    """Soft-delete an agent by setting status to 'deactivated'."""
    agent = await get_agent(db, agent_id)
    agent.status = "deactivated"
    agent.updated_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(agent)
    return agent
