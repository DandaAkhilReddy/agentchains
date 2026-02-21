"""Compliance API endpoints — GDPR data subject rights (v2 canonical API)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from marketplace.database import get_db
from marketplace.services.compliance_service import (
    delete_agent_data,
    export_agent_data,
    get_data_processing_record,
)

router = APIRouter(prefix="/compliance", tags=["compliance"])


@router.get("/export/{agent_id}")
async def compliance_export(
    agent_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Export all data associated with an agent (GDPR Article 20).

    Returns a portable structured dictionary of all personal data
    related to the specified agent, including profile, listings,
    and transaction history.
    """
    return await export_agent_data(db, agent_id)


@router.delete("/delete/{agent_id}")
async def compliance_delete(
    agent_id: str,
    soft_delete: bool = Query(True, description="Soft-delete (anonymize) if true, hard-delete if false"),
    db: AsyncSession = Depends(get_db),
):
    """Delete all data associated with an agent (GDPR Article 17).

    By default performs a soft delete (anonymization). Set
    soft_delete=false for permanent hard deletion.
    """
    return await delete_agent_data(db, agent_id, soft_delete=soft_delete)


@router.get("/processing-record/{agent_id}")
async def compliance_processing_record(
    agent_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Get a record of how an agent's data is processed (GDPR Article 30).

    Returns data categories, processing purposes, retention periods,
    and data recipients in compliance with GDPR record-keeping
    requirements.
    """
    return await get_data_processing_record(db, agent_id)
