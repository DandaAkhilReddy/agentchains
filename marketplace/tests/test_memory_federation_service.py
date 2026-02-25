"""Tests for Memory Federation Service — cross-agent memory sharing.

Covers:
- create_share_policy: basic creation, public share, with expiry, with read limits
- revoke_share_policy: success, nonexistent policy
- list_shared_with_me: targeted + public shares, excludes revoked
- list_my_shares: owner shares including revoked
- check_access: read/write/delete level checks, expiration, daily read limits
- log_access: audit log creation
- get_access_audit: filtering by accessor, limit
- MemoryFederationService class wrapper
"""

import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from marketplace.models.memory_share import MemoryAccessLog, MemorySharePolicy
from marketplace.services.memory_federation_service import (
    MemoryFederationService,
    check_access,
    create_share_policy,
    get_access_audit,
    list_my_shares,
    list_shared_with_me,
    log_access,
    revoke_share_policy,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

OWNER_ID = "owner-agent-001"
TARGET_ID = "target-agent-002"
OTHER_ID = "other-agent-003"
NAMESPACE = "conversation_history"


# ---------------------------------------------------------------------------
# create_share_policy
# ---------------------------------------------------------------------------

class TestCreateSharePolicy:
    async def test_create_basic_policy(self, db: AsyncSession):
        policy = await create_share_policy(
            db,
            owner_agent_id=OWNER_ID,
            memory_namespace=NAMESPACE,
            target_agent_id=TARGET_ID,
        )

        assert policy.id is not None
        assert policy.owner_agent_id == OWNER_ID
        assert policy.target_agent_id == TARGET_ID
        assert policy.memory_namespace == NAMESPACE
        assert policy.access_level == "read"
        assert policy.allow_derivative is False
        assert policy.max_reads_per_day is None
        assert policy.expires_at is None
        assert policy.status == "active"

    async def test_create_public_share(self, db: AsyncSession):
        policy = await create_share_policy(
            db,
            owner_agent_id=OWNER_ID,
            memory_namespace=NAMESPACE,
            target_agent_id=None,
        )

        assert policy.target_agent_id is None

    async def test_create_write_access(self, db: AsyncSession):
        policy = await create_share_policy(
            db,
            owner_agent_id=OWNER_ID,
            memory_namespace=NAMESPACE,
            target_agent_id=TARGET_ID,
            access_level="write",
        )

        assert policy.access_level == "write"

    async def test_create_admin_access(self, db: AsyncSession):
        policy = await create_share_policy(
            db,
            owner_agent_id=OWNER_ID,
            memory_namespace=NAMESPACE,
            target_agent_id=TARGET_ID,
            access_level="admin",
        )

        assert policy.access_level == "admin"

    async def test_create_with_read_limit(self, db: AsyncSession):
        policy = await create_share_policy(
            db,
            owner_agent_id=OWNER_ID,
            memory_namespace=NAMESPACE,
            target_agent_id=TARGET_ID,
            max_reads_per_day=100,
        )

        assert policy.max_reads_per_day == 100

    async def test_create_with_expiry(self, db: AsyncSession):
        expiry = datetime.now(timezone.utc) + timedelta(days=7)
        policy = await create_share_policy(
            db,
            owner_agent_id=OWNER_ID,
            memory_namespace=NAMESPACE,
            target_agent_id=TARGET_ID,
            expires_at=expiry,
        )

        assert policy.expires_at is not None

    async def test_create_with_derivative_allowed(self, db: AsyncSession):
        policy = await create_share_policy(
            db,
            owner_agent_id=OWNER_ID,
            memory_namespace=NAMESPACE,
            target_agent_id=TARGET_ID,
            allow_derivative=True,
        )

        assert policy.allow_derivative is True


# ---------------------------------------------------------------------------
# revoke_share_policy
# ---------------------------------------------------------------------------

class TestRevokeSharePolicy:
    async def test_revoke_existing_policy(self, db: AsyncSession):
        policy = await create_share_policy(
            db,
            owner_agent_id=OWNER_ID,
            memory_namespace=NAMESPACE,
            target_agent_id=TARGET_ID,
        )

        result = await revoke_share_policy(db, policy.id)
        assert result is True

        # Verify status changed
        from sqlalchemy import select
        stmt = select(MemorySharePolicy).where(MemorySharePolicy.id == policy.id)
        row = (await db.execute(stmt)).scalar_one()
        assert row.status == "revoked"

    async def test_revoke_nonexistent_returns_false(self, db: AsyncSession):
        result = await revoke_share_policy(db, "nonexistent-policy-id")
        assert result is False


# ---------------------------------------------------------------------------
# list_shared_with_me
# ---------------------------------------------------------------------------

class TestListSharedWithMe:
    async def test_returns_targeted_shares(self, db: AsyncSession):
        await create_share_policy(
            db,
            owner_agent_id=OWNER_ID,
            memory_namespace="ns1",
            target_agent_id=TARGET_ID,
        )
        await create_share_policy(
            db,
            owner_agent_id=OWNER_ID,
            memory_namespace="ns2",
            target_agent_id=OTHER_ID,
        )

        shares = await list_shared_with_me(db, TARGET_ID)
        assert len(shares) == 1
        assert shares[0].memory_namespace == "ns1"

    async def test_includes_public_shares(self, db: AsyncSession):
        await create_share_policy(
            db,
            owner_agent_id=OWNER_ID,
            memory_namespace="public_ns",
            target_agent_id=None,
        )

        shares = await list_shared_with_me(db, TARGET_ID)
        assert len(shares) == 1
        assert shares[0].target_agent_id is None

    async def test_excludes_revoked_shares(self, db: AsyncSession):
        policy = await create_share_policy(
            db,
            owner_agent_id=OWNER_ID,
            memory_namespace="revoked_ns",
            target_agent_id=TARGET_ID,
        )
        await revoke_share_policy(db, policy.id)

        shares = await list_shared_with_me(db, TARGET_ID)
        assert len(shares) == 0

    async def test_returns_both_targeted_and_public(self, db: AsyncSession):
        await create_share_policy(
            db,
            owner_agent_id=OWNER_ID,
            memory_namespace="targeted_ns",
            target_agent_id=TARGET_ID,
        )
        await create_share_policy(
            db,
            owner_agent_id=OWNER_ID,
            memory_namespace="public_ns",
            target_agent_id=None,
        )

        shares = await list_shared_with_me(db, TARGET_ID)
        assert len(shares) == 2

    async def test_empty_when_no_shares(self, db: AsyncSession):
        shares = await list_shared_with_me(db, "no-shares-agent")
        assert shares == []


# ---------------------------------------------------------------------------
# list_my_shares
# ---------------------------------------------------------------------------

class TestListMyShares:
    async def test_returns_all_owner_policies(self, db: AsyncSession):
        await create_share_policy(
            db,
            owner_agent_id=OWNER_ID,
            memory_namespace="ns1",
            target_agent_id=TARGET_ID,
        )
        await create_share_policy(
            db,
            owner_agent_id=OWNER_ID,
            memory_namespace="ns2",
            target_agent_id=OTHER_ID,
        )

        shares = await list_my_shares(db, OWNER_ID)
        assert len(shares) == 2

    async def test_includes_revoked_policies(self, db: AsyncSession):
        policy = await create_share_policy(
            db,
            owner_agent_id=OWNER_ID,
            memory_namespace="ns1",
            target_agent_id=TARGET_ID,
        )
        await revoke_share_policy(db, policy.id)

        shares = await list_my_shares(db, OWNER_ID)
        assert len(shares) == 1
        assert shares[0].status == "revoked"

    async def test_empty_for_other_owner(self, db: AsyncSession):
        await create_share_policy(
            db,
            owner_agent_id=OWNER_ID,
            memory_namespace="ns1",
            target_agent_id=TARGET_ID,
        )

        shares = await list_my_shares(db, OTHER_ID)
        assert shares == []


# ---------------------------------------------------------------------------
# check_access
# ---------------------------------------------------------------------------

class TestCheckAccess:
    async def test_read_access_with_read_policy(self, db: AsyncSession):
        await create_share_policy(
            db,
            owner_agent_id=OWNER_ID,
            memory_namespace=NAMESPACE,
            target_agent_id=TARGET_ID,
            access_level="read",
        )

        policy = await check_access(
            db,
            accessor_agent_id=TARGET_ID,
            owner_agent_id=OWNER_ID,
            memory_namespace=NAMESPACE,
            action="read",
        )
        assert policy is not None
        assert policy.access_level == "read"

    async def test_write_denied_with_read_policy(self, db: AsyncSession):
        await create_share_policy(
            db,
            owner_agent_id=OWNER_ID,
            memory_namespace=NAMESPACE,
            target_agent_id=TARGET_ID,
            access_level="read",
        )

        policy = await check_access(
            db,
            accessor_agent_id=TARGET_ID,
            owner_agent_id=OWNER_ID,
            memory_namespace=NAMESPACE,
            action="write",
        )
        assert policy is None

    async def test_write_access_with_write_policy(self, db: AsyncSession):
        await create_share_policy(
            db,
            owner_agent_id=OWNER_ID,
            memory_namespace=NAMESPACE,
            target_agent_id=TARGET_ID,
            access_level="write",
        )

        policy = await check_access(
            db,
            accessor_agent_id=TARGET_ID,
            owner_agent_id=OWNER_ID,
            memory_namespace=NAMESPACE,
            action="write",
        )
        assert policy is not None

    async def test_read_access_with_write_policy(self, db: AsyncSession):
        """Write policy also grants read access."""
        await create_share_policy(
            db,
            owner_agent_id=OWNER_ID,
            memory_namespace=NAMESPACE,
            target_agent_id=TARGET_ID,
            access_level="write",
        )

        policy = await check_access(
            db,
            accessor_agent_id=TARGET_ID,
            owner_agent_id=OWNER_ID,
            memory_namespace=NAMESPACE,
            action="read",
        )
        assert policy is not None

    async def test_delete_requires_admin(self, db: AsyncSession):
        await create_share_policy(
            db,
            owner_agent_id=OWNER_ID,
            memory_namespace=NAMESPACE,
            target_agent_id=TARGET_ID,
            access_level="write",
        )

        policy = await check_access(
            db,
            accessor_agent_id=TARGET_ID,
            owner_agent_id=OWNER_ID,
            memory_namespace=NAMESPACE,
            action="delete",
        )
        assert policy is None

    async def test_delete_with_admin_policy(self, db: AsyncSession):
        await create_share_policy(
            db,
            owner_agent_id=OWNER_ID,
            memory_namespace=NAMESPACE,
            target_agent_id=TARGET_ID,
            access_level="admin",
        )

        policy = await check_access(
            db,
            accessor_agent_id=TARGET_ID,
            owner_agent_id=OWNER_ID,
            memory_namespace=NAMESPACE,
            action="delete",
        )
        assert policy is not None

    async def test_expired_policy_denied(self, db: AsyncSession):
        # Use naive datetime because SQLite strips timezone info from stored values.
        # The service code uses datetime.now(timezone.utc), so we patch it to return
        # a naive datetime that is consistent with what SQLite returns.
        past = datetime.utcnow() - timedelta(hours=1)
        await create_share_policy(
            db,
            owner_agent_id=OWNER_ID,
            memory_namespace=NAMESPACE,
            target_agent_id=TARGET_ID,
            expires_at=past,
        )

        fake_now = datetime.utcnow() + timedelta(seconds=10)
        with patch(
            "marketplace.services.memory_federation_service.datetime"
        ) as mock_dt:
            mock_dt.now.return_value = fake_now
            mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)

            policy = await check_access(
                db,
                accessor_agent_id=TARGET_ID,
                owner_agent_id=OWNER_ID,
                memory_namespace=NAMESPACE,
                action="read",
            )
        assert policy is None

    async def test_expired_policy_status_updated_to_expired(self, db: AsyncSession):
        past = datetime.utcnow() - timedelta(hours=1)
        created = await create_share_policy(
            db,
            owner_agent_id=OWNER_ID,
            memory_namespace=NAMESPACE,
            target_agent_id=TARGET_ID,
            expires_at=past,
        )

        fake_now = datetime.utcnow() + timedelta(seconds=10)
        with patch(
            "marketplace.services.memory_federation_service.datetime"
        ) as mock_dt:
            mock_dt.now.return_value = fake_now
            mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)

            await check_access(
                db,
                accessor_agent_id=TARGET_ID,
                owner_agent_id=OWNER_ID,
                memory_namespace=NAMESPACE,
                action="read",
            )

        # Refresh to see the status change
        from sqlalchemy import select
        stmt = select(MemorySharePolicy).where(MemorySharePolicy.id == created.id)
        row = (await db.execute(stmt)).scalar_one()
        assert row.status == "expired"

    async def test_public_share_accessible_by_anyone(self, db: AsyncSession):
        await create_share_policy(
            db,
            owner_agent_id=OWNER_ID,
            memory_namespace=NAMESPACE,
            target_agent_id=None,
        )

        policy = await check_access(
            db,
            accessor_agent_id="random-agent-xyz",
            owner_agent_id=OWNER_ID,
            memory_namespace=NAMESPACE,
            action="read",
        )
        assert policy is not None

    async def test_wrong_namespace_denied(self, db: AsyncSession):
        await create_share_policy(
            db,
            owner_agent_id=OWNER_ID,
            memory_namespace="allowed_ns",
            target_agent_id=TARGET_ID,
        )

        policy = await check_access(
            db,
            accessor_agent_id=TARGET_ID,
            owner_agent_id=OWNER_ID,
            memory_namespace="different_ns",
            action="read",
        )
        assert policy is None

    async def test_revoked_policy_denied(self, db: AsyncSession):
        created = await create_share_policy(
            db,
            owner_agent_id=OWNER_ID,
            memory_namespace=NAMESPACE,
            target_agent_id=TARGET_ID,
        )
        await revoke_share_policy(db, created.id)

        policy = await check_access(
            db,
            accessor_agent_id=TARGET_ID,
            owner_agent_id=OWNER_ID,
            memory_namespace=NAMESPACE,
            action="read",
        )
        assert policy is None

    async def test_daily_read_limit_enforced(self, db: AsyncSession):
        created = await create_share_policy(
            db,
            owner_agent_id=OWNER_ID,
            memory_namespace=NAMESPACE,
            target_agent_id=TARGET_ID,
            max_reads_per_day=2,
        )

        # Log 2 accesses for today
        await log_access(db, created.id, TARGET_ID, NAMESPACE, "read")
        await log_access(db, created.id, TARGET_ID, NAMESPACE, "read")

        # Third access should be denied
        policy = await check_access(
            db,
            accessor_agent_id=TARGET_ID,
            owner_agent_id=OWNER_ID,
            memory_namespace=NAMESPACE,
            action="read",
        )
        assert policy is None

    async def test_daily_read_limit_not_exceeded(self, db: AsyncSession):
        created = await create_share_policy(
            db,
            owner_agent_id=OWNER_ID,
            memory_namespace=NAMESPACE,
            target_agent_id=TARGET_ID,
            max_reads_per_day=5,
        )

        # Only 1 access logged
        await log_access(db, created.id, TARGET_ID, NAMESPACE, "read")

        policy = await check_access(
            db,
            accessor_agent_id=TARGET_ID,
            owner_agent_id=OWNER_ID,
            memory_namespace=NAMESPACE,
            action="read",
        )
        assert policy is not None

    async def test_no_matching_policy_returns_none(self, db: AsyncSession):
        policy = await check_access(
            db,
            accessor_agent_id=TARGET_ID,
            owner_agent_id=OWNER_ID,
            memory_namespace="nonexistent_ns",
            action="read",
        )
        assert policy is None

    async def test_admin_grants_all_actions(self, db: AsyncSession):
        await create_share_policy(
            db,
            owner_agent_id=OWNER_ID,
            memory_namespace=NAMESPACE,
            target_agent_id=TARGET_ID,
            access_level="admin",
        )

        for action in ("read", "write", "delete"):
            policy = await check_access(
                db,
                accessor_agent_id=TARGET_ID,
                owner_agent_id=OWNER_ID,
                memory_namespace=NAMESPACE,
                action=action,
            )
            assert policy is not None, f"Admin should grant {action} access"


