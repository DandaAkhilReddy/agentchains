"""UT-6: Verification service + Audit service tests (30 tests)."""

import json
from datetime import datetime, timezone

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from marketplace.models.verification import VerificationRecord
from marketplace.services import audit_service, verification_service
from marketplace.services.storage_service import get_storage


class TestVerifyContent:
    """Tests for verification_service.verify_content()."""

    async def test_verify_content_matching_hash(self, db: AsyncSession):
        storage = get_storage()
        content = b"trusted content payload"
        expected_hash = storage.compute_hash(content)
        result = await verification_service.verify_content(db, "tx-001", content, expected_hash)
        assert result["verified"] is True
        assert result["actual_hash"] == expected_hash

    async def test_verify_content_mismatching_hash(self, db: AsyncSession):
        result = await verification_service.verify_content(db, "tx-002", b"tampered", "sha256:0000")
        assert result["verified"] is False

    async def test_verify_content_creates_db_record(self, db: AsyncSession):
        storage = get_storage()
        content = b"test content for record"
        expected = storage.compute_hash(content)
        await verification_service.verify_content(db, "tx-003", content, expected)
        rows = (await db.execute(select(VerificationRecord))).scalars().all()
        assert len(rows) == 1
        assert rows[0].transaction_id == "tx-003"
        assert rows[0].matches == 1

    async def test_verify_content_empty_bytes(self, db: AsyncSession):
        storage = get_storage()
        content = b""
        expected = storage.compute_hash(content)
        result = await verification_service.verify_content(db, "tx-004", content, expected)
        assert result["verified"] is True

    async def test_verify_content_large_payload(self, db: AsyncSession):
        storage = get_storage()
        content = b"X" * (1024 * 1024)
        expected = storage.compute_hash(content)
        result = await verification_service.verify_content(db, "tx-005", content, expected)
        assert result["verified"] is True

    async def test_verify_content_returns_both_hashes(self, db: AsyncSession):
        result = await verification_service.verify_content(db, "tx-006", b"abc", "sha256:bogus")
        assert "expected_hash" in result
        assert "actual_hash" in result
        assert result["expected_hash"] == "sha256:bogus"
        assert result["actual_hash"] != "sha256:bogus"

    async def test_verify_content_unicode_content(self, db: AsyncSession):
        storage = get_storage()
        content = "Hello world test".encode("utf-8")
        expected = storage.compute_hash(content)
        result = await verification_service.verify_content(db, "tx-007", content, expected)
        assert result["verified"] is True

    async def test_verify_content_binary_content(self, db: AsyncSession):
        storage = get_storage()
        content = bytes(range(256))
        expected = storage.compute_hash(content)
        result = await verification_service.verify_content(db, "tx-008", content, expected)
        assert result["verified"] is True

    async def test_verify_content_duplicate_verification(self, db: AsyncSession):
        storage = get_storage()
        content = b"duplicate check"
        expected = storage.compute_hash(content)
        await verification_service.verify_content(db, "tx-009", content, expected)
        await verification_service.verify_content(db, "tx-009", content, expected)
        rows = (await db.execute(
            select(VerificationRecord).where(VerificationRecord.transaction_id == "tx-009")
        )).scalars().all()
        assert len(rows) == 2

    async def test_verify_content_hash_format(self, db: AsyncSession):
        result = await verification_service.verify_content(db, "tx-010", b"format", "sha256:wrong")
        assert result["actual_hash"].startswith("sha256:")

    async def test_verify_content_preserves_transaction_id(self, db: AsyncSession):
        tx_id = "tx-custom-id-999"
        result = await verification_service.verify_content(db, tx_id, b"data", "sha256:x")
        assert result["transaction_id"] == tx_id

    async def test_verify_content_deterministic(self, db: AsyncSession):
        storage = get_storage()
        content = b"deterministic test"
        h1 = storage.compute_hash(content)
        h2 = storage.compute_hash(content)
        assert h1 == h2

    async def test_verify_content_single_bit_flip(self, db: AsyncSession):
        storage = get_storage()
        assert storage.compute_hash(b"payload-A") != storage.compute_hash(b"payload-B")

    async def test_verify_content_mismatch_record_matches_zero(self, db: AsyncSession):
        await verification_service.verify_content(db, "tx-014", b"wrong", "sha256:0000")
        rows = (await db.execute(select(VerificationRecord))).scalars().all()
        assert rows[0].matches == 0

    async def test_verify_content_null_expected_hash(self, db: AsyncSession):
        result = await verification_service.verify_content(db, "tx-015", b"data", "")
        assert result["verified"] is False


