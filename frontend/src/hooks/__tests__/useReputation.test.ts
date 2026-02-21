import { describe, expect, test, vi, beforeEach } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";
import { useReputation, useLeaderboard } from "../useReputation";
import { fetchReputation, fetchLeaderboard } from "../../lib/api";
import { createWrapper } from "../../test/test-utils";
import type { ReputationResponse, LeaderboardResponse } from "../../types/api";

// Mock the API module
vi.mock("../../lib/api", () => ({
  fetchReputation: vi.fn(),
  fetchLeaderboard: vi.fn(),
}));

const mockFetchReputation = vi.mocked(fetchReputation);
const mockFetchLeaderboard = vi.mocked(fetchLeaderboard);

describe("useReputation", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  test("returns loading state initially", () => {
    mockFetchReputation.mockImplementation(
      () => new Promise(() => {}), // Never resolves
    );

    const { result } = renderHook(() => useReputation("agent-1"), {
      wrapper: createWrapper(),
    });

    expect(result.current.isLoading).toBe(true);
    expect(result.current.data).toBeUndefined();
    expect(result.current.error).toBe(null);
  });

  test("returns reputation data on success", async () => {
    const mockData: ReputationResponse = {
      agent_id: "agent-1",
      agent_name: "Test Agent",
      total_transactions: 100,
      successful_deliveries: 95,
      failed_deliveries: 5,
      verified_count: 90,
      verification_failures: 2,
      avg_response_ms: 150.5,
      total_volume_usdc: 5000.0,
      composite_score: 0.92,
      last_calculated_at: "2026-02-21T00:00:00Z",
    };

    mockFetchReputation.mockResolvedValueOnce(mockData);

    const { result } = renderHook(() => useReputation("agent-1"), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(result.current.data).toEqual(mockData);
    expect(result.current.data?.agent_id).toBe("agent-1");
    expect(result.current.data?.composite_score).toBe(0.92);
    expect(result.current.error).toBe(null);
  });

  test("handles error state", async () => {
    const errorMessage = "API 500: Internal Server Error";
    mockFetchReputation.mockRejectedValueOnce(new Error(errorMessage));

    const { result } = renderHook(() => useReputation("agent-1"), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result.current.isError).toBe(true));

    expect(result.current.error).toBeTruthy();
    expect((result.current.error as Error).message).toBe(errorMessage);
    expect(result.current.data).toBeUndefined();
  });

  test("passes agent ID correctly", async () => {
    const mockData: ReputationResponse = {
      agent_id: "agent-42",
      agent_name: "Agent 42",
      total_transactions: 50,
      successful_deliveries: 48,
      failed_deliveries: 2,
      verified_count: 45,
      verification_failures: 1,
      avg_response_ms: 200,
      total_volume_usdc: 2500.0,
      composite_score: 0.88,
      last_calculated_at: "2026-02-21T00:00:00Z",
    };

    mockFetchReputation.mockResolvedValueOnce(mockData);

    renderHook(() => useReputation("agent-42"), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(mockFetchReputation).toHaveBeenCalled());

    expect(mockFetchReputation).toHaveBeenCalledTimes(1);
    expect(mockFetchReputation).toHaveBeenCalledWith("agent-42");
  });

  test("handles missing agent ID", () => {
    const { result } = renderHook(() => useReputation(null), {
      wrapper: createWrapper(),
    });

    // When agentId is null, the query should be disabled (not loading, not fetching)
    expect(result.current.isLoading).toBe(false);
    expect(result.current.fetchStatus).toBe("idle");
    expect(result.current.data).toBeUndefined();
    expect(mockFetchReputation).not.toHaveBeenCalled();
  });
});

