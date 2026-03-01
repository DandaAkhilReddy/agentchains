"""End-user account endpoints for no-code buyer flows."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.requests import Request

from marketplace.config import settings
from marketplace.core.auth import create_stream_token
from marketplace.core.password_validation import validate_password_strength
from marketplace.core.user_auth import get_current_user_id
from marketplace.database import get_db
from marketplace.schemas.dual_layer import (
    EndUserAuthResponse,
    EndUserLoginRequest,
    EndUserRegisterRequest,
    EndUserResponse,
    UserStreamTokenResponse,
)
from marketplace.services import auth_event_service, dual_layer_service

router = APIRouter(prefix="/users", tags=["users-v2"])


@router.post("/register", response_model=EndUserAuthResponse, status_code=201)
async def register_user_v2(
    req: EndUserRegisterRequest,
    db: AsyncSession = Depends(get_db),
):
    validate_password_strength(req.password)
    try:
        return await dual_layer_service.register_end_user(
            db,
            email=req.email,
            password=req.password,
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/login", response_model=EndUserAuthResponse)
async def login_user_v2(
    req: EndUserLoginRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
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
        return await dual_layer_service.login_end_user(
            db,
            email=req.email,
            password=req.password,
        )
    except ValueError as exc:
        await auth_event_service.log_auth_event(
            db,
            actor_type="user",
            event_type="login_failure",
            ip_address=ip_address,
            details={"email": req.email},
        )
        raise HTTPException(status_code=401, detail=str(exc)) from exc


@router.get("/me", response_model=EndUserResponse)
async def get_user_me_v2(
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    try:
        return await dual_layer_service.get_end_user_payload(db, user_id=user_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/events/stream-token", response_model=UserStreamTokenResponse)
async def get_user_stream_token_v2(
    user_id: str = Depends(get_current_user_id),
):
    expires_in_seconds = int(settings.stream_token_expire_minutes * 60)
    expires_at = datetime.now(timezone.utc) + timedelta(seconds=expires_in_seconds)
    allowed_topics = ["public.market", "public.market.orders", "private.user"]
    return {
        "user_id": user_id,
        "stream_token": create_stream_token(
            user_id,
            token_type="stream_user",
            allowed_topics=allowed_topics,
        ),
        "expires_in_seconds": expires_in_seconds,
        "expires_at": expires_at.isoformat(),
        "ws_url": "/ws/v2/events",
        "allowed_topics": allowed_topics,
    }
