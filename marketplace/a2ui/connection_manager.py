"""A2UI WebSocket connection manager.

Pattern follows marketplace/main.py ConnectionManager / ScopedConnectionManager
with session-to-WebSocket and agent-to-session mappings.
"""

import json
import logging
from typing import Any

from fastapi import WebSocket

logger = logging.getLogger(__name__)


class A2UIConnectionManager:
    """Manage A2UI WebSocket connections with session and agent tracking."""

    MAX_CONNECTIONS = 500

    def __init__(self):
        self._session_ws: dict[str, WebSocket] = {}
        self._agent_sessions: dict[str, set[str]] = {}

    async def connect(self, ws: WebSocket, session_id: str, agent_id: str) -> bool:
        """Accept and track a WebSocket connection for an A2UI session."""
        if len(self._session_ws) >= self.MAX_CONNECTIONS:
            await ws.close(code=4029, reason="Too many A2UI connections")
            return False
        await ws.accept()
        self._session_ws[session_id] = ws
        if agent_id not in self._agent_sessions:
            self._agent_sessions[agent_id] = set()
        self._agent_sessions[agent_id].add(session_id)
        return True

    def disconnect(self, ws: WebSocket) -> None:
        """Remove a WebSocket from all tracking structures."""
        # Find session_id for this WebSocket
        session_id: str | None = None
        for sid, sock in self._session_ws.items():
            if sock is ws:
                session_id = sid
                break
        if session_id is None:
            return
        del self._session_ws[session_id]
        # Remove from agent mapping
        for agent_id, sessions in list(self._agent_sessions.items()):
            sessions.discard(session_id)
            if not sessions:
                del self._agent_sessions[agent_id]

    async def send_to_session(self, session_id: str, message: dict[str, Any]) -> bool:
        """Send a JSON message to a specific session's WebSocket.

        Returns True if the message was sent, False otherwise.
        """
        ws = self._session_ws.get(session_id)
        if ws is None:
            return False
        try:
            await ws.send_text(json.dumps(message))
            return True
        except Exception:
            logger.warning("Failed to send to A2UI session %s", session_id)
            self.disconnect(ws)
            return False

    async def broadcast_to_agent(self, agent_id: str, message: dict[str, Any]) -> None:
        """Send a JSON message to all sessions belonging to an agent."""
        session_ids = self._agent_sessions.get(agent_id)
        if not session_ids:
            return
        data = json.dumps(message)
        dead: list[WebSocket] = []
        for sid in list(session_ids):
            ws = self._session_ws.get(sid)
            if ws is None:
                continue
            try:
                await ws.send_text(data)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(ws)


# Singleton
a2ui_connection_manager = A2UIConnectionManager()
