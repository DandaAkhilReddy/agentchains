"""Comprehensive model tests for batch-3 models.

Covers:
  - marketplace/models/token_account.py   (TokenAccount, TokenLedger, TokenDeposit)
  - marketplace/models/trust_verification.py (SourceReceipt, ArtifactManifest,
                                              VerificationJob, VerificationResult)
  - marketplace/models/webhook_v2.py      (DeadLetterEntry, DeliveryAttempt)
  - marketplace/models/webmcp_tool.py     (WebMCPTool)
  - marketplace/models/workflow.py        (WorkflowDefinition, WorkflowExecution,
                                          WorkflowNodeExecution)
  - marketplace/models/zkproof.py         (ZKProof)

All tests are async and use the `db` fixture from conftest.
pytest-asyncio is configured in auto mode — no marks needed.
"""

from datetime import datetime, timezone
from decimal import Decimal

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from marketplace.models.token_account import TokenAccount, TokenLedger, TokenDeposit
from marketplace.models.trust_verification import (
    SourceReceipt,
    ArtifactManifest,
    VerificationJob,
    VerificationResult,
)
from marketplace.models.webhook_v2 import DeadLetterEntry, DeliveryAttempt
from marketplace.models.webmcp_tool import WebMCPTool
from marketplace.models.workflow import (
    WorkflowDefinition,
    WorkflowExecution,
    WorkflowNodeExecution,
)
from marketplace.models.zkproof import ZKProof
from marketplace.models.agent import RegisteredAgent
from marketplace.models.listing import DataListing
from marketplace.models.creator import Creator
from marketplace.tests.conftest import _new_id


# ---------------------------------------------------------------------------
# Helper factories (local, lean — no fixture overhead for simple objects)
# ---------------------------------------------------------------------------

def _agent(**kwargs) -> RegisteredAgent:
    return RegisteredAgent(
        id=_new_id(),
        name=f"agent-{_new_id()[:8]}",
        agent_type=kwargs.get("agent_type", "both"),
        public_key="ssh-rsa AAAA_test_key",
        status="active",
    )


def _creator(**kwargs) -> Creator:
    return Creator(
        id=_new_id(),
        email=f"creator-{_new_id()[:8]}@test.com",
        password_hash="hashed_password",
        display_name="Test Creator",
        status="active",
    )


def _listing(seller_id: str, **kwargs) -> DataListing:
    return DataListing(
        id=_new_id(),
        seller_id=seller_id,
        title=f"Listing {_new_id()[:6]}",
        category="web_search",
        content_hash=f"sha256:{'a' * 64}",
        content_size=512,
        price_usdc=Decimal("1.0"),
        quality_score=Decimal("0.85"),
        status=kwargs.get("status", "active"),
    )


# ===========================================================================
# TokenAccount
# ===========================================================================

class TestTokenAccount:
    async def test_create_with_agent_id(self, db: AsyncSession):
        """TokenAccount can be created with an agent_id FK (no real agent row needed
        in SQLite because FK enforcement is off by default in SQLite)."""
        account = TokenAccount(id=_new_id(), agent_id=_new_id())
        db.add(account)
        await db.commit()
        await db.refresh(account)
        assert account.id is not None

    async def test_default_balance_zero(self, db: AsyncSession):
        account = TokenAccount(id=_new_id())
        db.add(account)
        await db.commit()
        await db.refresh(account)
        assert float(account.balance) == 0.0

    async def test_default_totals_zero(self, db: AsyncSession):
        account = TokenAccount(id=_new_id())
        db.add(account)
        await db.commit()
        await db.refresh(account)
        assert float(account.total_deposited) == 0.0
        assert float(account.total_earned) == 0.0
        assert float(account.total_spent) == 0.0
        assert float(account.total_fees_paid) == 0.0

    async def test_created_at_populated(self, db: AsyncSession):
        account = TokenAccount(id=_new_id())
        db.add(account)
        await db.commit()
        await db.refresh(account)
        assert isinstance(account.created_at, datetime)

    async def test_updated_at_populated(self, db: AsyncSession):
        account = TokenAccount(id=_new_id())
        db.add(account)
        await db.commit()
        await db.refresh(account)
        assert isinstance(account.updated_at, datetime)

    async def test_platform_treasury_both_fks_null(self, db: AsyncSession):
        """Platform treasury account has both agent_id and creator_id as NULL."""
        account = TokenAccount(id=_new_id(), agent_id=None, creator_id=None)
        db.add(account)
        await db.commit()
        await db.refresh(account)
        assert account.agent_id is None
        assert account.creator_id is None

    async def test_agent_id_unique_constraint(self, db: AsyncSession):
        agent_id = _new_id()
        db.add(TokenAccount(id=_new_id(), agent_id=agent_id))
        await db.commit()

        db.add(TokenAccount(id=_new_id(), agent_id=agent_id))
        with pytest.raises(IntegrityError):
            await db.commit()
        await db.rollback()

    async def test_creator_id_unique_constraint(self, db: AsyncSession):
        creator_id = _new_id()
        db.add(TokenAccount(id=_new_id(), creator_id=creator_id))
        await db.commit()

        db.add(TokenAccount(id=_new_id(), creator_id=creator_id))
        with pytest.raises(IntegrityError):
            await db.commit()
        await db.rollback()

    async def test_set_explicit_balance(self, db: AsyncSession):
        account = TokenAccount(id=_new_id(), balance=Decimal("99.500000"))
        db.add(account)
        await db.commit()
        await db.refresh(account)
        assert float(account.balance) == pytest.approx(99.5)

    async def test_decimal_precision_preserved(self, db: AsyncSession):
        account = TokenAccount(
            id=_new_id(),
            balance=Decimal("123.456789"),
            total_deposited=Decimal("200.000001"),
        )
        db.add(account)
        await db.commit()
        await db.refresh(account)
        assert float(account.balance) == pytest.approx(123.456789, rel=1e-5)
        assert float(account.total_deposited) == pytest.approx(200.000001, rel=1e-5)

    async def test_query_by_agent_id(self, db: AsyncSession):
        agent_id = _new_id()
        account = TokenAccount(id=_new_id(), agent_id=agent_id)
        db.add(account)
        await db.commit()

        result = await db.execute(
            select(TokenAccount).where(TokenAccount.agent_id == agent_id)
        )
        fetched = result.scalar_one()
        assert fetched.agent_id == agent_id


# ===========================================================================
# TokenLedger
# ===========================================================================

