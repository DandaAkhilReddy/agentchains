"""Plugin loader -- discovers, validates, and dynamically loads marketplace plugins.

Provides:
- ``PluginManifest`` dataclass describing a plugin from its ``plugin.json``
- ``load_plugin()`` to read a single manifest file
- ``load_plugins_from_directory()`` to discover all manifests under a directory
- ``initialize_plugin()`` to dynamically import and instantiate a plugin
"""

from __future__ import annotations

import importlib
import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

DEFAULT_PLUGINS_DIR = Path(__file__).parent / "examples"


@dataclass
class PluginManifest:
    """Metadata describing a marketplace plugin, read from ``plugin.json``."""

    name: str
    version: str
    description: str
    author: str
    entry_point: str
    dependencies: list[str] = field(default_factory=list)
    enabled: bool = True


def load_plugin(manifest_path: str | Path) -> PluginManifest:
    """Read a ``plugin.json`` file at *manifest_path* and return a validated manifest.

    Raises ``FileNotFoundError`` if the path does not exist and
    ``ValueError`` if required fields are missing.
    """
    manifest_path = Path(manifest_path)

    if not manifest_path.exists():
        raise FileNotFoundError(f"Plugin manifest not found: {manifest_path}")

    with open(manifest_path, "r", encoding="utf-8") as fh:
        data = json.load(fh)

    required = ("name", "version", "description", "author", "entry_point")
    missing = [k for k in required if k not in data]
    if missing:
        raise ValueError(f"Manifest missing required fields: {', '.join(missing)}")

    return PluginManifest(
        name=data["name"],
        version=data["version"],
        description=data["description"],
        author=data["author"],
        entry_point=data["entry_point"],
        dependencies=data.get("dependencies", []),
        enabled=data.get("enabled", True),
    )


def load_plugins_from_directory(plugins_dir: str | Path | None = None) -> list[PluginManifest]:
    """Scan *plugins_dir* for ``plugin.json`` files and return all valid manifests.

    Defaults to the built-in ``examples/`` directory when *plugins_dir* is ``None``.
    """
    plugins_dir = Path(plugins_dir) if plugins_dir else DEFAULT_PLUGINS_DIR
    manifests: list[PluginManifest] = []

    if not plugins_dir.exists():
        logger.warning("Plugins directory does not exist: %s", plugins_dir)
        return manifests

    for manifest_path in plugins_dir.rglob("plugin.json"):
        try:
            manifest = load_plugin(manifest_path)
            manifests.append(manifest)
            logger.info("Discovered plugin: %s v%s", manifest.name, manifest.version)
        except (json.JSONDecodeError, KeyError, ValueError, FileNotFoundError) as exc:
            logger.error("Invalid manifest %s: %s", manifest_path, exc)

    return manifests


def initialize_plugin(manifest: PluginManifest) -> Any:
    """Dynamically import and instantiate the plugin described by *manifest*.

    The ``entry_point`` field must be in ``module.path:ClassName`` format.
    Returns the instantiated plugin object.

    Raises ``ValueError`` if the entry_point format is invalid and
    ``ImportError`` / ``AttributeError`` on module resolution failures.
    """
    entry_point = manifest.entry_point

    if ":" not in entry_point:
        raise ValueError(
            f"entry_point must be 'module.path:ClassName', got '{entry_point}'"
        )

    module_path, class_name = entry_point.rsplit(":", 1)
    module = importlib.import_module(module_path)
    cls = getattr(module, class_name)

    instance = cls()
    logger.info("Initialized plugin: %s (%s)", manifest.name, class_name)
    return instance
