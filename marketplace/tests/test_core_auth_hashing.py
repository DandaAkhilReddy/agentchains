"""Tests for core auth, creator_auth, and hashing modules.

Covers JWT creation/decoding, password hashing, agent/creator auth
dependency functions, and SHA-256 ledger/audit hash utilities.
30 tests total — all pure function tests, no DB fixtures needed.
"""

import hashlib
import time
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from unittest.mock import patch

import pytest
from jose import jwt

from marketplace.config import settings
from marketplace.core.auth import (
    create_access_token,
    decode_token,
    get_current_agent_id,
    optional_agent_id,
)
from marketplace.core.creator_auth import (
    create_creator_token,
    get_current_creator_id,
    hash_password,
    verify_password,
)
from marketplace.core.exceptions import UnauthorizedError
from marketplace.core.hashing import (
    _norm,
    compute_audit_hash,
    compute_ledger_hash,
)


# ===========================================================================
# auth.py — create_access_token
# ===========================================================================


class TestCreateAccessToken:
    def test_create_access_token_returns_string(self):
        """create_access_token should return a non-empty string."""
        token = create_access_token("agent-1", "Agent One")
        assert isinstance(token, str)
        assert len(token) > 0

    def test_create_access_token_has_correct_claims(self):
        """Token payload must contain sub, name, exp, and iat claims."""
        token = create_access_token("agent-42", "Deep Thought")
        payload = jwt.decode(
            token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm]
        )
        assert payload["sub"] == "agent-42"
        assert payload["name"] == "Deep Thought"
        assert "exp" in payload
        assert "iat" in payload

    def test_create_access_token_exp_in_future(self):
        """The exp claim should be in the future (at least hours from now)."""
        token = create_access_token("agent-1", "Test")
        payload = jwt.decode(
            token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm]
        )
        exp_dt = datetime.fromtimestamp(payload["exp"], tz=timezone.utc)
        now = datetime.now(timezone.utc)
        # Should be at least 1 hour in the future (settings default is 7 days)
        assert exp_dt > now + timedelta(hours=1)


# ===========================================================================
# auth.py — decode_token
# ===========================================================================


class TestDecodeToken:
    def test_decode_token_valid(self):
        """decode_token should return the full payload for a valid token."""
        token = create_access_token("agent-7", "Lucky")
        payload = decode_token(token)
        assert payload["sub"] == "agent-7"
        assert payload["name"] == "Lucky"

    def test_decode_token_expired(self):
        """An expired token should raise UnauthorizedError."""
        expired_payload = {
            "sub": "agent-old",
            "name": "Expired",
            "exp": datetime.now(timezone.utc) - timedelta(hours=1),
            "iat": datetime.now(timezone.utc) - timedelta(hours=2),
        }
        token = jwt.encode(
            expired_payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm
        )
        with pytest.raises(UnauthorizedError):
            decode_token(token)

    def test_decode_token_tampered_signature(self):
        """A token signed with a different secret should raise UnauthorizedError."""
        payload = {
            "sub": "agent-hack",
            "name": "Hacker",
            "exp": datetime.now(timezone.utc) + timedelta(hours=1),
            "iat": datetime.now(timezone.utc),
        }
        token = jwt.encode(payload, "wrong-secret-key", algorithm=settings.jwt_algorithm)
        with pytest.raises(UnauthorizedError):
            decode_token(token)

    def test_decode_token_missing_sub(self):
        """A token without a 'sub' claim should raise UnauthorizedError."""
        payload = {
            "name": "NoSubject",
            "exp": datetime.now(timezone.utc) + timedelta(hours=1),
            "iat": datetime.now(timezone.utc),
        }
        token = jwt.encode(
            payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm
        )
        with pytest.raises(UnauthorizedError, match="Token missing subject"):
            decode_token(token)

    def test_decode_token_garbage_input(self):
        """Completely invalid token string should raise UnauthorizedError."""
        with pytest.raises(UnauthorizedError):
            decode_token("this.is.not.a.valid.jwt")


# ===========================================================================
# auth.py — get_current_agent_id
# ===========================================================================


