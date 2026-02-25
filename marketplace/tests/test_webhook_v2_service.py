"""Tests for marketplace.services.webhook_v2_service — Service Bus webhook
delivery, dead-letter management, and delivery statistics.

Uses in-memory SQLite via conftest fixtures.  asyncio_mode = "auto".
ServiceBusService and httpx are mocked to isolate webhook logic.
"""

from __future__ import annotations

import json
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from marketplace.models.webhook_v2 import DeadLetterEntry, DeliveryAttempt
from marketplace.services import webhook_v2_service as svc


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _uid() -> str:
    return str(uuid.uuid4())


def _mock_servicebus() -> MagicMock:
    """Build a stub ServiceBusService."""
    mock = MagicMock()
    mock.send_message.return_value = True
    mock.receive_messages.return_value = []
    mock.complete_message.return_value = True
    mock.dead_letter_message.return_value = True
    return mock


async def _create_dead_letter(
    db: AsyncSession,
    message_body: dict | None = None,
    retried: bool = False,
    retry_count: int = 0,
) -> DeadLetterEntry:
    entry = DeadLetterEntry(
        id=_uid(),
        original_queue="webhooks",
        message_body=json.dumps(message_body or {"subscription_id": "sub-1", "event": {}}),
        reason="Exhausted 3 delivery attempts",
        retried=retried,
        retry_count=retry_count,
    )
    db.add(entry)
    await db.commit()
    await db.refresh(entry)
    return entry


async def _create_delivery_attempt(
    db: AsyncSession,
    subscription_id: str = "sub-1",
    status: str = "pending",
    attempt_number: int = 1,
) -> DeliveryAttempt:
    attempt = DeliveryAttempt(
        id=_uid(),
        subscription_id=subscription_id,
        event_json="{}",
        status=status,
        attempt_number=attempt_number,
    )
    db.add(attempt)
    await db.commit()
    await db.refresh(attempt)
    return attempt


# ---------------------------------------------------------------------------
# enqueue_webhook_delivery
# ---------------------------------------------------------------------------


@patch("marketplace.services.webhook_v2_service.get_servicebus_service")
async def test_enqueue_webhook_delivery_creates_attempt(
    mock_get_sbs: MagicMock, db: AsyncSession,
):
    """enqueue_webhook_delivery creates a DeliveryAttempt and enqueues a message."""
    mock_sbs = _mock_servicebus()
    mock_get_sbs.return_value = mock_sbs

    event = {"type": "listing.created", "data": {"id": "listing-1"}}
    result = await svc.enqueue_webhook_delivery(db, subscription_id="sub-abc", event=event)

    assert result["subscription_id"] == "sub-abc"
    assert result["queued"] is True
    assert "delivery_attempt_id" in result

    # Verify DeliveryAttempt was persisted
    stmt = select(DeliveryAttempt).where(DeliveryAttempt.id == result["delivery_attempt_id"])
    row = (await db.execute(stmt)).scalar_one_or_none()
    assert row is not None
    assert row.subscription_id == "sub-abc"
    assert row.status == "pending"
    assert row.attempt_number == 1


@patch("marketplace.services.webhook_v2_service.get_servicebus_service")
async def test_enqueue_webhook_delivery_sends_message(
    mock_get_sbs: MagicMock, db: AsyncSession,
):
    """enqueue_webhook_delivery sends correct message to Service Bus."""
    mock_sbs = _mock_servicebus()
    mock_get_sbs.return_value = mock_sbs

    event = {"type": "tx.completed"}
    await svc.enqueue_webhook_delivery(db, subscription_id="sub-xyz", event=event)

    mock_sbs.send_message.assert_called_once()
    call_args = mock_sbs.send_message.call_args
    assert call_args[0][0] == "webhooks"
    body = call_args[0][1]
    assert body["subscription_id"] == "sub-xyz"
    assert body["event"] == event
    assert body["attempt"] == 1
    assert "enqueued_at" in body


@patch("marketplace.services.webhook_v2_service.get_servicebus_service")
async def test_enqueue_webhook_delivery_stub_mode(
    mock_get_sbs: MagicMock, db: AsyncSession,
):
    """When Service Bus returns False (stub mode), queued=False."""
    mock_sbs = _mock_servicebus()
    mock_sbs.send_message.return_value = False
    mock_get_sbs.return_value = mock_sbs

    result = await svc.enqueue_webhook_delivery(db, subscription_id="sub-stub", event={})

    assert result["queued"] is False


# ---------------------------------------------------------------------------
# process_webhook_queue
# ---------------------------------------------------------------------------