class TestTokenLedger:
    async def test_create_minimal(self, db: AsyncSession):
        entry = TokenLedger(id=_new_id(), amount=Decimal("10"), tx_type="deposit")
        db.add(entry)
        await db.commit()
        await db.refresh(entry)
        assert entry.id is not None

    async def test_default_fee_amount_zero(self, db: AsyncSession):
        entry = TokenLedger(id=_new_id(), amount=Decimal("5"), tx_type="purchase")
        db.add(entry)
        await db.commit()
        await db.refresh(entry)
        assert float(entry.fee_amount) == 0.0

    async def test_default_memo_empty_string(self, db: AsyncSession):
        entry = TokenLedger(id=_new_id(), amount=Decimal("1"), tx_type="sale")
        db.add(entry)
        await db.commit()
        await db.refresh(entry)
        assert entry.memo == ""

    async def test_nullable_from_account_allowed(self, db: AsyncSession):
        """from_account_id=None represents an external deposit."""
        entry = TokenLedger(
            id=_new_id(),
            from_account_id=None,
            to_account_id=_new_id(),
            amount=Decimal("50"),
            tx_type="deposit",
        )
        db.add(entry)
        await db.commit()
        await db.refresh(entry)
        assert entry.from_account_id is None

    async def test_nullable_to_account_allowed(self, db: AsyncSession):
        """to_account_id=None represents a withdrawal."""
        entry = TokenLedger(
            id=_new_id(),
            from_account_id=_new_id(),
            to_account_id=None,
            amount=Decimal("25"),
            tx_type="withdrawal",
        )
        db.add(entry)
        await db.commit()
        await db.refresh(entry)
        assert entry.to_account_id is None

    async def test_idempotency_key_unique(self, db: AsyncSession):
        key = f"idem-{_new_id()}"
        db.add(TokenLedger(id=_new_id(), amount=Decimal("1"), tx_type="deposit", idempotency_key=key))
        await db.commit()

        db.add(TokenLedger(id=_new_id(), amount=Decimal("2"), tx_type="deposit", idempotency_key=key))
        with pytest.raises(IntegrityError):
            await db.commit()
        await db.rollback()

    async def test_idempotency_key_nullable(self, db: AsyncSession):
        """Two entries with idempotency_key=None are both allowed (NULL != NULL in SQL)."""
        db.add(TokenLedger(id=_new_id(), amount=Decimal("1"), tx_type="deposit", idempotency_key=None))
        db.add(TokenLedger(id=_new_id(), amount=Decimal("2"), tx_type="deposit", idempotency_key=None))
        await db.commit()  # Should not raise

    async def test_created_at_set_automatically(self, db: AsyncSession):
        entry = TokenLedger(id=_new_id(), amount=Decimal("1"), tx_type="bonus")
        db.add(entry)
        await db.commit()
        await db.refresh(entry)
        assert isinstance(entry.created_at, datetime)

    async def test_prev_hash_nullable(self, db: AsyncSession):
        """Genesis entry has prev_hash=None."""
        entry = TokenLedger(
            id=_new_id(), amount=Decimal("1"), tx_type="deposit", prev_hash=None
        )
        db.add(entry)
        await db.commit()
        await db.refresh(entry)
        assert entry.prev_hash is None

    async def test_reference_fields_nullable(self, db: AsyncSession):
        entry = TokenLedger(
            id=_new_id(),
            amount=Decimal("1"),
            tx_type="refund",
            reference_id=None,
            reference_type=None,
        )
        db.add(entry)
        await db.commit()
        await db.refresh(entry)
        assert entry.reference_id is None
        assert entry.reference_type is None

    async def test_full_entry_roundtrip(self, db: AsyncSession):
        """All fields survive a commit-refresh cycle."""
        eid = _new_id()
        entry = TokenLedger(
            id=eid,
            from_account_id=_new_id(),
            to_account_id=_new_id(),
            amount=Decimal("123.456789"),
            fee_amount=Decimal("0.500000"),
            tx_type="purchase",
            reference_id=_new_id(),
            reference_type="transaction",
            idempotency_key=f"full-{_new_id()}",
            memo="integration test payment",
            prev_hash="a" * 64,
            entry_hash="b" * 64,
        )
        db.add(entry)
        await db.commit()
        await db.refresh(entry)
        assert entry.tx_type == "purchase"
        assert entry.memo == "integration test payment"
        assert entry.prev_hash == "a" * 64
        assert float(entry.fee_amount) == pytest.approx(0.5)


# ===========================================================================
# TokenDeposit
# ===========================================================================

class TestTokenDeposit:
    async def test_create_minimal(self, db: AsyncSession):
        deposit = TokenDeposit(
            id=_new_id(),
            agent_id=_new_id(),
            amount_usd=Decimal("100.00"),
        )
        db.add(deposit)
        await db.commit()
        await db.refresh(deposit)
        assert deposit.id is not None

    async def test_default_currency_usd(self, db: AsyncSession):
        deposit = TokenDeposit(
            id=_new_id(), agent_id=_new_id(), amount_usd=Decimal("50.00")
        )
        db.add(deposit)
        await db.commit()
        await db.refresh(deposit)
        assert deposit.currency == "USD"

    async def test_default_status_pending(self, db: AsyncSession):
        deposit = TokenDeposit(
            id=_new_id(), agent_id=_new_id(), amount_usd=Decimal("10.00")
        )
        db.add(deposit)
        await db.commit()
        await db.refresh(deposit)
        assert deposit.status == "pending"

    async def test_default_payment_method_admin_credit(self, db: AsyncSession):
        deposit = TokenDeposit(
            id=_new_id(), agent_id=_new_id(), amount_usd=Decimal("10.00")
        )
        db.add(deposit)
        await db.commit()
        await db.refresh(deposit)
        assert deposit.payment_method == "admin_credit"

    async def test_payment_ref_nullable(self, db: AsyncSession):
        deposit = TokenDeposit(
            id=_new_id(), agent_id=_new_id(), amount_usd=Decimal("5.00"), payment_ref=None
        )
        db.add(deposit)
        await db.commit()
        await db.refresh(deposit)
        assert deposit.payment_ref is None

    async def test_completed_at_nullable(self, db: AsyncSession):
        deposit = TokenDeposit(
            id=_new_id(), agent_id=_new_id(), amount_usd=Decimal("5.00")
        )
        db.add(deposit)
        await db.commit()
        await db.refresh(deposit)
        assert deposit.completed_at is None

    async def test_created_at_set(self, db: AsyncSession):
        deposit = TokenDeposit(
            id=_new_id(), agent_id=_new_id(), amount_usd=Decimal("1.00")
        )
        db.add(deposit)
        await db.commit()
        await db.refresh(deposit)
        assert isinstance(deposit.created_at, datetime)

    async def test_explicit_status_and_payment_method(self, db: AsyncSession):
        deposit = TokenDeposit(
            id=_new_id(),
            agent_id=_new_id(),
            amount_usd=Decimal("200.00"),
            currency="USD",
            status="completed",
            payment_method="stripe",
            payment_ref="pi_test_12345",
        )
        db.add(deposit)
        await db.commit()
        await db.refresh(deposit)
        assert deposit.status == "completed"
        assert deposit.payment_method == "stripe"
        assert deposit.payment_ref == "pi_test_12345"

    async def test_decimal_amount_precision(self, db: AsyncSession):
        deposit = TokenDeposit(
            id=_new_id(), agent_id=_new_id(), amount_usd=Decimal("9999.99")
        )
        db.add(deposit)
        await db.commit()
        await db.refresh(deposit)
        assert float(deposit.amount_usd) == pytest.approx(9999.99)


# ===========================================================================
# SourceReceipt (trust_verification)
# ===========================================================================

