"""Tests for marketplace.services.role_service (RBAC).

Covers:
- seed_system_roles: creates 6 default roles, is idempotent
- create_role: happy path, duplicate name raises ValueError
- get_role_by_name: found / not found
- list_roles: returns all roles
- update_role: changes description and permissions
- delete_role: removes non-system role, blocks system role deletion
- assign_role: creates assignment, is idempotent
- revoke_role: removes assignment, raises for missing assignment
- get_roles_for_actor: returns actor's roles
- has_permission: checks specific and wildcard permissions
"""

from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from marketplace.services.role_service import (
    SYSTEM_ROLES,
    assign_role,
    create_role,
    delete_role,
    get_role_by_name,
    get_roles_for_actor,
    has_permission,
    list_roles,
    revoke_role,
    seed_system_roles,
    update_role,
)


# ---------------------------------------------------------------------------
# In-memory DB fixture (self-contained — no conftest dependency)
# ---------------------------------------------------------------------------

@pytest.fixture
async def db() -> AsyncSession:
    from marketplace.database import Base

    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as session:
        yield session
    await engine.dispose()


# ---------------------------------------------------------------------------
# seed_system_roles
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_seed_system_roles_creates_six_roles(db: AsyncSession) -> None:
    """seed_system_roles creates exactly the 6 expected default system roles."""
    created = await seed_system_roles(db)
    assert len(created) == 6


@pytest.mark.asyncio
async def test_seed_system_roles_creates_expected_role_names(db: AsyncSession) -> None:
    """seed_system_roles creates roles with the correct names."""
    await seed_system_roles(db)
    roles = await list_roles(db)
    names = {r.name for r in roles}
    expected = {"admin", "moderator", "finance", "support", "creator", "user"}
    assert names == expected


@pytest.mark.asyncio
async def test_seed_system_roles_marks_all_as_system(db: AsyncSession) -> None:
    """All seeded roles have is_system=True."""
    await seed_system_roles(db)
    roles = await list_roles(db)
    assert all(r.is_system for r in roles)


@pytest.mark.asyncio
async def test_seed_system_roles_is_idempotent(db: AsyncSession) -> None:
    """Running seed_system_roles twice does not duplicate roles."""
    await seed_system_roles(db)
    second_created = await seed_system_roles(db)
    assert second_created == []
    roles = await list_roles(db)
    assert len(roles) == 6


@pytest.mark.asyncio
async def test_seed_system_roles_returns_empty_list_when_all_exist(db: AsyncSession) -> None:
    """seed_system_roles returns an empty list when no new roles were created."""
    await seed_system_roles(db)
    result = await seed_system_roles(db)
    assert result == []


# ---------------------------------------------------------------------------
# create_role
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_create_role_returns_role_with_correct_fields(db: AsyncSession) -> None:
    """create_role persists a non-system role with the given name, description, and permissions."""
    role = await create_role(
        db,
        name="analyst",
        description="Data analysis access",
        permissions=["reports:read", "analytics:read"],
    )

    assert role.id is not None
    assert role.name == "analyst"
    assert role.description == "Data analysis access"
    assert role.is_system is False


@pytest.mark.asyncio
async def test_create_role_with_no_permissions_defaults_to_empty_list(db: AsyncSession) -> None:
    """create_role with no permissions argument stores an empty permissions list."""
    import json

    role = await create_role(db, name="readonly")
    assert json.loads(role.permissions_json) == []


@pytest.mark.asyncio
async def test_create_role_raises_for_duplicate_name(db: AsyncSession) -> None:
    """create_role raises ValueError when a role with the same name already exists."""
    await create_role(db, name="duplicate-role")
    with pytest.raises(ValueError, match="already exists"):
        await create_role(db, name="duplicate-role")


