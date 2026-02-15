"""Event stream bootstrap endpoints (v2 canonical API)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends

from marketplace.config import settings
from marketplace.core.auth import create_stream_token, get_current_agent_id

router = APIRouter(prefix="/events", tags=["events-v2"])


@router.get("/stream-token")
async def get_stream_token_v2(agent_id: str = Depends(get_current_agent_id)):
    expires_in_seconds = int(settings.stream_token_expire_minutes * 60)
    expires_at = datetime.now(timezone.utc) + timedelta(seconds=expires_in_seconds)
    return {
        "agent_id": agent_id,
        "stream_token": create_stream_token(agent_id),
        "expires_in_seconds": expires_in_seconds,
        "expires_at": expires_at.isoformat(),
        "ws_url": "/ws/v2/events",
        "allowed_topics": ["public.market", "private.agent"],
    }
