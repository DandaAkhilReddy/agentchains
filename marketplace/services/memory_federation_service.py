"""Memory federation service — cross-agent memory sharing with ACL.

Allows agents to share memory namespaces with other agents under
controlled access policies and rate limiting.
"""

import json
import logging
from datetime import datetime, timezone

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from marketplace.models.memory_share import MemoryAccessLog, MemorySharePolicy

logger = logging.getLogger(__name__)


async def create_share_policy(
    db: AsyncSession,
    owner_agent_id: str,
    memory_namespace: str,
    *,
    access_level: str = "read",
    allowed_agent_ids: list[str] | None = None,
    max_reads_per_hour: int = 100,
    expires_at: datetime | None = None,
) -> MemorySharePolicy:
    """Create a memory sharing policy for a namespace."""
    policy = MemorySharePolicy(
        owner_agent_id=owner_agent_id,
        memory_namespace=memory_namespace,
        access_level=access_level,
        allowed_agent_ids=json.dumps(allowed_agent_ids or ["*"]),
        max_reads_per_hour=max_reads_per_hour,
        expires_at=expires_at,
    )
    db.add(policy)
    await db.commit()
    await db.refresh(policy)
    logger.info(
        "Memory share policy created: owner=%s namespace=%s level=%s",
        owner_agent_id, memory_namespace, access_level,
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


async def list_shared_namespaces(
    db: AsyncSession, requester_agent_id: str
) -> list[dict]:
    """List all memory namespaces shared with the requester."""
    result = await db.execute(
        select(MemorySharePolicy).where(
            MemorySharePolicy.status == "active"
        )
    )
    policies = result.scalars().all()

    accessible = []
    now = datetime.now(timezone.utc)
    for p in policies:
        if p.expires_at and p.expires_at < now:
            continue
        allowed = json.loads(p.allowed_agent_ids or "[]")
        if "*" in allowed or requester_agent_id in allowed:
            accessible.append({
                "policy_id": p.id,
                "owner_agent_id": p.owner_agent_id,
                "memory_namespace": p.memory_namespace,
                "access_level": p.access_level,
                "max_reads_per_hour": p.max_reads_per_hour,
            })
    return accessible


async def check_access(
    db: AsyncSession,
    requester_agent_id: str,
    owner_agent_id: str,
    memory_namespace: str,
    operation: str = "read",
) -> tuple[bool, str]:
    """Check if requester has access to a memory namespace.

    Returns (allowed, reason).
    """
    result = await db.execute(
        select(MemorySharePolicy).where(
            and_(
                MemorySharePolicy.owner_agent_id == owner_agent_id,
                MemorySharePolicy.memory_namespace == memory_namespace,
                MemorySharePolicy.status == "active",
            )
        )
    )
    policy = result.scalar_one_or_none()

    if not policy:
        return False, "No sharing policy found"

    now = datetime.now(timezone.utc)
    if policy.expires_at and policy.expires_at < now:
        return False, "Policy expired"

    allowed = json.loads(policy.allowed_agent_ids or "[]")
    if "*" not in allowed and requester_agent_id not in allowed:
        return False, "Agent not in allowed list"

    if operation == "write" and policy.access_level == "read":
        return False, "Write access not granted"

    # Check rate limit
    if policy.max_reads_per_hour > 0:
        from datetime import timedelta

        one_hour_ago = now - timedelta(hours=1)
        count_result = await db.execute(
            select(MemoryAccessLog).where(
                and_(
                    MemoryAccessLog.requester_agent_id == requester_agent_id,
                    MemoryAccessLog.policy_id == policy.id,
                    MemoryAccessLog.accessed_at > one_hour_ago,
                    MemoryAccessLog.success == True,  # noqa: E712
                )
            )
        )
        recent_count = len(count_result.scalars().all())
        if recent_count >= policy.max_reads_per_hour:
            return False, "Rate limit exceeded"

    return True, ""


async def log_access(
    db: AsyncSession,
    policy_id: str,
    requester_agent_id: str,
    owner_agent_id: str,
    memory_namespace: str,
    operation: str,
    success: bool,
    denial_reason: str = "",
) -> None:
    """Log a memory access event for auditing."""
    log_entry = MemoryAccessLog(
        policy_id=policy_id,
        requester_agent_id=requester_agent_id,
        owner_agent_id=owner_agent_id,
        memory_namespace=memory_namespace,
        operation=operation,
        success=success,
        denial_reason=denial_reason,
    )
    db.add(log_entry)
    await db.commit()


async def get_access_logs(
    db: AsyncSession,
    owner_agent_id: str,
    limit: int = 50,
) -> list[MemoryAccessLog]:
    """Get recent memory access logs for an agent's shared namespaces."""
    result = await db.execute(
        select(MemoryAccessLog)
        .where(MemoryAccessLog.owner_agent_id == owner_agent_id)
        .order_by(MemoryAccessLog.accessed_at.desc())
        .limit(limit)
    )
    return list(result.scalars().all())
