export interface SavingsSummary {
  money_saved_for_others_usd: number;
  fresh_cost_estimate_total_usd: number;
}

export interface AgentDashboardV2 {
  agent_id: string;
  money_received_usd: number;
  money_spent_usd: number;
  info_used_count: number;
  other_agents_served_count: number;
  data_served_bytes: number;
  savings: SavingsSummary;
  trust_status: string;
  trust_tier: string;
  trust_score: number;
  updated_at: string | null;
}

export interface CreatorDashboardV2 {
  creator_id: string;
  creator_balance_usd: number;
  creator_total_earned_usd: number;
  total_agent_earnings_usd: number;
  total_agent_spent_usd: number;
  total_agents: number;
  active_agents: number;
  money_saved_for_others_usd: number;
  data_served_bytes: number;
  updated_at: string | null;
}

export interface AgentPublicDashboardV2 {
  agent_id: string;
  agent_name: string;
  money_received_usd: number;
  info_used_count: number;
  other_agents_served_count: number;
  data_served_bytes: number;
  money_saved_for_others_usd: number;
  trust_status: string;
  trust_tier: string;
  trust_score: number;
  updated_at: string | null;
}

export interface AdminOverviewV2 {
  environment: string;
  total_agents: number;
  active_agents: number;
  total_listings: number;
  active_listings: number;
  total_transactions: number;
  completed_transactions: number;
  platform_volume_usd: number;
  trust_weighted_revenue_usd: number;
  updated_at: string;
}

export interface AdminFinanceV2 {
  platform_volume_usd: number;
  completed_transaction_count: number;
  payout_pending_count: number;
  payout_pending_usd: number;
  payout_processing_count: number;
  payout_processing_usd: number;
  top_sellers_by_revenue: Array<{
    agent_id: string;
    agent_name: string;
    money_received_usd: number;
  }>;
  updated_at: string;
}

export interface AdminUsageV2 {
  info_used_count: number;
  data_served_bytes: number;
  unique_buyers_count: number;
  unique_sellers_count: number;
  money_saved_for_others_usd: number;
  category_breakdown: Array<{
    category: string;
    usage_count: number;
    volume_usd: number;
    money_saved_usd: number;
  }>;
  updated_at: string;
}

export interface AdminAgentsRowV2 {
  agent_id: string;
  agent_name: string;
  status: string;
  trust_status: string;
  trust_tier: string;
  trust_score: number;
  money_received_usd: number;
  info_used_count: number;
  other_agents_served_count: number;
  data_served_bytes: number;
}

export interface AdminAgentsV2 {
  total: number;
  page: number;
  page_size: number;
  entries: AdminAgentsRowV2[];
}

export interface AdminSecurityEventsV2 {
  total: number;
  page: number;
  page_size: number;
  events: Array<{
    id: string;
    event_type: string;
    severity: string;
    agent_id: string | null;
    creator_id: string | null;
    ip_address: string | null;
    details: Record<string, unknown>;
    created_at: string;
  }>;
}

export interface OpenMarketAnalyticsV2 {
  generated_at: string;
  total_agents: number;
  total_listings: number;
  total_completed_transactions: number;
  platform_volume_usd: number;
  total_money_saved_usd: number;
  top_agents_by_revenue: Array<{
    agent_id: string;
    agent_name: string;
    money_received_usd: number;
  }>;
  top_agents_by_usage: Array<{
    agent_id: string;
    agent_name: string;
    info_used_count: number;
  }>;
  top_categories_by_usage: Array<{
    category: string;
    usage_count: number;
    volume_usd: number;
    money_saved_usd: number;
  }>;
}

export interface AdminStreamTokenResponse {
  creator_id: string;
  stream_token: string;
  ws_url: string;
  allowed_topics: string[];
}
