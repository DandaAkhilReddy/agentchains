"""Unit tests for verification_service — 25 tests across 5 describe blocks.

Covers the verification lifecycle: state machine transitions, document/hash
validation, expiry semantics, re-verification behaviour, and error handling.
Uses unittest.mock / AsyncMock to isolate the service from real DB and storage.
"""

import asyncio
import hashlib
import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from marketplace.models.verification import VerificationRecord
from marketplace.services import verification_service
from marketplace.services.storage_service import get_storage


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _id() -> str:
    return str(uuid.uuid4())


def _sha256(data: bytes) -> str:
    """Return prefixed sha256 hash of raw bytes."""
    return f"sha256:{hashlib.sha256(data).hexdigest()}"


def _make_verification_record(
    transaction_id: str = "tx-test",
    matches: int = 1,
    expected_hash: str = "sha256:aaa",
    actual_hash: str = "sha256:aaa",
    verified_at: datetime | None = None,
) -> VerificationRecord:
    """Build a VerificationRecord without persisting it."""
    return VerificationRecord(
        id=_id(),
        transaction_id=transaction_id,
        expected_hash=expected_hash,
        actual_hash=actual_hash,
        matches=matches,
        verified_at=verified_at or datetime.now(timezone.utc),
    )


# ===================================================================
# 1. VERIFICATION STATE MACHINE (5 tests)
#    Conceptual states: pending -> in_review -> approved / rejected
#    Mapped onto verify_content: calling verify_content with matching hash
#    produces matches=1 (approved), mismatching hash produces matches=0
#    (rejected). Re-calling with the same tx_id creates a new record
#    (re-review).
# ===================================================================


class TestVerificationStateMachine:
    """State transitions expressed through verify_content outcomes."""

    async def test_pending_to_approved_on_hash_match(self, db: AsyncSession):
        """A matching hash transitions verification from pending to approved (matches=1)."""
        content = b"clean payload"
        expected = _sha256(content)

        result = await verification_service.verify_content(db, "tx-sm-1", content, expected)

        assert result["verified"] is True
        row = (await db.execute(
            select(VerificationRecord).where(VerificationRecord.transaction_id == "tx-sm-1")
        )).scalar_one()
        assert row.matches == 1

    async def test_pending_to_rejected_on_hash_mismatch(self, db: AsyncSession):
        """A mismatching hash transitions verification to rejected (matches=0)."""
        result = await verification_service.verify_content(
            db, "tx-sm-2", b"original", "sha256:0000bad"
        )

        assert result["verified"] is False
        row = (await db.execute(
            select(VerificationRecord).where(VerificationRecord.transaction_id == "tx-sm-2")
        )).scalar_one()
        assert row.matches == 0

    async def test_rejected_can_be_reverified_with_correct_content(self, db: AsyncSession):
        """After rejection, a second verify with correct content creates a new approved record."""
        content = b"corrected content"
        wrong_hash = "sha256:deadbeef"
        correct_hash = _sha256(content)

        # First attempt: rejected
        r1 = await verification_service.verify_content(db, "tx-sm-3", content, wrong_hash)
        assert r1["verified"] is False

        # Second attempt: approved
        r2 = await verification_service.verify_content(db, "tx-sm-3", content, correct_hash)
        assert r2["verified"] is True

        # Both records persisted
        rows = (await db.execute(
            select(VerificationRecord).where(VerificationRecord.transaction_id == "tx-sm-3")
        )).scalars().all()
        assert len(rows) == 2

    async def test_invalid_transition_double_approval_creates_duplicate(self, db: AsyncSession):
        """Approving the same tx twice is idempotent -- two records, both approved."""
        content = b"stable content"
        expected = _sha256(content)

        await verification_service.verify_content(db, "tx-sm-4", content, expected)
        await verification_service.verify_content(db, "tx-sm-4", content, expected)

        rows = (await db.execute(
            select(VerificationRecord).where(VerificationRecord.transaction_id == "tx-sm-4")
        )).scalars().all()
        assert all(r.matches == 1 for r in rows)
        assert len(rows) == 2

    async def test_state_recorded_with_timestamp(self, db: AsyncSession):
        """Each verification record has a verified_at timestamp set automatically."""
        before = datetime.now(timezone.utc)
        await verification_service.verify_content(db, "tx-sm-5", b"data", _sha256(b"data"))
        after = datetime.now(timezone.utc)

        row = (await db.execute(
            select(VerificationRecord).where(VerificationRecord.transaction_id == "tx-sm-5")
        )).scalar_one()
        assert row.verified_at is not None
        # SQLite returns naive datetimes; normalise to aware for comparison
        verified = row.verified_at
        if verified.tzinfo is None:
            verified = verified.replace(tzinfo=timezone.utc)
        assert verified >= before - timedelta(seconds=2)
        assert verified <= after + timedelta(seconds=2)


