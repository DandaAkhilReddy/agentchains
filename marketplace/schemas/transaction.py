from datetime import datetime

from pydantic import BaseModel, Field


class TransactionInitiateRequest(BaseModel):
    listing_id: str


class PaymentDetails(BaseModel):
    pay_to_address: str
    network: str
    asset: str = "USDC"
    amount_usdc: float
    facilitator_url: str
    simulated: bool = False


class TransactionInitiateResponse(BaseModel):
    transaction_id: str
    status: str
    amount_usdc: float
    payment_details: PaymentDetails
    content_hash: str


class TransactionConfirmPaymentRequest(BaseModel):
    payment_signature: str = ""  # x402 payment signature
    payment_tx_hash: str = ""  # Direct blockchain tx hash


class TransactionDeliverRequest(BaseModel):
    content: str  # The actual data being delivered (base64 or JSON)


class TransactionVerifyRequest(BaseModel):
    transaction_id: str
    content: str
    expected_hash: str


class TransactionResponse(BaseModel):
    id: str
    listing_id: str
    buyer_id: str
    seller_id: str
    amount_usdc: float
    status: str
    payment_tx_hash: str | None = None
    payment_network: str | None = None
    content_hash: str
    delivered_hash: str | None = None
    verification_status: str
    error_message: str | None = None
    initiated_at: datetime
    paid_at: datetime | None = None
    delivered_at: datetime | None = None
    verified_at: datetime | None = None
    completed_at: datetime | None = None
    payment_method: str = "simulated"

    model_config = {"from_attributes": True}


class TransactionListResponse(BaseModel):
    total: int
    page: int
    page_size: int
    transactions: list[TransactionResponse]
