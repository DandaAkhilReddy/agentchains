"""API key management endpoints."""

from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from marketplace.core.auth_context import AuthContext
from marketplace.core.auth_dependencies import require_auth
from marketplace.database import get_db
from marketplace.schemas.auth import ApiKeyCreateRequest, ApiKeyCreateResponse, ApiKeyResponse
from marketplace.services import api_key_service

router = APIRouter(prefix="/api-keys", tags=["api-keys"])


def _key_to_response(key) -> ApiKeyResponse:
    return ApiKeyResponse(
        id=key.id,
        name=key.name,
        key_prefix=key.key_prefix,
        scopes=json.loads(key.scopes_json or '["*"]'),
        last_used_at=key.last_used_at.isoformat() if key.last_used_at else None,
        expires_at=key.expires_at.isoformat() if key.expires_at else None,
        revoked=key.revoked,
        created_at=key.created_at.isoformat() if key.created_at else "",
    )


@router.post("", response_model=ApiKeyCreateResponse, status_code=201)
async def create_api_key(
    req: ApiKeyCreateRequest,
    db: AsyncSession = Depends(get_db),
    ctx: AuthContext = Depends(require_auth),
) -> ApiKeyCreateResponse:
    plaintext, key = await api_key_service.create_api_key(
        db,
        actor_id=ctx.actor_id,
        actor_type=ctx.actor_type,
        name=req.name,
        scopes=req.scopes,
        expires_in_days=req.expires_in_days,
    )
    return ApiKeyCreateResponse(
        id=key.id,
        key=plaintext,
        name=key.name,
        key_prefix=key.key_prefix,
        scopes=json.loads(key.scopes_json or '["*"]'),
        expires_at=key.expires_at.isoformat() if key.expires_at else None,
        created_at=key.created_at.isoformat() if key.created_at else "",
    )


@router.get("", response_model=list[ApiKeyResponse])
async def list_api_keys(
    db: AsyncSession = Depends(get_db),
    ctx: AuthContext = Depends(require_auth),
) -> list[ApiKeyResponse]:
    keys = await api_key_service.list_api_keys(db, ctx.actor_id)
    return [_key_to_response(k) for k in keys]


@router.delete("/{key_id}", status_code=204)
async def revoke_api_key(
    key_id: str,
    db: AsyncSession = Depends(get_db),
    ctx: AuthContext = Depends(require_auth),
) -> None:
    try:
        await api_key_service.revoke_api_key(db, key_id, ctx.actor_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.get("/{key_id}/usage")
async def get_api_key_usage(
    key_id: str,
    db: AsyncSession = Depends(get_db),
    ctx: AuthContext = Depends(require_auth),
):
    from marketplace.models.api_key import ApiKey
    key = await db.get(ApiKey, key_id)
    if not key or key.actor_id != ctx.actor_id:
        raise HTTPException(status_code=404, detail="API key not found")
    return {
        "key_id": key.id,
        "last_used_at": key.last_used_at.isoformat() if key.last_used_at else None,
    }
