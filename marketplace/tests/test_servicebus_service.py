"""Tests for Azure Service Bus Service — producer/consumer with fallback stub.

Covers:
- ServiceBusService init: stub mode (no SDK), stub mode (no connection string),
  successful init, init failure
- send_message: stub returns False, success with properties, dict body serialization,
  send failure
- send_batch: stub, success, batch-full overflow, failure
- receive_messages: stub, success, failure
- complete_message: stub, success, AttributeError, failure
- dead_letter_message: stub, success, AttributeError, failure
- peek_dead_letters: stub, success, failure
- close: closes senders and client, handles errors, idempotent on None
- get_servicebus_service singleton factory
"""

import json
from unittest.mock import MagicMock, PropertyMock, patch

import pytest

from marketplace.services.servicebus_service import ServiceBusService, get_servicebus_service


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_stub_service() -> ServiceBusService:
    """Create a ServiceBusService in stub mode (no connection string)."""
    return ServiceBusService(connection_string="")


def _make_mock_service() -> tuple[ServiceBusService, MagicMock]:
    """Create a ServiceBusService with a mocked Azure client."""
    svc = ServiceBusService.__new__(ServiceBusService)
    svc._connection_string = "Endpoint=sb://test.servicebus.windows.net/;SharedAccessKeyName=test;SharedAccessKey=test"
    svc._senders = {}

    mock_client = MagicMock()
    svc._client = mock_client
    return svc, mock_client


# ---------------------------------------------------------------------------
# __init__ behavior
# ---------------------------------------------------------------------------

class TestInit:
    def test_stub_mode_no_connection_string(self):
        svc = ServiceBusService(connection_string="")
        assert svc._client is None
        assert svc._senders == {}

    def test_stub_mode_no_sdk(self):
        with patch("marketplace.services.servicebus_service._HAS_SERVICEBUS", False):
            svc = ServiceBusService(connection_string="some-connection-string")
            assert svc._client is None

    @patch("marketplace.services.servicebus_service._HAS_SERVICEBUS", True)
    def test_successful_init_with_sdk(self):
        mock_client = MagicMock()
        with patch(
            "marketplace.services.servicebus_service.ServiceBusClient"
        ) as MockSBClient:
            MockSBClient.from_connection_string.return_value = mock_client
            svc = ServiceBusService(connection_string="Endpoint=sb://test.servicebus.windows.net/")

        assert svc._client is mock_client

    @patch("marketplace.services.servicebus_service._HAS_SERVICEBUS", True)
    def test_init_failure_sets_client_none(self):
        with patch(
            "marketplace.services.servicebus_service.ServiceBusClient"
        ) as MockSBClient:
            MockSBClient.from_connection_string.side_effect = Exception("Connection failed")
            svc = ServiceBusService(connection_string="bad-conn-string")

        assert svc._client is None


# ---------------------------------------------------------------------------
# send_message
# ---------------------------------------------------------------------------