@patch("marketplace.services.webhook_v2_service.get_servicebus_service")
async def test_process_webhook_queue_empty(
    mock_get_sbs: MagicMock, db: AsyncSession,
):
    """Processing an empty queue returns all-zero stats."""
    mock_sbs = _mock_servicebus()
    mock_sbs.receive_messages.return_value = []
    mock_get_sbs.return_value = mock_sbs

    result = await svc.process_webhook_queue(db)

    assert result == {"delivered": 0, "failed": 0, "dead_lettered": 0}


@patch("marketplace.services.webhook_v2_service.get_servicebus_service")
@patch("marketplace.services.webhook_v2_service.httpx.AsyncClient")
async def test_process_webhook_queue_successful_delivery(
    mock_client_cls: MagicMock,
    mock_get_sbs: MagicMock,
    db: AsyncSession,
):
    """Successful HTTP POST results in delivered count incremented."""
    mock_sbs = _mock_servicebus()
    mock_get_sbs.return_value = mock_sbs

    msg_body = {
        "subscription_id": "sub-1",
        "event": {"callback_url": "https://example.com/hook", "type": "test"},
        "attempt": 1,
    }
    mock_msg = MagicMock()
    mock_msg.__str__ = lambda self: json.dumps(msg_body)
    mock_sbs.receive_messages.return_value = [mock_msg]

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_client = AsyncMock()
    mock_client.post.return_value = mock_response
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)
    mock_client_cls.return_value = mock_client

    result = await svc.process_webhook_queue(db)

    assert result["delivered"] == 1
    assert result["failed"] == 0
    assert result["dead_lettered"] == 0
    mock_sbs.complete_message.assert_called_once_with(mock_msg)


@patch("marketplace.services.webhook_v2_service.get_servicebus_service")
async def test_process_webhook_queue_no_callback_url(
    mock_get_sbs: MagicMock, db: AsyncSession,
):
    """Message with no callback_url is marked failed and completed."""
    mock_sbs = _mock_servicebus()
    mock_get_sbs.return_value = mock_sbs

    msg_body = {
        "subscription_id": "sub-nocb",
        "event": {"type": "test"},
        "attempt": 1,
    }
    mock_msg = MagicMock()
    mock_msg.__str__ = lambda self: json.dumps(msg_body)
    mock_sbs.receive_messages.return_value = [mock_msg]

    result = await svc.process_webhook_queue(db)

    assert result["failed"] == 1
    assert result["delivered"] == 0
    mock_sbs.complete_message.assert_called_once()


@patch("marketplace.services.webhook_v2_service.get_servicebus_service")
@patch("marketplace.services.webhook_v2_service.httpx.AsyncClient")
async def test_process_webhook_queue_http_failure_retry(
    mock_client_cls: MagicMock,
    mock_get_sbs: MagicMock,
    db: AsyncSession,
):
    """HTTP 500 on attempt 1 re-enqueues with attempt=2."""
    mock_sbs = _mock_servicebus()
    mock_get_sbs.return_value = mock_sbs

    msg_body = {
        "subscription_id": "sub-retry",
        "event": {"callback_url": "https://example.com/hook", "type": "test"},
        "attempt": 1,
    }
    mock_msg = MagicMock()
    mock_msg.__str__ = lambda self: json.dumps(msg_body)
    mock_sbs.receive_messages.return_value = [mock_msg]

    mock_response = MagicMock()
    mock_response.status_code = 500
    mock_client = AsyncMock()
    mock_client.post.return_value = mock_response
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)
    mock_client_cls.return_value = mock_client

    result = await svc.process_webhook_queue(db)

    assert result["failed"] == 1
    assert result["dead_lettered"] == 0
    # Should have re-enqueued with attempt=2
    retry_call = mock_sbs.send_message.call_args
    assert retry_call[0][1]["attempt"] == 2


