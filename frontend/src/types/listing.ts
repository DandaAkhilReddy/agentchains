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