class TestSourceReceipt:
    def _make(self, listing_id: str) -> SourceReceipt:
        return SourceReceipt(
            id=_new_id(),
            listing_id=listing_id,
            provider="openai",
            source_query="test query",
            response_hash=f"sha256:{'a' * 64}",
            seller_signature="sig_seller_" + "x" * 32,
            platform_signature="sig_platform_" + "y" * 32,
        )

    async def test_create_minimal(self, db: AsyncSession):
        listing_id = _new_id()
        receipt = self._make(listing_id)
        db.add(receipt)
        await db.commit()
        await db.refresh(receipt)
        assert receipt.id is not None
        assert receipt.listing_id == listing_id

    async def test_default_request_payload_json(self, db: AsyncSession):
        receipt = self._make(_new_id())
        db.add(receipt)
        await db.commit()
        await db.refresh(receipt)
        assert receipt.request_payload_json == "{}"

    async def test_default_headers_json(self, db: AsyncSession):
        receipt = self._make(_new_id())
        db.add(receipt)
        await db.commit()
        await db.refresh(receipt)
        assert receipt.headers_json == "{}"

    async def test_fetched_at_set(self, db: AsyncSession):
        receipt = self._make(_new_id())
        db.add(receipt)
        await db.commit()
        await db.refresh(receipt)
        assert isinstance(receipt.fetched_at, datetime)

    async def test_created_at_set(self, db: AsyncSession):
        receipt = self._make(_new_id())
        db.add(receipt)
        await db.commit()
        await db.refresh(receipt)
        assert isinstance(receipt.created_at, datetime)

    async def test_provider_required(self, db: AsyncSession):
        receipt = SourceReceipt(
            id=_new_id(),
            listing_id=_new_id(),
            provider=None,          # violates NOT NULL
            source_query="q",
            response_hash="sha256:" + "a" * 64,
            seller_signature="sig",
            platform_signature="sig",
        )
        db.add(receipt)
        with pytest.raises((IntegrityError, Exception)):
            await db.commit()
        await db.rollback()

    async def test_full_fields_roundtrip(self, db: AsyncSession):
        rid = _new_id()
        receipt = SourceReceipt(
            id=rid,
            listing_id=_new_id(),
            provider="anthropic",
            source_query="summarise this doc",
            request_payload_json='{"model":"claude-3"}',
            response_hash="sha256:" + "b" * 64,
            headers_json='{"content-type":"application/json"}',
            seller_signature="s" * 64,
            platform_signature="p" * 64,
        )
        db.add(receipt)
        await db.commit()
        await db.refresh(receipt)
        assert receipt.provider == "anthropic"
        assert receipt.source_query == "summarise this doc"
        assert receipt.request_payload_json == '{"model":"claude-3"}'


# ===========================================================================
# ArtifactManifest (trust_verification)
# ===========================================================================

class TestArtifactManifest:
    def _make(self, listing_id: str) -> ArtifactManifest:
        return ArtifactManifest(
            id=_new_id(),
            listing_id=listing_id,
            canonical_hash=f"sha256:{'c' * 64}",
            mime_type="application/json",
            content_size=1024,
        )

    async def test_create_minimal(self, db: AsyncSession):
        manifest = self._make(_new_id())
        db.add(manifest)
        await db.commit()
        await db.refresh(manifest)
        assert manifest.id is not None

    async def test_default_dependency_chain_json(self, db: AsyncSession):
        manifest = self._make(_new_id())
        db.add(manifest)
        await db.commit()
        await db.refresh(manifest)
        assert manifest.dependency_chain_json == "[]"

    async def test_schema_fingerprint_nullable(self, db: AsyncSession):
        manifest = self._make(_new_id())
        manifest.schema_fingerprint = None
        db.add(manifest)
        await db.commit()
        await db.refresh(manifest)
        assert manifest.schema_fingerprint is None

    async def test_schema_fingerprint_set(self, db: AsyncSession):
        manifest = self._make(_new_id())
        manifest.schema_fingerprint = f"sha256:{'d' * 64}"
        db.add(manifest)
        await db.commit()
        await db.refresh(manifest)
        assert manifest.schema_fingerprint is not None

    async def test_created_at_set(self, db: AsyncSession):
        manifest = self._make(_new_id())
        db.add(manifest)
        await db.commit()
        await db.refresh(manifest)
        assert isinstance(manifest.created_at, datetime)

    async def test_content_size_stored_correctly(self, db: AsyncSession):
        manifest = ArtifactManifest(
            id=_new_id(),
            listing_id=_new_id(),
            canonical_hash="sha256:" + "e" * 64,
            mime_type="text/csv",
            content_size=999999,
        )
        db.add(manifest)
        await db.commit()
        await db.refresh(manifest)
        assert manifest.content_size == 999999

    async def test_mime_type_stored(self, db: AsyncSession):
        manifest = self._make(_new_id())
        manifest.mime_type = "text/plain"
        db.add(manifest)
        await db.commit()
        await db.refresh(manifest)
        assert manifest.mime_type == "text/plain"


# ===========================================================================
# VerificationJob (trust_verification)
# ===========================================================================

class TestVerificationJob:
    def _make(self, listing_id: str) -> VerificationJob:
        return VerificationJob(id=_new_id(), listing_id=listing_id)

    async def test_create_minimal(self, db: AsyncSession):
        job = self._make(_new_id())
        db.add(job)
        await db.commit()
        await db.refresh(job)
        assert job.id is not None

    async def test_default_status_pending(self, db: AsyncSession):
        job = self._make(_new_id())
        db.add(job)
        await db.commit()
        await db.refresh(job)
        assert job.status == "pending"

    async def test_default_trigger_source(self, db: AsyncSession):
        job = self._make(_new_id())
        db.add(job)
        await db.commit()
        await db.refresh(job)
        assert job.trigger_source == "listing_create"

    async def test_default_stage_status_json(self, db: AsyncSession):
        job = self._make(_new_id())
        db.add(job)
        await db.commit()
        await db.refresh(job)
        assert job.stage_status_json == "{}"

    async def test_requested_by_nullable(self, db: AsyncSession):
        job = self._make(_new_id())
        job.requested_by = None
        db.add(job)
        await db.commit()
        await db.refresh(job)
        assert job.requested_by is None

    async def test_failure_reason_nullable(self, db: AsyncSession):
        job = self._make(_new_id())
        db.add(job)
        await db.commit()
        await db.refresh(job)
        assert job.failure_reason is None

    async def test_started_at_nullable(self, db: AsyncSession):
        job = self._make(_new_id())
        db.add(job)
        await db.commit()
        await db.refresh(job)
        assert job.started_at is None

    async def test_completed_at_nullable(self, db: AsyncSession):
        job = self._make(_new_id())
        db.add(job)
        await db.commit()
        await db.refresh(job)
        assert job.completed_at is None

    async def test_created_at_set(self, db: AsyncSession):
        job = self._make(_new_id())
        db.add(job)
        await db.commit()
        await db.refresh(job)
        assert isinstance(job.created_at, datetime)

    async def test_status_transitions_stored(self, db: AsyncSession):
        job = VerificationJob(
            id=_new_id(),
            listing_id=_new_id(),
            status="completed",
            trigger_source="manual_review",
            requested_by=_new_id(),
            failure_reason=None,
        )
        db.add(job)
        await db.commit()
        await db.refresh(job)
        assert job.status == "completed"
        assert job.trigger_source == "manual_review"

    async def test_failure_reason_stored(self, db: AsyncSession):
        job = VerificationJob(
            id=_new_id(),
            listing_id=_new_id(),
            status="failed",
            failure_reason="Schema validation failed: missing required field.",
        )
        db.add(job)
        await db.commit()
        await db.refresh(job)
        assert job.failure_reason == "Schema validation failed: missing required field."


