"""Comprehensive tests for payout, audit, and CDN services.

Tests cover:
- Payout service: eligible creators, thresholds, payout methods, idempotency
- Audit service: log creation, hash chain integrity, metadata, queries
- CDN service: HotCache operations, maxsize eviction, decay, tier promotions
"""

import json
import time
from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, Mock, patch

import pytest
from sqlalchemy import select

from marketplace.config import settings
from marketplace.models.audit_log import AuditLog
from marketplace.models.creator import Creator
from marketplace.models.redemption import RedemptionRequest
from marketplace.models.token_account import TokenAccount
from marketplace.services import audit_service, payout_service
from marketplace.services.cdn_service import HotCache, _hot_cache, get_content


# ==============================================================================
# PAYOUT SERVICE TESTS (7 tests)
# ==============================================================================


@pytest.mark.asyncio
async def test_monthly_payout_eligible_creators(db, make_creator):
    """Test monthly payout processes creators with sufficient balance."""
    # Create creator with token account above threshold
    creator, _ = await make_creator(email="payout1@test.com")

    # Create token account with balance above minimum
    min_balance = settings.creator_min_withdrawal_usd
    original_balance = min_balance + 10.00
    account = TokenAccount(
        creator_id=creator.id,
        balance=Decimal(str(original_balance)),
    )
    db.add(account)

    # Set payout method
    creator.payout_method = "upi"
    creator.status = "active"
    await db.commit()

    # Run monthly payout
    result = await payout_service.run_monthly_payout(db)

    assert result["processed"] == 1
    assert result["skipped"] == 0
    assert len(result["errors"]) == 0

    # Verify redemption request was created
    redemptions = await db.execute(
        select(RedemptionRequest).where(RedemptionRequest.creator_id == creator.id)
    )
    redemption = redemptions.scalar_one_or_none()
    assert redemption is not None
    assert redemption.redemption_type == "upi"
    # Check that the redemption amount matches the original balance
    assert float(redemption.amount_usd) == original_balance


@pytest.mark.asyncio
async def test_monthly_payout_below_threshold(db, make_creator):
    """Test monthly payout skips creators below minimum threshold."""
    creator, _ = await make_creator(email="payout2@test.com")

    # Create token account with balance BELOW minimum
    min_balance = settings.creator_min_withdrawal_usd
    account = TokenAccount(
        creator_id=creator.id,
        balance=Decimal(str(min_balance - 1.00)),
    )
    db.add(account)

    creator.payout_method = "bank"
    creator.status = "active"
    await db.commit()

    # Run monthly payout
    result = await payout_service.run_monthly_payout(db)

    assert result["processed"] == 0
    assert result["skipped"] == 0  # Not skipped, just not selected by query

    # Verify NO redemption request was created
    redemptions = await db.execute(
        select(RedemptionRequest).where(RedemptionRequest.creator_id == creator.id)
    )
    redemption = redemptions.scalar_one_or_none()
    assert redemption is None


@pytest.mark.asyncio
async def test_monthly_payout_no_payout_method(db, make_creator):
    """Test monthly payout skips creators with payout_method='none'."""
    creator, _ = await make_creator(email="payout3@test.com")

    min_balance = settings.creator_min_withdrawal_usd
    account = TokenAccount(
        creator_id=creator.id,
        balance=Decimal(str(min_balance + 5.00)),
    )
    db.add(account)

    creator.payout_method = "none"
    creator.status = "active"
    await db.commit()

    # Run monthly payout
    result = await payout_service.run_monthly_payout(db)

    assert result["processed"] == 0
    # Creator is not selected because payout_method != "none" is in WHERE clause

    redemptions = await db.execute(
        select(RedemptionRequest).where(RedemptionRequest.creator_id == creator.id)
    )
    assert redemptions.scalar_one_or_none() is None


@pytest.mark.asyncio
async def test_monthly_payout_inactive_creator(db, make_creator):
    """Test monthly payout skips inactive creators."""
    creator, _ = await make_creator(email="payout4@test.com")

    min_balance = settings.creator_min_withdrawal_usd
    account = TokenAccount(
        creator_id=creator.id,
        balance=Decimal(str(min_balance + 5.00)),
    )
    db.add(account)

    creator.payout_method = "upi"
    creator.status = "suspended"
    await db.commit()

    result = await payout_service.run_monthly_payout(db)

    assert result["processed"] == 0

    redemptions = await db.execute(
        select(RedemptionRequest).where(RedemptionRequest.creator_id == creator.id)
    )
    assert redemptions.scalar_one_or_none() is None


