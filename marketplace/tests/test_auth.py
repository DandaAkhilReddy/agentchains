"""Tests for marketplace.core.auth — agent JWT creation, decoding, and FastAPI deps.

Covers:
- create_access_token: payload structure, claims
- create_stream_token: token types, allowed_topics per type, subject_type mapping
- decode_token: valid decode, rejection of creator/user/stream tokens
- decode_stream_token: valid stream decode, rejection of non-stream tokens
- get_current_agent_id: header parsing, valid extraction, error paths
- optional_agent_id: returns None on missing/invalid auth
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from jose import jwt as jose_jwt

from marketplace.config import settings
from marketplace.core.auth import (
    create_access_token,
    create_stream_token,
    decode_stream_token,
    decode_token,
    get_current_agent_id,
    optional_agent_id,
)
from marketplace.core.exceptions import UnauthorizedError


# ---------------------------------------------------------------------------
# create_access_token
# ---------------------------------------------------------------------------


class TestCreateAccessToken:
    """Agent JWT creation."""

    def test_token_contains_sub_and_name(self) -> None:
        token = create_access_token("agent-42", "search-bot")
        payload = jose_jwt.decode(
            token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm],
            audience="agentchains-marketplace", issuer="agentchains",
        )
        assert payload["sub"] == "agent-42"
        assert payload["name"] == "search-bot"

    def test_token_has_correct_aud_and_iss(self) -> None:
        token = create_access_token("a-1", "bot")
        payload = jose_jwt.decode(
            token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm],
            audience="agentchains-marketplace", issuer="agentchains",
        )
        assert payload["aud"] == "agentchains-marketplace"
        assert payload["iss"] == "agentchains"

    def test_token_has_expiration_and_issued_at(self) -> None:
        token = create_access_token("a-1", "bot")
        payload = jose_jwt.decode(
            token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm],
            audience="agentchains-marketplace", issuer="agentchains",
        )
        assert "exp" in payload
        assert "iat" in payload

    def test_token_does_not_have_type_claim(self) -> None:
        """Agent access tokens have no 'type' field (distinguishes from creator/stream)."""
        token = create_access_token("a-1", "bot")
        payload = jose_jwt.decode(
            token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm],
            audience="agentchains-marketplace", issuer="agentchains",
        )
        assert "type" not in payload


# ---------------------------------------------------------------------------
# create_stream_token
# ---------------------------------------------------------------------------


class TestCreateStreamToken:
    """WebSocket stream token generation."""

    def test_default_stream_agent_type(self) -> None:
        token = create_stream_token("agent-1")
        payload = jose_jwt.decode(
            token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm],
            audience="agentchains-marketplace", issuer="agentchains",
        )
        assert payload["type"] == "stream_agent"
        assert payload["sub_type"] == "agent"

    def test_stream_admin_topics(self) -> None:
        token = create_stream_token("admin-1", token_type="stream_admin")
        payload = jose_jwt.decode(
            token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm],
            audience="agentchains-marketplace", issuer="agentchains",
        )
        assert payload["type"] == "stream_admin"
        assert payload["sub_type"] == "admin"
        assert "private.admin" in payload["allowed_topics"]
        assert "public.market" in payload["allowed_topics"]

    def test_stream_user_topics(self) -> None:
        token = create_stream_token("user-1", token_type="stream_user")
        payload = jose_jwt.decode(
            token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm],
            audience="agentchains-marketplace", issuer="agentchains",
        )
        assert payload["type"] == "stream_user"
        assert payload["sub_type"] == "user"
        assert "private.user" in payload["allowed_topics"]

    def test_stream_a2ui_topics(self) -> None:
        token = create_stream_token("agent-2", token_type="stream_a2ui")
        payload = jose_jwt.decode(
            token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm],
            audience="agentchains-marketplace", issuer="agentchains",
        )
        assert payload["type"] == "stream_a2ui"
        assert payload["sub_type"] == "agent"
        assert payload["allowed_topics"] == ["a2ui.session"]

    def test_custom_allowed_topics_override(self) -> None:
        custom = ["custom.topic1", "custom.topic2"]
        token = create_stream_token("a-1", allowed_topics=custom)
        payload = jose_jwt.decode(
            token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm],
            audience="agentchains-marketplace", issuer="agentchains",
        )
        assert payload["allowed_topics"] == custom

    def test_default_agent_stream_topics(self) -> None:
        token = create_stream_token("a-1", token_type="stream_agent")
        payload = jose_jwt.decode(
            token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm],
            audience="agentchains-marketplace", issuer="agentchains",
        )
        assert "public.market" in payload["allowed_topics"]
        assert "private.agent" in payload["allowed_topics"]


# ---------------------------------------------------------------------------
# decode_token
# ---------------------------------------------------------------------------


class TestDecodeToken:
    """Standard API token decode and validation."""

    def test_decode_valid_agent_token(self) -> None:
        token = create_access_token("agent-99", "test-agent")
        payload = decode_token(token)
        assert payload["sub"] == "agent-99"
        assert payload["name"] == "test-agent"

    def test_rejects_creator_token(self) -> None:
        from marketplace.core.creator_auth import create_creator_token

        token = create_creator_token("creator-1", "c@example.com")
        with pytest.raises(UnauthorizedError, match="Creator tokens cannot be used"):
            decode_token(token)

    def test_rejects_stream_agent_token(self) -> None:
        token = create_stream_token("a-1", token_type="stream_agent")
        with pytest.raises(UnauthorizedError, match="Stream tokens cannot be used"):
            decode_token(token)

    def test_rejects_stream_admin_token(self) -> None:
        token = create_stream_token("admin-1", token_type="stream_admin")
        with pytest.raises(UnauthorizedError, match="Stream tokens cannot be used"):
            decode_token(token)

    def test_rejects_stream_a2ui_token(self) -> None:
        token = create_stream_token("a-1", token_type="stream_a2ui")
        with pytest.raises(UnauthorizedError, match="Stream tokens cannot be used"):
            decode_token(token)

    def test_rejects_expired_token(self) -> None:
        payload = {
            "sub": "agent-expired",
            "name": "expired-bot",
            "aud": "agentchains-marketplace",
            "iss": "agentchains",
            "exp": datetime.now(timezone.utc) - timedelta(hours=1),
            "iat": datetime.now(timezone.utc) - timedelta(hours=2),
        }
        token = jose_jwt.encode(
            payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm
        )
        with pytest.raises(UnauthorizedError, match="Invalid or expired token"):
            decode_token(token)

    def test_rejects_token_without_subject(self) -> None:
        payload = {
            "name": "no-sub",
            "aud": "agentchains-marketplace",
            "iss": "agentchains",
            "exp": datetime.now(timezone.utc) + timedelta(hours=1),
            "iat": datetime.now(timezone.utc),
        }
        token = jose_jwt.encode(
            payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm
        )
        with pytest.raises(UnauthorizedError, match="Token missing subject"):
            decode_token(token)

    def test_rejects_garbage_token(self) -> None:
        with pytest.raises(UnauthorizedError, match="Invalid or expired token"):
            decode_token("not.a.jwt")

    def test_rejects_user_type_token(self) -> None:
        """Tokens with type='user' should be rejected for agent endpoints."""
        payload = {
            "sub": "user-1",
            "type": "user",
            "aud": "agentchains-marketplace",
            "iss": "agentchains",
            "exp": datetime.now(timezone.utc) + timedelta(hours=1),
            "iat": datetime.now(timezone.utc),
        }
        token = jose_jwt.encode(
            payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm
        )
        with pytest.raises(UnauthorizedError, match="User tokens cannot be used"):
            decode_token(token)


# ---------------------------------------------------------------------------
# decode_stream_token
# ---------------------------------------------------------------------------


class TestDecodeStreamToken:
    """WebSocket stream token decode and validation."""

    def test_decode_valid_stream_agent_token(self) -> None:
        token = create_stream_token("a-1", token_type="stream_agent")
        payload = decode_stream_token(token)
        assert payload["sub"] == "a-1"
        assert payload["type"] == "stream_agent"

    def test_decode_valid_stream_admin_token(self) -> None:
        token = create_stream_token("admin-1", token_type="stream_admin")
        payload = decode_stream_token(token)
        assert payload["sub"] == "admin-1"

    def test_decode_valid_stream_user_token(self) -> None:
        token = create_stream_token("user-1", token_type="stream_user")
        payload = decode_stream_token(token)
        assert payload["sub_type"] == "user"

    def test_decode_valid_stream_a2ui_token(self) -> None:
        token = create_stream_token("a-1", token_type="stream_a2ui")
        payload = decode_stream_token(token)
        assert payload["type"] == "stream_a2ui"

    def test_rejects_agent_access_token(self) -> None:
        token = create_access_token("a-1", "bot")
        with pytest.raises(UnauthorizedError, match="Stream token required"):
            decode_stream_token(token)

    def test_rejects_creator_token(self) -> None:
        from marketplace.core.creator_auth import create_creator_token

        token = create_creator_token("c-1", "c@example.com")
        with pytest.raises(UnauthorizedError, match="Stream token required"):
            decode_stream_token(token)

    def test_rejects_expired_stream_token(self) -> None:
        payload = {
            "sub": "a-1",
            "type": "stream_agent",
            "sub_type": "agent",
            "allowed_topics": ["public.market"],
            "aud": "agentchains-marketplace",
            "iss": "agentchains",
            "exp": datetime.now(timezone.utc) - timedelta(minutes=5),
            "iat": datetime.now(timezone.utc) - timedelta(minutes=35),
        }
        token = jose_jwt.encode(
            payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm
        )
        with pytest.raises(UnauthorizedError, match="Invalid or expired token"):
            decode_stream_token(token)

    def test_rejects_stream_token_without_subject(self) -> None:
        payload = {
            "type": "stream_agent",
            "sub_type": "agent",
            "allowed_topics": ["public.market"],
            "aud": "agentchains-marketplace",
            "iss": "agentchains",
            "exp": datetime.now(timezone.utc) + timedelta(minutes=30),
            "iat": datetime.now(timezone.utc),
        }
        token = jose_jwt.encode(
            payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm
        )
        with pytest.raises(UnauthorizedError, match="Token missing subject"):
            decode_stream_token(token)


# ---------------------------------------------------------------------------
# get_current_agent_id
# ---------------------------------------------------------------------------


class TestGetCurrentAgentId:
    """FastAPI dependency — extract agent_id from Authorization header."""

    def test_valid_bearer_token_returns_agent_id(self) -> None:
        token = create_access_token("agent-123", "bot")
        result = get_current_agent_id(f"Bearer {token}")
        assert result == "agent-123"

    def test_missing_header_raises(self) -> None:
        with pytest.raises(UnauthorizedError, match="Missing Authorization"):
            get_current_agent_id(None)

    def test_empty_header_raises(self) -> None:
        with pytest.raises(UnauthorizedError, match="Missing Authorization"):
            get_current_agent_id("")

    def test_no_bearer_prefix_raises(self) -> None:
        token = create_access_token("a-1", "bot")
        with pytest.raises(UnauthorizedError, match="Bearer"):
            get_current_agent_id(token)

    def test_extra_parts_raises(self) -> None:
        with pytest.raises(UnauthorizedError, match="Bearer"):
            get_current_agent_id("Bearer token extra junk")

    def test_basic_auth_rejected(self) -> None:
        with pytest.raises(UnauthorizedError, match="Bearer"):
            get_current_agent_id("Basic dXNlcjpwYXNz")


# ---------------------------------------------------------------------------
# optional_agent_id
# ---------------------------------------------------------------------------


class TestOptionalAgentId:
    """Optional auth dependency — None on missing/invalid."""

    def test_returns_none_for_missing_auth(self) -> None:
        result = optional_agent_id(None)
        assert result is None

    def test_returns_none_for_empty_string(self) -> None:
        result = optional_agent_id("")
        assert result is None

    def test_returns_agent_id_for_valid_token(self) -> None:
        token = create_access_token("agent-opt", "bot")
        result = optional_agent_id(f"Bearer {token}")
        assert result == "agent-opt"

    def test_returns_none_for_invalid_token(self) -> None:
        result = optional_agent_id("Bearer garbage.not.jwt")
        assert result is None

    def test_returns_none_for_creator_token(self) -> None:
        from marketplace.core.creator_auth import create_creator_token

        token = create_creator_token("c-1", "c@example.com")
        result = optional_agent_id(f"Bearer {token}")
        assert result is None
