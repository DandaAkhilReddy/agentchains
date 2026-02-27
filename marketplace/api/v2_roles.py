"""Role management API endpoints — admin-only RBAC CRUD."""

from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from marketplace.core.auth_context import AuthContext
from marketplace.core.auth_dependencies import require_role
from marketplace.database import get_db
from marketplace.schemas.auth import (
    ActorRoleResponse,
    AssignRoleRequest,
    RoleCreateRequest,
    RoleResponse,
    RoleUpdateRequest,
)
from marketplace.services import role_service

router = APIRouter(prefix="/roles", tags=["roles"])


def _role_to_response(role) -> RoleResponse:
    return RoleResponse(
        id=role.id,
        name=role.name,
        description=role.description or "",
        permissions=json.loads(role.permissions_json or "[]"),
        is_system=role.is_system,
        created_at=role.created_at.isoformat() if role.created_at else "",
    )


@router.get("", response_model=list[RoleResponse])
async def list_roles(
    db: AsyncSession = Depends(get_db),
    ctx: AuthContext = Depends(require_role("admin")),
) -> list[RoleResponse]:
    roles = await role_service.list_roles(db)
    return [_role_to_response(r) for r in roles]


@router.post("", response_model=RoleResponse, status_code=201)
async def create_role(
    req: RoleCreateRequest,
    db: AsyncSession = Depends(get_db),
    ctx: AuthContext = Depends(require_role("admin")),
) -> RoleResponse:
    try:
        role = await role_service.create_role(
            db, name=req.name, description=req.description, permissions=req.permissions,
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    return _role_to_response(role)


@router.get("/{role_id}", response_model=RoleResponse)
async def get_role(
    role_id: str,
    db: AsyncSession = Depends(get_db),
    ctx: AuthContext = Depends(require_role("admin")),
) -> RoleResponse:
    role = await role_service.get_role(db, role_id)
    if not role:
        raise HTTPException(status_code=404, detail="Role not found")
    return _role_to_response(role)


@router.put("/{role_id}", response_model=RoleResponse)
async def update_role(
    role_id: str,
    req: RoleUpdateRequest,
    db: AsyncSession = Depends(get_db),
    ctx: AuthContext = Depends(require_role("admin")),
) -> RoleResponse:
    try:
        role = await role_service.update_role(
            db, role_id, description=req.description, permissions=req.permissions,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    return _role_to_response(role)


@router.delete("/{role_id}", status_code=204)
async def delete_role(
    role_id: str,
    db: AsyncSession = Depends(get_db),
    ctx: AuthContext = Depends(require_role("admin")),
) -> None:
    try:
        await role_service.delete_role(db, role_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/actors/{actor_id}/roles", status_code=201)
async def assign_role_to_actor(
    actor_id: str,
    req: AssignRoleRequest,
    db: AsyncSession = Depends(get_db),
    ctx: AuthContext = Depends(require_role("admin")),
):
    try:
        assignment = await role_service.assign_role(
            db, actor_id=actor_id, actor_type="unknown",
            role_name=req.role_name, granted_by=ctx.actor_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {"actor_id": actor_id, "role": req.role_name, "status": "assigned"}


@router.delete("/actors/{actor_id}/roles/{role_name}", status_code=204)
async def revoke_role_from_actor(
    actor_id: str,
    role_name: str,
    db: AsyncSession = Depends(get_db),
    ctx: AuthContext = Depends(require_role("admin")),
) -> None:
    try:
        await role_service.revoke_role(db, actor_id=actor_id, role_name=role_name)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.get("/actors/{actor_id}/roles")
async def get_actor_roles(
    actor_id: str,
    db: AsyncSession = Depends(get_db),
    ctx: AuthContext = Depends(require_role("admin")),
):
    roles = await role_service.get_roles_for_actor(db, actor_id)
    return {"actor_id": actor_id, "roles": [_role_to_response(r) for r in roles]}
