"""Proof-of-Execution Service: JWT-based proof generation and verification."""

import hashlib
import json
import logging
import uuid
from datetime import datetime, timedelta, timezone

from jose import JWTError, jwt

from marketplace.config import settings

logger = logging.getLogger(__name__)

# Use HS256 with the platform secret for proof signing
# In production, tools would use RS256 with their own keys
PROOF_ALGORITHM = "HS256"
PROOF_ISSUER = "agentchains-marketplace"
PROOF_EXPIRY_HOURS = 720  # 30 days — proofs are long-lived receipts


def _hash_params(parameters: dict) -> str:
    """SHA-256 hash of canonicalized parameters."""
    canonical = json.dumps(parameters, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode()).hexdigest()


def _hash_result(result: dict) -> str:
    """SHA-256 hash of canonicalized result."""
    canonical = json.dumps(result, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode()).hexdigest()


def generate_proof(
    execution_id: str,
    tool_id: str,
    parameters: dict,
    result: dict,
    status: str = "success",
) -> str:
    """Generate a JWT proof-of-execution.

    The proof contains hashes of parameters and result so the buyer
    can verify that the execution was performed with the expected inputs
    and produced the claimed outputs.
    """
    now = datetime.now(timezone.utc)
    payload = {
        "iss": PROOF_ISSUER,
        "aud": "agentchains-buyer",
        "iat": now,
        "exp": now + timedelta(hours=PROOF_EXPIRY_HOURS),
        "jti": str(uuid.uuid4()),
        "execution_id": execution_id,
        "tool_id": tool_id,
        "params_hash": _hash_params(parameters),
        "result_hash": _hash_result(result),
        "status": status,
    }

    token = jwt.encode(payload, settings.jwt_secret_key, algorithm=PROOF_ALGORITHM)
    logger.info("Proof generated for execution %s", execution_id)
    return token


def verify_proof(
    proof_jwt: str,
    expected_params_hash: str | None = None,
) -> dict:
    """Verify a proof-of-execution JWT.

    Returns:
        dict with keys: valid (bool), claims (dict or None), error (str or None)
    """
    try:
        claims = jwt.decode(
            proof_jwt,
            settings.jwt_secret_key,
            algorithms=[PROOF_ALGORITHM],
            audience="agentchains-buyer",
        )
    except JWTError as e:
        logger.warning("Proof verification failed: %s", e)
        return {"valid": False, "claims": None, "error": str(e)}

    # Verify issuer
    if claims.get("iss") != PROOF_ISSUER:
        return {"valid": False, "claims": claims, "error": "Invalid issuer"}

    # Verify params hash if provided
    if expected_params_hash and claims.get("params_hash") != expected_params_hash:
        return {
            "valid": False,
            "claims": claims,
            "error": "Parameters hash mismatch",
        }

    # Verify execution status
    if claims.get("status") != "success":
        return {
            "valid": False,
            "claims": claims,
            "error": f"Execution status is {claims.get('status')}, not success",
        }

    return {"valid": True, "claims": claims, "error": None}