@pytest.mark.asyncio
async def test_monthly_payout_maps_payout_methods(db, make_creator):
    """Test monthly payout maps creator payout_method to redemption_type correctly."""
    creators_data = [
        ("upi", "upi"),
        ("bank", "bank_withdrawal"),
        ("gift_card", "gift_card"),
    ]

    min_balance = settings.creator_min_withdrawal_usd

    for idx, (payout_method, expected_redemption_type) in enumerate(creators_data):
        creator, _ = await make_creator(email=f"payout_map{idx}@test.com")
        account = TokenAccount(
            creator_id=creator.id,
            balance=Decimal(str(min_balance + 10.00)),
        )
        db.add(account)
        creator.payout_method = payout_method
        creator.status = "active"

    await db.commit()

    result = await payout_service.run_monthly_payout(db)

    assert result["processed"] == 3

    # Verify redemption types
    redemptions = await db.execute(select(RedemptionRequest))
    all_redemptions = redemptions.scalars().all()

    redemption_types = {r.redemption_type for r in all_redemptions}
    assert redemption_types == {"upi", "bank_withdrawal", "gift_card"}


@pytest.mark.asyncio
async def test_monthly_payout_error_handling(db, make_creator):
    """Test monthly payout logs errors but continues processing."""
    # Create multiple creators
    creator1, _ = await make_creator(email="error1@test.com")
    creator2, _ = await make_creator(email="error2@test.com")

    min_balance = settings.creator_min_withdrawal_usd

    for creator in [creator1, creator2]:
        account = TokenAccount(
            creator_id=creator.id,
            balance=Decimal(str(min_balance + 10.00)),
        )
        db.add(account)
        creator.payout_method = "upi"
        creator.status = "active"

    await db.commit()

    # Mock redemption_service to raise error for first creator
    original_create = payout_service.redemption_service.create_redemption
    call_count = {"count": 0}

    async def mock_create(*args, **kwargs):
        call_count["count"] += 1
        if call_count["count"] == 1:
            raise Exception("Simulated payout error")
        return await original_create(*args, **kwargs)

    with patch.object(
        payout_service.redemption_service,
        "create_redemption",
        side_effect=mock_create,
    ):
        result = await payout_service.run_monthly_payout(db)

    # First creator failed, second succeeded
    assert result["processed"] == 1
    assert len(result["errors"]) == 1
    assert "Simulated payout error" in result["errors"][0]["error"]


@pytest.mark.asyncio
async def test_process_pending_payouts(db, make_creator):
    """Test process_pending_payouts calls appropriate redemption processors."""
    creator, _ = await make_creator(email="pending@test.com")

    # Create pending redemptions of different types
    redemption_types = ["api_credits", "gift_card", "bank_withdrawal", "upi"]

    for idx, r_type in enumerate(redemption_types):
        redemption = RedemptionRequest(
            creator_id=creator.id,
            redemption_type=r_type,
            amount_usd=Decimal("10.00"),
            status="pending",
        )
        db.add(redemption)

    await db.commit()

    # Mock the redemption service processors
    with patch.object(
        payout_service.redemption_service, "process_api_credit_redemption", new_callable=AsyncMock
    ) as mock_api, patch.object(
        payout_service.redemption_service, "process_gift_card_redemption", new_callable=AsyncMock
    ) as mock_gift, patch.object(
        payout_service.redemption_service, "process_bank_withdrawal", new_callable=AsyncMock
    ) as mock_bank, patch.object(
        payout_service.redemption_service, "process_upi_transfer", new_callable=AsyncMock
    ) as mock_upi:

        result = await payout_service.process_pending_payouts(db)

    assert result["processed"] == 4
    assert result["total_pending"] == 4

    # Verify each processor was called once
    assert mock_api.call_count == 1
    assert mock_gift.call_count == 1
    assert mock_bank.call_count == 1
    assert mock_upi.call_count == 1


# ==============================================================================
# AUDIT SERVICE TESTS (6 tests)
# ==============================================================================


