"""Express delivery: single-request purchase optimized for cached content.

Target: <100ms for cache-hit content.
"""

import time
from datetime import datetime, timezone

from fastapi import HTTPException
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from marketplace.models.transaction import Transaction
from marketplace.services.cache_service import content_cache, listing_cache
from marketplace.services.listing_service import get_listing, get_listing_content


async def express_buy(db: AsyncSession, listing_id: str, buyer_id: str) -> JSONResponse:
    """Execute full buy flow in one call, optimized for cached content."""
    start = time.monotonic()

    # 1. Get listing (cached or DB)
    listing = await get_listing(db, listing_id)
    if listing.status != "active":
        raise HTTPException(status_code=400, detail="Listing is not active")
    if listing.seller_id == buyer_id:
        raise HTTPException(status_code=400, detail="Cannot buy your own listing")

    # 2. Check if content was in cache before fetching
    was_cache_hit = content_cache.get(f"content:{listing.content_hash}") is not None

    # 3. Get content (cached or disk)
    content_bytes = get_listing_content(listing.content_hash)
    if content_bytes is None:
        raise HTTPException(status_code=404, detail="Content not found in storage")

    # 4. Create completed transaction record (collapsed state machine)
    now = datetime.now(timezone.utc)
    tx = Transaction(
        listing_id=listing.id,
        buyer_id=buyer_id,
        seller_id=listing.seller_id,
        amount_usdc=float(listing.price_usdc),
        status="completed",
        content_hash=listing.content_hash,
        delivered_hash=listing.content_hash,
        verification_status="verified",
        payment_tx_hash=f"express_{int(now.timestamp() * 1000)}",
        initiated_at=now,
        paid_at=now,
        delivered_at=now,
        verified_at=now,
        completed_at=now,
    )
    db.add(tx)

    # 5. Increment access count
    listing.access_count += 1

    await db.commit()
    await db.refresh(tx)

    elapsed_ms = (time.monotonic() - start) * 1000

    # 6. Broadcast WebSocket event
    try:
        from marketplace.main import broadcast_event
        import asyncio

        asyncio.ensure_future(
            broadcast_event(
                "express_purchase",
                {
                    "transaction_id": tx.id,
                    "listing_id": listing.id,
                    "title": listing.title,
                    "buyer_id": buyer_id,
                    "price_usdc": float(listing.price_usdc),
                    "delivery_ms": round(elapsed_ms, 1),
                    "cache_hit": was_cache_hit,
                },
            )
        )
    except Exception:
        pass  # Don't fail the purchase if broadcast fails

    return JSONResponse(
        content={
            "transaction_id": tx.id,
            "listing_id": listing.id,
            "content": content_bytes.decode("utf-8"),
            "content_hash": listing.content_hash,
            "price_usdc": float(listing.price_usdc),
            "seller_id": listing.seller_id,
            "delivery_ms": round(elapsed_ms, 1),
            "cache_hit": was_cache_hit,
        },
        headers={"X-Delivery-Ms": str(round(elapsed_ms, 1))},
    )
