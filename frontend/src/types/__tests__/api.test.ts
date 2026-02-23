import { describe, it, expect } from "vitest";
import type {
  CacheStats,
  HealthResponse,
  Agent,
  AgentListResponse,
  SellerSummary,
  Category,
  Listing,
  ListingListResponse,
  TransactionStatus,
  Transaction,
  TransactionListResponse,
  ReputationResponse,
  LeaderboardEntry,
  LeaderboardResponse,
  FeedEvent,
  DiscoverParams,
  ExpressDeliveryResponse,
  AutoMatchResult,
  AutoMatchResponse,
  TrendingQuery,
  TrendingResponse,
  DemandGap,
  DemandGapsResponse,
  Opportunity,
  OpportunitiesResponse,
  EarningsTimelineEntry,
  EarningsBreakdown,
  AgentProfile,
  MultiLeaderboardEntry,
  MultiLeaderboardResponse,
  CDNStats,
  ZKProof,
  ZKProofListResponse,
  ZKVerifyResult,
  BloomCheckResult,
  CatalogEntry,
  CatalogSearchResponse,
  CatalogSubscription,
  RoutingStrategy,
  RoutingStrategyInfo,
  PriceSuggestion,
  DemandMatch,
  MCPHealth,
  TokenAccount,
  TokenLedgerEntry,
  TokenLedgerResponse,
  TokenDeposit,
  WalletBalanceResponse,
  DepositResponse,
  TransferResponse,
  Creator,
  CreatorAuthResponse,
  CreatorAgent,
  CreatorDashboard,
  SavingsSummary,
  AgentDashboardV2,
  CreatorDashboardV2,
  AgentPublicDashboardV2,
  AdminOverviewV2,
  AdminFinanceV2,
  AdminUsageV2,
  AdminAgentsRowV2,
  AdminAgentsV2,
  AdminSecurityEventsV2,
  OpenMarketAnalyticsV2,
  CreatorWallet,
  RedemptionRequest,
  RedemptionMethodInfo,
  PipelineToolCall,
  PipelineStep,
  AgentExecution,
  SystemMetrics,
  AgentTrustProfile,
  AgentTrustPublicSummary,
  AgentOnboardResponse,
  RuntimeAttestationResponse,
  KnowledgeChallengeResponse,
  MemorySnapshot,
  MemoryImportResponse,
  MemoryVerifyResponse,
  StreamTokenResponse,
  AdminStreamTokenResponse,
  WebhookSubscription,
} from "../api";

// ── CacheStats ─────────────────────────────────────────────────────────────

describe("CacheStats", () => {
  it("constructs a valid CacheStats object", () => {
    const stats: CacheStats = {
      hits: 100,
      misses: 20,
      size: 50,
      maxsize: 200,
      hit_rate: 0.833,
    };
    expect(stats.hits).toBe(100);
    expect(stats.misses).toBe(20);
    expect(stats.hit_rate).toBeCloseTo(0.833);
  });

  it("accepts zero values for an empty cache", () => {
    const stats: CacheStats = {
      hits: 0,
      misses: 0,
      size: 0,
      maxsize: 100,
      hit_rate: 0,
    };
    expect(stats.size).toBe(0);
    expect(stats.hit_rate).toBe(0);
  });
});

// ── HealthResponse ─────────────────────────────────────────────────────────

describe("HealthResponse", () => {
  it("constructs a minimal health response without cache_stats", () => {
    const health: HealthResponse = {
      status: "healthy",
      version: "1.2.3",
      agents_count: 10,
      listings_count: 50,
      transactions_count: 200,
    };
    expect(health.status).toBe("healthy");
    expect(health.version).toBe("1.2.3");
    expect(health.cache_stats).toBeUndefined();
  });

  it("constructs a health response with all three cache stat buckets", () => {
    const cacheEntry: CacheStats = { hits: 5, misses: 1, size: 10, maxsize: 100, hit_rate: 0.83 };
    const health: HealthResponse = {
      status: "healthy",
      version: "2.0.0",
      agents_count: 3,
      listings_count: 15,
      transactions_count: 42,
      cache_stats: {
        listings: cacheEntry,
        content: cacheEntry,
        agents: cacheEntry,
      },
    };
    expect(health.cache_stats).toBeDefined();
    expect(health.cache_stats!.listings.hit_rate).toBe(0.83);
    expect(health.cache_stats!.content).toEqual(cacheEntry);
    expect(health.cache_stats!.agents).toEqual(cacheEntry);
  });
});

// ── Agent ──────────────────────────────────────────────────────────────────

describe("Agent", () => {
  it("constructs a seller agent with all required fields", () => {
    const agent: Agent = {
      id: "agent-001",
      name: "DataBot",
      description: "A bot that sells data",
      agent_type: "seller",
      wallet_address: "0xabcdef",
      capabilities: ["web_search", "compute"],
      a2a_endpoint: "https://agent.example.com/a2a",
      status: "active",
      created_at: "2024-01-01T00:00:00Z",
      updated_at: "2024-06-01T00:00:00Z",
      last_seen_at: "2024-06-15T12:00:00Z",
    };
    expect(agent.id).toBe("agent-001");
    expect(agent.agent_type).toBe("seller");
    expect(agent.capabilities).toContain("web_search");
    expect(agent.last_seen_at).toBeTruthy();
  });

  it("accepts null for last_seen_at on a new agent", () => {
    const agent: Agent = {
      id: "agent-002",
      name: "BuyerBot",
      description: "Buys data",
      agent_type: "buyer",
      wallet_address: "0x123456",
      capabilities: [],
      a2a_endpoint: "https://buyer.example.com/a2a",
      status: "inactive",
      created_at: "2024-01-01T00:00:00Z",
      updated_at: "2024-01-01T00:00:00Z",
      last_seen_at: null,
    };
    expect(agent.last_seen_at).toBeNull();
    expect(agent.agent_type).toBe("buyer");
  });

  it("accepts 'both' as agent_type", () => {
    const agent: Agent = {
      id: "agent-003",
      name: "HybridBot",
      description: "Does both",
      agent_type: "both",
      wallet_address: "0xfedcba",
      capabilities: ["code_analysis"],
      a2a_endpoint: "https://hybrid.example.com/a2a",
      status: "active",
      created_at: "2024-01-01T00:00:00Z",
      updated_at: "2024-01-01T00:00:00Z",
      last_seen_at: null,
    };
    expect(agent.agent_type).toBe("both");
  });
});

// ── AgentListResponse ──────────────────────────────────────────────────────

describe("AgentListResponse", () => {
  it("constructs a paginated agent list response", () => {
    const response: AgentListResponse = {
      total: 100,
      page: 1,
      page_size: 20,
      agents: [],
    };
    expect(response.total).toBe(100);
    expect(response.page).toBe(1);
    expect(response.page_size).toBe(20);
    expect(response.agents).toHaveLength(0);
  });
});

// ── SellerSummary ──────────────────────────────────────────────────────────

describe("SellerSummary", () => {
  it("constructs a seller summary with a reputation score", () => {
    const summary: SellerSummary = { id: "s-1", name: "SellerBot", reputation_score: 0.95 };
    expect(summary.reputation_score).toBe(0.95);
  });

  it("accepts null reputation_score for an unrated seller", () => {
    const summary: SellerSummary = { id: "s-2", name: "NewBot", reputation_score: null };
    expect(summary.reputation_score).toBeNull();
  });
});

// ── Category ───────────────────────────────────────────────────────────────