class TestSendMessage:
    def test_stub_returns_false(self):
        svc = _make_stub_service()
        result = svc.send_message("my-queue", "hello world")
        assert result is False

    def test_stub_with_dict_body(self):
        svc = _make_stub_service()
        result = svc.send_message("my-queue", {"event": "test", "data": 42})
        assert result is False

    def test_send_success(self):
        svc, mock_client = _make_mock_service()
        mock_sender = MagicMock()
        mock_client.get_queue_sender.return_value = mock_sender

        result = svc.send_message("events", "test message")

        assert result is True
        mock_sender.send_messages.assert_called_once()

    def test_send_with_properties(self):
        svc, mock_client = _make_mock_service()
        mock_sender = MagicMock()
        mock_client.get_queue_sender.return_value = mock_sender

        with patch("marketplace.services.servicebus_service.ServiceBusMessage") as MockMsg:
            mock_msg_instance = MagicMock()
            MockMsg.return_value = mock_msg_instance

            result = svc.send_message(
                "events",
                "test body",
                properties={"event_type": "purchase", "agent_id": "agent-001"},
            )

        assert result is True
        assert mock_msg_instance.application_properties == {
            "event_type": "purchase",
            "agent_id": "agent-001",
        }

    def test_send_dict_body_serialized(self):
        svc, mock_client = _make_mock_service()
        mock_sender = MagicMock()
        mock_client.get_queue_sender.return_value = mock_sender

        with patch("marketplace.services.servicebus_service.ServiceBusMessage") as MockMsg:
            MockMsg.return_value = MagicMock()
            svc.send_message("events", {"type": "test"})

            # The body should be JSON-serialized
            call_args = MockMsg.call_args[0][0]
            parsed = json.loads(call_args)
            assert parsed == {"type": "test"}

    def test_send_failure_returns_false(self):
        svc, mock_client = _make_mock_service()
        mock_sender = MagicMock()
        mock_sender.send_messages.side_effect = Exception("Send failed")
        mock_client.get_queue_sender.return_value = mock_sender

        result = svc.send_message("events", "will fail")
        assert result is False

    def test_sender_caching(self):
        svc, mock_client = _make_mock_service()
        mock_sender = MagicMock()
        mock_client.get_queue_sender.return_value = mock_sender

        svc.send_message("queue-a", "msg1")
        svc.send_message("queue-a", "msg2")

        # get_queue_sender should only be called once (cached)
        mock_client.get_queue_sender.assert_called_once_with(queue_name="queue-a")


# ---------------------------------------------------------------------------
# send_batch
# ---------------------------------------------------------------------------

class TestSendBatch:
    def test_stub_returns_zero(self):
        svc = _make_stub_service()
        result = svc.send_batch("my-queue", ["msg1", "msg2"])
        assert result == 0

    def test_batch_success(self):
        svc, mock_client = _make_mock_service()
        mock_sender = MagicMock()
        mock_batch = MagicMock()
        mock_sender.create_message_batch.return_value = mock_batch
        mock_client.get_queue_sender.return_value = mock_sender

        with patch("marketplace.services.servicebus_service.ServiceBusMessage") as MockMsg:
            MockMsg.side_effect = lambda body: MagicMock(body=body)
            result = svc.send_batch("events", ["msg1", "msg2", "msg3"])

        assert result == 3
        mock_sender.send_messages.assert_called_once()

    def test_batch_with_dict_messages(self):
        svc, mock_client = _make_mock_service()
        mock_sender = MagicMock()
        mock_batch = MagicMock()
        mock_sender.create_message_batch.return_value = mock_batch
        mock_client.get_queue_sender.return_value = mock_sender

        with patch("marketplace.services.servicebus_service.ServiceBusMessage") as MockMsg:
            MockMsg.side_effect = lambda body: MagicMock(body=body)
            result = svc.send_batch("events", [{"a": 1}, {"b": 2}])

        assert result == 2

    def test_batch_overflow_creates_new_batch(self):
        svc, mock_client = _make_mock_service()
        mock_sender = MagicMock()

        batch1 = MagicMock()
        batch2 = MagicMock()
        call_count = 0

        def add_message_side_effect(msg):
            nonlocal call_count
            call_count += 1
            if call_count == 2:
                raise ValueError("Batch is full")

        batch1.add_message.side_effect = add_message_side_effect
        mock_sender.create_message_batch.side_effect = [batch1, batch2]
        mock_client.get_queue_sender.return_value = mock_sender

        with patch("marketplace.services.servicebus_service.ServiceBusMessage") as MockMsg:
            MockMsg.side_effect = lambda body: MagicMock(body=body)
            result = svc.send_batch("events", ["msg1", "msg2", "msg3"])

        # msg1 added to batch1, msg2 triggers overflow -> batch1 sent, msg2 added to batch2
        # msg3 added to batch2, batch2 sent
        assert result == 3
        assert mock_sender.send_messages.call_count == 2

    def test_batch_failure_returns_zero(self):
        svc, mock_client = _make_mock_service()
        mock_sender = MagicMock()
        mock_sender.create_message_batch.side_effect = Exception("Batch create failed")
        mock_client.get_queue_sender.return_value = mock_sender

        result = svc.send_batch("events", ["msg1"])
        assert result == 0

    def test_empty_batch(self):
        svc = _make_stub_service()
        result = svc.send_batch("events", [])
        assert result == 0


