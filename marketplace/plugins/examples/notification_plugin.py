"""Notification plugin -- dispatches event notifications across channels.

Provides a ``NotificationPlugin`` class that receives marketplace events
and routes them to configured notification channels (log, webhook, email).
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


class NotificationPlugin:
    """Routes marketplace event notifications to configured channels.

    Implements the standard plugin hook interface:
    - ``on_event(event_type, data)`` -- called on any marketplace event
    - ``get_channels()`` -- returns the list of active notification channels
    """

    DEFAULT_CHANNELS = ["log", "webhook", "email"]

    def __init__(self) -> None:
        self._channels: list[str] = list(self.DEFAULT_CHANNELS)
        self._event_log: list[dict] = []
        self._registered = False

    def on_register(self) -> None:
        """Called when the plugin is registered with the PluginRegistry."""
        self._registered = True
        logger.info(
            "[NotificationPlugin] Registered -- channels: %s",
            ", ".join(self._channels),
        )

    def on_event(self, event_type: str, data: Any) -> None:
        """Handle a marketplace event and dispatch to all active channels.

        Parameters
        ----------
        event_type:
            The type of event, e.g. ``"agent_created"``, ``"transaction_completed"``.
        data:
            The event payload (dict or object).
        """
        entry = {
            "event_type": event_type,
            "data": data if isinstance(data, dict) else str(data),
            "channels_notified": list(self._channels),
        }
        self._event_log.append(entry)

        for channel in self._channels:
            self._dispatch(channel, event_type, data)

    def get_channels(self) -> list[str]:
        """Return the list of currently active notification channels."""
        return list(self._channels)

    def add_channel(self, channel: str) -> None:
        """Add a notification channel if not already present."""
        if channel not in self._channels:
            self._channels.append(channel)
            logger.info("[NotificationPlugin] Added channel: %s", channel)

    def remove_channel(self, channel: str) -> None:
        """Remove a notification channel if present."""
        if channel in self._channels:
            self._channels.remove(channel)
            logger.info("[NotificationPlugin] Removed channel: %s", channel)

    def get_event_log(self) -> list[dict]:
        """Return the list of all dispatched event records."""
        return list(self._event_log)

    # ------------------------------------------------------------------
    # Internal dispatch
    # ------------------------------------------------------------------

    @staticmethod
    def _dispatch(channel: str, event_type: str, data: Any) -> None:
        """Dispatch a notification to a specific channel.

        In this example implementation all channels simply log the event.
        A production version would integrate with webhooks, email APIs, etc.
        """
        if channel == "log":
            logger.info(
                "[NotificationPlugin][log] Event: %s | Data: %s",
                event_type,
                data,
            )
        elif channel == "webhook":
            logger.info(
                "[NotificationPlugin][webhook] Would POST event '%s' to webhook endpoint",
                event_type,
            )
        elif channel == "email":
            logger.info(
                "[NotificationPlugin][email] Would send email notification for '%s'",
                event_type,
            )
        else:
            logger.debug(
                "[NotificationPlugin][%s] Event: %s", channel, event_type
            )
