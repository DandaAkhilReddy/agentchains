"""Tests for the plugin system — loader, manifest validation, and registry."""

import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from marketplace.plugins.loader import (
    PluginManifest,
    load_plugin,
    load_plugins_from_directory,
    initialize_plugin,
)
from marketplace.plugins.registry import PluginRegistry, plugin_registry


# ── PluginManifest tests ──


class TestPluginManifest:
    def test_create_manifest(self):
        m = PluginManifest(
            name="test", version="1.0", description="desc",
            author="author", entry_point="mod:Class",
        )
        assert m.name == "test"
        assert m.version == "1.0"

    def test_default_dependencies_empty(self):
        m = PluginManifest(
            name="test", version="1.0", description="d",
            author="a", entry_point="m:C",
        )
        assert m.dependencies == []

    def test_default_enabled_true(self):
        m = PluginManifest(
            name="test", version="1.0", description="d",
            author="a", entry_point="m:C",
        )
        assert m.enabled is True

    def test_custom_dependencies(self):
        m = PluginManifest(
            name="test", version="1.0", description="d",
            author="a", entry_point="m:C",
            dependencies=["dep1", "dep2"],
        )
        assert len(m.dependencies) == 2

    def test_disabled_manifest(self):
        m = PluginManifest(
            name="test", version="1.0", description="d",
            author="a", entry_point="m:C", enabled=False,
        )
        assert m.enabled is False


# ── load_plugin tests ──


class TestLoadPlugin:
    def _write_manifest(self, tmp_dir: Path, data: dict) -> Path:
        path = tmp_dir / "plugin.json"
        path.write_text(json.dumps(data))
        return path

    def test_loads_valid_manifest(self, tmp_path):
        path = self._write_manifest(tmp_path, {
            "name": "test-plugin", "version": "0.1.0",
            "description": "A test", "author": "Dev",
            "entry_point": "test_module:TestClass",
        })
        m = load_plugin(path)
        assert m.name == "test-plugin"
        assert m.version == "0.1.0"

    def test_raises_file_not_found(self):
        with pytest.raises(FileNotFoundError):
            load_plugin("/nonexistent/plugin.json")

    def test_raises_on_missing_name(self, tmp_path):
        path = self._write_manifest(tmp_path, {
            "version": "1.0", "description": "d", "author": "a", "entry_point": "m:C",
        })
        with pytest.raises(ValueError, match="name"):
            load_plugin(path)

    def test_raises_on_missing_version(self, tmp_path):
        path = self._write_manifest(tmp_path, {
            "name": "p", "description": "d", "author": "a", "entry_point": "m:C",
        })
        with pytest.raises(ValueError, match="version"):
            load_plugin(path)

    def test_raises_on_missing_entry_point(self, tmp_path):
        path = self._write_manifest(tmp_path, {
            "name": "p", "version": "1.0", "description": "d", "author": "a",
        })
        with pytest.raises(ValueError, match="entry_point"):
            load_plugin(path)

    def test_optional_dependencies(self, tmp_path):
        path = self._write_manifest(tmp_path, {
            "name": "p", "version": "1.0", "description": "d",
            "author": "a", "entry_point": "m:C",
        })
        m = load_plugin(path)
        assert m.dependencies == []

    def test_parses_dependencies(self, tmp_path):
        path = self._write_manifest(tmp_path, {
            "name": "p", "version": "1.0", "description": "d",
            "author": "a", "entry_point": "m:C",
            "dependencies": ["numpy", "pandas"],
        })
        m = load_plugin(path)
        assert m.dependencies == ["numpy", "pandas"]

    def test_parses_enabled_false(self, tmp_path):
        path = self._write_manifest(tmp_path, {
            "name": "p", "version": "1.0", "description": "d",
            "author": "a", "entry_point": "m:C", "enabled": False,
        })
        m = load_plugin(path)
        assert m.enabled is False


# ── load_plugins_from_directory tests ──


class TestLoadPluginsFromDirectory:
    def test_returns_empty_for_nonexistent_dir(self):
        result = load_plugins_from_directory("/nonexistent/path")
        assert result == []

    def test_returns_empty_for_empty_dir(self, tmp_path):
        result = load_plugins_from_directory(tmp_path)
        assert result == []

    def test_discovers_single_manifest(self, tmp_path):
        sub = tmp_path / "my_plugin"
        sub.mkdir()
        (sub / "plugin.json").write_text(json.dumps({
            "name": "my_plugin", "version": "1.0", "description": "d",
            "author": "a", "entry_point": "m:C",
        }))
        result = load_plugins_from_directory(tmp_path)
        assert len(result) == 1
        assert result[0].name == "my_plugin"

    def test_discovers_multiple_manifests(self, tmp_path):
        for i in range(3):
            sub = tmp_path / f"plugin_{i}"
            sub.mkdir()
            (sub / "plugin.json").write_text(json.dumps({
                "name": f"plugin-{i}", "version": "1.0", "description": "d",
                "author": "a", "entry_point": "m:C",
            }))
        result = load_plugins_from_directory(tmp_path)
        assert len(result) == 3

    def test_skips_invalid_manifest(self, tmp_path):
        sub = tmp_path / "bad"
        sub.mkdir()
        (sub / "plugin.json").write_text("not json")
        result = load_plugins_from_directory(tmp_path)
        assert result == []


