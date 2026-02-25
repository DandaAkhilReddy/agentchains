"""Tests for memory sharing models: MemorySharePolicy and MemoryAccessLog.

Covers: creation, defaults, access levels, expiry, status transitions, queries.
"""

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select

from marketplace.models.memory_share import MemoryAccessLog, MemorySharePolicy, utcnow


def _uid() -> str:
    return str(uuid.uuid4())


# ---------------------------------------------------------------------------
# MemorySharePolicy
# ---------------------------------------------------------------------------


class TestMemorySharePolicyModel:
    async def test_create_with_defaults(self, db):
        policy = MemorySharePolicy(
            id=_uid(),
            owner_agent_id="agent-owner",
            memory_namespace="tools.web_search",
        )
        db.add(policy)
        await db.commit()
        await db.refresh(policy)

        assert policy.owner_agent_id == "agent-owner"
        assert policy.target_agent_id is None  # public
        assert policy.memory_namespace == "tools.web_search"
        assert policy.access_level == "read"
        assert policy.allow_derivative is False
        assert policy.max_reads_per_day is None
        assert policy.expires_at is None
        assert policy.status == "active"
        assert policy.created_at is not None
        assert policy.updated_at is not None

    async def test_public_policy_null_target(self, db):
        """A policy with target_agent_id=None means public access."""
        policy = MemorySharePolicy(
            id=_uid(),
            owner_agent_id="a1",
            target_agent_id=None,
            memory_namespace="public_data",
        )
        db.add(policy)
        await db.commit()
        await db.refresh(policy)

        assert policy.target_agent_id is None

    async def test_targeted_policy(self, db):
        policy = MemorySharePolicy(
            id=_uid(),
            owner_agent_id="a1",
            target_agent_id="a2",
            memory_namespace="shared.analysis",
            access_level="write",
        )
        db.add(policy)
        await db.commit()
        await db.refresh(policy)

        assert policy.target_agent_id == "a2"
        assert policy.access_level == "write"

    async def test_access_levels(self, db):
        for level in ("read", "write", "admin"):
            policy = MemorySharePolicy(
                id=_uid(),
                owner_agent_id="owner",
                memory_namespace="ns",
                access_level=level,
            )
            db.add(policy)
            await db.commit()
            await db.refresh(policy)
            assert policy.access_level == level

    async def test_allow_derivative(self, db):
        policy = MemorySharePolicy(
            id=_uid(),
            owner_agent_id="owner",
            memory_namespace="data",
            allow_derivative=True,
        )
        db.add(policy)
        await db.commit()
        await db.refresh(policy)

        assert policy.allow_derivative is True

    async def test_rate_limited_policy(self, db):
        policy = MemorySharePolicy(
            id=_uid(),
            owner_agent_id="owner",
            memory_namespace="expensive_data",
            max_reads_per_day=100,
        )
        db.add(policy)
        await db.commit()
        await db.refresh(policy)

        assert policy.max_reads_per_day == 100

    async def test_expiring_policy(self, db):
        expires = datetime.now(timezone.utc) + timedelta(days=30)
        policy = MemorySharePolicy(
            id=_uid(),
            owner_agent_id="owner",
            memory_namespace="temp_share",
            expires_at=expires,
        )
        db.add(policy)
        await db.commit()
        await db.refresh(policy)

        assert policy.expires_at is not None

    async def test_status_transitions(self, db):
        policy = MemorySharePolicy(
            id=_uid(),
            owner_agent_id="owner",
            memory_namespace="data",
            status="active",
        )
        db.add(policy)
        await db.commit()

        # active -> revoked
        policy.status = "revoked"
        await db.commit()
        await db.refresh(policy)
        assert policy.status == "revoked"

    async def test_all_status_values(self, db):
        for status in ("active", "revoked", "expired"):
            policy = MemorySharePolicy(
                id=_uid(),
                owner_agent_id="owner",
                memory_namespace="data",
                status=status,
            )
            db.add(policy)
        await db.commit()

        result = await db.execute(
            select(MemorySharePolicy).where(MemorySharePolicy.status == "active")
        )
        active = list(result.scalars().all())
        assert len(active) == 1


