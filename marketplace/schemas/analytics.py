"""Pydantic schemas for the Analytics API."""

from datetime import datetime
from pydantic import BaseModel


class TrendingQueryResponse(BaseModel):
    query_pattern: str
    category: str | None = None
    search_count: int
    unique_requesters: int
    velocity: float
    fulfillment_rate: float
    last_searched_at: datetime


class TrendingResponse(BaseModel):
    time_window_hours: int
    trends: list[TrendingQueryResponse]


class DemandGapResponse(BaseModel):
    query_pattern: str
    category: str | None = None
    search_count: int
    unique_requesters: int
    avg_max_price: float | None = None
    fulfillment_rate: float
    first_searched_at: datetime


class DemandGapsResponse(BaseModel):
    gaps: list[DemandGapResponse]


class OpportunityResponse(BaseModel):
    id: str
    query_pattern: str
    category: str | None = None
    estimated_revenue_usdc: float
    search_velocity: float
    competing_listings: int
    urgency_score: float
    created_at: datetime


class OpportunitiesResponse(BaseModel):
    opportunities: list[OpportunityResponse]


class EarningsTimelineEntry(BaseModel):
    date: str
    earned: float
    spent: float


class EarningsResponse(BaseModel):
    agent_id: str
    total_earned_usdc: float
    total_spent_usdc: float
    net_revenue_usdc: float
    earnings_by_category: dict[str, float]
    earnings_timeline: list[EarningsTimelineEntry]


class AgentStatsResponse(BaseModel):
    agent_id: str
    agent_name: str
    unique_buyers_served: int
    total_listings_created: int
    total_cache_hits: int
    category_count: int
    categories: list[str]
    total_earned_usdc: float
    total_spent_usdc: float
    demand_gaps_filled: int
    avg_listing_quality: float
    total_data_bytes: int
    helpfulness_score: float
    helpfulness_rank: int | None = None
    earnings_rank: int | None = None
    primary_specialization: str | None = None
    specialization_tags: list[str] = []
    last_calculated_at: datetime


class MultiLeaderboardEntry(BaseModel):
    rank: int
    agent_id: str
    agent_name: str
    primary_score: float
    secondary_label: str
    total_transactions: int
    helpfulness_score: float | None = None
    total_earned_usdc: float | None = None


class MultiLeaderboardResponse(BaseModel):
    board_type: str
    entries: list[MultiLeaderboardEntry]
