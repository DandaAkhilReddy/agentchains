"""Webhook v2 delivery service — enqueue webhook events via Service Bus with retry and DLQ support."""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone

import httpx
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from marketplace.models.webhook_v2 import DeadLetterEntry, DeliveryAttempt
from marketplace.services.servicebus_service import get_servicebus_service

logger = logging.getLogger(__name__)

WEBHOOK_QUEUE = "webhooks"
MAX_DELIVERY_ATTEMPTS = 3


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# Enqueue
# ---------------------------------------------------------------------------


async def enqueue_webhook_delivery(
    db: AsyncSession,
    subscription_id: str,
    event: dict,
) -> dict:
    """Put a webhook event on the webhooks Service Bus queue for async delivery.

    Instead of fire-and-forget HTTP, this enqueues the event on Service Bus so
    that delivery is retried with dead-letter support on failure.

    Also creates a pending DeliveryAttempt record for tracking.
    """
    svc = get_servicebus_service()

    message = {
        "subscription_id": subscription_id,
        "event": event,
        "enqueued_at": _utcnow().isoformat(),
        "attempt": 1,
    }

    # Create initial delivery attempt record
    attempt = DeliveryAttempt(
        id=str(uuid.uuid4()),
        subscription_id=subscription_id,
        event_json=json.dumps(event, default=str),
        status="pending",
        attempt_number=1,
        attempted_at=_utcnow(),
    )
    db.add(attempt)
    await db.commit()
    await db.refresh(attempt)

    sent = svc.send_message(
        WEBHOOK_QUEUE,
        message,
        properties={"subscription_id": subscription_id, "attempt": "1"},
    )

    logger.info(
        "Enqueued webhook delivery for subscription '%s' (sent=%s)",
        subscription_id,
        sent,
    )
    return {
        "delivery_attempt_id": attempt.id,
        "subscription_id": subscription_id,
        "queued": sent,
    }


# ---------------------------------------------------------------------------
# Consumer: process the webhook queue
# ---------------------------------------------------------------------------


async def process_webhook_queue(db: AsyncSession) -> dict:
    """Consumer loop: pull messages from the webhooks queue and deliver them.

    For each message, attempt HTTP POST to the subscription's callback URL.
    On failure, retry up to MAX_DELIVERY_ATTEMPTS. After exhaustion, dead-letter.

    Returns summary statistics.
    """
    svc = get_servicebus_service()
    delivered = 0
    failed = 0
    dead_lettered = 0

    messages = svc.receive_messages(WEBHOOK_QUEUE, max_messages=10, max_wait_time=5)

    for msg in messages:
        try:
            body_str = str(msg)
            try:
                body = json.loads(body_str)
            except (json.JSONDecodeError, TypeError):
                body = {"raw": body_str}

            subscription_id = body.get("subscription_id", "")
            event = body.get("event", {})
            attempt_num = body.get("attempt", 1)
            callback_url = event.get("callback_url", "")

            # Record this delivery attempt
            attempt = DeliveryAttempt(
                id=str(uuid.uuid4()),
                subscription_id=subscription_id,
                event_json=json.dumps(event, default=str),
                status="pending",
                attempt_number=attempt_num,
                attempted_at=_utcnow(),
            )
            db.add(attempt)
            await db.flush()

            if not callback_url:
                attempt.status = "failed"
                attempt.error_message = "No callback_url provided"
                await db.commit()
                svc.complete_message(msg)
                failed += 1
                continue

            # Try delivering
            try:
                async with httpx.AsyncClient(timeout=10.0) as client:
                    resp = await client.post(callback_url, json=event)
                    attempt.response_code = resp.status_code

                    if 200 <= resp.status_code < 300:
                        attempt.status = "delivered"
                        await db.commit()
                        svc.complete_message(msg)
                        delivered += 1
                        logger.info("Delivered webhook to '%s' (attempt %d)", callback_url, attempt_num)
                        continue
                    else:
                        attempt.status = "failed"
                        attempt.error_message = f"HTTP {resp.status_code}"

            except Exception as exc:
                attempt.status = "failed"
                attempt.error_message = str(exc)[:500]

            await db.commit()

            # Check retry exhaustion
            if attempt_num >= MAX_DELIVERY_ATTEMPTS:
                # Move to dead-letter queue
                entry = DeadLetterEntry(
                    id=str(uuid.uuid4()),
                    original_queue=WEBHOOK_QUEUE,
                    message_body=json.dumps(body, default=str),
                    reason=f"Exhausted {MAX_DELIVERY_ATTEMPTS} delivery attempts",
                    dead_lettered_at=_utcnow(),
                )
                db.add(entry)
                await db.commit()

                svc.dead_letter_message(msg, reason=f"Exhausted {MAX_DELIVERY_ATTEMPTS} delivery attempts")
                dead_lettered += 1
                logger.warning(
                    "Webhook for subscription '%s' dead-lettered after %d attempts",
                    subscription_id,
                    attempt_num,
                )
            else:
                # Re-enqueue with incremented attempt counter
                retry_body = dict(body)
                retry_body["attempt"] = attempt_num + 1
                svc.send_message(
                    WEBHOOK_QUEUE,
                    retry_body,
                    properties={"subscription_id": subscription_id, "attempt": str(attempt_num + 1)},
                )
                svc.complete_message(msg)
                failed += 1

        except Exception:
            logger.exception("Error processing webhook message")
            failed += 1

    return {
        "delivered": delivered,
        "failed": failed,
        "dead_lettered": dead_lettered,
    }


