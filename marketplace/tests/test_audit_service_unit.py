"""Unit tests for the audit_service module.

25 tests across 5 describe blocks:
  - Audit log creation (1-5)
  - Compliance checks (6-10)
  - Tamper detection (11-15)
  - Retention policies (16-20)
  - Search & filtering (21-25)

Written as direct service-layer tests using the in-memory SQLite backend
from conftest. No HTTP layer involved.
"""

import hashlib
import json
import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from marketplace.core.hashing import compute_audit_hash
from marketplace.models.audit_log import AuditLog
from marketplace.services.audit_service import log_event
from marketplace.tests.conftest import TestSession


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _uid() -> str:
    return str(uuid.uuid4())


async def _insert_event(db: AsyncSession, **overrides) -> AuditLog:
    """Thin wrapper around log_event with sensible defaults."""
    defaults = {
        "event_type": "agent.registered",
        "agent_id": _uid(),
        "details": {"key": "value"},
        "severity": "info",
    }
    defaults.update(overrides)
    return await log_event(db, defaults.pop("event_type"), **defaults)


# ===========================================================================
# 1. AUDIT LOG CREATION (tests 1-5)
# ===========================================================================


class TestAuditLogCreation:
    """Verify that log_event correctly persists audit entries."""

    @pytest.mark.asyncio
    async def test_log_event_returns_audit_log_instance(self, db: AsyncSession):
        """1. log_event returns an AuditLog ORM object."""
        entry = await log_event(db, "agent.registered", agent_id=_uid())
        assert isinstance(entry, AuditLog)
        assert entry.event_type == "agent.registered"

    @pytest.mark.asyncio
    async def test_log_event_persists_required_fields(self, db: AsyncSession):
        """2. All required fields are populated on the persisted entry."""
        agent_id = _uid()
        entry = await log_event(
            db, "listing.created", agent_id=agent_id, severity="warning",
        )
        assert entry.event_type == "listing.created"
        assert entry.agent_id == agent_id
        assert entry.severity == "warning"
        assert entry.entry_hash is not None
        assert entry.id is not None

    @pytest.mark.asyncio
    async def test_log_event_captures_metadata(self, db: AsyncSession):
        """3. Optional metadata fields (ip_address, user_agent, details) are stored."""
        entry = await log_event(
            db,
            "transaction.completed",
            agent_id=_uid(),
            ip_address="192.168.1.42",
            user_agent="TestBot/1.0",
            details={"amount": 99.5, "currency": "USD"},
        )
        assert entry.ip_address == "192.168.1.42"
        assert entry.user_agent == "TestBot/1.0"
        parsed = json.loads(entry.details)
        assert parsed["amount"] == 99.5
        assert parsed["currency"] == "USD"

    @pytest.mark.asyncio
    async def test_log_event_sets_utc_timestamp(self, db: AsyncSession):
        """4. created_at is set to a recent UTC timestamp."""
        before = datetime.now(timezone.utc)
        entry = await log_event(db, "agent.heartbeat", agent_id=_uid())
        after = datetime.now(timezone.utc)

        # created_at should be between before and after (allow for tz-naive SQLite round-trip)
        ts = entry.created_at
        if ts.tzinfo is not None:
            ts = ts.replace(tzinfo=None)
        before_naive = before.replace(tzinfo=None)
        after_naive = after.replace(tzinfo=None)
        assert before_naive <= ts <= after_naive

    @pytest.mark.asyncio
    async def test_log_event_serializes_details_deterministically(self, db: AsyncSession):
        """5. Details dict is serialized with sort_keys for deterministic hashing."""
        entry = await log_event(
            db, "test.event", agent_id=_uid(),
            details={"zebra": 1, "alpha": 2, "middle": 3},
        )
        parsed = json.loads(entry.details)
        keys = list(parsed.keys())
        assert keys == sorted(keys), "Details JSON keys must be sorted"


# ===========================================================================
# 2. COMPLIANCE CHECKS (tests 6-10)
# ===========================================================================