@patch("marketplace.services.webhook_v2_service.get_servicebus_service")
@patch("marketplace.services.webhook_v2_service.httpx.AsyncClient")
async def test_process_webhook_queue_dead_letter_on_exhaustion(
    mock_client_cls: MagicMock,
    mock_get_sbs: MagicMock,
    db: AsyncSession,
):
    """After MAX_DELIVERY_ATTEMPTS, message is dead-lettered."""
    mock_sbs = _mock_servicebus()
    mock_get_sbs.return_value = mock_sbs

    msg_body = {
        "subscription_id": "sub-dlq",
        "event": {"callback_url": "https://example.com/hook", "type": "test"},
        "attempt": 3,  # Already at max
    }
    mock_msg = MagicMock()
    mock_msg.__str__ = lambda self: json.dumps(msg_body)
    mock_sbs.receive_messages.return_value = [mock_msg]

    mock_response = MagicMock()
    mock_response.status_code = 502
    mock_client = AsyncMock()
    mock_client.post.return_value = mock_response
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)
    mock_client_cls.return_value = mock_client

    result = await svc.process_webhook_queue(db)

    assert result["dead_lettered"] == 1
    mock_sbs.dead_letter_message.assert_called_once()

    # Verify DeadLetterEntry was persisted
    stmt = select(DeadLetterEntry)
    entries = (await db.execute(stmt)).scalars().all()
    assert len(entries) == 1
    assert "Exhausted" in entries[0].reason


@patch("marketplace.services.webhook_v2_service.get_servicebus_service")
@patch("marketplace.services.webhook_v2_service.httpx.AsyncClient")
async def test_process_webhook_queue_http_exception_retry(
    mock_client_cls: MagicMock,
    mock_get_sbs: MagicMock,
    db: AsyncSession,
):
    """HTTP connection error triggers retry re-enqueue."""
    mock_sbs = _mock_servicebus()
    mock_get_sbs.return_value = mock_sbs

    msg_body = {
        "subscription_id": "sub-exc",
        "event": {"callback_url": "https://example.com/hook", "type": "test"},
        "attempt": 2,
    }
    mock_msg = MagicMock()
    mock_msg.__str__ = lambda self: json.dumps(msg_body)
    mock_sbs.receive_messages.return_value = [mock_msg]

    mock_client = AsyncMock()
    mock_client.post.side_effect = ConnectionError("DNS resolution failed")
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)
    mock_client_cls.return_value = mock_client

    result = await svc.process_webhook_queue(db)

    assert result["failed"] == 1
    # Re-enqueued with attempt=3
    retry_call = mock_sbs.send_message.call_args
    assert retry_call[0][1]["attempt"] == 3


@patch("marketplace.services.webhook_v2_service.get_servicebus_service")
async def test_process_webhook_queue_invalid_json(
    mock_get_sbs: MagicMock, db: AsyncSession,
):
    """Invalid JSON in message body falls back to raw body handling."""
    mock_sbs = _mock_servicebus()
    mock_get_sbs.return_value = mock_sbs

    mock_msg = MagicMock()
    mock_msg.__str__ = lambda self: "not-valid-json"
    mock_sbs.receive_messages.return_value = [mock_msg]

    result = await svc.process_webhook_queue(db)

    # No callback_url in the raw fallback dict, so it gets marked failed
    assert result["failed"] == 1


@patch("marketplace.services.webhook_v2_service.get_servicebus_service")
async def test_process_webhook_queue_ssrf_blocked(
    mock_get_sbs: MagicMock, db: AsyncSession,
):
    """A callback URL that fails SSRF validation is blocked and marked failed."""
    mock_sbs = _mock_servicebus()
    mock_get_sbs.return_value = mock_sbs

    msg_body = {
        "subscription_id": "sub-ssrf",
        "event": {"callback_url": "http://169.254.169.254/metadata", "type": "test"},
        "attempt": 1,
    }
    mock_msg = MagicMock()
    mock_msg.__str__ = lambda self: json.dumps(msg_body)
    mock_sbs.receive_messages.return_value = [mock_msg]

    result = await svc.process_webhook_queue(db)

    assert result["failed"] == 1
    assert result["delivered"] == 0
    mock_sbs.complete_message.assert_called_once()

    # Verify the attempt was marked as blocked
    stmt = select(DeliveryAttempt).where(DeliveryAttempt.status == "blocked")
    rows = (await db.execute(stmt)).scalars().all()
    assert len(rows) == 1
    assert "URL validation failed" in rows[0].error_message


@patch("marketplace.services.webhook_v2_service.get_servicebus_service")
async def test_process_webhook_queue_outer_exception(
    mock_get_sbs: MagicMock, db: AsyncSession,
):
    """Unexpected exception in outer try block increments failed count."""
    mock_sbs = _mock_servicebus()
    mock_get_sbs.return_value = mock_sbs

    # Create a message that will cause an exception when str() is called
    mock_msg = MagicMock()
    mock_msg.__str__ = MagicMock(side_effect=RuntimeError("unexpected crash"))
    mock_sbs.receive_messages.return_value = [mock_msg]

    result = await svc.process_webhook_queue(db)

    assert result["failed"] == 1
    assert result["delivered"] == 0


