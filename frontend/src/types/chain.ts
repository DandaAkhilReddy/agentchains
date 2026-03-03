/** Chain-related types matching the v5 API response shapes. */

export interface ChainTemplate {
  id: string;
  name: string;
  description: string;
  category: string;
  workflow_id: string | null;
  graph_json: string;
  author_id: string;
  forked_from_id: string | null;
  version: number;
  status: string;
  tags: string[];
  execution_count: number;
  avg_cost_usd: number;
  avg_duration_ms: number;
  trust_score: number;
  max_budget_usd: number | null;
  created_at: string | null;
  updated_at: string | null;
}

export interface ChainExecution {
  id: string;
  chain_template_id: string;
  workflow_execution_id: string | null;
  initiated_by: string;
  status: string;
  input_json: string | null;
  output_json: string | null;
  total_cost_usd: number;
  participant_agents: string[];
  provenance_hash: string | null;
  idempotency_key: string | null;
  created_at: string | null;
  completed_at: string | null;
}

export interface ChainAssignment {
  capability: string;
  agent_id: string;
  agent_name: string;
  rank_score: number;
}

export interface AgentSuggestion {
  agent_id: string;
  name: string;
  description: string;
  a2a_endpoint: string | null;
  match_source: string;
  reputation_score: number;
  catalog_quality: number;
  avg_price: number;
  rank_score: number;
}

export interface ComposeResult {
  name: string;
  description: string;
  category: string;
  graph_json: string;
  status: string;
  capabilities: string[];
  assignments: ChainAssignment[];
  alternatives: Record<string, AgentSuggestion[]>;
}

export interface ChainTemplateListResponse {
  templates: ChainTemplate[];
  total: number;
  limit: number;
  offset: number;
}

export interface ChainExecutionListResponse {
  executions: ChainExecution[];
  total: number;
  limit: number;
  offset: number;
}
