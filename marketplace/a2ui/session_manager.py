"""A2UI session lifecycle and rate limiting.

Pattern follows marketplace/mcp/session_manager.py with additions for
pending input futures and active component tracking.
"""

import asyncio
import time
import uuid
from dataclasses import dataclass, field
from typing import Any


@dataclass
class A2UISession:
    session_id: str
    agent_id: str
    user_id: str | None = None
    created_at: float = field(default_factory=time.monotonic)
    last_activity: float = field(default_factory=time.monotonic)
    request_count: int = 0
    window_start: float = field(default_factory=time.monotonic)
    capabilities: dict[str, Any] = field(default_factory=dict)
    pending_inputs: dict[str, asyncio.Future] = field(default_factory=dict)
    active_components: set[str] = field(default_factory=set)


class A2UISessionManager:
    """Manage A2UI sessions with rate limiting."""

    def __init__(self, rate_limit_per_minute: int = 60, session_timeout: float = 3600):
        self._sessions: dict[str, A2UISession] = {}
        self._rate_limit = rate_limit_per_minute
        self._timeout = session_timeout

    def create_session(
        self,
        agent_id: str,
        user_id: str | None = None,
        capabilities: dict[str, Any] | None = None,
    ) -> A2UISession:
        session_id = str(uuid.uuid4())
        session = A2UISession(
            session_id=session_id,
            agent_id=agent_id,
            user_id=user_id,
            capabilities=capabilities or {},
        )
        self._sessions[session_id] = session
        return session

    def get_session(self, session_id: str) -> A2UISession | None:
        session = self._sessions.get(session_id)
        if session is None:
            return None
        # Check timeout
        if time.monotonic() - session.last_activity > self._timeout:
            del self._sessions[session_id]
            return None
        return session

    def check_rate_limit(self, session: A2UISession) -> bool:
        """Returns True if request is within rate limit, False if exceeded."""
        now = time.monotonic()
        # Reset window every 60 seconds
        if now - session.window_start > 60:
            session.window_start = now
            session.request_count = 0

        session.request_count += 1
        session.last_activity = now
        return session.request_count <= self._rate_limit

    def close_session(self, session_id: str):
        session = self._sessions.pop(session_id, None)
        if session:
            # Cancel any pending input futures
            for future in session.pending_inputs.values():
                if not future.done():
                    future.cancel()

    def cleanup_expired(self):
        """Remove expired sessions."""
        now = time.monotonic()
        expired = [
            sid for sid, s in self._sessions.items()
            if now - s.last_activity > self._timeout
        ]
        for sid in expired:
            self.close_session(sid)

    @property
    def active_count(self) -> int:
        return len(self._sessions)

    def set_pending_input(self, session_id: str, request_id: str) -> asyncio.Future:
        """Create and store a Future for a pending user input request."""
        session = self.get_session(session_id)
        if not session:
            raise ValueError(f"Session {session_id} not found")
        loop = asyncio.get_running_loop()
        future: asyncio.Future = loop.create_future()
        session.pending_inputs[request_id] = future
        return future

    def resolve_pending_input(self, session_id: str, request_id: str, value: Any) -> bool:
        """Resolve a pending input Future with the user's value.

        Returns True if the future was found and resolved, False otherwise.
        """
        session = self.get_session(session_id)
        if not session:
            return False
        future = session.pending_inputs.pop(request_id, None)
        if future is None or future.done():
            return False
        future.set_result(value)
        return True


# Singleton
a2ui_session_manager = A2UISessionManager()
