"""A2UI security utilities.

Provides HTML sanitisation, payload size validation, and consent tracking.
"""

from __future__ import annotations

import html
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


def sanitize_html(text: str) -> str:
    """Strip dangerous tags/attributes using html.escape (basic XSS prevention)."""
    return html.escape(text, quote=True)


def validate_payload_size(data: dict[str, Any], max_bytes: int = 1_048_576) -> bool:
    """Check that a payload dictionary isn't too large (default 1 MB).

    Returns True if the payload is within the size limit, False if exceeded.
    """
    try:
        raw = json.dumps(data, default=str)
        return len(raw.encode("utf-8")) <= max_bytes
    except (TypeError, ValueError):
        return False


@dataclass
class _ConsentEntry:
    consent_type: str
    granted: bool
    granted_at: datetime


class A2UIConsentTracker:
    """Track per-session consent for A2UI operations."""

    def __init__(self):
        self._consents: dict[str, dict[str, _ConsentEntry]] = {}

    def track_consent(self, session_id: str, consent_type: str, granted: bool) -> None:
        """Record a consent decision for a session."""
        if session_id not in self._consents:
            self._consents[session_id] = {}
        self._consents[session_id][consent_type] = _ConsentEntry(
            consent_type=consent_type,
            granted=granted,
            granted_at=datetime.now(timezone.utc),
        )

    def check_consent(self, session_id: str, consent_type: str) -> bool:
        """Check if a consent type is currently granted for a session."""
        session_consents = self._consents.get(session_id, {})
        entry = session_consents.get(consent_type)
        if entry is None:
            return False
        return entry.granted

    def revoke_consent(self, session_id: str) -> None:
        """Revoke all consents for a session."""
        self._consents.pop(session_id, None)
