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
  price_axn?: number;
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
  payment_method?: "token" | "fiat" | "simulated";
  amount_axn?: number | null;
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

// ── CDN Stats ──

export interface CDNStats {
  overview: {
    total_requests: number;
    tier1_hits: number;
    tier2_hits: number;
    tier3_hits: number;
    total_misses: number;
  };
  hot_cache: {
    tier: string;
    entries: number;
    bytes_used: number;
    bytes_max: number;
    utilization_pct: number;
    hits: number;
    misses: number;
    promotions: number;
    evictions: number;
    hit_rate: number;
  };
  warm_cache: CacheStats;
}

// ── ZKP (Zero-Knowledge Proofs) ──

export interface ZKProof {
  id: string;
  proof_type: "merkle_root" | "schema" | "bloom_filter" | "metadata";
  commitment: string;
  public_inputs: Record<string, unknown>;
  created_at: string;
}

export interface ZKProofListResponse {
  listing_id: string;
  proofs: ZKProof[];
  count: number;
}

export interface ZKVerifyResult {
  listing_id: string;
  verified: boolean;
  checks: Record<string, { passed: boolean; details?: Record<string, unknown> }>;
  proof_types_available: string[];
}

export interface BloomCheckResult {
  listing_id: string;
  word: string;
  probably_present: boolean;
  note: string;
}

// ── Data Catalog ──

export interface CatalogEntry {
  id: string;
  agent_id: string;
  namespace: string;
  topic: string;
  description: string;
  schema_json: Record<string, unknown>;
  price_range: [number, number];
  quality_avg: number;
  active_listings_count: number;
  status: string;
  created_at: string;
}

export interface CatalogSearchResponse {
  entries: CatalogEntry[];
  total: number;
  page: number;
  page_size: number;
}

export interface CatalogSubscription {
  id: string;
  namespace_pattern: string;
  topic_pattern: string;
  notify_via: string;
  status: string;
}

// ── Routing ──

export type RoutingStrategy =
  | "cheapest"
  | "fastest"
  | "highest_quality"
  | "best_value"
  | "round_robin"
  | "weighted_random"
  | "locality";

export interface RoutingStrategyInfo {
  strategies: RoutingStrategy[];
  default: string;
  descriptions: Record<string, string>;
}

// ── Seller API ──

export interface PriceSuggestion {
  suggested_price: number;
  category: string;
  quality_score: number;
  competitors: number;
  median_price: number;
  price_range: [number, number];
  demand_searches: number;
  strategy: string;
}

export interface DemandMatch {
  demand_id: string;
  query_pattern: string;
  category: string;
  velocity: number;
  total_searches: number;
  avg_max_price: number;
  fulfillment_rate: number;
  opportunity: string;
}

// ── MCP ──

export interface MCPHealth {
  status: string;
  protocol_version: string;
  server: string;
  version: string;
  active_sessions: number;
  tools_count: number;
  resources_count: number;
}

// ── Token Economy (ARD) ──

export interface TokenAccount {
  id: string;
  agent_id: string | null;
  balance: number;
  total_deposited: number;
  total_earned: number;
  total_spent: number;
  total_fees_paid: number;
  tier: "bronze" | "silver" | "gold" | "platinum";
  created_at: string;
  updated_at: string;
}

export interface TokenLedgerEntry {
  id: string;
  from_account_id: string | null;
  to_account_id: string | null;
  amount: number;
  fee_amount: number;
  burn_amount: number;
  tx_type: string;
  reference_id: string | null;
  reference_type: string | null;
  memo: string;
  created_at: string;
}

export interface TokenLedgerResponse {
  entries: TokenLedgerEntry[];
  total: number;
  page: number;
  page_size: number;
}

export interface TokenDeposit {
  id: string;
  agent_id: string;
  amount_fiat: number;
  currency: string;
  exchange_rate: number;
  amount_axn: number;
  status: "pending" | "completed" | "failed" | "refunded";
  payment_method: string;
  payment_ref: string | null;
  created_at: string;
  completed_at: string | null;
}

export interface TokenSupply {
  total_minted: number;
  total_burned: number;
  circulating: number;
  platform_balance: number;
  last_updated: string;
}

export interface TokenTier {
  name: string;
  min_volume: number;
  fee_discount_pct: number;
  badge_color: string;
}

export interface SupportedCurrency {
  code: string;
  name: string;
  rate_per_axn: number;
  min_purchase_fiat: number;
  min_purchase_axn: number;
}

export interface WalletBalanceResponse {
  account: TokenAccount;
  balance_usd: number;
}

export interface DepositResponse {
  deposit: TokenDeposit;
  new_balance: number;
}

export interface TransferResponse {
  ledger_entry_id: string;
  from_balance: number;
  to_balance: number;
  fee: number;
  burned: number;
}

// ── Creator Economy ──

export interface Creator {
  id: string;
  email: string;
  display_name: string;
  phone: string | null;
  country: string | null;
  payout_method: "none" | "upi" | "bank" | "gift_card";
  status: "active" | "suspended" | "pending_verification";
  created_at: string;
  updated_at: string;
}

export interface CreatorAuthResponse {
  creator: Creator;
  token: string;
}

export interface CreatorAgent {
  agent_id: string;
  agent_name: string;
  agent_type: string;
  status: string;
  total_earned: number;
  total_spent: number;
  balance: number;
}

export interface CreatorDashboard {
  creator_balance: number;
  creator_total_earned: number;
  creator_balance_usd: number;
  agents_count: number;
  agents: CreatorAgent[];
  total_agent_earnings: number;
  total_agent_spent: number;
  peg_rate_usd: number;
  token_name: string;
}

export interface CreatorWallet {
  balance: number;
  balance_usd: number;
  total_earned: number;
  total_spent: number;
  total_deposited: number;
  total_fees_paid: number;
  tier: string;
  token_name: string;
  peg_rate_usd: number;
}

export interface RedemptionRequest {
  id: string;
  creator_id: string;
  redemption_type: "api_credits" | "gift_card" | "bank_withdrawal" | "upi";
  amount_ard: number;
  amount_fiat: number | null;
  currency: string;
  exchange_rate: number | null;
  status: "pending" | "processing" | "completed" | "failed" | "rejected";
  payout_ref: string | null;
  admin_notes: string;
  rejection_reason: string;
  created_at: string;
  processed_at: string | null;
  completed_at: string | null;
}

export interface RedemptionMethodInfo {
  type: string;
  label: string;
  min_ard: number;
  min_usd: number;
  processing_time: string;
  available: boolean;
}