describe("Category", () => {
  it("accepts all five category literals", () => {
    const categories: Category[] = [
      "web_search",
      "code_analysis",
      "document_summary",
      "api_response",
      "computation",
    ];
    expect(categories).toHaveLength(5);
    categories.forEach((c) => expect(typeof c).toBe("string"));
  });
});

// ── Listing ────────────────────────────────────────────────────────────────

describe("Listing", () => {
  it("constructs a full listing with seller summary", () => {
    const listing: Listing = {
      id: "listing-001",
      seller_id: "seller-1",
      seller: { id: "seller-1", name: "DataBot", reputation_score: 0.9 },
      title: "Market Trends Q1",
      description: "Monthly market analysis",
      category: "api_response",
      content_hash: "sha256:abc123",
      content_size: 4096,
      content_type: "application/json",
      price_usdc: 0.05,
      currency: "USDC",
      metadata: { source: "scraper-v2" },
      tags: ["market", "trends"],
      quality_score: 0.87,
      freshness_at: "2024-06-01T00:00:00Z",
      expires_at: "2024-07-01T00:00:00Z",
      status: "active",
      access_count: 42,
      created_at: "2024-05-01T00:00:00Z",
      updated_at: "2024-06-01T00:00:00Z",
    };
    expect(listing.id).toBe("listing-001");
    expect(listing.category).toBe("api_response");
    expect(listing.seller!.reputation_score).toBe(0.9);
    expect(listing.tags).toContain("market");
    expect(listing.price_usdc).toBe(0.05);
  });

  it("accepts null seller and null expires_at", () => {
    const listing: Listing = {
      id: "listing-002",
      seller_id: "seller-99",
      seller: null,
      title: "Raw data",
      description: "No seller attached",
      category: "computation",
      content_hash: "sha256:xyz",
      content_size: 1024,
      content_type: "text/plain",
      price_usdc: 0.01,
      currency: "USDC",
      metadata: {},
      tags: [],
      quality_score: 0.5,
      freshness_at: "2024-06-01T00:00:00Z",
      expires_at: null,
      status: "pending",
      access_count: 0,
      created_at: "2024-05-01T00:00:00Z",
      updated_at: "2024-05-01T00:00:00Z",
    };
    expect(listing.seller).toBeNull();
    expect(listing.expires_at).toBeNull();
  });
});

// ── ListingListResponse ────────────────────────────────────────────────────

describe("ListingListResponse", () => {
  it("constructs a listing list response with results field", () => {
    const response: ListingListResponse = {
      total: 0,
      page: 1,
      page_size: 10,
      results: [],
    };
    expect(response.results).toBeDefined();
    expect(response.results).toHaveLength(0);
  });
});

// ── TransactionStatus ──────────────────────────────────────────────────────

describe("TransactionStatus", () => {
  it("accepts all eight transaction status literals", () => {
    const statuses: TransactionStatus[] = [
      "initiated",
      "payment_pending",
      "payment_confirmed",
      "delivered",
      "verified",
      "completed",
      "failed",
      "disputed",
    ];
    expect(statuses).toHaveLength(8);
  });
});

// ── Transaction ────────────────────────────────────────────────────────────

describe("Transaction", () => {
  it("constructs a completed transaction", () => {
    const tx: Transaction = {
      id: "tx-001",
      listing_id: "listing-001",
      buyer_id: "buyer-1",
      seller_id: "seller-1",
      amount_usdc: 0.05,
      status: "completed",
      payment_tx_hash: "0xdeadbeef",
      payment_network: "polygon",
      content_hash: "sha256:abc",
      delivered_hash: "sha256:def",
      verification_status: "verified",
      error_message: null,
      initiated_at: "2024-06-01T00:00:00Z",
      paid_at: "2024-06-01T00:01:00Z",
      delivered_at: "2024-06-01T00:02:00Z",
      verified_at: "2024-06-01T00:03:00Z",
      completed_at: "2024-06-01T00:04:00Z",
    };
    expect(tx.status).toBe("completed");
    expect(tx.error_message).toBeNull();
    expect(tx.payment_method).toBeUndefined();
  });

  it("constructs a failed transaction with error and simulated payment", () => {
    const tx: Transaction = {
      id: "tx-002",
      listing_id: "listing-002",
      buyer_id: "buyer-2",
      seller_id: "seller-2",
      amount_usdc: 0.1,
      status: "failed",
      payment_tx_hash: null,
      payment_network: null,
      content_hash: "sha256:ghi",
      delivered_hash: null,
      verification_status: "pending",
      error_message: "Delivery timeout",
      initiated_at: "2024-06-02T00:00:00Z",
      paid_at: null,
      delivered_at: null,
      verified_at: null,
      completed_at: null,
      payment_method: "simulated",
    };
    expect(tx.status).toBe("failed");
    expect(tx.error_message).toBe("Delivery timeout");
    expect(tx.payment_method).toBe("simulated");
  });

  it("accepts all three payment_method values", () => {
    const methods: Array<Transaction["payment_method"]> = [
      "balance",
      "fiat",
      "simulated",
    ];
    methods.forEach((method) => {
      expect(typeof method).toBe("string");
    });
  });
});

// ── TransactionListResponse ────────────────────────────────────────────────

describe("TransactionListResponse", () => {
  it("constructs a transaction list response", () => {
    const response: TransactionListResponse = {
      total: 0,
      page: 1,
      page_size: 25,
      transactions: [],
    };
    expect(response.transactions).toBeDefined();
  });
});

// ── ReputationResponse ─────────────────────────────────────────────────────

describe("ReputationResponse", () => {
  it("constructs a full reputation response", () => {
    const rep: ReputationResponse = {
      agent_id: "agent-1",
      agent_name: "DataBot",
      total_transactions: 100,
      successful_deliveries: 95,
      failed_deliveries: 5,
      verified_count: 90,
      verification_failures: 2,
      avg_response_ms: 120.5,
      total_volume_usdc: 50.0,
      composite_score: 0.93,
      last_calculated_at: "2024-06-01T00:00:00Z",
    };
    expect(rep.composite_score).toBe(0.93);
    expect(rep.avg_response_ms).toBe(120.5);
  });

  it("accepts null avg_response_ms for agents with no data", () => {
    const rep: ReputationResponse = {
      agent_id: "agent-2",
      agent_name: "NewBot",
      total_transactions: 0,
      successful_deliveries: 0,
      failed_deliveries: 0,
      verified_count: 0,
      verification_failures: 0,
      avg_response_ms: null,
      total_volume_usdc: 0,
      composite_score: 0,
      last_calculated_at: "2024-06-01T00:00:00Z",
    };
    expect(rep.avg_response_ms).toBeNull();
  });
});

// ── LeaderboardEntry / LeaderboardResponse ─────────────────────────────────

describe("LeaderboardEntry and LeaderboardResponse", () => {
  it("constructs a leaderboard entry", () => {
    const entry: LeaderboardEntry = {
      rank: 1,
      agent_id: "agent-1",
      agent_name: "TopBot",
      composite_score: 0.99,
      total_transactions: 500,
      total_volume_usdc: 250.0,
    };
    expect(entry.rank).toBe(1);
    expect(entry.composite_score).toBe(0.99);
  });

  it("constructs a leaderboard response with multiple entries", () => {
    const response: LeaderboardResponse = {
      entries: [
        { rank: 1, agent_id: "a1", agent_name: "Top", composite_score: 0.99, total_transactions: 100, total_volume_usdc: 50 },
        { rank: 2, agent_id: "a2", agent_name: "Second", composite_score: 0.95, total_transactions: 80, total_volume_usdc: 40 },
      ],
    };
    expect(response.entries).toHaveLength(2);
    expect(response.entries[0].rank).toBe(1);
  });
});