# ===========================================================================
# VerificationResult (trust_verification)
# ===========================================================================

class TestVerificationResult:
    def _make(self, job_id: str, listing_id: str) -> VerificationResult:
        return VerificationResult(
            id=_new_id(),
            job_id=job_id,
            listing_id=listing_id,
        )

    async def test_create_minimal(self, db: AsyncSession):
        result = self._make(_new_id(), _new_id())
        db.add(result)
        await db.commit()
        await db.refresh(result)
        assert result.id is not None

    async def test_default_passed_false(self, db: AsyncSession):
        result = self._make(_new_id(), _new_id())
        db.add(result)
        await db.commit()
        await db.refresh(result)
        assert result.passed is False

    async def test_default_trust_score_zero(self, db: AsyncSession):
        result = self._make(_new_id(), _new_id())
        db.add(result)
        await db.commit()
        await db.refresh(result)
        assert result.trust_score == 0

    async def test_all_check_flags_default_false(self, db: AsyncSession):
        result = self._make(_new_id(), _new_id())
        db.add(result)
        await db.commit()
        await db.refresh(result)
        assert result.provenance_passed is False
        assert result.integrity_passed is False
        assert result.safety_passed is False
        assert result.reproducibility_passed is False
        assert result.policy_passed is False

    async def test_default_evidence_json(self, db: AsyncSession):
        result = self._make(_new_id(), _new_id())
        db.add(result)
        await db.commit()
        await db.refresh(result)
        assert result.evidence_json == "{}"

    async def test_created_at_set(self, db: AsyncSession):
        result = self._make(_new_id(), _new_id())
        db.add(result)
        await db.commit()
        await db.refresh(result)
        assert isinstance(result.created_at, datetime)

    async def test_passing_result_stored(self, db: AsyncSession):
        result = VerificationResult(
            id=_new_id(),
            job_id=_new_id(),
            listing_id=_new_id(),
            passed=True,
            trust_score=95,
            provenance_passed=True,
            integrity_passed=True,
            safety_passed=True,
            reproducibility_passed=True,
            policy_passed=True,
            evidence_json='{"checks": ["all_passed"]}',
        )
        db.add(result)
        await db.commit()
        await db.refresh(result)
        assert result.passed is True
        assert result.trust_score == 95
        assert result.provenance_passed is True
        assert result.policy_passed is True

    async def test_partial_pass_stored(self, db: AsyncSession):
        """Some flags True, some False — correct partial-pass scenario."""
        result = VerificationResult(
            id=_new_id(),
            job_id=_new_id(),
            listing_id=_new_id(),
            passed=False,
            trust_score=40,
            provenance_passed=True,
            integrity_passed=False,
            safety_passed=True,
            reproducibility_passed=False,
            policy_passed=False,
        )
        db.add(result)
        await db.commit()
        await db.refresh(result)
        assert result.passed is False
        assert result.trust_score == 40
        assert result.provenance_passed is True
        assert result.integrity_passed is False

    async def test_query_by_listing_id(self, db: AsyncSession):
        listing_id = _new_id()
        result = VerificationResult(
            id=_new_id(), job_id=_new_id(), listing_id=listing_id
        )
        db.add(result)
        await db.commit()

        fetched = (
            await db.execute(
                select(VerificationResult).where(
                    VerificationResult.listing_id == listing_id
                )
            )
        ).scalar_one()
        assert fetched.listing_id == listing_id


# ===========================================================================
# DeadLetterEntry (webhook_v2)
# ===========================================================================

class TestDeadLetterEntry:
    async def test_create_minimal(self, db: AsyncSession):
        entry = DeadLetterEntry(id=_new_id(), message_body='{"event":"test"}')
        db.add(entry)
        await db.commit()
        await db.refresh(entry)
        assert entry.id is not None

    async def test_default_original_queue(self, db: AsyncSession):
        entry = DeadLetterEntry(id=_new_id())
        db.add(entry)
        await db.commit()
        await db.refresh(entry)
        assert entry.original_queue == "webhooks"

    async def test_default_message_body(self, db: AsyncSession):
        entry = DeadLetterEntry(id=_new_id())
        db.add(entry)
        await db.commit()
        await db.refresh(entry)
        assert entry.message_body == "{}"

    async def test_default_retried_false(self, db: AsyncSession):
        entry = DeadLetterEntry(id=_new_id())
        db.add(entry)
        await db.commit()
        await db.refresh(entry)
        assert entry.retried is False

    async def test_default_retry_count_zero(self, db: AsyncSession):
        entry = DeadLetterEntry(id=_new_id())
        db.add(entry)
        await db.commit()
        await db.refresh(entry)
        assert entry.retry_count == 0

    async def test_dead_lettered_at_set(self, db: AsyncSession):
        entry = DeadLetterEntry(id=_new_id())
        db.add(entry)
        await db.commit()
        await db.refresh(entry)
        assert isinstance(entry.dead_lettered_at, datetime)

    async def test_backward_compat_queue_name_property(self, db: AsyncSession):
        entry = DeadLetterEntry(id=_new_id(), original_queue="custom_queue")
        db.add(entry)
        await db.commit()
        await db.refresh(entry)
        assert entry.queue_name == "custom_queue"

    async def test_backward_compat_original_message_json_property(self, db: AsyncSession):
        body = '{"event":"order.completed","id":"abc"}'
        entry = DeadLetterEntry(id=_new_id(), message_body=body)
        db.add(entry)
        await db.commit()
        await db.refresh(entry)
        assert entry.original_message_json == body

    async def test_backward_compat_created_at_property(self, db: AsyncSession):
        entry = DeadLetterEntry(id=_new_id())
        db.add(entry)
        await db.commit()
        await db.refresh(entry)
        assert entry.created_at == entry.dead_lettered_at

    async def test_retried_at_property_when_not_retried(self, db: AsyncSession):
        entry = DeadLetterEntry(id=_new_id(), retried=False)
        db.add(entry)
        await db.commit()
        await db.refresh(entry)
        assert entry.retried_at is None

    async def test_retried_at_property_when_retried(self, db: AsyncSession):
        entry = DeadLetterEntry(id=_new_id(), retried=True)
        db.add(entry)
        await db.commit()
        await db.refresh(entry)
        assert entry.retried_at == entry.dead_lettered_at

    async def test_reason_stored(self, db: AsyncSession):
        entry = DeadLetterEntry(
            id=_new_id(),
            reason="Max retries exceeded after 5 attempts",
            retry_count=5,
            retried=True,
        )
        db.add(entry)
        await db.commit()
        await db.refresh(entry)
        assert entry.reason == "Max retries exceeded after 5 attempts"
        assert entry.retry_count == 5

    async def test_explicit_queue_and_body(self, db: AsyncSession):
        entry = DeadLetterEntry(
            id=_new_id(),
            original_queue="payments_queue",
            message_body='{"tx_id":"xyz"}',
        )
        db.add(entry)
        await db.commit()
        await db.refresh(entry)
        assert entry.original_queue == "payments_queue"
        assert entry.message_body == '{"tx_id":"xyz"}'


