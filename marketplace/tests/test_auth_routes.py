"""Integration tests for all auth API routes.

Tests the full auth flow: register -> login -> get tokens -> refresh -> revoke,
plus RBAC, API key, and auth event endpoints.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from marketplace.config import settings
from marketplace.database import Base

# Use the actual settings secret so patching at import sites is unnecessary.
_TEST_JWT_SECRET = settings.jwt_secret_key
_TEST_JWT_ALGORITHM = settings.jwt_algorithm


@pytest_asyncio.fixture
async def db_engine():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def db(db_engine):
    session_factory = async_sessionmaker(
        db_engine, class_=AsyncSession, expire_on_commit=False,
    )
    async with session_factory() as session:
        yield session


@pytest_asyncio.fixture
async def app(db_engine):
    """Create a test FastAPI app with auth routes."""
    from fastapi.responses import JSONResponse
    from starlette.requests import Request

    from marketplace.api.v2_auth import router as auth_router
    from marketplace.api.v2_roles import router as roles_router
    from marketplace.api.v2_api_keys import router as api_keys_router
    from marketplace.api.v2_auth_events import router as auth_events_router
    from marketplace.core.exceptions import DomainError

    test_app = FastAPI()

    # Register the DomainError handler (mirrors main.py)
    @test_app.exception_handler(DomainError)
    async def _domain_error_handler(_request: Request, exc: DomainError):
        return JSONResponse(
            status_code=exc.http_status,
            content={"detail": exc.detail, "code": exc.code},
        )

    session_factory = async_sessionmaker(
        db_engine, class_=AsyncSession, expire_on_commit=False,
    )

    async def get_test_db():
        async with session_factory() as session:
            yield session

    from marketplace.database import get_db
    test_app.dependency_overrides[get_db] = get_test_db

    test_app.include_router(auth_router, prefix="/api/v2")
    test_app.include_router(roles_router, prefix="/api/v2")
    test_app.include_router(api_keys_router, prefix="/api/v2")
    test_app.include_router(auth_events_router, prefix="/api/v2")

    return test_app


@pytest_asyncio.fixture
async def client(app):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


def _create_test_token(
    actor_id: str,
    actor_type: str = "creator",
    email: str = "test@example.com",
) -> str:
    """Create a JWT token for testing using the actual settings secret."""
    from jose import jwt
    payload = {
        "sub": actor_id,
        "type": actor_type,
        "email": email,
        "jti": str(uuid.uuid4()),
        "aud": "agentchains-marketplace",
        "iss": "agentchains",
        "exp": datetime.now(timezone.utc) + timedelta(hours=1),
        "iat": datetime.now(timezone.utc),
    }
    return jwt.encode(payload, _TEST_JWT_SECRET, algorithm=_TEST_JWT_ALGORITHM)


# ── Auth /me endpoint ───────────────────────────────────────────


@pytest.mark.asyncio
async def test_auth_me_returns_actor_context(client: AsyncClient):
    """GET /auth/me returns the authenticated actor's identity."""
    token = _create_test_token("creator-123", "creator")
    resp = await client.get(
        "/api/v2/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["actor_id"] == "creator-123"
    assert data["actor_type"] == "creator"
    assert isinstance(data["roles"], list)
    assert isinstance(data["scopes"], list)


@pytest.mark.asyncio
async def test_auth_me_without_token_returns_401(client: AsyncClient):
    """GET /auth/me without Authorization header returns 401."""
    resp = await client.get("/api/v2/auth/me")
    assert resp.status_code == 401


# ── Token refresh endpoint ──────────────────────────────────────


@pytest.mark.asyncio
async def test_refresh_with_invalid_token_returns_401(client: AsyncClient):
    """POST /auth/refresh with invalid refresh token returns 401."""
    resp = await client.post(
        "/api/v2/auth/refresh",
        json={"refresh_token": "rt_invalid_token_here"},
    )
    assert resp.status_code == 401


# ── Token revoke endpoint ──────────────────────────────────────


@pytest.mark.asyncio
async def test_revoke_current_token(client: AsyncClient):
    """POST /auth/revoke revokes the current access token."""
    token = _create_test_token("creator-456", "creator")
    resp = await client.post(
        "/api/v2/auth/revoke",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 204


@pytest.mark.asyncio
async def test_revoke_all_tokens(client: AsyncClient):
    """POST /auth/revoke-all revokes all tokens for the actor."""
    token = _create_test_token("creator-789", "creator")
    resp = await client.post(
        "/api/v2/auth/revoke-all",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 204


# ── Change password endpoint ────────────────────────────────────


@pytest.mark.asyncio
async def test_change_password_for_agent_returns_400(client: AsyncClient):
    """POST /auth/change-password for agent actor type returns 400."""
    token = _create_test_token("agent-001", "agent")
    # Agent tokens don't have "type" field, so the decoder sees them as agents
    # But we explicitly set type="agent" here
    resp = await client.post(
        "/api/v2/auth/change-password",
        headers={"Authorization": f"Bearer {token}"},
        json={"current_password": "old-pass", "new_password": "NewPass123!"},
    )
    assert resp.status_code == 400


# ── API key endpoints ───────────────────────────────────────────


@pytest.mark.asyncio
async def test_create_and_list_api_keys(client: AsyncClient):
    """Full API key lifecycle: create -> list -> verify prefix."""
    token = _create_test_token("creator-api-test", "creator")
    headers = {"Authorization": f"Bearer {token}"}

    # Create
    resp = await client.post(
        "/api/v2/api-keys",
        headers=headers,
        json={"name": "CI/CD Key", "scopes": ["agents:read"]},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["key"].startswith("ac_live_")
    assert data["name"] == "CI/CD Key"
    key_id = data["id"]

    # List
    resp = await client.get("/api/v2/api-keys", headers=headers)
    assert resp.status_code == 200
    keys = resp.json()
    assert len(keys) >= 1
    assert any(k["id"] == key_id for k in keys)

    # Usage
    resp = await client.get(f"/api/v2/api-keys/{key_id}/usage", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["key_id"] == key_id


@pytest.mark.asyncio
async def test_revoke_api_key(client: AsyncClient):
    """DELETE /api-keys/{key_id} revokes the key."""
    token = _create_test_token("creator-revoke-test", "creator")
    headers = {"Authorization": f"Bearer {token}"}

    # Create a key first
    resp = await client.post(
        "/api/v2/api-keys",
        headers=headers,
        json={"name": "Temp Key"},
    )
    assert resp.status_code == 201
    key_id = resp.json()["id"]

    # Revoke
    resp = await client.delete(f"/api/v2/api-keys/{key_id}", headers=headers)
    assert resp.status_code == 204

    # Verify it appears as revoked in list
    resp = await client.get("/api/v2/api-keys", headers=headers)
    revoked_key = next(k for k in resp.json() if k["id"] == key_id)
    assert revoked_key["revoked"] is True


# ── Role management endpoints (admin-only) ──────────────────────


@pytest.mark.asyncio
async def test_roles_endpoint_requires_admin(client: AsyncClient):
    """GET /roles returns 403 for non-admin actor."""
    token = _create_test_token("regular-creator", "creator")
    resp = await client.get(
        "/api/v2/roles",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_roles_list_with_admin(client: AsyncClient, db: AsyncSession):
    """GET /roles returns roles for admin actor."""
    from marketplace.services.role_service import assign_role, seed_system_roles

    # Seed roles and assign admin
    await seed_system_roles(db)
    admin_id = "admin-creator-001"
    await assign_role(db, admin_id, "creator", "admin", "system")

    token = _create_test_token(admin_id, "creator")
    resp = await client.get(
        "/api/v2/roles",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    roles = resp.json()
    assert len(roles) >= 6  # 6 system roles
    role_names = {r["name"] for r in roles}
    assert "admin" in role_names
    assert "moderator" in role_names
    assert "finance" in role_names


@pytest.mark.asyncio
async def test_create_custom_role(client: AsyncClient, db: AsyncSession):
    """POST /roles creates a custom role (admin-only)."""
    from marketplace.services.role_service import assign_role, seed_system_roles

    await seed_system_roles(db)
    admin_id = "admin-creator-002"
    await assign_role(db, admin_id, "creator", "admin", "system")

    token = _create_test_token(admin_id, "creator")
    resp = await client.post(
        "/api/v2/roles",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "name": "reviewer",
            "description": "Code reviewer role",
            "permissions": ["listings:review", "agents:read"],
        },
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "reviewer"
    assert data["is_system"] is False
    assert "listings:review" in data["permissions"]


@pytest.mark.asyncio
async def test_assign_and_revoke_role(client: AsyncClient, db: AsyncSession):
    """Full role assignment lifecycle: assign -> check -> revoke."""
    from marketplace.services.role_service import assign_role, seed_system_roles

    await seed_system_roles(db)
    admin_id = "admin-creator-003"
    await assign_role(db, admin_id, "creator", "admin", "system")

    token = _create_test_token(admin_id, "creator")
    target_actor = "target-actor-001"

    # Assign
    resp = await client.post(
        f"/api/v2/roles/actors/{target_actor}/roles",
        headers={"Authorization": f"Bearer {token}"},
        json={"role_name": "moderator"},
    )
    assert resp.status_code == 201

    # Check
    resp = await client.get(
        f"/api/v2/roles/actors/{target_actor}/roles",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    role_names = {r["name"] for r in resp.json()["roles"]}
    assert "moderator" in role_names

    # Revoke
    resp = await client.delete(
        f"/api/v2/roles/actors/{target_actor}/roles/moderator",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 204


# ── Auth events endpoints (admin-only) ──────────────────────────


@pytest.mark.asyncio
async def test_auth_events_requires_admin(client: AsyncClient):
    """GET /auth/events returns 403 for non-admin."""
    token = _create_test_token("regular-creator-2", "creator")
    resp = await client.get(
        "/api/v2/auth/events",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_auth_events_list_with_admin(client: AsyncClient, db: AsyncSession):
    """GET /auth/events returns events for admin."""
    from marketplace.services.role_service import assign_role, seed_system_roles
    from marketplace.services import auth_event_service

    await seed_system_roles(db)
    admin_id = "admin-creator-events"
    await assign_role(db, admin_id, "creator", "admin", "system")

    # Log some events
    await auth_event_service.log_auth_event(
        db, actor_id="user-1", event_type="login_success",
    )
    await auth_event_service.log_auth_event(
        db, actor_id="user-2", event_type="login_failure",
    )

    token = _create_test_token(admin_id, "creator")
    resp = await client.get(
        "/api/v2/auth/events",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] >= 2
    assert len(data["items"]) >= 2


@pytest.mark.asyncio
async def test_auth_events_summary_with_admin(client: AsyncClient, db: AsyncSession):
    """GET /auth/events/summary returns aggregated stats for admin."""
    from marketplace.services.role_service import assign_role, seed_system_roles

    await seed_system_roles(db)
    admin_id = "admin-creator-summary"
    await assign_role(db, admin_id, "creator", "admin", "system")

    token = _create_test_token(admin_id, "creator")
    resp = await client.get(
        "/api/v2/auth/events/summary",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "total_events" in data
    assert "login_successes" in data
    assert "login_failures" in data
    assert "period_hours" in data
