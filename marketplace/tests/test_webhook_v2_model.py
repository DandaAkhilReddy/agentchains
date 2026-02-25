"""Tests for webhook v2 models: DeadLetterEntry and DeliveryAttempt.

Covers: creation, defaults, backward-compat properties, queries.
"""

import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy import select

from marketplace.models.webhook_v2 import DeadLetterEntry, DeliveryAttempt, utcnow


def _uid() -> str:
    return str(uuid.uuid4())


# ---------------------------------------------------------------------------
# DeadLetterEntry
# ---------------------------------------------------------------------------


class TestDeadLetterEntryModel:
    async def test_create_with_defaults(self, db):
        entry = DeadLetterEntry(
            id=_uid(),
            message_body='{"event": "listing.created", "data": {}}',
            reason="Max retries exceeded",
        )
        db.add(entry)
        await db.commit()
        await db.refresh(entry)

        assert entry.original_queue == "webhooks"
        assert entry.retried is False
        assert entry.retry_count == 0
        assert entry.dead_lettered_at is not None

    async def test_custom_queue_name(self, db):
        entry = DeadLetterEntry(
            id=_uid(),
            original_queue="webhook-delivery",
            message_body="{}",
        )
        db.add(entry)
        await db.commit()
        await db.refresh(entry)

        assert entry.original_queue == "webhook-delivery"

    async def test_retried_entry(self, db):
        entry = DeadLetterEntry(
            id=_uid(),
            message_body='{"event": "test"}',
            reason="timeout",
            retried=True,
            retry_count=3,
        )
        db.add(entry)
        await db.commit()
        await db.refresh(entry)

        assert entry.retried is True
        assert entry.retry_count == 3


class TestDeadLetterEntryBackwardCompat:
    """Tests for backward compatibility properties."""

    async def test_queue_name_property(self, db):
        entry = DeadLetterEntry(
            id=_uid(),
            original_queue="my-queue",
            message_body="{}",
        )
        db.add(entry)
        await db.commit()
        await db.refresh(entry)

        assert entry.queue_name == "my-queue"

    async def test_original_message_json_property(self, db):
        body = '{"key": "value"}'
        entry = DeadLetterEntry(
            id=_uid(),
            message_body=body,
        )
        db.add(entry)
        await db.commit()
        await db.refresh(entry)

        assert entry.original_message_json == body

    async def test_created_at_property(self, db):
        entry = DeadLetterEntry(
            id=_uid(),
            message_body="{}",
        )
        db.add(entry)
        await db.commit()
        await db.refresh(entry)

        assert entry.created_at == entry.dead_lettered_at

    async def test_retried_at_when_retried(self, db):
        entry = DeadLetterEntry(
            id=_uid(),
            message_body="{}",
            retried=True,
        )
        db.add(entry)
        await db.commit()
        await db.refresh(entry)

        assert entry.retried_at == entry.dead_lettered_at

    async def test_retried_at_when_not_retried(self, db):
        entry = DeadLetterEntry(
            id=_uid(),
            message_body="{}",
            retried=False,
        )
        db.add(entry)
        await db.commit()
        await db.refresh(entry)

        assert entry.retried_at is None


class TestDeadLetterEntryQueries:
    async def test_query_by_queue(self, db):
        for queue in ("webhooks", "webhook-delivery", "webhooks"):
            entry = DeadLetterEntry(
                id=_uid(),
                original_queue=queue,
                message_body="{}",
            )
            db.add(entry)
        await db.commit()

        result = await db.execute(
            select(DeadLetterEntry).where(DeadLetterEntry.original_queue == "webhooks")
        )
        entries = list(result.scalars().all())
        assert len(entries) == 2

    async def test_query_unretried_entries(self, db):
        for retried in (True, False, False, True, False):
            entry = DeadLetterEntry(
                id=_uid(),
                message_body="{}",
                retried=retried,
            )
            db.add(entry)
        await db.commit()

        result = await db.execute(
            select(DeadLetterEntry).where(DeadLetterEntry.retried == False)  # noqa: E712
        )
        unretried = list(result.scalars().all())
        assert len(unretried) == 3