# ===========================================================================
# DeliveryAttempt (webhook_v2)
# ===========================================================================

class TestDeliveryAttempt:
    async def test_create_minimal(self, db: AsyncSession):
        attempt = DeliveryAttempt(
            id=_new_id(),
            webhook_id=_new_id(),
            event_type="order.created",
            target_url="https://example.com/webhook",
        )
        db.add(attempt)
        await db.commit()
        await db.refresh(attempt)
        assert attempt.id is not None

    async def test_default_success_false(self, db: AsyncSession):
        attempt = DeliveryAttempt(id=_new_id())
        db.add(attempt)
        await db.commit()
        await db.refresh(attempt)
        assert attempt.success is False

    async def test_default_status_pending(self, db: AsyncSession):
        attempt = DeliveryAttempt(id=_new_id())
        db.add(attempt)
        await db.commit()
        await db.refresh(attempt)
        assert attempt.status == "pending"

    async def test_default_attempt_number_one(self, db: AsyncSession):
        attempt = DeliveryAttempt(id=_new_id())
        db.add(attempt)
        await db.commit()
        await db.refresh(attempt)
        assert attempt.attempt_number == 1

    async def test_status_code_nullable(self, db: AsyncSession):
        attempt = DeliveryAttempt(id=_new_id(), status_code=None)
        db.add(attempt)
        await db.commit()
        await db.refresh(attempt)
        assert attempt.status_code is None

    async def test_attempted_at_set(self, db: AsyncSession):
        attempt = DeliveryAttempt(id=_new_id())
        db.add(attempt)
        await db.commit()
        await db.refresh(attempt)
        assert isinstance(attempt.attempted_at, datetime)

    async def test_successful_delivery_stored(self, db: AsyncSession):
        attempt = DeliveryAttempt(
            id=_new_id(),
            webhook_id=_new_id(),
            event_type="payment.completed",
            target_url="https://example.com/hook",
            status_code=200,
            response_body='{"ok":true}',
            success=True,
            status="delivered",
            attempt_number=1,
        )
        db.add(attempt)
        await db.commit()
        await db.refresh(attempt)
        assert attempt.success is True
        assert attempt.status == "delivered"
        assert attempt.status_code == 200

    async def test_failed_delivery_with_error_message(self, db: AsyncSession):
        attempt = DeliveryAttempt(
            id=_new_id(),
            webhook_id=_new_id(),
            event_type="order.failed",
            target_url="https://example.com/hook",
            status_code=503,
            success=False,
            status="failed",
            error_message="Connection timeout",
            attempt_number=3,
        )
        db.add(attempt)
        await db.commit()
        await db.refresh(attempt)
        assert attempt.success is False
        assert attempt.status == "failed"
        assert attempt.error_message == "Connection timeout"
        assert attempt.attempt_number == 3

    async def test_subscription_id_stored(self, db: AsyncSession):
        sub_id = _new_id()
        attempt = DeliveryAttempt(
            id=_new_id(), subscription_id=sub_id, event_json='{"type":"ping"}'
        )
        db.add(attempt)
        await db.commit()
        await db.refresh(attempt)
        assert attempt.subscription_id == sub_id
        assert attempt.event_json == '{"type":"ping"}'

    async def test_query_by_status(self, db: AsyncSession):
        for _ in range(3):
            db.add(DeliveryAttempt(id=_new_id(), status="failed"))
        db.add(DeliveryAttempt(id=_new_id(), status="delivered"))
        await db.commit()

        rows = (
            await db.execute(
                select(DeliveryAttempt).where(DeliveryAttempt.status == "failed")
            )
        ).scalars().all()
        assert len(rows) == 3


# ===========================================================================
# WebMCPTool
# ===========================================================================

