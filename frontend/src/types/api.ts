export interface CacheStats {
  hits: number;
  misses: number;
  size: number;
  maxsize: number;
  hit_rate: number;
}

export interface HealthResponse {
  status: string;
  version: string;
  agents_count: number;
  listings_count: number;
  transactions_count: number;
  cache_stats?: {
    listing_cache: CacheStats;
    content_cache: CacheStats;
    agent_cache: CacheStats;
  };
}

export interface Agent {
  id: string;
  name: string;
  description: string;
  agent_type: "seller" | "buyer" | "both";
  wallet_address: string;
  capabilities: string[];
  a2a_endpoint: string;
  status: string;
  created_at: string;
  updated_at: string;
  last_seen_at: string | null;
}

export interface AgentListResponse {
  total: number;
  page: number;
  page_size: number;
  agents: Agent[];
}

export interface SellerSummary {
  id: string;
  name: string;
  reputation_score: number | null;
}

export type Category =
  | "web_search"
  | "code_analysis"
  | "document_summary"
  | "api_response"
  | "computation";

export interface Listing {
  id: string;
  seller_id: string;
  seller: SellerSummary | null;
  title: string;
  description: string;
  category: Category;
  content_hash: string;
  content_size: number;
  content_type: string;
  price_usdc: number;
  currency: string;
  metadata: Record<string, unknown>;
  tags: string[];
  quality_score: number;
  freshness_at: string;
  expires_at: string | null;
  status: string;
  access_count: number;
  created_at: string;
  updated_at: string;
}

export interface ListingListResponse {
  total: number;
  page: number;
  page_size: number;
  results: Listing[];
}

export type TransactionStatus =
  | "initiated"
  | "payment_pending"
  | "payment_confirmed"
  | "delivered"
  | "verified"
  | "completed"
  | "failed"
  | "disputed";

export interface Transaction {
  id: string;
  listing_id: string;
  buyer_id: string;
  seller_id: string;
  amount_usdc: number;
  status: TransactionStatus;
  payment_tx_hash: string | null;
  payment_network: string | null;
  content_hash: string;
  delivered_hash: string | null;
  verification_status: string;
  error_message: string | null;
  initiated_at: string;
  paid_at: string | null;
  delivered_at: string | null;
  verified_at: string | null;
  completed_at: string | null;
}

export interface TransactionListResponse {
  total: number;
  page: number;
  page_size: number;
  transactions: Transaction[];
}

export interface ReputationResponse {
  agent_id: string;
  agent_name: string;
  total_transactions: number;
  successful_deliveries: number;
  failed_deliveries: number;
  verified_count: number;
  verification_failures: number;
  avg_response_ms: number | null;
  total_volume_usdc: number;
  composite_score: number;
  last_calculated_at: string;
}

export interface LeaderboardEntry {
  rank: number;
  agent_id: string;
  agent_name: string;
  composite_score: number;
  total_transactions: number;
  total_volume_usdc: number;
}

export interface LeaderboardResponse {
  entries: LeaderboardEntry[];
}

export interface FeedEvent {
  type: string;
  timestamp: string;
  data: Record<string, unknown>;
}

export interface DiscoverParams {
  q?: string;
  category?: Category | "";
  min_price?: number;
  max_price?: number;
  min_quality?: number;
  max_age_hours?: number;
  seller_id?: string;
  sort_by?: "price_asc" | "price_desc" | "freshness" | "quality";
  page?: number;
  page_size?: number;
}

export interface ExpressDeliveryResponse {
  listing_id: string;
  transaction_id: string;
  content: string;
  content_hash: string;
  price_usdc: number;
  delivery_ms: number;
  cache_hit: boolean;
}

export interface AutoMatchResult {
  listing_id: string;
  title: string;
  category: string;
  price_usdc: number;
  quality_score: number;
  freshness_at: string;
  seller_name: string;
  match_score: number;
  savings_usdc: number;
  savings_percent: number;
}

export interface AutoMatchResponse {
  matches: AutoMatchResult[];
  fresh_cost_estimate: number;
  purchase_result?: ExpressDeliveryResponse;
}

export interface TrendingQuery {
  query_pattern: string;
  category: string | null;
  search_count: number;
  unique_requesters: number;
  velocity: number;
  fulfillment_rate: number;
  last_searched_at: string;
}

export interface TrendingResponse {
  time_window_hours: number;
  trends: TrendingQuery[];
}

export interface DemandGap {
  query_pattern: string;
  category: string | null;
  search_count: number;
  unique_requesters: number;
  avg_max_price: number | null;
  fulfillment_rate: number;
  first_searched_at: string;
}

export interface DemandGapsResponse {
  gaps: DemandGap[];
}

export interface Opportunity {
  id: string;
  query_pattern: string;
  category: string | null;
  estimated_revenue_usdc: number;
  search_velocity: number;
  competing_listings: number;
  urgency_score: number;
  created_at: string;
}

export interface OpportunitiesResponse {
  opportunities: Opportunity[];
}

export interface EarningsTimelineEntry {
  date: string;
  earned: number;
  spent: number;
}

export interface EarningsBreakdown {
  agent_id: string;
  total_earned_usdc: number;
  total_spent_usdc: number;
  net_revenue_usdc: number;
  earnings_by_category: Record<string, number>;
  earnings_timeline: EarningsTimelineEntry[];
}

export interface AgentProfile {
  agent_id: string;
  agent_name: string;
  unique_buyers_served: number;
  total_listings_created: number;
  total_cache_hits: number;
  category_count: number;
  categories: string[];
  total_earned_usdc: number;
  total_spent_usdc: number;
  demand_gaps_filled: number;
  avg_listing_quality: number;
  total_data_bytes: number;
  helpfulness_score: number;
  helpfulness_rank: number | null;
  earnings_rank: number | null;
  primary_specialization: string | null;
  specialization_tags: string[];
  last_calculated_at: string;
}

export interface MultiLeaderboardEntry {
  rank: number;
  agent_id: string;
  agent_name: string;
  primary_score: number;
  secondary_label: string;
  total_transactions: number;
  helpfulness_score: number | null;
  total_earned_usdc: number | null;
}

export interface MultiLeaderboardResponse {
  board_type: string;
  entries: MultiLeaderboardEntry[];
}
