"""Strict trust verification pipeline for listing provenance and safety."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from marketplace.models.listing import DataListing
from marketplace.models.trust_verification import (
    ArtifactManifest,
    SourceReceipt,
    VerificationJob,
    VerificationResult,
)
from marketplace.services.storage_service import get_storage

TRUST_STATUS_VERIFIED = "verified_secure_data"
TRUST_STATUS_FAILED = "verification_failed"
TRUST_STATUS_PENDING = "pending_verification"

_ALLOWED_SOURCE_PROVIDERS = {
    "firecrawl",
    "serpapi",
    "browserbase",
    "openapi",
    "custom_api",
    "manual_upload",
}

_INJECTION_PATTERNS = (
    "ignore previous instructions",
    "system prompt",
    "<script",
    "javascript:",
    "rm -rf",
    "drop table",
    "prompt injection",
)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _as_utc(value: datetime | None) -> datetime:
    if value is None:
        return _utcnow()
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _safe_json_load(value: Any, fallback: Any) -> Any:
    if value is None:
        return fallback
    if isinstance(value, (dict, list)):
        return value
    if isinstance(value, str):
        try:
            return json.loads(value)
        except Exception:
            return fallback
    return fallback


def _platform_signature(listing_id: str, provider: str, response_hash: str) -> str:
    payload = f"{listing_id}|{provider}|{response_hash}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _schema_fingerprint(metadata: dict[str, Any]) -> str | None:
    schema_obj = metadata.get("schema") or metadata.get("schema_json")
    if not schema_obj:
        return None
    canonical = json.dumps(schema_obj, sort_keys=True, separators=(",", ":"))
    return f"sha256:{hashlib.sha256(canonical.encode('utf-8')).hexdigest()}"


def _contains_injection_risk(content_text: str, metadata: dict[str, Any]) -> bool:
    lowered = content_text.lower()
    metadata_text = json.dumps(metadata, sort_keys=True, default=str).lower()
    return any(pattern in lowered or pattern in metadata_text for pattern in _INJECTION_PATTERNS)


def _compute_trust_status(stage_map: dict[str, bool]) -> tuple[str, int]:
    passed_count = sum(1 for value in stage_map.values() if value)
    score = int((passed_count / 5) * 100)
    if all(stage_map.values()):
        return TRUST_STATUS_VERIFIED, score
    return TRUST_STATUS_FAILED, score


async def _latest_receipt(db: AsyncSession, listing_id: str) -> SourceReceipt | None:
    result = await db.execute(
        select(SourceReceipt)
        .where(SourceReceipt.listing_id == listing_id)
        .order_by(SourceReceipt.created_at.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def _latest_manifest(db: AsyncSession, listing_id: str) -> ArtifactManifest | None:
    result = await db.execute(
        select(ArtifactManifest)
        .where(ArtifactManifest.listing_id == listing_id)
        .order_by(ArtifactManifest.created_at.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def bootstrap_listing_trust_artifacts(
    db: AsyncSession,
    listing: DataListing,
    metadata: dict[str, Any],
) -> None:
    """Create baseline provenance and manifest rows when listing is first published."""
    manifest = ArtifactManifest(
        listing_id=listing.id,
        canonical_hash=listing.content_hash,
        mime_type=listing.content_type,
        content_size=listing.content_size,
        schema_fingerprint=_schema_fingerprint(metadata),
        dependency_chain_json=json.dumps(metadata.get("dependency_chain", [])),
    )
    db.add(manifest)

    provider = str(metadata.get("source_provider") or metadata.get("provider") or "manual_upload")
    source_query = str(metadata.get("source_query") or metadata.get("query") or "")
    response_hash = str(
        metadata.get("source_response_hash")
        or metadata.get("response_hash")
        or listing.content_hash
    )
    seller_signature = str(metadata.get("seller_signature") or "")
    platform_sig = _platform_signature(listing.id, provider, response_hash)

    receipt = SourceReceipt(
        listing_id=listing.id,
        provider=provider,
        source_query=source_query,
        request_payload_json=json.dumps(metadata.get("source_request", {})),
        response_hash=response_hash,
        headers_json=json.dumps(metadata.get("source_headers", {})),
        seller_signature=seller_signature,
        platform_signature=platform_sig,
        fetched_at=_as_utc(listing.freshness_at),
    )
    db.add(receipt)
    await db.flush()


async def run_strict_verification(
    db: AsyncSession,
    listing: DataListing,
    *,
    requested_by: str | None = None,
    trigger_source: str = "manual",
) -> dict[str, Any]:
    """Run strict verification checks and persist result + listing trust state."""
    metadata = _safe_json_load(getattr(listing, "metadata_json", "{}"), {})
    storage = get_storage()
    raw = storage.get(listing.content_hash) or b""
    content_text = raw.decode("utf-8", errors="ignore")

    job = VerificationJob(
        listing_id=listing.id,
        status="running",
        trigger_source=trigger_source,
        requested_by=requested_by,
        started_at=_utcnow(),
    )
    db.add(job)
    await db.flush()

    receipt = await _latest_receipt(db, listing.id)
    manifest = await _latest_manifest(db, listing.id)

    provenance_passed = bool(
        receipt
        and receipt.provider in _ALLOWED_SOURCE_PROVIDERS
        and receipt.source_query.strip()
        and receipt.response_hash.startswith("sha256:")
        and receipt.seller_signature.strip()
        and receipt.platform_signature.strip()
    )

    integrity_passed = bool(
        manifest
        and manifest.canonical_hash == listing.content_hash
        and int(manifest.content_size) == int(listing.content_size)
    )

    safety_passed = not _contains_injection_risk(content_text, metadata)

    expected_repro_hash = str(metadata.get("reproducibility_hash") or metadata.get("source_response_hash") or "")
    reproducibility_passed = bool(
        expected_repro_hash
        and expected_repro_hash.startswith("sha256:")
        and expected_repro_hash == listing.content_hash
    )

    ttl_hours = int(metadata.get("freshness_ttl_hours", 24))
    freshness_deadline = _as_utc(listing.freshness_at) + timedelta(hours=ttl_hours)
    provider_ok = bool(receipt and receipt.provider in _ALLOWED_SOURCE_PROVIDERS)
    metadata_required = all(key in metadata for key in ("source_provider", "source_query"))
    policy_passed = provider_ok and metadata_required and _utcnow() <= freshness_deadline

    stages = {
        "provenance": provenance_passed,
        "integrity": integrity_passed,
        "safety": safety_passed,
        "reproducibility": reproducibility_passed,
        "policy": policy_passed,
    }
    trust_status, trust_score = _compute_trust_status(stages)

    evidence = {
        "stages": stages,
        "job_id": job.id,
        "listing_id": listing.id,
        "evaluated_at": _utcnow().isoformat(),
        "provider": receipt.provider if receipt else None,
        "receipt_id": receipt.id if receipt else None,
        "manifest_id": manifest.id if manifest else None,
        "reproducibility_expected_hash": expected_repro_hash or None,
    }

    result = VerificationResult(
        job_id=job.id,
        listing_id=listing.id,
        passed=(trust_status == TRUST_STATUS_VERIFIED),
        trust_score=trust_score,
        provenance_passed=provenance_passed,
        integrity_passed=integrity_passed,
        safety_passed=safety_passed,
        reproducibility_passed=reproducibility_passed,
        policy_passed=policy_passed,
        evidence_json=json.dumps(evidence),
    )
    db.add(result)

    listing.trust_status = trust_status
    listing.trust_score = trust_score
    listing.verification_summary_json = json.dumps(
        {
            "status": trust_status,
            "score": trust_score,
            "stages": stages,
            "job_id": job.id,
        }
    )
    listing.provenance_json = json.dumps(
        {
            "source": receipt.provider if receipt else None,
            "fetched_at": _as_utc(receipt.fetched_at).isoformat() if receipt else None,
            "receipt_id": receipt.id if receipt else None,
            "reproducibility_state": "passed" if reproducibility_passed else "failed",
        }
    )
    listing.verification_updated_at = _utcnow()

    job.status = "completed" if trust_status == TRUST_STATUS_VERIFIED else "failed"
    job.stage_status_json = json.dumps(stages)
    job.failure_reason = None if trust_status == TRUST_STATUS_VERIFIED else "One or more strict checks failed"
    job.completed_at = _utcnow()

    await db.commit()
    await db.refresh(listing)
    await db.refresh(job)

    return {
        "listing_id": listing.id,
        "trust_status": trust_status,
        "trust_score": trust_score,
        "verification_summary": _safe_json_load(listing.verification_summary_json, {}),
        "provenance": _safe_json_load(listing.provenance_json, {}),
        "job_id": job.id,
    }


async def run_strict_verification_by_listing_id(
    db: AsyncSession,
    listing_id: str,
    *,
    requested_by: str | None = None,
    trigger_source: str = "manual",
) -> dict[str, Any]:
    result = await db.execute(select(DataListing).where(DataListing.id == listing_id))
    listing = result.scalar_one_or_none()
    if listing is None:
        raise ValueError(f"Listing {listing_id} not found")
    return await run_strict_verification(
        db,
        listing,
        requested_by=requested_by,
        trigger_source=trigger_source,
    )


async def add_source_receipt(
    db: AsyncSession,
    *,
    listing_id: str,
    provider: str,
    source_query: str,
    seller_signature: str,
    response_hash: str | None = None,
    request_payload: dict[str, Any] | None = None,
    headers: dict[str, Any] | None = None,
) -> SourceReceipt:
    result = await db.execute(select(DataListing).where(DataListing.id == listing_id))
    listing = result.scalar_one_or_none()
    if listing is None:
        raise ValueError(f"Listing {listing_id} not found")

    normalized_hash = response_hash or listing.content_hash
    receipt = SourceReceipt(
        listing_id=listing_id,
        provider=provider,
        source_query=source_query,
        request_payload_json=json.dumps(request_payload or {}),
        response_hash=normalized_hash,
        headers_json=json.dumps(headers or {}),
        seller_signature=seller_signature,
        platform_signature=_platform_signature(listing_id, provider, normalized_hash),
        fetched_at=_as_utc(listing.freshness_at),
    )
    db.add(receipt)

    manifest = await _latest_manifest(db, listing_id)
    if manifest is None:
        db.add(
            ArtifactManifest(
                listing_id=listing_id,
                canonical_hash=listing.content_hash,
                mime_type=listing.content_type,
                content_size=listing.content_size,
                schema_fingerprint=_schema_fingerprint(
                    _safe_json_load(getattr(listing, "metadata_json", "{}"), {})
                ),
                dependency_chain_json="[]",
            )
        )

    await db.commit()
    await db.refresh(receipt)
    return receipt


def build_trust_payload(listing: DataListing) -> dict[str, Any]:
    return {
        "trust_status": getattr(listing, "trust_status", TRUST_STATUS_PENDING) or TRUST_STATUS_PENDING,
        "trust_score": int(getattr(listing, "trust_score", 0) or 0),
        "verification_summary": _safe_json_load(
            getattr(listing, "verification_summary_json", "{}"), {}
        ),
        "provenance": _safe_json_load(getattr(listing, "provenance_json", "{}"), {}),
    }