// ── FeedEvent ──────────────────────────────────────────────────────────────

describe("FeedEvent", () => {
  it("constructs a minimal feed event with required fields only", () => {
    const event: FeedEvent = {
      type: "listing.created",
      timestamp: "2024-06-01T00:00:00Z",
      data: { listing_id: "l-1" },
    };
    expect(event.type).toBe("listing.created");
    expect(event.data).toHaveProperty("listing_id");
  });

  it("constructs a rich feed event with all optional fields", () => {
    const event: FeedEvent = {
      type: "transaction.completed",
      timestamp: "2024-06-01T01:00:00Z",
      data: { tx_id: "tx-1" },
      event_id: "ev-001",
      seq: 42,
      event_type: "transaction.completed",
      occurred_at: "2024-06-01T01:00:00Z",
      agent_id: "agent-1",
      payload: { amount: 0.05 },
      signature: "sig123",
      signature_key_id: "key-1",
      delivery_attempt: 1,
      visibility: "public",
      topic: "public.market",
      target_agent_ids: ["agent-2"],
      target_creator_ids: ["creator-1"],
      schema_version: "1.0",
      blocked: false,
    };
    expect(event.visibility).toBe("public");
    expect(event.topic).toBe("public.market");
    expect(event.target_agent_ids).toContain("agent-2");
    expect(event.blocked).toBe(false);
  });

  it("accepts null agent_id", () => {
    const event: FeedEvent = {
      type: "system.notice",
      timestamp: "2024-06-01T00:00:00Z",
      data: {},
      agent_id: null,
    };
    expect(event.agent_id).toBeNull();
  });
});

// ── DiscoverParams ─────────────────────────────────────────────────────────

describe("DiscoverParams", () => {
  it("constructs empty params (all fields optional)", () => {
    const params: DiscoverParams = {};
    expect(Object.keys(params)).toHaveLength(0);
  });

  it("constructs fully-populated discover params", () => {
    const params: DiscoverParams = {
      q: "machine learning",
      category: "computation",
      min_price: 0.01,
      max_price: 1.0,
      min_quality: 0.7,
      max_age_hours: 24,
      seller_id: "seller-1",
      sort_by: "quality",
      page: 2,
      page_size: 10,
    };
    expect(params.q).toBe("machine learning");
    expect(params.category).toBe("computation");
    expect(params.sort_by).toBe("quality");
    expect(params.page).toBe(2);
  });

  it("accepts all four sort_by options", () => {
    const sortOptions: Array<DiscoverParams["sort_by"]> = [
      "price_asc",
      "price_desc",
      "freshness",
      "quality",
    ];
    sortOptions.forEach((s) => {
      const params: DiscoverParams = { sort_by: s };
      expect(params.sort_by).toBe(s);
    });
  });

  it("accepts empty string for category to reset filter", () => {
    const params: DiscoverParams = { category: "" };
    expect(params.category).toBe("");
  });
});

// ── ExpressDeliveryResponse ────────────────────────────────────────────────

describe("ExpressDeliveryResponse", () => {
  it("constructs an express delivery response", () => {
    const resp: ExpressDeliveryResponse = {
      listing_id: "l-1",
      transaction_id: "tx-1",
      content: "{ ... }",
      content_hash: "sha256:abc",
      price_usdc: 0.05,
      delivery_ms: 42,
      cache_hit: true,
    };
    expect(resp.cache_hit).toBe(true);
    expect(resp.delivery_ms).toBe(42);
    expect(resp.price_usdc).toBe(0.05);
  });
});

// ── AutoMatchResult / AutoMatchResponse ───────────────────────────────────

describe("AutoMatchResult and AutoMatchResponse", () => {
  it("constructs an auto match result", () => {
    const match: AutoMatchResult = {
      listing_id: "l-1",
      title: "Web Data Feed",
      category: "web_search",
      price_usdc: 0.03,
      quality_score: 0.9,
      freshness_at: "2024-06-01T00:00:00Z",
      seller_name: "DataBot",
      match_score: 0.95,
      savings_usdc: 0.02,
      savings_percent: 40.0,
    };
    expect(match.match_score).toBe(0.95);
    expect(match.savings_percent).toBe(40.0);
  });

  it("constructs an auto match response without purchase_result", () => {
    const resp: AutoMatchResponse = {
      matches: [],
      fresh_cost_estimate: 0.25,
    };
    expect(resp.purchase_result).toBeUndefined();
  });

  it("constructs an auto match response with purchase_result", () => {
    const resp: AutoMatchResponse = {
      matches: [],
      fresh_cost_estimate: 0.25,
      purchase_result: {
        listing_id: "l-1",
        transaction_id: "tx-1",
        content: "data",
        content_hash: "sha256:abc",
        price_usdc: 0.05,
        delivery_ms: 15,
        cache_hit: false,
      },
    };
    expect(resp.purchase_result).toBeDefined();
    expect(resp.purchase_result!.cache_hit).toBe(false);
  });
});

// ── TrendingQuery / TrendingResponse ──────────────────────────────────────

describe("TrendingQuery and TrendingResponse", () => {
  it("constructs a trending query", () => {
    const trend: TrendingQuery = {
      query_pattern: "crypto prices",
      category: "api_response",
      search_count: 150,
      unique_requesters: 30,
      velocity: 5.2,
      fulfillment_rate: 0.85,
      last_searched_at: "2024-06-01T00:00:00Z",
    };
    expect(trend.velocity).toBe(5.2);
    expect(trend.fulfillment_rate).toBe(0.85);
  });

  it("constructs a trending response with a time window", () => {
    const response: TrendingResponse = {
      time_window_hours: 24,
      trends: [],
    };
    expect(response.time_window_hours).toBe(24);
  });
});

// ── DemandGap / DemandGapsResponse ────────────────────────────────────────

describe("DemandGap and DemandGapsResponse", () => {
  it("constructs a demand gap with optional avg_max_price", () => {
    const gap: DemandGap = {
      query_pattern: "real-time forex",
      category: null,
      search_count: 50,
      unique_requesters: 12,
      avg_max_price: 0.1,
      fulfillment_rate: 0.2,
      first_searched_at: "2024-05-01T00:00:00Z",
    };
    expect(gap.avg_max_price).toBe(0.1);
    expect(gap.category).toBeNull();
  });

  it("accepts null avg_max_price", () => {
    const gap: DemandGap = {
      query_pattern: "unknown topic",
      category: "document_summary",
      search_count: 5,
      unique_requesters: 2,
      avg_max_price: null,
      fulfillment_rate: 0,
      first_searched_at: "2024-05-01T00:00:00Z",
    };
    expect(gap.avg_max_price).toBeNull();
  });

  it("constructs a demand gaps response", () => {
    const response: DemandGapsResponse = { gaps: [] };
    expect(response.gaps).toHaveLength(0);
  });
});

// ── Opportunity / OpportunitiesResponse ───────────────────────────────────

describe("Opportunity and OpportunitiesResponse", () => {
  it("constructs an opportunity with nullable category", () => {
    const opp: Opportunity = {
      id: "opp-1",
      query_pattern: "daily stock data",
      category: "api_response",
      estimated_revenue_usdc: 1.5,
      search_velocity: 10,
      competing_listings: 2,
      urgency_score: 0.8,
      created_at: "2024-06-01T00:00:00Z",
    };
    expect(opp.urgency_score).toBe(0.8);
    expect(opp.category).toBe("api_response");
  });

  it("constructs an opportunity with null category", () => {
    const opp: Opportunity = {
      id: "opp-2",
      query_pattern: "misc data",
      category: null,
      estimated_revenue_usdc: 0.5,
      search_velocity: 2,
      competing_listings: 0,
      urgency_score: 0.3,
      created_at: "2024-06-01T00:00:00Z",
    };
    expect(opp.category).toBeNull();
  });

  it("constructs an opportunities response", () => {
    const response: OpportunitiesResponse = { opportunities: [] };
    expect(response.opportunities).toHaveLength(0);
  });
});

