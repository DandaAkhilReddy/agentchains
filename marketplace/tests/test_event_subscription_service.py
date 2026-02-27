"""Comprehensive tests for event_subscription_service — webhook subscriptions,
event envelope construction, signature verification, SSRF validation, and delivery.

Uses in-memory SQLite via conftest fixtures.  asyncio_mode = "auto".
"""

from __future__ import annotations

import hashlib
import hmac
import json
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from marketplace.models.agent_trust import EventSubscription, WebhookDelivery
from marketplace.services import event_subscription_service as svc


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_sub(agent_id: str, callback_url: str = "https://example.com/hook",
              event_types: list[str] | None = None, status: str = "active",
              secret: str = "whsec_test") -> EventSubscription:
    return EventSubscription(
        id=str(uuid.uuid4()),
        agent_id=agent_id,
        callback_url=callback_url,
        event_types_json=json.dumps(event_types or ["*"]),
        secret=secret,
        status=status,
        failure_count=0,
    )


# ---------------------------------------------------------------------------
# _json_load
# ---------------------------------------------------------------------------

class TestJsonLoad:
    def test_none_returns_fallback(self):
        assert svc._json_load(None, []) == []

    def test_dict_passthrough(self):
        d = {"a": 1}
        assert svc._json_load(d, []) == d

    def test_list_passthrough(self):
        lst = [1, 2]
        assert svc._json_load(lst, {}) == lst

    def test_valid_json_string(self):
        assert svc._json_load('["foo"]', []) == ["foo"]

    def test_invalid_json_string_returns_fallback(self):
        assert svc._json_load("not json", "default") == "default"

    def test_int_returns_fallback(self):
        assert svc._json_load(42, "fallback") == "fallback"


# ---------------------------------------------------------------------------
# _canonical_payload / _sign
# ---------------------------------------------------------------------------

class TestCanonicalPayloadAndSigning:
    def test_canonical_payload_sorted_no_spaces(self):
        result = svc._canonical_payload({"b": 2, "a": 1})
        assert result == '{"a":1,"b":2}'

    def test_sign_format(self):
        sig = svc._sign("secret", {"x": 1})
        assert sig.startswith("sha256=")
        # Must be deterministic
        assert sig == svc._sign("secret", {"x": 1})

    def test_sign_differs_with_different_secret(self):
        sig1 = svc._sign("secret1", {"x": 1})
        sig2 = svc._sign("secret2", {"x": 1})
        assert sig1 != sig2


# ---------------------------------------------------------------------------
# _event_signing_secret
# ---------------------------------------------------------------------------

class TestEventSigningSecret:
    def test_returns_configured_secret(self):
        with patch.object(svc.settings, "event_signing_secret", "my-secret"):
            assert svc._event_signing_secret() == "my-secret"

    def test_raises_on_empty_secret(self):
        with patch.object(svc.settings, "event_signing_secret", ""):
            with pytest.raises(RuntimeError, match="EVENT_SIGNING_SECRET must be configured"):
                svc._event_signing_secret()

    def test_raises_on_whitespace_only_secret(self):
        with patch.object(svc.settings, "event_signing_secret", "   "):
            with pytest.raises(RuntimeError, match="EVENT_SIGNING_SECRET must be configured"):
                svc._event_signing_secret()


# ---------------------------------------------------------------------------
# verify_event_signature
# ---------------------------------------------------------------------------

class TestVerifyEventSignature:
    def test_valid_signature_accepted(self):
        payload = {"event": "test"}
        sig = svc._sign("current-secret", payload)
        assert svc.verify_event_signature(
            payload=payload, signature=sig,
            current_secret="current-secret",
        ) is True

    def test_invalid_signature_rejected(self):
        assert svc.verify_event_signature(
            payload={"x": 1}, signature="sha256=bad",
            current_secret="secret",
        ) is False

    def test_empty_signature_rejected(self):
        assert svc.verify_event_signature(
            payload={"x": 1}, signature="",
            current_secret="secret",
        ) is False

    def test_previous_secret_accepted_during_rotation(self):
        payload = {"event": "rotate"}
        old_sig = svc._sign("old-secret", payload)
        assert svc.verify_event_signature(
            payload=payload, signature=old_sig,
            current_secret="new-secret", previous_secret="old-secret",
        ) is True

    def test_neither_secret_matches(self):
        payload = {"event": "rotate"}
        sig = svc._sign("totally-different", payload)
        assert svc.verify_event_signature(
            payload=payload, signature=sig,
            current_secret="new-secret", previous_secret="old-secret",
        ) is False


# ---------------------------------------------------------------------------
# _event_policy and _extract_target_*_ids
# ---------------------------------------------------------------------------

class TestEventPolicy:
    def test_known_event_type(self):
        policy = svc._event_policy("demand_spike")
        assert policy["visibility"] == "public"
        assert policy["topic"] == svc._PUBLIC_TOPIC

    def test_unknown_event_type_returns_private_default(self):
        policy = svc._event_policy("totally_unknown_event")
        assert policy["visibility"] == "private"
        assert policy["topic"] == svc._PRIVATE_TOPIC


