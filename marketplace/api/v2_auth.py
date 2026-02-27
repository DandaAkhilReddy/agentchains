"""Auth API — refresh, revoke, change-password, me endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from marketplace.core.auth_context import AuthContext
from marketplace.core.auth_dependencies import require_auth
from marketplace.core.password_validation import validate_password_strength
from marketplace.core.refresh_tokens import refresh_access_token, revoke_refresh_tokens_for_actor
from marketplace.core.token_revocation import revoke_all_for_actor, revoke_token
from marketplace.database import get_db
from marketplace.services import auth_event_service
from marketplace.schemas.auth import (
    AuthMeResponse,
    ChangePasswordRequest,
    RefreshTokenRequest,
    TokenPairResponse,
)

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/refresh", response_model=TokenPairResponse)
async def refresh_token(
    req: RefreshTokenRequest,
    db: AsyncSession = Depends(get_db),
):
    """Exchange a refresh token for a new access + refresh token pair."""
    pair = await refresh_access_token(db, req.refresh_token)
    await auth_event_service.log_auth_event(
        db,
        event_type="token_refresh",
    )
    return TokenPairResponse(
        access_token=pair.access_token,
        refresh_token=pair.refresh_token,
        expires_in=pair.expires_in,
    )


@router.post("/revoke", status_code=204)
async def revoke_current_token(
    db: AsyncSession = Depends(get_db),
    ctx: AuthContext = Depends(require_auth),
):
    """Revoke the current access token."""
    if ctx.token_jti:
        from datetime import datetime, timedelta, timezone
        expires_at = datetime.now(timezone.utc) + timedelta(hours=1)
        await revoke_token(db, ctx.token_jti, ctx.actor_id, expires_at)
    await auth_event_service.log_auth_event(
        db,
        actor_id=ctx.actor_id,
        actor_type=ctx.actor_type,
        event_type="token_revoke",
    )


@router.post("/revoke-all", status_code=204)
async def revoke_all_tokens(
    db: AsyncSession = Depends(get_db),
    ctx: AuthContext = Depends(require_auth),
):
    """Revoke all tokens (access + refresh) for the current actor."""
    await revoke_all_for_actor(db, ctx.actor_id)
    await revoke_refresh_tokens_for_actor(db, ctx.actor_id)
    await auth_event_service.log_auth_event(
        db,
        actor_id=ctx.actor_id,
        actor_type=ctx.actor_type,
        event_type="token_revoke",
        details={"scope": "all tokens"},
    )


@router.post("/change-password", status_code=204)
async def change_password(
    req: ChangePasswordRequest,
    db: AsyncSession = Depends(get_db),
    ctx: AuthContext = Depends(require_auth),
):
    """Change password and revoke all existing tokens."""
    validate_password_strength(req.new_password)
    from marketplace.core.creator_auth import hash_password, verify_password

    if ctx.is_creator:
        from marketplace.models.creator import Creator
        creator = await db.get(Creator, ctx.actor_id)
        if not creator:
            raise HTTPException(status_code=404, detail="Creator not found")
        if not verify_password(req.current_password, creator.password_hash):
            raise HTTPException(status_code=401, detail="Current password is incorrect")
        creator.password_hash = hash_password(req.new_password)
    elif ctx.is_user:
        from marketplace.models.dual_layer import EndUser
        user = await db.get(EndUser, ctx.actor_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        if not verify_password(req.current_password, user.password_hash):
            raise HTTPException(status_code=401, detail="Current password is incorrect")
        user.password_hash = hash_password(req.new_password)
    else:
        raise HTTPException(status_code=400, detail="Password change not supported for this actor type")

    await db.commit()

    # Revoke all tokens
    await revoke_all_for_actor(db, ctx.actor_id)
    await revoke_refresh_tokens_for_actor(db, ctx.actor_id)

    await auth_event_service.log_auth_event(
        db,
        actor_id=ctx.actor_id,
        actor_type=ctx.actor_type,
        event_type="password_change",
    )


@router.get("/me", response_model=AuthMeResponse)
async def auth_me(
    ctx: AuthContext = Depends(require_auth),
) -> AuthMeResponse:
    """Return the current authenticated actor's identity and roles."""
    return AuthMeResponse(
        actor_id=ctx.actor_id,
        actor_type=ctx.actor_type,
        roles=sorted(ctx.roles),
        trust_tier=ctx.trust_tier,
        scopes=sorted(ctx.scopes),
    )