// ── EarningsBreakdown ──────────────────────────────────────────────────────

describe("EarningsBreakdown", () => {
  it("constructs an earnings breakdown with timeline", () => {
    const entry: EarningsTimelineEntry = { date: "2024-06-01", earned: 1.5, spent: 0.5 };
    const breakdown: EarningsBreakdown = {
      agent_id: "agent-1",
      total_earned_usdc: 10.0,
      total_spent_usdc: 3.0,
      net_revenue_usdc: 7.0,
      earnings_by_category: { api_response: 5.0, computation: 5.0 },
      earnings_timeline: [entry],
    };
    expect(breakdown.net_revenue_usdc).toBe(7.0);
    expect(breakdown.earnings_timeline).toHaveLength(1);
    expect(breakdown.earnings_by_category["api_response"]).toBe(5.0);
  });
});

// ── AgentProfile ───────────────────────────────────────────────────────────

describe("AgentProfile", () => {
  it("constructs an agent profile with nullable rank fields", () => {
    const profile: AgentProfile = {
      agent_id: "agent-1",
      agent_name: "DataBot",
      unique_buyers_served: 10,
      total_listings_created: 50,
      total_cache_hits: 200,
      category_count: 3,
      categories: ["api_response", "web_search", "computation"],
      total_earned_usdc: 25.0,
      total_spent_usdc: 5.0,
      demand_gaps_filled: 4,
      avg_listing_quality: 0.88,
      total_data_bytes: 1048576,
      helpfulness_score: 0.92,
      helpfulness_rank: 3,
      earnings_rank: 5,
      primary_specialization: "api_response",
      specialization_tags: ["finance", "market-data"],
      last_calculated_at: "2024-06-01T00:00:00Z",
    };
    expect(profile.helpfulness_score).toBe(0.92);
    expect(profile.primary_specialization).toBe("api_response");
    expect(profile.specialization_tags).toContain("finance");
  });

  it("accepts null for rank and specialization on unranked agents", () => {
    const profile: AgentProfile = {
      agent_id: "agent-new",
      agent_name: "NewBot",
      unique_buyers_served: 0,
      total_listings_created: 0,
      total_cache_hits: 0,
      category_count: 0,
      categories: [],
      total_earned_usdc: 0,
      total_spent_usdc: 0,
      demand_gaps_filled: 0,
      avg_listing_quality: 0,
      total_data_bytes: 0,
      helpfulness_score: 0,
      helpfulness_rank: null,
      earnings_rank: null,
      primary_specialization: null,
      specialization_tags: [],
      last_calculated_at: "2024-06-01T00:00:00Z",
    };
    expect(profile.helpfulness_rank).toBeNull();
    expect(profile.earnings_rank).toBeNull();
    expect(profile.primary_specialization).toBeNull();
  });
});

// ── MultiLeaderboardEntry / MultiLeaderboardResponse ──────────────────────

describe("MultiLeaderboardEntry and MultiLeaderboardResponse", () => {
  it("constructs a multi-leaderboard entry with nullable scores", () => {
    const entry: MultiLeaderboardEntry = {
      rank: 1,
      agent_id: "agent-1",
      agent_name: "TopBot",
      primary_score: 0.99,
      secondary_label: "helpfulness",
      total_transactions: 500,
      helpfulness_score: 0.95,
      total_earned_usdc: 100.0,
    };
    expect(entry.rank).toBe(1);
    expect(entry.helpfulness_score).toBe(0.95);
  });

  it("accepts null helpfulness_score and total_earned_usdc", () => {
    const entry: MultiLeaderboardEntry = {
      rank: 2,
      agent_id: "agent-2",
      agent_name: "SecondBot",
      primary_score: 0.9,
      secondary_label: "volume",
      total_transactions: 200,
      helpfulness_score: null,
      total_earned_usdc: null,
    };
    expect(entry.helpfulness_score).toBeNull();
    expect(entry.total_earned_usdc).toBeNull();
  });

  it("constructs a multi-leaderboard response with board_type", () => {
    const response: MultiLeaderboardResponse = { board_type: "helpfulness", entries: [] };
    expect(response.board_type).toBe("helpfulness");
  });
});

// ── CDNStats ───────────────────────────────────────────────────────────────

describe("CDNStats", () => {
  it("constructs a CDN stats object with all tiers", () => {
    const cacheEntry: CacheStats = { hits: 10, misses: 2, size: 50, maxsize: 100, hit_rate: 0.83 };
    const stats: CDNStats = {
      overview: {
        total_requests: 1000,
        tier1_hits: 700,
        tier2_hits: 200,
        tier3_hits: 50,
        total_misses: 50,
      },
      hot_cache: {
        tier: "L1",
        entries: 50,
        bytes_used: 512000,
        bytes_max: 1048576,
        utilization_pct: 48.8,
        hits: 700,
        misses: 30,
        promotions: 10,
        evictions: 5,
        hit_rate: 0.959,
      },
      warm_cache: cacheEntry,
    };
    expect(stats.overview.total_requests).toBe(1000);
    expect(stats.hot_cache.tier).toBe("L1");
    expect(stats.hot_cache.hit_rate).toBeCloseTo(0.959);
    expect(stats.warm_cache.hits).toBe(10);
  });
});

// ── ZKProof / ZKProofListResponse / ZKVerifyResult / BloomCheckResult ─────

describe("ZKP types", () => {
  it("constructs a ZKProof for each proof type", () => {
    const proofTypes: Array<ZKProof["proof_type"]> = [
      "merkle_root",
      "schema",
      "bloom_filter",
      "metadata",
    ];
    proofTypes.forEach((pt) => {
      const proof: ZKProof = {
        id: `proof-${pt}`,
        proof_type: pt,
        commitment: "0xcommit",
        public_inputs: { listing_id: "l-1" },
        created_at: "2024-06-01T00:00:00Z",
      };
      expect(proof.proof_type).toBe(pt);
    });
  });

  it("constructs a ZKProofListResponse", () => {
    const response: ZKProofListResponse = {
      listing_id: "l-1",
      proofs: [],
      count: 0,
    };
    expect(response.count).toBe(0);
  });

  it("constructs a ZKVerifyResult", () => {
    const result: ZKVerifyResult = {
      listing_id: "l-1",
      verified: true,
      checks: {
        merkle: { passed: true, details: { root: "abc" } },
        schema: { passed: false },
      },
      proof_types_available: ["merkle_root", "schema"],
    };
    expect(result.verified).toBe(true);
    expect(result.checks["merkle"].passed).toBe(true);
    expect(result.checks["schema"]).not.toHaveProperty("details");
  });

  it("constructs a BloomCheckResult", () => {
    const result: BloomCheckResult = {
      listing_id: "l-1",
      word: "AI",
      probably_present: true,
      note: "Bloom filter indicates probable presence",
    };
    expect(result.probably_present).toBe(true);
  });
});

// ── CatalogEntry / CatalogSearchResponse / CatalogSubscription ────────────

