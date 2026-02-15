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
    listings: CacheStats;
    content: CacheStats;
    agents: CacheStats;
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
  payment_method?: "balance" | "fiat" | "simulated";
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
  event_id?: string;
  seq?: number;
  event_type?: string;
  occurred_at?: string;
  agent_id?: string | null;
  payload?: Record<string, unknown>;
  signature?: string;
  signature_key_id?: string;
  delivery_attempt?: number;
  visibility?: "public" | "private";
  topic?: "public.market" | "private.agent" | "private.admin" | string;
  target_agent_ids?: string[];
  target_creator_ids?: string[];
  schema_version?: string;
  blocked?: boolean;
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

// ── Billing (USD) ──

export interface TokenAccount {
  id: string;
  agent_id: string | null;
  balance: number;
  total_deposited: number;
  total_earned: number;
  total_spent: number;
  total_fees_paid: number;
  created_at: string;
  updated_at: string;
}

export interface TokenLedgerEntry {
  id: string;
  from_account_id: string | null;
  to_account_id: string | null;
  amount: number;
  fee_amount: number;
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
  amount_usd: number;
  status: "pending" | "completed" | "failed" | "refunded";
  payment_method: string;
  payment_ref: string | null;
  created_at: string;
  completed_at: string | null;
}

export interface WalletBalanceResponse {
  balance: number;
  total_earned: number;
  total_spent: number;
  total_deposited: number;
  total_fees_paid: number;
}

export interface DepositResponse {
  id: string;
  agent_id: string;
  amount_usd: number;
  currency: string;
  status: string;
  payment_method: string;
  payment_ref: string | null;
  created_at: string | null;
  completed_at: string | null;
}

export interface TransferResponse {
  id: string;
  amount: number;
  fee_amount: number;
  tx_type: string;
  memo: string | null;
  created_at: string | null;
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
  agents_count: number;
  agents: CreatorAgent[];
  total_agent_earnings: number;
  total_agent_spent: number;
}

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

export interface CreatorWallet {
  balance: number;
  total_earned: number;
  total_spent: number;
  total_deposited: number;
  total_fees_paid: number;
}

export interface RedemptionRequest {
  id: string;
  creator_id: string;
  redemption_type: "api_credits" | "gift_card" | "bank_withdrawal" | "upi";
  amount_usd: number;
  currency: string;
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
  min_usd: number;
  processing_time: string;
  available: boolean;
}

// ── Pipeline Types ──

export interface PipelineToolCall {
  name: string;
  input: Record<string, unknown>;
  output?: unknown;
}

export interface PipelineStep {
  id: string;
  agentId: string;
  agentName: string;
  action: string;
  status: "running" | "completed" | "failed" | "waiting";
  startedAt: string;
  completedAt?: string;
  latencyMs?: number;
  toolCall?: PipelineToolCall;
  error?: string;
}

export interface AgentExecution {
  agentId: string;
  agentName: string;
  status: "active" | "idle" | "error";
  steps: PipelineStep[];
  startedAt: string;
  lastActivityAt: string;
}

// ── System Metrics (for Technology page) ──

export interface SystemMetrics {
  health: HealthResponse;
  cdn: CDNStats;
}

// -- Agent Trust + Memory (v2) --

export interface AgentTrustProfile {
  agent_id: string;
  agent_trust_status: "unverified" | "provisional" | "verified" | "restricted";
  agent_trust_tier: "T0" | "T1" | "T2" | "T3";
  agent_trust_score: number;
  stage_scores: {
    identity: number;
    runtime: number;
    knowledge: number;
    memory: number;
    abuse: number;
  };
  knowledge_challenge_summary: Record<string, unknown>;
  memory_provenance: Record<string, unknown>;
  updated_at: string | null;
}

export interface AgentTrustPublicSummary {
  agent_id: string;
  agent_trust_status: "unverified" | "provisional" | "verified" | "restricted";
  agent_trust_tier: "T0" | "T1" | "T2" | "T3";
  agent_trust_score: number;
  updated_at: string | null;
}

export interface AgentOnboardResponse extends AgentTrustProfile {
  onboarding_session_id: string;
  agent_id: string;
  agent_name: string;
  agent_jwt_token: string;
  agent_card_url: string;
  stream_token: string;
}

export interface RuntimeAttestationResponse {
  attestation_id: string;
  stage_runtime_score: number;
  profile: AgentTrustProfile;
}

export interface KnowledgeChallengeResponse {
  agent_id: string;
  status: "passed" | "failed";
  severe_safety_failure: boolean;
  stage_knowledge_score: number;
  knowledge_challenge_summary: Record<string, unknown>;
  profile: AgentTrustProfile;
}

export interface MemorySnapshot {
  snapshot_id: string;
  agent_id: string;
  source_type: string;
  label: string;
  manifest: Record<string, unknown>;
  merkle_root: string;
  status: "imported" | "verified" | "failed" | "quarantined" | string;
  total_records: number;
  total_chunks: number;
  created_at: string | null;
  verified_at: string | null;
}

export interface MemoryImportResponse {
  snapshot: MemorySnapshot;
  chunk_hashes: string[];
  trust_profile: AgentTrustProfile;
}

export interface MemoryVerifyResponse {
  snapshot: MemorySnapshot;
  verification_run_id: string;
  status: string;
  score: number;
  sampled_entries: Record<string, unknown>[];
  trust_profile: AgentTrustProfile;
}

export interface StreamTokenResponse {
  agent_id: string;
  stream_token: string;
  expires_in_seconds: number;
  expires_at: string;
  ws_url: string;
  allowed_topics: string[];
}

export interface AdminStreamTokenResponse {
  creator_id: string;
  stream_token: string;
  ws_url: string;
  allowed_topics: string[];
}

export interface WebhookSubscription {
  id: string;
  agent_id: string;
  callback_url: string;
  event_types: string[];
  status: string;
  failure_count: number;
  last_delivery_at: string | null;
  created_at: string | null;
  secret?: string;
}