@pytest.mark.asyncio
async def test_create_role_raises_for_duplicate_system_role_name(db: AsyncSession) -> None:
    """create_role raises ValueError when attempting to create a role with an existing system name."""
    await seed_system_roles(db)
    with pytest.raises(ValueError, match="already exists"):
        await create_role(db, name="admin")


# ---------------------------------------------------------------------------
# get_role_by_name
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_role_by_name_returns_role_when_found(db: AsyncSession) -> None:
    """get_role_by_name returns the matching Role object."""
    await create_role(db, name="tester-role")
    role = await get_role_by_name(db, "tester-role")
    assert role is not None
    assert role.name == "tester-role"


@pytest.mark.asyncio
async def test_get_role_by_name_returns_none_for_missing_name(db: AsyncSession) -> None:
    """get_role_by_name returns None when no role has the given name."""
    result = await get_role_by_name(db, "nonexistent-role")
    assert result is None


# ---------------------------------------------------------------------------
# list_roles
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_list_roles_returns_all_roles_ordered_by_name(db: AsyncSession) -> None:
    """list_roles returns all roles sorted alphabetically by name."""
    await seed_system_roles(db)
    await create_role(db, name="zzz-custom")
    roles = await list_roles(db)
    names = [r.name for r in roles]
    assert names == sorted(names)


@pytest.mark.asyncio
async def test_list_roles_returns_empty_when_no_roles_exist(db: AsyncSession) -> None:
    """list_roles returns an empty list when the roles table is empty."""
    roles = await list_roles(db)
    assert roles == []


@pytest.mark.asyncio
async def test_list_roles_includes_system_and_custom_roles(db: AsyncSession) -> None:
    """list_roles returns both system roles and custom roles."""
    await seed_system_roles(db)
    await create_role(db, name="my-custom-role")
    roles = await list_roles(db)
    names = {r.name for r in roles}
    assert "admin" in names
    assert "my-custom-role" in names


# ---------------------------------------------------------------------------
# update_role
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_update_role_changes_description(db: AsyncSession) -> None:
    """update_role updates the description field."""
    role = await create_role(db, name="updatable", description="old description")
    updated = await update_role(db, role.id, description="new description")
    assert updated.description == "new description"


@pytest.mark.asyncio
async def test_update_role_changes_permissions(db: AsyncSession) -> None:
    """update_role replaces the permissions list."""
    import json

    role = await create_role(db, name="perm-role", permissions=["old:perm"])
    updated = await update_role(db, role.id, permissions=["new:perm", "another:perm"])
    assert json.loads(updated.permissions_json) == ["new:perm", "another:perm"]


@pytest.mark.asyncio
async def test_update_role_raises_for_nonexistent_role(db: AsyncSession) -> None:
    """update_role raises ValueError when the role_id does not exist."""
    with pytest.raises(ValueError, match="Role not found"):
        await update_role(db, "nonexistent-id", description="anything")


@pytest.mark.asyncio
async def test_update_role_none_description_leaves_field_unchanged(db: AsyncSession) -> None:
    """update_role with description=None does not overwrite the existing description."""
    role = await create_role(db, name="stable-desc", description="keep this")
    updated = await update_role(db, role.id, description=None)
    assert updated.description == "keep this"


# ---------------------------------------------------------------------------
# delete_role
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_delete_role_removes_non_system_role(db: AsyncSession) -> None:
    """delete_role successfully removes a custom (non-system) role."""
    role = await create_role(db, name="to-delete")
    await delete_role(db, role.id)
    result = await get_role_by_name(db, "to-delete")
    assert result is None


@pytest.mark.asyncio
async def test_delete_role_raises_for_nonexistent_role(db: AsyncSession) -> None:
    """delete_role raises ValueError when the role does not exist."""
    with pytest.raises(ValueError, match="Role not found"):
        await delete_role(db, "ghost-id")


@pytest.mark.asyncio
async def test_delete_role_raises_for_system_role(db: AsyncSession) -> None:
    """delete_role raises ValueError when attempting to delete a system role."""
    await seed_system_roles(db)
    admin = await get_role_by_name(db, "admin")
    with pytest.raises(ValueError, match="Cannot delete system role"):
        await delete_role(db, admin.id)