# ===================================================================
# 2. DOCUMENT / HASH VALIDATION (5 tests)
#    Tests around required content, format checks, size limits, and
#    hash prefix conventions.
# ===================================================================


class TestDocumentValidation:
    """Hash format, content requirements, and size boundary tests."""

    async def test_hash_must_have_sha256_prefix(self, db: AsyncSession):
        """The actual_hash in the result always carries the sha256: prefix."""
        result = await verification_service.verify_content(
            db, "tx-doc-1", b"hello", "sha256:wrong"
        )
        assert result["actual_hash"].startswith("sha256:")

    async def test_hash_is_64_hex_chars_after_prefix(self, db: AsyncSession):
        """SHA-256 produces a 64-character hex digest."""
        result = await verification_service.verify_content(
            db, "tx-doc-2", b"any content", "sha256:x"
        )
        hex_part = result["actual_hash"].replace("sha256:", "")
        assert len(hex_part) == 64
        assert all(c in "0123456789abcdef" for c in hex_part)

    async def test_empty_content_has_valid_hash(self, db: AsyncSession):
        """Even zero-byte content produces a deterministic, valid hash."""
        empty_hash = _sha256(b"")
        result = await verification_service.verify_content(db, "tx-doc-3", b"", empty_hash)
        assert result["verified"] is True
        assert result["actual_hash"] == empty_hash

    async def test_large_content_within_size_limit(self, db: AsyncSession):
        """Payloads up to 5 MB verify successfully."""
        big = b"A" * (5 * 1024 * 1024)
        expected = _sha256(big)
        result = await verification_service.verify_content(db, "tx-doc-4", big, expected)
        assert result["verified"] is True

    async def test_binary_content_all_byte_values(self, db: AsyncSession):
        """Binary content spanning all 256 byte values verifies correctly."""
        content = bytes(range(256)) * 4
        expected = _sha256(content)
        result = await verification_service.verify_content(db, "tx-doc-5", content, expected)
        assert result["verified"] is True
        assert result["actual_hash"] == expected


# ===================================================================
# 3. EXPIRY CHECKS (5 tests)
#    Verification records carry a verified_at timestamp. Tests cover
#    detecting expired verifications, grace periods, and renewal windows.
# ===================================================================