# ---------------------------------------------------------------------------
# log_access
# ---------------------------------------------------------------------------

class TestLogAccess:
    async def test_log_creates_audit_entry(self, db: AsyncSession):
        policy = await create_share_policy(
            db,
            owner_agent_id=OWNER_ID,
            memory_namespace=NAMESPACE,
            target_agent_id=TARGET_ID,
        )

        await log_access(
            db,
            policy_id=policy.id,
            accessor_agent_id=TARGET_ID,
            memory_namespace=NAMESPACE,
            action="read",
            resource_key="conversation/2024-01-01",
        )

        logs = await get_access_audit(db, accessor_agent_id=TARGET_ID)
        assert len(logs) == 1
        assert logs[0].policy_id == policy.id
        assert logs[0].action == "read"
        assert logs[0].resource_key == "conversation/2024-01-01"

    async def test_log_without_resource_key(self, db: AsyncSession):
        policy = await create_share_policy(
            db,
            owner_agent_id=OWNER_ID,
            memory_namespace=NAMESPACE,
            target_agent_id=TARGET_ID,
        )

        await log_access(
            db,
            policy_id=policy.id,
            accessor_agent_id=TARGET_ID,
            memory_namespace=NAMESPACE,
            action="write",
        )

        logs = await get_access_audit(db, accessor_agent_id=TARGET_ID)
        assert len(logs) == 1
        assert logs[0].resource_key is None


