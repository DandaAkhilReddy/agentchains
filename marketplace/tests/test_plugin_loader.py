"""Tests for plugin loader — discovery, validation, and initialization.

Covers:
  - load_plugin: valid manifest, missing file, missing fields (tests 1-4)
  - load_plugins_from_directory: scan directory, skip invalid (tests 5-7)
  - initialize_plugin: valid entry_point, invalid formats, security checks (tests 8-16)
  - PluginManifest dataclass defaults (test 17)
"""

import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from marketplace.plugins.loader import (
    PluginManifest,
    load_plugin,
    load_plugins_from_directory,
    initialize_plugin,
    _ALLOWED_PLUGIN_MODULE_PREFIX,
)


def _write_manifest(directory: Path, data: dict) -> Path:
    """Write a plugin.json to the given directory and return its path."""
    manifest_path = directory / "plugin.json"
    manifest_path.write_text(json.dumps(data), encoding="utf-8")
    return manifest_path


def _valid_manifest_data(**overrides) -> dict:
    """Return a valid manifest dict with optional overrides."""
    base = {
        "name": "test-plugin",
        "version": "1.0.0",
        "description": "A test plugin",
        "author": "test-author",
        "entry_point": "marketplace.plugins.example:TestPlugin",
    }
    base.update(overrides)
    return base


class TestLoadPlugin:
    """Tests 1-4: load_plugin reads and validates plugin.json."""

    # 1
    def test_load_valid_manifest(self, tmp_path: Path):
        """load_plugin should return a PluginManifest for a valid file."""
        data = _valid_manifest_data(dependencies=["dep-a"], enabled=False)
        path = _write_manifest(tmp_path, data)

        result = load_plugin(path)

        assert isinstance(result, PluginManifest)
        assert result.name == "test-plugin"
        assert result.version == "1.0.0"
        assert result.dependencies == ["dep-a"]
        assert result.enabled is False

    # 2
    def test_load_missing_file_raises(self, tmp_path: Path):
        """load_plugin should raise FileNotFoundError for missing manifest."""
        with pytest.raises(FileNotFoundError, match="Plugin manifest not found"):
            load_plugin(tmp_path / "nonexistent.json")

    # 3
    def test_load_missing_required_fields_raises(self, tmp_path: Path):
        """load_plugin should raise ValueError when required fields are missing."""
        data = {"name": "incomplete", "version": "0.1"}
        path = _write_manifest(tmp_path, data)

        with pytest.raises(ValueError, match="missing required fields"):
            load_plugin(path)

    # 4
    def test_load_defaults_dependencies_and_enabled(self, tmp_path: Path):
        """load_plugin should default dependencies=[] and enabled=True."""
        data = _valid_manifest_data()
        # Remove optional fields
        data.pop("dependencies", None)
        data.pop("enabled", None)
        path = _write_manifest(tmp_path, data)

        result = load_plugin(path)

        assert result.dependencies == []
        assert result.enabled is True


class TestLoadPluginsFromDirectory:
    """Tests 5-7: directory scanning for plugin manifests."""

    # 5
    def test_scan_discovers_all_manifests(self, tmp_path: Path):
        """Should find all plugin.json files in nested directories."""
        plugin_a = tmp_path / "plugin-a"
        plugin_b = tmp_path / "plugin-b"
        plugin_a.mkdir()
        plugin_b.mkdir()
        _write_manifest(plugin_a, _valid_manifest_data(name="plugin-a"))
        _write_manifest(plugin_b, _valid_manifest_data(name="plugin-b"))

        results = load_plugins_from_directory(tmp_path)

        assert len(results) == 2
        names = {m.name for m in results}
        assert "plugin-a" in names
        assert "plugin-b" in names

    # 6
    def test_scan_skips_invalid_manifests(self, tmp_path: Path):
        """Invalid manifests should be skipped without crashing."""
        valid_dir = tmp_path / "valid"
        invalid_dir = tmp_path / "invalid"
        valid_dir.mkdir()
        invalid_dir.mkdir()
        _write_manifest(valid_dir, _valid_manifest_data(name="good-plugin"))
        # Write invalid JSON
        (invalid_dir / "plugin.json").write_text("not json", encoding="utf-8")

        results = load_plugins_from_directory(tmp_path)

        assert len(results) == 1
        assert results[0].name == "good-plugin"

    # 7
    def test_scan_nonexistent_directory_returns_empty(self, tmp_path: Path):
        """Scanning a nonexistent directory should return empty list."""
        results = load_plugins_from_directory(tmp_path / "does_not_exist")

        assert results == []

    # 7b
    def test_scan_empty_directory_returns_empty(self, tmp_path: Path):
        """Scanning a directory with no manifests should return empty list."""
        results = load_plugins_from_directory(tmp_path)

        assert results == []