# ---------------------------------------------------------------------------
# receive_messages
# ---------------------------------------------------------------------------

class TestReceiveMessages:
    def test_stub_returns_empty_list(self):
        svc = _make_stub_service()
        result = svc.receive_messages("my-queue")
        assert result == []

    def test_receive_success(self):
        svc, mock_client = _make_mock_service()
        mock_receiver = MagicMock()
        mock_messages = [MagicMock(), MagicMock()]
        mock_receiver.receive_messages.return_value = mock_messages
        mock_receiver.__enter__ = MagicMock(return_value=mock_receiver)
        mock_receiver.__exit__ = MagicMock(return_value=False)
        mock_client.get_queue_receiver.return_value = mock_receiver

        result = svc.receive_messages("events", max_messages=5, max_wait_time=10)

        assert len(result) == 2
        mock_client.get_queue_receiver.assert_called_once_with(
            queue_name="events", max_wait_time=10
        )

    def test_receive_failure_returns_empty(self):
        svc, mock_client = _make_mock_service()
        mock_client.get_queue_receiver.side_effect = Exception("Receive failed")

        result = svc.receive_messages("events")
        assert result == []


# ---------------------------------------------------------------------------
# complete_message
# ---------------------------------------------------------------------------

class TestCompleteMessage:
    def test_stub_returns_false(self):
        svc = _make_stub_service()
        result = svc.complete_message(MagicMock())
        assert result is False

    def test_complete_success(self):
        svc, _ = _make_mock_service()
        mock_msg = MagicMock()

        result = svc.complete_message(mock_msg)
        assert result is True
        mock_msg.complete.assert_called_once()

    def test_complete_attribute_error(self):
        svc, _ = _make_mock_service()
        mock_msg = MagicMock()
        mock_msg.complete.side_effect = AttributeError("no complete method")

        result = svc.complete_message(mock_msg)
        assert result is False

    def test_complete_general_exception(self):
        svc, _ = _make_mock_service()
        mock_msg = MagicMock()
        mock_msg.complete.side_effect = RuntimeError("unexpected")

        result = svc.complete_message(mock_msg)
        assert result is False


# ---------------------------------------------------------------------------
# dead_letter_message
# ---------------------------------------------------------------------------

class TestDeadLetterMessage:
    def test_stub_returns_false(self):
        svc = _make_stub_service()
        result = svc.dead_letter_message(MagicMock(), reason="test")
        assert result is False

    def test_dead_letter_success(self):
        svc, _ = _make_mock_service()
        mock_msg = MagicMock()

        result = svc.dead_letter_message(mock_msg, reason="processing failed")
        assert result is True
        mock_msg.dead_letter.assert_called_once_with(
            reason="processing failed", error_description="processing failed"
        )

    def test_dead_letter_attribute_error(self):
        svc, _ = _make_mock_service()
        mock_msg = MagicMock()
        mock_msg.dead_letter.side_effect = AttributeError("no dead_letter method")

        result = svc.dead_letter_message(mock_msg, reason="bad msg")
        assert result is False

    def test_dead_letter_general_exception(self):
        svc, _ = _make_mock_service()
        mock_msg = MagicMock()
        mock_msg.dead_letter.side_effect = RuntimeError("unexpected")

        result = svc.dead_letter_message(mock_msg, reason="error")
        assert result is False

    def test_dead_letter_empty_reason(self):
        svc, _ = _make_mock_service()
        mock_msg = MagicMock()

        result = svc.dead_letter_message(mock_msg)
        assert result is True
        mock_msg.dead_letter.assert_called_once_with(
            reason="", error_description=""
        )


# ---------------------------------------------------------------------------
# peek_dead_letters
# ---------------------------------------------------------------------------

