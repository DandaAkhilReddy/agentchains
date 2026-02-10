from pydantic import BaseModel


class ExpressDeliveryResponse(BaseModel):
    transaction_id: str
    listing_id: str
    content: str
    content_hash: str
    price_usdc: float
    seller_id: str
    delivery_ms: float
    cache_hit: bool