@pytest.mark.asyncio
async def test_delete_role_also_removes_actor_assignments(db: AsyncSession) -> None:
    """delete_role removes all ActorRole rows that reference the deleted role."""
    role = await create_role(db, name="soon-deleted")
    await assign_role(db, actor_id="actor-1", actor_type="user", role_name="soon-deleted", granted_by="admin-1")
    await delete_role(db, role.id)
    # After deletion the actor should have no roles
    roles = await get_roles_for_actor(db, "actor-1")
    assert roles == []


# ---------------------------------------------------------------------------
# assign_role
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_assign_role_creates_actor_role_row(db: AsyncSession) -> None:
    """assign_role persists an ActorRole assignment linking actor to role."""
    await create_role(db, name="assignable")
    assignment = await assign_role(
        db, actor_id="user-abc", actor_type="user", role_name="assignable", granted_by="admin-x"
    )
    assert assignment.actor_id == "user-abc"
    assert assignment.actor_type == "user"
    assert assignment.granted_by == "admin-x"


@pytest.mark.asyncio
async def test_assign_role_raises_for_nonexistent_role(db: AsyncSession) -> None:
    """assign_role raises ValueError when the role name does not exist."""
    with pytest.raises(ValueError, match="not found"):
        await assign_role(db, actor_id="u1", actor_type="user", role_name="ghost-role", granted_by="admin")


@pytest.mark.asyncio
async def test_assign_role_is_idempotent(db: AsyncSession) -> None:
    """assign_role called twice for the same actor/role pair returns the existing assignment."""
    await create_role(db, name="idempotent-role")
    first = await assign_role(db, actor_id="actor-z", actor_type="agent", role_name="idempotent-role", granted_by="admin")
    second = await assign_role(db, actor_id="actor-z", actor_type="agent", role_name="idempotent-role", granted_by="admin")
    assert first.id == second.id


@pytest.mark.asyncio
async def test_assign_role_same_actor_different_roles_creates_two_rows(db: AsyncSession) -> None:
    """assign_role allows the same actor to hold multiple distinct roles."""
    await create_role(db, name="role-alpha")
    await create_role(db, name="role-beta")
    await assign_role(db, actor_id="actor-multi", actor_type="user", role_name="role-alpha", granted_by="admin")
    await assign_role(db, actor_id="actor-multi", actor_type="user", role_name="role-beta", granted_by="admin")
    roles = await get_roles_for_actor(db, "actor-multi")
    names = {r.name for r in roles}
    assert names == {"role-alpha", "role-beta"}


# ---------------------------------------------------------------------------
# revoke_role
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_revoke_role_removes_assignment(db: AsyncSession) -> None:
    """revoke_role deletes the ActorRole row so the actor no longer has the role."""
    await create_role(db, name="revocable")
    await assign_role(db, actor_id="actor-rev", actor_type="user", role_name="revocable", granted_by="admin")
    await revoke_role(db, actor_id="actor-rev", role_name="revocable")
    roles = await get_roles_for_actor(db, "actor-rev")
    assert roles == []


@pytest.mark.asyncio
async def test_revoke_role_raises_for_nonexistent_assignment(db: AsyncSession) -> None:
    """revoke_role raises ValueError when the actor does not hold the given role."""
    await create_role(db, name="not-assigned-role")
    with pytest.raises(ValueError, match="does not have role"):
        await revoke_role(db, actor_id="actor-x", role_name="not-assigned-role")


@pytest.mark.asyncio
async def test_revoke_role_raises_for_unknown_role_name(db: AsyncSession) -> None:
    """revoke_role raises ValueError when the role name itself does not exist."""
    with pytest.raises(ValueError, match="not found"):
        await revoke_role(db, actor_id="actor-x", role_name="totally-unknown-role")