class TestExtractTargetIds:
    def test_extract_agent_ids_from_payload(self):
        policy = {"target_keys": ["seller_id"]}
        payload = {"agent_id": "a1", "buyer_id": "b1", "seller_id": "s1"}
        ids = svc._extract_target_agent_ids(payload, policy)
        assert "a1" in ids
        assert "b1" in ids
        assert "s1" in ids

    def test_extract_agent_ids_with_explicit_targets(self):
        ids = svc._extract_target_agent_ids({}, {"target_keys": []}, ["explicit-1"])
        assert "explicit-1" in ids

    def test_extract_agent_ids_skips_empty_strings(self):
        ids = svc._extract_target_agent_ids(
            {"agent_id": "  ", "buyer_id": ""},
            {"target_keys": []},
        )
        assert ids == []

    def test_extract_agent_ids_from_list_values(self):
        payload = {"agent_id": ["a1", "a2"]}
        ids = svc._extract_target_agent_ids(payload, {"target_keys": []})
        assert "a1" in ids
        assert "a2" in ids

    def test_extract_creator_ids_from_payload(self):
        policy = {"target_keys": ["creator_id"]}
        payload = {"creator_id": "c1", "target_creator_id": "c2"}
        ids = svc._extract_target_creator_ids(payload, policy)
        assert "c1" in ids
        assert "c2" in ids

    def test_extract_creator_ids_with_explicit_targets(self):
        ids = svc._extract_target_creator_ids({}, {"target_keys": []}, ["explicit-c1"])
        assert "explicit-c1" in ids

    def test_extract_creator_ids_from_list_values(self):
        payload = {"creator_id": ["c1", "c2"]}
        ids = svc._extract_target_creator_ids(payload, {"target_keys": []})
        assert "c1" in ids
        assert "c2" in ids

    def test_extract_creator_ids_skips_empty_strings(self):
        ids = svc._extract_target_creator_ids(
            {"creator_id": "  ", "target_creator_id": ""},
            {"target_keys": []},
        )
        assert ids == []

    def test_extract_user_ids_from_payload(self):
        policy = {"target_keys": ["user_id"]}
        payload = {"user_id": "u1", "target_user_id": "u2"}
        ids = svc._extract_target_user_ids(payload, policy)
        assert "u1" in ids
        assert "u2" in ids

    def test_extract_user_ids_with_explicit_targets(self):
        ids = svc._extract_target_user_ids({}, {"target_keys": []}, ["explicit-u1"])
        assert "explicit-u1" in ids

    def test_extract_user_ids_from_list_values(self):
        payload = {"user_id": ["u1", "u2"]}
        ids = svc._extract_target_user_ids(payload, {"target_keys": []})
        assert "u1" in ids
        assert "u2" in ids

    def test_extract_user_ids_skips_empty_strings(self):
        ids = svc._extract_target_user_ids(
            {"user_id": "  ", "target_user_id": ""},
            {"target_keys": []},
        )
        assert ids == []


# ---------------------------------------------------------------------------
# _sanitize_payload
# ---------------------------------------------------------------------------

class TestSanitizePayload:
    def test_private_returns_full_copy(self):
        payload = {"a": 1, "b": 2, "c": 3}
        result = svc._sanitize_payload(payload, {"public_fields": ["a"]}, "private")
        assert result == payload
        assert result is not payload  # must be a copy

    def test_public_filters_to_listed_fields(self):
        payload = {"a": 1, "b": 2, "c": 3}
        result = svc._sanitize_payload(payload, {"public_fields": ["a", "b"]}, "public")
        assert result == {"a": 1, "b": 2}

    def test_public_with_empty_fields_returns_full(self):
        payload = {"a": 1}
        result = svc._sanitize_payload(payload, {"public_fields": []}, "public")
        assert result == payload

    def test_public_missing_fields_skipped(self):
        payload = {"a": 1}
        result = svc._sanitize_payload(payload, {"public_fields": ["a", "missing"]}, "public")
        assert result == {"a": 1}


# ---------------------------------------------------------------------------
# build_event_envelope
# ---------------------------------------------------------------------------

