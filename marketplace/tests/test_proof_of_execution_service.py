"""Tests for proof_of_execution_service — JWT proof generation and verification.

All functions are called directly. No mocks — these are pure functions that
operate on JWTs using the application's jwt_secret_key.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from jose import jwt

from marketplace.config import settings
from marketplace.services.proof_of_execution_service import (
    PROOF_ALGORITHM,
    PROOF_EXPIRY_HOURS,
    PROOF_ISSUER,
    _hash_params,
    _hash_result,
    generate_proof,
    verify_proof,
)


# ---------------------------------------------------------------------------
# Hash helpers — pure functions
# ---------------------------------------------------------------------------


class TestHashHelpers:

    def test_hash_params_deterministic(self):
        params = {"b": 2, "a": 1}
        h1 = _hash_params(params)
        h2 = _hash_params({"a": 1, "b": 2})
        assert h1 == h2

    def test_hash_params_returns_sha256_hex(self):
        params = {"key": "value"}
        result = _hash_params(params)
        assert len(result) == 64
        int(result, 16)

    def test_hash_result_deterministic(self):
        result = {"status": "ok", "data": [1, 2]}
        h1 = _hash_result(result)
        h2 = _hash_result({"data": [1, 2], "status": "ok"})
        assert h1 == h2

    def test_hash_params_different_for_different_inputs(self):
        h1 = _hash_params({"a": 1})
        h2 = _hash_params({"a": 2})
        assert h1 != h2

    def test_hash_result_empty_dict(self):
        result = _hash_result({})
        expected = hashlib.sha256(b"{}").hexdigest()
        assert result == expected

    def test_hash_params_nested_dict(self):
        params = {"outer": {"inner": "value"}}
        result = _hash_params(params)
        assert len(result) == 64

    def test_hash_params_with_list_value(self):
        params = {"items": [1, 2, 3]}
        result = _hash_params(params)
        assert len(result) == 64


# ---------------------------------------------------------------------------
# generate_proof — real JWT creation
# ---------------------------------------------------------------------------


class TestGenerateProof:

    def test_returns_valid_jwt_string(self):
        token = generate_proof(
            execution_id="exec-1",
            tool_id="tool-1",
            parameters={"url": "https://example.com"},
            result={"data": "ok"},
        )
        assert isinstance(token, str)
        assert len(token) > 0
        assert token.count(".") == 2

    def test_jwt_contains_expected_claims(self):
        token = generate_proof(
            execution_id="exec-2",
            tool_id="tool-2",
            parameters={"q": "test"},
            result={"answer": 42},
        )
        claims = jwt.decode(
            token, settings.jwt_secret_key,
            algorithms=[PROOF_ALGORITHM],
            audience="agentchains-buyer",
        )
        assert claims["iss"] == PROOF_ISSUER
        assert claims["aud"] == "agentchains-buyer"
        assert claims["execution_id"] == "exec-2"
        assert claims["tool_id"] == "tool-2"
        assert claims["status"] == "success"
        assert "params_hash" in claims
        assert "result_hash" in claims
        assert "jti" in claims
        assert "exp" in claims
        assert "iat" in claims

    def test_params_hash_matches_manual_computation(self):
        params = {"url": "https://test.com", "selector": "div"}
        result = {"data": "content"}
        token = generate_proof("e1", "t1", params, result)
        claims = jwt.decode(
            token, settings.jwt_secret_key,
            algorithms=[PROOF_ALGORITHM],
            audience="agentchains-buyer",
        )
        assert claims["params_hash"] == _hash_params(params)
        assert claims["result_hash"] == _hash_result(result)

    def test_custom_status_is_encoded(self):
        token = generate_proof(
            execution_id="e1", tool_id="t1",
            parameters={}, result={}, status="partial"
        )
        claims = jwt.decode(
            token, settings.jwt_secret_key,
            algorithms=[PROOF_ALGORITHM],
            audience="agentchains-buyer",
        )
        assert claims["status"] == "partial"

    def test_expiry_is_set_correctly(self):
        token = generate_proof("e1", "t1", {}, {})
        claims = jwt.decode(
            token, settings.jwt_secret_key,
            algorithms=[PROOF_ALGORITHM],
            audience="agentchains-buyer",
        )
        iat = claims["iat"]
        exp = claims["exp"]
        diff_hours = (exp - iat) / 3600
        assert abs(diff_hours - PROOF_EXPIRY_HOURS) < 0.01

    def test_each_proof_has_unique_jti(self):
        token1 = generate_proof("e1", "t1", {}, {})
        token2 = generate_proof("e1", "t1", {}, {})
        claims1 = jwt.decode(
            token1, settings.jwt_secret_key,
            algorithms=[PROOF_ALGORITHM], audience="agentchains-buyer",
        )
        claims2 = jwt.decode(
            token2, settings.jwt_secret_key,
            algorithms=[PROOF_ALGORITHM], audience="agentchains-buyer",
        )
        assert claims1["jti"] != claims2["jti"]

    def test_generate_proof_with_complex_params(self):
        params = {"nested": {"list": [1, 2, 3], "dict": {"a": "b"}}}
        result = {"complex": True, "data": [{"x": 1}]}
        token = generate_proof("e1", "t1", params, result)
        claims = jwt.decode(
            token, settings.jwt_secret_key,
            algorithms=[PROOF_ALGORITHM], audience="agentchains-buyer",
        )
        assert claims["params_hash"] == _hash_params(params)
        assert claims["result_hash"] == _hash_result(result)


# ---------------------------------------------------------------------------
# verify_proof — valid proofs
# ---------------------------------------------------------------------------


class TestVerifyProofValid:

    def test_valid_proof_returns_valid_true(self):
        token = generate_proof("e1", "t1", {"a": 1}, {"b": 2})
        result = verify_proof(token)
        assert result["valid"] is True
        assert result["error"] is None
        assert result["claims"]["execution_id"] == "e1"

    def test_valid_proof_with_params_hash_check(self):
        params = {"url": "https://example.com"}
        token = generate_proof("e1", "t1", params, {"ok": True})
        expected_hash = _hash_params(params)
        result = verify_proof(token, expected_params_hash=expected_hash)
        assert result["valid"] is True

    def test_verify_returns_all_claims(self):
        token = generate_proof("e1", "t1", {}, {})
        result = verify_proof(token)
        claims = result["claims"]
        assert "iss" in claims
        assert "aud" in claims
        assert "execution_id" in claims
        assert "tool_id" in claims

    def test_valid_proof_without_params_hash_check(self):
        token = generate_proof("e1", "t1", {"key": "val"}, {"result": "ok"})
        result = verify_proof(token, expected_params_hash=None)
        assert result["valid"] is True


# ---------------------------------------------------------------------------
# verify_proof — invalid proofs
# ---------------------------------------------------------------------------


class TestVerifyProofInvalid:

    def test_tampered_token_fails(self):
        token = generate_proof("e1", "t1", {}, {})
        tampered = token[:-5] + "XXXXX"
        result = verify_proof(tampered)
        assert result["valid"] is False
        assert result["error"] is not None

    def test_wrong_secret_key_fails(self):
        fake_token = jwt.encode(
            {"iss": PROOF_ISSUER, "aud": "agentchains-buyer",
             "execution_id": "e1", "status": "success",
             "exp": datetime.now(timezone.utc) + timedelta(hours=1),
             "iat": datetime.now(timezone.utc)},
            "wrong-secret",
            algorithm=PROOF_ALGORITHM,
        )
        result = verify_proof(fake_token)
        assert result["valid"] is False

    def test_params_hash_mismatch_fails(self):
        params = {"url": "https://example.com"}
        token = generate_proof("e1", "t1", params, {})
        result = verify_proof(token, expected_params_hash="wrong_hash")
        assert result["valid"] is False
        assert "hash mismatch" in result["error"].lower()

    def test_non_success_status_fails(self):
        token = generate_proof("e1", "t1", {}, {}, status="failed")
        result = verify_proof(token)
        assert result["valid"] is False
        assert "status" in result["error"].lower()

    def test_wrong_issuer_fails(self):
        payload = {
            "iss": "wrong-issuer",
            "aud": "agentchains-buyer",
            "execution_id": "e1",
            "status": "success",
            "params_hash": "abc",
            "result_hash": "def",
            "exp": datetime.now(timezone.utc) + timedelta(hours=1),
            "iat": datetime.now(timezone.utc),
        }
        token = jwt.encode(payload, settings.jwt_secret_key, algorithm=PROOF_ALGORITHM)
        result = verify_proof(token)
        assert result["valid"] is False
        assert "issuer" in result["error"].lower()

    def test_expired_token_fails(self):
        payload = {
            "iss": PROOF_ISSUER,
            "aud": "agentchains-buyer",
            "execution_id": "e1",
            "tool_id": "t1",
            "status": "success",
            "params_hash": _hash_params({}),
            "result_hash": _hash_result({}),
            "jti": str(uuid.uuid4()),
            "iat": datetime.now(timezone.utc) - timedelta(hours=2),
            "exp": datetime.now(timezone.utc) - timedelta(hours=1),
        }
        token = jwt.encode(payload, settings.jwt_secret_key, algorithm=PROOF_ALGORITHM)
        result = verify_proof(token)
        assert result["valid"] is False

    def test_wrong_audience_fails(self):
        payload = {
            "iss": PROOF_ISSUER,
            "aud": "wrong-audience",
            "execution_id": "e1",
            "status": "success",
            "exp": datetime.now(timezone.utc) + timedelta(hours=1),
            "iat": datetime.now(timezone.utc),
        }
        token = jwt.encode(payload, settings.jwt_secret_key, algorithm=PROOF_ALGORITHM)
        result = verify_proof(token)
        assert result["valid"] is False

    def test_empty_string_token_fails(self):
        result = verify_proof("")
        assert result["valid"] is False

    def test_garbage_string_fails(self):
        result = verify_proof("not.a.jwt.at.all")
        assert result["valid"] is False


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------


class TestConstants:

    def test_proof_algorithm_is_hs256(self):
        assert PROOF_ALGORITHM == "HS256"

    def test_proof_issuer_value(self):
        assert PROOF_ISSUER == "agentchains-marketplace"

    def test_proof_expiry_is_30_days(self):
        assert PROOF_EXPIRY_HOURS == 720
