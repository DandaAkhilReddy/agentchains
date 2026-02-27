"""Tests for marketplace/api/v2_users.py -- end-user account endpoints.

Uses real HTTP requests through the ``client`` fixture.  The dual_layer_service
is mocked because user registration/login involves password hashing and complex
model creation (EndUser, managed agent), but all route-level logic runs for
real.  User auth uses real JWT tokens via ``create_user_token``.
"""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

from marketplace.core.user_auth import create_user_token
from marketplace.tests.conftest import _new_id


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _user_auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


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

USERS_PREFIX = "/api/v2/users"


# ---------------------------------------------------------------------------
# POST /api/v2/users/register -- register a new end user
# ---------------------------------------------------------------------------

async def test_register_user_success(client):
    """POST /register creates a new user and returns auth response."""
    with patch(
        "marketplace.api.v2_users.dual_layer_service.register_end_user",
        new_callable=AsyncMock,
        return_value=_MOCK_AUTH_RESPONSE,
    ):
        resp = await client.post(
            f"{USERS_PREFIX}/register",
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
    """POST /register returns 409 when email is already registered."""
    with patch(
        "marketplace.api.v2_users.dual_layer_service.register_end_user",
        new_callable=AsyncMock,
        side_effect=ValueError("Email already registered"),
    ):
        resp = await client.post(
            f"{USERS_PREFIX}/register",
            json={
                "email": "existing@example.com",
                "password": "securepassword123",
            },
        )
    assert resp.status_code == 409
    assert "already registered" in resp.json()["detail"].lower()


async def test_register_user_short_email(client):
    """POST /register rejects email shorter than min_length=5."""
    resp = await client.post(
        f"{USERS_PREFIX}/register",
        json={
            "email": "x@y",
            "password": "securepassword123",
        },
    )
    assert resp.status_code == 422


async def test_register_user_short_password(client):
    """POST /register rejects password shorter than min_length=8."""
    resp = await client.post(
        f"{USERS_PREFIX}/register",
        json={
            "email": "user@example.com",
            "password": "short",
        },
    )
    assert resp.status_code == 422


async def test_register_user_missing_email(client):
    """POST /register rejects missing email field."""
    resp = await client.post(
        f"{USERS_PREFIX}/register",
        json={"password": "securepassword123"},
    )
    assert resp.status_code == 422


async def test_register_user_missing_password(client):
    """POST /register rejects missing password field."""
    resp = await client.post(
        f"{USERS_PREFIX}/register",
        json={"email": "user@example.com"},
    )
    assert resp.status_code == 422


async def test_register_user_empty_body(client):
    """POST /register rejects empty body."""
    resp = await client.post(f"{USERS_PREFIX}/register", json={})
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# POST /api/v2/users/login -- login an end user
# ---------------------------------------------------------------------------

async def test_login_user_success(client):
    """POST /login returns auth response on valid credentials."""
    with patch(
        "marketplace.api.v2_users.dual_layer_service.login_end_user",
        new_callable=AsyncMock,
        return_value=_MOCK_AUTH_RESPONSE,
    ):
        resp = await client.post(
            f"{USERS_PREFIX}/login",
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
    """POST /login returns 401 on wrong password."""
    with patch(
        "marketplace.api.v2_users.dual_layer_service.login_end_user",
        new_callable=AsyncMock,
        side_effect=ValueError("Invalid email or password"),
    ):
        resp = await client.post(
            f"{USERS_PREFIX}/login",
            json={
                "email": "test@example.com",
                "password": "wrongpassword",
            },
        )
    assert resp.status_code == 401
    assert "invalid" in resp.json()["detail"].lower()


async def test_login_user_missing_fields(client):
    """POST /login rejects missing password field."""
    resp = await client.post(
        f"{USERS_PREFIX}/login",
        json={"email": "test@example.com"},
    )
    assert resp.status_code == 422


async def test_login_user_empty_body(client):
    """POST /login rejects empty body."""
    resp = await client.post(f"{USERS_PREFIX}/login", json={})
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# GET /api/v2/users/me -- get current user profile
# ---------------------------------------------------------------------------

async def test_get_user_me_success(client):
    """GET /me returns current user profile."""
    user_id = f"user-{_new_id()[:8]}"
    user_token = create_user_token(user_id, "me@test.com")

    with patch(
        "marketplace.api.v2_users.dual_layer_service.get_end_user_payload",
        new_callable=AsyncMock,
        return_value={**_MOCK_USER, "id": user_id},
    ):
        resp = await client.get(
            f"{USERS_PREFIX}/me",
            headers=_user_auth(user_token),
        )
    assert resp.status_code == 200
    body = resp.json()
    assert body["id"] == user_id
    assert body["email"] == "test@example.com"
    assert body["status"] == "active"


async def test_get_user_me_not_found(client):
    """GET /me returns 404 when user is not in the database."""
    user_id = f"user-{_new_id()[:8]}"
    user_token = create_user_token(user_id, "ghost@test.com")

    with patch(
        "marketplace.api.v2_users.dual_layer_service.get_end_user_payload",
        new_callable=AsyncMock,
        side_effect=ValueError("User not found"),
    ):
        resp = await client.get(
            f"{USERS_PREFIX}/me",
            headers=_user_auth(user_token),
        )
    assert resp.status_code == 404


async def test_get_user_me_no_auth(client):
    """GET /me without auth returns 401."""
    resp = await client.get(f"{USERS_PREFIX}/me")
    assert resp.status_code == 401


async def test_get_user_me_agent_token_rejected(client, make_agent):
    """GET /me rejects agent tokens."""
    _, agent_token = await make_agent()
    resp = await client.get(
        f"{USERS_PREFIX}/me",
        headers=_user_auth(agent_token),
    )
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# GET /api/v2/users/events/stream-token -- get user stream token
# ---------------------------------------------------------------------------

async def test_get_user_stream_token_success(client):
    """GET /events/stream-token returns a valid stream token."""
    user_id = f"user-{_new_id()[:8]}"
    user_token = create_user_token(user_id, "stream@test.com")

    resp = await client.get(
        f"{USERS_PREFIX}/events/stream-token",
        headers=_user_auth(user_token),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["user_id"] == user_id
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
    """GET /events/stream-token without auth returns 401."""
    resp = await client.get(f"{USERS_PREFIX}/events/stream-token")
    assert resp.status_code == 401


async def test_get_user_stream_token_invalid_auth(client):
    """GET /events/stream-token with garbage token returns 401."""
    resp = await client.get(
        f"{USERS_PREFIX}/events/stream-token",
        headers={"Authorization": "Bearer invalid-garbage-token"},
    )
    assert resp.status_code == 401


async def test_get_user_stream_token_agent_token_rejected(client, make_agent):
    """Agent tokens should not work for user endpoints."""
    _, agent_token = await make_agent()

    resp = await client.get(
        f"{USERS_PREFIX}/events/stream-token",
        headers={"Authorization": f"Bearer {agent_token}"},
    )
    assert resp.status_code == 401


async def test_get_user_stream_token_creator_token_rejected(client, make_creator):
    """Creator tokens should not work for user endpoints."""
    _, creator_token = await make_creator()

    resp = await client.get(
        f"{USERS_PREFIX}/events/stream-token",
        headers={"Authorization": f"Bearer {creator_token}"},
    )
    assert resp.status_code == 401
