export interface HealthResponse {
  status: string;
  version: string;
  agents_count: number;
  listings_count: number;
  transactions_count: number;
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
