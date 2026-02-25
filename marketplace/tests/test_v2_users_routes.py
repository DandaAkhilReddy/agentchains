"""Tests for marketplace/api/v2_users.py — end-user account endpoints."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

from marketplace.core.user_auth import get_current_user_id
from marketplace.main import app
from marketplace.tests.conftest import _new_id


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _user_auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _override_user_id(user_id: str = "user-1"):
    app.dependency_overrides[get_current_user_id] = lambda: user_id


def _clear_user_override():
    app.dependency_overrides.pop(get_current_user_id, None)


_NOW = datetime.now(timezone.utc)

_MOCK_USER = {
    "id": "user-1",
    "email": "test@example.com",
    "status": "active",
    "managed_agent_id": "agent-1",
    "created_at": _NOW.isoformat(),
    "updated_at": _NOW.isoformat(),
    "last_login_at": None,
}

_MOCK_AUTH_RESPONSE = {
    "user": _MOCK_USER,
    "token": "jwt-token-here",
}


# ---------------------------------------------------------------------------
# POST /api/v2/users/register — register a new end user
# ---------------------------------------------------------------------------

async def test_register_user_success(client):
    with patch(
        "marketplace.api.v2_users.dual_layer_service.register_end_user",
        new_callable=AsyncMock,
        return_value=_MOCK_AUTH_RESPONSE,
    ):
        resp = await client.post(
            "/api/v2/users/register",
            json={
                "email": "newuser@example.com",
                "password": "securepassword123",
            },
        )
    assert resp.status_code == 201
    body = resp.json()
    assert "user" in body
    assert "token" in body
    assert body["user"]["email"] == "test@example.com"


async def test_register_user_conflict(client):
    with patch(
        "marketplace.api.v2_users.dual_layer_service.register_end_user",
        new_callable=AsyncMock,
        side_effect=ValueError("Email already registered"),
    ):
        resp = await client.post(
            "/api/v2/users/register",
            json={
                "email": "existing@example.com",
                "password": "securepassword123",
            },
        )
    assert resp.status_code == 409
    assert "already registered" in resp.json()["detail"].lower()


async def test_register_user_short_email(client):
    resp = await client.post(
        "/api/v2/users/register",
        json={
            "email": "x@y",  # min_length=5
            "password": "securepassword123",
        },
    )
    assert resp.status_code == 422


async def test_register_user_short_password(client):
    resp = await client.post(
        "/api/v2/users/register",
        json={
            "email": "user@example.com",
            "password": "short",  # min_length=8
        },
    )
    assert resp.status_code == 422


async def test_register_user_missing_email(client):
    resp = await client.post(
        "/api/v2/users/register",
        json={
            "password": "securepassword123",
        },
    )
    assert resp.status_code == 422


async def test_register_user_missing_password(client):
    resp = await client.post(
        "/api/v2/users/register",
        json={
            "email": "user@example.com",
        },
    )
    assert resp.status_code == 422


async def test_register_user_empty_body(client):
    resp = await client.post("/api/v2/users/register", json={})
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# POST /api/v2/users/login — login an end user
# ---------------------------------------------------------------------------

async def test_login_user_success(client):
    with patch(
        "marketplace.api.v2_users.dual_layer_service.login_end_user",
        new_callable=AsyncMock,
        return_value=_MOCK_AUTH_RESPONSE,
    ):
        resp = await client.post(
            "/api/v2/users/login",
            json={
                "email": "test@example.com",
                "password": "securepassword123",
            },
        )
    assert resp.status_code == 200
    body = resp.json()
    assert "user" in body
    assert "token" in body


async def test_login_user_invalid_credentials(client):
    with patch(
        "marketplace.api.v2_users.dual_layer_service.login_end_user",
        new_callable=AsyncMock,
        side_effect=ValueError("Invalid email or password"),
    ):
        resp = await client.post(
            "/api/v2/users/login",
            json={
                "email": "test@example.com",
                "password": "wrongpassword",
            },
        )
    assert resp.status_code == 401
    assert "invalid" in resp.json()["detail"].lower()


async def test_login_user_missing_fields(client):
    resp = await client.post(
        "/api/v2/users/login",
        json={"email": "test@example.com"},
    )
    assert resp.status_code == 422


async def test_login_user_empty_body(client):
    resp = await client.post("/api/v2/users/login", json={})
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# GET /api/v2/users/me — get current user profile
# ---------------------------------------------------------------------------

async def test_get_user_me_success(client):
    _override_user_id("user-1")
    try:
        with patch(
            "marketplace.api.v2_users.dual_layer_service.get_end_user_payload",
            new_callable=AsyncMock,
            return_value=_MOCK_USER,
        ):
            resp = await client.get("/api/v2/users/me")
    finally:
        _clear_user_override()

    assert resp.status_code == 200
    body = resp.json()
    assert body["id"] == "user-1"
    assert body["email"] == "test@example.com"
    assert body["status"] == "active"
    assert body["managed_agent_id"] == "agent-1"


async def test_get_user_me_not_found(client):
    _override_user_id("user-nonexistent")
    try:
        with patch(
            "marketplace.api.v2_users.dual_layer_service.get_end_user_payload",
            new_callable=AsyncMock,
            side_effect=ValueError("User not found"),
        ):
            resp = await client.get("/api/v2/users/me")
    finally:
        _clear_user_override()

    assert resp.status_code == 404


async def test_get_user_me_no_auth(client):
    resp = await client.get("/api/v2/users/me")
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# GET /api/v2/users/events/stream-token — get user stream token
# ---------------------------------------------------------------------------

async def test_get_user_stream_token_success(client):
    _override_user_id("user-1")
    try:
        resp = await client.get("/api/v2/users/events/stream-token")
    finally:
        _clear_user_override()

    assert resp.status_code == 200
    body = resp.json()
    assert body["user_id"] == "user-1"
    assert "stream_token" in body
    assert body["stream_token"]  # non-empty
    assert "expires_in_seconds" in body
    assert body["expires_in_seconds"] > 0
    assert "expires_at" in body
    assert body["ws_url"] == "/ws/v2/events"
    assert "allowed_topics" in body
    assert "public.market" in body["allowed_topics"]
    assert "public.market.orders" in body["allowed_topics"]
    assert "private.user" in body["allowed_topics"]


async def test_get_user_stream_token_no_auth(client):
    resp = await client.get("/api/v2/users/events/stream-token")
    assert resp.status_code == 401


async def test_get_user_stream_token_invalid_auth(client):
    resp = await client.get(
        "/api/v2/users/events/stream-token",
        headers={"Authorization": "Bearer invalid-garbage-token"},
    )
    assert resp.status_code == 401


async def test_get_user_stream_token_agent_token_rejected(client, make_agent):
    """Agent tokens should not work for user endpoints."""
    _, agent_token = await make_agent()

    resp = await client.get(
        "/api/v2/users/events/stream-token",
        headers={"Authorization": f"Bearer {agent_token}"},
    )
    assert resp.status_code == 401