# ---------------------------------------------------------------------------
# Dead-letter management
# ---------------------------------------------------------------------------


async def retry_dead_letters(db: AsyncSession) -> list[dict]:
    """Replay all un-retried dead-letter entries by re-enqueuing to Service Bus.

    Returns a list of results for each entry.
    """
    svc = get_servicebus_service()

    result = await db.execute(
        select(DeadLetterEntry)
        .where(DeadLetterEntry.retried == False)  # noqa: E712
        .order_by(DeadLetterEntry.dead_lettered_at.asc())
    )
    entries = list(result.scalars().all())
    results = []

    for entry in entries:
        try:
            original_message = json.loads(entry.message_body)
        except (json.JSONDecodeError, TypeError):
            results.append({"entry_id": entry.id, "error": "Invalid original message JSON"})
            continue

        original_message["attempt"] = 1  # Reset attempt counter
        subscription_id = original_message.get("subscription_id", "")

        sent = svc.send_message(
            WEBHOOK_QUEUE,
            original_message,
            properties={"subscription_id": subscription_id, "attempt": "1", "retried_from_dlq": entry.id},
        )

        entry.retried = True
        entry.retry_count = (entry.retry_count or 0) + 1
        await db.flush()

        results.append({
            "entry_id": entry.id,
            "re_enqueued": sent,
            "retry_count": entry.retry_count,
        })

    await db.commit()
    logger.info("Retried %d dead-letter entries", len(results))
    return results


async def get_delivery_stats(db: AsyncSession) -> dict:
    """Return summary statistics for webhook delivery.

    Returns dict with total_sent, total_failed, dlq_depth.
    """
    # Total delivered
    delivered_result = await db.execute(
        select(func.count(DeliveryAttempt.id)).where(DeliveryAttempt.status == "delivered")
    )
    total_sent = delivered_result.scalar() or 0

    # Total failed
    failed_result = await db.execute(
        select(func.count(DeliveryAttempt.id)).where(DeliveryAttempt.status == "failed")
    )
    total_failed = failed_result.scalar() or 0

    # DLQ depth (entries that have never been retried)
    dlq_result = await db.execute(
        select(func.count(DeadLetterEntry.id)).where(DeadLetterEntry.retried == False)  # noqa: E712
    )
    dlq_depth = dlq_result.scalar() or 0

    return {
        "total_sent": total_sent,
        "total_failed": total_failed,
        "dlq_depth": dlq_depth,
    }


async def get_dead_letter_entries(db: AsyncSession, limit: int = 50) -> list[dict]:
    """List recent dead-letter entries."""
    result = await db.execute(
        select(DeadLetterEntry)
        .order_by(DeadLetterEntry.dead_lettered_at.desc())
        .limit(limit)
    )
    entries = list(result.scalars().all())

    return [
        {
            "id": entry.id,
            "original_queue": entry.original_queue,
            "message_body": entry.message_body,
            "reason": entry.reason,
            "retried": entry.retried,
            "retry_count": entry.retry_count,
            "dead_lettered_at": entry.dead_lettered_at.isoformat() if entry.dead_lettered_at else None,
        }
        for entry in entries
    ]


async def retry_dead_letter(db: AsyncSession, entry_id: str) -> dict:
    """Retry a single dead-lettered delivery by re-enqueuing the original message."""
    svc = get_servicebus_service()

    result = await db.execute(
        select(DeadLetterEntry).where(DeadLetterEntry.id == entry_id)
    )
    entry = result.scalar_one_or_none()

    if not entry:
        return {"error": "Dead letter entry not found", "entry_id": entry_id}

    try:
        original_message = json.loads(entry.message_body)
    except (json.JSONDecodeError, TypeError):
        return {"error": "Invalid original message JSON", "entry_id": entry_id}

    original_message["attempt"] = 1  # Reset attempt counter
    subscription_id = original_message.get("subscription_id", "")

    sent = svc.send_message(
        WEBHOOK_QUEUE,
        original_message,
        properties={"subscription_id": subscription_id, "attempt": "1", "retried_from_dlq": entry_id},
    )

    entry.retried = True
    entry.retry_count = (entry.retry_count or 0) + 1
    await db.commit()

    logger.info("Retried dead-letter entry '%s' (sent=%s)", entry_id, sent)
    return {
        "entry_id": entry_id,
        "re_enqueued": sent,
        "retry_count": entry.retry_count,
    }


class WebhookV2Service:
    """Class wrapper for webhook v2 delivery functions."""

    async def enqueue(self, db, **kwargs):
        return await enqueue_webhook_delivery(db, **kwargs)

    async def process_queue(self, db, **kwargs):
        return await process_webhook_queue(db, **kwargs)

    async def retry(self, db, entry_id):
        return await retry_dead_letter(db, entry_id)
