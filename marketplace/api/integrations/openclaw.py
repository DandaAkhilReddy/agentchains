"""OpenClaw integration endpoints — webhook registration and event delivery."""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from marketplace.core.auth import get_current_agent_id
from marketplace.database import get_db
from marketplace.services import openclaw_service

router = APIRouter(prefix="/integrations/openclaw", tags=["openclaw"])


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class WebhookRegisterRequest(BaseModel):
    gateway_url: str = Field(..., description="OpenClaw gateway POST /hooks/agent URL")
    bearer_token: str = Field(..., description="OpenClaw webhook bearer token")
    event_types: list[str] = ["opportunity", "demand_spike", "transaction", "listing_created"]
    filters: dict = {}


class WebhookResponse(BaseModel):
    id: str
    agent_id: str
    gateway_url: str
    event_types: list[str]
    filters: dict
    status: str
    failure_count: int
    last_delivered_at: Optional[str] = None
    created_at: Optional[str] = None


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("/register-webhook", response_model=WebhookResponse)
async def register_webhook(
    req: WebhookRegisterRequest,
    db: AsyncSession = Depends(get_db),
    agent_id: str = Depends(get_current_agent_id),
):
    """Register an OpenClaw gateway to receive marketplace events."""
    webhook = await openclaw_service.register_webhook(
        db, agent_id, req.gateway_url, req.bearer_token,
        event_types=req.event_types, filters=req.filters,
    )
    return openclaw_service._webhook_to_dict(webhook)


@router.get("/webhooks")
async def list_webhooks(
    db: AsyncSession = Depends(get_db),
    agent_id: str = Depends(get_current_agent_id),
):
    """List all registered webhooks for the authenticated agent."""
    webhooks = await openclaw_service.list_webhooks(db, agent_id)
    return {"webhooks": webhooks, "count": len(webhooks)}


@router.delete("/webhooks/{webhook_id}")
async def delete_webhook(
    webhook_id: str,
    db: AsyncSession = Depends(get_db),
    agent_id: str = Depends(get_current_agent_id),
):
    """Delete a webhook registration."""
    deleted = await openclaw_service.delete_webhook(db, webhook_id, agent_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Webhook not found")
    return {"deleted": True}


@router.post("/webhooks/{webhook_id}/test")
async def test_webhook(
    webhook_id: str,
    db: AsyncSession = Depends(get_db),
    agent_id: str = Depends(get_current_agent_id),
):
    """Send a test event to verify webhook connectivity."""
    result = await openclaw_service.test_webhook(db, webhook_id, agent_id)
    return result


@router.get("/status")
async def get_status(
    db: AsyncSession = Depends(get_db),
    agent_id: str = Depends(get_current_agent_id),
):
    """Get OpenClaw connection status for the authenticated agent."""
    return await openclaw_service.get_status(db, agent_id)
