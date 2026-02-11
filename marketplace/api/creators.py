"""Creator account API endpoints."""
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.ext.asyncio import AsyncSession

from marketplace.core.creator_auth import get_current_creator_id
from marketplace.database import get_db
from marketplace.services import creator_service

router = APIRouter(prefix="/creators", tags=["creators"])


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class CreatorRegisterRequest(BaseModel):
    email: str = Field(..., min_length=5, max_length=255)
    password: str = Field(..., min_length=8, max_length=128)
    display_name: str = Field(..., min_length=1, max_length=100)
    phone: Optional[str] = None
    country: Optional[str] = Field(None, min_length=2, max_length=2)

class CreatorLoginRequest(BaseModel):
    email: str
    password: str

class CreatorUpdateRequest(BaseModel):
    display_name: Optional[str] = None
    phone: Optional[str] = None
    country: Optional[str] = None
    payout_method: Optional[str] = None
    payout_details: Optional[dict] = None


# ---------------------------------------------------------------------------
# Public endpoints
# ---------------------------------------------------------------------------

@router.post("/register", status_code=201)
async def register_creator(
    req: CreatorRegisterRequest,
    db: AsyncSession = Depends(get_db),
):
    """Register a new creator account."""
    try:
        result = await creator_service.register_creator(
            db, req.email, req.password, req.display_name,
            phone=req.phone, country=req.country,
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))

@router.post("/login")
async def login_creator(
    req: CreatorLoginRequest,
    db: AsyncSession = Depends(get_db),
):
    """Login with email and password."""
    try:
        return await creator_service.login_creator(db, req.email, req.password)
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid email or password")


# ---------------------------------------------------------------------------
# Authenticated endpoints
# ---------------------------------------------------------------------------

@router.get("/me")
async def get_my_profile(
    db: AsyncSession = Depends(get_db),
    authorization: str = Header(None),
):
    """Get current creator's profile."""
    creator_id = get_current_creator_id(authorization)
    creator = await creator_service.get_creator(db, creator_id)
    if not creator:
        raise HTTPException(status_code=404, detail="Creator not found")
    return creator

@router.put("/me")
async def update_my_profile(
    req: CreatorUpdateRequest,
    db: AsyncSession = Depends(get_db),
    authorization: str = Header(None),
):
    """Update creator profile and payout details."""
    creator_id = get_current_creator_id(authorization)
    updates = {k: v for k, v in req.model_dump().items() if v is not None}
    try:
        return await creator_service.update_creator(db, creator_id, updates)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

@router.get("/me/agents")
async def get_my_agents(
    db: AsyncSession = Depends(get_db),
    authorization: str = Header(None),
):
    """List all agents owned by this creator."""
    creator_id = get_current_creator_id(authorization)
    agents = await creator_service.get_creator_agents(db, creator_id)
    return {"agents": agents, "count": len(agents)}

@router.post("/me/agents/{agent_id}/claim")
async def claim_agent(
    agent_id: str,
    db: AsyncSession = Depends(get_db),
    authorization: str = Header(None),
):
    """Claim ownership of an agent."""
    creator_id = get_current_creator_id(authorization)
    try:
        return await creator_service.link_agent_to_creator(db, creator_id, agent_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/me/dashboard")
async def get_my_dashboard(
    db: AsyncSession = Depends(get_db),
    authorization: str = Header(None),
):
    """Get aggregated creator dashboard with earnings across all agents."""
    creator_id = get_current_creator_id(authorization)
    return await creator_service.get_creator_dashboard(db, creator_id)

@router.get("/me/wallet")
async def get_my_wallet(
    db: AsyncSession = Depends(get_db),
    authorization: str = Header(None),
):
    """Get creator's ARD token balance."""
    creator_id = get_current_creator_id(authorization)
    return await creator_service.get_creator_wallet(db, creator_id)