# ---------------------------------------------------------------------------
# get_access_audit
# ---------------------------------------------------------------------------

class TestGetAccessAudit:
    async def test_filter_by_accessor(self, db: AsyncSession):
        policy = await create_share_policy(
            db,
            owner_agent_id=OWNER_ID,
            memory_namespace=NAMESPACE,
            target_agent_id=TARGET_ID,
        )

        await log_access(db, policy.id, TARGET_ID, NAMESPACE, "read")
        await log_access(db, policy.id, OTHER_ID, NAMESPACE, "read")

        logs = await get_access_audit(db, accessor_agent_id=TARGET_ID)
        assert len(logs) == 1
        assert logs[0].accessor_agent_id == TARGET_ID

    async def test_respects_limit(self, db: AsyncSession):
        policy = await create_share_policy(
            db,
            owner_agent_id=OWNER_ID,
            memory_namespace=NAMESPACE,
            target_agent_id=TARGET_ID,
        )

        for _ in range(10):
            await log_access(db, policy.id, TARGET_ID, NAMESPACE, "read")

        logs = await get_access_audit(db, accessor_agent_id=TARGET_ID, limit=3)
        assert len(logs) == 3

    async def test_no_filter_returns_all(self, db: AsyncSession):
        policy = await create_share_policy(
            db,
            owner_agent_id=OWNER_ID,
            memory_namespace=NAMESPACE,
            target_agent_id=TARGET_ID,
        )

        await log_access(db, policy.id, TARGET_ID, NAMESPACE, "read")
        await log_access(db, policy.id, OTHER_ID, NAMESPACE, "write")

        logs = await get_access_audit(db)
        assert len(logs) == 2

    async def test_empty_audit_log(self, db: AsyncSession):
        logs = await get_access_audit(db)
        assert logs == []