class TestBuildEventEnvelope:
    def test_public_event_envelope_structure(self):
        envelope = svc.build_event_envelope(
            "demand_spike",
            {"query_pattern": "python", "velocity": 5.0, "category": "web_search"},
        )
        assert envelope["event_type"] == "demand_spike"
        assert envelope["visibility"] == "public"
        assert envelope["topic"] == svc._PUBLIC_TOPIC
        assert "signature" in envelope
        assert envelope["signature"].startswith("sha256=")
        assert "event_id" in envelope
        assert "seq" in envelope
        # Backward-compat aliases
        assert envelope["type"] == "demand_spike"
        assert envelope["timestamp"] == envelope["occurred_at"]
        assert envelope["data"] == envelope["payload"]
        assert envelope["schema_version"] == svc._SCHEMA_VERSION

    def test_private_event_with_no_targets_is_blocked(self):
        # "catalog_update" is private with target_keys ["subscriber_id", "agent_id"]
        # No targets in payload -> blocked
        envelope = svc.build_event_envelope("catalog_update", {})
        assert envelope["blocked"] is True

    def test_private_event_with_targets_is_not_blocked(self):
        envelope = svc.build_event_envelope(
            "catalog_update",
            {"agent_id": "agent-1", "subscriber_id": "sub-1"},
        )
        assert envelope["blocked"] is False

    def test_public_event_is_never_blocked(self):
        envelope = svc.build_event_envelope("test_event", {})
        assert envelope["blocked"] is False

    def test_explicit_agent_id_overrides_resolved(self):
        envelope = svc.build_event_envelope(
            "catalog_update",
            {"agent_id": "from-payload"},
            agent_id="explicit-agent",
        )
        assert envelope["agent_id"] == "explicit-agent"

    def test_delivery_attempt_propagates(self):
        envelope = svc.build_event_envelope("test_event", {}, delivery_attempt=3)
        assert envelope["delivery_attempt"] == 3

    def test_private_user_topic_blocked_without_user_targets(self):
        # market.order.created is private, topic = _PRIVATE_USER_TOPIC
        envelope = svc.build_event_envelope("market.order.created", {})
        assert envelope["blocked"] is True

    def test_private_user_topic_not_blocked_with_user_targets(self):
        envelope = svc.build_event_envelope(
            "market.order.created", {"user_id": "u1"}
        )
        assert envelope["blocked"] is False


# ---------------------------------------------------------------------------
# should_dispatch_event
# ---------------------------------------------------------------------------

class TestShouldDispatchEvent:
    def test_blocked_event_not_dispatched(self):
        assert svc.should_dispatch_event({"blocked": True}) is False

    def test_unblocked_event_dispatched(self):
        assert svc.should_dispatch_event({"blocked": False}) is True

    def test_no_blocked_key_dispatched(self):
        assert svc.should_dispatch_event({}) is True


# ---------------------------------------------------------------------------
# validate_callback_url
# ---------------------------------------------------------------------------

class TestValidateCallbackUrl:
    def test_valid_https_url(self):
        result = svc.validate_callback_url("https://example.com/webhook")
        assert result == "https://example.com/webhook"

    def test_valid_http_url_in_dev(self):
        with patch.object(svc.settings, "environment", "development"):
            result = svc.validate_callback_url("http://example.com/webhook")
            assert result == "http://example.com/webhook"

    def test_strips_whitespace(self):
        result = svc.validate_callback_url("  https://example.com/hook  ")
        assert result == "https://example.com/hook"

    def test_normalizes_empty_path_to_slash(self):
        result = svc.validate_callback_url("https://example.com")
        assert result == "https://example.com/"

    def test_rejects_ftp_scheme(self):
        with pytest.raises(ValueError, match="http or https"):
            svc.validate_callback_url("ftp://example.com/hook")

    def test_rejects_empty_host(self):
        with pytest.raises(ValueError, match="valid host"):
            svc.validate_callback_url("https://")

    def test_rejects_no_scheme(self):
        with pytest.raises(ValueError, match="http or https"):
            svc.validate_callback_url("example.com/hook")

    def test_rejects_private_ip(self):
        with pytest.raises(ValueError, match="private or reserved"):
            svc.validate_callback_url("https://10.0.0.1/hook")

    def test_rejects_loopback_ip(self):
        with pytest.raises(ValueError, match="private or reserved"):
            svc.validate_callback_url("https://127.0.0.1/hook")

    def test_rejects_link_local_ip(self):
        with pytest.raises(ValueError, match="private or reserved"):
            svc.validate_callback_url("https://169.254.1.1/hook")

    def test_prod_rejects_http(self):
        with patch.object(svc, "_is_prod", return_value=True):
            with pytest.raises(ValueError, match="HTTPS"):
                svc.validate_callback_url("http://example.com/hook")

    def test_prod_rejects_localhost(self):
        with patch.object(svc, "_is_prod", return_value=True):
            with pytest.raises(ValueError, match="Localhost"):
                svc.validate_callback_url("https://localhost/hook")

    def test_prod_resolves_hostname_and_blocks_private(self):
        with (
            patch.object(svc, "_is_prod", return_value=True),
            patch.object(svc, "_resolve_host_ips", return_value=[
                __import__("ipaddress").ip_address("10.0.0.5")
            ]),
        ):
            with pytest.raises(ValueError, match="private or reserved"):
                svc.validate_callback_url("https://internal.corp/hook")

    def test_preserves_query_params(self):
        url = "https://example.com/hook?token=abc"
        result = svc.validate_callback_url(url)
        assert "token=abc" in result


# ---------------------------------------------------------------------------
# _resolve_host_ips
# ---------------------------------------------------------------------------

