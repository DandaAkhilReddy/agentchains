"""Platform-neutral webhook integrations (v2 canonical API)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from marketplace.core.auth import get_current_agent_id
from marketplace.database import get_db
from marketplace.services import event_subscription_service

router = APIRouter(prefix="/integrations", tags=["integrations-v2"])


class WebhookSubscriptionRequest(BaseModel):
    callback_url: str = Field(..., min_length=8, max_length=500)
    event_types: list[str] = Field(default_factory=lambda: ["*"])


@router.post("/webhooks", status_code=201)
async def create_webhook_subscription_v2(
    req: WebhookSubscriptionRequest,
    db: AsyncSession = Depends(get_db),
    agent_id: str = Depends(get_current_agent_id),
):
    try:
        return await event_subscription_service.register_subscription(
            db,
            agent_id=agent_id,
            callback_url=req.callback_url,
            event_types=req.event_types,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/webhooks")
async def list_webhook_subscriptions_v2(
    db: AsyncSession = Depends(get_db),
    agent_id: str = Depends(get_current_agent_id),
):
    subscriptions = await event_subscription_service.list_subscriptions(
        db,
        agent_id=agent_id,
    )
    return {"subscriptions": subscriptions, "count": len(subscriptions)}


@router.delete("/webhooks/{subscription_id}")
async def delete_webhook_subscription_v2(
    subscription_id: str,
    db: AsyncSession = Depends(get_db),
    agent_id: str = Depends(get_current_agent_id),
):
    deleted = await event_subscription_service.delete_subscription(
        db,
        agent_id=agent_id,
        subscription_id=subscription_id,
    )
    if not deleted:
        raise HTTPException(status_code=404, detail="Webhook subscription not found")
    return {"deleted": True}