describe("useLeaderboard", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  test("returns loading state initially", () => {
    mockFetchLeaderboard.mockImplementation(
      () => new Promise(() => {}), // Never resolves
    );

    const { result } = renderHook(() => useLeaderboard(), {
      wrapper: createWrapper(),
    });

    expect(result.current.isLoading).toBe(true);
    expect(result.current.data).toBeUndefined();
    expect(result.current.error).toBe(null);
  });

  test("returns leaderboard data on success", async () => {
    const mockData: LeaderboardResponse = {
      entries: [
        {
          rank: 1,
          agent_id: "agent-1",
          agent_name: "Top Agent",
          composite_score: 0.99,
          total_transactions: 500,
          total_volume_usdc: 25000.0,
        },
        {
          rank: 2,
          agent_id: "agent-2",
          agent_name: "Second Agent",
          composite_score: 0.95,
          total_transactions: 400,
          total_volume_usdc: 20000.0,
        },
      ],
    };

    mockFetchLeaderboard.mockResolvedValueOnce(mockData);

    const { result } = renderHook(() => useLeaderboard(), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(result.current.data).toEqual(mockData);
    expect(result.current.data?.entries).toHaveLength(2);
    expect(result.current.data?.entries[0].rank).toBe(1);
    expect(result.current.error).toBe(null);
  });

  test("handles error state", async () => {
    const errorMessage = "API 503: Service Unavailable";
    mockFetchLeaderboard.mockRejectedValueOnce(new Error(errorMessage));

    const { result } = renderHook(() => useLeaderboard(), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result.current.isError).toBe(true));

    expect(result.current.error).toBeTruthy();
    expect((result.current.error as Error).message).toBe(errorMessage);
    expect(result.current.data).toBeUndefined();
  });

  test("handles empty leaderboard", async () => {
    const mockData: LeaderboardResponse = {
      entries: [],
    };

    mockFetchLeaderboard.mockResolvedValueOnce(mockData);

    const { result } = renderHook(() => useLeaderboard(), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(result.current.data).toEqual(mockData);
    expect(result.current.data?.entries).toHaveLength(0);
  });

  test("query key is correct", async () => {
    const mockData: LeaderboardResponse = { entries: [] };

    mockFetchLeaderboard.mockResolvedValueOnce(mockData);
    mockFetchLeaderboard.mockResolvedValueOnce(mockData);

    // Default limit is 20
    const { result } = renderHook(() => useLeaderboard(), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(mockFetchLeaderboard).toHaveBeenCalledWith(20);

    // Custom limit
    const { result: result2 } = renderHook(() => useLeaderboard(10), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result2.current.isSuccess).toBe(true));

    expect(mockFetchLeaderboard).toHaveBeenCalledWith(10);
  });
});

describe("useReputation + useLeaderboard", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  test("correct query keys and parameters", async () => {
    const reputationData: ReputationResponse = {
      agent_id: "agent-1",
      agent_name: "Test Agent",
      total_transactions: 10,
      successful_deliveries: 9,
      failed_deliveries: 1,
      verified_count: 8,
      verification_failures: 0,
      avg_response_ms: null,
      total_volume_usdc: 100.0,
      composite_score: 0.85,
      last_calculated_at: "2026-02-21T00:00:00Z",
    };

    const leaderboardData: LeaderboardResponse = {
      entries: [
        {
          rank: 1,
          agent_id: "agent-1",
          agent_name: "Test Agent",
          composite_score: 0.85,
          total_transactions: 10,
          total_volume_usdc: 100.0,
        },
      ],
    };

    mockFetchReputation.mockResolvedValueOnce(reputationData);
    mockFetchLeaderboard.mockResolvedValueOnce(leaderboardData);

    const { result: repResult } = renderHook(
      () => useReputation("agent-1"),
      { wrapper: createWrapper() },
    );

    const { result: lbResult } = renderHook(
      () => useLeaderboard(5),
      { wrapper: createWrapper() },
    );

    await waitFor(() => expect(repResult.current.isSuccess).toBe(true));
    await waitFor(() => expect(lbResult.current.isSuccess).toBe(true));

    // Verify correct API calls
    expect(mockFetchReputation).toHaveBeenCalledWith("agent-1");
    expect(mockFetchLeaderboard).toHaveBeenCalledWith(5);

    // Verify data returned
    expect(repResult.current.data).toEqual(reputationData);
    expect(lbResult.current.data).toEqual(leaderboardData);
  });
});
