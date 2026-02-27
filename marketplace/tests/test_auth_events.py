"""Tests for marketplace.services.auth_event_service.

Covers:
- log_auth_event: persists an AuthEvent row in the DB
- log_auth_event: handles all-optional fields (None actor, no details)
- get_events: returns events filtered by actor_id
- get_events: returns events filtered by event_type
- get_events: returns all events when no filters are applied
- get_events: pagination (page / page_size)
- get_events: returns empty list and total=0 with no matching events
- detect_brute_force: returns True when login_failure count >= threshold
- detect_brute_force: returns False when count is below threshold
- detect_brute_force: counts only login_failure events (not other types)
- detect_brute_force: respects the time window (ignores old events)
- get_event_summary: returns aggregated counts by event_type
- get_event_summary: returns zero counts when no events in period
- cleanup_old_events: deletes events older than retention period
- cleanup_old_events: preserves recent events
- cleanup_old_events: returns the number of deleted rows
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from marketplace.models.auth_event import AuthEvent
from marketplace.services.auth_event_service import (
    cleanup_old_events,
    detect_brute_force,
    get_event_summary,
    get_events,
    log_auth_event,
)


# ---------------------------------------------------------------------------
# In-memory DB fixture (self-contained)
# ---------------------------------------------------------------------------

@pytest.fixture
async def db() -> AsyncSession:
    from marketplace.database import Base

    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as session:
        yield session
    await engine.dispose()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _log(db: AsyncSession, event_type: str = "login_success", **kwargs) -> None:
    """Shorthand to log an event with sensible defaults."""
    await log_auth_event(db, event_type=event_type, actor_id="actor-default", **kwargs)


async def _insert_event_at(
    db: AsyncSession,
    event_type: str,
    actor_id: str,
    ts: datetime,
) -> None:
    """Insert an AuthEvent with a specific created_at timestamp (bypasses service layer for timing control)."""
    import uuid

    event = AuthEvent(
        id=str(uuid.uuid4()),
        actor_id=actor_id,
        actor_type="user",
        event_type=event_type,
        created_at=ts,
    )
    db.add(event)
    await db.commit()


# ---------------------------------------------------------------------------
# log_auth_event
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_log_auth_event_creates_row_in_db(db: AsyncSession) -> None:
    """log_auth_event persists exactly one AuthEvent row."""
    await log_auth_event(
        db,
        actor_id="actor-1",
        actor_type="user",
        event_type="login_success",
        ip_address="1.2.3.4",
        user_agent="Mozilla/5.0",
        details={"method": "password"},
    )
    result = await db.execute(select(AuthEvent))
    events = result.scalars().all()
    assert len(events) == 1


@pytest.mark.asyncio
async def test_log_auth_event_stores_correct_event_type(db: AsyncSession) -> None:
    """log_auth_event persists the event_type on the row."""
    await log_auth_event(db, event_type="token_refresh")
    result = await db.execute(select(AuthEvent))
    event = result.scalars().first()
    assert event.event_type == "token_refresh"


@pytest.mark.asyncio
async def test_log_auth_event_stores_actor_id_and_ip(db: AsyncSession) -> None:
    """log_auth_event persists actor_id and ip_address on the row."""
    await log_auth_event(db, actor_id="actor-ip", actor_type="creator", event_type="login_failure", ip_address="9.9.9.9")
    result = await db.execute(select(AuthEvent).where(AuthEvent.actor_id == "actor-ip"))
    event = result.scalars().first()
    assert event is not None
    assert event.ip_address == "9.9.9.9"


@pytest.mark.asyncio
async def test_log_auth_event_accepts_none_actor_id(db: AsyncSession) -> None:
    """log_auth_event can log events without an actor_id (e.g. anonymous failures)."""
    await log_auth_event(db, event_type="login_failure", actor_id=None, ip_address="5.5.5.5")
    result = await db.execute(select(AuthEvent).where(AuthEvent.ip_address == "5.5.5.5"))
    event = result.scalars().first()
    assert event is not None
    assert event.actor_id is None


@pytest.mark.asyncio
async def test_log_auth_event_accepts_no_details(db: AsyncSession) -> None:
    """log_auth_event with no details stores an empty JSON object."""
    import json

    await log_auth_event(db, event_type="login_success")
    result = await db.execute(select(AuthEvent))
    event = result.scalars().first()
    assert json.loads(event.details_json) == {}


@pytest.mark.asyncio
async def test_log_auth_event_stores_details_json(db: AsyncSession) -> None:
    """log_auth_event serialises the details dict to details_json."""
    import json

    await log_auth_event(db, event_type="login_success", details={"foo": "bar", "count": 3})
    result = await db.execute(select(AuthEvent))
    event = result.scalars().first()
    assert json.loads(event.details_json) == {"foo": "bar", "count": 3}


@pytest.mark.asyncio
async def test_log_auth_event_multiple_calls_create_multiple_rows(db: AsyncSession) -> None:
    """Multiple log_auth_event calls each create a distinct row."""
    for _ in range(5):
        await log_auth_event(db, event_type="login_success")
    result = await db.execute(select(AuthEvent))
    assert len(result.scalars().all()) == 5


# ---------------------------------------------------------------------------
# get_events
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_events_returns_events_for_actor_id(db: AsyncSession) -> None:
    """get_events with actor_id filter returns only that actor's events."""
    await log_auth_event(db, actor_id="actor-a", event_type="login_success")
    await log_auth_event(db, actor_id="actor-b", event_type="login_success")
    events, total = await get_events(db, actor_id="actor-a")
    assert total == 1
    assert events[0].actor_id == "actor-a"


