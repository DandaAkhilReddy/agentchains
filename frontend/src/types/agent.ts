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

// ── Agent Trust + Memory (v2) ──

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