class TestResolveHostIps:
    def test_gaierror_raises_value_error(self):
        import socket
        with patch.object(socket, "getaddrinfo", side_effect=socket.gaierror("lookup failed")):
            with pytest.raises(ValueError, match="Unable to resolve callback host"):
                svc._resolve_host_ips("nonexistent.invalid")

    def test_no_routable_addresses_raises_value_error(self):
        # Return getaddrinfo results with unparseable IP addresses
        import socket
        fake_infos = [
            (socket.AF_INET, socket.SOCK_STREAM, 0, "", ("not-an-ip", 0)),
        ]
        with patch.object(socket, "getaddrinfo", return_value=fake_infos):
            with pytest.raises(ValueError, match="No routable IP addresses"):
                svc._resolve_host_ips("example.com")

    def test_valid_resolution_returns_addresses(self):
        import ipaddress
        import socket
        fake_infos = [
            (socket.AF_INET, socket.SOCK_STREAM, 0, "", ("8.8.8.8", 0)),
            (socket.AF_INET, socket.SOCK_STREAM, 0, "", ("8.8.4.4", 0)),
        ]
        with patch.object(socket, "getaddrinfo", return_value=fake_infos):
            result = svc._resolve_host_ips("dns.google")
        assert ipaddress.ip_address("8.8.8.8") in result
        assert ipaddress.ip_address("8.8.4.4") in result


# ---------------------------------------------------------------------------
# _event_matches
# ---------------------------------------------------------------------------

class TestEventMatches:
    def test_wildcard_subscription_matches_all(self, make_agent):
        sub = _make_sub("agent-1")
        event = {
            "event_type": "demand_spike",
            "visibility": "public",
            "agent_id": "agent-1",
            "target_agent_ids": [],
        }
        assert svc._event_matches(sub, event) is True

    def test_specific_type_matches(self):
        sub = _make_sub("agent-1")
        sub.event_types_json = json.dumps(["demand_spike"])
        event = {
            "event_type": "demand_spike",
            "visibility": "public",
            "agent_id": "agent-1",
            "target_agent_ids": [],
        }
        assert svc._event_matches(sub, event) is True

    def test_specific_type_no_match(self):
        sub = _make_sub("agent-1")
        sub.event_types_json = json.dumps(["listing_created"])
        event = {
            "event_type": "demand_spike",
            "visibility": "public",
            "agent_id": "agent-1",
            "target_agent_ids": [],
        }
        assert svc._event_matches(sub, event) is False

    def test_private_event_requires_agent_in_targets(self):
        sub = _make_sub("agent-1")
        event = {
            "event_type": "catalog_update",
            "visibility": "private",
            "target_agent_ids": ["agent-2"],
        }
        assert svc._event_matches(sub, event) is False

    def test_private_event_matches_when_in_targets(self):
        sub = _make_sub("agent-1")
        event = {
            "event_type": "catalog_update",
            "visibility": "private",
            "target_agent_ids": ["agent-1"],
        }
        assert svc._event_matches(sub, event) is True

    def test_public_event_different_agent_no_match(self):
        sub = _make_sub("agent-1")
        event = {
            "event_type": "listing_created",
            "visibility": "public",
            "agent_id": "agent-2",
            "target_agent_ids": [],
        }
        assert svc._event_matches(sub, event) is False

    def test_invalid_event_types_json_returns_false(self):
        sub = _make_sub("agent-1")
        sub.event_types_json = '"not-a-list"'
        event = {
            "event_type": "demand_spike",
            "visibility": "public",
            "agent_id": "agent-1",
        }
        assert svc._event_matches(sub, event) is False


# ---------------------------------------------------------------------------
# register_subscription / list_subscriptions / delete_subscription (DB)
# ---------------------------------------------------------------------------

