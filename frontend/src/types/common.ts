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

export interface SystemMetrics {
  health: HealthResponse;
  cdn: CDNStats;
}

// Forward reference — CDNStats is defined here to keep common types together
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
