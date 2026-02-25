"""Tests for trust verification models: SourceReceipt, ArtifactManifest, VerificationJob, VerificationResult.

Uses the db fixture from conftest for real SQLite persistence.
"""

import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy import select

from marketplace.models.trust_verification import (
    ArtifactManifest,
    SourceReceipt,
    VerificationJob,
    VerificationResult,
    utcnow,
)


def _uid() -> str:
    return str(uuid.uuid4())


# ---------------------------------------------------------------------------
# SourceReceipt
# ---------------------------------------------------------------------------


class TestSourceReceiptModel:
    async def test_create_source_receipt(self, db, make_agent, make_listing):
        agent, _ = await make_agent()
        listing = await make_listing(seller_id=agent.id)

        receipt = SourceReceipt(
            id=_uid(),
            listing_id=listing.id,
            provider="serp_api",
            source_query="python tutorial",
            response_hash="sha256:" + "a" * 64,
            seller_signature="sig-seller-" + "x" * 50,
            platform_signature="sig-platform-" + "y" * 50,
        )
        db.add(receipt)
        await db.commit()
        await db.refresh(receipt)

        assert receipt.provider == "serp_api"
        assert receipt.source_query == "python tutorial"
        assert receipt.created_at is not None
        assert receipt.fetched_at is not None

    async def test_source_receipt_defaults(self, db, make_agent, make_listing):
        agent, _ = await make_agent()
        listing = await make_listing(seller_id=agent.id)

        receipt = SourceReceipt(
            id=_uid(),
            listing_id=listing.id,
            provider="google",
            source_query="test",
            response_hash="sha256:" + "b" * 64,
            seller_signature="sig1",
            platform_signature="sig2",
        )
        db.add(receipt)
        await db.commit()
        await db.refresh(receipt)

        assert receipt.request_payload_json == "{}"
        assert receipt.headers_json == "{}"

    async def test_source_receipt_with_custom_payload(self, db, make_agent, make_listing):
        agent, _ = await make_agent()
        listing = await make_listing(seller_id=agent.id)

        receipt = SourceReceipt(
            id=_uid(),
            listing_id=listing.id,
            provider="custom_api",
            source_query="query",
            response_hash="sha256:" + "c" * 64,
            seller_signature="s",
            platform_signature="p",
            request_payload_json='{"q": "test", "limit": 10}',
            headers_json='{"Content-Type": "application/json"}',
        )
        db.add(receipt)
        await db.commit()
        await db.refresh(receipt)

        assert '"q": "test"' in receipt.request_payload_json

    async def test_query_receipts_by_listing(self, db, make_agent, make_listing):
        agent, _ = await make_agent()
        listing = await make_listing(seller_id=agent.id)

        for i in range(3):
            receipt = SourceReceipt(
                id=_uid(),
                listing_id=listing.id,
                provider=f"provider_{i}",
                source_query=f"query_{i}",
                response_hash="sha256:" + f"{i}" * 64,
                seller_signature="s",
                platform_signature="p",
            )
            db.add(receipt)
        await db.commit()

        result = await db.execute(
            select(SourceReceipt).where(SourceReceipt.listing_id == listing.id)
        )
        receipts = list(result.scalars().all())
        assert len(receipts) == 3


# ---------------------------------------------------------------------------
# ArtifactManifest
# ---------------------------------------------------------------------------


class TestArtifactManifestModel:
    async def test_create_artifact_manifest(self, db, make_agent, make_listing):
        agent, _ = await make_agent()
        listing = await make_listing(seller_id=agent.id)

        manifest = ArtifactManifest(
            id=_uid(),
            listing_id=listing.id,
            canonical_hash="sha256:" + "d" * 64,
            mime_type="application/json",
            content_size=1024,
        )
        db.add(manifest)
        await db.commit()
        await db.refresh(manifest)

        assert manifest.mime_type == "application/json"
        assert manifest.content_size == 1024
        assert manifest.created_at is not None

    async def test_manifest_defaults(self, db, make_agent, make_listing):
        agent, _ = await make_agent()
        listing = await make_listing(seller_id=agent.id)

        manifest = ArtifactManifest(
            id=_uid(),
            listing_id=listing.id,
            canonical_hash="sha256:" + "e" * 64,
            mime_type="text/plain",
            content_size=256,
        )
        db.add(manifest)
        await db.commit()
        await db.refresh(manifest)

        assert manifest.schema_fingerprint is None
        assert manifest.dependency_chain_json == "[]"

    async def test_manifest_with_schema_fingerprint(self, db, make_agent, make_listing):
        agent, _ = await make_agent()
        listing = await make_listing(seller_id=agent.id)

        manifest = ArtifactManifest(
            id=_uid(),
            listing_id=listing.id,
            canonical_hash="sha256:" + "f" * 64,
            mime_type="application/json",
            content_size=512,
            schema_fingerprint="sha256:" + "1" * 64,
            dependency_chain_json='["sha256:aaa", "sha256:bbb"]',
        )
        db.add(manifest)
        await db.commit()
        await db.refresh(manifest)

        assert manifest.schema_fingerprint is not None
        assert "aaa" in manifest.dependency_chain_json

    async def test_query_by_canonical_hash(self, db, make_agent, make_listing):
        agent, _ = await make_agent()
        listing = await make_listing(seller_id=agent.id)
        target_hash = "sha256:" + "9" * 64

        manifest = ArtifactManifest(
            id=_uid(),
            listing_id=listing.id,
            canonical_hash=target_hash,
            mime_type="text/plain",
            content_size=100,
        )
        db.add(manifest)
        await db.commit()

        result = await db.execute(
            select(ArtifactManifest).where(ArtifactManifest.canonical_hash == target_hash)
        )
        found = result.scalar_one()
        assert found.id == manifest.id