# ---------------------------------------------------------------------------
# retry_dead_letters (bulk)
# ---------------------------------------------------------------------------


@patch("marketplace.services.webhook_v2_service.get_servicebus_service")
async def test_retry_dead_letters_empty(
    mock_get_sbs: MagicMock, db: AsyncSession,
):
    """retry_dead_letters with no entries returns empty list."""
    mock_sbs = _mock_servicebus()
    mock_get_sbs.return_value = mock_sbs

    results = await svc.retry_dead_letters(db)
    assert results == []


@patch("marketplace.services.webhook_v2_service.get_servicebus_service")
async def test_retry_dead_letters_re_enqueues(
    mock_get_sbs: MagicMock, db: AsyncSession,
):
    """retry_dead_letters re-enqueues un-retried entries and marks them retried."""
    mock_sbs = _mock_servicebus()
    mock_get_sbs.return_value = mock_sbs

    entry = await _create_dead_letter(db, message_body={
        "subscription_id": "sub-dlq-1",
        "event": {"type": "test"},
    })

    results = await svc.retry_dead_letters(db)

    assert len(results) == 1
    assert results[0]["entry_id"] == entry.id
    assert results[0]["re_enqueued"] is True
    assert results[0]["retry_count"] == 1

    # Verify entry marked as retried in DB
    await db.refresh(entry)
    assert entry.retried is True
    assert entry.retry_count == 1

    # Message sent with attempt=1 (reset)
    call_body = mock_sbs.send_message.call_args[0][1]
    assert call_body["attempt"] == 1


@patch("marketplace.services.webhook_v2_service.get_servicebus_service")
async def test_retry_dead_letters_skips_already_retried(
    mock_get_sbs: MagicMock, db: AsyncSession,
):
    """retry_dead_letters ignores entries where retried=True."""
    mock_sbs = _mock_servicebus()
    mock_get_sbs.return_value = mock_sbs

    await _create_dead_letter(db, retried=True, retry_count=1)

    results = await svc.retry_dead_letters(db)
    assert results == []


@patch("marketplace.services.webhook_v2_service.get_servicebus_service")
async def test_retry_dead_letters_invalid_json(
    mock_get_sbs: MagicMock, db: AsyncSession,
):
    """retry_dead_letters handles entries with invalid JSON gracefully."""
    mock_sbs = _mock_servicebus()
    mock_get_sbs.return_value = mock_sbs

    entry = DeadLetterEntry(
        id=_uid(),
        original_queue="webhooks",
        message_body="not-valid-json",
        reason="test",
        retried=False,
    )
    db.add(entry)
    await db.commit()

    results = await svc.retry_dead_letters(db)

    assert len(results) == 1
    assert "Invalid original message JSON" in results[0]["error"]


# ---------------------------------------------------------------------------
# retry_dead_letter (single entry)
# ---------------------------------------------------------------------------


@patch("marketplace.services.webhook_v2_service.get_servicebus_service")
async def test_retry_dead_letter_single_success(
    mock_get_sbs: MagicMock, db: AsyncSession,
):
    """retry_dead_letter re-enqueues a single entry successfully."""
    mock_sbs = _mock_servicebus()
    mock_get_sbs.return_value = mock_sbs

    entry = await _create_dead_letter(db, message_body={
        "subscription_id": "sub-single",
        "event": {"type": "test"},
    })

    result = await svc.retry_dead_letter(db, entry.id)

    assert result["entry_id"] == entry.id
    assert result["re_enqueued"] is True
    assert result["retry_count"] == 1


@patch("marketplace.services.webhook_v2_service.get_servicebus_service")
async def test_retry_dead_letter_not_found(
    mock_get_sbs: MagicMock, db: AsyncSession,
):
    """retry_dead_letter returns error for non-existent entry."""
    mock_sbs = _mock_servicebus()
    mock_get_sbs.return_value = mock_sbs

    result = await svc.retry_dead_letter(db, "nonexistent-id")

    assert "not found" in result["error"]


@patch("marketplace.services.webhook_v2_service.get_servicebus_service")
async def test_retry_dead_letter_invalid_json(
    mock_get_sbs: MagicMock, db: AsyncSession,
):
    """retry_dead_letter returns error for entry with invalid JSON."""
    mock_sbs = _mock_servicebus()
    mock_get_sbs.return_value = mock_sbs

    entry = DeadLetterEntry(
        id=_uid(),
        original_queue="webhooks",
        message_body="broken-json",
        reason="test",
        retried=False,
    )
    db.add(entry)
    await db.commit()

    result = await svc.retry_dead_letter(db, entry.id)

    assert "Invalid original message JSON" in result["error"]


