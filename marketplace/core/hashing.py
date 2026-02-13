"""SHA-256 hash chain utilities for tamper-proof ledger entries."""

import hashlib
from decimal import Decimal

_QUANT = Decimal("0.000001")


def _norm(value) -> str:
    """Normalize a numeric value to 6 decimal places for deterministic hashing."""
    return str(Decimal(str(value)).quantize(_QUANT))


def compute_ledger_hash(
    prev_hash: str | None,
    from_account_id: str | None,
    to_account_id: str | None,
    amount: Decimal,
    fee_amount: Decimal,
    tx_type: str,
    timestamp_iso: str,
) -> str:
    payload = "|".join([
        prev_hash or "GENESIS",
        from_account_id or "MINT",
        to_account_id or "WITHDRAW",
        _norm(amount),
        _norm(fee_amount),
        tx_type,
        timestamp_iso,
    ])
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def compute_audit_hash(
    prev_hash: str | None,
    event_type: str,
    agent_id: str | None,
    details_json: str,
    severity: str,
    timestamp_iso: str,
) -> str:
    payload = "|".join([
        prev_hash or "GENESIS",
        event_type,
        agent_id or "SYSTEM",
        details_json,
        severity,
        timestamp_iso,
    ])
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
