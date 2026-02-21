"""Plugin registry -- central registry for loaded plugin instances.

Provides:
- ``PluginRegistry`` class to register, unregister, query, and execute hooks
- ``plugin_registry`` module-level singleton for global access
"""

from __future__ import annotations

import logging
from typing import Any

from marketplace.plugins.loader import PluginManifest

logger = logging.getLogger(__name__)


class PluginRegistry:
    """Central registry that tracks loaded plugin instances and enables hook execution.

    Plugins are registered with their :class:`PluginManifest` and live instance.
    The registry supports executing named hooks across all plugins that implement
    the corresponding method.
    """

    def __init__(self) -> None:
        self._plugins: dict[str, dict[str, Any]] = {}

    def register(self, manifest: PluginManifest, instance: Any) -> bool:
        """Register a plugin with its *manifest* and *instance*.

        Returns ``True`` if the plugin was newly registered, ``False`` if a
        plugin with the same name was already present (existing registration
        is left unchanged).
        """
        if manifest.name in self._plugins:
            logger.warning("Plugin already registered: %s", manifest.name)
            return False

        self._plugins[manifest.name] = {
            "manifest": manifest,
            "instance": instance,
        }
        logger.info("Registered plugin: %s v%s", manifest.name, manifest.version)

        # Call on_register lifecycle hook if available
        if hasattr(instance, "on_register"):
            try:
                instance.on_register()
            except Exception as exc:
                logger.error("on_register failed for %s: %s", manifest.name, exc)

        return True

    def unregister(self, plugin_name: str) -> bool:
        """Remove a plugin from the registry by *plugin_name*.

        Returns ``True`` if the plugin was found and removed, ``False`` otherwise.
        """
        entry = self._plugins.pop(plugin_name, None)
        if entry is None:
            return False

        logger.info("Unregistered plugin: %s", plugin_name)
        return True

    def get(self, plugin_name: str) -> Any | None:
        """Return the instance of a registered plugin, or ``None`` if not found."""
        entry = self._plugins.get(plugin_name)
        return entry["instance"] if entry else None

    def list_plugins(self) -> list[dict]:
        """Return a list of dicts describing every registered plugin.

        Each dict contains ``name``, ``version``, ``description``, ``author``,
        and ``enabled`` fields from the manifest.
        """
        results: list[dict] = []
        for entry in self._plugins.values():
            manifest: PluginManifest = entry["manifest"]
            results.append({
                "name": manifest.name,
                "version": manifest.version,
                "description": manifest.description,
                "author": manifest.author,
                "enabled": manifest.enabled,
            })
        return results

    def is_registered(self, plugin_name: str) -> bool:
        """Return ``True`` if a plugin with *plugin_name* is registered."""
        return plugin_name in self._plugins

    def execute_hook(self, hook_name: str, *args: Any, **kwargs: Any) -> list:
        """Execute *hook_name* on every registered plugin that implements it.

        Returns a list of return values from each plugin that handled the hook.
        Plugins that do not implement the hook are silently skipped.
        Exceptions within individual hooks are logged but do not prevent
        other plugins from executing.
        """
        results: list = []
        for name, entry in self._plugins.items():
            instance = entry["instance"]
            handler = getattr(instance, hook_name, None)
            if handler is None:
                continue
            try:
                result = handler(*args, **kwargs)
                results.append(result)
            except Exception as exc:
                logger.error(
                    "Hook '%s' failed in plugin '%s': %s", hook_name, name, exc
                )
        return results


# Singleton instance for global access
plugin_registry = PluginRegistry()