class TestComplianceChecks:
    """Verify event type validation, severity levels, and actor identification."""

    @pytest.mark.asyncio
    async def test_event_type_stored_exactly(self, db: AsyncSession):
        """6. Event type string is stored verbatim."""
        entry = await log_event(db, "agent.deactivated", agent_id=_uid())
        assert entry.event_type == "agent.deactivated"

    @pytest.mark.asyncio
    async def test_severity_defaults_to_info(self, db: AsyncSession):
        """7. Severity defaults to 'info' when not specified."""
        entry = await log_event(db, "agent.registered", agent_id=_uid())
        assert entry.severity == "info"

    @pytest.mark.asyncio
    async def test_severity_levels_accepted(self, db: AsyncSession):
        """8. Various severity levels are accepted and stored."""
        levels = ["info", "warning", "error", "critical"]
        for level in levels:
            entry = await log_event(
                db, "test.severity", agent_id=_uid(), severity=level,
            )
            assert entry.severity == level

    @pytest.mark.asyncio
    async def test_actor_identified_by_agent_id(self, db: AsyncSession):
        """9. Agent-initiated events store agent_id as the actor."""
        agent_id = _uid()
        entry = await log_event(
            db, "listing.purchased", agent_id=agent_id,
        )
        assert entry.agent_id == agent_id
        assert entry.creator_id is None

    @pytest.mark.asyncio
    async def test_actor_identified_by_creator_id(self, db: AsyncSession):
        """10. Creator-initiated events store creator_id as the actor."""
        creator_id = _uid()
        entry = await log_event(
            db, "content.uploaded", creator_id=creator_id,
        )
        assert entry.creator_id == creator_id
        assert entry.agent_id is None


# ===========================================================================
# 3. TAMPER DETECTION (tests 11-15)
# ===========================================================================


class TestTamperDetection:
    """Verify hash chain integrity, gap detection, and tamper resistance."""

    @pytest.mark.asyncio
    async def test_first_entry_has_no_prev_hash(self, db: AsyncSession):
        """11. The very first entry in the chain has prev_hash=None (genesis)."""
        entry = await log_event(db, "genesis.event", agent_id=_uid())
        assert entry.prev_hash is None

    @pytest.mark.asyncio
    async def test_hash_chain_links_consecutive_entries(self, db: AsyncSession):
        """12. Each entry's prev_hash equals the previous entry's entry_hash."""
        e1 = await log_event(db, "chain.first", agent_id=_uid())
        e2 = await log_event(db, "chain.second", agent_id=_uid())
        e3 = await log_event(db, "chain.third", agent_id=_uid())

        assert e2.prev_hash == e1.entry_hash
        assert e3.prev_hash == e2.entry_hash

    @pytest.mark.asyncio
    async def test_entry_hash_is_sha256_hex(self, db: AsyncSession):
        """13. entry_hash is a valid 64-character SHA-256 hex digest."""
        entry = await log_event(db, "hash.test", agent_id=_uid())
        assert len(entry.entry_hash) == 64
        # Verify it is valid hex
        int(entry.entry_hash, 16)

    @pytest.mark.asyncio
    async def test_tampered_entry_detected_by_recompute(self, db: AsyncSession):
        """14. Modifying an entry's details breaks the hash chain verification."""
        e1 = await log_event(db, "tamper.test", agent_id=_uid(), details={"original": True})
        e2 = await log_event(db, "tamper.next", agent_id=_uid())
        await db.commit()

        # Tamper with e1's details without updating its hash
        await db.execute(
            update(AuditLog)
            .where(AuditLog.id == e1.id)
            .values(details=json.dumps({"tampered": True}))
        )
        await db.commit()

        # Recompute and verify the hash no longer matches
        result = await db.execute(
            select(AuditLog).where(AuditLog.id == e1.id)
        )
        tampered = result.scalar_one()
        recomputed = compute_audit_hash(
            tampered.prev_hash,
            tampered.event_type,
            tampered.agent_id or tampered.creator_id,
            tampered.details,
            tampered.severity,
            tampered.created_at.isoformat(),
        )
        assert recomputed != tampered.entry_hash, "Tampered entry hash should not match"

    @pytest.mark.asyncio
    async def test_hash_uses_genesis_for_first_entry(self, db: AsyncSession):
        """15. compute_audit_hash uses 'GENESIS' when prev_hash is None."""
        agent_id = _uid()
        entry = await log_event(
            db, "genesis.check", agent_id=agent_id, details={"seq": 0},
        )
        expected = compute_audit_hash(
            None,  # GENESIS
            "genesis.check",
            agent_id,
            entry.details,
            "info",
            entry.created_at.isoformat(),
        )
        assert entry.entry_hash == expected


