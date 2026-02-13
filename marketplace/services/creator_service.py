"""Creator account management — registration, login, dashboard, agent linking."""
import json
import logging
import uuid
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from marketplace.config import settings
from marketplace.core.creator_auth import create_creator_token, hash_password, verify_password
from marketplace.core.exceptions import UnauthorizedError
from marketplace.models.creator import Creator
from marketplace.models.token_account import TokenAccount, TokenLedger

logger = logging.getLogger(__name__)


async def register_creator(
    db: AsyncSession,
    email: str,
    password: str,
    display_name: str,
    phone: str | None = None,
    country: str | None = None,
) -> dict:
    """Register a new creator account with email/password."""
    # Check for duplicate email
    existing = await db.execute(select(Creator).where(Creator.email == email))
    if existing.scalar_one_or_none():
        raise ValueError("Email already registered")

    creator = Creator(
        id=str(uuid.uuid4()),
        email=email.lower().strip(),
        password_hash=hash_password(password),
        display_name=display_name.strip(),
        phone=phone,
        country=country.upper() if country else None,
    )
    db.add(creator)

    # Create token account for creator
    account = TokenAccount(
        id=str(uuid.uuid4()),
        agent_id=None,
        creator_id=creator.id,
        balance=Decimal(str(settings.signup_bonus_usd)),
        total_deposited=Decimal(str(settings.signup_bonus_usd)),
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    db.add(account)

    await db.commit()
    await db.refresh(creator)

    token = create_creator_token(creator.id, creator.email)
    logger.info("Creator registered: %s (%s)", creator.display_name, creator.email)

    return {
        "creator": _creator_to_dict(creator),
        "token": token,
    }


async def login_creator(db: AsyncSession, email: str, password: str) -> dict:
    """Authenticate a creator by email/password. Returns JWT."""
    result = await db.execute(select(Creator).where(Creator.email == email.lower().strip()))
    creator = result.scalar_one_or_none()
    if not creator:
        raise UnauthorizedError("Invalid email or password")
    if not verify_password(password, creator.password_hash):
        raise UnauthorizedError("Invalid email or password")
    if creator.status != "active":
        raise UnauthorizedError("Account is suspended")

    token = create_creator_token(creator.id, creator.email)
    return {
        "creator": _creator_to_dict(creator),
        "token": token,
    }


async def get_creator(db: AsyncSession, creator_id: str) -> dict | None:
    """Fetch a creator by ID."""
    result = await db.execute(select(Creator).where(Creator.id == creator_id))
    creator = result.scalar_one_or_none()
    if not creator:
        return None
    return _creator_to_dict(creator)


async def update_creator(db: AsyncSession, creator_id: str, updates: dict) -> dict:
    """Update creator profile fields."""
    result = await db.execute(select(Creator).where(Creator.id == creator_id))
    creator = result.scalar_one_or_none()
    if not creator:
        raise ValueError("Creator not found")

    allowed_fields = {"display_name", "phone", "country", "payout_method", "payout_details"}
    for key, value in updates.items():
        if key in allowed_fields:
            if key == "payout_details" and isinstance(value, dict):
                value = json.dumps(value)
            if key == "country" and value:
                value = value.upper()
            setattr(creator, key, value)

    creator.updated_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(creator)
    return _creator_to_dict(creator)


async def link_agent_to_creator(db: AsyncSession, creator_id: str, agent_id: str) -> dict:
    """Claim ownership of an agent (set creator_id on RegisteredAgent)."""
    from marketplace.models.agent import RegisteredAgent

    result = await db.execute(select(RegisteredAgent).where(RegisteredAgent.id == agent_id))
    agent = result.scalar_one_or_none()
    if not agent:
        raise ValueError("Agent not found")
    if agent.creator_id and agent.creator_id != creator_id:
        raise ValueError("Agent already claimed by another creator")

    agent.creator_id = creator_id
    await db.commit()
    await db.refresh(agent)
    return {"agent_id": agent.id, "agent_name": agent.name, "creator_id": creator_id}


async def get_creator_agents(db: AsyncSession, creator_id: str) -> list[dict]:
    """List all agents owned by a creator with their earnings."""
    from marketplace.models.agent import RegisteredAgent

    result = await db.execute(
        select(RegisteredAgent).where(RegisteredAgent.creator_id == creator_id)
    )
    agents = result.scalars().all()

    agent_list = []
    for agent in agents:
        # Get agent's token account for earnings
        acct_result = await db.execute(
            select(TokenAccount).where(TokenAccount.agent_id == agent.id)
        )
        acct = acct_result.scalar_one_or_none()
        agent_list.append({
            "agent_id": agent.id,
            "agent_name": agent.name,
            "agent_type": agent.agent_type,
            "status": agent.status,
            "total_earned": float(acct.total_earned) if acct else 0,
            "total_spent": float(acct.total_spent) if acct else 0,
            "balance": float(acct.balance) if acct else 0,
        })
    return agent_list


async def get_creator_dashboard(db: AsyncSession, creator_id: str) -> dict:
    """Get aggregated dashboard data for a creator."""
    # Creator's own account
    acct_result = await db.execute(
        select(TokenAccount).where(TokenAccount.creator_id == creator_id)
    )
    creator_acct = acct_result.scalar_one_or_none()

    # Agents
    agents = await get_creator_agents(db, creator_id)

    total_agent_earnings = sum(a["total_earned"] for a in agents)
    total_agent_spent = sum(a["total_spent"] for a in agents)

    return {
        "creator_balance": float(creator_acct.balance) if creator_acct else 0,
        "creator_total_earned": float(creator_acct.total_earned) if creator_acct else 0,
        "agents_count": len(agents),
        "agents": agents,
        "total_agent_earnings": total_agent_earnings,
        "total_agent_spent": total_agent_spent,
    }


async def get_creator_wallet(db: AsyncSession, creator_id: str) -> dict:
    """Get creator's token account balance and history."""
    acct_result = await db.execute(
        select(TokenAccount).where(TokenAccount.creator_id == creator_id)
    )
    acct = acct_result.scalar_one_or_none()
    if not acct:
        return {"balance": 0, "total_earned": 0, "total_spent": 0}

    return {
        "balance": float(acct.balance),
        "total_earned": float(acct.total_earned),
        "total_spent": float(acct.total_spent),
        "total_deposited": float(acct.total_deposited),
        "total_fees_paid": float(acct.total_fees_paid),
    }


def _creator_to_dict(creator: Creator) -> dict:
    return {
        "id": creator.id,
        "email": creator.email,
        "display_name": creator.display_name,
        "phone": creator.phone,
        "country": creator.country,
        "payout_method": creator.payout_method,
        "status": creator.status,
        "created_at": str(creator.created_at),
        "updated_at": str(creator.updated_at),
    }
