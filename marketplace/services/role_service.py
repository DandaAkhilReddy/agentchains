"""RBAC role service — CRUD for roles and actor-role assignments."""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from marketplace.models.role import ActorRole, Role

logger = logging.getLogger(__name__)

# Default system roles seeded on first startup
SYSTEM_ROLES: list[dict] = [
    {
        "name": "admin",
        "description": "Full platform administrator",
        "permissions": ["*"],
        "is_system": True,
    },
    {
        "name": "moderator",
        "description": "Content moderation and user management",
        "permissions": [
            "agents:read", "agents:suspend", "listings:read", "listings:moderate",
            "users:read", "auth_events:read",
        ],
        "is_system": True,
    },
    {
        "name": "finance",
        "description": "Financial operations — payouts, billing, transactions",
        "permissions": [
            "payouts:read", "payouts:approve", "payouts:reject",
            "transactions:read", "billing:read", "finance:read",
        ],
        "is_system": True,
    },
    {
        "name": "support",
        "description": "Customer support — read access to users and agents",
        "permissions": [
            "agents:read", "users:read", "creators:read",
            "transactions:read", "auth_events:read",
        ],
        "is_system": True,
    },
    {
        "name": "creator",
        "description": "Default role for creator accounts",
        "permissions": [
            "agents:create", "agents:read", "listings:create",
            "listings:read", "creators:profile",
        ],
        "is_system": True,
    },
    {
        "name": "user",
        "description": "Default role for end-user accounts",
        "permissions": [
            "listings:read", "transactions:create", "users:profile",
        ],
        "is_system": True,
    },
]


async def seed_system_roles(db: AsyncSession) -> list[Role]:
    """Create default system roles if they don't already exist."""
    created: list[Role] = []
    for role_def in SYSTEM_ROLES:
        result = await db.execute(
            select(Role).where(Role.name == role_def["name"])
        )
        existing = result.scalar_one_or_none()
        if existing:
            continue
        role = Role(
            id=str(uuid.uuid4()),
            name=role_def["name"],
            description=role_def["description"],
            permissions_json=json.dumps(role_def["permissions"]),
            is_system=role_def["is_system"],
        )
        db.add(role)
        created.append(role)
    if created:
        await db.commit()
        logger.info("Seeded %d system roles", len(created))
    return created


async def create_role(
    db: AsyncSession,
    name: str,
    description: str = "",
    permissions: list[str] | None = None,
) -> Role:
    """Create a custom (non-system) role."""
    # Check uniqueness
    result = await db.execute(select(Role).where(Role.name == name))
    if result.scalar_one_or_none():
        raise ValueError(f"Role '{name}' already exists")

    role = Role(
        id=str(uuid.uuid4()),
        name=name,
        description=description,
        permissions_json=json.dumps(permissions or []),
        is_system=False,
    )
    db.add(role)
    await db.commit()
    await db.refresh(role)
    return role


async def get_role(db: AsyncSession, role_id: str) -> Role | None:
    return await db.get(Role, role_id)


async def get_role_by_name(db: AsyncSession, name: str) -> Role | None:
    result = await db.execute(select(Role).where(Role.name == name))
    return result.scalar_one_or_none()


async def list_roles(db: AsyncSession) -> list[Role]:
    result = await db.execute(select(Role).order_by(Role.name))
    return list(result.scalars().all())


async def update_role(
    db: AsyncSession,
    role_id: str,
    description: str | None = None,
    permissions: list[str] | None = None,
) -> Role:
    role = await db.get(Role, role_id)
    if not role:
        raise ValueError("Role not found")
    if description is not None:
        role.description = description
    if permissions is not None:
        role.permissions_json = json.dumps(permissions)
    await db.commit()
    await db.refresh(role)
    return role


async def delete_role(db: AsyncSession, role_id: str) -> None:
    role = await db.get(Role, role_id)
    if not role:
        raise ValueError("Role not found")
    if role.is_system:
        raise ValueError("Cannot delete system role")
    # Remove all actor-role assignments for this role
    await db.execute(delete(ActorRole).where(ActorRole.role_id == role_id))
    await db.delete(role)
    await db.commit()


async def assign_role(
    db: AsyncSession,
    actor_id: str,
    actor_type: str,
    role_name: str,
    granted_by: str,
) -> ActorRole:
    """Assign a role to an actor. No-op if already assigned."""
    role = await get_role_by_name(db, role_name)
    if not role:
        raise ValueError(f"Role '{role_name}' not found")

    # Check if already assigned
    result = await db.execute(
        select(ActorRole).where(
            ActorRole.actor_id == actor_id,
            ActorRole.role_id == role.id,
        )
    )
    existing = result.scalar_one_or_none()
    if existing:
        return existing

    assignment = ActorRole(
        id=str(uuid.uuid4()),
        actor_id=actor_id,
        actor_type=actor_type,
        role_id=role.id,
        granted_by=granted_by,
    )
    db.add(assignment)
    await db.commit()
    await db.refresh(assignment)
    return assignment


async def revoke_role(
    db: AsyncSession,
    actor_id: str,
    role_name: str,
) -> None:
    """Remove a role assignment from an actor."""
    role = await get_role_by_name(db, role_name)
    if not role:
        raise ValueError(f"Role '{role_name}' not found")
    result = await db.execute(
        delete(ActorRole).where(
            ActorRole.actor_id == actor_id,
            ActorRole.role_id == role.id,
        )
    )
    if result.rowcount == 0:
        raise ValueError(f"Actor does not have role '{role_name}'")
    await db.commit()


async def get_roles_for_actor(db: AsyncSession, actor_id: str) -> list[Role]:
    """Get all roles assigned to an actor."""
    result = await db.execute(
        select(Role)
        .join(ActorRole, ActorRole.role_id == Role.id)
        .where(ActorRole.actor_id == actor_id)
    )
    return list(result.scalars().all())


async def has_permission(db: AsyncSession, actor_id: str, permission: str) -> bool:
    """Check if an actor has a specific permission via any of their roles."""
    roles = await get_roles_for_actor(db, actor_id)
    for role in roles:
        perms = json.loads(role.permissions_json or "[]")
        if "*" in perms or permission in perms:
            return True
    return False
