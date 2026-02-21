"""Hello plugin -- minimal example demonstrating the plugin lifecycle hooks.

Provides a simple ``HelloPlugin`` class that responds to marketplace
lifecycle events: registration, agent creation, and listing creation.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


class HelloPlugin:
    """Example plugin that logs friendly messages on marketplace events.

    Implements the standard plugin hook interface:
    - ``on_register()`` -- called when the plugin is added to the registry
    - ``on_agent_created(agent)`` -- called when a new agent is registered
    - ``on_listing_created(listing)`` -- called when a new listing is published
    - ``get_info()`` -- returns metadata about this plugin
    """

    def __init__(self) -> None:
        self._registered = False
        self._agents_seen: list[str] = []
        self._listings_seen: list[str] = []

    def on_register(self) -> None:
        """Called when the plugin is registered with the PluginRegistry."""
        self._registered = True
        logger.info("[HelloPlugin] Registered and ready to greet new agents!")

    def on_agent_created(self, agent: Any) -> None:
        """Called when a new agent is created in the marketplace.

        *agent* may be a dict or object with an ``agent_id`` attribute.
        """
        agent_id = (
            agent.get("agent_id", "unknown")
            if isinstance(agent, dict)
            else getattr(agent, "agent_id", "unknown")
        )
        self._agents_seen.append(agent_id)
        logger.info(
            "[HelloPlugin] Welcome to AgentChains, agent %s! You are agent #%d.",
            agent_id,
            len(self._agents_seen),
        )

    def on_listing_created(self, listing: Any) -> None:
        """Called when a new listing is created.

        *listing* may be a dict or object with a ``listing_id`` attribute.
        """
        listing_id = (
            listing.get("listing_id", "unknown")
            if isinstance(listing, dict)
            else getattr(listing, "listing_id", "unknown")
        )
        self._listings_seen.append(listing_id)
        logger.info(
            "[HelloPlugin] New listing published: %s (total: %d)",
            listing_id,
            len(self._listings_seen),
        )

    def get_info(self) -> dict:
        """Return metadata about this plugin and its current state."""
        return {
            "name": "hello_plugin",
            "version": "0.1.0",
            "author": "AgentChains Team",
            "description": "Simple example plugin that greets new agents and listings.",
            "registered": self._registered,
            "agents_greeted": len(self._agents_seen),
            "listings_seen": len(self._listings_seen),
        }
