"""MCP session lifecycle and rate limiting."""

import time
import uuid
from dataclasses import dataclass, field


@dataclass
class MCPSession:
    session_id: str
    agent_id: str
    created_at: float = field(default_factory=time.monotonic)
    last_activity: float = field(default_factory=time.monotonic)
    request_count: int = 0
    window_start: float = field(default_factory=time.monotonic)


class SessionManager:
    """Manage MCP sessions with rate limiting."""

    def __init__(self, rate_limit_per_minute: int = 60, session_timeout: float = 3600):
        self._sessions: dict[str, MCPSession] = {}
        self._rate_limit = rate_limit_per_minute
        self._timeout = session_timeout

    def create_session(self, agent_id: str) -> MCPSession:
        session_id = str(uuid.uuid4())
        session = MCPSession(session_id=session_id, agent_id=agent_id)
        self._sessions[session_id] = session
        return session

    def get_session(self, session_id: str) -> MCPSession | None:
        session = self._sessions.get(session_id)
        if session is None:
            return None
        # Check timeout
        if time.monotonic() - session.last_activity > self._timeout:
            del self._sessions[session_id]
            return None
        return session

    def check_rate_limit(self, session: MCPSession) -> bool:
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
        self._sessions.pop(session_id, None)

    def cleanup_expired(self):
        """Remove expired sessions."""
        now = time.monotonic()
        expired = [
            sid for sid, s in self._sessions.items()
            if now - s.last_activity > self._timeout
        ]
        for sid in expired:
            del self._sessions[sid]

    @property
    def active_count(self) -> int:
        return len(self._sessions)


# Singleton
session_manager = SessionManager()