class TestPeekDeadLetters:
    def test_stub_returns_empty(self):
        svc = _make_stub_service()
        result = svc.peek_dead_letters("my-queue")
        assert result == []

    def test_peek_success(self):
        svc, mock_client = _make_mock_service()
        mock_receiver = MagicMock()
        dlq_messages = [MagicMock(), MagicMock()]
        mock_receiver.peek_messages.return_value = dlq_messages
        mock_receiver.__enter__ = MagicMock(return_value=mock_receiver)
        mock_receiver.__exit__ = MagicMock(return_value=False)
        mock_client.get_queue_receiver.return_value = mock_receiver

        result = svc.peek_dead_letters("events", max_count=5)

        assert len(result) == 2
        mock_client.get_queue_receiver.assert_called_once_with(
            queue_name="events/$deadletterqueue", max_wait_time=5
        )

    def test_peek_failure_returns_empty(self):
        svc, mock_client = _make_mock_service()
        mock_client.get_queue_receiver.side_effect = Exception("DLQ error")

        result = svc.peek_dead_letters("events")
        assert result == []


# ---------------------------------------------------------------------------
# close
# ---------------------------------------------------------------------------

class TestClose:
    def test_close_closes_senders_and_client(self):
        svc, mock_client = _make_mock_service()
        mock_sender1 = MagicMock()
        mock_sender2 = MagicMock()
        svc._senders = {"q1": mock_sender1, "q2": mock_sender2}

        svc.close()

        mock_sender1.close.assert_called_once()
        mock_sender2.close.assert_called_once()
        mock_client.close.assert_called_once()
        assert svc._senders == {}
        assert svc._client is None

    def test_close_handles_sender_error(self):
        svc, mock_client = _make_mock_service()
        bad_sender = MagicMock()
        bad_sender.close.side_effect = Exception("sender close failed")
        svc._senders = {"q1": bad_sender}

        # Should not raise
        svc.close()
        assert svc._senders == {}

    def test_close_handles_client_error(self):
        svc, mock_client = _make_mock_service()
        mock_client.close.side_effect = Exception("client close failed")

        # Should not raise
        svc.close()
        assert svc._client is None

    def test_close_stub_mode(self):
        svc = _make_stub_service()
        # Should not raise
        svc.close()
        assert svc._client is None
        assert svc._senders == {}

    def test_close_idempotent(self):
        svc, mock_client = _make_mock_service()

        svc.close()
        svc.close()  # Second call should not raise

        assert svc._client is None


# ---------------------------------------------------------------------------
# _get_sender caching
# ---------------------------------------------------------------------------

class TestGetSender:
    def test_returns_none_without_client(self):
        svc = _make_stub_service()
        result = svc._get_sender("my-queue")
        assert result is None

    def test_creates_and_caches_sender(self):
        svc, mock_client = _make_mock_service()
        mock_sender = MagicMock()
        mock_client.get_queue_sender.return_value = mock_sender

        sender1 = svc._get_sender("my-queue")
        sender2 = svc._get_sender("my-queue")

        assert sender1 is mock_sender
        assert sender2 is mock_sender
        mock_client.get_queue_sender.assert_called_once_with(queue_name="my-queue")

    def test_different_queues_get_different_senders(self):
        svc, mock_client = _make_mock_service()
        sender_a = MagicMock()
        sender_b = MagicMock()
        mock_client.get_queue_sender.side_effect = [sender_a, sender_b]

        result_a = svc._get_sender("queue-a")
        result_b = svc._get_sender("queue-b")

        assert result_a is sender_a
        assert result_b is sender_b


# ---------------------------------------------------------------------------
# get_servicebus_service singleton
# ---------------------------------------------------------------------------

class TestGetServicebusService:
    def test_returns_service_instance(self):
        with patch(
            "marketplace.services.servicebus_service._servicebus_service", None
        ):
            with patch(
                "marketplace.services.servicebus_service.settings"
            ) as mock_settings:
                mock_settings.azure_servicebus_connection = ""
                svc = get_servicebus_service()
                assert isinstance(svc, ServiceBusService)

    def test_singleton_returns_same_instance(self):
        with patch(
            "marketplace.services.servicebus_service._servicebus_service", None
        ):
            with patch(
                "marketplace.services.servicebus_service.settings"
            ) as mock_settings:
                mock_settings.azure_servicebus_connection = ""
                svc1 = get_servicebus_service()

            # Patch _servicebus_service to be the returned instance
            with patch(
                "marketplace.services.servicebus_service._servicebus_service", svc1
            ):
                svc2 = get_servicebus_service()
                assert svc2 is svc1
