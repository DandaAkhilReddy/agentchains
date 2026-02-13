from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from marketplace.core.auth import get_current_agent_id
from marketplace.database import get_db
from marketplace.schemas.transaction import (
    TransactionConfirmPaymentRequest,
    TransactionDeliverRequest,
    TransactionInitiateRequest,
    TransactionInitiateResponse,
    TransactionListResponse,
    TransactionResponse,
    PaymentDetails,
)
from marketplace.services import transaction_service

router = APIRouter(prefix="/transactions", tags=["transactions"])


@router.post("/initiate", response_model=TransactionInitiateResponse, status_code=201)
async def initiate_transaction(
    req: TransactionInitiateRequest,
    db: AsyncSession = Depends(get_db),
    current_agent: str = Depends(get_current_agent_id),
):
    result = await transaction_service.initiate_transaction(db, req.listing_id, current_agent)
    return TransactionInitiateResponse(
        transaction_id=result["transaction_id"],
        status=result["status"],
        amount_usdc=result["amount_usdc"],
        payment_details=PaymentDetails(**result["payment_details"]),
        content_hash=result["content_hash"],
    )


@router.post("/{tx_id}/confirm-payment", response_model=TransactionResponse)
async def confirm_payment(
    tx_id: str,
    req: TransactionConfirmPaymentRequest,
    db: AsyncSession = Depends(get_db),
    current_agent: str = Depends(get_current_agent_id),
):
    tx = await transaction_service.confirm_payment(
        db, tx_id, req.payment_signature, req.payment_tx_hash
    )
    return _tx_to_response(tx)


@router.post("/{tx_id}/deliver", response_model=TransactionResponse)
async def deliver_content(
    tx_id: str,
    req: TransactionDeliverRequest,
    db: AsyncSession = Depends(get_db),
    current_agent: str = Depends(get_current_agent_id),
):
    tx = await transaction_service.deliver_content(db, tx_id, req.content, current_agent)
    return _tx_to_response(tx)


@router.post("/{tx_id}/verify", response_model=TransactionResponse)
async def verify_delivery(
    tx_id: str,
    db: AsyncSession = Depends(get_db),
    current_agent: str = Depends(get_current_agent_id),
):
    tx = await transaction_service.verify_delivery(db, tx_id, current_agent)
    return _tx_to_response(tx)


@router.get("/{tx_id}", response_model=TransactionResponse)
async def get_transaction(
    tx_id: str,
    db: AsyncSession = Depends(get_db),
    current_agent: str = Depends(get_current_agent_id),
):
    tx = await transaction_service.get_transaction(db, tx_id)
    return _tx_to_response(tx)


@router.get("", response_model=TransactionListResponse)
async def list_transactions(
    status: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_agent: str = Depends(get_current_agent_id),
):
    txns, total = await transaction_service.list_transactions(
        db, current_agent, status, page, page_size
    )
    return TransactionListResponse(
        total=total,
        page=page,
        page_size=page_size,
        transactions=[_tx_to_response(t) for t in txns],
    )


def _tx_to_response(tx) -> TransactionResponse:
    return TransactionResponse(
        id=tx.id,
        listing_id=tx.listing_id,
        buyer_id=tx.buyer_id,
        seller_id=tx.seller_id,
        amount_usdc=float(tx.amount_usdc),
        status=tx.status,
        payment_tx_hash=tx.payment_tx_hash,
        payment_network=tx.payment_network,
        content_hash=tx.content_hash,
        delivered_hash=tx.delivered_hash,
        verification_status=tx.verification_status,
        error_message=tx.error_message,
        initiated_at=tx.initiated_at,
        paid_at=tx.paid_at,
        delivered_at=tx.delivered_at,
        verified_at=tx.verified_at,
        completed_at=tx.completed_at,
        payment_method=tx.payment_method or "simulated",
    )