class TestGetCurrentAgentId:
    def test_get_current_agent_id_valid_bearer(self):
        """Should extract agent_id from a valid Bearer token."""
        token = create_access_token("agent-123", "TestBot")
        agent_id = get_current_agent_id(f"Bearer {token}")
        assert agent_id == "agent-123"

    def test_get_current_agent_id_missing_header(self):
        """None authorization header should raise UnauthorizedError."""
        with pytest.raises(UnauthorizedError, match="Missing Authorization header"):
            get_current_agent_id(None)

    def test_get_current_agent_id_no_bearer_prefix(self):
        """Authorization without 'Bearer' prefix should raise UnauthorizedError."""
        token = create_access_token("agent-1", "Bot")
        with pytest.raises(UnauthorizedError, match="Bearer <token>"):
            get_current_agent_id(f"Token {token}")

    def test_get_current_agent_id_three_parts(self):
        """Authorization header with 3 space-separated parts should raise."""
        token = create_access_token("agent-1", "Bot")
        with pytest.raises(UnauthorizedError, match="Bearer <token>"):
            get_current_agent_id(f"Bearer {token} extra")


# ===========================================================================
# auth.py — optional_agent_id
# ===========================================================================


class TestOptionalAgentId:
    def test_optional_agent_id_none_on_missing(self):
        """Should return None when authorization is None."""
        result = optional_agent_id(None)
        assert result is None

    def test_optional_agent_id_none_on_bad_token(self):
        """Should return None for an invalid token instead of raising."""
        result = optional_agent_id("Bearer garbage.token.here")
        assert result is None

    def test_optional_agent_id_returns_id_on_valid(self):
        """Should return the agent_id for a valid Bearer token."""
        token = create_access_token("agent-opt", "Optional")
        result = optional_agent_id(f"Bearer {token}")
        assert result == "agent-opt"


# ===========================================================================
# creator_auth.py — hash_password / verify_password
# ===========================================================================


class TestPasswordHashing:
    def test_hash_password_returns_bcrypt_format(self):
        """Bcrypt hashes start with '$2b$' (or '$2a$') and are ~60 chars."""
        hashed = hash_password("s3cureP@ss")
        assert hashed.startswith("$2b$") or hashed.startswith("$2a$")
        assert len(hashed) == 60

    def test_verify_password_correct(self):
        """verify_password should return True for the correct password."""
        hashed = hash_password("mypassword123")
        assert verify_password("mypassword123", hashed) is True

    def test_verify_password_incorrect(self):
        """verify_password should return False for a wrong password."""
        hashed = hash_password("rightpassword")
        assert verify_password("wrongpassword", hashed) is False


# ===========================================================================
# creator_auth.py — create_creator_token
# ===========================================================================


class TestCreateCreatorToken:
    def test_create_creator_token_has_type_creator(self):
        """Creator token payload must have type='creator'."""
        token = create_creator_token("creator-1", "alice@example.com")
        payload = jwt.decode(
            token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm]
        )
        assert payload["type"] == "creator"

    def test_create_creator_token_has_email(self):
        """Creator token payload must include the email claim."""
        token = create_creator_token("creator-2", "bob@example.com")
        payload = jwt.decode(
            token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm]
        )
        assert payload["email"] == "bob@example.com"

    def test_create_creator_token_has_jti(self):
        """Creator token must include a jti (JWT ID) that is a valid UUID."""
        token = create_creator_token("creator-3", "carol@example.com")
        payload = jwt.decode(
            token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm]
        )
        assert "jti" in payload
        # Validate it is a proper UUID
        uuid.UUID(payload["jti"])  # raises ValueError if invalid


# ===========================================================================
# creator_auth.py — get_current_creator_id
# ===========================================================================


class TestGetCurrentCreatorId:
    def test_get_current_creator_id_valid(self):
        """Should return creator_id from a valid creator Bearer token."""
        token = create_creator_token("creator-99", "valid@test.com")
        creator_id = get_current_creator_id(f"Bearer {token}")
        assert creator_id == "creator-99"

    def test_get_current_creator_id_non_creator_token_raises(self):
        """An agent token (no type=creator) should raise UnauthorizedError."""
        agent_token = create_access_token("agent-1", "NotACreator")
        with pytest.raises(UnauthorizedError, match="Not a creator token"):
            get_current_creator_id(f"Bearer {agent_token}")

    def test_get_current_creator_id_missing_header(self):
        """None authorization should raise UnauthorizedError."""
        with pytest.raises(UnauthorizedError, match="Missing Authorization header"):
            get_current_creator_id(None)


