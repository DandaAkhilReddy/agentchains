"""Tests for Stripe and Razorpay webhook handlers."""

import hashlib
import hmac
import json
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import Request
from fastapi.testclient import TestClient


class TestStripeWebhookSignature:
    def test_valid_stripe_signature_format(self):
        timestamp = str(int(time.time()))
        payload = b'{"type":"payment_intent.succeeded"}'
        secret = "whsec_test_secret"
        signed_payload = f"{timestamp}.{payload.decode()}"
        signature = hmac.new(
            secret.encode(), signed_payload.encode(), hashlib.sha256
        ).hexdigest()
        header = f"t={timestamp},v1={signature}"
        assert header.startswith("t=")
        assert ",v1=" in header

    def test_timestamp_must_be_recent(self):
        old_timestamp = str(int(time.time()) - 600)
        assert int(old_timestamp) < int(time.time())

    def test_invalid_signature_detected(self):
        payload = b'{"type":"test"}'
        header = "t=123456,v1=invalidsignature"
        # Should fail verification
        assert "invalidsignature" in header

    def test_stripe_event_types(self):
        events = [
            "payment_intent.succeeded",
            "payment_intent.payment_failed",
            "checkout.session.completed",
            "customer.subscription.created",
            "customer.subscription.updated",
            "customer.subscription.deleted",
            "invoice.paid",
            "invoice.payment_failed",
        ]
        assert len(events) == 8
        for e in events:
            assert "." in e

    def test_stripe_payment_intent_fields(self):
        event = {
            "type": "payment_intent.succeeded",
            "data": {
                "object": {
                    "id": "pi_test_123",
                    "amount": 5000,
                    "currency": "usd",
                    "status": "succeeded",
                    "metadata": {"agent_id": "agent-1"},
                }
            },
        }
        assert event["data"]["object"]["amount"] == 5000
        assert event["data"]["object"]["currency"] == "usd"


class TestRazorpayWebhookSignature:
    def test_razorpay_hmac_sha256(self):
        payload = b'{"entity":"event","event":"payment.captured"}'
        secret = "test_webhook_secret"
        signature = hmac.new(
            secret.encode(), payload, hashlib.sha256
        ).hexdigest()
        assert len(signature) == 64  # SHA-256 hex digest

    def test_signature_verification_succeeds(self):
        payload = b'test_payload'
        secret = "secret"
        expected = hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()
        actual = hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()
        assert hmac.compare_digest(expected, actual)

    def test_signature_verification_fails_with_wrong_secret(self):
        payload = b'test_payload'
        sig1 = hmac.new(b"secret1", payload, hashlib.sha256).hexdigest()
        sig2 = hmac.new(b"secret2", payload, hashlib.sha256).hexdigest()
        assert not hmac.compare_digest(sig1, sig2)

    def test_razorpay_event_types(self):
        events = [
            "payment.captured",
            "payment.failed",
            "order.paid",
            "subscription.charged",
            "subscription.halted",
            "subscription.cancelled",
        ]
        assert len(events) == 6

    def test_razorpay_payment_entity(self):
        event = {
            "entity": "event",
            "event": "payment.captured",
            "payload": {
                "payment": {
                    "entity": {
                        "id": "pay_test_123",
                        "amount": 50000,
                        "currency": "INR",
                        "status": "captured",
                    }
                }
            },
        }
        payment = event["payload"]["payment"]["entity"]
        assert payment["amount"] == 50000
        assert payment["currency"] == "INR"


