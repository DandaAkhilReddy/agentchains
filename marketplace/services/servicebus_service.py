"""Azure Service Bus producer/consumer service for reliable messaging.

Provides queue-based messaging with dead-letter support for webhook delivery
and async event processing.  Falls back to a no-op stub when the SDK or
connection string is not available.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from marketplace.config import settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Graceful SDK import
# ---------------------------------------------------------------------------
try:
    from azure.servicebus import ServiceBusClient, ServiceBusMessage
    from azure.servicebus.exceptions import ServiceBusError

    _HAS_SERVICEBUS = True
except ImportError:
    _HAS_SERVICEBUS = False
    logger.warning(
        "azure-servicebus is not installed — ServiceBusService will use stub implementation. "
        "Install with: pip install azure-servicebus"
    )


# ---------------------------------------------------------------------------
# ServiceBusService
# ---------------------------------------------------------------------------

class ServiceBusService:
    """Azure Service Bus integration for the AgentChains marketplace.

    Provides reliable queue-based messaging with dead-letter support.
    Falls back to a no-op stub when the SDK or connection string is not available.
    """

    def __init__(self, connection_string: str = "") -> None:
        self._connection_string = connection_string
        self._client: Any | None = None
        self._senders: dict[str, Any] = {}

        if _HAS_SERVICEBUS and self._connection_string:
            try:
                self._client = ServiceBusClient.from_connection_string(
                    conn_str=self._connection_string,
                    logging_enable=False,
                )
                logger.info("Azure Service Bus client initialised.")
            except Exception:
                logger.exception("Failed to initialise Service Bus client.")
                self._client = None
        else:
            if self._connection_string and not _HAS_SERVICEBUS:
                logger.warning("Service Bus connection string provided but SDK not installed.")
            elif not self._connection_string:
                logger.info("Service Bus connection string not configured — stub mode.")

    # ----- helpers ----------------------------------------------------------

    def _get_sender(self, queue_name: str) -> Any | None:
        """Return a cached sender for the given queue."""
        if not self._client:
            return None
        if queue_name not in self._senders:
            self._senders[queue_name] = self._client.get_queue_sender(queue_name=queue_name)
        return self._senders[queue_name]

    # ----- sending ----------------------------------------------------------

    def send_message(
        self,
        queue_name: str,
        message_body: str | dict,
        properties: dict[str, str] | None = None,
    ) -> bool:
        """Send a single message to a Service Bus queue.

        Args:
            queue_name: Target queue name.
            message_body: Message body (str or dict serialised to JSON).
            properties: Optional application properties to attach.

        Returns:
            True if message was sent, False on error or stub mode.
        """
        body = json.dumps(message_body) if isinstance(message_body, dict) else message_body

        if not self._client:
            logger.info(
                "[ServiceBus Stub] queue=%s body=%s properties=%s",
                queue_name,
                body[:500],
                properties,
            )
            return False

        try:
            sender = self._get_sender(queue_name)
            msg = ServiceBusMessage(body)
            if properties:
                msg.application_properties = {k: v for k, v in properties.items()}
            sender.send_messages(msg)
            logger.debug("Sent message to queue '%s'", queue_name)
            return True
        except Exception:
            logger.exception("Failed to send message to queue '%s'", queue_name)
            return False

    def send_batch(
        self,
        queue_name: str,
        messages: list[str | dict],
    ) -> int:
        """Send a batch of messages to a Service Bus queue.

        Args:
            queue_name: Target queue name.
            messages: List of message bodies.

        Returns:
            Number of messages sent successfully.
        """
        if not self._client:
            logger.info(
                "[ServiceBus Stub] batch queue=%s count=%d",
                queue_name,
                len(messages),
            )
            return 0

        try:
            sender = self._get_sender(queue_name)
            batch = sender.create_message_batch()
            sent = 0
            for msg_body in messages:
                body = json.dumps(msg_body) if isinstance(msg_body, dict) else msg_body
                try:
                    batch.add_message(ServiceBusMessage(body))
                    sent += 1
                except ValueError:
                    # Batch is full — send it and start a new one
                    sender.send_messages(batch)
                    batch = sender.create_message_batch()
                    batch.add_message(ServiceBusMessage(body))
                    sent += 1
            # Send remaining messages
            if sent > 0:
                sender.send_messages(batch)
            logger.debug("Sent batch of %d messages to queue '%s'", sent, queue_name)
            return sent
        except Exception:
            logger.exception("Failed to send batch to queue '%s'", queue_name)
            return 0

    # ----- receiving --------------------------------------------------------

    def receive_messages(
        self,
        queue_name: str,
        max_messages: int = 10,
        max_wait_time: int = 5,
    ) -> list[Any]:
        """Receive messages from a Service Bus queue.

        Args:
            queue_name: Source queue name.
            max_messages: Maximum number of messages to receive.
            max_wait_time: Maximum time in seconds to wait for messages.

        Returns:
            List of received messages (ServiceBusReceivedMessage objects).
        """
        if not self._client:
            logger.debug("receive_messages: no client — returning empty list.")
            return []

        try:
            receiver = self._client.get_queue_receiver(
                queue_name=queue_name,
                max_wait_time=max_wait_time,
            )
            with receiver:
                messages = receiver.receive_messages(
                    max_message_count=max_messages,
                    max_wait_time=max_wait_time,
                )
                return list(messages)
        except Exception:
            logger.exception("Failed to receive messages from queue '%s'", queue_name)
            return []

    # ----- message lifecycle ------------------------------------------------

    def complete_message(self, message: Any) -> bool:
        """Mark a message as completed (removes from queue).

        Args:
            message: The received message to complete.

        Returns:
            True if the message was completed successfully.
        """
        if not self._client:
            return False
        try:
            message.complete()
            return True
        except AttributeError:
            logger.warning("Message does not support .complete() — skipping.")
            return False
        except Exception:
            logger.exception("Failed to complete message.")
            return False

    def dead_letter_message(self, message: Any, reason: str = "") -> bool:
        """Send a message to the dead-letter queue.

        Args:
            message: The received message to dead-letter.
            reason: Reason for dead-lettering.

        Returns:
            True if the message was dead-lettered.
        """
        if not self._client:
            return False
        try:
            message.dead_letter(reason=reason, error_description=reason)
            return True
        except AttributeError:
            logger.warning("Message does not support .dead_letter() — skipping.")
            return False
        except Exception:
            logger.exception("Failed to dead-letter message.")
            return False

    def peek_dead_letters(
        self,
        queue_name: str,
        max_count: int = 10,
    ) -> list[Any]:
        """Peek at messages in the dead-letter sub-queue.

        Args:
            queue_name: The parent queue name.
            max_count: Maximum number of DLQ messages to peek.

        Returns:
            List of peeked dead-letter messages.
        """
        if not self._client:
            logger.debug("peek_dead_letters: no client — returning empty list.")
            return []

        dlq_name = f"{queue_name}/$deadletterqueue"
        try:
            receiver = self._client.get_queue_receiver(
                queue_name=dlq_name,
                max_wait_time=5,
            )
            with receiver:
                messages = receiver.peek_messages(max_message_count=max_count)
                return list(messages)
        except Exception:
            logger.exception("Failed to peek DLQ for queue '%s'", queue_name)
            return []

    # ----- lifecycle --------------------------------------------------------

    def close(self) -> None:
        """Close the Service Bus client and all cached senders."""
        for sender in self._senders.values():
            try:
                sender.close()
            except Exception:
                pass
        self._senders.clear()

        if self._client:
            try:
                self._client.close()
            except Exception:
                pass
            self._client = None
        logger.info("Service Bus client closed.")


# ---------------------------------------------------------------------------
# Singleton factory
# ---------------------------------------------------------------------------

_servicebus_service: ServiceBusService | None = None


def get_servicebus_service() -> ServiceBusService:
    """Return the singleton ServiceBusService, lazily initialised from settings."""
    global _servicebus_service
    if _servicebus_service is None:
        _servicebus_service = ServiceBusService(
            connection_string=settings.azure_servicebus_connection,
        )
    return _servicebus_service