describe("Catalog types", () => {
  it("constructs a catalog entry", () => {
    const entry: CatalogEntry = {
      id: "cat-1",
      agent_id: "agent-1",
      namespace: "finance",
      topic: "market-prices",
      description: "Real-time market prices",
      schema_json: { type: "object", properties: {} },
      price_range: [0.01, 0.5],
      quality_avg: 0.9,
      active_listings_count: 5,
      status: "active",
      created_at: "2024-06-01T00:00:00Z",
    };
    expect(entry.namespace).toBe("finance");
    expect(entry.price_range[0]).toBe(0.01);
    expect(entry.price_range[1]).toBe(0.5);
  });

  it("constructs a catalog search response", () => {
    const response: CatalogSearchResponse = {
      entries: [],
      total: 0,
      page: 1,
      page_size: 10,
    };
    expect(response.entries).toHaveLength(0);
  });

  it("constructs a catalog subscription", () => {
    const sub: CatalogSubscription = {
      id: "sub-1",
      namespace_pattern: "finance.*",
      topic_pattern: "*",
      notify_via: "webhook",
      status: "active",
    };
    expect(sub.namespace_pattern).toBe("finance.*");
    expect(sub.notify_via).toBe("webhook");
  });
});

// ── RoutingStrategy / RoutingStrategyInfo ─────────────────────────────────

describe("RoutingStrategy and RoutingStrategyInfo", () => {
  it("accepts all seven routing strategy literals", () => {
    const strategies: RoutingStrategy[] = [
      "cheapest",
      "fastest",
      "highest_quality",
      "best_value",
      "round_robin",
      "weighted_random",
      "locality",
    ];
    expect(strategies).toHaveLength(7);
  });

  it("constructs a routing strategy info", () => {
    const info: RoutingStrategyInfo = {
      strategies: ["cheapest", "fastest"],
      default: "best_value",
      descriptions: {
        cheapest: "Route to cheapest provider",
        fastest: "Route to fastest provider",
      },
    };
    expect(info.default).toBe("best_value");
    expect(info.strategies).toContain("fastest");
  });
});

// ── PriceSuggestion / DemandMatch ──────────────────────────────────────────

describe("PriceSuggestion and DemandMatch", () => {
  it("constructs a price suggestion", () => {
    const suggestion: PriceSuggestion = {
      suggested_price: 0.08,
      category: "api_response",
      quality_score: 0.85,
      competitors: 5,
      median_price: 0.07,
      price_range: [0.02, 0.15],
      demand_searches: 120,
      strategy: "competitive",
    };
    expect(suggestion.suggested_price).toBe(0.08);
    expect(suggestion.price_range[0]).toBe(0.02);
  });

  it("constructs a demand match", () => {
    const match: DemandMatch = {
      demand_id: "dem-1",
      query_pattern: "news headlines",
      category: "web_search",
      velocity: 3.5,
      total_searches: 75,
      avg_max_price: 0.04,
      fulfillment_rate: 0.6,
      opportunity: "medium",
    };
    expect(match.velocity).toBe(3.5);
    expect(match.opportunity).toBe("medium");
  });
});

// ── MCPHealth ──────────────────────────────────────────────────────────────

describe("MCPHealth", () => {
  it("constructs an MCP health response", () => {
    const health: MCPHealth = {
      status: "ok",
      protocol_version: "2024-11",
      server: "agentchains-mcp",
      version: "1.0.0",
      active_sessions: 3,
      tools_count: 12,
      resources_count: 5,
    };
    expect(health.protocol_version).toBe("2024-11");
    expect(health.tools_count).toBe(12);
  });
});

// ── TokenAccount / TokenLedgerEntry / TokenLedgerResponse ─────────────────

describe("Billing token types", () => {
  it("constructs a token account", () => {
    const account: TokenAccount = {
      id: "acc-1",
      agent_id: "agent-1",
      balance: 10.5,
      total_deposited: 20.0,
      total_earned: 5.0,
      total_spent: 14.5,
      total_fees_paid: 0.5,
      created_at: "2024-01-01T00:00:00Z",
      updated_at: "2024-06-01T00:00:00Z",
    };
    expect(account.balance).toBe(10.5);
    expect(account.agent_id).toBe("agent-1");
  });

  it("accepts null agent_id for system accounts", () => {
    const account: TokenAccount = {
      id: "acc-sys",
      agent_id: null,
      balance: 1000.0,
      total_deposited: 5000.0,
      total_earned: 0,
      total_spent: 4000.0,
      total_fees_paid: 100.0,
      created_at: "2024-01-01T00:00:00Z",
      updated_at: "2024-06-01T00:00:00Z",
    };
    expect(account.agent_id).toBeNull();
  });

  it("constructs a token ledger entry", () => {
    const entry: TokenLedgerEntry = {
      id: "ledger-1",
      from_account_id: "acc-1",
      to_account_id: "acc-2",
      amount: 5.0,
      fee_amount: 0.01,
      tx_type: "transfer",
      reference_id: "tx-1",
      reference_type: "transaction",
      memo: "Payment for listing",
      created_at: "2024-06-01T00:00:00Z",
    };
    expect(entry.tx_type).toBe("transfer");
    expect(entry.fee_amount).toBe(0.01);
  });

  it("constructs a token ledger response", () => {
    const response: TokenLedgerResponse = {
      entries: [],
      total: 0,
      page: 1,
      page_size: 50,
    };
    expect(response.entries).toHaveLength(0);
  });
});

// ── TokenDeposit / WalletBalanceResponse / DepositResponse / TransferResponse ──

describe("Wallet types", () => {
  it("constructs a token deposit", () => {
    const deposit: TokenDeposit = {
      id: "dep-1",
      agent_id: "agent-1",
      amount_usd: 10.0,
      status: "completed",
      payment_method: "stripe",
      payment_ref: "pi_123",
      created_at: "2024-06-01T00:00:00Z",
      completed_at: "2024-06-01T00:01:00Z",
    };
    expect(deposit.status).toBe("completed");
    expect(deposit.amount_usd).toBe(10.0);
  });

  it("accepts all four deposit status values", () => {
    const statuses: Array<TokenDeposit["status"]> = [
      "pending",
      "completed",
      "failed",
      "refunded",
    ];
    statuses.forEach((s) => {
      expect(typeof s).toBe("string");
    });
  });

  it("constructs a wallet balance response", () => {
    const balance: WalletBalanceResponse = {
      balance: 5.25,
      total_earned: 10.0,
      total_spent: 4.5,
      total_deposited: 20.0,
      total_fees_paid: 0.25,
    };
    expect(balance.balance).toBe(5.25);
  });

  it("constructs a deposit response with nullable dates", () => {
    const resp: DepositResponse = {
      id: "dep-2",
      agent_id: "agent-1",
      amount_usd: 5.0,
      currency: "USD",
      status: "pending",
      payment_method: "fiat",
      payment_ref: null,
      created_at: null,
      completed_at: null,
    };
    expect(resp.payment_ref).toBeNull();
    expect(resp.created_at).toBeNull();
  });

  it("constructs a transfer response", () => {
    const resp: TransferResponse = {
      id: "xfer-1",
      amount: 2.5,
      fee_amount: 0.05,
      tx_type: "transfer",
      memo: "Test transfer",
      created_at: "2024-06-01T00:00:00Z",
    };
    expect(resp.amount).toBe(2.5);
    expect(resp.memo).toBe("Test transfer");
  });

  it("constructs a transfer response with null memo and created_at", () => {
    const resp: TransferResponse = {
      id: "xfer-2",
      amount: 1.0,
      fee_amount: 0.02,
      tx_type: "fee",
      memo: null,
      created_at: null,
    };
    expect(resp.memo).toBeNull();
    expect(resp.created_at).toBeNull();
  });
});

// ── Creator Economy ────────────────────────────────────────────────────────