# ---------------------------------------------------------------------------
# MemoryFederationService class wrapper
# ---------------------------------------------------------------------------

class TestMemoryFederationServiceClass:
    async def test_create_share_via_class(self, db: AsyncSession):
        svc = MemoryFederationService()
        policy = await svc.create_share(
            db,
            owner_agent_id=OWNER_ID,
            memory_namespace=NAMESPACE,
            target_agent_id=TARGET_ID,
        )
        assert policy.owner_agent_id == OWNER_ID

    async def test_revoke_share_via_class(self, db: AsyncSession):
        svc = MemoryFederationService()
        policy = await svc.create_share(
            db,
            owner_agent_id=OWNER_ID,
            memory_namespace=NAMESPACE,
            target_agent_id=TARGET_ID,
        )
        result = await svc.revoke_share(db, policy_id=policy.id)
        assert result is True

    async def test_check_via_class(self, db: AsyncSession):
        svc = MemoryFederationService()
        await svc.create_share(
            db,
            owner_agent_id=OWNER_ID,
            memory_namespace=NAMESPACE,
            target_agent_id=TARGET_ID,
        )

        result = await svc.check(
            db,
            accessor_agent_id=TARGET_ID,
            owner_agent_id=OWNER_ID,
            memory_namespace=NAMESPACE,
            action="read",
        )
        assert result is not None

    async def test_class_with_injected_db(self, db: AsyncSession):
        svc = MemoryFederationService(db=db)
        policy = await svc.create_share(
            owner_agent_id=OWNER_ID,
            memory_namespace=NAMESPACE,
            target_agent_id=TARGET_ID,
        )
        assert policy.owner_agent_id == OWNER_ID

    async def test_class_db_param_overrides_injected(self, db: AsyncSession):
        """When both injected db and explicit db are provided, explicit wins."""
        svc = MemoryFederationService(db=None)
        policy = await svc.create_share(
            db,
            owner_agent_id=OWNER_ID,
            memory_namespace=NAMESPACE,
            target_agent_id=TARGET_ID,
        )
        assert policy.owner_agent_id == OWNER_ID