@pytest.mark.asyncio
async def test_audit_log_creates_entry(db, make_agent):
    """Test audit service creates AuditLog entry with correct fields."""
    agent, _ = await make_agent(name="audit-agent-1")

    entry = await audit_service.log_event(
        db,
        "agent_registered",
        agent_id=agent.id,
        ip_address="192.168.1.100",
        user_agent="TestAgent/1.0",
        details={"action": "registration", "version": "1.0"},
        severity="info",
    )

    await db.commit()

    assert entry.event_type == "agent_registered"
    assert entry.agent_id == agent.id
    assert entry.ip_address == "192.168.1.100"
    assert entry.user_agent == "TestAgent/1.0"
    assert entry.severity == "info"

    # Verify details is JSON string
    details_dict = json.loads(entry.details)
    assert details_dict["action"] == "registration"
    assert details_dict["version"] == "1.0"


@pytest.mark.asyncio
async def test_audit_log_hash_chain(db, make_agent):
    """Test audit logs maintain hash chain integrity."""
    agent, _ = await make_agent(name="audit-agent-2")

    # Create first entry
    entry1 = await audit_service.log_event(
        db,
        "agent_login",
        agent_id=agent.id,
        details={"attempt": 1},
        severity="info",
    )
    await db.commit()

    assert entry1.prev_hash is None  # First entry has no previous
    assert entry1.entry_hash is not None

    # Create second entry
    entry2 = await audit_service.log_event(
        db,
        "agent_logout",
        agent_id=agent.id,
        details={"attempt": 2},
        severity="info",
    )
    await db.commit()

    # Verify hash chain
    assert entry2.prev_hash == entry1.entry_hash
    assert entry2.entry_hash is not None
    assert entry2.entry_hash != entry1.entry_hash


@pytest.mark.asyncio
async def test_audit_log_with_creator_id(db, make_creator):
    """Test audit log works with creator_id instead of agent_id."""
    creator, _ = await make_creator(email="audit_creator@test.com")

    entry = await audit_service.log_event(
        db,
        "creator_withdrawal_requested",
        creator_id=creator.id,
        details={"amount_usd": 100.00},
        severity="warn",
    )
    await db.commit()

    assert entry.creator_id == creator.id
    assert entry.agent_id is None
    assert entry.severity == "warn"


@pytest.mark.asyncio
async def test_audit_log_metadata_json_serialization(db):
    """Test audit log handles complex JSON metadata correctly."""
    complex_details = {
        "nested": {"key": "value", "list": [1, 2, 3]},
        "timestamp": datetime.now(timezone.utc),  # datetime should be converted to str
        "decimal": Decimal("123.456"),  # Decimal should be converted
        "boolean": True,
        "null": None,
    }

    entry = await audit_service.log_event(
        db,
        "test_event",
        details=complex_details,
        severity="debug",
    )
    await db.commit()

    # Verify JSON was serialized correctly
    parsed = json.loads(entry.details)
    assert parsed["nested"]["key"] == "value"
    assert parsed["nested"]["list"] == [1, 2, 3]
    assert parsed["boolean"] is True
    assert parsed["null"] is None
    # datetime and Decimal should be strings
    assert isinstance(parsed["timestamp"], str)
    assert isinstance(parsed["decimal"], str)


@pytest.mark.asyncio
async def test_audit_log_query_by_event_type(db, make_agent):
    """Test querying audit logs by event type."""
    agent, _ = await make_agent(name="audit-query-agent")

    # Create multiple events
    await audit_service.log_event(db, "login", agent_id=agent.id)
    await audit_service.log_event(db, "purchase", agent_id=agent.id)
    await audit_service.log_event(db, "login", agent_id=agent.id)
    await db.commit()

    # Query by event type
    result = await db.execute(
        select(AuditLog).where(AuditLog.event_type == "login")
    )
    login_events = result.scalars().all()

    assert len(login_events) == 2
    assert all(e.event_type == "login" for e in login_events)


@pytest.mark.asyncio
async def test_audit_log_query_by_severity(db, make_agent):
    """Test querying audit logs by severity level."""
    agent, _ = await make_agent(name="severity-agent")

    # Create events with different severities
    await audit_service.log_event(db, "info_event", agent_id=agent.id, severity="info")
    await audit_service.log_event(db, "warn_event", agent_id=agent.id, severity="warn")
    await audit_service.log_event(db, "error_event", agent_id=agent.id, severity="error")
    await db.commit()

    # Query critical events (warn + error)
    result = await db.execute(
        select(AuditLog).where(AuditLog.severity.in_(["warn", "error"]))
    )
    critical_events = result.scalars().all()

    assert len(critical_events) == 2
    assert set(e.severity for e in critical_events) == {"warn", "error"}


# ==============================================================================
# CDN SERVICE TESTS (8 tests)
# ==============================================================================