describe("Creator Economy types", () => {
  it("constructs a creator with all fields", () => {
    const creator: Creator = {
      id: "creator-1",
      email: "creator@example.com",
      display_name: "Alice",
      phone: "+1-555-0100",
      country: "US",
      payout_method: "bank",
      status: "active",
      created_at: "2024-01-01T00:00:00Z",
      updated_at: "2024-06-01T00:00:00Z",
    };
    expect(creator.payout_method).toBe("bank");
    expect(creator.status).toBe("active");
  });

  it("accepts null phone and country, and 'none' payout_method", () => {
    const creator: Creator = {
      id: "creator-2",
      email: "anon@example.com",
      display_name: "Anon",
      phone: null,
      country: null,
      payout_method: "none",
      status: "pending_verification",
      created_at: "2024-06-01T00:00:00Z",
      updated_at: "2024-06-01T00:00:00Z",
    };
    expect(creator.phone).toBeNull();
    expect(creator.payout_method).toBe("none");
  });

  it("accepts all payout_method values", () => {
    const methods: Array<Creator["payout_method"]> = ["none", "upi", "bank", "gift_card"];
    expect(methods).toHaveLength(4);
  });

  it("constructs a creator auth response", () => {
    const creator: Creator = {
      id: "c-1", email: "a@b.com", display_name: "A", phone: null, country: null,
      payout_method: "none", status: "active",
      created_at: "2024-01-01T00:00:00Z", updated_at: "2024-01-01T00:00:00Z",
    };
    const auth: CreatorAuthResponse = { creator, token: "jwt.token.here" };
    expect(auth.token).toBe("jwt.token.here");
  });

  it("constructs a creator agent", () => {
    const agent: CreatorAgent = {
      agent_id: "agent-1",
      agent_name: "BotAlpha",
      agent_type: "seller",
      status: "active",
      total_earned: 5.0,
      total_spent: 1.0,
      balance: 4.0,
    };
    expect(agent.balance).toBe(4.0);
  });

  it("constructs a creator dashboard", () => {
    const dashboard: CreatorDashboard = {
      creator_balance: 50.0,
      creator_total_earned: 100.0,
      agents_count: 3,
      agents: [],
      total_agent_earnings: 80.0,
      total_agent_spent: 30.0,
    };
    expect(dashboard.agents_count).toBe(3);
  });

  it("constructs a savings summary", () => {
    const summary: SavingsSummary = {
      money_saved_for_others_usd: 15.5,
      fresh_cost_estimate_total_usd: 45.0,
    };
    expect(summary.money_saved_for_others_usd).toBe(15.5);
  });
});

// ── V2 Dashboard types ─────────────────────────────────────────────────────

describe("V2 dashboard types", () => {
  it("constructs AgentDashboardV2 with nullable updated_at", () => {
    const dash: AgentDashboardV2 = {
      agent_id: "agent-1",
      money_received_usd: 10.0,
      money_spent_usd: 2.0,
      info_used_count: 50,
      other_agents_served_count: 15,
      data_served_bytes: 2097152,
      savings: { money_saved_for_others_usd: 5.0, fresh_cost_estimate_total_usd: 20.0 },
      trust_status: "verified",
      trust_tier: "T2",
      trust_score: 0.88,
      updated_at: null,
    };
    expect(dash.trust_tier).toBe("T2");
    expect(dash.updated_at).toBeNull();
  });

  it("constructs CreatorDashboardV2", () => {
    const dash: CreatorDashboardV2 = {
      creator_id: "creator-1",
      creator_balance_usd: 100.0,
      creator_total_earned_usd: 200.0,
      total_agent_earnings_usd: 150.0,
      total_agent_spent_usd: 50.0,
      total_agents: 5,
      active_agents: 3,
      money_saved_for_others_usd: 20.0,
      data_served_bytes: 5242880,
      updated_at: "2024-06-01T00:00:00Z",
    };
    expect(dash.active_agents).toBe(3);
    expect(dash.data_served_bytes).toBe(5242880);
  });

  it("constructs AgentPublicDashboardV2", () => {
    const dash: AgentPublicDashboardV2 = {
      agent_id: "agent-1",
      agent_name: "PublicBot",
      money_received_usd: 5.0,
      info_used_count: 10,
      other_agents_served_count: 3,
      data_served_bytes: 1024,
      money_saved_for_others_usd: 2.0,
      trust_status: "provisional",
      trust_tier: "T1",
      trust_score: 0.5,
      updated_at: null,
    };
    expect(dash.trust_tier).toBe("T1");
  });

  it("constructs AdminOverviewV2", () => {
    const overview: AdminOverviewV2 = {
      environment: "production",
      total_agents: 100,
      active_agents: 75,
      total_listings: 500,
      active_listings: 350,
      total_transactions: 2000,
      completed_transactions: 1900,
      platform_volume_usd: 1000.0,
      trust_weighted_revenue_usd: 950.0,
      updated_at: "2024-06-01T00:00:00Z",
    };
    expect(overview.environment).toBe("production");
    expect(overview.active_agents).toBe(75);
  });

  it("constructs AdminFinanceV2 with top_sellers array", () => {
    const finance: AdminFinanceV2 = {
      platform_volume_usd: 10000.0,
      completed_transaction_count: 500,
      payout_pending_count: 10,
      payout_pending_usd: 50.0,
      payout_processing_count: 5,
      payout_processing_usd: 25.0,
      top_sellers_by_revenue: [
        { agent_id: "a1", agent_name: "BestBot", money_received_usd: 500.0 },
      ],
      updated_at: "2024-06-01T00:00:00Z",
    };
    expect(finance.top_sellers_by_revenue).toHaveLength(1);
    expect(finance.top_sellers_by_revenue[0].money_received_usd).toBe(500.0);
  });

  it("constructs AdminUsageV2 with category_breakdown array", () => {
    const usage: AdminUsageV2 = {
      info_used_count: 1000,
      data_served_bytes: 10485760,
      unique_buyers_count: 50,
      unique_sellers_count: 20,
      money_saved_for_others_usd: 100.0,
      category_breakdown: [
        { category: "api_response", usage_count: 600, volume_usd: 30.0, money_saved_usd: 60.0 },
      ],
      updated_at: "2024-06-01T00:00:00Z",
    };
    expect(usage.category_breakdown).toHaveLength(1);
    expect(usage.category_breakdown[0].category).toBe("api_response");
  });

  it("constructs AdminAgentsV2 with entries", () => {
    const row: AdminAgentsRowV2 = {
      agent_id: "a-1",
      agent_name: "Bot",
      status: "active",
      trust_status: "verified",
      trust_tier: "T2",
      trust_score: 0.9,
      money_received_usd: 50.0,
      info_used_count: 100,
      other_agents_served_count: 20,
      data_served_bytes: 512000,
    };
    const list: AdminAgentsV2 = { total: 1, page: 1, page_size: 10, entries: [row] };
    expect(list.entries).toHaveLength(1);
    expect(list.entries[0].trust_tier).toBe("T2");
  });

  it("constructs AdminSecurityEventsV2", () => {
    const events: AdminSecurityEventsV2 = {
      total: 1,
      page: 1,
      page_size: 10,
      events: [
        {
          id: "ev-1",
          event_type: "brute_force",
          severity: "high",
          agent_id: null,
          creator_id: "creator-1",
          ip_address: "192.168.1.1",
          details: { attempts: 10 },
          created_at: "2024-06-01T00:00:00Z",
        },
      ],
    };
    expect(events.events[0].severity).toBe("high");
    expect(events.events[0].agent_id).toBeNull();
  });

  it("constructs OpenMarketAnalyticsV2", () => {
    const analytics: OpenMarketAnalyticsV2 = {
      generated_at: "2024-06-01T00:00:00Z",
      total_agents: 50,
      total_listings: 200,
      total_completed_transactions: 1000,
      platform_volume_usd: 5000.0,
      total_money_saved_usd: 1000.0,
      top_agents_by_revenue: [
        { agent_id: "a1", agent_name: "Top", money_received_usd: 500.0 },
      ],
      top_agents_by_usage: [
        { agent_id: "a2", agent_name: "Busy", info_used_count: 300 },
      ],
      top_categories_by_usage: [
        { category: "api_response", usage_count: 600, volume_usd: 30.0, money_saved_usd: 10.0 },
      ],
    };
    expect(analytics.total_agents).toBe(50);
    expect(analytics.top_agents_by_revenue[0].money_received_usd).toBe(500.0);
  });
});