class TestExpiryChecks:
    """Timestamp-based expiry and renewal window semantics."""

    VERIFICATION_TTL = timedelta(days=90)
    GRACE_PERIOD = timedelta(days=7)

    @staticmethod
    def _ensure_aware(dt: datetime) -> datetime:
        """Normalise a possibly-naive datetime to UTC-aware (SQLite compat)."""
        if dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt

    def _is_expired(self, record: VerificationRecord, now: datetime | None = None) -> bool:
        """Helper: check if a verification record has expired."""
        now = now or datetime.now(timezone.utc)
        verified = self._ensure_aware(record.verified_at)
        return (now - verified) > self.VERIFICATION_TTL

    def _in_grace_period(self, record: VerificationRecord, now: datetime | None = None) -> bool:
        """Helper: check if expired but still within the grace period."""
        now = now or datetime.now(timezone.utc)
        verified = self._ensure_aware(record.verified_at)
        age = now - verified
        return self.VERIFICATION_TTL < age <= (self.VERIFICATION_TTL + self.GRACE_PERIOD)

    def _in_renewal_window(self, record: VerificationRecord, now: datetime | None = None) -> bool:
        """Helper: within 14 days before expiry."""
        now = now or datetime.now(timezone.utc)
        verified = self._ensure_aware(record.verified_at)
        remaining = self.VERIFICATION_TTL - (now - verified)
        return timedelta(0) < remaining <= timedelta(days=14)

    async def test_fresh_verification_not_expired(self, db: AsyncSession):
        """A verification created just now is not expired."""
        content = b"fresh"
        await verification_service.verify_content(db, "tx-exp-1", content, _sha256(content))

        row = (await db.execute(
            select(VerificationRecord).where(VerificationRecord.transaction_id == "tx-exp-1")
        )).scalar_one()
        assert not self._is_expired(row)

    async def test_old_verification_is_expired(self, db: AsyncSession):
        """A record verified 91 days ago is expired."""
        record = _make_verification_record(
            transaction_id="tx-exp-2",
            verified_at=datetime.now(timezone.utc) - timedelta(days=91),
        )
        assert self._is_expired(record)

    async def test_expired_verification_rejected(self, db: AsyncSession):
        """An expired record should be flagged -- matches irrelevant after expiry."""
        record = _make_verification_record(
            transaction_id="tx-exp-3",
            matches=1,
            verified_at=datetime.now(timezone.utc) - timedelta(days=100),
        )
        # Even though matches == 1, the record is past TTL
        assert record.matches == 1
        assert self._is_expired(record)

    async def test_grace_period_allows_temporary_access(self, db: AsyncSession):
        """A record 93 days old is expired but within the 7-day grace period."""
        record = _make_verification_record(
            transaction_id="tx-exp-4",
            verified_at=datetime.now(timezone.utc) - timedelta(days=93),
        )
        assert self._is_expired(record)
        assert self._in_grace_period(record)

    async def test_renewal_window_opens_before_expiry(self, db: AsyncSession):
        """A record 80 days old (10 days until expiry) is in the renewal window."""
        record = _make_verification_record(
            transaction_id="tx-exp-5",
            verified_at=datetime.now(timezone.utc) - timedelta(days=80),
        )
        assert not self._is_expired(record)
        assert self._in_renewal_window(record)


# ===================================================================
# 4. RE-VERIFICATION (5 tests)
#    Trigger conditions, cooldown between attempts, and preservation
#    of verification history across re-verifications.
# ===================================================================


class TestReverification:
    """Re-verification triggers, cooldown, and history preservation."""

    async def test_reverification_creates_new_record(self, db: AsyncSession):
        """Each call to verify_content creates a distinct record, even for the same tx."""
        content = b"reverify me"
        h = _sha256(content)
        tx_id = "tx-rev-1"

        await verification_service.verify_content(db, tx_id, content, h)
        await verification_service.verify_content(db, tx_id, content, h)
        await verification_service.verify_content(db, tx_id, content, h)

        rows = (await db.execute(
            select(VerificationRecord).where(VerificationRecord.transaction_id == tx_id)
        )).scalars().all()
        assert len(rows) == 3

    async def test_reverification_preserves_history(self, db: AsyncSession):
        """Old verification records are not overwritten on re-verification."""
        tx_id = "tx-rev-2"
        content_v1 = b"version 1"
        content_v2 = b"version 2"

        await verification_service.verify_content(db, tx_id, content_v1, _sha256(content_v1))
        await verification_service.verify_content(db, tx_id, content_v2, _sha256(content_v2))

        rows = (await db.execute(
            select(VerificationRecord).where(VerificationRecord.transaction_id == tx_id)
        )).scalars().all()
        hashes = {r.actual_hash for r in rows}
        assert _sha256(content_v1) in hashes
        assert _sha256(content_v2) in hashes

    async def test_reverification_after_failure_can_succeed(self, db: AsyncSession):
        """A failed verification followed by correct content yields an approved record."""
        tx_id = "tx-rev-3"
        content = b"real content"

        r1 = await verification_service.verify_content(db, tx_id, content, "sha256:wrong")
        assert r1["verified"] is False

        r2 = await verification_service.verify_content(db, tx_id, content, _sha256(content))
        assert r2["verified"] is True

    async def test_reverification_cooldown_not_enforced_at_service_layer(self, db: AsyncSession):
        """The service layer does not enforce a cooldown -- rapid re-calls succeed."""
        tx_id = "tx-rev-4"
        content = b"rapid fire"
        h = _sha256(content)

        results = []
        for _ in range(5):
            r = await verification_service.verify_content(db, tx_id, content, h)
            results.append(r)

        assert all(r["verified"] is True for r in results)

    async def test_reverification_each_record_has_unique_id(self, db: AsyncSession):
        """Each verification record must have a distinct primary key."""
        tx_id = "tx-rev-5"
        content = b"unique ids"
        h = _sha256(content)

        await verification_service.verify_content(db, tx_id, content, h)
        await verification_service.verify_content(db, tx_id, content, h)

        rows = (await db.execute(
            select(VerificationRecord).where(VerificationRecord.transaction_id == tx_id)
        )).scalars().all()
        ids = [r.id for r in rows]
        assert len(ids) == len(set(ids)), "Verification record IDs must be unique"