class TestSubscriptionCRUD:
    async def test_register_new_subscription(self, db: AsyncSession, make_agent):
        agent, _ = await make_agent()
        result = await svc.register_subscription(
            db, agent_id=agent.id,
            callback_url="https://example.com/hook",
            event_types=["demand_spike"],
        )
        assert result["agent_id"] == agent.id
        assert result["callback_url"] == "https://example.com/hook"
        assert result["event_types"] == ["demand_spike"]
        assert result["status"] == "active"
        assert "secret" in result
        assert result["secret"].startswith("whsec_")

    async def test_register_subscription_updates_existing(self, db: AsyncSession, make_agent):
        agent, _ = await make_agent()
        r1 = await svc.register_subscription(
            db, agent_id=agent.id,
            callback_url="https://example.com/hook",
            event_types=["demand_spike"],
        )
        r2 = await svc.register_subscription(
            db, agent_id=agent.id,
            callback_url="https://example.com/hook",
            event_types=["listing_created"],
        )
        # Same subscription row — updated
        assert r1["id"] == r2["id"]
        assert r2["event_types"] == ["listing_created"]
        assert r2["failure_count"] == 0

    async def test_register_subscription_resets_failure_count(self, db: AsyncSession, make_agent):
        agent, _ = await make_agent()
        r1 = await svc.register_subscription(
            db, agent_id=agent.id,
            callback_url="https://example.com/hook",
        )
        # Manually bump failure count
        res = await db.execute(
            select(EventSubscription).where(EventSubscription.id == r1["id"])
        )
        sub = res.scalar_one()
        sub.failure_count = 5
        sub.status = "paused"
        await db.commit()

        # Re-register resets
        r2 = await svc.register_subscription(
            db, agent_id=agent.id,
            callback_url="https://example.com/hook",
        )
        assert r2["failure_count"] == 0
        assert r2["status"] == "active"

    async def test_register_subscription_defaults_to_wildcard(self, db: AsyncSession, make_agent):
        agent, _ = await make_agent()
        result = await svc.register_subscription(
            db, agent_id=agent.id,
            callback_url="https://example.com/hook",
        )
        assert result["event_types"] == ["*"]

    async def test_register_subscription_rejects_invalid_url(self, db: AsyncSession, make_agent):
        agent, _ = await make_agent()
        with pytest.raises(ValueError, match="http or https"):
            await svc.register_subscription(
                db, agent_id=agent.id,
                callback_url="ftp://bad.com/hook",
            )

    async def test_list_subscriptions_empty(self, db: AsyncSession, make_agent):
        agent, _ = await make_agent()
        result = await svc.list_subscriptions(db, agent_id=agent.id)
        assert result == []

    async def test_list_subscriptions_returns_all(self, db: AsyncSession, make_agent):
        agent, _ = await make_agent()
        await svc.register_subscription(
            db, agent_id=agent.id, callback_url="https://a.com/hook",
        )
        await svc.register_subscription(
            db, agent_id=agent.id, callback_url="https://b.com/hook",
        )
        result = await svc.list_subscriptions(db, agent_id=agent.id)
        assert len(result) == 2

    async def test_list_subscriptions_isolated_by_agent(self, db: AsyncSession, make_agent):
        a1, _ = await make_agent("agent-one")
        a2, _ = await make_agent("agent-two")
        await svc.register_subscription(
            db, agent_id=a1.id, callback_url="https://a.com/hook",
        )
        await svc.register_subscription(
            db, agent_id=a2.id, callback_url="https://b.com/hook",
        )
        result = await svc.list_subscriptions(db, agent_id=a1.id)
        assert len(result) == 1
        assert result[0]["agent_id"] == a1.id

    async def test_delete_subscription_success(self, db: AsyncSession, make_agent):
        agent, _ = await make_agent()
        r = await svc.register_subscription(
            db, agent_id=agent.id, callback_url="https://a.com/hook",
        )
        deleted = await svc.delete_subscription(
            db, agent_id=agent.id, subscription_id=r["id"],
        )
        assert deleted is True
        remaining = await svc.list_subscriptions(db, agent_id=agent.id)
        assert len(remaining) == 0

    async def test_delete_subscription_wrong_agent(self, db: AsyncSession, make_agent):
        a1, _ = await make_agent("agent-one")
        a2, _ = await make_agent("agent-two")
        r = await svc.register_subscription(
            db, agent_id=a1.id, callback_url="https://a.com/hook",
        )
        deleted = await svc.delete_subscription(
            db, agent_id=a2.id, subscription_id=r["id"],
        )
        assert deleted is False

    async def test_delete_subscription_nonexistent(self, db: AsyncSession, make_agent):
        agent, _ = await make_agent()
        deleted = await svc.delete_subscription(
            db, agent_id=agent.id, subscription_id="nonexistent",
        )
        assert deleted is False


# ---------------------------------------------------------------------------
# _deliver_to_subscription (webhook delivery)
# ---------------------------------------------------------------------------

