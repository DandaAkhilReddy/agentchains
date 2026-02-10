from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from marketplace.database import get_db
from marketplace.schemas.transaction import TransactionVerifyRequest
from marketplace.services import verification_service

router = APIRouter(tags=["verification"])


@router.post("/verify")
async def verify_content(
    req: TransactionVerifyRequest,
    db: AsyncSession = Depends(get_db),
):
    content_bytes = req.content.encode("utf-8")
    result = await verification_service.verify_content(
        db, req.transaction_id, content_bytes, req.expected_hash
    )
    return result