@pytest.mark.asyncio
async def test_get_events_returns_events_for_event_type(db: AsyncSession) -> None:
    """get_events with event_type filter returns only events of that type."""
    await log_auth_event(db, event_type="login_success", actor_id="actor-filter")
    await log_auth_event(db, event_type="login_failure", actor_id="actor-filter")
    events, total = await get_events(db, event_type="login_failure")
    assert total == 1
    assert events[0].event_type == "login_failure"


@pytest.mark.asyncio
async def test_get_events_returns_all_when_no_filters(db: AsyncSession) -> None:
    """get_events with no filters returns all events."""
    await log_auth_event(db, event_type="login_success")
    await log_auth_event(db, event_type="login_failure")
    await log_auth_event(db, event_type="token_refresh")
    events, total = await get_events(db)
    assert total == 3
    assert len(events) == 3


@pytest.mark.asyncio
async def test_get_events_returns_empty_when_no_matching_events(db: AsyncSession) -> None:
    """get_events returns an empty list and total=0 when no events match."""
    events, total = await get_events(db, actor_id="ghost-actor")
    assert events == []
    assert total == 0


@pytest.mark.asyncio
async def test_get_events_pagination_returns_correct_page(db: AsyncSession) -> None:
    """get_events respects page and page_size for pagination."""
    for i in range(10):
        await log_auth_event(db, event_type="login_success", actor_id=f"actor-page-{i}")
    events, total = await get_events(db, page=1, page_size=4)
    assert total == 10
    assert len(events) == 4


@pytest.mark.asyncio
async def test_get_events_page_two_returns_correct_slice(db: AsyncSession) -> None:
    """get_events page 2 returns items 5-8 when page_size=4."""
    for i in range(8):
        await log_auth_event(db, event_type="login_success", actor_id="actor-pg2")
    events_p1, total = await get_events(db, actor_id="actor-pg2", page=1, page_size=4)
    events_p2, _ = await get_events(db, actor_id="actor-pg2", page=2, page_size=4)
    assert total == 8
    assert len(events_p1) == 4
    assert len(events_p2) == 4
    # Pages must not overlap
    p1_ids = {e.id for e in events_p1}
    p2_ids = {e.id for e in events_p2}
    assert p1_ids.isdisjoint(p2_ids)


@pytest.mark.asyncio
async def test_get_events_combined_actor_and_type_filter(db: AsyncSession) -> None:
    """get_events supports combining actor_id and event_type filters."""
    await log_auth_event(db, actor_id="actor-combo", event_type="login_success")
    await log_auth_event(db, actor_id="actor-combo", event_type="login_failure")
    await log_auth_event(db, actor_id="actor-other", event_type="login_success")
    events, total = await get_events(db, actor_id="actor-combo", event_type="login_success")
    assert total == 1
    assert events[0].actor_id == "actor-combo"
    assert events[0].event_type == "login_success"


