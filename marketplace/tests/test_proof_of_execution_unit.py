"""Unit tests for proof_of_execution_service — JWT proof generation and verification.

Covers generate_proof (valid JWT output), verify_proof (valid, tampered, hash
mismatch), and _hash_params (deterministic hashing).
"""

import uuid

import pytest
from jose import jwt as jose_jwt

from marketplace.config import settings
from marketplace.services.proof_of_execution_service import (
    PROOF_ALGORITHM,
    PROOF_ISSUER,
    _hash_params,
    generate_proof,
    verify_proof,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_ids():
    return str(uuid.uuid4()), str(uuid.uuid4())


def _sample_params():
    return {"query": "laptop", "region": "US"}


def _sample_result():
    return {"status": "success", "items": [{"name": "Laptop", "price": 999.99}]}


# ---------------------------------------------------------------------------
# generate_proof
# ---------------------------------------------------------------------------

class TestGenerateProof:
    """Test proof_of_execution_service.generate_proof."""

    def test_generate_returns_valid_jwt_string(self):
        exec_id, tool_id = _make_ids()
        params = _sample_params()
        result = _sample_result()

        proof = generate_proof(
            execution_id=exec_id,
            tool_id=tool_id,
            parameters=params,
            result=result,
            status="success",
        )

        assert isinstance(proof, str)
        assert len(proof) > 0
        # JWT has three dot-separated parts
        assert proof.count(".") == 2

    def test_generate_proof_contains_expected_claims(self):
        exec_id, tool_id = _make_ids()
        params = _sample_params()
        result = _sample_result()

        proof = generate_proof(
            execution_id=exec_id,
            tool_id=tool_id,
            parameters=params,
            result=result,
            status="success",
        )

        # Decode without verification to inspect claims
        claims = jose_jwt.decode(
            proof,
            settings.jwt_secret_key,
            algorithms=[PROOF_ALGORITHM],
            audience="agentchains-buyer",
        )

        assert claims["iss"] == PROOF_ISSUER
        assert claims["aud"] == "agentchains-buyer"
        assert claims["execution_id"] == exec_id
        assert claims["tool_id"] == tool_id
        assert claims["status"] == "success"
        assert "params_hash" in claims
        assert "result_hash" in claims
        assert "jti" in claims
        assert "iat" in claims
        assert "exp" in claims

    def test_generate_proof_params_hash_matches(self):
        exec_id, tool_id = _make_ids()
        params = _sample_params()
        result = _sample_result()

        proof = generate_proof(
            execution_id=exec_id,
            tool_id=tool_id,
            parameters=params,
            result=result,
        )

        claims = jose_jwt.decode(
            proof,
            settings.jwt_secret_key,
            algorithms=[PROOF_ALGORITHM],
            audience="agentchains-buyer",
        )

        assert claims["params_hash"] == _hash_params(params)

    def test_generate_proof_unique_jti_each_call(self):
        exec_id, tool_id = _make_ids()
        params = _sample_params()
        result = _sample_result()

        proof1 = generate_proof(
            execution_id=exec_id, tool_id=tool_id,
            parameters=params, result=result,
        )
        proof2 = generate_proof(
            execution_id=exec_id, tool_id=tool_id,
            parameters=params, result=result,
        )

        claims1 = jose_jwt.decode(
            proof1, settings.jwt_secret_key,
            algorithms=[PROOF_ALGORITHM], audience="agentchains-buyer",
        )
        claims2 = jose_jwt.decode(
            proof2, settings.jwt_secret_key,
            algorithms=[PROOF_ALGORITHM], audience="agentchains-buyer",
        )

        assert claims1["jti"] != claims2["jti"]


# ---------------------------------------------------------------------------
# verify_proof — valid
# ---------------------------------------------------------------------------

class TestVerifyProofValid:
    """Test verify_proof with valid proofs."""

    def test_valid_proof_returns_valid_true(self):
        exec_id, tool_id = _make_ids()
        params = _sample_params()
        result = _sample_result()

        proof = generate_proof(
            execution_id=exec_id, tool_id=tool_id,
            parameters=params, result=result,
        )

        verification = verify_proof(proof)

        assert verification["valid"] is True
        assert verification["error"] is None
        assert verification["claims"] is not None

    def test_valid_proof_with_matching_params_hash(self):
        exec_id, tool_id = _make_ids()
        params = _sample_params()
        result = _sample_result()

        proof = generate_proof(
            execution_id=exec_id, tool_id=tool_id,
            parameters=params, result=result,
        )

        expected_hash = _hash_params(params)
        verification = verify_proof(proof, expected_params_hash=expected_hash)

        assert verification["valid"] is True
        assert verification["error"] is None


# ---------------------------------------------------------------------------
# verify_proof — tampered
# ---------------------------------------------------------------------------

class TestVerifyProofTampered:
    """Test verify_proof with tampered/invalid JWTs."""

    def test_tampered_jwt_returns_valid_false(self):
        exec_id, tool_id = _make_ids()
        params = _sample_params()
        result = _sample_result()

        proof = generate_proof(
            execution_id=exec_id, tool_id=tool_id,
            parameters=params, result=result,
        )

        # Tamper with the proof by flipping characters in the signature
        parts = proof.split(".")
        # Modify the signature (third part)
        tampered_sig = parts[2][::-1]  # Reverse the signature
        tampered_proof = f"{parts[0]}.{parts[1]}.{tampered_sig}"

        verification = verify_proof(tampered_proof)

        assert verification["valid"] is False
        assert verification["error"] is not None

    def test_completely_invalid_token_returns_valid_false(self):
        verification = verify_proof("not.a.valid.jwt.token")

        assert verification["valid"] is False
        assert verification["error"] is not None

    def test_empty_token_returns_valid_false(self):
        verification = verify_proof("")

        assert verification["valid"] is False
        assert verification["error"] is not None


# ---------------------------------------------------------------------------
# verify_proof — params hash mismatch
# ---------------------------------------------------------------------------

class TestVerifyProofParamsHashMismatch:
    """Test verify_proof when expected_params_hash doesn't match."""

    def test_params_hash_mismatch_returns_valid_false(self):
        exec_id, tool_id = _make_ids()
        params = _sample_params()
        result = _sample_result()

        proof = generate_proof(
            execution_id=exec_id, tool_id=tool_id,
            parameters=params, result=result,
        )

        # Provide a different hash than what was used
        wrong_hash = _hash_params({"query": "different", "region": "UK"})
        verification = verify_proof(proof, expected_params_hash=wrong_hash)

        assert verification["valid"] is False
        assert verification["error"] == "Parameters hash mismatch"
        # Claims should still be decoded even though verification failed
        assert verification["claims"] is not None

    def test_no_expected_hash_skips_hash_check(self):
        exec_id, tool_id = _make_ids()
        params = _sample_params()
        result = _sample_result()

        proof = generate_proof(
            execution_id=exec_id, tool_id=tool_id,
            parameters=params, result=result,
        )

        # Not providing expected_params_hash should skip that check
        verification = verify_proof(proof, expected_params_hash=None)

        assert verification["valid"] is True


# ---------------------------------------------------------------------------
# verify_proof — failed status
# ---------------------------------------------------------------------------

class TestVerifyProofStatus:
    """Test verify_proof checks execution status."""

    def test_failed_status_returns_valid_false(self):
        exec_id, tool_id = _make_ids()
        params = _sample_params()
        result = _sample_result()

        proof = generate_proof(
            execution_id=exec_id, tool_id=tool_id,
            parameters=params, result=result,
            status="failed",
        )

        verification = verify_proof(proof)

        assert verification["valid"] is False
        assert "not success" in verification["error"]


# ---------------------------------------------------------------------------
# _hash_params — deterministic hashing
# ---------------------------------------------------------------------------

class TestHashParams:
    """Test _hash_params determinism and behavior."""

    def test_same_input_same_hash(self):
        params = {"query": "laptop", "region": "US"}

        hash1 = _hash_params(params)
        hash2 = _hash_params(params)

        assert hash1 == hash2

    def test_different_key_order_same_hash(self):
        """sort_keys=True ensures key order doesn't matter."""
        params_a = {"region": "US", "query": "laptop"}
        params_b = {"query": "laptop", "region": "US"}

        assert _hash_params(params_a) == _hash_params(params_b)

    def test_different_input_different_hash(self):
        params_a = {"query": "laptop"}
        params_b = {"query": "tablet"}

        assert _hash_params(params_a) != _hash_params(params_b)

    def test_hash_is_64_char_hex_string(self):
        """SHA-256 produces a 64-character hex digest."""
        h = _hash_params({"key": "value"})

        assert len(h) == 64
        assert all(c in "0123456789abcdef" for c in h)

    def test_empty_dict_produces_consistent_hash(self):
        h1 = _hash_params({})
        h2 = _hash_params({})

        assert h1 == h2
        assert len(h1) == 64

    def test_nested_dict_deterministic(self):
        params = {"outer": {"inner": "value", "count": 42}}

        h1 = _hash_params(params)
        h2 = _hash_params(params)

        assert h1 == h2