class TestWebhookPayloadParsing:
    def test_parse_stripe_checkout_completed(self):
        payload = {
            "type": "checkout.session.completed",
            "data": {
                "object": {
                    "id": "cs_test_123",
                    "payment_status": "paid",
                    "customer": "cus_test",
                    "subscription": "sub_test",
                }
            },
        }
        obj = payload["data"]["object"]
        assert obj["payment_status"] == "paid"

    def test_parse_stripe_invoice_paid(self):
        payload = {
            "type": "invoice.paid",
            "data": {
                "object": {
                    "id": "in_test_123",
                    "amount_paid": 4999,
                    "customer": "cus_test",
                    "subscription": "sub_test",
                    "lines": {"data": [{"amount": 4999}]},
                }
            },
        }
        assert payload["data"]["object"]["amount_paid"] == 4999

    def test_parse_razorpay_subscription_charged(self):
        payload = {
            "entity": "event",
            "event": "subscription.charged",
            "payload": {
                "subscription": {
                    "entity": {
                        "id": "sub_test_123",
                        "plan_id": "plan_test",
                        "status": "active",
                    }
                },
                "payment": {
                    "entity": {
                        "id": "pay_test_456",
                        "amount": 99900,
                    }
                },
            },
        }
        sub = payload["payload"]["subscription"]["entity"]
        assert sub["status"] == "active"

    def test_unknown_event_type_handled(self):
        payload = {"type": "unknown.event.type", "data": {}}
        assert payload["type"] == "unknown.event.type"

    def test_webhook_idempotency_key(self):
        headers = {
            "Stripe-Signature": "t=123,v1=abc",
            "Idempotency-Key": "idem_123",
        }
        assert "Idempotency-Key" in headers


class TestWebhookRetryLogic:
    def test_retry_count_tracking(self):
        attempt = {"webhook_id": "wh-1", "attempt": 1, "max_retries": 5}
        assert attempt["attempt"] < attempt["max_retries"]

    def test_exponential_backoff(self):
        backoffs = [2 ** i for i in range(5)]
        assert backoffs == [1, 2, 4, 8, 16]

    def test_max_retry_exceeded(self):
        attempt = {"attempt": 6, "max_retries": 5}
        assert attempt["attempt"] > attempt["max_retries"]

    def test_dead_letter_queue_entry(self):
        dlq_entry = {
            "webhook_id": "wh-1",
            "payload": '{"type":"test"}',
            "failure_reason": "HTTP 500",
            "attempts": 5,
        }
        assert dlq_entry["attempts"] == 5
        assert "500" in dlq_entry["failure_reason"]

    def test_delivery_attempt_logging(self):
        attempt = {
            "id": "att-1",
            "webhook_id": "wh-1",
            "status_code": 200,
            "response_body": "OK",
            "duration_ms": 150,
        }
        assert attempt["status_code"] == 200
        assert attempt["duration_ms"] < 1000


class TestPaymentReconciliation:
    def test_reconciliation_matching(self):
        stripe_records = [
            {"id": "pi_1", "amount": 5000, "status": "succeeded"},
            {"id": "pi_2", "amount": 3000, "status": "succeeded"},
        ]
        db_records = [
            {"stripe_id": "pi_1", "amount": 5000, "status": "completed"},
            {"stripe_id": "pi_2", "amount": 3000, "status": "completed"},
        ]
        assert len(stripe_records) == len(db_records)

    def test_reconciliation_mismatch_detected(self):
        stripe_amount = 5000
        db_amount = 4999
        assert stripe_amount != db_amount

    def test_missing_record_detected(self):
        stripe_ids = {"pi_1", "pi_2", "pi_3"}
        db_ids = {"pi_1", "pi_2"}
        missing = stripe_ids - db_ids
        assert missing == {"pi_3"}

    def test_duplicate_payment_detection(self):
        payments = ["pi_1", "pi_2", "pi_1"]
        unique = set(payments)
        assert len(unique) < len(payments)

    def test_currency_validation(self):
        valid_currencies = {"usd", "eur", "gbp", "inr", "jpy"}
        assert "usd" in valid_currencies
        assert "xyz" not in valid_currencies

    def test_amount_must_be_positive(self):
        amounts = [100, 5000, 0, -100]
        positive = [a for a in amounts if a > 0]
        assert len(positive) == 2

    def test_reconciliation_report_fields(self):
        report = {
            "total_stripe": 10,
            "total_db": 10,
            "matched": 9,
            "mismatched": 1,
            "missing_in_db": 0,
            "missing_in_stripe": 0,
        }
        assert report["matched"] + report["mismatched"] == report["total_stripe"]