class TestWebMCPTool:
    async def _creator_and_agent(self, db: AsyncSession):
        creator = _creator()
        db.add(creator)
        await db.commit()
        await db.refresh(creator)

        agent = _agent()
        agent.creator_id = creator.id
        db.add(agent)
        await db.commit()
        await db.refresh(agent)
        return creator, agent

    def _tool(self, creator_id: str, **kwargs) -> WebMCPTool:
        return WebMCPTool(
            id=_new_id(),
            name=f"Tool-{_new_id()[:6]}",
            domain="https://example.com",
            endpoint_url="https://example.com/mcp",
            creator_id=creator_id,
            category=kwargs.pop("category", "shopping"),
            **kwargs,
        )

    async def test_create_minimal(self, db: AsyncSession):
        creator, _ = await self._creator_and_agent(db)
        tool = self._tool(creator.id)
        db.add(tool)
        await db.commit()
        await db.refresh(tool)
        assert tool.id is not None

    async def test_default_version(self, db: AsyncSession):
        creator, _ = await self._creator_and_agent(db)
        tool = self._tool(creator.id)
        db.add(tool)
        await db.commit()
        await db.refresh(tool)
        assert tool.version == "1.0.0"

    async def test_default_status_pending(self, db: AsyncSession):
        creator, _ = await self._creator_and_agent(db)
        tool = self._tool(creator.id)
        db.add(tool)
        await db.commit()
        await db.refresh(tool)
        assert tool.status == "pending"

    async def test_default_execution_count_zero(self, db: AsyncSession):
        creator, _ = await self._creator_and_agent(db)
        tool = self._tool(creator.id)
        db.add(tool)
        await db.commit()
        await db.refresh(tool)
        assert tool.execution_count == 0

    async def test_default_avg_execution_time_zero(self, db: AsyncSession):
        creator, _ = await self._creator_and_agent(db)
        tool = self._tool(creator.id)
        db.add(tool)
        await db.commit()
        await db.refresh(tool)
        assert tool.avg_execution_time_ms == 0

    async def test_default_success_rate_one(self, db: AsyncSession):
        creator, _ = await self._creator_and_agent(db)
        tool = self._tool(creator.id)
        db.add(tool)
        await db.commit()
        await db.refresh(tool)
        assert float(tool.success_rate) == pytest.approx(1.0)

    async def test_default_description_empty(self, db: AsyncSession):
        creator, _ = await self._creator_and_agent(db)
        tool = self._tool(creator.id)
        db.add(tool)
        await db.commit()
        await db.refresh(tool)
        assert tool.description == ""

    async def test_default_input_schema(self, db: AsyncSession):
        creator, _ = await self._creator_and_agent(db)
        tool = self._tool(creator.id)
        db.add(tool)
        await db.commit()
        await db.refresh(tool)
        assert tool.input_schema == "{}"

    async def test_default_output_schema(self, db: AsyncSession):
        creator, _ = await self._creator_and_agent(db)
        tool = self._tool(creator.id)
        db.add(tool)
        await db.commit()
        await db.refresh(tool)
        assert tool.output_schema == "{}"

    async def test_default_schema_hash_empty(self, db: AsyncSession):
        creator, _ = await self._creator_and_agent(db)
        tool = self._tool(creator.id)
        db.add(tool)
        await db.commit()
        await db.refresh(tool)
        assert tool.schema_hash == ""

    async def test_agent_id_nullable(self, db: AsyncSession):
        creator, _ = await self._creator_and_agent(db)
        tool = self._tool(creator.id, agent_id=None)
        db.add(tool)
        await db.commit()
        await db.refresh(tool)
        assert tool.agent_id is None

    async def test_approval_notes_nullable(self, db: AsyncSession):
        creator, _ = await self._creator_and_agent(db)
        tool = self._tool(creator.id)
        db.add(tool)
        await db.commit()
        await db.refresh(tool)
        assert tool.approval_notes is None

    async def test_created_at_set(self, db: AsyncSession):
        creator, _ = await self._creator_and_agent(db)
        tool = self._tool(creator.id)
        db.add(tool)
        await db.commit()
        await db.refresh(tool)
        assert isinstance(tool.created_at, datetime)

    async def test_updated_at_set(self, db: AsyncSession):
        creator, _ = await self._creator_and_agent(db)
        tool = self._tool(creator.id)
        db.add(tool)
        await db.commit()
        await db.refresh(tool)
        assert isinstance(tool.updated_at, datetime)

    async def test_category_stored(self, db: AsyncSession):
        creator, _ = await self._creator_and_agent(db)
        tool = self._tool(creator.id, category="research")
        db.add(tool)
        await db.commit()
        await db.refresh(tool)
        assert tool.category == "research"

    async def test_success_rate_decimal_precision(self, db: AsyncSession):
        creator, _ = await self._creator_and_agent(db)
        tool = self._tool(creator.id)
        tool.success_rate = Decimal("0.9375")
        db.add(tool)
        await db.commit()
        await db.refresh(tool)
        assert float(tool.success_rate) == pytest.approx(0.9375, rel=1e-4)

    async def test_full_tool_roundtrip(self, db: AsyncSession):
        creator, agent = await self._creator_and_agent(db)
        tool = WebMCPTool(
            id=_new_id(),
            name="Amazon Price Tracker",
            description="Tracks prices on Amazon product pages",
            domain="https://amazon.com",
            endpoint_url="https://amazon.com/webmcp/price",
            input_schema='{"type":"object","properties":{"asin":{"type":"string"}}}',
            output_schema='{"type":"object","properties":{"price":{"type":"number"}}}',
            schema_hash="a" * 64,
            creator_id=creator.id,
            agent_id=agent.id,
            category="shopping",
            version="2.1.0",
            status="active",
            approval_notes="Approved by admin on 2026-01-01",
            execution_count=500,
            avg_execution_time_ms=120,
            success_rate=Decimal("0.9800"),
        )
        db.add(tool)
        await db.commit()
        await db.refresh(tool)
        assert tool.name == "Amazon Price Tracker"
        assert tool.version == "2.1.0"
        assert tool.status == "active"
        assert tool.execution_count == 500
        assert float(tool.success_rate) == pytest.approx(0.98, rel=1e-4)

    async def test_query_by_category(self, db: AsyncSession):
        creator, _ = await self._creator_and_agent(db)
        for cat in ("shopping", "shopping", "research"):
            db.add(self._tool(creator.id, category=cat))
        await db.commit()

        rows = (
            await db.execute(
                select(WebMCPTool).where(WebMCPTool.category == "shopping")
            )
        ).scalars().all()
        assert len(rows) == 2


# ===========================================================================
# WorkflowDefinition
# ===========================================================================

class TestWorkflowDefinition:
    def _make(self, **kwargs) -> WorkflowDefinition:
        return WorkflowDefinition(
            id=_new_id(),
            name=f"Workflow-{_new_id()[:6]}",
            graph_json=kwargs.pop("graph_json", '{"nodes":[],"edges":[]}'),
            owner_id=kwargs.pop("owner_id", _new_id()),
            **kwargs,
        )

    async def test_create_minimal(self, db: AsyncSession):
        wf = self._make()
        db.add(wf)
        await db.commit()
        await db.refresh(wf)
        assert wf.id is not None

    async def test_default_description_empty(self, db: AsyncSession):
        wf = self._make()
        db.add(wf)
        await db.commit()
        await db.refresh(wf)
        assert wf.description == ""

    async def test_default_version_one(self, db: AsyncSession):
        wf = self._make()
        db.add(wf)
        await db.commit()
        await db.refresh(wf)
        assert wf.version == 1

    async def test_default_status_draft(self, db: AsyncSession):
        wf = self._make()
        db.add(wf)
        await db.commit()
        await db.refresh(wf)
        assert wf.status == "draft"

    async def test_max_budget_nullable(self, db: AsyncSession):
        wf = self._make()
        db.add(wf)
        await db.commit()
        await db.refresh(wf)
        assert wf.max_budget_usd is None

    async def test_max_budget_stored(self, db: AsyncSession):
        wf = self._make(max_budget_usd=Decimal("50.0000"))
        db.add(wf)
        await db.commit()
        await db.refresh(wf)
        assert float(wf.max_budget_usd) == pytest.approx(50.0)

    async def test_created_at_set(self, db: AsyncSession):
        wf = self._make()
        db.add(wf)
        await db.commit()
        await db.refresh(wf)
        assert isinstance(wf.created_at, datetime)

    async def test_updated_at_set(self, db: AsyncSession):
        wf = self._make()
        db.add(wf)
        await db.commit()
        await db.refresh(wf)
        assert isinstance(wf.updated_at, datetime)

    async def test_graph_json_stored(self, db: AsyncSession):
        graph = '{"nodes":[{"id":"n1","type":"agent"}],"edges":[]}'
        wf = self._make(graph_json=graph)
        db.add(wf)
        await db.commit()
        await db.refresh(wf)
        assert wf.graph_json == graph

    async def test_explicit_status_active(self, db: AsyncSession):
        wf = self._make(status="active")
        db.add(wf)
        await db.commit()
        await db.refresh(wf)
        assert wf.status == "active"

    async def test_query_by_owner(self, db: AsyncSession):
        owner_id = _new_id()
        for _ in range(2):
            db.add(self._make(owner_id=owner_id))
        db.add(self._make())  # different owner
        await db.commit()

        rows = (
            await db.execute(
                select(WorkflowDefinition).where(
                    WorkflowDefinition.owner_id == owner_id
                )
            )
        ).scalars().all()
        assert len(rows) == 2


# ===========================================================================
# WorkflowExecution
# ===========================================================================

