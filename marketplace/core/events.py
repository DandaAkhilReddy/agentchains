"""Event broadcasting system — decouples services from main.py.

Services import ``broadcast_event`` from here instead of ``marketplace.main``,
breaking the circular dependency.  The actual broadcaster is registered at
app startup by main.py via ``register_broadcaster()``.

If no broadcaster has been registered (e.g. during unit tests or when
services are imported without a running app), calls to ``broadcast_event``
are silently ignored — matching the previous try/except ImportError behavior.
"""

from __future__ import annotations

import logging
from typing import Awaitable, Callable

from marketplace.core.async_tasks import fire_and_forget

logger = logging.getLogger(__name__)

# The registered broadcaster function signature
BroadcasterFn = Callable[[str, dict], Awaitable[None]]

_broadcaster: BroadcasterFn | None = None


def register_broadcaster(fn: BroadcasterFn) -> None:
    """Register the concrete broadcast_event implementation (called by main.py at startup)."""
    global _broadcaster
    _broadcaster = fn
    logger.info("Event broadcaster registered")


def broadcast_event(event_type: str, data: dict) -> None:
    """Fire-and-forget an event broadcast.

    Safe to call even when no broadcaster is registered — the event
    is simply dropped (matching previous behavior where
    ``from marketplace.main import broadcast_event`` would fail silently
    inside a try/except).
    """
    if _broadcaster is None:
        return
    fire_and_forget(
        _broadcaster(event_type, data),
        task_name=f"broadcast_{event_type}",
    )