# ---------------------------------------------------------------------------
# detect_brute_force
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_detect_brute_force_returns_true_when_threshold_exceeded(db: AsyncSession) -> None:
    """detect_brute_force returns True when login_failure count >= threshold within the window."""
    actor = "bf-actor"
    for _ in range(10):
        await log_auth_event(db, actor_id=actor, event_type="login_failure")
    result = await detect_brute_force(db, actor_id=actor, threshold=10)
    assert result is True


@pytest.mark.asyncio
async def test_detect_brute_force_returns_false_when_below_threshold(db: AsyncSession) -> None:
    """detect_brute_force returns False when login_failure count < threshold."""
    actor = "safe-actor"
    for _ in range(5):
        await log_auth_event(db, actor_id=actor, event_type="login_failure")
    result = await detect_brute_force(db, actor_id=actor, threshold=10)
    assert result is False


@pytest.mark.asyncio
async def test_detect_brute_force_at_exactly_threshold_returns_true(db: AsyncSession) -> None:
    """detect_brute_force returns True when count equals the threshold exactly (>=)."""
    actor = "exact-actor"
    for _ in range(3):
        await log_auth_event(db, actor_id=actor, event_type="login_failure")
    result = await detect_brute_force(db, actor_id=actor, threshold=3)
    assert result is True


@pytest.mark.asyncio
async def test_detect_brute_force_ignores_non_login_failure_events(db: AsyncSession) -> None:
    """detect_brute_force does not count non-login_failure events."""
    actor = "success-actor"
    for _ in range(15):
        await log_auth_event(db, actor_id=actor, event_type="login_success")
    result = await detect_brute_force(db, actor_id=actor, threshold=10)
    assert result is False


@pytest.mark.asyncio
async def test_detect_brute_force_by_ip_address(db: AsyncSession) -> None:
    """detect_brute_force can detect attacks by IP address regardless of actor_id."""
    ip = "192.168.1.100"
    for _ in range(12):
        await log_auth_event(db, event_type="login_failure", ip_address=ip)
    result = await detect_brute_force(db, ip_address=ip, threshold=10)
    assert result is True


@pytest.mark.asyncio
async def test_detect_brute_force_ignores_events_outside_time_window(db: AsyncSession) -> None:
    """detect_brute_force ignores login_failure events older than window_minutes."""
    actor = "old-events-actor"
    old_ts = datetime.now(timezone.utc) - timedelta(minutes=30)
    for _ in range(20):
        await _insert_event_at(db, "login_failure", actor, old_ts)
    # Only check the last 5-minute window; old events should be excluded
    result = await detect_brute_force(db, actor_id=actor, window_minutes=5, threshold=10)
    assert result is False


@pytest.mark.asyncio
async def test_detect_brute_force_returns_false_with_no_events(db: AsyncSession) -> None:
    """detect_brute_force returns False when there are no login_failure events at all."""
    result = await detect_brute_force(db, actor_id="empty-actor", threshold=1)
    assert result is False


# ---------------------------------------------------------------------------
# get_event_summary
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_event_summary_returns_correct_counts(db: AsyncSession) -> None:
    """get_event_summary aggregates event counts by type within the period."""
    await log_auth_event(db, event_type="login_success")
    await log_auth_event(db, event_type="login_success")
    await log_auth_event(db, event_type="login_failure")
    await log_auth_event(db, event_type="token_refresh")
    summary = await get_event_summary(db, period_hours=24)
    assert summary["login_successes"] == 2
    assert summary["login_failures"] == 1
    assert summary["token_refreshes"] == 1
    assert summary["total_events"] == 4


@pytest.mark.asyncio
async def test_get_event_summary_returns_zeros_when_no_events(db: AsyncSession) -> None:
    """get_event_summary returns all-zero counts when there are no events."""
    summary = await get_event_summary(db, period_hours=24)
    assert summary["total_events"] == 0
    assert summary["login_successes"] == 0
    assert summary["login_failures"] == 0
    assert summary["token_refreshes"] == 0
    assert summary["token_revocations"] == 0
    assert summary["brute_force_detections"] == 0