class TestWorkflowExecution:
    async def _workflow(self, db: AsyncSession) -> WorkflowDefinition:
        wf = WorkflowDefinition(
            id=_new_id(),
            name=f"WF-{_new_id()[:6]}",
            graph_json="{}",
            owner_id=_new_id(),
        )
        db.add(wf)
        await db.commit()
        await db.refresh(wf)
        return wf

    def _exec(self, workflow_id: str, **kwargs) -> WorkflowExecution:
        return WorkflowExecution(
            id=_new_id(),
            workflow_id=workflow_id,
            initiated_by=_new_id(),
            **kwargs,
        )

    async def test_create_minimal(self, db: AsyncSession):
        wf = await self._workflow(db)
        ex = self._exec(wf.id)
        db.add(ex)
        await db.commit()
        await db.refresh(ex)
        assert ex.id is not None

    async def test_default_status_pending(self, db: AsyncSession):
        wf = await self._workflow(db)
        ex = self._exec(wf.id)
        db.add(ex)
        await db.commit()
        await db.refresh(ex)
        assert ex.status == "pending"

    async def test_default_input_json(self, db: AsyncSession):
        wf = await self._workflow(db)
        ex = self._exec(wf.id)
        db.add(ex)
        await db.commit()
        await db.refresh(ex)
        assert ex.input_json == "{}"

    async def test_default_output_json(self, db: AsyncSession):
        wf = await self._workflow(db)
        ex = self._exec(wf.id)
        db.add(ex)
        await db.commit()
        await db.refresh(ex)
        assert ex.output_json == "{}"

    async def test_default_total_cost_zero(self, db: AsyncSession):
        wf = await self._workflow(db)
        ex = self._exec(wf.id)
        db.add(ex)
        await db.commit()
        await db.refresh(ex)
        assert float(ex.total_cost_usd) == pytest.approx(0.0)

    async def test_started_at_nullable(self, db: AsyncSession):
        wf = await self._workflow(db)
        ex = self._exec(wf.id)
        db.add(ex)
        await db.commit()
        await db.refresh(ex)
        assert ex.started_at is None

    async def test_completed_at_nullable(self, db: AsyncSession):
        wf = await self._workflow(db)
        ex = self._exec(wf.id)
        db.add(ex)
        await db.commit()
        await db.refresh(ex)
        assert ex.completed_at is None

    async def test_error_message_nullable(self, db: AsyncSession):
        wf = await self._workflow(db)
        ex = self._exec(wf.id)
        db.add(ex)
        await db.commit()
        await db.refresh(ex)
        assert ex.error_message is None

    async def test_created_at_set(self, db: AsyncSession):
        wf = await self._workflow(db)
        ex = self._exec(wf.id)
        db.add(ex)
        await db.commit()
        await db.refresh(ex)
        assert isinstance(ex.created_at, datetime)

    async def test_total_cost_stored(self, db: AsyncSession):
        wf = await self._workflow(db)
        ex = self._exec(wf.id, total_cost_usd=Decimal("3.141592"))
        db.add(ex)
        await db.commit()
        await db.refresh(ex)
        assert float(ex.total_cost_usd) == pytest.approx(3.141592, rel=1e-5)

    async def test_completed_execution_fields(self, db: AsyncSession):
        wf = await self._workflow(db)
        now = datetime.now(timezone.utc)
        ex = WorkflowExecution(
            id=_new_id(),
            workflow_id=wf.id,
            initiated_by=_new_id(),
            status="completed",
            input_json='{"query":"search python"}',
            output_json='{"result":"ok"}',
            total_cost_usd=Decimal("0.050000"),
            started_at=now,
            completed_at=now,
        )
        db.add(ex)
        await db.commit()
        await db.refresh(ex)
        assert ex.status == "completed"
        assert ex.input_json == '{"query":"search python"}'
        assert isinstance(ex.started_at, datetime)
        assert isinstance(ex.completed_at, datetime)

    async def test_failed_execution_stores_error(self, db: AsyncSession):
        wf = await self._workflow(db)
        ex = self._exec(
            wf.id,
            status="failed",
            error_message="Node n3 timed out after 30s",
        )
        db.add(ex)
        await db.commit()
        await db.refresh(ex)
        assert ex.status == "failed"
        assert ex.error_message == "Node n3 timed out after 30s"


# ===========================================================================
# WorkflowNodeExecution
# ===========================================================================

class TestWorkflowNodeExecution:
    async def _execution_id(self, db: AsyncSession) -> str:
        wf = WorkflowDefinition(
            id=_new_id(), name=f"WF-{_new_id()[:6]}", graph_json="{}", owner_id=_new_id()
        )
        db.add(wf)
        ex = WorkflowExecution(id=_new_id(), workflow_id=wf.id, initiated_by=_new_id())
        db.add(ex)
        await db.commit()
        return ex.id

    def _node_exec(self, execution_id: str, **kwargs) -> WorkflowNodeExecution:
        return WorkflowNodeExecution(
            id=_new_id(),
            execution_id=execution_id,
            node_id=f"node-{_new_id()[:6]}",
            node_type=kwargs.pop("node_type", "agent"),
            **kwargs,
        )

    async def test_create_minimal(self, db: AsyncSession):
        ex_id = await self._execution_id(db)
        node_ex = self._node_exec(ex_id)
        db.add(node_ex)
        await db.commit()
        await db.refresh(node_ex)
        assert node_ex.id is not None

    async def test_default_status_pending(self, db: AsyncSession):
        ex_id = await self._execution_id(db)
        node_ex = self._node_exec(ex_id)
        db.add(node_ex)
        await db.commit()
        await db.refresh(node_ex)
        assert node_ex.status == "pending"

    async def test_default_input_json(self, db: AsyncSession):
        ex_id = await self._execution_id(db)
        node_ex = self._node_exec(ex_id)
        db.add(node_ex)
        await db.commit()
        await db.refresh(node_ex)
        assert node_ex.input_json == "{}"

    async def test_default_output_json(self, db: AsyncSession):
        ex_id = await self._execution_id(db)
        node_ex = self._node_exec(ex_id)
        db.add(node_ex)
        await db.commit()
        await db.refresh(node_ex)
        assert node_ex.output_json == "{}"

    async def test_default_cost_usd_zero(self, db: AsyncSession):
        ex_id = await self._execution_id(db)
        node_ex = self._node_exec(ex_id)
        db.add(node_ex)
        await db.commit()
        await db.refresh(node_ex)
        assert float(node_ex.cost_usd) == pytest.approx(0.0)

    async def test_default_attempt_one(self, db: AsyncSession):
        ex_id = await self._execution_id(db)
        node_ex = self._node_exec(ex_id)
        db.add(node_ex)
        await db.commit()
        await db.refresh(node_ex)
        assert node_ex.attempt == 1

    async def test_started_at_nullable(self, db: AsyncSession):
        ex_id = await self._execution_id(db)
        node_ex = self._node_exec(ex_id)
        db.add(node_ex)
        await db.commit()
        await db.refresh(node_ex)
        assert node_ex.started_at is None

    async def test_completed_at_nullable(self, db: AsyncSession):
        ex_id = await self._execution_id(db)
        node_ex = self._node_exec(ex_id)
        db.add(node_ex)
        await db.commit()
        await db.refresh(node_ex)
        assert node_ex.completed_at is None

    async def test_error_message_nullable(self, db: AsyncSession):
        ex_id = await self._execution_id(db)
        node_ex = self._node_exec(ex_id)
        db.add(node_ex)
        await db.commit()
        await db.refresh(node_ex)
        assert node_ex.error_message is None

    async def test_cost_usd_precision(self, db: AsyncSession):
        ex_id = await self._execution_id(db)
        node_ex = self._node_exec(ex_id, cost_usd=Decimal("0.001234"))
        db.add(node_ex)
        await db.commit()
        await db.refresh(node_ex)
        assert float(node_ex.cost_usd) == pytest.approx(0.001234, rel=1e-4)

    async def test_retry_attempt_stored(self, db: AsyncSession):
        ex_id = await self._execution_id(db)
        node_ex = self._node_exec(ex_id, attempt=3, status="failed")
        db.add(node_ex)
        await db.commit()
        await db.refresh(node_ex)
        assert node_ex.attempt == 3

    async def test_node_type_stored(self, db: AsyncSession):
        ex_id = await self._execution_id(db)
        node_ex = self._node_exec(ex_id, node_type="condition")
        db.add(node_ex)
        await db.commit()
        await db.refresh(node_ex)
        assert node_ex.node_type == "condition"

    async def test_query_by_execution_id(self, db: AsyncSession):
        ex_id = await self._execution_id(db)
        for _ in range(4):
            db.add(self._node_exec(ex_id))
        await db.commit()

        rows = (
            await db.execute(
                select(WorkflowNodeExecution).where(
                    WorkflowNodeExecution.execution_id == ex_id
                )
            )
        ).scalars().all()
        assert len(rows) == 4

    async def test_multiple_node_types_within_same_execution(self, db: AsyncSession):
        ex_id = await self._execution_id(db)
        for nt in ("agent", "condition", "transform", "output"):
            db.add(self._node_exec(ex_id, node_type=nt))
        await db.commit()

        rows = (
            await db.execute(
                select(WorkflowNodeExecution).where(
                    WorkflowNodeExecution.execution_id == ex_id
                )
            )
        ).scalars().all()
        node_types = {r.node_type for r in rows}
        assert node_types == {"agent", "condition", "transform", "output"}