# ── initialize_plugin tests ──


class TestInitializePlugin:
    def test_raises_on_invalid_entry_point_format(self):
        m = PluginManifest(
            name="bad", version="1.0", description="d",
            author="a", entry_point="no_colon_here",
        )
        with pytest.raises(ValueError, match="module.path:ClassName"):
            initialize_plugin(m)

    def test_raises_on_nonexistent_module(self):
        m = PluginManifest(
            name="bad", version="1.0", description="d",
            author="a", entry_point="nonexistent_module_xyz:Cls",
        )
        with pytest.raises((ImportError, ModuleNotFoundError)):
            initialize_plugin(m)


# ── PluginRegistry tests ──


class TestPluginRegistry:
    def _make_manifest(self, name="test-plugin"):
        return PluginManifest(
            name=name, version="1.0", description="d",
            author="a", entry_point="m:C",
        )

    def test_register_returns_true(self):
        reg = PluginRegistry()
        result = reg.register(self._make_manifest(), MagicMock())
        assert result is True

    def test_register_duplicate_returns_false(self):
        reg = PluginRegistry()
        m = self._make_manifest()
        reg.register(m, MagicMock())
        assert reg.register(m, MagicMock()) is False

    def test_get_returns_instance(self):
        reg = PluginRegistry()
        instance = MagicMock()
        reg.register(self._make_manifest(), instance)
        assert reg.get("test-plugin") is instance

    def test_get_returns_none_for_unknown(self):
        reg = PluginRegistry()
        assert reg.get("nonexistent") is None

    def test_unregister_returns_true(self):
        reg = PluginRegistry()
        reg.register(self._make_manifest(), MagicMock())
        assert reg.unregister("test-plugin") is True

    def test_unregister_returns_false_for_unknown(self):
        reg = PluginRegistry()
        assert reg.unregister("nonexistent") is False

    def test_unregister_removes_plugin(self):
        reg = PluginRegistry()
        reg.register(self._make_manifest(), MagicMock())
        reg.unregister("test-plugin")
        assert reg.get("test-plugin") is None

    def test_is_registered(self):
        reg = PluginRegistry()
        reg.register(self._make_manifest(), MagicMock())
        assert reg.is_registered("test-plugin") is True
        assert reg.is_registered("other") is False

    def test_list_plugins_empty(self):
        reg = PluginRegistry()
        assert reg.list_plugins() == []

    def test_list_plugins_returns_info(self):
        reg = PluginRegistry()
        reg.register(self._make_manifest("alpha"), MagicMock())
        reg.register(self._make_manifest("beta"), MagicMock())
        plugins = reg.list_plugins()
        assert len(plugins) == 2
        names = {p["name"] for p in plugins}
        assert names == {"alpha", "beta"}

    def test_list_plugins_includes_fields(self):
        reg = PluginRegistry()
        reg.register(self._make_manifest(), MagicMock())
        info = reg.list_plugins()[0]
        assert "name" in info
        assert "version" in info
        assert "description" in info
        assert "author" in info
        assert "enabled" in info

    def test_execute_hook_calls_matching_plugins(self):
        reg = PluginRegistry()
        instance = MagicMock()
        instance.on_request = MagicMock(return_value="handled")
        reg.register(self._make_manifest(), instance)
        results = reg.execute_hook("on_request", "arg1")
        assert results == ["handled"]
        instance.on_request.assert_called_once_with("arg1")

    def test_execute_hook_skips_plugins_without_method(self):
        reg = PluginRegistry()
        instance = MagicMock(spec=[])  # no methods
        reg.register(self._make_manifest(), instance)
        results = reg.execute_hook("nonexistent_hook")
        assert results == []

    def test_execute_hook_handles_errors(self):
        reg = PluginRegistry()
        instance = MagicMock()
        instance.on_error = MagicMock(side_effect=RuntimeError("boom"))
        reg.register(self._make_manifest(), instance)
        results = reg.execute_hook("on_error")
        assert results == []  # error caught, empty result

    def test_execute_hook_multiple_plugins(self):
        reg = PluginRegistry()
        for i in range(3):
            instance = MagicMock()
            instance.on_test = MagicMock(return_value=i)
            reg.register(self._make_manifest(f"plugin-{i}"), instance)
        results = reg.execute_hook("on_test")
        assert len(results) == 3

    def test_on_register_lifecycle_hook(self):
        reg = PluginRegistry()
        instance = MagicMock()
        instance.on_register = MagicMock()
        reg.register(self._make_manifest(), instance)
        instance.on_register.assert_called_once()

    def test_on_register_error_doesnt_prevent_registration(self):
        reg = PluginRegistry()
        instance = MagicMock()
        instance.on_register = MagicMock(side_effect=RuntimeError("init failed"))
        result = reg.register(self._make_manifest(), instance)
        assert result is True
        assert reg.is_registered("test-plugin")

    def test_singleton_exists(self):
        assert isinstance(plugin_registry, PluginRegistry)
