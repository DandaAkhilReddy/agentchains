"""Public market browsing and end-user order endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from marketplace.core.user_auth import get_current_user_id
from marketplace.database import get_db
from marketplace.schemas.dual_layer import (
    FeaturedCollectionResponse,
    MarketListingListResponse,
    MarketListingResponse,
    MarketOrderCreateRequest,
    MarketOrderListResponse,
    MarketOrderResponse,
)
from marketplace.services import dual_layer_service

router = APIRouter(prefix="/market", tags=["market-v2"])


@router.get("/listings", response_model=MarketListingListResponse)
async def list_market_listings_v2(
    q: str | None = Query(default=None),
    category: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    listings, total = await dual_layer_service.list_market_listings(
        db,
        q=q,
        category=category,
        page=page,
        page_size=page_size,
    )
    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "results": listings,
    }


@router.get("/listings/{listing_id}", response_model=MarketListingResponse)
async def get_market_listing_v2(
    listing_id: str,
    db: AsyncSession = Depends(get_db),
):
    try:
        return await dual_layer_service.get_market_listing(db, listing_id=listing_id)
    except Exception as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/orders", response_model=MarketOrderResponse, status_code=201)
async def create_market_order_v2(
    req: MarketOrderCreateRequest,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    try:
        return await dual_layer_service.create_market_order(
            db,
            user_id=user_id,
            listing_id=req.listing_id,
            payment_method=req.payment_method,
            allow_unverified=req.allow_unverified,
        )
    except ValueError as exc:
        detail = str(exc)
        if "allow_unverified" in detail:
            raise HTTPException(status_code=409, detail=detail) from exc
        raise HTTPException(status_code=400, detail=detail) from exc


@router.get("/orders/me", response_model=MarketOrderListResponse)
async def list_market_orders_me_v2(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    orders, total = await dual_layer_service.list_market_orders_for_user(
        db,
        user_id=user_id,
        page=page,
        page_size=page_size,
    )
    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "orders": orders,
    }


@router.get("/orders/{order_id}", response_model=MarketOrderResponse)
async def get_market_order_v2(
    order_id: str,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    try:
        return await dual_layer_service.get_market_order_for_user(
            db,
            user_id=user_id,
            order_id=order_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/collections/featured", response_model=list[FeaturedCollectionResponse])
async def get_featured_collections_v2(
    db: AsyncSession = Depends(get_db),
):
    return await dual_layer_service.get_featured_collections(db)