# ===========================================================================
# 4. RETENTION POLICIES (tests 16-20)
# ===========================================================================


class TestRetentionPolicies:
    """Verify log rotation, TTL enforcement, archival, and bulk cleanup."""

    @pytest.mark.asyncio
    async def test_old_entries_identifiable_by_created_at(self, db: AsyncSession):
        """16. Entries older than a TTL threshold can be queried for cleanup."""
        # Insert an entry, then backdate it
        entry = await log_event(db, "old.event", agent_id=_uid())
        old_ts = datetime.now(timezone.utc) - timedelta(days=91)
        await db.execute(
            update(AuditLog).where(AuditLog.id == entry.id).values(created_at=old_ts)
        )
        await db.commit()

        # Query for entries older than 90 days
        cutoff = datetime.now(timezone.utc) - timedelta(days=90)
        result = await db.execute(
            select(func.count(AuditLog.id)).where(AuditLog.created_at < cutoff)
        )
        count = result.scalar()
        assert count == 1

    @pytest.mark.asyncio
    async def test_bulk_delete_old_entries(self, db: AsyncSession):
        """17. Bulk deletion removes entries beyond retention period."""
        # Create 3 entries and backdate 2 of them
        e1 = await log_event(db, "retain.new", agent_id=_uid())
        e2 = await log_event(db, "retain.old1", agent_id=_uid())
        e3 = await log_event(db, "retain.old2", agent_id=_uid())
        await db.commit()

        old_ts = datetime.now(timezone.utc) - timedelta(days=365)
        await db.execute(
            update(AuditLog)
            .where(AuditLog.id.in_([e2.id, e3.id]))
            .values(created_at=old_ts)
        )
        await db.commit()

        # Bulk delete entries older than 90 days
        cutoff = datetime.now(timezone.utc) - timedelta(days=90)
        await db.execute(
            delete(AuditLog).where(AuditLog.created_at < cutoff)
        )
        await db.commit()

        remaining = await db.execute(select(func.count(AuditLog.id)))
        assert remaining.scalar() == 1

    @pytest.mark.asyncio
    async def test_recent_entries_survive_cleanup(self, db: AsyncSession):
        """18. Entries within retention window are not affected by cleanup."""
        recent = await log_event(db, "fresh.event", agent_id=_uid())
        await db.commit()

        cutoff = datetime.now(timezone.utc) - timedelta(days=90)
        await db.execute(
            delete(AuditLog).where(AuditLog.created_at < cutoff)
        )
        await db.commit()

        result = await db.execute(select(AuditLog).where(AuditLog.id == recent.id))
        assert result.scalar_one_or_none() is not None

    @pytest.mark.asyncio
    async def test_archival_query_returns_date_sorted(self, db: AsyncSession):
        """19. Archival export query returns entries in chronological order."""
        ids = []
        for i in range(5):
            entry = await log_event(
                db, "archive.event", agent_id=_uid(), details={"seq": i},
            )
            ids.append(entry.id)
        await db.commit()

        result = await db.execute(
            select(AuditLog).order_by(AuditLog.created_at.asc())
        )
        entries = result.scalars().all()
        # Normalize to naive UTC for comparison (aiosqlite may strip tz info)
        timestamps = [
            e.created_at.replace(tzinfo=None) if e.created_at.tzinfo else e.created_at
            for e in entries
        ]
        assert timestamps == sorted(timestamps)

    @pytest.mark.asyncio
    async def test_count_by_severity_for_rotation_decisions(self, db: AsyncSession):
        """20. Count of entries by severity supports rotation policy decisions."""
        for _ in range(3):
            await log_event(db, "count.info", agent_id=_uid(), severity="info")
        for _ in range(2):
            await log_event(db, "count.warn", agent_id=_uid(), severity="warning")
        await log_event(db, "count.error", agent_id=_uid(), severity="error")
        await db.commit()

        result = await db.execute(
            select(AuditLog.severity, func.count(AuditLog.id))
            .group_by(AuditLog.severity)
        )
        counts = {row[0]: row[1] for row in result.all()}
        assert counts["info"] == 3
        assert counts["warning"] == 2
        assert counts["error"] == 1