@pytest.mark.asyncio
async def test_get_event_summary_includes_period_hours_in_result(db: AsyncSession) -> None:
    """get_event_summary echoes back the period_hours used."""
    summary = await get_event_summary(db, period_hours=48)
    assert summary["period_hours"] == 48


@pytest.mark.asyncio
async def test_get_event_summary_excludes_events_outside_period(db: AsyncSession) -> None:
    """get_event_summary does not count events older than period_hours."""
    old_ts = datetime.now(timezone.utc) - timedelta(hours=50)
    await _insert_event_at(db, "login_success", "actor-old", old_ts)
    # Add one fresh event
    await log_auth_event(db, event_type="login_success")
    summary = await get_event_summary(db, period_hours=24)
    assert summary["login_successes"] == 1
    assert summary["total_events"] == 1


@pytest.mark.asyncio
async def test_get_event_summary_counts_token_revocations(db: AsyncSession) -> None:
    """get_event_summary correctly counts token_revoke events."""
    await log_auth_event(db, event_type="token_revoke")
    await log_auth_event(db, event_type="token_revoke")
    summary = await get_event_summary(db)
    assert summary["token_revocations"] == 2


@pytest.mark.asyncio
async def test_get_event_summary_counts_brute_force_detected_events(db: AsyncSession) -> None:
    """get_event_summary correctly counts brute_force_detected events."""
    await log_auth_event(db, event_type="brute_force_detected")
    summary = await get_event_summary(db)
    assert summary["brute_force_detections"] == 1


# ---------------------------------------------------------------------------
# cleanup_old_events
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_cleanup_old_events_deletes_events_beyond_retention(db: AsyncSession) -> None:
    """cleanup_old_events removes events older than retention_days."""
    old_ts = datetime.now(timezone.utc) - timedelta(days=40)
    await _insert_event_at(db, "login_success", "actor-cleanup", old_ts)
    deleted = await cleanup_old_events(db, retention_days=30)
    assert deleted == 1


@pytest.mark.asyncio
async def test_cleanup_old_events_preserves_recent_events(db: AsyncSession) -> None:
    """cleanup_old_events does not delete events within the retention window."""
    await log_auth_event(db, event_type="login_success")  # just now
    deleted = await cleanup_old_events(db, retention_days=30)
    assert deleted == 0
    result = await db.execute(select(AuthEvent))
    assert len(result.scalars().all()) == 1


@pytest.mark.asyncio
async def test_cleanup_old_events_returns_count_of_deleted_rows(db: AsyncSession) -> None:
    """cleanup_old_events returns the exact number of rows it deleted."""
    old_ts = datetime.now(timezone.utc) - timedelta(days=60)
    for _ in range(5):
        await _insert_event_at(db, "login_failure", "actor-batch", old_ts)
    deleted = await cleanup_old_events(db, retention_days=30)
    assert deleted == 5


@pytest.mark.asyncio
async def test_cleanup_old_events_returns_zero_when_nothing_to_delete(db: AsyncSession) -> None:
    """cleanup_old_events returns 0 when all events are within the retention period."""
    await log_auth_event(db, event_type="login_success")
    deleted = await cleanup_old_events(db, retention_days=30)
    assert deleted == 0


@pytest.mark.asyncio
async def test_cleanup_old_events_deletes_old_but_keeps_recent(db: AsyncSession) -> None:
    """cleanup_old_events selectively deletes old events and leaves recent ones intact."""
    old_ts = datetime.now(timezone.utc) - timedelta(days=45)
    await _insert_event_at(db, "login_success", "actor-mix", old_ts)
    await log_auth_event(db, event_type="login_failure")  # recent

    deleted = await cleanup_old_events(db, retention_days=30)
    assert deleted == 1

    result = await db.execute(select(AuthEvent))
    remaining = result.scalars().all()
    assert len(remaining) == 1
    assert remaining[0].event_type == "login_failure"
