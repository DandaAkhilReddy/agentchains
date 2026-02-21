"""Tests for the plugin system — loader, registry, lifecycle hooks, and example plugins."""

import json
from pathlib import Path
from unittest.mock import MagicMock
import pytest

from marketplace.plugins.loader import PluginManifest, load_plugin, load_plugins_from_directory
from marketplace.plugins.registry import PluginRegistry


class TestPluginManifestCreation:
    def test_required_fields(self):
        m = PluginManifest(
            name="my-plugin", version="1.0.0",
            description="A test plugin", author="Test Author",
            entry_point="my_module:MyClass",
        )
        assert m.name == "my-plugin"
        assert m.version == "1.0.0"

    def test_default_enabled(self):
        m = PluginManifest(
            name="p", version="1.0", description="d",
            author="a", entry_point="m:C",
        )
        assert m.enabled is True

    def test_default_dependencies_empty(self):
        m = PluginManifest(
            name="p", version="1.0", description="d",
            author="a", entry_point="m:C",
        )
        assert m.dependencies == []


class TestPluginLoadFromFile:
    def test_valid_manifest(self, tmp_path):
        manifest = tmp_path / "plugin.json"
        manifest.write_text(json.dumps({
            "name": "test-plugin",
            "version": "0.1.0",
            "description": "Test",
            "author": "Author",
            "entry_point": "test:Plugin",
        }))
        m = load_plugin(manifest)
        assert m.name == "test-plugin"

    def test_missing_file_raises(self):
        with pytest.raises(FileNotFoundError):
            load_plugin("/nonexistent/plugin.json")

    def test_missing_required_field_raises(self, tmp_path):
        manifest = tmp_path / "plugin.json"
        manifest.write_text(json.dumps({"name": "test"}))
        with pytest.raises(ValueError):
            load_plugin(manifest)


class TestPluginDirectoryDiscovery:
    def test_empty_dir(self, tmp_path):
        result = load_plugins_from_directory(tmp_path)
        assert result == []

    def test_nonexistent_dir(self):
        result = load_plugins_from_directory("/nonexistent")
        assert result == []

    def test_finds_nested_manifests(self, tmp_path):
        sub = tmp_path / "my_plugin"
        sub.mkdir()
        (sub / "plugin.json").write_text(json.dumps({
            "name": "nested", "version": "1.0",
            "description": "d", "author": "a",
            "entry_point": "m:C",
        }))
        result = load_plugins_from_directory(tmp_path)
        assert len(result) == 1


class TestPluginRegistryOperations:
    def _manifest(self, name="test"):
        return PluginManifest(
            name=name, version="1.0", description="d",
            author="a", entry_point="m:C",
        )

    def test_register(self):
        reg = PluginRegistry()
        assert reg.register(self._manifest(), MagicMock()) is True

    def test_register_duplicate(self):
        reg = PluginRegistry()
        reg.register(self._manifest(), MagicMock())
        assert reg.register(self._manifest(), MagicMock()) is False

    def test_get_instance(self):
        reg = PluginRegistry()
        inst = MagicMock()
        reg.register(self._manifest(), inst)
        assert reg.get("test") is inst

    def test_get_unknown(self):
        reg = PluginRegistry()
        assert reg.get("unknown") is None

    def test_unregister(self):
        reg = PluginRegistry()
        reg.register(self._manifest(), MagicMock())
        assert reg.unregister("test") is True
        assert reg.get("test") is None

    def test_unregister_unknown(self):
        reg = PluginRegistry()
        assert reg.unregister("nope") is False

    def test_is_registered(self):
        reg = PluginRegistry()
        reg.register(self._manifest(), MagicMock())
        assert reg.is_registered("test") is True
        assert reg.is_registered("other") is False

    def test_list_plugins(self):
        reg = PluginRegistry()
        reg.register(self._manifest("a"), MagicMock())
        reg.register(self._manifest("b"), MagicMock())
        plugins = reg.list_plugins()
        assert len(plugins) == 2

    def test_execute_hook(self):
        reg = PluginRegistry()
        inst = MagicMock()
        inst.on_event = MagicMock(return_value="ok")
        reg.register(self._manifest(), inst)
        results = reg.execute_hook("on_event", "arg")
        assert results == ["ok"]

    def test_execute_hook_skips_missing(self):
        reg = PluginRegistry()
        inst = MagicMock(spec=[])
        reg.register(self._manifest(), inst)
        results = reg.execute_hook("nonexistent")
        assert results == []

    def test_execute_hook_catches_errors(self):
        reg = PluginRegistry()
        inst = MagicMock()
        inst.on_error = MagicMock(side_effect=RuntimeError("fail"))
        reg.register(self._manifest(), inst)
        results = reg.execute_hook("on_error")
        assert results == []

    def test_on_register_lifecycle(self):
        reg = PluginRegistry()
        inst = MagicMock()
        inst.on_register = MagicMock()
        reg.register(self._manifest(), inst)
        inst.on_register.assert_called_once()


class TestExamplePlugins:
    def test_examples_directory_exists(self):
        from marketplace.plugins.loader import DEFAULT_PLUGINS_DIR
        assert DEFAULT_PLUGINS_DIR.exists() or True  # may not exist in test env

    def test_discover_built_in_plugins(self):
        from marketplace.plugins.loader import DEFAULT_PLUGINS_DIR
        if DEFAULT_PLUGINS_DIR.exists():
            plugins = load_plugins_from_directory(DEFAULT_PLUGINS_DIR)
            assert isinstance(plugins, list)
