"""Webhook v2 models — dead-letter entries and delivery attempts for Service Bus webhooks."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, Index, Integer, String, Text, DateTime

from marketplace.database import Base


def utcnow():
    return datetime.now(timezone.utc)


class DeadLetterEntry(Base):
    """Record of a message moved to the dead-letter queue after repeated failures."""

    __tablename__ = "dead_letter_entries"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    original_queue = Column(String(100), nullable=False, default="webhooks")
    message_body = Column(Text, nullable=False, default="{}")
    reason = Column(String(500), default="")
    dead_lettered_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)
    retried = Column(Boolean, nullable=False, default=False)
    retry_count = Column(Integer, nullable=False, default=0)

    # Aliases for backward compatibility with existing code referencing old column names
    @property
    def queue_name(self) -> str:
        return self.original_queue

    @property
    def original_message_json(self) -> str:
        return self.message_body

    @property
    def created_at(self) -> datetime | None:
        return self.dead_lettered_at

    @property
    def retried_at(self) -> datetime | None:
        """Backward compat — return dead_lettered_at if retried."""
        return self.dead_lettered_at if self.retried else None

    __table_args__ = (
        Index("idx_dead_letter_queue", "original_queue"),
        Index("idx_dead_letter_created", "dead_lettered_at"),
    )


class DeliveryAttempt(Base):
    """Record of a single webhook delivery attempt."""

    __tablename__ = "webhook_delivery_attempts"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    webhook_id = Column(String(36), nullable=False, default="")
    event_type = Column(String(100), nullable=False, default="")
    target_url = Column(String(500), nullable=False, default="")
    status_code = Column(Integer, nullable=True)
    response_body = Column(Text, default="")
    attempted_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)
    success = Column(Boolean, nullable=False, default=False)
    error_message = Column(Text, default="")

    # Additional fields used by the webhook_v2_service
    subscription_id = Column(String(36), nullable=False, default="")
    event_json = Column(Text, nullable=False, default="{}")
    status = Column(String(20), nullable=False, default="pending")  # pending | delivered | failed
    attempt_number = Column(Integer, nullable=False, default=1)

    __table_args__ = (
        Index("idx_delivery_attempt_sub", "subscription_id"),
        Index("idx_delivery_attempt_status", "status"),
        Index("idx_delivery_attempt_webhook", "webhook_id"),
    )
