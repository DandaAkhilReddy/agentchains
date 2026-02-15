"""Managed memory vault endpoints (v2 canonical API)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from marketplace.core.auth import get_current_agent_id
from marketplace.database import get_db
from marketplace.models.agent import RegisteredAgent
from marketplace.services import memory_service

router = APIRouter(prefix="/memory", tags=["memory-v2"])


class SnapshotImportRequest(BaseModel):
    source_type: str = Field(default="sdk", min_length=2, max_length=40)
    label: str = Field(default="default", min_length=1, max_length=120)
    records: list[dict[str, Any]] = Field(default_factory=list)
    chunk_size: int = Field(default=100, ge=1, le=1000)
    source_metadata: dict[str, Any] = Field(default_factory=dict)
    encrypted_blob_ref: str | None = Field(default=None, max_length=255)


class SnapshotVerifyRequest(BaseModel):
    sample_size: int = Field(default=5, ge=1, le=100)


@router.post("/snapshots/import", status_code=201)
async def import_memory_snapshot_v2(
    req: SnapshotImportRequest,
    db: AsyncSession = Depends(get_db),
    agent_id: str = Depends(get_current_agent_id),
):
    agent_result = await db.execute(
        select(RegisteredAgent).where(RegisteredAgent.id == agent_id)
    )
    agent = agent_result.scalar_one_or_none()
    creator_id = agent.creator_id if agent else None
    try:
        return await memory_service.import_snapshot(
            db,
            agent_id=agent_id,
            creator_id=creator_id,
            source_type=req.source_type,
            label=req.label,
            records=req.records,
            chunk_size=req.chunk_size,
            source_metadata=req.source_metadata,
            encrypted_blob_ref=req.encrypted_blob_ref,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/snapshots/{snapshot_id}/verify")
async def verify_memory_snapshot_v2(
    snapshot_id: str,
    req: SnapshotVerifyRequest,
    db: AsyncSession = Depends(get_db),
    agent_id: str = Depends(get_current_agent_id),
):
    try:
        return await memory_service.verify_snapshot(
            db,
            snapshot_id=snapshot_id,
            agent_id=agent_id,
            sample_size=req.sample_size,
        )
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/snapshots/{snapshot_id}")
async def get_memory_snapshot_v2(
    snapshot_id: str,
    db: AsyncSession = Depends(get_db),
    agent_id: str = Depends(get_current_agent_id),
):
    try:
        return await memory_service.get_snapshot(
            db,
            snapshot_id=snapshot_id,
            agent_id=agent_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