# ===========================================================================
# 5. SEARCH & FILTERING (tests 21-25)
# ===========================================================================


class TestSearchAndFiltering:
    """Verify filtering by actor, action type, date range, severity, and combined."""

    @pytest.mark.asyncio
    async def test_filter_by_agent_id(self, db: AsyncSession):
        """21. Filtering by agent_id returns only that agent's entries."""
        target_agent = _uid()
        other_agent = _uid()

        await log_event(db, "agent.action", agent_id=target_agent)
        await log_event(db, "agent.action", agent_id=target_agent)
        await log_event(db, "agent.action", agent_id=other_agent)
        await db.commit()

        result = await db.execute(
            select(AuditLog).where(AuditLog.agent_id == target_agent)
        )
        entries = result.scalars().all()
        assert len(entries) == 2
        assert all(e.agent_id == target_agent for e in entries)

    @pytest.mark.asyncio
    async def test_filter_by_event_type(self, db: AsyncSession):
        """22. Filtering by event_type returns matching entries only."""
        await log_event(db, "listing.created", agent_id=_uid())
        await log_event(db, "listing.created", agent_id=_uid())
        await log_event(db, "transaction.completed", agent_id=_uid())
        await db.commit()

        result = await db.execute(
            select(AuditLog).where(AuditLog.event_type == "listing.created")
        )
        entries = result.scalars().all()
        assert len(entries) == 2
        assert all(e.event_type == "listing.created" for e in entries)

    @pytest.mark.asyncio
    async def test_filter_by_date_range(self, db: AsyncSession):
        """23. Filtering by date range returns entries within the window."""
        e1 = await log_event(db, "date.range", agent_id=_uid())
        e2 = await log_event(db, "date.range", agent_id=_uid())
        e3 = await log_event(db, "date.range", agent_id=_uid())
        await db.commit()

        # Backdate e1 to 30 days ago
        old_ts = datetime.now(timezone.utc) - timedelta(days=30)
        await db.execute(
            update(AuditLog).where(AuditLog.id == e1.id).values(created_at=old_ts)
        )
        await db.commit()

        # Query for entries from the last 7 days
        cutoff = datetime.now(timezone.utc) - timedelta(days=7)
        result = await db.execute(
            select(AuditLog).where(AuditLog.created_at >= cutoff)
        )
        entries = result.scalars().all()
        assert len(entries) == 2
        entry_ids = {e.id for e in entries}
        assert e1.id not in entry_ids

    @pytest.mark.asyncio
    async def test_filter_by_severity(self, db: AsyncSession):
        """24. Filtering by severity returns only matching entries."""
        await log_event(db, "sev.info", agent_id=_uid(), severity="info")
        await log_event(db, "sev.error", agent_id=_uid(), severity="error")
        await log_event(db, "sev.error", agent_id=_uid(), severity="error")
        await db.commit()

        result = await db.execute(
            select(AuditLog).where(AuditLog.severity == "error")
        )
        entries = result.scalars().all()
        assert len(entries) == 2
        assert all(e.severity == "error" for e in entries)

    @pytest.mark.asyncio
    async def test_combined_filters(self, db: AsyncSession):
        """25. Combining agent_id + event_type + severity narrows results correctly."""
        target_agent = _uid()
        other_agent = _uid()

        # Target: agent=target, type=listing.created, severity=warning
        await log_event(
            db, "listing.created", agent_id=target_agent, severity="warning",
        )
        # Same agent, different type
        await log_event(
            db, "agent.heartbeat", agent_id=target_agent, severity="warning",
        )
        # Same type & severity, different agent
        await log_event(
            db, "listing.created", agent_id=other_agent, severity="warning",
        )
        # Same agent & type, different severity
        await log_event(
            db, "listing.created", agent_id=target_agent, severity="info",
        )
        await db.commit()

        result = await db.execute(
            select(AuditLog).where(
                AuditLog.agent_id == target_agent,
                AuditLog.event_type == "listing.created",
                AuditLog.severity == "warning",
            )
        )
        entries = result.scalars().all()
        assert len(entries) == 1
        entry = entries[0]
        assert entry.agent_id == target_agent
        assert entry.event_type == "listing.created"
        assert entry.severity == "warning"