# ---------------------------------------------------------------------------
# VerificationJob
# ---------------------------------------------------------------------------


class TestVerificationJobModel:
    async def test_create_job_with_defaults(self, db, make_agent, make_listing):
        agent, _ = await make_agent()
        listing = await make_listing(seller_id=agent.id)

        job = VerificationJob(
            id=_uid(),
            listing_id=listing.id,
        )
        db.add(job)
        await db.commit()
        await db.refresh(job)

        assert job.status == "pending"
        assert job.trigger_source == "listing_create"
        assert job.requested_by is None
        assert job.stage_status_json == "{}"
        assert job.failure_reason is None
        assert job.started_at is None
        assert job.completed_at is None

    async def test_job_status_transitions(self, db, make_agent, make_listing):
        agent, _ = await make_agent()
        listing = await make_listing(seller_id=agent.id)

        job = VerificationJob(
            id=_uid(),
            listing_id=listing.id,
            status="pending",
        )
        db.add(job)
        await db.commit()

        # Transition to running
        job.status = "running"
        job.started_at = datetime.now(timezone.utc)
        await db.commit()
        await db.refresh(job)
        assert job.status == "running"
        assert job.started_at is not None

        # Transition to completed
        job.status = "completed"
        job.completed_at = datetime.now(timezone.utc)
        await db.commit()
        await db.refresh(job)
        assert job.status == "completed"

    async def test_job_failure(self, db, make_agent, make_listing):
        agent, _ = await make_agent()
        listing = await make_listing(seller_id=agent.id)

        job = VerificationJob(
            id=_uid(),
            listing_id=listing.id,
            status="failed",
            failure_reason="Provenance check failed: source not reachable",
        )
        db.add(job)
        await db.commit()
        await db.refresh(job)

        assert job.status == "failed"
        assert "Provenance check failed" in job.failure_reason

    async def test_query_jobs_by_status(self, db, make_agent, make_listing):
        agent, _ = await make_agent()
        listing = await make_listing(seller_id=agent.id)

        for status in ("pending", "running", "completed", "failed"):
            job = VerificationJob(
                id=_uid(),
                listing_id=listing.id,
                status=status,
            )
            db.add(job)
        await db.commit()

        result = await db.execute(
            select(VerificationJob).where(VerificationJob.status == "pending")
        )
        pending = list(result.scalars().all())
        assert len(pending) == 1


# ---------------------------------------------------------------------------
# VerificationResult
# ---------------------------------------------------------------------------


class TestVerificationResultModel:
    async def test_create_passing_result(self, db, make_agent, make_listing):
        agent, _ = await make_agent()
        listing = await make_listing(seller_id=agent.id)

        job = VerificationJob(id=_uid(), listing_id=listing.id, status="completed")
        db.add(job)
        await db.commit()

        result = VerificationResult(
            id=_uid(),
            job_id=job.id,
            listing_id=listing.id,
            passed=True,
            trust_score=95,
            provenance_passed=True,
            integrity_passed=True,
            safety_passed=True,
            reproducibility_passed=True,
            policy_passed=True,
        )
        db.add(result)
        await db.commit()
        await db.refresh(result)

        assert result.passed is True
        assert result.trust_score == 95
        assert result.provenance_passed is True
        assert result.integrity_passed is True
        assert result.safety_passed is True
        assert result.reproducibility_passed is True
        assert result.policy_passed is True

    async def test_create_failing_result(self, db, make_agent, make_listing):
        agent, _ = await make_agent()
        listing = await make_listing(seller_id=agent.id)

        job = VerificationJob(id=_uid(), listing_id=listing.id, status="completed")
        db.add(job)
        await db.commit()

        result = VerificationResult(
            id=_uid(),
            job_id=job.id,
            listing_id=listing.id,
            passed=False,
            trust_score=30,
            provenance_passed=True,
            integrity_passed=False,
            safety_passed=True,
            reproducibility_passed=False,
            policy_passed=True,
            evidence_json='{"integrity": "hash mismatch", "reproducibility": "timeout"}',
        )
        db.add(result)
        await db.commit()
        await db.refresh(result)

        assert result.passed is False
        assert result.integrity_passed is False
        assert result.reproducibility_passed is False
        assert "hash mismatch" in result.evidence_json

    async def test_result_defaults(self, db, make_agent, make_listing):
        agent, _ = await make_agent()
        listing = await make_listing(seller_id=agent.id)

        job = VerificationJob(id=_uid(), listing_id=listing.id)
        db.add(job)
        await db.commit()

        result = VerificationResult(
            id=_uid(),
            job_id=job.id,
            listing_id=listing.id,
        )
        db.add(result)
        await db.commit()
        await db.refresh(result)

        assert result.passed is False
        assert result.trust_score == 0
        assert result.evidence_json == "{}"

    async def test_query_results_by_listing(self, db, make_agent, make_listing):
        agent, _ = await make_agent()
        listing = await make_listing(seller_id=agent.id)

        job = VerificationJob(id=_uid(), listing_id=listing.id)
        db.add(job)
        await db.commit()

        for passed in (True, False, True):
            vr = VerificationResult(
                id=_uid(),
                job_id=job.id,
                listing_id=listing.id,
                passed=passed,
            )
            db.add(vr)
        await db.commit()

        result = await db.execute(
            select(VerificationResult).where(
                VerificationResult.listing_id == listing.id,
                VerificationResult.passed == True,  # noqa: E712
            )
        )
        passing = list(result.scalars().all())
        assert len(passing) == 2