class TestDeliverToSubscription:
    async def test_successful_delivery_resets_failures(self, db: AsyncSession, make_agent):
        agent, _ = await make_agent()
        sub_data = await svc.register_subscription(
            db, agent_id=agent.id, callback_url="https://example.com/hook",
        )
        res = await db.execute(
            select(EventSubscription).where(EventSubscription.id == sub_data["id"])
        )
        sub = res.scalar_one()
        sub.failure_count = 3
        await db.commit()

        event = svc.build_event_envelope("test_event", {})

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = "ok"

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            await svc._deliver_to_subscription(db, subscription=sub, event=event)

        await db.refresh(sub)
        assert sub.failure_count == 0
        assert sub.last_delivery_at is not None

    async def test_failed_delivery_increments_failure_count(self, db: AsyncSession, make_agent):
        agent, _ = await make_agent()
        sub_data = await svc.register_subscription(
            db, agent_id=agent.id, callback_url="https://example.com/hook",
        )
        res = await db.execute(
            select(EventSubscription).where(EventSubscription.id == sub_data["id"])
        )
        sub = res.scalar_one()
        event = svc.build_event_envelope("test_event", {})

        with (
            patch("httpx.AsyncClient") as mock_client_cls,
            patch.object(svc.settings, "trust_webhook_max_retries", 1),
        ):
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(side_effect=httpx.RequestError("timeout"))
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            await svc._deliver_to_subscription(db, subscription=sub, event=event)

        await db.refresh(sub)
        assert sub.failure_count >= 1

    async def test_too_many_failures_pauses_subscription(self, db: AsyncSession, make_agent):
        agent, _ = await make_agent()
        sub_data = await svc.register_subscription(
            db, agent_id=agent.id, callback_url="https://example.com/hook",
        )
        res = await db.execute(
            select(EventSubscription).where(EventSubscription.id == sub_data["id"])
        )
        sub = res.scalar_one()
        sub.failure_count = 4  # One below max (default 5)
        await db.commit()

        event = svc.build_event_envelope("test_event", {})

        with (
            patch("httpx.AsyncClient") as mock_client_cls,
            patch.object(svc.settings, "trust_webhook_max_retries", 1),
            patch.object(svc.settings, "trust_webhook_max_failures", 5),
        ):
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(side_effect=httpx.RequestError("timeout"))
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            await svc._deliver_to_subscription(db, subscription=sub, event=event)

        await db.refresh(sub)
        assert sub.status == "paused"

    async def test_delivery_creates_webhook_delivery_record(self, db: AsyncSession, make_agent):
        agent, _ = await make_agent()
        sub_data = await svc.register_subscription(
            db, agent_id=agent.id, callback_url="https://example.com/hook",
        )
        res = await db.execute(
            select(EventSubscription).where(EventSubscription.id == sub_data["id"])
        )
        sub = res.scalar_one()
        event = svc.build_event_envelope("test_event", {})

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = "ok"

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            await svc._deliver_to_subscription(db, subscription=sub, event=event)

        deliveries_result = await db.execute(
            select(WebhookDelivery).where(WebhookDelivery.subscription_id == sub.id)
        )
        deliveries = deliveries_result.scalars().all()
        assert len(deliveries) >= 1
        assert deliveries[0].status == "delivered"

    async def test_delivery_blocked_on_url_revalidation_failure(
        self, db: AsyncSession, make_agent,
    ):
        """If URL fails re-validation at delivery time (DNS rebinding), delivery is blocked."""
        agent, _ = await make_agent()
        sub_data = await svc.register_subscription(
            db, agent_id=agent.id, callback_url="https://example.com/hook",
        )
        res = await db.execute(
            select(EventSubscription).where(EventSubscription.id == sub_data["id"])
        )
        sub = res.scalar_one()
        event = svc.build_event_envelope("test_event", {})

        with patch.object(
            svc, "validate_callback_url",
            side_effect=ValueError("resolves to private address"),
        ):
            await svc._deliver_to_subscription(db, subscription=sub, event=event)

        deliveries_result = await db.execute(
            select(WebhookDelivery).where(WebhookDelivery.subscription_id == sub.id)
        )
        deliveries = deliveries_result.scalars().all()
        assert len(deliveries) == 1
        assert deliveries[0].status == "blocked"

    async def test_delivery_blocked_dns_rebinding_pauses_on_max_failures(
        self, db: AsyncSession, make_agent,
    ):
        """DNS rebinding failure increments failure_count and pauses when hitting max."""
        agent, _ = await make_agent()
        sub_data = await svc.register_subscription(
            db, agent_id=agent.id, callback_url="https://example.com/hook",
        )
        res = await db.execute(
            select(EventSubscription).where(EventSubscription.id == sub_data["id"])
        )
        sub = res.scalar_one()
        sub.failure_count = 4  # One below max of 5
        await db.commit()

        event = svc.build_event_envelope("test_event", {})

        with (
            patch.object(
                svc, "validate_callback_url",
                side_effect=ValueError("resolves to private address"),
            ),
            patch.object(svc.settings, "trust_webhook_max_failures", 5),
        ):
            await svc._deliver_to_subscription(db, subscription=sub, event=event)

        await db.refresh(sub)
        assert sub.status == "paused"
        assert sub.failure_count >= 5

    async def test_delivery_hostname_dns_rebinding_at_delivery_time(
        self, db: AsyncSession, make_agent,
    ):
        """Hostname resolves to private IP at delivery time triggers blocked delivery."""
        import ipaddress

        agent, _ = await make_agent()
        sub_data = await svc.register_subscription(
            db, agent_id=agent.id, callback_url="https://evil-rebind.com/hook",
        )
        res = await db.execute(
            select(EventSubscription).where(EventSubscription.id == sub_data["id"])
        )
        sub = res.scalar_one()
        event = svc.build_event_envelope("test_event", {})

        # validate_callback_url passes (first check), but _resolve_host_ips at
        # delivery time returns a private address
        with (
            patch.object(svc, "_resolve_host_ips", return_value=[
                ipaddress.ip_address("10.0.0.5")
            ]),
            patch.object(svc.settings, "trust_webhook_max_retries", 1),
        ):
            await svc._deliver_to_subscription(db, subscription=sub, event=event)

        deliveries_result = await db.execute(
            select(WebhookDelivery).where(WebhookDelivery.subscription_id == sub.id)
        )
        deliveries = deliveries_result.scalars().all()
        assert len(deliveries) == 1
        assert deliveries[0].status == "blocked"


# ---------------------------------------------------------------------------
# dispatch_event_to_subscriptions
# ---------------------------------------------------------------------------