// ── CreatorWallet / RedemptionRequest / RedemptionMethodInfo ───────────────

describe("Creator wallet and redemption types", () => {
  it("constructs a creator wallet", () => {
    const wallet: CreatorWallet = {
      balance: 25.0,
      total_earned: 50.0,
      total_spent: 10.0,
      total_deposited: 30.0,
      total_fees_paid: 5.0,
    };
    expect(wallet.balance).toBe(25.0);
  });

  it("constructs a redemption request with all fields", () => {
    const req: RedemptionRequest = {
      id: "red-1",
      creator_id: "creator-1",
      redemption_type: "bank_withdrawal",
      amount_usd: 50.0,
      currency: "USD",
      status: "processing",
      payout_ref: null,
      admin_notes: "",
      rejection_reason: "",
      created_at: "2024-06-01T00:00:00Z",
      processed_at: null,
      completed_at: null,
    };
    expect(req.redemption_type).toBe("bank_withdrawal");
    expect(req.status).toBe("processing");
    expect(req.payout_ref).toBeNull();
  });

  it("accepts all redemption_type values", () => {
    const types: Array<RedemptionRequest["redemption_type"]> = [
      "api_credits",
      "gift_card",
      "bank_withdrawal",
      "upi",
    ];
    expect(types).toHaveLength(4);
  });

  it("accepts all redemption status values", () => {
    const statuses: Array<RedemptionRequest["status"]> = [
      "pending",
      "processing",
      "completed",
      "failed",
      "rejected",
    ];
    expect(statuses).toHaveLength(5);
  });

  it("constructs a redemption method info", () => {
    const method: RedemptionMethodInfo = {
      type: "bank_withdrawal",
      label: "Bank Transfer",
      min_usd: 10.0,
      processing_time: "3-5 business days",
      available: true,
    };
    expect(method.available).toBe(true);
    expect(method.min_usd).toBe(10.0);
  });
});

// ── Pipeline types ─────────────────────────────────────────────────────────

describe("Pipeline types", () => {
  it("constructs a PipelineToolCall", () => {
    const call: PipelineToolCall = {
      name: "web_search",
      input: { query: "latest AI news" },
      output: { results: ["item1", "item2"] },
    };
    expect(call.name).toBe("web_search");
    expect(call.output).toBeDefined();
  });

  it("constructs a PipelineToolCall without output", () => {
    const call: PipelineToolCall = {
      name: "compute",
      input: { expression: "2+2" },
    };
    expect(call.output).toBeUndefined();
  });

  it("constructs a PipelineStep in each status", () => {
    const statuses: Array<PipelineStep["status"]> = [
      "running",
      "completed",
      "failed",
      "waiting",
    ];
    statuses.forEach((status) => {
      const step: PipelineStep = {
        id: `step-${status}`,
        agentId: "agent-1",
        agentName: "Bot",
        action: "process",
        status,
        startedAt: "2024-06-01T00:00:00Z",
      };
      expect(step.status).toBe(status);
    });
  });

  it("constructs a completed PipelineStep with all optional fields", () => {
    const step: PipelineStep = {
      id: "step-1",
      agentId: "agent-1",
      agentName: "DataBot",
      action: "fetch_data",
      status: "completed",
      startedAt: "2024-06-01T00:00:00Z",
      completedAt: "2024-06-01T00:00:05Z",
      latencyMs: 5000,
      toolCall: { name: "fetch", input: { url: "https://api.example.com" } },
    };
    expect(step.latencyMs).toBe(5000);
    expect(step.toolCall!.name).toBe("fetch");
    expect(step.error).toBeUndefined();
  });

  it("constructs a failed PipelineStep with error", () => {
    const step: PipelineStep = {
      id: "step-err",
      agentId: "agent-1",
      agentName: "Bot",
      action: "validate",
      status: "failed",
      startedAt: "2024-06-01T00:00:00Z",
      error: "Timeout after 30s",
    };
    expect(step.error).toBe("Timeout after 30s");
  });

  it("constructs an AgentExecution", () => {
    const exec: AgentExecution = {
      agentId: "agent-1",
      agentName: "DataBot",
      status: "active",
      steps: [],
      startedAt: "2024-06-01T00:00:00Z",
      lastActivityAt: "2024-06-01T00:01:00Z",
    };
    expect(exec.status).toBe("active");
    expect(exec.steps).toHaveLength(0);
  });
});

// ── SystemMetrics ──────────────────────────────────────────────────────────

describe("SystemMetrics", () => {
  it("constructs a system metrics object composing health and CDN stats", () => {
    const cacheEntry: CacheStats = { hits: 1, misses: 0, size: 1, maxsize: 10, hit_rate: 1.0 };
    const metrics: SystemMetrics = {
      health: {
        status: "healthy",
        version: "1.0.0",
        agents_count: 5,
        listings_count: 20,
        transactions_count: 100,
      },
      cdn: {
        overview: {
          total_requests: 200,
          tier1_hits: 150,
          tier2_hits: 40,
          tier3_hits: 5,
          total_misses: 5,
        },
        hot_cache: {
          tier: "L1",
          entries: 10,
          bytes_used: 1024,
          bytes_max: 4096,
          utilization_pct: 25.0,
          hits: 150,
          misses: 5,
          promotions: 2,
          evictions: 1,
          hit_rate: 0.968,
        },
        warm_cache: cacheEntry,
      },
    };
    expect(metrics.health.status).toBe("healthy");
    expect(metrics.cdn.overview.total_requests).toBe(200);
  });
});

// ── Agent Trust and Memory types ───────────────────────────────────────────

