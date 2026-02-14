"""Express delivery: single-request purchase optimized for cached content.

Target: <100ms for cache-hit content.
"""

import time
import uuid
from datetime import datetime, timezone

from fastapi import HTTPException
from fastapi.responses import JSONResponse
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from marketplace.core.async_tasks import fire_and_forget
from marketplace.models.listing import DataListing
from marketplace.models.transaction import Transaction
from marketplace.services.cache_service import content_cache
from marketplace.services.cdn_service import get_content as cdn_get_content
from marketplace.services.listing_service import get_listing


async def express_buy(db: AsyncSession, listing_id: str, buyer_id: str, payment_method: str = "token") -> JSONResponse:
    """Execute full buy flow in one call, optimized for cached content."""
    start = time.monotonic()

    # 1. Get listing (cached or DB) — read-only, no merge needed
    listing = await get_listing(db, listing_id)

    if listing.status != "active":
        raise HTTPException(status_code=400, detail="Listing is not active")
    if listing.seller_id == buyer_id:
        raise HTTPException(status_code=400, detail="Cannot buy your own listing")

    # 2. Capture scalar values (safe even if listing is detached/cached)
    lid = listing.id
    content_hash = listing.content_hash
    price_usdc = float(listing.price_usdc)
    seller_id = listing.seller_id
    listing_title = listing.title

    # 3. Check if content was in cache before fetching
    was_cache_hit = content_cache.get(f"content:{content_hash}") is not None

    # 4. Get content via CDN (hot -> warm -> cold)
    content_bytes = await cdn_get_content(content_hash)
    if content_bytes is None:
        raise HTTPException(status_code=404, detail="Content not found in storage")

    # 5. Balance payment — pre-generate tx_id for idempotency
    tx_id = str(uuid.uuid4())
    token_result = None
    cost_usd = None
    if payment_method == "token":
        try:
            from marketplace.services.token_service import debit_for_purchase
            token_result = await debit_for_purchase(
                db, buyer_id, seller_id, price_usdc, tx_id
            )
            cost_usd = token_result["amount_usd"]
        except Exception as e:
            raise HTTPException(status_code=402, detail=f"Insufficient balance: {e}")

    # 6. Create completed transaction record (collapsed state machine)
    now = datetime.now(timezone.utc)
    tx = Transaction(
        id=tx_id,
        listing_id=lid,
        buyer_id=buyer_id,
        seller_id=seller_id,
        amount_usdc=price_usdc,
        status="completed",
        content_hash=content_hash,
        delivered_hash=content_hash,
        verification_status="verified",
        payment_tx_hash=f"express_{int(now.timestamp() * 1000)}",
        payment_method=payment_method,
        initiated_at=now,
        paid_at=now,
        delivered_at=now,
        verified_at=now,
        completed_at=now,
    )
    db.add(tx)

    # 7. Increment access count via SQL UPDATE (avoids merge/detached issues)
    await db.execute(
        update(DataListing)
        .where(DataListing.id == lid)
        .values(access_count=DataListing.access_count + 1)
    )

    await db.commit()
    await db.refresh(tx)

    elapsed_ms = (time.monotonic() - start) * 1000

    # 8. Broadcast WebSocket event (fire-and-forget)
    try:
        from marketplace.main import broadcast_event

        fire_and_forget(
            broadcast_event(
                "express_purchase",
                {
                    "transaction_id": tx.id,
                    "listing_id": lid,
                    "title": listing_title,
                    "buyer_id": buyer_id,
                    "price_usdc": price_usdc,
                    "cost_usd": cost_usd,
                    "payment_method": payment_method,
                    "buyer_balance": token_result["buyer_balance"] if token_result else None,
                    "delivery_ms": round(elapsed_ms, 1),
                    "cache_hit": was_cache_hit,
                },
            ),
            task_name="broadcast_express_purchase",
        )
    except Exception:
        pass  # Don't fail the purchase if broadcast fails

    return JSONResponse(
        content={
            "transaction_id": tx.id,
            "listing_id": lid,
            "content": content_bytes.decode("utf-8"),
            "content_hash": content_hash,
            "price_usdc": price_usdc,
            "cost_usd": cost_usd,
            "payment_method": payment_method,
            "buyer_balance": token_result["buyer_balance"] if token_result else None,
            "seller_id": seller_id,
            "delivery_ms": round(elapsed_ms, 1),
            "cache_hit": was_cache_hit,
        },
        headers={"X-Delivery-Ms": str(round(elapsed_ms, 1))},
    )
