"""Creator account API endpoints."""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.requests import Request

from marketplace.core.creator_auth import get_current_creator_id
from marketplace.core.password_validation import validate_password_strength
from marketplace.database import get_db
from marketplace.services import auth_event_service, creator_service

router = APIRouter(prefix="/creators", tags=["creators"])


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class CreatorRegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)
    display_name: str = Field(..., min_length=1, max_length=100)
    phone: Optional[str] = Field(None, max_length=20, pattern=r"^\+?[0-9]{7,20}$")
    country: Optional[str] = Field(None, min_length=2, max_length=2)

class CreatorLoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=1, max_length=128)

class CreatorUpdateRequest(BaseModel):
    display_name: Optional[str] = Field(None, max_length=100)
    phone: Optional[str] = Field(None, max_length=20, pattern=r"^\+?[0-9]{7,20}$")
    country: Optional[str] = Field(None, min_length=2, max_length=2)
    payout_method: Optional[str] = Field(None, max_length=50)
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
    validate_password_strength(req.password)
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
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Login with email and password."""
    ip_address = request.client.host if request.client else None
    is_brute_force = await auth_event_service.detect_brute_force(
        db,
        ip_address=ip_address,
        window_minutes=5,
        threshold=10,
    )
    if is_brute_force:
        raise HTTPException(status_code=429, detail="Too many login attempts. Please try again later.")
    try:
        result = await creator_service.login_creator(db, req.email, req.password)
        await auth_event_service.log_auth_event(
            db,
            actor_id=result["creator"]["id"],
            actor_type="creator",
            event_type="login_success",
            ip_address=ip_address,
        )
        return result
    except Exception:
        await auth_event_service.log_auth_event(
            db,
            actor_type="creator",
            event_type="login_failure",
            ip_address=ip_address,
            details={"email": req.email},
        )
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
    """Get creator's USD balance."""
    creator_id = get_current_creator_id(authorization)
    return await creator_service.get_creator_wallet(db, creator_id)