class TestDispatchEventToSubscriptions:
    async def test_skips_blocked_events(self, db: AsyncSession, make_agent):
        agent, _ = await make_agent()
        await svc.register_subscription(
            db, agent_id=agent.id, callback_url="https://example.com/hook",
        )
        # Dispatch a blocked event — should return immediately
        event = {"blocked": True, "event_type": "test", "visibility": "public"}
        await svc.dispatch_event_to_subscriptions(db, event=event)
        # No deliveries created
        deliveries_result = await db.execute(select(WebhookDelivery))
        assert deliveries_result.scalars().all() == []

    async def test_private_event_with_no_targets_skips(self, db: AsyncSession, make_agent):
        agent, _ = await make_agent()
        await svc.register_subscription(
            db, agent_id=agent.id, callback_url="https://example.com/hook",
        )
        event = {
            "blocked": False,
            "event_type": "catalog_update",
            "visibility": "private",
            "target_agent_ids": [],
        }
        await svc.dispatch_event_to_subscriptions(db, event=event)
        deliveries_result = await db.execute(select(WebhookDelivery))
        assert deliveries_result.scalars().all() == []

    async def test_delivers_to_matching_active_subscriptions(self, db: AsyncSession, make_agent):
        agent, _ = await make_agent()
        await svc.register_subscription(
            db, agent_id=agent.id, callback_url="https://example.com/hook",
        )
        event = svc.build_event_envelope(
            "test_event", {}, agent_id=agent.id,
        )

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = "ok"

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            await svc.dispatch_event_to_subscriptions(db, event=event)

        deliveries_result = await db.execute(select(WebhookDelivery))
        deliveries = deliveries_result.scalars().all()
        assert len(deliveries) >= 1

    async def test_private_event_dispatches_to_targeted_agent(
        self, db: AsyncSession, make_agent,
    ):
        """Private event with target_agent_ids filters subscriptions to those agents."""
        a1, _ = await make_agent("targeted-agent")
        a2, _ = await make_agent("other-agent")
        await svc.register_subscription(
            db, agent_id=a1.id, callback_url="https://target.com/hook",
        )
        await svc.register_subscription(
            db, agent_id=a2.id, callback_url="https://other.com/hook",
        )
        # Build a proper event envelope for a private event type
        event = svc.build_event_envelope(
            "catalog_update",
            {"agent_id": a1.id, "subscriber_id": a1.id},
            target_agent_ids=[a1.id],
        )

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = "ok"

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            await svc.dispatch_event_to_subscriptions(db, event=event)

        deliveries_result = await db.execute(select(WebhookDelivery))
        deliveries = deliveries_result.scalars().all()
        # Only the targeted agent's subscription should receive delivery
        assert len(deliveries) == 1
        target_sub_result = await db.execute(
            select(EventSubscription).where(EventSubscription.agent_id == a1.id)
        )
        target_sub = target_sub_result.scalar_one()
        assert deliveries[0].subscription_id == target_sub.id

    async def test_public_event_without_agent_id_dispatches_to_all(
        self, db: AsyncSession, make_agent,
    ):
        """Public event with no agent_id should query all active subscriptions."""
        agent, _ = await make_agent()
        await svc.register_subscription(
            db, agent_id=agent.id, callback_url="https://public.com/hook",
        )
        # Build a proper event envelope for a public event, then override agent_id
        event = svc.build_event_envelope("test_event", {})
        event["agent_id"] = None  # Force no agent_id for this test case

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = "ok"

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            await svc.dispatch_event_to_subscriptions(db, event=event)

        deliveries_result = await db.execute(select(WebhookDelivery))
        deliveries = deliveries_result.scalars().all()
        assert len(deliveries) >= 1

    async def test_dispatch_handles_sqlalchemy_error_gracefully(
        self, db: AsyncSession, make_agent,
    ):
        """SQLAlchemyError during subscription query is caught and dispatch returns silently."""
        from sqlalchemy.exc import SQLAlchemyError

        agent, _ = await make_agent()
        await svc.register_subscription(
            db, agent_id=agent.id, callback_url="https://example.com/hook",
        )
        event = svc.build_event_envelope("test_event", {}, agent_id=agent.id)

        original_execute = db.execute

        async def _failing_execute(stmt, *args, **kwargs):
            raise SQLAlchemyError("DB error")

        with patch.object(db, "execute", side_effect=_failing_execute):
            # Should not raise — silently returns
            await svc.dispatch_event_to_subscriptions(db, event=event)


# ---------------------------------------------------------------------------
# redact_old_webhook_deliveries
# ---------------------------------------------------------------------------

