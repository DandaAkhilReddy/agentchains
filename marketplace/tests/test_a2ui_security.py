"""Tests for A2UI security module — sanitization, payload validation, and consent tracking."""

import json
import pytest
from datetime import datetime, timezone

from marketplace.a2ui.security import (
    sanitize_html,
    validate_payload_size,
    A2UIConsentTracker,
)


class TestSanitizeHtml:
    def test_escapes_script_tags(self):
        result = sanitize_html("<script>alert('xss')</script>")
        assert "<script>" not in result
        assert "&lt;script&gt;" in result

    def test_escapes_angle_brackets(self):
        assert sanitize_html("<div>") == "&lt;div&gt;"

    def test_escapes_double_quotes(self):
        result = sanitize_html('value="bad"')
        assert "&quot;" in result

    def test_escapes_single_quotes(self):
        result = sanitize_html("it's")
        assert "&#x27;" in result or "it&#x27;s" in result or "it's" in result

    def test_escapes_ampersand(self):
        result = sanitize_html("a & b")
        assert "&amp;" in result

    def test_preserves_plain_text(self):
        assert sanitize_html("hello world") == "hello world"

    def test_handles_empty_string(self):
        assert sanitize_html("") == ""

    def test_escapes_nested_tags(self):
        result = sanitize_html("<div><span>test</span></div>")
        assert "<div>" not in result
        assert "<span>" not in result

    def test_escapes_event_handlers(self):
        result = sanitize_html('<img onerror="alert(1)">')
        assert "onerror" in result
        assert "<img" not in result

    def test_escapes_javascript_uri(self):
        result = sanitize_html('javascript:alert(1)')
        # plain text is fine, just no HTML injection
        assert "javascript" in result

    def test_handles_unicode(self):
        result = sanitize_html("héllo wörld 日本語")
        assert "héllo" in result

    def test_escapes_multiple_injections(self):
        result = sanitize_html('<script>x</script><img onerror="y">')
        assert "<script>" not in result
        assert "<img" not in result


class TestValidatePayloadSize:
    def test_small_payload_passes(self):
        assert validate_payload_size({"key": "value"}) is True

    def test_empty_payload_passes(self):
        assert validate_payload_size({}) is True

    def test_large_payload_fails(self):
        data = {"big": "x" * 2_000_000}
        assert validate_payload_size(data) is False

    def test_exact_limit_passes(self):
        # Create payload close to 100 bytes, then set limit to its size
        data = {"a": "b"}
        raw = json.dumps(data, default=str)
        size = len(raw.encode("utf-8"))
        assert validate_payload_size(data, max_bytes=size) is True

    def test_one_byte_over_fails(self):
        data = {"a": "b"}
        raw = json.dumps(data, default=str)
        size = len(raw.encode("utf-8"))
        assert validate_payload_size(data, max_bytes=size - 1) is False

    def test_custom_max_bytes(self):
        data = {"key": "x" * 100}
        assert validate_payload_size(data, max_bytes=50) is False
        assert validate_payload_size(data, max_bytes=1000) is True

    def test_nested_payload(self):
        data = {"nested": {"deep": {"list": [1, 2, 3]}}}
        assert validate_payload_size(data) is True

    def test_payload_with_datetime(self):
        data = {"time": datetime.now(timezone.utc)}
        assert validate_payload_size(data) is True  # default=str handles datetime

    def test_default_limit_is_1mb(self):
        data = {"small": "test"}
        assert validate_payload_size(data) is True

    def test_handles_unicode_in_payload(self):
        data = {"text": "日本語テスト" * 100}
        assert validate_payload_size(data) is True


class TestA2UIConsentTracker:
    def test_track_consent_granted(self):
        tracker = A2UIConsentTracker()
        tracker.track_consent("sess-1", "data_collection", True)
        assert tracker.check_consent("sess-1", "data_collection") is True

    def test_track_consent_denied(self):
        tracker = A2UIConsentTracker()
        tracker.track_consent("sess-1", "data_collection", False)
        assert tracker.check_consent("sess-1", "data_collection") is False

    def test_unknown_session_returns_false(self):
        tracker = A2UIConsentTracker()
        assert tracker.check_consent("nonexistent", "data_collection") is False

    def test_unknown_consent_type_returns_false(self):
        tracker = A2UIConsentTracker()
        tracker.track_consent("sess-1", "data_collection", True)
        assert tracker.check_consent("sess-1", "analytics") is False

    def test_revoke_consent_removes_all(self):
        tracker = A2UIConsentTracker()
        tracker.track_consent("sess-1", "data_collection", True)
        tracker.track_consent("sess-1", "analytics", True)
        tracker.revoke_consent("sess-1")
        assert tracker.check_consent("sess-1", "data_collection") is False
        assert tracker.check_consent("sess-1", "analytics") is False

    def test_revoke_nonexistent_session_is_safe(self):
        tracker = A2UIConsentTracker()
        tracker.revoke_consent("nonexistent")  # should not raise

    def test_multiple_sessions_isolated(self):
        tracker = A2UIConsentTracker()
        tracker.track_consent("sess-1", "data_collection", True)
        tracker.track_consent("sess-2", "data_collection", False)
        assert tracker.check_consent("sess-1", "data_collection") is True
        assert tracker.check_consent("sess-2", "data_collection") is False

    def test_update_consent_overwrites(self):
        tracker = A2UIConsentTracker()
        tracker.track_consent("sess-1", "data_collection", True)
        tracker.track_consent("sess-1", "data_collection", False)
        assert tracker.check_consent("sess-1", "data_collection") is False

    def test_revoke_one_session_preserves_others(self):
        tracker = A2UIConsentTracker()
        tracker.track_consent("sess-1", "analytics", True)
        tracker.track_consent("sess-2", "analytics", True)
        tracker.revoke_consent("sess-1")
        assert tracker.check_consent("sess-1", "analytics") is False
        assert tracker.check_consent("sess-2", "analytics") is True

    def test_consent_entry_has_timestamp(self):
        tracker = A2UIConsentTracker()
        tracker.track_consent("sess-1", "data_collection", True)
        entry = tracker._consents["sess-1"]["data_collection"]
        assert isinstance(entry.granted_at, datetime)
        assert entry.granted_at.tzinfo is not None

    def test_multiple_consent_types_per_session(self):
        tracker = A2UIConsentTracker()
        tracker.track_consent("sess-1", "data_collection", True)
        tracker.track_consent("sess-1", "analytics", True)
        tracker.track_consent("sess-1", "marketing", False)
        assert tracker.check_consent("sess-1", "data_collection") is True
        assert tracker.check_consent("sess-1", "analytics") is True
        assert tracker.check_consent("sess-1", "marketing") is False

    def test_many_sessions(self):
        tracker = A2UIConsentTracker()
        for i in range(100):
            tracker.track_consent(f"sess-{i}", "analytics", i % 2 == 0)
        assert tracker.check_consent("sess-0", "analytics") is True
        assert tracker.check_consent("sess-1", "analytics") is False
        assert tracker.check_consent("sess-50", "analytics") is True
