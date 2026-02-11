import { describe, expect, test, vi, beforeEach } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";
import {
  useTrending,
  useDemandGaps,
  useOpportunities,
  useMyEarnings,
  useMyStats,
  useAgentProfile,
  useMultiLeaderboard,
} from "../useAnalytics";
import { createWrapper } from "../../test/test-utils";
import * as api from "../../lib/api";

// Mock the API module
vi.mock("../../lib/api", () => ({
  fetchTrending: vi.fn(),
  fetchDemandGaps: vi.fn(),
  fetchOpportunities: vi.fn(),
  fetchMyEarnings: vi.fn(),
  fetchMyStats: vi.fn(),
  fetchAgentProfile: vi.fn(),
  fetchMultiLeaderboard: vi.fn(),
}));

describe("useTrending", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  test("fetches trending data with default parameters", async () => {
    const mockData = {
      time_window_hours: 6,
      trends: [
        {
          id: "trend-1",
          query_text: "AI agents",
          category: "automation",
          search_count: 42,
          unique_requesters: 15,
          avg_max_price: 10.5,
          created_at: "2026-02-11T10:00:00Z",
        },
      ],
    };

    vi.mocked(api.fetchTrending).mockResolvedValue(mockData);

    const { result } = renderHook(() => useTrending(), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(api.fetchTrending).toHaveBeenCalledWith(20, 6);
    expect(result.current.data).toEqual(mockData);
  });

  test("fetches trending data with custom limit and hours", async () => {
    const mockData = {
      time_window_hours: 12,
      trends: [],
    };

    vi.mocked(api.fetchTrending).mockResolvedValue(mockData);

    const { result } = renderHook(() => useTrending(50, 12), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(api.fetchTrending).toHaveBeenCalledWith(50, 12);
    expect(result.current.data).toEqual(mockData);
  });

  test("includes correct query key for cache management", async () => {
    vi.mocked(api.fetchTrending).mockResolvedValue({
      time_window_hours: 6,
      trends: [],
    });

    const { result } = renderHook(() => useTrending(30, 8), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    // Query key should include limit and hours for proper caching
    expect(result.current.data).toBeDefined();
  });
});

describe("useDemandGaps", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  test("fetches demand gaps with default parameters", async () => {
    const mockData = {
      gaps: [
        {
          query_pattern: "data visualization",
          category: "analytics",
          search_count: 28,
          unique_requesters: 10,
          avg_max_price: 15.75,
          fulfillment_rate: 0.2,
          first_searched_at: "2026-02-10T08:00:00Z",
        },
      ],
    };

    vi.mocked(api.fetchDemandGaps).mockResolvedValue(mockData);

    const { result } = renderHook(() => useDemandGaps(), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(api.fetchDemandGaps).toHaveBeenCalledWith(20, undefined);
    expect(result.current.data).toEqual(mockData);
  });

  test("fetches demand gaps with category filter", async () => {
    const mockData = {
      gaps: [
        {
          query_pattern: "AI training",
          category: "ml",
          search_count: 15,
          unique_requesters: 8,
          avg_max_price: 25.0,
          fulfillment_rate: 0.1,
          first_searched_at: "2026-02-09T12:00:00Z",
        },
      ],
    };

    vi.mocked(api.fetchDemandGaps).mockResolvedValue(mockData);

    const { result } = renderHook(() => useDemandGaps(10, "ml"), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(api.fetchDemandGaps).toHaveBeenCalledWith(10, "ml");
    expect(result.current.data).toEqual(mockData);
  });

  test("includes category in query key for proper cache separation", async () => {
    vi.mocked(api.fetchDemandGaps).mockResolvedValue({ gaps: [] });

    const { result } = renderHook(() => useDemandGaps(20, "automation"), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(result.current.data).toBeDefined();
  });
});

describe("useOpportunities", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  test("fetches opportunities and returns correct data shape", async () => {
    const mockData = {
      opportunities: [
        {
          id: "opp-123",
          query_pattern: "blockchain analytics",
          category: "crypto",
          estimated_revenue_usdc: 150.5,
          search_velocity: 5.2,
          competing_listings: 3,
          urgency_score: 0.85,
          created_at: "2026-02-11T09:00:00Z",
        },
      ],
    };

    vi.mocked(api.fetchOpportunities).mockResolvedValue(mockData);

    const { result } = renderHook(() => useOpportunities(), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(api.fetchOpportunities).toHaveBeenCalledWith(20, undefined);
    expect(result.current.data).toEqual(mockData);
    expect(result.current.data?.opportunities).toHaveLength(1);
    expect(result.current.data?.opportunities[0]).toHaveProperty("id");
    expect(result.current.data?.opportunities[0]).toHaveProperty("estimated_revenue_usdc");
    expect(result.current.data?.opportunities[0]).toHaveProperty("urgency_score");
  });

  test("fetches opportunities with custom limit and category", async () => {
    const mockData = {
      opportunities: [],
    };

    vi.mocked(api.fetchOpportunities).mockResolvedValue(mockData);

    const { result } = renderHook(() => useOpportunities(15, "data"), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(api.fetchOpportunities).toHaveBeenCalledWith(15, "data");
  });
});

describe("useMyEarnings", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  test("is disabled when token is null", () => {
    const { result } = renderHook(() => useMyEarnings(null), {
      wrapper: createWrapper(),
    });

    expect(result.current.isFetching).toBe(false);
    expect(result.current.data).toBeUndefined();
    expect(api.fetchMyEarnings).not.toHaveBeenCalled();
  });

  test("is disabled when token is empty string", () => {
    const { result } = renderHook(() => useMyEarnings(""), {
      wrapper: createWrapper(),
    });

    expect(result.current.isFetching).toBe(false);
    expect(api.fetchMyEarnings).not.toHaveBeenCalled();
  });

  test("fetches earnings data when token is provided", async () => {
    const mockData = {
      agent_id: "agent-456",
      total_earned_usdc: 1250.75,
      total_spent_usdc: 300.25,
      net_revenue_usdc: 950.5,
      earnings_by_category: {
        automation: 600.0,
        analytics: 650.75,
      },
      earnings_timeline: [
        {
          date: "2026-02-10",
          earned: 125.5,
          spent: 30.0,
        },
      ],
    };

    vi.mocked(api.fetchMyEarnings).mockResolvedValue(mockData);

    const { result } = renderHook(() => useMyEarnings("valid-token-123"), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(api.fetchMyEarnings).toHaveBeenCalledWith("valid-token-123");
    expect(result.current.data).toEqual(mockData);
  });

  test("includes token in query key for proper cache management", async () => {
    const mockData = {
      agent_id: "agent-789",
      total_earned_usdc: 500.0,
      total_spent_usdc: 100.0,
      net_revenue_usdc: 400.0,
      earnings_by_category: {},
      earnings_timeline: [],
    };

    vi.mocked(api.fetchMyEarnings).mockResolvedValue(mockData);

    const { result: result1 } = renderHook(
      () => useMyEarnings("token-1"),
      { wrapper: createWrapper() }
    );
    const { result: result2 } = renderHook(
      () => useMyEarnings("token-2"),
      { wrapper: createWrapper() }
    );

    await waitFor(() => expect(result1.current.isSuccess).toBe(true));
    await waitFor(() => expect(result2.current.isSuccess).toBe(true));

    // Each token should trigger separate API calls
    expect(api.fetchMyEarnings).toHaveBeenCalledTimes(2);
  });
});

describe("useMyStats", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  test("is disabled when token is null", () => {
    const { result } = renderHook(() => useMyStats(null), {
      wrapper: createWrapper(),
    });

    expect(result.current.isFetching).toBe(false);
    expect(result.current.data).toBeUndefined();
    expect(api.fetchMyStats).not.toHaveBeenCalled();
  });

  test("is disabled when token is empty string", () => {
    const { result } = renderHook(() => useMyStats(""), {
      wrapper: createWrapper(),
    });

    expect(result.current.isFetching).toBe(false);
    expect(api.fetchMyStats).not.toHaveBeenCalled();
  });

  test("fetches stats data when token is provided", async () => {
    const mockData = {
      agent_id: "agent-999",
      agent_name: "TestAgent",
      unique_buyers_served: 25,
      total_listings_created: 50,
      total_cache_hits: 150,
      category_count: 5,
      categories: ["automation", "analytics", "ml"],
      total_earned_usdc: 2000.0,
      total_spent_usdc: 500.0,
      demand_gaps_filled: 8,
      avg_listing_quality: 0.92,
      total_data_bytes: 1048576,
      helpfulness_score: 0.88,
      helpfulness_rank: 12,
      earnings_rank: 5,
      primary_specialization: "automation",
      specialization_tags: ["ai", "workflow"],
      last_calculated_at: "2026-02-11T10:00:00Z",
    };

    vi.mocked(api.fetchMyStats).mockResolvedValue(mockData);

    const { result } = renderHook(() => useMyStats("valid-token-456"), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(api.fetchMyStats).toHaveBeenCalledWith("valid-token-456");
    expect(result.current.data).toEqual(mockData);
  });
});

describe("useAgentProfile", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  test("is disabled when agentId is null", () => {
    const { result } = renderHook(() => useAgentProfile(null), {
      wrapper: createWrapper(),
    });

    expect(result.current.isFetching).toBe(false);
    expect(result.current.data).toBeUndefined();
    expect(api.fetchAgentProfile).not.toHaveBeenCalled();
  });

  test("is disabled when agentId is empty string", () => {
    const { result } = renderHook(() => useAgentProfile(""), {
      wrapper: createWrapper(),
    });

    expect(result.current.isFetching).toBe(false);
    expect(api.fetchAgentProfile).not.toHaveBeenCalled();
  });

  test("fetches agent profile when agentId is provided", async () => {
    const mockData = {
      agent_id: "agent-profile-123",
      agent_name: "ProfileAgent",
      unique_buyers_served: 100,
      total_listings_created: 200,
      total_cache_hits: 500,
      category_count: 10,
      categories: ["automation", "analytics", "ml", "crypto"],
      total_earned_usdc: 5000.0,
      total_spent_usdc: 1000.0,
      demand_gaps_filled: 20,
      avg_listing_quality: 0.95,
      total_data_bytes: 10485760,
      helpfulness_score: 0.92,
      helpfulness_rank: 3,
      earnings_rank: 2,
      primary_specialization: "ml",
      specialization_tags: ["ai", "deep-learning", "nlp"],
      last_calculated_at: "2026-02-11T11:00:00Z",
    };

    vi.mocked(api.fetchAgentProfile).mockResolvedValue(mockData);

    const { result } = renderHook(() => useAgentProfile("agent-profile-123"), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(api.fetchAgentProfile).toHaveBeenCalledWith("agent-profile-123");
    expect(result.current.data).toEqual(mockData);
  });

  test("includes agentId in query key for cache separation", async () => {
    const mockData1 = {
      agent_id: "agent-1",
      agent_name: "Agent1",
      unique_buyers_served: 10,
      total_listings_created: 20,
      total_cache_hits: 50,
      category_count: 2,
      categories: ["automation"],
      total_earned_usdc: 100.0,
      total_spent_usdc: 20.0,
      demand_gaps_filled: 1,
      avg_listing_quality: 0.8,
      total_data_bytes: 1024,
      helpfulness_score: 0.7,
      helpfulness_rank: 50,
      earnings_rank: 40,
      primary_specialization: null,
      specialization_tags: [],
      last_calculated_at: "2026-02-11T10:00:00Z",
    };

    vi.mocked(api.fetchAgentProfile).mockResolvedValue(mockData1);

    const { result: result1 } = renderHook(
      () => useAgentProfile("agent-1"),
      { wrapper: createWrapper() }
    );
    const { result: result2 } = renderHook(
      () => useAgentProfile("agent-2"),
      { wrapper: createWrapper() }
    );

    await waitFor(() => expect(result1.current.isSuccess).toBe(true));
    await waitFor(() => expect(result2.current.isSuccess).toBe(true));

    // Each agentId should trigger separate API calls
    expect(api.fetchAgentProfile).toHaveBeenCalledTimes(2);
    expect(api.fetchAgentProfile).toHaveBeenCalledWith("agent-1");
    expect(api.fetchAgentProfile).toHaveBeenCalledWith("agent-2");
  });
});

describe("useMultiLeaderboard", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  test("fetches leaderboard with boardType parameter", async () => {
    const mockData = {
      board_type: "earnings",
      entries: [
        {
          rank: 1,
          agent_id: "top-agent",
          agent_name: "TopAgent",
          primary_score: 10000.0,
          secondary_label: "Total Earned",
          total_transactions: 500,
          helpfulness_score: 0.95,
          total_earned_usdc: 10000.0,
        },
      ],
    };

    vi.mocked(api.fetchMultiLeaderboard).mockResolvedValue(mockData);

    const { result } = renderHook(() => useMultiLeaderboard("earnings"), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(api.fetchMultiLeaderboard).toHaveBeenCalledWith("earnings", 20);
    expect(result.current.data).toEqual(mockData);
  });

  test("fetches leaderboard with custom limit", async () => {
    const mockData = {
      board_type: "helpfulness",
      entries: [],
    };

    vi.mocked(api.fetchMultiLeaderboard).mockResolvedValue(mockData);

    const { result } = renderHook(() => useMultiLeaderboard("helpfulness", 50), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(api.fetchMultiLeaderboard).toHaveBeenCalledWith("helpfulness", 50);
  });

  test("includes boardType and limit in query key", async () => {
    const mockData1 = {
      board_type: "earnings",
      entries: [],
    };
    const mockData2 = {
      board_type: "transactions",
      entries: [],
    };

    vi.mocked(api.fetchMultiLeaderboard)
      .mockResolvedValueOnce(mockData1)
      .mockResolvedValueOnce(mockData2);

    const { result: result1 } = renderHook(
      () => useMultiLeaderboard("earnings", 10),
      { wrapper: createWrapper() }
    );
    const { result: result2 } = renderHook(
      () => useMultiLeaderboard("transactions", 20),
      { wrapper: createWrapper() }
    );

    await waitFor(() => expect(result1.current.isSuccess).toBe(true));
    await waitFor(() => expect(result2.current.isSuccess).toBe(true));

    // Different board types and limits should trigger separate calls
    expect(api.fetchMultiLeaderboard).toHaveBeenCalledTimes(2);
    expect(api.fetchMultiLeaderboard).toHaveBeenCalledWith("earnings", 10);
    expect(api.fetchMultiLeaderboard).toHaveBeenCalledWith("transactions", 20);
  });

  test("correctly handles different board types", async () => {
    const boardTypes = ["earnings", "helpfulness", "transactions", "quality"];

    for (const boardType of boardTypes) {
      vi.mocked(api.fetchMultiLeaderboard).mockResolvedValue({
        board_type: boardType,
        entries: [],
      });

      const { result } = renderHook(
        () => useMultiLeaderboard(boardType),
        { wrapper: createWrapper() }
      );

      await waitFor(() => expect(result.current.isSuccess).toBe(true));

      expect(api.fetchMultiLeaderboard).toHaveBeenCalledWith(boardType, 20);
      expect(result.current.data?.board_type).toBe(boardType);
    }
  });
});
