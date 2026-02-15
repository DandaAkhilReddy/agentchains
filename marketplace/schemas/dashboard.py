"""Schemas for admin and role-based dashboard responses."""

from __future__ import annotations

from datetime import datetime
from pydantic import BaseModel


class SavingsSummary(BaseModel):
    money_saved_for_others_usd: float
    fresh_cost_estimate_total_usd: float


class AgentDashboardResponse(BaseModel):
    agent_id: str
    money_received_usd: float
    money_spent_usd: float
    info_used_count: int
    other_agents_served_count: int
    data_served_bytes: int
    savings: SavingsSummary
    trust_status: str
    trust_tier: str
    trust_score: int
    updated_at: datetime | None = None


class CreatorDashboardV2Response(BaseModel):
    creator_id: str
    creator_balance_usd: float
    creator_total_earned_usd: float
    total_agent_earnings_usd: float
    total_agent_spent_usd: float
    total_agents: int
    active_agents: int
    money_saved_for_others_usd: float
    data_served_bytes: int
    updated_at: datetime | None = None


class AgentPublicDashboardResponse(BaseModel):
    agent_id: str
    agent_name: str
    money_received_usd: float
    info_used_count: int
    other_agents_served_count: int
    data_served_bytes: int
    money_saved_for_others_usd: float
    trust_status: str
    trust_tier: str
    trust_score: int
    updated_at: datetime | None = None


class AdminOverviewResponse(BaseModel):
    environment: str
    total_agents: int
    active_agents: int
    total_listings: int
    active_listings: int
    total_transactions: int
    completed_transactions: int
    platform_volume_usd: float
    trust_weighted_revenue_usd: float
    updated_at: datetime


class AdminFinanceResponse(BaseModel):
    platform_volume_usd: float
    completed_transaction_count: int
    payout_pending_count: int
    payout_pending_usd: float
    payout_processing_count: int
    payout_processing_usd: float
    top_sellers_by_revenue: list[dict]
    updated_at: datetime


class AdminUsageResponse(BaseModel):
    info_used_count: int
    data_served_bytes: int
    unique_buyers_count: int
    unique_sellers_count: int
    money_saved_for_others_usd: float
    category_breakdown: list[dict]
    updated_at: datetime


class AdminAgentRow(BaseModel):
    agent_id: str
    agent_name: str
    status: str
    trust_status: str
    trust_tier: str
    trust_score: int
    money_received_usd: float
    info_used_count: int
    other_agents_served_count: int
    data_served_bytes: int


class AdminAgentsResponse(BaseModel):
    total: int
    page: int
    page_size: int
    entries: list[AdminAgentRow]


class AdminSecurityEvent(BaseModel):
    id: str
    event_type: str
    severity: str
    agent_id: str | None = None
    creator_id: str | None = None
    ip_address: str | None = None
    details: dict
    created_at: datetime


class AdminSecurityEventsResponse(BaseModel):
    total: int
    page: int
    page_size: int
    events: list[AdminSecurityEvent]


class OpenMarketAnalyticsResponse(BaseModel):
    generated_at: datetime
    total_agents: int
    total_listings: int
    total_completed_transactions: int
    platform_volume_usd: float
    total_money_saved_usd: float
    top_agents_by_revenue: list[dict]
    top_agents_by_usage: list[dict]
    top_categories_by_usage: list[dict]
