from datetime import datetime

from pydantic import BaseModel, Field


class ListingCreateRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    description: str = ""
    category: str = Field(..., pattern="^(web_search|code_analysis|document_summary|api_response|computation)$")
    content: str = Field(..., min_length=1)  # Base64 or JSON string
    price_usdc: float = Field(..., gt=0, le=1000)
    price_usd: float | None = Field(default=None, gt=0, le=1000)
    metadata: dict = {}
    tags: list[str] = []
    quality_score: float = Field(default=0.5, ge=0, le=1)


class ListingUpdateRequest(BaseModel):
    title: str | None = None
    description: str | None = None
    price_usdc: float | None = Field(default=None, gt=0, le=1000)
    price_usd: float | None = Field(default=None, gt=0, le=1000)
    tags: list[str] | None = None
    quality_score: float | None = Field(default=None, ge=0, le=1)
    status: str | None = None


class SellerSummary(BaseModel):
    id: str
    name: str
    reputation_score: float | None = None


class ListingResponse(BaseModel):
    id: str
    seller_id: str
    seller: SellerSummary | None = None
    title: str
    description: str
    category: str
    content_hash: str
    content_size: int
    content_type: str
    price_usdc: float
    price_usd: float | None = None
    currency: str
    metadata: dict
    tags: list[str]
    quality_score: float
    freshness_at: datetime
    expires_at: datetime | None = None
    status: str
    trust_status: str = "pending_verification"
    trust_score: int = 0
    verification_summary: dict = {}
    provenance: dict = {}
    access_count: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ListingListResponse(BaseModel):
    total: int
    page: int
    page_size: int
    results: list[ListingResponse]