# ---------------------------------------------------------------------------
# DeliveryAttempt
# ---------------------------------------------------------------------------


class TestDeliveryAttemptModel:
    async def test_create_with_defaults(self, db):
        attempt = DeliveryAttempt(
            id=_uid(),
            webhook_id=_uid(),
            event_type="listing.created",
            target_url="https://example.com/webhook",
        )
        db.add(attempt)
        await db.commit()
        await db.refresh(attempt)

        assert attempt.success is False
        assert attempt.status == "pending"
        assert attempt.attempt_number == 1
        assert attempt.attempted_at is not None
        assert attempt.status_code is None
        assert attempt.response_body == ""
        assert attempt.error_message == ""

    async def test_successful_delivery(self, db):
        attempt = DeliveryAttempt(
            id=_uid(),
            webhook_id=_uid(),
            event_type="transaction.completed",
            target_url="https://example.com/hook",
            status_code=200,
            response_body='{"ok": true}',
            success=True,
            status="delivered",
        )
        db.add(attempt)
        await db.commit()
        await db.refresh(attempt)

        assert attempt.success is True
        assert attempt.status_code == 200
        assert attempt.status == "delivered"

    async def test_failed_delivery(self, db):
        attempt = DeliveryAttempt(
            id=_uid(),
            webhook_id=_uid(),
            event_type="listing.deleted",
            target_url="https://dead-server.example.com/hook",
            status_code=500,
            success=False,
            status="failed",
            error_message="Internal server error",
            attempt_number=3,
        )
        db.add(attempt)
        await db.commit()
        await db.refresh(attempt)

        assert attempt.success is False
        assert attempt.status_code == 500
        assert attempt.status == "failed"
        assert attempt.attempt_number == 3
        assert "Internal server error" in attempt.error_message

    async def test_subscription_and_event_json_fields(self, db):
        sub_id = _uid()
        event_json = '{"type": "listing.created", "payload": {"id": "123"}}'
        attempt = DeliveryAttempt(
            id=_uid(),
            webhook_id=_uid(),
            event_type="listing.created",
            target_url="https://example.com",
            subscription_id=sub_id,
            event_json=event_json,
        )
        db.add(attempt)
        await db.commit()
        await db.refresh(attempt)

        assert attempt.subscription_id == sub_id
        assert attempt.event_json == event_json


class TestDeliveryAttemptQueries:
    async def test_query_by_subscription(self, db):
        sub_id = _uid()
        for i in range(3):
            attempt = DeliveryAttempt(
                id=_uid(),
                webhook_id=_uid(),
                event_type="test",
                target_url="https://example.com",
                subscription_id=sub_id,
                attempt_number=i + 1,
            )
            db.add(attempt)
        await db.commit()

        result = await db.execute(
            select(DeliveryAttempt).where(DeliveryAttempt.subscription_id == sub_id)
        )
        attempts = list(result.scalars().all())
        assert len(attempts) == 3

    async def test_query_by_status(self, db):
        for status in ("pending", "delivered", "failed", "pending"):
            attempt = DeliveryAttempt(
                id=_uid(),
                webhook_id=_uid(),
                event_type="test",
                target_url="https://example.com",
                status=status,
            )
            db.add(attempt)
        await db.commit()

        result = await db.execute(
            select(DeliveryAttempt).where(DeliveryAttempt.status == "pending")
        )
        pending = list(result.scalars().all())
        assert len(pending) == 2

    async def test_query_by_webhook_id(self, db):
        webhook_id = _uid()
        for _ in range(2):
            attempt = DeliveryAttempt(
                id=_uid(),
                webhook_id=webhook_id,
                event_type="test",
                target_url="https://example.com",
            )
            db.add(attempt)
        await db.commit()

        result = await db.execute(
            select(DeliveryAttempt).where(DeliveryAttempt.webhook_id == webhook_id)
        )
        found = list(result.scalars().all())
        assert len(found) == 2