class TestInitializePlugin:
    """Tests 8-16: dynamic plugin instantiation with security checks."""

    # 8
    def test_initialize_valid_plugin(self):
        """Should import module, instantiate class, and return instance."""
        mock_cls = MagicMock(spec=type)
        mock_instance = MagicMock()
        mock_cls.return_value = mock_instance

        manifest = PluginManifest(
            name="test", version="1.0", description="d", author="a",
            entry_point="marketplace.plugins.example:MyPlugin",
        )

        with patch("importlib.import_module") as mock_import:
            mock_module = MagicMock()
            mock_module.MyPlugin = mock_cls
            mock_import.return_value = mock_module

            result = initialize_plugin(manifest)

            mock_import.assert_called_once_with("marketplace.plugins.example")
            assert result is mock_instance

    # 9
    def test_initialize_rejects_missing_colon(self):
        """entry_point without ':' should raise ValueError."""
        manifest = PluginManifest(
            name="bad", version="1.0", description="d", author="a",
            entry_point="marketplace.plugins.example.MyPlugin",
        )

        with pytest.raises(ValueError, match="module.path:ClassName"):
            initialize_plugin(manifest)

    # 10
    def test_initialize_rejects_outside_allowed_prefix(self):
        """entry_point outside marketplace.plugins. should raise ValueError."""
        manifest = PluginManifest(
            name="bad", version="1.0", description="d", author="a",
            entry_point="os.path:join",
        )

        with pytest.raises(ValueError, match="must be under"):
            initialize_plugin(manifest)

    # 11
    def test_initialize_rejects_path_traversal(self):
        """entry_point with '..' should raise ValueError."""
        manifest = PluginManifest(
            name="bad", version="1.0", description="d", author="a",
            entry_point="marketplace.plugins...evil:BadClass",
        )

        with pytest.raises(ValueError, match="path traversal"):
            initialize_plugin(manifest)

    # 12
    def test_initialize_rejects_non_identifier_class_name(self):
        """Class name that is not a valid identifier should raise ValueError."""
        manifest = PluginManifest(
            name="bad", version="1.0", description="d", author="a",
            entry_point="marketplace.plugins.example:123Bad",
        )

        with pytest.raises(ValueError, match="Invalid class name"):
            initialize_plugin(manifest)

    # 13
    def test_initialize_rejects_underscore_prefix_class(self):
        """Class name starting with underscore should raise ValueError."""
        manifest = PluginManifest(
            name="bad", version="1.0", description="d", author="a",
            entry_point="marketplace.plugins.example:_PrivateClass",
        )

        with pytest.raises(ValueError, match="must not start with underscore"):
            initialize_plugin(manifest)

    # 14
    def test_initialize_rejects_non_class_entry_point(self):
        """entry_point pointing to a function (not a class) should raise ValueError."""
        manifest = PluginManifest(
            name="func", version="1.0", description="d", author="a",
            entry_point="marketplace.plugins.example:some_function",
        )

        with patch("importlib.import_module") as mock_import:
            mock_module = MagicMock()
            mock_module.some_function = lambda: None  # Function, not a class
            mock_import.return_value = mock_module

            with pytest.raises(ValueError, match="is not a class"):
                initialize_plugin(manifest)

    # 15
    def test_initialize_handles_import_error(self):
        """ImportError during module import should propagate."""
        manifest = PluginManifest(
            name="missing", version="1.0", description="d", author="a",
            entry_point="marketplace.plugins.nonexistent:SomeClass",
        )

        with patch("importlib.import_module", side_effect=ImportError("No module")):
            with pytest.raises(ImportError):
                initialize_plugin(manifest)

    # 16
    def test_initialize_handles_attribute_error(self):
        """Missing class on the module should raise AttributeError."""
        manifest = PluginManifest(
            name="attr", version="1.0", description="d", author="a",
            entry_point="marketplace.plugins.example:MissingClass",
        )

        with patch("importlib.import_module") as mock_import:
            mock_module = MagicMock(spec=[])  # Empty spec, no attributes
            mock_import.return_value = mock_module

            with pytest.raises(AttributeError):
                initialize_plugin(manifest)


class TestPluginManifestDataclass:
    """Test 17: PluginManifest dataclass defaults."""

    # 17
    def test_manifest_defaults(self):
        """PluginManifest should have correct defaults for optional fields."""
        manifest = PluginManifest(
            name="m", version="0.1", description="d",
            author="a", entry_point="marketplace.plugins.x:Y",
        )

        assert manifest.dependencies == []
        assert manifest.enabled is True

    # 17b
    def test_manifest_with_all_fields(self):
        """PluginManifest should accept all fields."""
        manifest = PluginManifest(
            name="full", version="2.0", description="full desc",
            author="full-author", entry_point="marketplace.plugins.x:Y",
            dependencies=["dep1", "dep2"], enabled=False,
        )

        assert manifest.name == "full"
        assert manifest.dependencies == ["dep1", "dep2"]
        assert manifest.enabled is False


class TestAllowedPrefixConstant:
    """Test: verify the security prefix constant."""

    def test_allowed_prefix(self):
        """The allowed plugin module prefix should be marketplace.plugins."""
        assert _ALLOWED_PLUGIN_MODULE_PREFIX == "marketplace.plugins."
