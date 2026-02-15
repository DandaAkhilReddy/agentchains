"""Schemas for dual-layer developer builder + end-user buyer APIs."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class EndUserRegisterRequest(BaseModel):
    email: str = Field(..., min_length=5, max_length=255)
    password: str = Field(..., min_length=8, max_length=128)


class EndUserLoginRequest(BaseModel):
    email: str = Field(..., min_length=5, max_length=255)
    password: str = Field(..., min_length=1, max_length=128)


class EndUserResponse(BaseModel):
    id: str
    email: str
    status: str
    managed_agent_id: str
    created_at: datetime
    updated_at: datetime
    last_login_at: datetime | None = None


class EndUserAuthResponse(BaseModel):
    user: EndUserResponse
    token: str


class UserStreamTokenResponse(BaseModel):
    user_id: str
    stream_token: str
    expires_in_seconds: int
    expires_at: str
    ws_url: str
    allowed_topics: list[str]


class MarketListingResponse(BaseModel):
    id: str
    title: str
    description: str
    category: str
    seller_id: str
    seller_name: str
    price_usd: float
    currency: str
    trust_status: str
    trust_score: int
    requires_unverified_confirmation: bool
    freshness_at: datetime
    created_at: datetime


class MarketListingListResponse(BaseModel):
    total: int
    page: int
    page_size: int
    results: list[MarketListingResponse]


class MarketOrderCreateRequest(BaseModel):
    listing_id: str
    payment_method: str = Field(default="simulated", pattern="^(token|fiat|simulated)$")
    allow_unverified: bool = False


class MarketOrderResponse(BaseModel):
    id: str
    listing_id: str
    tx_id: str
    status: str
    amount_usd: float
    fee_usd: float
    payout_usd: float
    trust_status: str
    warning_acknowledged: bool
    created_at: datetime
    content: str | None = None


class MarketOrderListResponse(BaseModel):
    total: int
    page: int
    page_size: int
    orders: list[MarketOrderResponse]


class DeveloperProfileUpdateRequest(BaseModel):
    bio: str = Field(default="", max_length=5000)
    links: list[str] = Field(default_factory=list)
    specialties: list[str] = Field(default_factory=list)
    featured_flag: bool = False


class DeveloperProfileResponse(BaseModel):
    creator_id: str
    bio: str
    links: list[str]
    specialties: list[str]
    featured_flag: bool
    created_at: datetime
    updated_at: datetime


class BuilderTemplateResponse(BaseModel):
    key: str
    name: str
    description: str
    default_category: str
    suggested_price_usd: float


class BuilderProjectCreateRequest(BaseModel):
    template_key: str
    title: str = Field(..., min_length=1, max_length=255)
    config: dict = Field(default_factory=dict)


class BuilderProjectResponse(BaseModel):
    id: str
    creator_id: str
    template_key: str
    title: str
    status: str
    published_listing_id: str | None = None
    created_at: datetime
    updated_at: datetime


class BuilderProjectListResponse(BaseModel):
    total: int
    projects: list[BuilderProjectResponse]


class BuilderPublishResponse(BaseModel):
    project: BuilderProjectResponse
    listing_id: str


class FeaturedCollectionResponse(BaseModel):
    key: str
    title: str
    description: str
    listings: list[MarketListingResponse]