describe("AgentTrustProfile and related types", () => {
  const buildTrustProfile = (): AgentTrustProfile => ({
    agent_id: "agent-1",
    agent_trust_status: "verified",
    agent_trust_tier: "T2",
    agent_trust_score: 0.88,
    stage_scores: {
      identity: 0.9,
      runtime: 0.85,
      knowledge: 0.88,
      memory: 0.82,
      abuse: 0.95,
    },
    knowledge_challenge_summary: { passed: 4, failed: 1 },
    memory_provenance: { snapshots: 2 },
    updated_at: "2024-06-01T00:00:00Z",
  });

  it("constructs a full AgentTrustProfile", () => {
    const profile = buildTrustProfile();
    expect(profile.agent_trust_status).toBe("verified");
    expect(profile.agent_trust_tier).toBe("T2");
    expect(profile.stage_scores.identity).toBe(0.9);
  });

  it("accepts all four trust status values", () => {
    const statuses: Array<AgentTrustProfile["agent_trust_status"]> = [
      "unverified", "provisional", "verified", "restricted",
    ];
    expect(statuses).toHaveLength(4);
  });

  it("accepts all four trust tier values", () => {
    const tiers: Array<AgentTrustProfile["agent_trust_tier"]> = [
      "T0", "T1", "T2", "T3",
    ];
    expect(tiers).toHaveLength(4);
  });

  it("constructs AgentTrustPublicSummary", () => {
    const summary: AgentTrustPublicSummary = {
      agent_id: "agent-1",
      agent_trust_status: "provisional",
      agent_trust_tier: "T1",
      agent_trust_score: 0.55,
      updated_at: null,
    };
    expect(summary.agent_trust_tier).toBe("T1");
    expect(summary.updated_at).toBeNull();
  });

  it("constructs AgentOnboardResponse extending AgentTrustProfile", () => {
    const onboard: AgentOnboardResponse = {
      ...buildTrustProfile(),
      onboarding_session_id: "session-123",
      agent_id: "agent-1",
      agent_name: "OnboardBot",
      agent_jwt_token: "jwt.token.here",
      agent_card_url: "https://agentchains.io/agents/agent-1/card",
      stream_token: "stream-tok-abc",
    };
    expect(onboard.agent_jwt_token).toBe("jwt.token.here");
    expect(onboard.agent_trust_status).toBe("verified");
  });

  it("constructs RuntimeAttestationResponse", () => {
    const resp: RuntimeAttestationResponse = {
      attestation_id: "attest-1",
      stage_runtime_score: 0.9,
      profile: buildTrustProfile(),
    };
    expect(resp.stage_runtime_score).toBe(0.9);
    expect(resp.profile.agent_trust_tier).toBe("T2");
  });

  it("constructs KnowledgeChallengeResponse for passed and failed", () => {
    const passed: KnowledgeChallengeResponse = {
      agent_id: "agent-1",
      status: "passed",
      severe_safety_failure: false,
      stage_knowledge_score: 0.88,
      knowledge_challenge_summary: { passed: 8, failed: 2 },
      profile: buildTrustProfile(),
    };
    expect(passed.status).toBe("passed");
    expect(passed.severe_safety_failure).toBe(false);

    const failed: KnowledgeChallengeResponse = {
      agent_id: "agent-2",
      status: "failed",
      severe_safety_failure: true,
      stage_knowledge_score: 0.2,
      knowledge_challenge_summary: { passed: 2, failed: 8 },
      profile: buildTrustProfile(),
    };
    expect(failed.severe_safety_failure).toBe(true);
  });
});

// ── MemorySnapshot / MemoryImportResponse / MemoryVerifyResponse ───────────

describe("Memory types", () => {
  const buildSnapshot = (): MemorySnapshot => ({
    snapshot_id: "snap-1",
    agent_id: "agent-1",
    source_type: "conversation",
    label: "Session logs",
    manifest: { files: 3 },
    merkle_root: "0xmerkle",
    status: "verified",
    total_records: 100,
    total_chunks: 10,
    created_at: "2024-06-01T00:00:00Z",
    verified_at: "2024-06-01T00:05:00Z",
  });

  it("constructs a MemorySnapshot with all fields", () => {
    const snap = buildSnapshot();
    expect(snap.merkle_root).toBe("0xmerkle");
    expect(snap.status).toBe("verified");
  });

  it("accepts all documented status values including arbitrary strings", () => {
    const statuses = ["imported", "verified", "failed", "quarantined", "custom-status"];
    statuses.forEach((s) => {
      const snap: MemorySnapshot = { ...buildSnapshot(), status: s };
      expect(snap.status).toBe(s);
    });
  });

  it("accepts null created_at and verified_at", () => {
    const snap: MemorySnapshot = { ...buildSnapshot(), created_at: null, verified_at: null };
    expect(snap.created_at).toBeNull();
    expect(snap.verified_at).toBeNull();
  });

  it("constructs a MemoryImportResponse", () => {
    const profile: AgentTrustProfile = {
      agent_id: "agent-1",
      agent_trust_status: "provisional",
      agent_trust_tier: "T1",
      agent_trust_score: 0.6,
      stage_scores: { identity: 0.7, runtime: 0.6, knowledge: 0.5, memory: 0.5, abuse: 0.9 },
      knowledge_challenge_summary: {},
      memory_provenance: {},
      updated_at: null,
    };
    const resp: MemoryImportResponse = {
      snapshot: buildSnapshot(),
      chunk_hashes: ["hash1", "hash2", "hash3"],
      trust_profile: profile,
    };
    expect(resp.chunk_hashes).toHaveLength(3);
    expect(resp.trust_profile.agent_trust_status).toBe("provisional");
  });

  it("constructs a MemoryVerifyResponse", () => {
    const profile: AgentTrustProfile = {
      agent_id: "agent-1",
      agent_trust_status: "verified",
      agent_trust_tier: "T2",
      agent_trust_score: 0.85,
      stage_scores: { identity: 0.9, runtime: 0.8, knowledge: 0.85, memory: 0.88, abuse: 0.9 },
      knowledge_challenge_summary: {},
      memory_provenance: {},
      updated_at: "2024-06-01T00:00:00Z",
    };
    const resp: MemoryVerifyResponse = {
      snapshot: buildSnapshot(),
      verification_run_id: "run-1",
      status: "completed",
      score: 0.92,
      sampled_entries: [{ key: "value" }],
      trust_profile: profile,
    };
    expect(resp.score).toBe(0.92);
    expect(resp.sampled_entries).toHaveLength(1);
  });
});

// ── StreamTokenResponse / AdminStreamTokenResponse ─────────────────────────

describe("Stream token types", () => {
  it("constructs a StreamTokenResponse", () => {
    const resp: StreamTokenResponse = {
      agent_id: "agent-1",
      stream_token: "stream-abc-123",
      expires_in_seconds: 3600,
      expires_at: "2024-06-01T01:00:00Z",
      ws_url: "wss://agentchains.io/ws",
      allowed_topics: ["public.market", "private.agent"],
    };
    expect(resp.expires_in_seconds).toBe(3600);
    expect(resp.allowed_topics).toContain("public.market");
  });

  it("constructs an AdminStreamTokenResponse", () => {
    const resp: AdminStreamTokenResponse = {
      creator_id: "creator-1",
      stream_token: "admin-stream-xyz",
      ws_url: "wss://agentchains.io/ws/admin",
      allowed_topics: ["private.admin"],
    };
    expect(resp.creator_id).toBe("creator-1");
    expect(resp.allowed_topics).toContain("private.admin");
  });
});

// ── WebhookSubscription ────────────────────────────────────────────────────

describe("WebhookSubscription", () => {
  it("constructs a webhook subscription without secret", () => {
    const sub: WebhookSubscription = {
      id: "wh-1",
      agent_id: "agent-1",
      callback_url: "https://example.com/webhook",
      event_types: ["listing.created", "transaction.completed"],
      status: "active",
      failure_count: 0,
      last_delivery_at: null,
      created_at: null,
    };
    expect(sub.event_types).toContain("listing.created");
    expect(sub.failure_count).toBe(0);
    expect(sub.secret).toBeUndefined();
  });

  it("constructs a webhook subscription with secret", () => {
    const sub: WebhookSubscription = {
      id: "wh-2",
      agent_id: "agent-2",
      callback_url: "https://secure.example.com/hook",
      event_types: ["transaction.completed"],
      status: "active",
      failure_count: 0,
      last_delivery_at: "2024-06-01T00:00:00Z",
      created_at: "2024-05-01T00:00:00Z",
      secret: "whsec_supersecret",
    };
    expect(sub.secret).toBe("whsec_supersecret");
    expect(sub.last_delivery_at).toBeTruthy();
  });
});
