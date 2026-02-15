"""Developer profile endpoints for creator identities."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Header
from sqlalchemy.ext.asyncio import AsyncSession

from marketplace.core.creator_auth import get_current_creator_id
from marketplace.database import get_db
from marketplace.schemas.dual_layer import (
    DeveloperProfileResponse,
    DeveloperProfileUpdateRequest,
)
from marketplace.services import dual_layer_service

router = APIRouter(prefix="/creators", tags=["creators-v2"])


@router.get("/me/developer-profile", response_model=DeveloperProfileResponse)
async def get_my_developer_profile_v2(
    db: AsyncSession = Depends(get_db),
    authorization: str | None = Header(default=None),
):
    creator_id = get_current_creator_id(authorization)
    return await dual_layer_service.get_developer_profile_payload(
        db, creator_id=creator_id
    )


@router.put("/me/developer-profile", response_model=DeveloperProfileResponse)
async def update_my_developer_profile_v2(
    req: DeveloperProfileUpdateRequest,
    db: AsyncSession = Depends(get_db),
    authorization: str | None = Header(default=None),
):
    creator_id = get_current_creator_id(authorization)
    return await dual_layer_service.update_developer_profile(
        db,
        creator_id=creator_id,
        bio=req.bio,
        links=req.links,
        specialties=req.specialties,
        featured_flag=req.featured_flag,
    )
