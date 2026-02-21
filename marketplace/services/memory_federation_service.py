"""Cross-agent memory federation service.

Enables agents to share memory namespaces with other agents under
controlled access policies. Supports ACL-based permissions, read
limits, and expiration.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from marketplace.models.memory_share import MemoryAccessLog, MemorySharePolicy

logger = logging.getLogger(__name__)


class MemoryFederationService:
    """Facade for cross-agent memory federation operations."""

    def __init__(self, db: AsyncSession | None = None):
        self._db = db

    async def create_share(self, db: AsyncSession | None = None, **kwargs) -> Any:
        session = db or self._db
        return await create_share_policy(session, **kwargs)

    async def revoke_share(self, db: AsyncSession | None = None, **kwargs) -> bool:
        session = db or self._db
        return await revoke_share_policy(session, **kwargs)

    async def check(self, db: AsyncSession | None = None, **kwargs) -> Any:
        session = db or self._db
        return await check_access(session, **kwargs)


async def create_share_policy(
    db: AsyncSession,
    owner_agent_id: str,
    memory_namespace: str,
    *,
    target_agent_id: str | None = None,
    access_level: str = "read",
    allow_derivative: bool = False,
    max_reads_per_day: int | None = None,
    expires_at: datetime | None = None,
) -> MemorySharePolicy:
    """Create a memory sharing policy."""
    import uuid

    policy = MemorySharePolicy(
        id=str(uuid.uuid4()),
        owner_agent_id=owner_agent_id,
        target_agent_id=target_agent_id,
        memory_namespace=memory_namespace,
        access_level=access_level,
        allow_derivative=allow_derivative,
        max_reads_per_day=max_reads_per_day,
        expires_at=expires_at,
    )
    db.add(policy)
    await db.commit()
    await db.refresh(policy)
    logger.info(
        "Memory share policy created: %s -> %s (ns=%s, level=%s)",
        owner_agent_id, target_agent_id or "public", memory_namespace, access_level,
    )
    return policy


async def revoke_share_policy(db: AsyncSession, policy_id: str) -> bool:
    """Revoke a memory sharing policy."""
    result = await db.execute(
        select(MemorySharePolicy).where(MemorySharePolicy.id == policy_id)
    )
    policy = result.scalar_one_or_none()
    if not policy:
        return False

    policy.status = "revoked"
    await db.commit()
    return True


async def list_shared_with_me(
    db: AsyncSession,
    agent_id: str,
) -> list[MemorySharePolicy]:
    """List all memory namespaces shared with a specific agent."""
    result = await db.execute(
        select(MemorySharePolicy).where(
            and_(
                MemorySharePolicy.status == "active",
                (
                    (MemorySharePolicy.target_agent_id == agent_id)
                    | (MemorySharePolicy.target_agent_id.is_(None))
                ),
            )
        )
    )
    return list(result.scalars().all())


async def list_my_shares(
    db: AsyncSession,
    owner_agent_id: str,
) -> list[MemorySharePolicy]:
    """List all sharing policies created by an agent."""
    result = await db.execute(
        select(MemorySharePolicy).where(
            MemorySharePolicy.owner_agent_id == owner_agent_id
        )
    )
    return list(result.scalars().all())


async def check_access(
    db: AsyncSession,
    accessor_agent_id: str,
    owner_agent_id: str,
    memory_namespace: str,
    action: str = "read",
) -> MemorySharePolicy | None:
    """Check if an agent has access to a memory namespace.

    Returns the applicable policy if access is granted, None otherwise.
    """
    now = datetime.now(timezone.utc)

    result = await db.execute(
        select(MemorySharePolicy).where(
            and_(
                MemorySharePolicy.owner_agent_id == owner_agent_id,
                MemorySharePolicy.memory_namespace == memory_namespace,
                MemorySharePolicy.status == "active",
                (
                    (MemorySharePolicy.target_agent_id == accessor_agent_id)
                    | (MemorySharePolicy.target_agent_id.is_(None))
                ),
            )
        )
    )
    policies = result.scalars().all()

    for policy in policies:
        # Check expiration
        if policy.expires_at and policy.expires_at < now:
            policy.status = "expired"
            await db.commit()
            continue

        # Check access level
        if action == "read" and policy.access_level in ("read", "write", "admin"):
            # Check daily read limit
            if policy.max_reads_per_day is not None:
                today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
                count_result = await db.execute(
                    select(func.count(MemoryAccessLog.id)).where(
                        and_(
                            MemoryAccessLog.policy_id == policy.id,
                            MemoryAccessLog.accessor_agent_id == accessor_agent_id,
                            MemoryAccessLog.accessed_at >= today_start,
                        )
                    )
                )
                today_reads = count_result.scalar() or 0
                if today_reads >= policy.max_reads_per_day:
                    continue
            return policy

        if action == "write" and policy.access_level in ("write", "admin"):
            return policy

        if action == "delete" and policy.access_level == "admin":
            return policy

    return None


async def log_access(
    db: AsyncSession,
    policy_id: str,
    accessor_agent_id: str,
    memory_namespace: str,
    action: str,
    resource_key: str | None = None,
) -> None:
    """Log a memory access event for auditing."""
    import uuid

    log_entry = MemoryAccessLog(
        id=str(uuid.uuid4()),
        policy_id=policy_id,
        accessor_agent_id=accessor_agent_id,
        memory_namespace=memory_namespace,
        action=action,
        resource_key=resource_key,
    )
    db.add(log_entry)
    await db.commit()


async def get_access_audit(
    db: AsyncSession,
    owner_agent_id: str | None = None,
    accessor_agent_id: str | None = None,
    limit: int = 100,
) -> list[MemoryAccessLog]:
    """Get memory access audit log entries."""
    query = select(MemoryAccessLog).order_by(MemoryAccessLog.accessed_at.desc()).limit(limit)
    if accessor_agent_id:
        query = query.where(MemoryAccessLog.accessor_agent_id == accessor_agent_id)
    result = await db.execute(query)
    return list(result.scalars().all())