# ===========================================================================
# ZKProof
# ===========================================================================

class TestZKProof:
    def _make(self, listing_id: str, proof_type: str = "merkle_root") -> ZKProof:
        return ZKProof(
            id=_new_id(),
            listing_id=listing_id,
            proof_type=proof_type,
            commitment="a" * 64,
        )

    async def test_create_minimal(self, db: AsyncSession):
        proof = self._make(_new_id())
        db.add(proof)
        await db.commit()
        await db.refresh(proof)
        assert proof.id is not None

    async def test_default_proof_data_json(self, db: AsyncSession):
        proof = self._make(_new_id())
        db.add(proof)
        await db.commit()
        await db.refresh(proof)
        assert proof.proof_data == "{}"

    async def test_default_public_inputs_json(self, db: AsyncSession):
        proof = self._make(_new_id())
        db.add(proof)
        await db.commit()
        await db.refresh(proof)
        assert proof.public_inputs == "{}"

    async def test_created_at_set(self, db: AsyncSession):
        proof = self._make(_new_id())
        db.add(proof)
        await db.commit()
        await db.refresh(proof)
        assert isinstance(proof.created_at, datetime)

    async def test_proof_type_merkle_root(self, db: AsyncSession):
        proof = self._make(_new_id(), "merkle_root")
        db.add(proof)
        await db.commit()
        await db.refresh(proof)
        assert proof.proof_type == "merkle_root"

    async def test_proof_type_schema(self, db: AsyncSession):
        proof = self._make(_new_id(), "schema")
        db.add(proof)
        await db.commit()
        await db.refresh(proof)
        assert proof.proof_type == "schema"

    async def test_proof_type_bloom_filter(self, db: AsyncSession):
        proof = self._make(_new_id(), "bloom_filter")
        db.add(proof)
        await db.commit()
        await db.refresh(proof)
        assert proof.proof_type == "bloom_filter"

    async def test_proof_type_metadata(self, db: AsyncSession):
        proof = self._make(_new_id(), "metadata")
        db.add(proof)
        await db.commit()
        await db.refresh(proof)
        assert proof.proof_type == "metadata"

    async def test_commitment_stored(self, db: AsyncSession):
        commitment = "f" * 64
        proof = ZKProof(
            id=_new_id(),
            listing_id=_new_id(),
            proof_type="merkle_root",
            commitment=commitment,
        )
        db.add(proof)
        await db.commit()
        await db.refresh(proof)
        assert proof.commitment == commitment

    async def test_proof_data_json_stored(self, db: AsyncSession):
        payload = '{"root":"abc","leaves":["x","y"]}'
        proof = ZKProof(
            id=_new_id(),
            listing_id=_new_id(),
            proof_type="merkle_root",
            commitment="a" * 64,
            proof_data=payload,
        )
        db.add(proof)
        await db.commit()
        await db.refresh(proof)
        assert proof.proof_data == payload

    async def test_public_inputs_json_stored(self, db: AsyncSession):
        inputs = '{"field_count":5,"row_count":100}'
        proof = ZKProof(
            id=_new_id(),
            listing_id=_new_id(),
            proof_type="schema",
            commitment="b" * 64,
            public_inputs=inputs,
        )
        db.add(proof)
        await db.commit()
        await db.refresh(proof)
        assert proof.public_inputs == inputs

    async def test_four_proof_types_for_same_listing(self, db: AsyncSession):
        """A listing can have up to four distinct proof-type rows."""
        listing_id = _new_id()
        for pt in ("merkle_root", "schema", "bloom_filter", "metadata"):
            db.add(ZKProof(
                id=_new_id(),
                listing_id=listing_id,
                proof_type=pt,
                commitment="c" * 64,
            ))
        await db.commit()

        rows = (
            await db.execute(
                select(ZKProof).where(ZKProof.listing_id == listing_id)
            )
        ).scalars().all()
        assert len(rows) == 4
        proof_types = {r.proof_type for r in rows}
        assert proof_types == {"merkle_root", "schema", "bloom_filter", "metadata"}

    async def test_query_by_proof_type(self, db: AsyncSession):
        lid = _new_id()
        db.add(ZKProof(id=_new_id(), listing_id=lid, proof_type="merkle_root", commitment="a" * 64))
        db.add(ZKProof(id=_new_id(), listing_id=lid, proof_type="schema", commitment="b" * 64))
        await db.commit()

        merkle_rows = (
            await db.execute(
                select(ZKProof).where(
                    ZKProof.listing_id == lid,
                    ZKProof.proof_type == "merkle_root",
                )
            )
        ).scalars().all()
        assert len(merkle_rows) == 1
        assert merkle_rows[0].proof_type == "merkle_root"

    async def test_listing_id_required(self, db: AsyncSession):
        """listing_id is NOT NULL — omitting it must raise."""
        proof = ZKProof(
            id=_new_id(),
            listing_id=None,    # violates NOT NULL
            proof_type="merkle_root",
            commitment="a" * 64,
        )
        db.add(proof)
        with pytest.raises((IntegrityError, Exception)):
            await db.commit()
        await db.rollback()
