import type {
  HealthResponse,
  AgentListResponse,
  ListingListResponse,
  TransactionListResponse,
  ReputationResponse,
  LeaderboardResponse,
  DiscoverParams,
  ExpressDeliveryResponse,
  AutoMatchResponse,
  TrendingResponse,
  DemandGapsResponse,
  OpportunitiesResponse,
  EarningsBreakdown,
  AgentProfile,
  MultiLeaderboardResponse,
} from "../types/api";

const BASE = "/api/v1";

async function get<T>(
  path: string,
  params?: Record<string, string | number | undefined>,
): Promise<T> {
  const url = new URL(`${BASE}${path}`, window.location.origin);
  if (params) {
    for (const [k, v] of Object.entries(params)) {
      if (v !== undefined && v !== null && v !== "") {
        url.searchParams.set(k, String(v));
      }
    }
  }
  const res = await fetch(url.toString());
  if (!res.ok) {
    throw new Error(`API ${res.status}: ${await res.text()}`);
  }
  return res.json();
}

async function authGet<T>(
  path: string,
  token: string,
  params?: Record<string, string | number | undefined>,
): Promise<T> {
  const url = new URL(`${BASE}${path}`, window.location.origin);
  if (params) {
    for (const [k, v] of Object.entries(params)) {
      if (v !== undefined && v !== null && v !== "") {
        url.searchParams.set(k, String(v));
      }
    }
  }
  const res = await fetch(url.toString(), {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!res.ok) {
    throw new Error(`API ${res.status}: ${await res.text()}`);
  }
  return res.json();
}

async function authPost<T>(
  path: string,
  token: string,
  body: unknown,
): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${token}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    throw new Error(`API ${res.status}: ${await res.text()}`);
  }
  return res.json();
}

export const fetchHealth = () => get<HealthResponse>("/health");

export const fetchAgents = (params?: {
  agent_type?: string;
  status?: string;
  page?: number;
  page_size?: number;
}) => get<AgentListResponse>("/agents", params as Record<string, string | number | undefined>);

export const fetchListings = (params?: {
  category?: string;
  status?: string;
  page?: number;
  page_size?: number;
}) => get<ListingListResponse>("/listings", params as Record<string, string | number | undefined>);

export const fetchDiscover = (params: DiscoverParams) =>
  get<ListingListResponse>("/discover", params as Record<string, string | number | undefined>);

export const fetchTransactions = (
  token: string,
  params?: { status?: string; page?: number; page_size?: number },
) =>
  authGet<TransactionListResponse>(
    "/transactions",
    token,
    params as Record<string, string | number | undefined>,
  );

export const fetchLeaderboard = (limit?: number) =>
  get<LeaderboardResponse>("/reputation/leaderboard", { limit });

export const fetchReputation = (agentId: string) =>
  get<ReputationResponse>(`/reputation/${agentId}`, { recalculate: "true" });

export const expressBuy = (token: string, listingId: string) =>
  authGet<ExpressDeliveryResponse>(`/express/${listingId}`, token);

export const autoMatch = (
  token: string,
  params: {
    description: string;
    category?: string;
    max_price?: number;
    auto_buy?: boolean;
    auto_buy_max_price?: number;
  },
) => authPost<AutoMatchResponse>("/agents/auto-match", token, params);

export const fetchTrending = (limit?: number, hours?: number) =>
  get<TrendingResponse>("/analytics/trending", { limit, hours });

export const fetchDemandGaps = (limit?: number, category?: string) =>
  get<DemandGapsResponse>("/analytics/demand-gaps", { limit, category });

export const fetchOpportunities = (limit?: number, category?: string) =>
  get<OpportunitiesResponse>("/analytics/opportunities", { limit, category });

export const fetchMyEarnings = (token: string) =>
  authGet<EarningsBreakdown>("/analytics/my-earnings", token);

export const fetchMyStats = (token: string) =>
  authGet<AgentProfile>("/analytics/my-stats", token);

export const fetchAgentProfile = (agentId: string) =>
  get<AgentProfile>(`/analytics/agent/${agentId}/profile`);

export const fetchMultiLeaderboard = (boardType: string, limit?: number) =>
  get<MultiLeaderboardResponse>(`/analytics/leaderboard/${boardType}`, { limit });
