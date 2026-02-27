"""Tests for marketplace.core.creator_auth — creator password hashing and JWT auth.

Covers:
- hash_password / verify_password: bcrypt round-trip, wrong password rejection
- create_creator_token: JWT payload structure, claims validation
- get_current_creator_id: valid token extraction, error paths (missing header,
  bad format, wrong token type, expired, missing subject)
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from jose import jwt as jose_jwt

from marketplace.config import settings
from marketplace.core.creator_auth import (
    create_creator_token,
    get_current_creator_id,
    hash_password,
    verify_password,
)
from marketplace.core.exceptions import UnauthorizedError


# ---------------------------------------------------------------------------
# Password hashing
# ---------------------------------------------------------------------------


class TestHashPassword:
    """bcrypt hashing and verification."""

    def test_hash_is_not_plaintext(self) -> None:
        hashed = hash_password("mysecretpassword")
        assert hashed != "mysecretpassword"
        assert hashed.startswith("$2")  # bcrypt prefix

    def test_verify_correct_password(self) -> None:
        hashed = hash_password("correct-horse-battery-staple")
        assert verify_password("correct-horse-battery-staple", hashed) is True

    def test_verify_wrong_password(self) -> None:
        hashed = hash_password("correct-horse-battery-staple")
        assert verify_password("wrong-password", hashed) is False

    def test_different_hashes_for_same_password(self) -> None:
        """bcrypt generates a random salt each time."""
        h1 = hash_password("same-password")
        h2 = hash_password("same-password")
        assert h1 != h2  # different salts
        assert verify_password("same-password", h1) is True
        assert verify_password("same-password", h2) is True

    def test_empty_password_hashes_without_error(self) -> None:
        hashed = hash_password("")
        assert verify_password("", hashed) is True
        assert verify_password("not-empty", hashed) is False

    def test_unicode_password(self) -> None:
        hashed = hash_password("p@$$w0rd-\u00fc\u00f1\u00ee\u00e7\u00f8\u00f0\u00e9")
        assert verify_password("p@$$w0rd-\u00fc\u00f1\u00ee\u00e7\u00f8\u00f0\u00e9", hashed) is True


# ---------------------------------------------------------------------------
# create_creator_token
# ---------------------------------------------------------------------------


class TestCreateCreatorToken:
    """JWT generation for creators."""

    def test_token_is_decodable(self) -> None:
        token = create_creator_token("creator-123", "alice@example.com")
        payload = jose_jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
            audience="agentchains-marketplace",
            issuer="agentchains",
        )
        assert payload["sub"] == "creator-123"
        assert payload["email"] == "alice@example.com"

    def test_token_has_creator_type(self) -> None:
        token = create_creator_token("c-1", "a@b.com")
        payload = jose_jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
            audience="agentchains-marketplace",
            issuer="agentchains",
        )
        assert payload["type"] == "creator"

    def test_token_has_jti_claim(self) -> None:
        token = create_creator_token("c-1", "a@b.com")
        payload = jose_jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
            audience="agentchains-marketplace",
            issuer="agentchains",
        )
        # jti should be a valid UUID
        uuid.UUID(payload["jti"])

    def test_token_has_correct_audience(self) -> None:
        token = create_creator_token("c-1", "a@b.com")
        payload = jose_jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
            audience="agentchains-marketplace",
            issuer="agentchains",
        )
        assert payload["aud"] == "agentchains-marketplace"

    def test_token_has_correct_issuer(self) -> None:
        token = create_creator_token("c-1", "a@b.com")
        payload = jose_jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
            audience="agentchains-marketplace",
            issuer="agentchains",
        )
        assert payload["iss"] == "agentchains"

    def test_token_has_expiration(self) -> None:
        token = create_creator_token("c-1", "a@b.com")
        payload = jose_jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
            audience="agentchains-marketplace",
            issuer="agentchains",
        )
        assert "exp" in payload
        assert "iat" in payload

    def test_two_tokens_have_different_jti(self) -> None:
        t1 = create_creator_token("c-1", "a@b.com")
        t2 = create_creator_token("c-1", "a@b.com")
        p1 = jose_jwt.decode(
            t1, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm],
            audience="agentchains-marketplace", issuer="agentchains",
        )
        p2 = jose_jwt.decode(
            t2, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm],
            audience="agentchains-marketplace", issuer="agentchains",
        )
        assert p1["jti"] != p2["jti"]


# ---------------------------------------------------------------------------
# get_current_creator_id
# ---------------------------------------------------------------------------


class TestGetCurrentCreatorId:
    """Token extraction from Authorization header."""

    def test_valid_token_returns_creator_id(self) -> None:
        token = create_creator_token("creator-abc", "test@example.com")
        result = get_current_creator_id(f"Bearer {token}")
        assert result == "creator-abc"

    def test_missing_authorization_raises(self) -> None:
        with pytest.raises(UnauthorizedError, match="Missing Authorization"):
            get_current_creator_id(None)

    def test_empty_authorization_raises(self) -> None:
        with pytest.raises(UnauthorizedError, match="Missing Authorization"):
            get_current_creator_id("")

    def test_no_bearer_prefix_raises(self) -> None:
        token = create_creator_token("c-1", "a@b.com")
        with pytest.raises(UnauthorizedError, match="Bearer"):
            get_current_creator_id(token)  # missing "Bearer " prefix

    def test_malformed_header_raises(self) -> None:
        with pytest.raises(UnauthorizedError, match="Bearer"):
            get_current_creator_id("Basic dXNlcjpwYXNz")

    def test_extra_parts_in_header_raises(self) -> None:
        with pytest.raises(UnauthorizedError, match="Bearer"):
            get_current_creator_id("Bearer token extra-garbage")

    def test_agent_token_rejected(self) -> None:
        """Agent tokens (no 'type: creator') must be rejected."""
        from marketplace.core.auth import create_access_token

        agent_token = create_access_token("agent-1", "test-agent")
        with pytest.raises(UnauthorizedError, match="Not a creator token"):
            get_current_creator_id(f"Bearer {agent_token}")

    def test_expired_token_raises(self) -> None:
        """Manually craft an expired creator token."""
        payload = {
            "sub": "creator-expired",
            "email": "expired@example.com",
            "type": "creator",
            "jti": str(uuid.uuid4()),
            "aud": "agentchains-marketplace",
            "iss": "agentchains",
            "exp": datetime.now(timezone.utc) - timedelta(hours=1),
            "iat": datetime.now(timezone.utc) - timedelta(hours=2),
        }
        token = jose_jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)
        with pytest.raises(UnauthorizedError, match="Invalid token"):
            get_current_creator_id(f"Bearer {token}")

    def test_wrong_audience_raises(self) -> None:
        payload = {
            "sub": "creator-wrong-aud",
            "email": "wrong@example.com",
            "type": "creator",
            "jti": str(uuid.uuid4()),
            "aud": "wrong-audience",
            "iss": "agentchains",
            "exp": datetime.now(timezone.utc) + timedelta(hours=1),
            "iat": datetime.now(timezone.utc),
        }
        token = jose_jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)
        with pytest.raises(UnauthorizedError, match="Invalid token"):
            get_current_creator_id(f"Bearer {token}")

    def test_missing_subject_raises(self) -> None:
        payload = {
            "email": "nosub@example.com",
            "type": "creator",
            "jti": str(uuid.uuid4()),
            "aud": "agentchains-marketplace",
            "iss": "agentchains",
            "exp": datetime.now(timezone.utc) + timedelta(hours=1),
            "iat": datetime.now(timezone.utc),
        }
        token = jose_jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)
        with pytest.raises(UnauthorizedError, match="Token missing subject"):
            get_current_creator_id(f"Bearer {token}")

    def test_garbage_token_raises(self) -> None:
        with pytest.raises(UnauthorizedError, match="Invalid token"):
            get_current_creator_id("Bearer not.a.valid.jwt.at.all")
