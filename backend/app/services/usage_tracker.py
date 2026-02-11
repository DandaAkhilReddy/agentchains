"""Lightweight API usage tracker — estimates costs and logs to DB."""

import logging
import uuid
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.repositories.usage_repo import UsageLogRepository

logger = logging.getLogger(__name__)

# Pricing estimates (USD per unit) — OpenAI pricing as of early 2026
PRICING = {
    "openai": {
        "input_per_1m": 0.15,   # GPT-4o-mini input
        "output_per_1m": 0.60,  # GPT-4o-mini output
    },
    "doc_intel": {
        "per_page": 0.0015,     # ~$1.50/1000 pages
    },
    "blob_storage": {
        "per_operation": 0.000001,  # ~$0.01/10K ops
    },
    "translator": {
        "per_1m_chars": 10.0,   # $10/1M characters
    },
    "tts": {
        "per_1m_chars": 16.0,   # $16/1M characters (neural)
    },
}


def estimate_openai_cost(tokens_in: int, tokens_out: int) -> float:
    cost_in = (tokens_in / 1_000_000) * PRICING["openai"]["input_per_1m"]
    cost_out = (tokens_out / 1_000_000) * PRICING["openai"]["output_per_1m"]
    return round(cost_in + cost_out, 6)


def estimate_doc_intel_cost(pages: int = 1) -> float:
    return round(pages * PRICING["doc_intel"]["per_page"], 6)


def estimate_blob_cost() -> float:
    return PRICING["blob_storage"]["per_operation"]


async def track_usage(
    db: AsyncSession,
    service: str,
    operation: str,
    user_id: uuid.UUID | None = None,
    tokens_input: int | None = None,
    tokens_output: int | None = None,
    estimated_cost: float = 0,
    metadata: dict | None = None,
) -> None:
    """Fire-and-forget usage logging. Errors are logged but never raised."""
    try:
        repo = UsageLogRepository(db)
        await repo.log(
            service=service,
            operation=operation,
            user_id=user_id,
            tokens_input=tokens_input,
            tokens_output=tokens_output,
            estimated_cost=estimated_cost,
            metadata=metadata,
        )
    except Exception as e:
        logger.warning(f"Failed to log usage: {e}")
