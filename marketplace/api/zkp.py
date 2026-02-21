"""ZKP endpoints: pre-purchase verification without revealing content."""

import json
import logging

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from marketplace.database import get_db
from marketplace.services import zkp_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/zkp", tags=["zero-knowledge-proofs"])


class VerifyRequest(BaseModel):
    keywords: list[str] | None = Field(default=None, max_length=20)
    schema_has_fields: list[str] | None = Field(default=None, max_length=50)
    min_size: int | None = Field(default=None, ge=0)
    min_quality: float | None = Field(default=None, ge=0.0, le=1.0)


@router.get("/{listing_id}/proofs")
async def get_proofs(
    listing_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Get all zero-knowledge proofs for a listing."""
    proofs = await zkp_service.get_proofs(db, listing_id)
    return {
        "listing_id": listing_id,
        "proofs": [
            {
                "id": p.id,
                "proof_type": p.proof_type,
                "commitment": p.commitment,
                "public_inputs": json.loads(p.public_inputs),
                "created_at": p.created_at.isoformat() if p.created_at else None,
            }
            for p in proofs
        ],
        "count": len(proofs),
    }


@router.post("/{listing_id}/verify")
async def verify_listing(
    listing_id: str,
    req: VerifyRequest,
    db: AsyncSession = Depends(get_db),
):
    """Pre-purchase verification: check claims without seeing content.

    Pass any combination of checks:
    - keywords: bloom filter keyword presence
    - schema_has_fields: verify JSON field names exist
    - min_size: verify content size >= N bytes
    - min_quality: verify quality score >= N
    """
    return await zkp_service.verify_listing(
        db, listing_id,
        keywords=req.keywords,
        schema_has_fields=req.schema_has_fields,
        min_size=req.min_size,
        min_quality=req.min_quality,
    )


@router.get("/{listing_id}/bloom-check")
async def bloom_check(
    listing_id: str,
    word: str = Query(..., min_length=1, max_length=100),
    db: AsyncSession = Depends(get_db),
):
    """Quick single-word bloom filter check.

    Returns whether the word is probably present in the listing content.
    Bloom filters never give false negatives but may give false positives.
    """
    try:
        return await zkp_service.bloom_check_word(db, listing_id, word)
    except Exception:
        logger.exception("Bloom check failed for listing=%s word=%s", listing_id, word)
        return {
            "listing_id": listing_id,
            "word": word,
            "error": "Internal server error",
            "probably_present": False,
        }
