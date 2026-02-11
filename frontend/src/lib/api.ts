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
  CDNStats,
  ZKProofListResponse,
  ZKVerifyResult,
  BloomCheckResult,
  CatalogSearchResponse,
  CatalogEntry,
  CatalogSubscription,
  RoutingStrategyInfo,
  PriceSuggestion,
  DemandMatch,
  MCPHealth,
  WalletBalanceResponse,
  TokenLedgerResponse,
  TokenSupply,
  TokenTier,
  SupportedCurrency,
  DepositResponse,
  TransferResponse,
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

async function authDelete<T>(
  path: string,
  token: string,
): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    method: "DELETE",
    headers: {
      Authorization: `Bearer ${token}`,
    },
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

// ── CDN ──

export const fetchCDNStats = () => get<CDNStats>("/health/cdn");

// ── ZKP ──

export const fetchZKProofs = (listingId: string) =>
  get<ZKProofListResponse>(`/zkp/${listingId}/proofs`);

export const verifyZKP = (
  token: string,
  listingId: string,
  params: { keywords?: string[]; schema_has_fields?: string[]; min_size?: number; min_quality?: number },
) => authPost<ZKVerifyResult>(`/zkp/${listingId}/verify`, token, params);

export const bloomCheck = (listingId: string, word: string) =>
  get<BloomCheckResult>(`/zkp/${listingId}/bloom-check`, { word });

// ── Catalog ──

export const searchCatalog = (params?: {
  q?: string;
  namespace?: string;
  min_quality?: number;
  max_price?: number;
  page?: number;
  page_size?: number;
}) => get<CatalogSearchResponse>("/catalog/search", params as Record<string, string | number | undefined>);

export const getAgentCatalog = (agentId: string) =>
  get<{ entries: CatalogEntry[]; count: number }>(`/catalog/agent/${agentId}`);

export const registerCatalog = (
  token: string,
  body: { namespace: string; topic: string; description?: string; price_range_min?: number; price_range_max?: number },
) => authPost<CatalogEntry>("/catalog", token, body);

export const subscribeCatalog = (
  token: string,
  body: { namespace_pattern: string; topic_pattern?: string; max_price?: number; min_quality?: number },
) => authPost<CatalogSubscription>("/catalog/subscribe", token, body);

// ── Routing ──

export const fetchRoutingStrategies = () => get<RoutingStrategyInfo>("/route/strategies");

// ── Seller API ──

export const suggestPrice = (
  token: string,
  body: { category: string; quality_score?: number },
) => authPost<PriceSuggestion>("/seller/price-suggest", token, body);

export const fetchDemandForMe = (token: string) =>
  authGet<{ matches: DemandMatch[]; count: number }>("/seller/demand-for-me", token);

// ── MCP ──

export const fetchMCPHealth = () => {
  const url = new URL("/mcp/health", window.location.origin);
  return fetch(url.toString()).then(r => r.json()) as Promise<MCPHealth>;
};

// ── Wallet (AXN Token Economy) ──

export const fetchWalletBalance = (token: string) =>
  authGet<WalletBalanceResponse>("/wallet/balance", token);

export const fetchWalletHistory = (token: string, params?: { page?: number; page_size?: number; tx_type?: string }) =>
  authGet<TokenLedgerResponse>("/wallet/history", token, params as Record<string, string | number | undefined>);

export const fetchTokenSupply = () => get<TokenSupply>("/wallet/supply");

export const fetchTokenTiers = () => get<{ tiers: TokenTier[] }>("/wallet/tiers");

export const fetchSupportedCurrencies = () => get<{ currencies: SupportedCurrency[] }>("/wallet/currencies");

export const createDeposit = (token: string, body: { amount_fiat: number; currency: string }) =>
  authPost<DepositResponse>("/wallet/deposit", token, body);

export const createTransfer = (
  token: string,
  body: { to_agent_id: string; amount: number; memo?: string },
) => authPost<TransferResponse>("/wallet/transfer", token, body);

// ── OpenClaw Integration ──

export const registerOpenClawWebhook = (token: string, body: {
  gateway_url: string;
  bearer_token: string;
  event_types: string[];
  filters: Record<string, unknown>;
}) => authPost<any>("/integrations/openclaw/register-webhook", token, body);

export const fetchOpenClawWebhooks = (token: string) =>
  authGet<{ webhooks: any[]; count: number }>("/integrations/openclaw/webhooks", token);

export const deleteOpenClawWebhook = (token: string, webhookId: string) =>
  authDelete<{ deleted: boolean }>(`/integrations/openclaw/webhooks/${webhookId}`, token);

export const testOpenClawWebhook = (token: string, webhookId: string) =>
  authPost<{ success: boolean; message: string }>(`/integrations/openclaw/webhooks/${webhookId}/test`, token, {});

export const fetchOpenClawStatus = (token: string) =>
  authGet<{ connected: boolean; webhooks_count: number; active_count: number; last_delivery: string | null }>("/integrations/openclaw/status", token);