class TestRedactOldWebhookDeliveries:
    async def test_redacts_old_deliveries(self, db: AsyncSession, make_agent):
        agent, _ = await make_agent()
        sub_data = await svc.register_subscription(
            db, agent_id=agent.id, callback_url="https://example.com/hook",
        )
        # Insert an old delivery manually
        old_delivery = WebhookDelivery(
            id=str(uuid.uuid4()),
            subscription_id=sub_data["id"],
            event_id=str(uuid.uuid4()),
            event_type="test_event",
            payload_json='{"secret": "data"}',
            signature="sha256=abc",
            status="delivered",
            response_body="response body",
            delivery_attempt=1,
            created_at=datetime.now(timezone.utc) - timedelta(days=60),
        )
        db.add(old_delivery)
        await db.commit()

        redacted = await svc.redact_old_webhook_deliveries(db, retention_days=30)
        assert redacted == 1

        await db.refresh(old_delivery)
        assert old_delivery.payload_json == "{}"
        assert old_delivery.response_body == "[redacted]"

    async def test_does_not_redact_recent_deliveries(self, db: AsyncSession, make_agent):
        agent, _ = await make_agent()
        sub_data = await svc.register_subscription(
            db, agent_id=agent.id, callback_url="https://example.com/hook",
        )
        recent_delivery = WebhookDelivery(
            id=str(uuid.uuid4()),
            subscription_id=sub_data["id"],
            event_id=str(uuid.uuid4()),
            event_type="test_event",
            payload_json='{"data": "fresh"}',
            signature="sha256=abc",
            status="delivered",
            response_body="ok",
            delivery_attempt=1,
        )
        db.add(recent_delivery)
        await db.commit()

        redacted = await svc.redact_old_webhook_deliveries(db, retention_days=30)
        assert redacted == 0

    async def test_already_redacted_not_counted(self, db: AsyncSession, make_agent):
        agent, _ = await make_agent()
        sub_data = await svc.register_subscription(
            db, agent_id=agent.id, callback_url="https://example.com/hook",
        )
        old_delivery = WebhookDelivery(
            id=str(uuid.uuid4()),
            subscription_id=sub_data["id"],
            event_id=str(uuid.uuid4()),
            event_type="test_event",
            payload_json="{}",
            signature="sha256=abc",
            status="delivered",
            response_body="[redacted]",
            delivery_attempt=1,
            created_at=datetime.now(timezone.utc) - timedelta(days=60),
        )
        db.add(old_delivery)
        await db.commit()

        redacted = await svc.redact_old_webhook_deliveries(db, retention_days=30)
        assert redacted == 0


# ---------------------------------------------------------------------------
# _serialize_subscription
# ---------------------------------------------------------------------------

class TestSerializeSubscription:
    def test_serialize_includes_all_fields(self):
        sub = EventSubscription(
            id="sub-1",
            agent_id="agent-1",
            callback_url="https://example.com/hook",
            event_types_json='["demand_spike"]',
            secret="whsec_test",
            status="active",
            failure_count=2,
            last_delivery_at=datetime(2025, 1, 1, tzinfo=timezone.utc),
            created_at=datetime(2024, 6, 1, tzinfo=timezone.utc),
        )
        result = svc._serialize_subscription(sub)
        assert result["id"] == "sub-1"
        assert result["agent_id"] == "agent-1"
        assert result["event_types"] == ["demand_spike"]
        assert result["failure_count"] == 2
        assert result["last_delivery_at"] is not None
        assert result["created_at"] is not None

    def test_serialize_handles_null_failure_count(self):
        sub = EventSubscription(
            id="sub-1", agent_id="a", callback_url="https://a.com",
            event_types_json='["*"]', secret="s", status="active",
            failure_count=None, last_delivery_at=None, created_at=None,
        )
        result = svc._serialize_subscription(sub)
        assert result["failure_count"] == 0
        assert result["last_delivery_at"] is None
        assert result["created_at"] is None


# ---------------------------------------------------------------------------
# _is_disallowed_ip
# ---------------------------------------------------------------------------

class TestIsDisallowedIp:
    def test_loopback_disallowed(self):
        import ipaddress
        assert svc._is_disallowed_ip(ipaddress.ip_address("127.0.0.1")) is True

    def test_private_10_disallowed(self):
        import ipaddress
        assert svc._is_disallowed_ip(ipaddress.ip_address("10.1.2.3")) is True

    def test_private_172_disallowed(self):
        import ipaddress
        assert svc._is_disallowed_ip(ipaddress.ip_address("172.16.0.1")) is True

    def test_private_192_disallowed(self):
        import ipaddress
        assert svc._is_disallowed_ip(ipaddress.ip_address("192.168.1.1")) is True

    def test_public_ip_allowed(self):
        import ipaddress
        assert svc._is_disallowed_ip(ipaddress.ip_address("8.8.8.8")) is False

    def test_ipv6_loopback_disallowed(self):
        import ipaddress
        assert svc._is_disallowed_ip(ipaddress.ip_address("::1")) is True


# ---------------------------------------------------------------------------
# _base_event_payload
# ---------------------------------------------------------------------------

class TestBaseEventPayload:
    def test_extracts_expected_fields(self):
        event = {
            "event_id": "eid-1",
            "seq": 42,
            "event_type": "test_event",
            "occurred_at": "2025-01-01T00:00:00",
            "agent_id": "agent-1",
            "payload": {"key": "value"},
            "visibility": "public",
            "topic": "public.market",
            "target_agent_ids": ["agent-1"],
            "target_creator_ids": [],
            "target_user_ids": [],
            "schema_version": "2026-02-15",
            "delivery_attempt": 1,
        }
        result = svc._base_event_payload(event)
        assert result["event_id"] == "eid-1"
        assert result["seq"] == 42
        assert result["payload"] == {"key": "value"}

    def test_defaults_for_missing_fields(self):
        event = {
            "event_id": "eid-1",
            "seq": 1,
            "event_type": "test",
            "occurred_at": "2025-01-01T00:00:00",
        }
        result = svc._base_event_payload(event)
        assert result["agent_id"] is None
        assert result["payload"] == {}
        assert result["visibility"] == "private"
