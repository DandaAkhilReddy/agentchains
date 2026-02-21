"""A2UI v4 API — stream tokens, session management, and health check."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException

from marketplace.a2ui import A2UI_VERSION, A2UI_WS_PATH
from marketplace.a2ui.session_manager import a2ui_session_manager
from marketplace.config import settings
from marketplace.core.auth import create_stream_token, get_current_agent_id

router = APIRouter(prefix="", tags=["a2ui"])


@router.post("/stream-token")
async def generate_stream_token(agent_id: str = Depends(get_current_agent_id)):
    """Generate a stream token for A2UI WebSocket authentication.

    Requires an agent JWT in the Authorization header.
    """
    expires_in_seconds = int(settings.stream_token_expire_minutes * 60)
    expires_at = datetime.now(timezone.utc) + timedelta(seconds=expires_in_seconds)
    return {
        "agent_id": agent_id,
        "stream_token": create_stream_token(
            agent_id,
            token_type="stream_agent",
            allowed_topics=["a2ui"],
        ),
        "expires_in_seconds": expires_in_seconds,
        "expires_at": expires_at.isoformat(),
        "ws_url": A2UI_WS_PATH,
    }


@router.get("/sessions")
async def list_sessions(agent_id: str = Depends(get_current_agent_id)):
    """List active A2UI sessions for the authenticated agent."""
    sessions = []
    for sid, session in a2ui_session_manager._sessions.items():
        if session.agent_id != agent_id:
            continue
        sessions.append({
            "session_id": session.session_id,
            "agent_id": session.agent_id,
            "user_id": session.user_id,
            "active_components": len(session.active_components),
            "pending_inputs": len(session.pending_inputs),
        })
    return {"sessions": sessions, "total": len(sessions)}


@router.get("/sessions/{session_id}")
async def get_session(session_id: str, agent_id: str = Depends(get_current_agent_id)):
    """Get details for a specific A2UI session."""
    session = a2ui_session_manager.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    if session.agent_id != agent_id:
        raise HTTPException(status_code=403, detail="Not authorised to view this session")
    return {
        "session_id": session.session_id,
        "agent_id": session.agent_id,
        "user_id": session.user_id,
        "capabilities": session.capabilities,
        "active_components": list(session.active_components),
        "pending_inputs": list(session.pending_inputs.keys()),
        "request_count": session.request_count,
    }


@router.delete("/sessions/{session_id}")
async def close_session(session_id: str, agent_id: str = Depends(get_current_agent_id)):
    """Close an A2UI session."""
    session = a2ui_session_manager.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    if session.agent_id != agent_id:
        raise HTTPException(status_code=403, detail="Not authorised to close this session")
    a2ui_session_manager.close_session(session_id)
    return {"status": "closed", "session_id": session_id}


@router.get("/health")
async def a2ui_health():
    """A2UI protocol health check."""
    return {
        "status": "ok",
        "protocol": "a2ui",
        "version": A2UI_VERSION,
        "ws_path": A2UI_WS_PATH,
        "active_sessions": a2ui_session_manager.active_count,
    }