# ===========================================================================
# hashing.py — _norm
# ===========================================================================


class TestNorm:
    def test_norm_decimal_precision(self):
        """_norm should quantize to exactly 6 decimal places."""
        assert _norm(1) == "1.000000"
        assert _norm(3.14) == "3.140000"
        assert _norm(Decimal("0.1234567890")) == "0.123457"  # rounded
        assert _norm("100") == "100.000000"


# ===========================================================================
# hashing.py — compute_ledger_hash
# ===========================================================================


class TestComputeLedgerHash:
    def test_compute_ledger_hash_deterministic(self):
        """Identical inputs must produce the same hash every time."""
        kwargs = dict(
            prev_hash=None,
            from_account_id="acct-A",
            to_account_id="acct-B",
            amount=Decimal("50"),
            fee_amount=Decimal("1"),
            burn_amount=Decimal("0.5"),
            tx_type="purchase",
            timestamp_iso="2026-02-11T12:00:00",
        )
        h1 = compute_ledger_hash(**kwargs)
        h2 = compute_ledger_hash(**kwargs)
        assert h1 == h2
        assert len(h1) == 64  # SHA-256 hex digest length

    def test_compute_ledger_hash_genesis_no_prev(self):
        """When prev_hash is None, 'GENESIS' is used in the payload."""
        h = compute_ledger_hash(
            prev_hash=None,
            from_account_id=None,
            to_account_id="acct-1",
            amount=Decimal("100"),
            fee_amount=Decimal("0"),
            burn_amount=Decimal("0"),
            tx_type="mint",
            timestamp_iso="2026-01-01T00:00:00",
        )
        # Manually reproduce to verify GENESIS and MINT placeholders
        expected_payload = "|".join([
            "GENESIS", "MINT", "acct-1",
            "100.000000", "0.000000", "0.000000",
            "mint", "2026-01-01T00:00:00",
        ])
        expected_hash = hashlib.sha256(expected_payload.encode("utf-8")).hexdigest()
        assert h == expected_hash

    def test_compute_ledger_hash_chain_linking(self):
        """Each hash should depend on the previous, forming a chain."""
        h1 = compute_ledger_hash(
            None, "a", "b", Decimal("10"), Decimal("0"), Decimal("0"), "transfer", "t1"
        )
        h2 = compute_ledger_hash(
            h1, "b", "c", Decimal("5"), Decimal("0"), Decimal("0"), "transfer", "t2"
        )
        # Recompute h2 with a different prev_hash to prove chain dependency
        h2_alt = compute_ledger_hash(
            "0000000000000000000000000000000000000000000000000000000000000000",
            "b", "c", Decimal("5"), Decimal("0"), Decimal("0"), "transfer", "t2",
        )
        assert h2 != h2_alt  # different prev_hash -> different result


# ===========================================================================
# hashing.py — compute_audit_hash
# ===========================================================================


class TestComputeAuditHash:
    def test_compute_audit_hash_deterministic(self):
        """Identical inputs must produce the same audit hash."""
        kwargs = dict(
            prev_hash="abc123",
            event_type="login",
            agent_id="agent-1",
            details_json='{"ip":"127.0.0.1"}',
            severity="info",
            timestamp_iso="2026-02-11T08:00:00",
        )
        h1 = compute_audit_hash(**kwargs)
        h2 = compute_audit_hash(**kwargs)
        assert h1 == h2
        assert len(h1) == 64

    def test_compute_audit_hash_system_agent_none(self):
        """When agent_id is None, 'SYSTEM' should be used in the payload."""
        h = compute_audit_hash(
            prev_hash=None,
            event_type="startup",
            agent_id=None,
            details_json="{}",
            severity="info",
            timestamp_iso="2026-01-01T00:00:00",
        )
        # Manually reproduce to verify GENESIS and SYSTEM placeholders
        expected_payload = "|".join([
            "GENESIS", "startup", "SYSTEM", "{}", "info", "2026-01-01T00:00:00",
        ])
        expected_hash = hashlib.sha256(expected_payload.encode("utf-8")).hexdigest()
        assert h == expected_hash