# ---------------------------------------------------------------------------
# get_roles_for_actor
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_roles_for_actor_returns_assigned_roles(db: AsyncSession) -> None:
    """get_roles_for_actor returns all roles the actor has been assigned."""
    await create_role(db, name="viewer")
    await create_role(db, name="editor")
    await assign_role(db, actor_id="actor-check", actor_type="user", role_name="viewer", granted_by="admin")
    await assign_role(db, actor_id="actor-check", actor_type="user", role_name="editor", granted_by="admin")
    roles = await get_roles_for_actor(db, "actor-check")
    names = {r.name for r in roles}
    assert names == {"viewer", "editor"}


@pytest.mark.asyncio
async def test_get_roles_for_actor_returns_empty_list_for_unassigned_actor(db: AsyncSession) -> None:
    """get_roles_for_actor returns an empty list when the actor has no assignments."""
    roles = await get_roles_for_actor(db, "actor-nobody")
    assert roles == []


@pytest.mark.asyncio
async def test_get_roles_for_actor_isolates_actors(db: AsyncSession) -> None:
    """get_roles_for_actor does not return roles assigned to other actors."""
    await create_role(db, name="isolated-role")
    await assign_role(db, actor_id="actor-a", actor_type="user", role_name="isolated-role", granted_by="admin")
    roles_b = await get_roles_for_actor(db, "actor-b")
    assert roles_b == []


# ---------------------------------------------------------------------------
# has_permission
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_has_permission_returns_true_for_exact_permission(db: AsyncSession) -> None:
    """has_permission returns True when the actor's role includes the exact permission string."""
    await create_role(db, name="perm-exact", permissions=["reports:read"])
    await assign_role(db, actor_id="actor-perm", actor_type="user", role_name="perm-exact", granted_by="admin")
    result = await has_permission(db, "actor-perm", "reports:read")
    assert result is True


@pytest.mark.asyncio
async def test_has_permission_returns_false_for_missing_permission(db: AsyncSession) -> None:
    """has_permission returns False when the actor's role does not include the permission."""
    await create_role(db, name="perm-limited", permissions=["reports:read"])
    await assign_role(db, actor_id="actor-limited", actor_type="user", role_name="perm-limited", granted_by="admin")
    result = await has_permission(db, "actor-limited", "admin:delete")
    assert result is False


@pytest.mark.asyncio
async def test_has_permission_wildcard_grants_all_permissions(db: AsyncSession) -> None:
    """has_permission returns True for any permission when role has wildcard '*'."""
    await seed_system_roles(db)
    await assign_role(db, actor_id="actor-admin", actor_type="user", role_name="admin", granted_by="system")
    result = await has_permission(db, "actor-admin", "anything:whatsoever")
    assert result is True


@pytest.mark.asyncio
async def test_has_permission_returns_false_for_actor_with_no_roles(db: AsyncSession) -> None:
    """has_permission returns False for an actor who holds no roles."""
    result = await has_permission(db, "actor-no-roles", "reports:read")
    assert result is False


@pytest.mark.asyncio
async def test_has_permission_checks_across_all_actor_roles(db: AsyncSession) -> None:
    """has_permission returns True if any one of the actor's roles grants the permission."""
    await create_role(db, name="role-x", permissions=["x:read"])
    await create_role(db, name="role-y", permissions=["y:write"])
    await assign_role(db, actor_id="actor-multi-perm", actor_type="user", role_name="role-x", granted_by="admin")
    await assign_role(db, actor_id="actor-multi-perm", actor_type="user", role_name="role-y", granted_by="admin")
    # Actor has role-x (x:read) and role-y (y:write); should have both
    assert await has_permission(db, "actor-multi-perm", "x:read") is True
    assert await has_permission(db, "actor-multi-perm", "y:write") is True
    assert await has_permission(db, "actor-multi-perm", "z:delete") is False