@patch("marketplace.services.webhook_v2_service.get_servicebus_service")
async def test_retry_dead_letter_increments_retry_count(
    mock_get_sbs: MagicMock, db: AsyncSession,
):
    """retry_dead_letter increments retry_count on repeated retries."""
    mock_sbs = _mock_servicebus()
    mock_get_sbs.return_value = mock_sbs

    entry = await _create_dead_letter(db, retry_count=2)

    result = await svc.retry_dead_letter(db, entry.id)

    assert result["retry_count"] == 3
    await db.refresh(entry)
    assert entry.retry_count == 3


# ---------------------------------------------------------------------------
# get_delivery_stats
# ---------------------------------------------------------------------------


async def test_get_delivery_stats_empty(db: AsyncSession):
    """get_delivery_stats returns zeros when no data exists."""
    stats = await svc.get_delivery_stats(db)

    assert stats["total_sent"] == 0
    assert stats["total_failed"] == 0
    assert stats["dlq_depth"] == 0


async def test_get_delivery_stats_counts(db: AsyncSession):
    """get_delivery_stats counts delivered, failed, and DLQ entries correctly."""
    await _create_delivery_attempt(db, status="delivered")
    await _create_delivery_attempt(db, status="delivered")
    await _create_delivery_attempt(db, status="failed")
    await _create_dead_letter(db, retried=False)
    await _create_dead_letter(db, retried=True)  # Should not count in dlq_depth

    stats = await svc.get_delivery_stats(db)

    assert stats["total_sent"] == 2
    assert stats["total_failed"] == 1
    assert stats["dlq_depth"] == 1


# ---------------------------------------------------------------------------
# get_dead_letter_entries
# ---------------------------------------------------------------------------


async def test_get_dead_letter_entries_empty(db: AsyncSession):
    """get_dead_letter_entries returns empty list when no entries exist."""
    entries = await svc.get_dead_letter_entries(db)
    assert entries == []


async def test_get_dead_letter_entries_returns_dicts(db: AsyncSession):
    """get_dead_letter_entries returns list of dicts with expected keys."""
    await _create_dead_letter(db)
    await _create_dead_letter(db, retried=True, retry_count=2)

    entries = await svc.get_dead_letter_entries(db)

    assert len(entries) == 2
    for entry in entries:
        assert "id" in entry
        assert "original_queue" in entry
        assert "message_body" in entry
        assert "reason" in entry
        assert "retried" in entry
        assert "retry_count" in entry
        assert "dead_lettered_at" in entry


async def test_get_dead_letter_entries_limit(db: AsyncSession):
    """get_dead_letter_entries respects the limit parameter."""
    for _ in range(5):
        await _create_dead_letter(db)

    entries = await svc.get_dead_letter_entries(db, limit=3)
    assert len(entries) == 3


# ---------------------------------------------------------------------------
# WebhookV2Service class wrapper
# ---------------------------------------------------------------------------


@patch("marketplace.services.webhook_v2_service.get_servicebus_service")
async def test_class_wrapper_enqueue(
    mock_get_sbs: MagicMock, db: AsyncSession,
):
    """WebhookV2Service.enqueue delegates to module-level function."""
    mock_sbs = _mock_servicebus()
    mock_get_sbs.return_value = mock_sbs

    service = svc.WebhookV2Service()
    result = await service.enqueue(
        db, subscription_id="sub-wrap", event={"type": "test"},
    )
    assert "delivery_attempt_id" in result


@patch("marketplace.services.webhook_v2_service.get_servicebus_service")
async def test_class_wrapper_process_queue(
    mock_get_sbs: MagicMock, db: AsyncSession,
):
    """WebhookV2Service.process_queue delegates to module-level function."""
    mock_sbs = _mock_servicebus()
    mock_sbs.receive_messages.return_value = []
    mock_get_sbs.return_value = mock_sbs

    service = svc.WebhookV2Service()
    result = await service.process_queue(db)
    assert result["delivered"] == 0


@patch("marketplace.services.webhook_v2_service.get_servicebus_service")
async def test_class_wrapper_retry(
    mock_get_sbs: MagicMock, db: AsyncSession,
):
    """WebhookV2Service.retry delegates to retry_dead_letter."""
    mock_sbs = _mock_servicebus()
    mock_get_sbs.return_value = mock_sbs

    entry = await _create_dead_letter(db)

    service = svc.WebhookV2Service()
    result = await service.retry(db, entry.id)
    assert result["re_enqueued"] is True
