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
  DepositResponse,
  TransferResponse,
  Creator,
  CreatorAuthResponse,
  CreatorAgent,
  CreatorDashboard,
  CreatorWallet,
  RedemptionRequest,
  RedemptionMethodInfo,
  AgentOnboardResponse,
  RuntimeAttestationResponse,
  KnowledgeChallengeResponse,
  AgentTrustProfile,
  AgentTrustPublicSummary,
  AgentDashboardV2,
  CreatorDashboardV2,
  AgentPublicDashboardV2,
  AdminOverviewV2,
  AdminFinanceV2,
  AdminUsageV2,
  AdminAgentsV2,
  AdminSecurityEventsV2,
  OpenMarketAnalyticsV2,
  MemoryImportResponse,
  MemoryVerifyResponse,
  MemorySnapshot,
  StreamTokenResponse,
  AdminStreamTokenResponse,
  WebhookSubscription,
} from "../types/api";

const BASE = "/api/v1";
const BASE_V2 = "/api/v2";

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

async function authPut<T>(
  path: string,
  token: string,
  body: unknown,
): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    method: "PUT",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`API ${res.status}: ${await res.text()}`);
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

async function getV2<T>(
  path: string,
  params?: Record<string, string | number | undefined>,
): Promise<T> {
  const url = new URL(`${BASE_V2}${path}`, window.location.origin);
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

async function authGetV2<T>(
  path: string,
  token: string,
  params?: Record<string, string | number | undefined>,
): Promise<T> {
  const url = new URL(`${BASE_V2}${path}`, window.location.origin);
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

async function authPostV2<T>(
  path: string,
  token: string,
  body: unknown,
): Promise<T> {
  const res = await fetch(`${BASE_V2}${path}`, {
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

async function authDeleteV2<T>(
  path: string,
  token: string,
): Promise<T> {
  const res = await fetch(`${BASE_V2}${path}`, {
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
  authPost<ExpressDeliveryResponse>(`/express/${listingId}`, token, {});

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

// ── Wallet (USD Billing) ──

export const fetchWalletBalance = (token: string) =>
  authGet<WalletBalanceResponse>("/wallet/balance", token);

export const fetchWalletHistory = (token: string, params?: { page?: number; page_size?: number; tx_type?: string }) =>
  authGet<TokenLedgerResponse>("/wallet/history", token, params as Record<string, string | number | undefined>);

export const createDeposit = (token: string, body: { amount_usd: number }) =>
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

// ── Creator Account ──

export const creatorRegister = (body: {
  email: string;
  password: string;
  display_name: string;
  phone?: string;
  country?: string;
}) => {
  return fetch(`${BASE}/creators/register`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  }).then(async (r) => {
    if (!r.ok) throw new Error(`API ${r.status}: ${await r.text()}`);
    return r.json() as Promise<CreatorAuthResponse>;
  });
};

export const creatorLogin = (body: { email: string; password: string }) => {
  return fetch(`${BASE}/creators/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  }).then(async (r) => {
    if (!r.ok) throw new Error(`API ${r.status}: ${await r.text()}`);
    return r.json() as Promise<CreatorAuthResponse>;
  });
};

export const fetchCreatorProfile = (token: string) =>
  authGet<Creator>("/creators/me", token);

export const updateCreatorProfile = (token: string, body: Record<string, unknown>) =>
  authPut<Creator>("/creators/me", token, body);

export const fetchCreatorAgents = (token: string) =>
  authGet<{ agents: CreatorAgent[]; count: number }>("/creators/me/agents", token);

export const claimAgent = (token: string, agentId: string) =>
  authPost<{ agent_id: string; creator_id: string }>(`/creators/me/agents/${agentId}/claim`, token, {});

export const fetchCreatorDashboard = (token: string) =>
  authGet<CreatorDashboard>("/creators/me/dashboard", token);

export const fetchCreatorWallet = (token: string) =>
  authGet<CreatorWallet>("/creators/me/wallet", token);

// ── Redemptions ──

export const createRedemption = (
  token: string,
  body: { redemption_type: string; amount_usd: number; currency?: string },
) => authPost<RedemptionRequest>("/redemptions", token, body);

export const fetchRedemptions = (
  token: string,
  params?: { status?: string; page?: number; page_size?: number },
) => authGet<{ redemptions: RedemptionRequest[]; total: number }>("/redemptions", token, params as Record<string, string | number | undefined>);

export const cancelRedemption = (token: string, id: string) =>
  authPost<{ message: string }>(`/redemptions/${id}/cancel`, token, {});

export const fetchRedemptionMethods = () =>
  get<{ methods: RedemptionMethodInfo[] }>("/redemptions/methods");

// -- Agent Trust + Memory (v2) --

export const onboardAgentV2 = (
  creatorToken: string,
  body: {
    name: string;
    description?: string;
    agent_type: "seller" | "buyer" | "both";
    public_key: string;
    wallet_address?: string;
    capabilities?: string[];
    a2a_endpoint?: string;
    memory_import_intent?: boolean;
  },
) => authPostV2<AgentOnboardResponse>("/agents/onboard", creatorToken, body);

export const attestRuntimeV2 = (
  agentToken: string,
  agentId: string,
  body: {
    runtime_name: string;
    runtime_version?: string;
    sdk_version?: string;
    endpoint_reachable?: boolean;
    supports_memory?: boolean;
  },
) =>
  authPostV2<RuntimeAttestationResponse>(
    `/agents/${agentId}/attest/runtime`,
    agentToken,
    body,
  );

export const runKnowledgeChallengeV2 = (
  agentToken: string,
  agentId: string,
  body: {
    capabilities?: string[];
    claim_payload?: Record<string, unknown>;
  },
) =>
  authPostV2<KnowledgeChallengeResponse>(
    `/agents/${agentId}/attest/knowledge/run`,
    agentToken,
    body,
  );

export const fetchAgentTrustV2 = (agentId: string, agentToken: string) =>
  authGetV2<AgentTrustProfile>(`/agents/${agentId}/trust`, agentToken);

export const fetchAgentTrustPublicV2 = (agentId: string) =>
  getV2<AgentTrustPublicSummary>(`/agents/${agentId}/trust/public`);

export const fetchDashboardAgentMeV2 = (agentToken: string) =>
  authGetV2<AgentDashboardV2>("/dashboards/agent/me", agentToken);

export const fetchDashboardCreatorMeV2 = (creatorToken: string) =>
  authGetV2<CreatorDashboardV2>("/dashboards/creator/me", creatorToken);

export const fetchDashboardAgentPublicV2 = (agentId: string) =>
  getV2<AgentPublicDashboardV2>(`/dashboards/agent/${agentId}/public`);

export const fetchOpenMarketAnalyticsV2 = (limit = 10) =>
  getV2<OpenMarketAnalyticsV2>("/analytics/market/open", { limit });

export const importMemorySnapshotV2 = (
  agentToken: string,
  body: {
    source_type?: string;
    label?: string;
    records: Record<string, unknown>[];
    chunk_size?: number;
    source_metadata?: Record<string, unknown>;
    encrypted_blob_ref?: string;
  },
) => authPostV2<MemoryImportResponse>("/memory/snapshots/import", agentToken, body);

export const verifyMemorySnapshotV2 = (
  agentToken: string,
  snapshotId: string,
  body?: { sample_size?: number },
) =>
  authPostV2<MemoryVerifyResponse>(
    `/memory/snapshots/${snapshotId}/verify`,
    agentToken,
    body ?? {},
  );

export const fetchMemorySnapshotV2 = (agentToken: string, snapshotId: string) =>
  authGetV2<MemorySnapshot>(`/memory/snapshots/${snapshotId}`, agentToken);

export const fetchStreamTokenV2 = (agentToken: string) =>
  authGetV2<StreamTokenResponse>("/events/stream-token", agentToken);

export const fetchAdminOverviewV2 = (creatorToken: string) =>
  authGetV2<AdminOverviewV2>("/admin/overview", creatorToken);

export const fetchAdminFinanceV2 = (creatorToken: string) =>
  authGetV2<AdminFinanceV2>("/admin/finance", creatorToken);

export const fetchAdminUsageV2 = (creatorToken: string) =>
  authGetV2<AdminUsageV2>("/admin/usage", creatorToken);

export const fetchAdminAgentsV2 = (
  creatorToken: string,
  params?: { page?: number; page_size?: number; status?: string },
) => authGetV2<AdminAgentsV2>("/admin/agents", creatorToken, params as Record<string, string | number | undefined>);

export const fetchAdminSecurityEventsV2 = (
  creatorToken: string,
  params?: { page?: number; page_size?: number; severity?: string; event_type?: string },
) => authGetV2<AdminSecurityEventsV2>("/admin/security/events", creatorToken, params as Record<string, string | number | undefined>);

export const fetchAdminPendingPayoutsV2 = (
  creatorToken: string,
  limit = 100,
) => authGetV2<{ count: number; total_pending_usd: number; requests: unknown[] }>("/admin/payouts/pending", creatorToken, { limit });

export const approveAdminPayoutV2 = (
  creatorToken: string,
  requestId: string,
  adminNotes = "",
) => authPostV2(`/admin/payouts/${requestId}/approve`, creatorToken, { admin_notes: adminNotes });

export const rejectAdminPayoutV2 = (
  creatorToken: string,
  requestId: string,
  reason: string,
) => authPostV2(`/admin/payouts/${requestId}/reject`, creatorToken, { reason });

export const fetchAdminStreamTokenV2 = (creatorToken: string) =>
  authGetV2<AdminStreamTokenResponse>("/admin/events/stream-token", creatorToken);

export const createWebhookSubscriptionV2 = (
  agentToken: string,
  body: { callback_url: string; event_types?: string[] },
) => authPostV2<WebhookSubscription>("/integrations/webhooks", agentToken, body);

export const fetchWebhookSubscriptionsV2 = (agentToken: string) =>
  authGetV2<{ subscriptions: WebhookSubscription[]; count: number }>(
    "/integrations/webhooks",
    agentToken,
  );

export const deleteWebhookSubscriptionV2 = (
  agentToken: string,
  subscriptionId: string,
) =>
  authDeleteV2<{ deleted: boolean }>(
    `/integrations/webhooks/${subscriptionId}`,
    agentToken,
  );

// ── System Metrics (combined) ──

export async function fetchSystemMetrics(): Promise<{
  health: HealthResponse;
  cdn: CDNStats;
}> {
  const [health, cdn] = await Promise.all([
    get<HealthResponse>("/health"),
    get<CDNStats>("/health/cdn"),
  ]);
  return { health, cdn };
}
