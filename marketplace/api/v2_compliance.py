"""Compliance API endpoints -- GDPR data subject rights (v2 canonical API).

Provides endpoints for:
- Data export requests (GDPR Article 20)
- Data deletion requests (GDPR Article 17 -- right to erasure)
- Consent management (GDPR Article 7)
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from marketplace.core.auth import get_current_agent_id
from marketplace.database import get_db

router = APIRouter(prefix="/compliance", tags=["compliance"])

# ---------------------------------------------------------------------------
# In-memory stores (replace with DB-backed persistence in production)
# ---------------------------------------------------------------------------

_export_jobs: dict[str, dict] = {}
_deletion_requests: dict[str, dict] = {}
_consent_records: dict[str, list[dict]] = {}  # agent_id -> [consent records]


# ---------------------------------------------------------------------------
# Request / response models
# ---------------------------------------------------------------------------

class DataExportRequest(BaseModel):
    agent_id: Optional[str] = Field(
        default=None,
        description="Target agent ID for export. Defaults to the authenticated agent.",
    )
    format: str = Field(default="json", description="Export format: json or csv")
    include_transactions: bool = Field(default=True)
    include_listings: bool = Field(default=True)
    include_reputation: bool = Field(default=True)


class DataExportStatusResponse(BaseModel):
    job_id: str
    status: str
    agent_id: str
    format: str
    created_at: str
    completed_at: Optional[str] = None
    download_url: Optional[str] = None


class DataDeletionRequest(BaseModel):
    agent_id: Optional[str] = Field(
        default=None,
        description="Target agent ID for deletion. Defaults to the authenticated agent.",
    )
    reason: str = Field(default="user_request", description="Reason for deletion request")
    soft_delete: bool = Field(
        default=True,
        description="Soft-delete (anonymize) if true, hard-delete if false",
    )


class DataDeletionStatusResponse(BaseModel):
    request_id: str
    status: str
    agent_id: str
    reason: str
    soft_delete: bool
    created_at: str
    completed_at: Optional[str] = None


class ConsentRecord(BaseModel):
    consent_type: str = Field(
        ...,
        description="Type of consent, e.g. 'data_processing', 'marketing', 'analytics'",
    )
    granted: bool = Field(..., description="True to grant consent, False to revoke")
    purpose: str = Field(default="", description="Description of the consent purpose")


class ConsentRecordResponse(BaseModel):
    id: str
    agent_id: str
    consent_type: str
    granted: bool
    purpose: str
    recorded_at: str


# ---------------------------------------------------------------------------
# Data export endpoints
# ---------------------------------------------------------------------------

@router.post("/data-export", response_model=DataExportStatusResponse)
async def request_data_export(
    req: DataExportRequest,
    db: AsyncSession = Depends(get_db),
    agent_id: str = Depends(get_current_agent_id),
):
    """Request a GDPR data export for the authenticated agent.

    Creates an asynchronous export job and returns the ``job_id``
    which can be polled for status and download.
    """
    target_agent_id = req.agent_id or agent_id
    if target_agent_id != agent_id:
        raise HTTPException(
            status_code=403,
            detail="You can only request data exports for your own account",
        )

    job_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()

    _export_jobs[job_id] = {
        "job_id": job_id,
        "status": "processing",
        "agent_id": target_agent_id,
        "format": req.format,
        "include_transactions": req.include_transactions,
        "include_listings": req.include_listings,
        "include_reputation": req.include_reputation,
        "created_at": now,
        "completed_at": None,
        "download_url": None,
    }

    # In production this would enqueue a background task.
    # For now, mark as completed immediately with a placeholder URL.
    _export_jobs[job_id]["status"] = "completed"
    _export_jobs[job_id]["completed_at"] = now
    _export_jobs[job_id]["download_url"] = f"/api/v2/compliance/data-export/{job_id}/download"

    return DataExportStatusResponse(**{
        k: _export_jobs[job_id][k]
        for k in DataExportStatusResponse.model_fields
    })


@router.get("/data-export/{job_id}", response_model=DataExportStatusResponse)
async def get_data_export_status(
    job_id: str,
    agent_id: str = Depends(get_current_agent_id),
):
    """Get the status of a data export job and its download link when ready."""
    job = _export_jobs.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Export job not found")

    if job["agent_id"] != agent_id:
        raise HTTPException(
            status_code=403,
            detail="You do not have access to this export job",
        )

    return DataExportStatusResponse(**{
        k: job[k] for k in DataExportStatusResponse.model_fields
    })


# ---------------------------------------------------------------------------
# Data deletion endpoints
# ---------------------------------------------------------------------------

@router.post("/data-deletion", response_model=DataDeletionStatusResponse)
async def request_data_deletion(
    req: DataDeletionRequest,
    db: AsyncSession = Depends(get_db),
    agent_id: str = Depends(get_current_agent_id),
):
    """Request right-to-deletion (GDPR Article 17) for the authenticated agent.

    Creates an asynchronous deletion request and returns the ``request_id``
    which can be polled for status.
    """
    target_agent_id = req.agent_id or agent_id
    if target_agent_id != agent_id:
        raise HTTPException(
            status_code=403,
            detail="You can only request data deletion for your own account",
        )

    request_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()

    _deletion_requests[request_id] = {
        "request_id": request_id,
        "status": "pending",
        "agent_id": target_agent_id,
        "reason": req.reason,
        "soft_delete": req.soft_delete,
        "created_at": now,
        "completed_at": None,
    }

    return DataDeletionStatusResponse(**{
        k: _deletion_requests[request_id][k]
        for k in DataDeletionStatusResponse.model_fields
    })


@router.get("/data-deletion/{request_id}", response_model=DataDeletionStatusResponse)
async def get_data_deletion_status(
    request_id: str,
    agent_id: str = Depends(get_current_agent_id),
):
    """Get the status of a data deletion request."""
    request = _deletion_requests.get(request_id)
    if request is None:
        raise HTTPException(status_code=404, detail="Deletion request not found")

    if request["agent_id"] != agent_id:
        raise HTTPException(
            status_code=403,
            detail="You do not have access to this deletion request",
        )

    return DataDeletionStatusResponse(**{
        k: request[k] for k in DataDeletionStatusResponse.model_fields
    })


# ---------------------------------------------------------------------------
# Consent management endpoints
# ---------------------------------------------------------------------------

@router.get("/consent", response_model=list[ConsentRecordResponse])
async def get_consent_records(
    agent_id: str = Depends(get_current_agent_id),
):
    """Get all consent records for the authenticated agent."""
    records = _consent_records.get(agent_id, [])
    return [ConsentRecordResponse(**r) for r in records]


@router.post("/consent", response_model=ConsentRecordResponse)
async def record_consent(
    req: ConsentRecord,
    agent_id: str = Depends(get_current_agent_id),
):
    """Record a consent grant or revocation for the authenticated agent.

    If a record for the same ``consent_type`` already exists, it is updated
    with the new ``granted`` value.
    """
    now = datetime.now(timezone.utc).isoformat()
    consent_id = str(uuid.uuid4())

    record = {
        "id": consent_id,
        "agent_id": agent_id,
        "consent_type": req.consent_type,
        "granted": req.granted,
        "purpose": req.purpose,
        "recorded_at": now,
    }

    # Upsert: replace existing record for the same consent_type
    agent_records = _consent_records.setdefault(agent_id, [])
    existing_idx = next(
        (i for i, r in enumerate(agent_records) if r["consent_type"] == req.consent_type),
        None,
    )
    if existing_idx is not None:
        record["id"] = agent_records[existing_idx]["id"]
        agent_records[existing_idx] = record
    else:
        agent_records.append(record)

    return ConsentRecordResponse(**record)