class TestAuditService:
    """Tests for audit_service.log_event()."""

    async def test_audit_log_event_basic(self, db: AsyncSession):
        entry = await audit_service.log_event(db, "agent_registered")
        assert entry.event_type == "agent_registered"
        assert entry.entry_hash is not None

    async def test_audit_log_event_genesis(self, db: AsyncSession):
        entry = await audit_service.log_event(db, "genesis")
        assert entry.prev_hash is None

    async def test_audit_chain_linking(self, db: AsyncSession):
        e1 = await audit_service.log_event(db, "first")
        await db.commit()
        e2 = await audit_service.log_event(db, "second")
        assert e2.prev_hash == e1.entry_hash

    async def test_audit_chain_three_entries(self, db: AsyncSession):
        e1 = await audit_service.log_event(db, "e1")
        await db.commit()
        e2 = await audit_service.log_event(db, "e2")
        await db.commit()
        e3 = await audit_service.log_event(db, "e3")
        assert e1.prev_hash is None
        assert e2.prev_hash == e1.entry_hash
        assert e3.prev_hash == e2.entry_hash

    async def test_audit_log_with_agent_id(self, db: AsyncSession):
        entry = await audit_service.log_event(db, "test", agent_id="agent-123")
        assert entry.agent_id == "agent-123"

    async def test_audit_log_with_creator_id(self, db: AsyncSession):
        entry = await audit_service.log_event(db, "test", creator_id="creator-456")
        assert entry.creator_id == "creator-456"

    async def test_audit_log_with_ip_address(self, db: AsyncSession):
        entry = await audit_service.log_event(db, "test", ip_address="192.168.1.1")
        assert entry.ip_address == "192.168.1.1"

    async def test_audit_log_with_details(self, db: AsyncSession):
        details = {"action": "purchase", "amount": 50}
        entry = await audit_service.log_event(db, "test", details=details)
        parsed = json.loads(entry.details)
        assert parsed["action"] == "purchase"
        assert parsed["amount"] == 50

    async def test_audit_log_severity_info(self, db: AsyncSession):
        entry = await audit_service.log_event(db, "test")
        assert entry.severity == "info"

    async def test_audit_log_severity_warning(self, db: AsyncSession):
        entry = await audit_service.log_event(db, "test", severity="warning")
        assert entry.severity == "warning"

    async def test_audit_log_severity_critical(self, db: AsyncSession):
        entry = await audit_service.log_event(db, "test", severity="critical")
        assert entry.severity == "critical"

    async def test_audit_log_complex_details(self, db: AsyncSession):
        details = {"items": [{"id": 1}, {"id": 2}], "meta": {"v": 3}}
        entry = await audit_service.log_event(db, "test", details=details)
        parsed = json.loads(entry.details)
        assert len(parsed["items"]) == 2
        assert parsed["meta"]["v"] == 3

    async def test_audit_log_non_serializable_details(self, db: AsyncSession):
        now = datetime.now(timezone.utc)
        details = {"timestamp": now, "value": 42}
        entry = await audit_service.log_event(db, "test", details=details)
        parsed = json.loads(entry.details)
        assert str(now) in parsed["timestamp"]

    async def test_audit_log_empty_details(self, db: AsyncSession):
        entry = await audit_service.log_event(db, "test", details={})
        assert entry.details == "{}"

    async def test_audit_concurrent_entries(self, db: AsyncSession):
        entries = []
        for i in range(5):
            e = await audit_service.log_event(db, f"event-{i}")
            await db.commit()
            entries.append(e)
        for i in range(1, len(entries)):
            assert entries[i].prev_hash == entries[i - 1].entry_hash