class TestMemorySharePolicyQueries:
    async def test_query_by_owner(self, db):
        owner = "agent-owner-123"
        for i in range(3):
            policy = MemorySharePolicy(
                id=_uid(),
                owner_agent_id=owner,
                memory_namespace=f"ns_{i}",
            )
            db.add(policy)
        # Different owner
        other_policy = MemorySharePolicy(
            id=_uid(),
            owner_agent_id="other-owner",
            memory_namespace="ns_other",
        )
        db.add(other_policy)
        await db.commit()

        result = await db.execute(
            select(MemorySharePolicy).where(MemorySharePolicy.owner_agent_id == owner)
        )
        found = list(result.scalars().all())
        assert len(found) == 3

    async def test_query_by_target(self, db):
        target = "agent-target-456"
        policy = MemorySharePolicy(
            id=_uid(),
            owner_agent_id="owner",
            target_agent_id=target,
            memory_namespace="shared",
        )
        db.add(policy)
        await db.commit()

        result = await db.execute(
            select(MemorySharePolicy).where(MemorySharePolicy.target_agent_id == target)
        )
        found = result.scalar_one()
        assert found.target_agent_id == target

    async def test_query_by_namespace(self, db):
        for ns in ("web_search", "code_gen", "web_search"):
            policy = MemorySharePolicy(
                id=_uid(),
                owner_agent_id="owner",
                memory_namespace=ns,
            )
            db.add(policy)
        await db.commit()

        result = await db.execute(
            select(MemorySharePolicy).where(MemorySharePolicy.memory_namespace == "web_search")
        )
        found = list(result.scalars().all())
        assert len(found) == 2

    async def test_query_active_policies_for_agent(self, db):
        target = "shared-target"
        for i, status in enumerate(["active", "revoked", "active", "expired"]):
            policy = MemorySharePolicy(
                id=_uid(),
                owner_agent_id=f"owner_{i}",
                target_agent_id=target,
                memory_namespace=f"ns_{i}",
                status=status,
            )
            db.add(policy)
        await db.commit()

        result = await db.execute(
            select(MemorySharePolicy).where(
                MemorySharePolicy.target_agent_id == target,
                MemorySharePolicy.status == "active",
            )
        )
        active = list(result.scalars().all())
        assert len(active) == 2


# ---------------------------------------------------------------------------
# MemoryAccessLog
# ---------------------------------------------------------------------------


class TestMemoryAccessLogModel:
    async def test_create_access_log(self, db):
        log = MemoryAccessLog(
            id=_uid(),
            policy_id=_uid(),
            accessor_agent_id="accessor-1",
            memory_namespace="tools.web_search",
            action="read",
        )
        db.add(log)
        await db.commit()
        await db.refresh(log)

        assert log.accessor_agent_id == "accessor-1"
        assert log.memory_namespace == "tools.web_search"
        assert log.action == "read"
        assert log.resource_key is None
        assert log.accessed_at is not None

    async def test_log_with_resource_key(self, db):
        log = MemoryAccessLog(
            id=_uid(),
            policy_id=_uid(),
            accessor_agent_id="accessor-2",
            memory_namespace="analysis",
            action="write",
            resource_key="memories/session_123/context",
        )
        db.add(log)
        await db.commit()
        await db.refresh(log)

        assert log.resource_key == "memories/session_123/context"

    async def test_all_action_types(self, db):
        for action in ("read", "write", "delete"):
            log = MemoryAccessLog(
                id=_uid(),
                policy_id=_uid(),
                accessor_agent_id="agent-1",
                memory_namespace="data",
                action=action,
            )
            db.add(log)
        await db.commit()

        result = await db.execute(
            select(MemoryAccessLog).where(MemoryAccessLog.accessor_agent_id == "agent-1")
        )
        logs = list(result.scalars().all())
        assert len(logs) == 3
        actions = {log.action for log in logs}
        assert actions == {"read", "write", "delete"}


class TestMemoryAccessLogQueries:
    async def test_query_by_accessor(self, db):
        accessor = "specific-accessor"
        for i in range(5):
            log = MemoryAccessLog(
                id=_uid(),
                policy_id=_uid(),
                accessor_agent_id=accessor,
                memory_namespace="ns",
                action="read",
            )
            db.add(log)
        await db.commit()

        result = await db.execute(
            select(MemoryAccessLog).where(MemoryAccessLog.accessor_agent_id == accessor)
        )
        found = list(result.scalars().all())
        assert len(found) == 5

    async def test_query_by_policy(self, db):
        policy_id = _uid()
        for _ in range(3):
            log = MemoryAccessLog(
                id=_uid(),
                policy_id=policy_id,
                accessor_agent_id="agent",
                memory_namespace="ns",
                action="read",
            )
            db.add(log)
        await db.commit()

        result = await db.execute(
            select(MemoryAccessLog).where(MemoryAccessLog.policy_id == policy_id)
        )
        found = list(result.scalars().all())
        assert len(found) == 3

    async def test_audit_trail_ordering(self, db):
        """Access logs should be queryable in chronological order."""
        for i in range(3):
            log = MemoryAccessLog(
                id=_uid(),
                policy_id=_uid(),
                accessor_agent_id="agent",
                memory_namespace="ns",
                action="read",
                resource_key=f"key_{i}",
            )
            db.add(log)
            await db.commit()

        result = await db.execute(
            select(MemoryAccessLog)
            .where(MemoryAccessLog.accessor_agent_id == "agent")
            .order_by(MemoryAccessLog.accessed_at)
        )
        logs = list(result.scalars().all())
        assert len(logs) == 3
        # Chronological order should be maintained
        for j in range(len(logs) - 1):
            assert logs[j].accessed_at <= logs[j + 1].accessed_at