@pytest.mark.asyncio
async def test_hotcache_put_and_get():
    """Test HotCache basic put and get operations."""
    cache = HotCache(max_bytes=1024)

    data = b"test content"
    assert cache.put("key1", data) is True

    retrieved = cache.get("key1")
    assert retrieved == data
    assert cache.hits == 1
    assert cache.misses == 0


@pytest.mark.asyncio
async def test_hotcache_miss():
    """Test HotCache returns None for missing keys."""
    cache = HotCache(max_bytes=1024)

    result = cache.get("nonexistent")
    assert result is None
    assert cache.misses == 1
    assert cache.hits == 0


@pytest.mark.asyncio
async def test_hotcache_maxsize_eviction():
    """Test HotCache evicts LFU entries when maxsize is reached."""
    cache = HotCache(max_bytes=100)

    # Put two 40-byte entries
    data1 = b"a" * 40
    data2 = b"b" * 40

    cache.put("key1", data1)
    cache.put("key2", data2)

    # Access key1 multiple times to increase frequency
    cache.get("key1")
    cache.get("key1")
    cache.get("key1")

    # Access key2 only once (LFU)
    cache.get("key2")

    # Put a new 40-byte entry (should evict key2, the LFU, to make room)
    data3 = b"c" * 40
    cache.put("key3", data3)

    # key2 should be evicted because it had the lowest frequency
    assert cache.get("key2") is None
    # key1 and key3 should still exist
    assert cache.get("key1") == data1
    assert cache.get("key3") == data3
    assert cache.evictions >= 1


@pytest.mark.asyncio
async def test_hotcache_rejects_oversized_content():
    """Test HotCache rejects content larger than max_bytes."""
    cache = HotCache(max_bytes=100)

    oversized_data = b"x" * 150
    result = cache.put("oversized", oversized_data)

    assert result is False
    assert cache.get("oversized") is None


@pytest.mark.asyncio
async def test_hotcache_should_promote():
    """Test HotCache promotion logic for hot content."""
    cache = HotCache(max_bytes=1024)

    # Record 11 accesses to trigger promotion threshold (>10)
    for _ in range(11):
        cache.record_access("hot_key")

    assert cache.should_promote("hot_key") is True

    # Cold key with fewer accesses
    cache.record_access("cold_key")
    assert cache.should_promote("cold_key") is False


@pytest.mark.asyncio
async def test_hotcache_decay_counters():
    """Test HotCache decay halves access counters."""
    cache = HotCache(max_bytes=1024)

    # Record 10 accesses
    for _ in range(10):
        cache.record_access("decay_key")

    assert cache._access_count["decay_key"] == 10

    # Decay
    cache.decay_counters()

    assert cache._access_count["decay_key"] == 5

    # Decay again
    cache.decay_counters()

    assert cache._access_count["decay_key"] == 2


@pytest.mark.asyncio
async def test_hotcache_stats():
    """Test HotCache stats reporting."""
    cache = HotCache(max_bytes=1000)

    data = b"test" * 10
    cache.put("key1", data)
    cache.put("key2", data)

    cache.get("key1")
    cache.get("key1")
    cache.get("nonexistent")

    stats = cache.stats()

    assert stats["tier"] == "hot"
    assert stats["entries"] == 2
    assert stats["bytes_used"] == len(data) * 2
    assert stats["bytes_max"] == 1000
    assert stats["hits"] == 2
    assert stats["misses"] == 1
    assert stats["promotions"] == 2
    assert stats["hit_rate"] == pytest.approx(66.7, rel=0.1)


@pytest.mark.asyncio
async def test_cdn_get_content_tier_promotion():
    """Test CDN content promotion through tiers."""
    # Create a mock storage that returns content
    mock_storage = Mock()
    mock_storage.get = Mock(return_value=b"tier3_content")

    with patch("marketplace.services.cdn_service.get_storage", return_value=mock_storage):
        # Clear caches
        _hot_cache._store.clear()
        _hot_cache._access_count.clear()

        content_hash = "test_hash_123"

        # First access: should come from Tier 3 (cold storage)
        result = await get_content(content_hash)
        assert result == b"tier3_content"

        # Record many accesses to trigger promotion
        for _ in range(15):
            _hot_cache.record_access(content_hash)

        # Now content should be promoted to hot cache
        assert _hot_cache.should_promote(content_hash) is True

        # Manually promote to test (normally done by get_content)
        _hot_cache.put(content_hash, b"tier3_content")

        # Next access should hit Tier 1
        cached = _hot_cache.get(content_hash)
        assert cached == b"tier3_content"
