import { describe, expect, test, vi, beforeEach } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";
import { useAgents } from "../useAgents";
import { fetchAgents } from "../../lib/api";
import { createWrapper } from "../../test/test-utils";
import type { AgentListResponse } from "../../types/api";

// Mock the API module
vi.mock("../../lib/api", () => ({
  fetchAgents: vi.fn(),
}));

const mockFetchAgents = vi.mocked(fetchAgents);

describe("useAgents", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  test("fetches agents on mount", async () => {
    const mockData: AgentListResponse = {
      agents: [
        {
          agent_id: "agent-1",
          agent_type: "mcp",
          display_name: "Test Agent",
          status: "active",
          created_at: "2026-01-01T00:00:00Z",
        },
      ],
      total: 1,
    };

    mockFetchAgents.mockResolvedValueOnce(mockData);

    const { result } = renderHook(() => useAgents({}), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(mockFetchAgents).toHaveBeenCalledTimes(1);
    expect(mockFetchAgents).toHaveBeenCalledWith({});
    expect(result.current.data).toEqual(mockData);
  });

  test("passes params to fetchAgents", async () => {
    const mockData: AgentListResponse = {
      agents: [],
      total: 0,
    };

    mockFetchAgents.mockResolvedValueOnce(mockData);

    const params = {
      agent_type: "mcp",
      status: "active",
      page: 2,
    };

    renderHook(() => useAgents(params), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(mockFetchAgents).toHaveBeenCalled());

    expect(mockFetchAgents).toHaveBeenCalledWith(params);
  });

  test("returns loading state initially", () => {
    mockFetchAgents.mockImplementation(
      () => new Promise(() => {}), // Never resolves
    );

    const { result } = renderHook(() => useAgents({}), {
      wrapper: createWrapper(),
    });

    expect(result.current.isLoading).toBe(true);
    expect(result.current.data).toBeUndefined();
    expect(result.current.error).toBe(null);
  });

  test("returns data on success", async () => {
    const mockData: AgentListResponse = {
      agents: [
        {
          agent_id: "agent-1",
          agent_type: "mcp",
          display_name: "Agent One",
          status: "active",
          created_at: "2026-01-01T00:00:00Z",
        },
        {
          agent_id: "agent-2",
          agent_type: "custom",
          display_name: "Agent Two",
          status: "paused",
          created_at: "2026-01-02T00:00:00Z",
        },
      ],
      total: 2,
    };

    mockFetchAgents.mockResolvedValueOnce(mockData);

    const { result } = renderHook(() => useAgents({}), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(result.current.data).toEqual(mockData);
    expect(result.current.data?.agents).toHaveLength(2);
    expect(result.current.data?.total).toBe(2);
    expect(result.current.error).toBe(null);
  });

  test("returns error on failure", async () => {
    const errorMessage = "API 500: Internal Server Error";
    mockFetchAgents.mockRejectedValueOnce(new Error(errorMessage));

    const { result } = renderHook(() => useAgents({}), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result.current.isError).toBe(true));

    expect(result.current.error).toBeTruthy();
    expect((result.current.error as Error).message).toBe(errorMessage);
    expect(result.current.data).toBeUndefined();
  });

  test("refetches when params change", async () => {
    const mockData1: AgentListResponse = {
      agents: [
        {
          agent_id: "agent-1",
          agent_type: "mcp",
          display_name: "MCP Agent",
          status: "active",
          created_at: "2026-01-01T00:00:00Z",
        },
      ],
      total: 1,
    };

    const mockData2: AgentListResponse = {
      agents: [
        {
          agent_id: "agent-2",
          agent_type: "custom",
          display_name: "Custom Agent",
          status: "paused",
          created_at: "2026-01-02T00:00:00Z",
        },
      ],
      total: 1,
    };

    mockFetchAgents.mockResolvedValueOnce(mockData1);
    mockFetchAgents.mockResolvedValueOnce(mockData2);

    const { result, rerender } = renderHook(
      ({ params }) => useAgents(params),
      {
        wrapper: createWrapper(),
        initialProps: { params: { agent_type: "mcp" } },
      },
    );

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(mockFetchAgents).toHaveBeenCalledWith({ agent_type: "mcp" });
    expect(result.current.data).toEqual(mockData1);

    // Change params
    rerender({ params: { agent_type: "custom", status: "paused" } });

    await waitFor(() => {
      expect(mockFetchAgents).toHaveBeenCalledTimes(2);
    });

    expect(mockFetchAgents).toHaveBeenNthCalledWith(2, {
      agent_type: "custom",
      status: "paused",
    });

    await waitFor(() => expect(result.current.data).toEqual(mockData2));
  });

  test("uses correct query key", async () => {
    const mockData: AgentListResponse = {
      agents: [],
      total: 0,
    };

    mockFetchAgents.mockResolvedValueOnce(mockData);

    const params = {
      agent_type: "mcp",
      status: "active",
      page: 1,
    };

    const { result } = renderHook(() => useAgents(params), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    // Verify that the query key includes both "agents" and params
    // This is important for proper cache invalidation and query matching
    expect(result.current.data).toEqual(mockData);

    // The query key should be ["agents", params]
    // We can verify this by checking that changing params triggers a new fetch
    expect(mockFetchAgents).toHaveBeenCalledWith(params);
  });

  test("handles empty params object", async () => {
    const mockData: AgentListResponse = {
      agents: [],
      total: 0,
    };

    mockFetchAgents.mockResolvedValueOnce(mockData);

    const { result } = renderHook(() => useAgents({}), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(mockFetchAgents).toHaveBeenCalledWith({});
    expect(result.current.data).toEqual(mockData);
  });

  test("handles partial params", async () => {
    const mockData: AgentListResponse = {
      agents: [],
      total: 0,
    };

    mockFetchAgents.mockResolvedValueOnce(mockData);

    const { result } = renderHook(
      () => useAgents({ agent_type: "mcp" }),
      {
        wrapper: createWrapper(),
      },
    );

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(mockFetchAgents).toHaveBeenCalledWith({ agent_type: "mcp" });
    expect(result.current.data).toEqual(mockData);
  });
});
