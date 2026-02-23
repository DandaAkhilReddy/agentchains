"""Comprehensive tests for the plugin loader and all example plugins.

Covers:
- loader.py: PluginManifest, load_plugin(), load_plugins_from_directory(),
  initialize_plugin()
- examples/hello_plugin.py: HelloPlugin
- examples/analytics_plugin.py: AnalyticsPlugin
- examples/notification_plugin.py: NotificationPlugin
- examples/rate_limit_plugin.py: RateLimitPlugin

All test functions are async (asyncio_mode = "auto" in pyproject.toml).
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from marketplace.plugins.loader import (
    DEFAULT_PLUGINS_DIR,
    PluginManifest,
    initialize_plugin,
    load_plugin,
    load_plugins_from_directory,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _minimal_manifest_data(**overrides) -> dict:
    """Return a minimal valid manifest dict, allowing field overrides."""
    base = {
        "name": "test-plugin",
        "version": "1.0.0",
        "description": "A test plugin",
        "author": "Test Author",
        "entry_point": "marketplace.plugins.examples.hello_plugin:HelloPlugin",
    }
    base.update(overrides)
    return base


def _write_manifest(tmp_path: Path, data: dict, filename: str = "plugin.json") -> Path:
    """Write a dict as JSON to tmp_path/filename and return the path."""
    p = tmp_path / filename
    p.write_text(json.dumps(data), encoding="utf-8")
    return p


# ===========================================================================
# PluginManifest dataclass
# ===========================================================================

class TestPluginManifest:
    async def test_all_required_fields_stored(self):
        m = PluginManifest(
            name="my-plugin",
            version="2.3.4",
            description="Does stuff",
            author="Someone",
            entry_point="pkg.mod:MyClass",
        )
        assert m.name == "my-plugin"
        assert m.version == "2.3.4"
        assert m.description == "Does stuff"
        assert m.author == "Someone"
        assert m.entry_point == "pkg.mod:MyClass"

    async def test_enabled_defaults_to_true(self):
        m = PluginManifest(
            name="p", version="1", description="d", author="a", entry_point="m:C"
        )
        assert m.enabled is True

    async def test_enabled_can_be_set_false(self):
        m = PluginManifest(
            name="p", version="1", description="d", author="a",
            entry_point="m:C", enabled=False,
        )
        assert m.enabled is False

    async def test_dependencies_defaults_to_empty_list(self):
        m = PluginManifest(
            name="p", version="1", description="d", author="a", entry_point="m:C"
        )
        assert m.dependencies == []

    async def test_dependencies_stored(self):
        m = PluginManifest(
            name="p", version="1", description="d", author="a",
            entry_point="m:C", dependencies=["requests", "httpx"],
        )
        assert m.dependencies == ["requests", "httpx"]

    async def test_two_instances_with_same_data_are_equal(self):
        kwargs = dict(
            name="p", version="1.0", description="d", author="a", entry_point="m:C"
        )
        assert PluginManifest(**kwargs) == PluginManifest(**kwargs)


# ===========================================================================
# load_plugin()
# ===========================================================================

class TestLoadPlugin:
    async def test_loads_all_required_fields(self, tmp_path):
        p = _write_manifest(tmp_path, _minimal_manifest_data())
        m = load_plugin(p)
        assert m.name == "test-plugin"
        assert m.version == "1.0.0"
        assert m.description == "A test plugin"
        assert m.author == "Test Author"
        assert m.entry_point == "marketplace.plugins.examples.hello_plugin:HelloPlugin"

    async def test_optional_dependencies_loaded(self, tmp_path):
        data = _minimal_manifest_data(dependencies=["dep-a", "dep-b"])
        p = _write_manifest(tmp_path, data)
        m = load_plugin(p)
        assert m.dependencies == ["dep-a", "dep-b"]

    async def test_optional_enabled_false(self, tmp_path):
        p = _write_manifest(tmp_path, _minimal_manifest_data(enabled=False))
        m = load_plugin(p)
        assert m.enabled is False

    async def test_optional_enabled_defaults_to_true_when_absent(self, tmp_path):
        data = _minimal_manifest_data()
        data.pop("enabled", None)  # ensure the key is absent
        p = _write_manifest(tmp_path, data)
        m = load_plugin(p)
        assert m.enabled is True

    async def test_dependencies_defaults_to_empty_list_when_absent(self, tmp_path):
        data = _minimal_manifest_data()
        data.pop("dependencies", None)
        p = _write_manifest(tmp_path, data)
        m = load_plugin(p)
        assert m.dependencies == []

    async def test_accepts_string_path(self, tmp_path):
        p = _write_manifest(tmp_path, _minimal_manifest_data())
        m = load_plugin(str(p))  # str, not Path
        assert m.name == "test-plugin"

    async def test_missing_file_raises_file_not_found(self):
        with pytest.raises(FileNotFoundError, match="Plugin manifest not found"):
            load_plugin("/nonexistent/path/plugin.json")

    async def test_missing_name_raises_value_error(self, tmp_path):
        data = _minimal_manifest_data()
        del data["name"]
        p = _write_manifest(tmp_path, data)
        with pytest.raises(ValueError, match="name"):
            load_plugin(p)

    async def test_missing_version_raises_value_error(self, tmp_path):
        data = _minimal_manifest_data()
        del data["version"]
        p = _write_manifest(tmp_path, data)
        with pytest.raises(ValueError, match="version"):
            load_plugin(p)

    async def test_missing_description_raises_value_error(self, tmp_path):
        data = _minimal_manifest_data()
        del data["description"]
        p = _write_manifest(tmp_path, data)
        with pytest.raises(ValueError, match="description"):
            load_plugin(p)

    async def test_missing_author_raises_value_error(self, tmp_path):
        data = _minimal_manifest_data()
        del data["author"]
        p = _write_manifest(tmp_path, data)
        with pytest.raises(ValueError, match="author"):
            load_plugin(p)

    async def test_missing_entry_point_raises_value_error(self, tmp_path):
        data = _minimal_manifest_data()
        del data["entry_point"]
        p = _write_manifest(tmp_path, data)
        with pytest.raises(ValueError, match="entry_point"):
            load_plugin(p)

    async def test_all_required_fields_missing_error_lists_them(self, tmp_path):
        p = _write_manifest(tmp_path, {})
        with pytest.raises(ValueError) as exc_info:
            load_plugin(p)
        msg = str(exc_info.value)
        for field in ("name", "version", "description", "author", "entry_point"):
            assert field in msg

    async def test_invalid_json_propagates(self, tmp_path):
        p = tmp_path / "plugin.json"
        p.write_text("{not valid json}", encoding="utf-8")
        with pytest.raises(Exception):  # json.JSONDecodeError
            load_plugin(p)


# ===========================================================================
# load_plugins_from_directory()
# ===========================================================================

class TestLoadPluginsFromDirectory:
    async def test_empty_directory_returns_empty_list(self, tmp_path):
        result = load_plugins_from_directory(tmp_path)
        assert result == []

    async def test_nonexistent_directory_returns_empty_list(self):
        result = load_plugins_from_directory("/nonexistent/directory/abc123")
        assert result == []

    async def test_discovers_single_manifest(self, tmp_path):
        _write_manifest(tmp_path, _minimal_manifest_data())
        result = load_plugins_from_directory(tmp_path)
        assert len(result) == 1
        assert result[0].name == "test-plugin"

    async def test_discovers_nested_manifests(self, tmp_path):
        sub1 = tmp_path / "plugin_a"
        sub1.mkdir()
        _write_manifest(sub1, _minimal_manifest_data(name="plugin-a"))

        sub2 = tmp_path / "plugin_b"
        sub2.mkdir()
        _write_manifest(sub2, _minimal_manifest_data(name="plugin-b"))

        result = load_plugins_from_directory(tmp_path)
        names = {m.name for m in result}
        assert names == {"plugin-a", "plugin-b"}

    async def test_skips_invalid_manifest_and_loads_valid(self, tmp_path):
        # Valid plugin in one sub-dir
        sub_valid = tmp_path / "valid"
        sub_valid.mkdir()
        _write_manifest(sub_valid, _minimal_manifest_data(name="valid-plugin"))

        # Invalid (missing required fields) plugin in another
        sub_bad = tmp_path / "bad"
        sub_bad.mkdir()
        _write_manifest(sub_bad, {"name": "only-name"})

        result = load_plugins_from_directory(tmp_path)
        assert len(result) == 1
        assert result[0].name == "valid-plugin"

    async def test_accepts_none_uses_default_dir(self):
        # When called with None it should use DEFAULT_PLUGINS_DIR (or return []
        # gracefully if it doesn't exist in this test env).
        result = load_plugins_from_directory(None)
        assert isinstance(result, list)

    async def test_returns_plugin_manifest_instances(self, tmp_path):
        _write_manifest(tmp_path, _minimal_manifest_data())
        result = load_plugins_from_directory(tmp_path)
        assert all(isinstance(m, PluginManifest) for m in result)

    async def test_accepts_string_path(self, tmp_path):
        _write_manifest(tmp_path, _minimal_manifest_data())
        result = load_plugins_from_directory(str(tmp_path))
        assert len(result) == 1

    async def test_directory_with_no_plugin_json_files(self, tmp_path):
        (tmp_path / "readme.txt").write_text("hello")
        (tmp_path / "config.yaml").write_text("key: value")
        result = load_plugins_from_directory(tmp_path)
        assert result == []


# ===========================================================================
# initialize_plugin()
# ===========================================================================

class TestInitializePlugin:
    async def test_initializes_hello_plugin(self):
        manifest = PluginManifest(
            name="hello",
            version="0.1.0",
            description="Hello plugin",
            author="AgentChains Team",
            entry_point="marketplace.plugins.examples.hello_plugin:HelloPlugin",
        )
        instance = initialize_plugin(manifest)
        from marketplace.plugins.examples.hello_plugin import HelloPlugin
        assert isinstance(instance, HelloPlugin)

    async def test_initializes_analytics_plugin(self):
        manifest = PluginManifest(
            name="analytics",
            version="0.1.0",
            description="Analytics",
            author="AgentChains Team",
            entry_point="marketplace.plugins.examples.analytics_plugin:AnalyticsPlugin",
        )
        instance = initialize_plugin(manifest)
        from marketplace.plugins.examples.analytics_plugin import AnalyticsPlugin
        assert isinstance(instance, AnalyticsPlugin)

    async def test_initializes_notification_plugin(self):
        manifest = PluginManifest(
            name="notification",
            version="0.1.0",
            description="Notification",
            author="AgentChains Team",
            entry_point="marketplace.plugins.examples.notification_plugin:NotificationPlugin",
        )
        instance = initialize_plugin(manifest)
        from marketplace.plugins.examples.notification_plugin import NotificationPlugin
        assert isinstance(instance, NotificationPlugin)

    async def test_initializes_rate_limit_plugin(self):
        manifest = PluginManifest(
            name="rate-limit",
            version="0.1.0",
            description="Rate Limit",
            author="AgentChains Team",
            entry_point="marketplace.plugins.examples.rate_limit_plugin:RateLimitPlugin",
        )
        instance = initialize_plugin(manifest)
        from marketplace.plugins.examples.rate_limit_plugin import RateLimitPlugin
        assert isinstance(instance, RateLimitPlugin)

    async def test_invalid_entry_point_format_raises_value_error(self):
        manifest = PluginManifest(
            name="bad",
            version="1.0",
            description="Bad",
            author="A",
            entry_point="no_colon_here",
        )
        with pytest.raises(ValueError, match="entry_point must be"):
            initialize_plugin(manifest)

    async def test_nonexistent_module_raises_import_error(self):
        manifest = PluginManifest(
            name="bad",
            version="1.0",
            description="Bad",
            author="A",
            entry_point="nonexistent.module.path:SomeClass",
        )
        with pytest.raises(ImportError):
            initialize_plugin(manifest)

    async def test_nonexistent_class_raises_attribute_error(self):
        manifest = PluginManifest(
            name="bad",
            version="1.0",
            description="Bad",
            author="A",
            entry_point="marketplace.plugins.examples.hello_plugin:NonExistentClass",
        )
        with pytest.raises(AttributeError):
            initialize_plugin(manifest)

    async def test_each_call_returns_fresh_instance(self):
        manifest = PluginManifest(
            name="hello",
            version="0.1.0",
            description="d",
            author="a",
            entry_point="marketplace.plugins.examples.hello_plugin:HelloPlugin",
        )
        inst1 = initialize_plugin(manifest)
        inst2 = initialize_plugin(manifest)
        assert inst1 is not inst2


# ===========================================================================
# HelloPlugin
# ===========================================================================

class TestHelloPlugin:
    def _plugin(self):
        from marketplace.plugins.examples.hello_plugin import HelloPlugin
        return HelloPlugin()

    async def test_initial_state(self):
        p = self._plugin()
        info = p.get_info()
        assert info["registered"] is False
        assert info["agents_greeted"] == 0
        assert info["listings_seen"] == 0

    async def test_on_register_sets_registered(self):
        p = self._plugin()
        p.on_register()
        assert p._registered is True
        assert p.get_info()["registered"] is True

    async def test_on_agent_created_dict(self):
        p = self._plugin()
        p.on_agent_created({"agent_id": "agent-001"})
        assert p._agents_seen == ["agent-001"]
        assert p.get_info()["agents_greeted"] == 1

    async def test_on_agent_created_object(self):
        p = self._plugin()
        agent = SimpleNamespace(agent_id="agent-obj-42")
        p.on_agent_created(agent)
        assert "agent-obj-42" in p._agents_seen

    async def test_on_agent_created_missing_agent_id_uses_unknown(self):
        p = self._plugin()
        p.on_agent_created({})  # no agent_id key
        assert p._agents_seen == ["unknown"]

    async def test_on_agent_created_object_missing_attr_uses_unknown(self):
        p = self._plugin()
        p.on_agent_created(SimpleNamespace())  # no agent_id attribute
        assert p._agents_seen == ["unknown"]

    async def test_on_agent_created_increments_count(self):
        p = self._plugin()
        p.on_agent_created({"agent_id": "a1"})
        p.on_agent_created({"agent_id": "a2"})
        p.on_agent_created({"agent_id": "a3"})
        assert p.get_info()["agents_greeted"] == 3

    async def test_on_listing_created_dict(self):
        p = self._plugin()
        p.on_listing_created({"listing_id": "listing-001"})
        assert p._listings_seen == ["listing-001"]
        assert p.get_info()["listings_seen"] == 1

    async def test_on_listing_created_object(self):
        p = self._plugin()
        listing = SimpleNamespace(listing_id="listing-obj-99")
        p.on_listing_created(listing)
        assert "listing-obj-99" in p._listings_seen

    async def test_on_listing_created_missing_listing_id_uses_unknown(self):
        p = self._plugin()
        p.on_listing_created({})
        assert p._listings_seen == ["unknown"]

    async def test_on_listing_created_object_missing_attr_uses_unknown(self):
        p = self._plugin()
        p.on_listing_created(SimpleNamespace())
        assert p._listings_seen == ["unknown"]

    async def test_get_info_returns_all_keys(self):
        p = self._plugin()
        info = p.get_info()
        expected_keys = {
            "name", "version", "author", "description",
            "registered", "agents_greeted", "listings_seen",
        }
        assert expected_keys.issubset(info.keys())

    async def test_get_info_name_and_version(self):
        p = self._plugin()
        info = p.get_info()
        assert info["name"] == "hello_plugin"
        assert info["version"] == "0.1.0"


# ===========================================================================
# AnalyticsPlugin
# ===========================================================================

class TestAnalyticsPlugin:
    def _plugin(self):
        from marketplace.plugins.examples.analytics_plugin import AnalyticsPlugin
        return AnalyticsPlugin()

    async def test_initial_stats(self):
        p = self._plugin()
        stats = p.get_stats()
        assert stats["registered"] is False
        assert stats["transaction_count"] == 0
        assert stats["total_amount_usd"] == 0.0
        assert stats["average_amount_usd"] == 0.0
        assert stats["by_type"] == {}
        assert stats["recent_transactions"] == []

    async def test_on_register_sets_registered(self):
        p = self._plugin()
        p.on_register()
        assert p.get_stats()["registered"] is True

    async def test_on_transaction_completed_dict(self):
        p = self._plugin()
        p.on_transaction_completed({
            "transaction_id": "tx-001",
            "amount": 5.0,
            "tx_type": "sale",
        })
        stats = p.get_stats()
        assert stats["transaction_count"] == 1
        assert stats["total_amount_usd"] == 5.0
        assert stats["average_amount_usd"] == 5.0
        assert stats["by_type"] == {"sale": 1}

    async def test_on_transaction_completed_object(self):
        p = self._plugin()
        tx = SimpleNamespace(transaction_id="tx-obj-1", amount=10.0, tx_type="purchase")
        p.on_transaction_completed(tx)
        stats = p.get_stats()
        assert stats["transaction_count"] == 1
        assert stats["total_amount_usd"] == 10.0

    async def test_on_transaction_completed_missing_fields_uses_defaults(self):
        p = self._plugin()
        p.on_transaction_completed({})  # all optional
        stats = p.get_stats()
        assert stats["transaction_count"] == 1
        assert stats["total_amount_usd"] == 0.0
        assert "unknown" in stats["by_type"]

    async def test_multiple_transactions_accumulate(self):
        p = self._plugin()
        p.on_transaction_completed({"transaction_id": "t1", "amount": 3.0, "tx_type": "sale"})
        p.on_transaction_completed({"transaction_id": "t2", "amount": 7.0, "tx_type": "sale"})
        p.on_transaction_completed({"transaction_id": "t3", "amount": 2.0, "tx_type": "refund"})
        stats = p.get_stats()
        assert stats["transaction_count"] == 3
        assert stats["total_amount_usd"] == 12.0
        assert round(stats["average_amount_usd"], 2) == 4.0
        assert stats["by_type"]["sale"] == 2
        assert stats["by_type"]["refund"] == 1

    async def test_average_amount_zero_when_no_transactions(self):
        p = self._plugin()
        assert p.get_stats()["average_amount_usd"] == 0.0

    async def test_recent_transactions_capped_at_ten(self):
        p = self._plugin()
        for i in range(15):
            p.on_transaction_completed({
                "transaction_id": f"tx-{i}",
                "amount": 1.0,
                "tx_type": "sale",
            })
        stats = p.get_stats()
        assert len(stats["recent_transactions"]) == 10

    async def test_recent_transactions_are_latest(self):
        p = self._plugin()
        for i in range(12):
            p.on_transaction_completed({
                "transaction_id": f"tx-{i}",
                "amount": float(i),
                "tx_type": "sale",
            })
        recent = p.get_stats()["recent_transactions"]
        # Should contain the last 10 transactions (tx-2 through tx-11)
        recent_ids = [r["transaction_id"] for r in recent]
        assert "tx-2" in recent_ids
        assert "tx-0" not in recent_ids

    async def test_transaction_stored_in_recent_transactions(self):
        p = self._plugin()
        p.on_transaction_completed({
            "transaction_id": "tx-abc",
            "amount": 42.5,
            "tx_type": "purchase",
        })
        recent = p.get_stats()["recent_transactions"]
        assert len(recent) == 1
        assert recent[0]["transaction_id"] == "tx-abc"
        assert recent[0]["amount"] == 42.5
        assert recent[0]["tx_type"] == "purchase"

    async def test_total_amount_rounded_to_two_decimal_places(self):
        p = self._plugin()
        p.on_transaction_completed({"amount": 1.111, "tx_type": "s", "transaction_id": "t"})
        p.on_transaction_completed({"amount": 2.222, "tx_type": "s", "transaction_id": "t2"})
        stats = p.get_stats()
        # 1.111 + 2.222 = 3.333, rounded to 2 dp
        assert stats["total_amount_usd"] == round(1.111 + 2.222, 2)


# ===========================================================================
# NotificationPlugin
# ===========================================================================

class TestNotificationPlugin:
    def _plugin(self):
        from marketplace.plugins.examples.notification_plugin import NotificationPlugin
        return NotificationPlugin()

    async def test_default_channels(self):
        p = self._plugin()
        channels = p.get_channels()
        assert set(channels) == {"log", "webhook", "email"}

    async def test_on_register_sets_registered(self):
        p = self._plugin()
        p.on_register()
        assert p._registered is True

    async def test_on_event_dict_data_stored_in_log(self):
        p = self._plugin()
        p.on_event("agent_created", {"agent_id": "a1"})
        log = p.get_event_log()
        assert len(log) == 1
        assert log[0]["event_type"] == "agent_created"
        assert log[0]["data"] == {"agent_id": "a1"}

    async def test_on_event_object_data_converted_to_str(self):
        p = self._plugin()
        obj = SimpleNamespace(foo="bar")
        p.on_event("test_event", obj)
        log = p.get_event_log()
        assert isinstance(log[0]["data"], str)

    async def test_on_event_records_channels_notified(self):
        p = self._plugin()
        p.on_event("sale", {"amount": 10.0})
        log = p.get_event_log()
        assert set(log[0]["channels_notified"]) == {"log", "webhook", "email"}

    async def test_multiple_events_accumulated(self):
        p = self._plugin()
        p.on_event("event_a", {})
        p.on_event("event_b", {})
        p.on_event("event_c", {})
        assert len(p.get_event_log()) == 3

    async def test_add_channel_appends(self):
        p = self._plugin()
        p.add_channel("sms")
        assert "sms" in p.get_channels()

    async def test_add_channel_duplicate_ignored(self):
        p = self._plugin()
        p.add_channel("log")  # already present
        assert p.get_channels().count("log") == 1

    async def test_remove_channel_removes(self):
        p = self._plugin()
        p.remove_channel("email")
        assert "email" not in p.get_channels()

    async def test_remove_channel_not_present_is_no_op(self):
        p = self._plugin()
        initial = set(p.get_channels())
        p.remove_channel("nonexistent_channel")
        assert set(p.get_channels()) == initial

    async def test_get_channels_returns_copy(self):
        p = self._plugin()
        channels = p.get_channels()
        channels.append("mutated")
        assert "mutated" not in p.get_channels()

    async def test_get_event_log_returns_copy(self):
        p = self._plugin()
        p.on_event("e", {})
        log = p.get_event_log()
        log.clear()
        assert len(p.get_event_log()) == 1

    async def test_on_event_after_add_channel_includes_new_channel(self):
        p = self._plugin()
        p.add_channel("slack")
        p.on_event("purchase", {"amount": 5.0})
        log = p.get_event_log()
        assert "slack" in log[0]["channels_notified"]

    async def test_on_event_after_remove_channel_excludes_removed(self):
        p = self._plugin()
        p.remove_channel("webhook")
        p.on_event("sale", {})
        log = p.get_event_log()
        assert "webhook" not in log[0]["channels_notified"]

    async def test_dispatch_log_channel_does_not_raise(self):
        from marketplace.plugins.examples.notification_plugin import NotificationPlugin
        NotificationPlugin._dispatch("log", "test_event", {"key": "value"})

    async def test_dispatch_webhook_channel_does_not_raise(self):
        from marketplace.plugins.examples.notification_plugin import NotificationPlugin
        NotificationPlugin._dispatch("webhook", "test_event", {})

    async def test_dispatch_email_channel_does_not_raise(self):
        from marketplace.plugins.examples.notification_plugin import NotificationPlugin
        NotificationPlugin._dispatch("email", "test_event", {})

    async def test_dispatch_unknown_channel_does_not_raise(self):
        from marketplace.plugins.examples.notification_plugin import NotificationPlugin
        NotificationPlugin._dispatch("custom_channel", "test_event", {})


# ===========================================================================
# RateLimitPlugin
# ===========================================================================

class TestRateLimitPlugin:
    def _plugin(self, window_seconds=60, max_requests=30):
        from marketplace.plugins.examples.rate_limit_plugin import RateLimitPlugin
        return RateLimitPlugin(
            window_seconds=window_seconds,
            max_requests=max_requests,
        )

    async def test_default_params(self):
        from marketplace.plugins.examples.rate_limit_plugin import (
            DEFAULT_MAX_REQUESTS,
            DEFAULT_WINDOW_SECONDS,
            RateLimitPlugin,
        )
        p = RateLimitPlugin()
        assert p.window_seconds == DEFAULT_WINDOW_SECONDS
        assert p.max_requests == DEFAULT_MAX_REQUESTS

    async def test_custom_params_stored(self):
        p = self._plugin(window_seconds=10, max_requests=5)
        assert p.window_seconds == 10
        assert p.max_requests == 5

    async def test_on_load_does_not_raise(self):
        p = self._plugin()
        await p.on_load()

    async def test_on_unload_clears_state(self):
        p = self._plugin()
        p._record("agent-1")
        await p.on_unload()
        assert p._requests["agent-1"] == []

    async def test_is_allowed_for_unknown_agent(self):
        p = self._plugin(max_requests=5)
        # No requests recorded for agent yet
        assert p.is_allowed("brand-new-agent") is True

    async def test_is_allowed_within_limit(self):
        p = self._plugin(max_requests=3)
        p._record("agent-a")
        p._record("agent-a")
        assert p.is_allowed("agent-a") is True

    async def test_is_allowed_exactly_at_limit(self):
        p = self._plugin(max_requests=3)
        for _ in range(3):
            p._record("agent-a")
        # len == max_requests == 3, condition is <=, so still allowed
        assert p.is_allowed("agent-a") is True

    async def test_is_allowed_exceeds_limit(self):
        p = self._plugin(max_requests=3)
        for _ in range(4):
            p._record("agent-a")
        assert p.is_allowed("agent-a") is False

    async def test_get_remaining_full_budget(self):
        p = self._plugin(max_requests=10)
        assert p.get_remaining("agent-x") == 10

    async def test_get_remaining_partial_usage(self):
        p = self._plugin(max_requests=10)
        p._record("agent-x")
        p._record("agent-x")
        assert p.get_remaining("agent-x") == 8

    async def test_get_remaining_exhausted(self):
        p = self._plugin(max_requests=2)
        p._record("agent-x")
        p._record("agent-x")
        p._record("agent-x")  # now 3 > max_requests=2
        assert p.get_remaining("agent-x") == 0

    async def test_get_remaining_never_goes_negative(self):
        p = self._plugin(max_requests=1)
        for _ in range(5):
            p._record("agent-x")
        assert p.get_remaining("agent-x") == 0

    async def test_prune_removes_old_timestamps(self):
        p = self._plugin(window_seconds=1)
        # Inject old timestamps manually
        old_ts = time.monotonic() - 10  # 10 seconds ago, outside 1s window
        p._requests["agent-z"] = [old_ts, old_ts, old_ts]
        p._prune("agent-z")
        assert p._requests["agent-z"] == []

    async def test_prune_keeps_recent_timestamps(self):
        p = self._plugin(window_seconds=60)
        now = time.monotonic()
        p._requests["agent-z"] = [now - 5, now - 3, now - 1]  # all within 60s
        p._prune("agent-z")
        assert len(p._requests["agent-z"]) == 3

    async def test_on_agent_registered_dict_records_request(self):
        p = self._plugin(max_requests=5)
        await p.on_agent_registered({"agent_id": "agent-99"})
        assert len(p._requests["agent-99"]) == 1

    async def test_on_agent_registered_non_dict_uses_str(self):
        p = self._plugin(max_requests=5)
        await p.on_agent_registered("some-string-id")
        assert len(p._requests["some-string-id"]) == 1

    async def test_on_agent_registered_missing_agent_id_uses_unknown(self):
        p = self._plugin(max_requests=5)
        await p.on_agent_registered({})  # no agent_id key
        assert len(p._requests["unknown"]) == 1

    async def test_on_agent_registered_returns_is_allowed_false_when_exceeded(self):
        # max_requests=1 and we call on_agent_registered twice
        p = self._plugin(max_requests=1)
        await p.on_agent_registered({"agent_id": "burner"})
        await p.on_agent_registered({"agent_id": "burner"})
        # After 2 calls with max=1, is_allowed should be False
        assert p.is_allowed("burner") is False

    async def test_meta_class_attribute(self):
        from marketplace.plugins.examples.rate_limit_plugin import PLUGIN_JSON, RateLimitPlugin
        assert RateLimitPlugin.meta == PLUGIN_JSON

    async def test_plugin_json_has_required_fields(self):
        from marketplace.plugins.examples.rate_limit_plugin import PLUGIN_JSON
        for field in ("name", "version", "author", "description", "entry_point"):
            assert field in PLUGIN_JSON

    async def test_plugin_json_entry_point_format(self):
        from marketplace.plugins.examples.rate_limit_plugin import PLUGIN_JSON
        assert ":" in PLUGIN_JSON["entry_point"]

    async def test_independent_agents_dont_affect_each_other(self):
        p = self._plugin(max_requests=2)
        p._record("alice")
        p._record("alice")
        p._record("alice")  # alice exceeded
        # bob has never been seen
        assert p.is_allowed("alice") is False
        assert p.is_allowed("bob") is True


# ===========================================================================
# Integration: loader -> initialize_plugin -> plugin works end-to-end
# ===========================================================================

class TestLoaderIntegration:
    async def test_load_then_initialize_hello_plugin(self, tmp_path):
        data = _minimal_manifest_data(
            name="hello-integration",
            entry_point="marketplace.plugins.examples.hello_plugin:HelloPlugin",
        )
        p = _write_manifest(tmp_path, data)
        manifest = load_plugin(p)
        instance = initialize_plugin(manifest)

        # Plugin is usable immediately
        instance.on_register()
        instance.on_agent_created({"agent_id": "integration-agent"})
        info = instance.get_info()
        assert info["registered"] is True
        assert info["agents_greeted"] == 1

    async def test_load_then_initialize_analytics_plugin(self, tmp_path):
        data = _minimal_manifest_data(
            name="analytics-integration",
            entry_point="marketplace.plugins.examples.analytics_plugin:AnalyticsPlugin",
        )
        p = _write_manifest(tmp_path, data)
        manifest = load_plugin(p)
        instance = initialize_plugin(manifest)

        instance.on_register()
        instance.on_transaction_completed({"transaction_id": "t1", "amount": 9.99, "tx_type": "purchase"})
        stats = instance.get_stats()
        assert stats["registered"] is True
        assert stats["transaction_count"] == 1
        assert stats["total_amount_usd"] == 9.99

    async def test_directory_discovery_and_initialization(self, tmp_path):
        data = _minimal_manifest_data(
            name="dir-hello",
            entry_point="marketplace.plugins.examples.hello_plugin:HelloPlugin",
        )
        sub = tmp_path / "hello_plugin"
        sub.mkdir()
        _write_manifest(sub, data)

        manifests = load_plugins_from_directory(tmp_path)
        assert len(manifests) == 1

        instance = initialize_plugin(manifests[0])
        assert hasattr(instance, "on_register")
        assert hasattr(instance, "on_agent_created")

    async def test_default_plugins_dir_constant_is_path(self):
        assert isinstance(DEFAULT_PLUGINS_DIR, Path)
        assert DEFAULT_PLUGINS_DIR.name == "examples"
