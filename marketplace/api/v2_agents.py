"""Agent onboarding and trust lifecycle endpoints (v2 canonical API)."""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from marketplace.core.auth import create_stream_token, get_current_agent_id
from marketplace.core.creator_auth import get_current_creator_id
from marketplace.core.exceptions import AgentAlreadyExistsError, UnauthorizedError
from marketplace.database import get_db
from marketplace.schemas.agent import AgentRegisterRequest
from marketplace.services import agent_trust_service, registry_service

router = APIRouter(prefix="/agents", tags=["agents-v2"])


class AgentOnboardRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    description: str = ""
    agent_type: str = Field(..., pattern="^(seller|buyer|both)$")
    public_key: str = Field(..., min_length=10)
    wallet_address: str = ""
    capabilities: list[str] = []
    a2a_endpoint: str = ""
    memory_import_intent: bool = False


class RuntimeAttestationRequest(BaseModel):
    runtime_name: str = Field(default="unspecified", min_length=1, max_length=80)
    runtime_version: str = Field(default="", max_length=80)
    sdk_version: str = Field(default="", max_length=80)
    endpoint_reachable: bool = False
    supports_memory: bool = False


class KnowledgeChallengeRequest(BaseModel):
    capabilities: list[str] = Field(default_factory=list)
    claim_payload: dict[str, Any] = Field(default_factory=dict)


@router.post("/onboard", status_code=201)
async def onboard_agent_v2(
    req: AgentOnboardRequest,
    db: AsyncSession = Depends(get_db),
    authorization: str | None = Header(default=None),
):
    """Open self-serve onboarding for creators with deterministic trust bootstrap."""
    try:
        creator_id = get_current_creator_id(authorization)
    except UnauthorizedError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc

    register_req = AgentRegisterRequest(
        name=req.name,
        description=req.description,
        agent_type=req.agent_type,
        public_key=req.public_key,
        wallet_address=req.wallet_address,
        capabilities=req.capabilities,
        a2a_endpoint=req.a2a_endpoint,
    )
    try:
        registered = await registry_service.register_agent(
            db,
            register_req,
            creator_id=creator_id,
        )
    except AgentAlreadyExistsError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    identity = await agent_trust_service.run_identity_attestation(
        db,
        agent_id=registered.id,
        creator_id=creator_id,
    )
    profile = identity["profile"]
    if req.memory_import_intent:
        profile = await agent_trust_service.update_memory_stage(
            db,
            agent_id=registered.id,
            snapshot_id="pending-import",
            status="pending_verification",
            score=2,
            provenance={
                "memory_import_intent": True,
                "verified": False,
            },
        )

    return {
        "onboarding_session_id": str(uuid.uuid4()),
        "agent_id": registered.id,
        "agent_name": registered.name,
        "agent_jwt_token": registered.jwt_token,
        "agent_card_url": registered.agent_card_url,
        "stream_token": create_stream_token(registered.id),
        **profile,
    }


@router.post("/{agent_id}/attest/runtime")
async def attest_runtime_v2(
    agent_id: str,
    req: RuntimeAttestationRequest,
    db: AsyncSession = Depends(get_db),
    current_agent_id: str = Depends(get_current_agent_id),
):
    if current_agent_id != agent_id:
        raise HTTPException(status_code=403, detail="Can only attest runtime for your own agent")
    return await agent_trust_service.run_runtime_attestation(
        db,
        agent_id=agent_id,
        runtime_name=req.runtime_name,
        runtime_version=req.runtime_version,
        sdk_version=req.sdk_version,
        endpoint_reachable=req.endpoint_reachable,
        supports_memory=req.supports_memory,
    )


@router.post("/{agent_id}/attest/knowledge/run")
async def run_knowledge_challenge_v2(
    agent_id: str,
    req: KnowledgeChallengeRequest,
    db: AsyncSession = Depends(get_db),
    current_agent_id: str = Depends(get_current_agent_id),
):
    if current_agent_id != agent_id:
        raise HTTPException(
            status_code=403,
            detail="Can only run knowledge challenge for your own agent",
        )
    capabilities = req.capabilities or ["general"]
    return await agent_trust_service.run_knowledge_challenge(
        db,
        agent_id=agent_id,
        capabilities=capabilities,
        claim_payload=req.claim_payload,
    )


@router.get("/{agent_id}/trust")
async def get_agent_trust_v2(
    agent_id: str,
    db: AsyncSession = Depends(get_db),
):
    try:
        return await agent_trust_service.get_or_create_trust_profile(db, agent_id=agent_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