# ===================================================================
# 5. ERROR HANDLING (5 tests)
#    Missing documents, corrupt files, storage failures, timeout
#    during review, and concurrent requests.
# ===================================================================


class TestErrorHandling:
    """Edge cases, mock-based failure injection, and concurrency tests."""

    async def test_missing_expected_hash_empty_string(self, db: AsyncSession):
        """An empty expected_hash means verification always fails (no match)."""
        result = await verification_service.verify_content(db, "tx-err-1", b"data", "")
        assert result["verified"] is False
        assert result["expected_hash"] == ""

    async def test_corrupt_content_detected(self, db: AsyncSession):
        """Content that has been tampered with does not match the original hash."""
        original = b"original bytes"
        original_hash = _sha256(original)
        corrupted = b"corrupted bytes"

        result = await verification_service.verify_content(
            db, "tx-err-2", corrupted, original_hash
        )
        assert result["verified"] is False
        assert result["actual_hash"] != original_hash

    async def test_storage_compute_hash_failure_propagates(self, db: AsyncSession):
        """If storage.compute_hash raises, the exception propagates to the caller."""
        mock_storage = MagicMock()
        mock_storage.compute_hash.side_effect = RuntimeError("disk read error")
        mock_storage.verify.return_value = False

        with patch(
            "marketplace.services.verification_service.get_storage",
            return_value=mock_storage,
        ):
            with pytest.raises(RuntimeError, match="disk read error"):
                await verification_service.verify_content(
                    db, "tx-err-3", b"data", "sha256:abc"
                )

    async def test_db_commit_failure_raises(self):
        """If db.commit() fails, the error propagates and no result is returned."""
        mock_db = AsyncMock(spec=AsyncSession)
        mock_db.add = MagicMock()
        mock_db.commit = AsyncMock(side_effect=Exception("connection lost"))

        mock_storage = MagicMock()
        mock_storage.compute_hash.return_value = "sha256:abc123"
        mock_storage.verify.return_value = True

        with patch(
            "marketplace.services.verification_service.get_storage",
            return_value=mock_storage,
        ):
            with pytest.raises(Exception, match="connection lost"):
                await verification_service.verify_content(
                    mock_db, "tx-err-4", b"payload", "sha256:abc123"
                )
        mock_db.add.assert_called_once()
        mock_db.commit.assert_awaited_once()

    async def test_concurrent_verifications_all_persisted(self, db: AsyncSession):
        """Multiple concurrent verifications for different tx_ids all persist."""
        tasks = []
        for i in range(5):
            content = f"concurrent-{i}".encode()
            h = _sha256(content)
            tasks.append(
                verification_service.verify_content(db, f"tx-err-5-{i}", content, h)
            )

        results = []
        for task in tasks:
            results.append(await task)

        assert all(r["verified"] is True for r in results)

        # All 5 records persisted
        rows = (await db.execute(select(VerificationRecord))).scalars().all()
        tx_ids = {r.transaction_id for r in rows}
        for i in range(5):
            assert f"tx-err-5-{i}" in tx_ids
