from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from marketplace.models.verification import VerificationRecord
from marketplace.storage.hashfs import HashFS
from marketplace.services.storage_service import get_storage


async def verify_content(
    db: AsyncSession,
    transaction_id: str,
    content: bytes,
    expected_hash: str,
) -> dict:
    """Verify delivered content matches expected hash. Returns verification result."""
    storage = get_storage()
    actual_hash = storage.compute_hash(content)
    matches = storage.verify(content, expected_hash)

    record = VerificationRecord(
        transaction_id=transaction_id,
        expected_hash=expected_hash,
        actual_hash=actual_hash,
        matches=1 if matches else 0,
    )
    db.add(record)
    await db.commit()

    return {
        "verified": matches,
        "expected_hash": expected_hash,
        "actual_hash": actual_hash,
        "transaction_id": transaction_id,
    }
