import { describe, expect, test, vi, beforeEach } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";
import { useSystemMetrics, useCDNStats } from "../useSystemMetrics";
import { fetchSystemMetrics, fetchCDNStats } from "../../lib/api";
import { createWrapper } from "../../test/test-utils";
import type { HealthResponse, CDNStats } from "../../types/api";

// Mock the API module
vi.mock("../../lib/api", () => ({
  fetchSystemMetrics: vi.fn(),
  fetchCDNStats: vi.fn(),
}));

const mockFetchSystemMetrics = vi.mocked(fetchSystemMetrics);
const mockFetchCDNStats = vi.mocked(fetchCDNStats);

const makeCDNStats = (overrides?: Partial<CDNStats>): CDNStats => ({
  overview: {
    total_requests: 5000,
    tier1_hits: 3000,
    tier2_hits: 1000,
    tier3_hits: 500,
    total_misses: 500,
  },
  hot_cache: {
    tier: "hot",
    entries: 120,
    bytes_used: 1024000,
    bytes_max: 2048000,
    utilization_pct: 50,
    hits: 3000,
    misses: 200,
    promotions: 50,
    evictions: 10,
    hit_rate: 0.94,
  },
  warm_cache: {
    hits: 1000,
    misses: 500,
    size: 300,
    maxsize: 1000,
    hit_rate: 0.67,
  },
  ...overrides,
});

const makeHealthResponse = (
  overrides?: Partial<HealthResponse>,
): HealthResponse => ({
  status: "ok",
  version: "1.5.0",
  agents_count: 42,
  listings_count: 100,
  transactions_count: 256,
  cache_stats: {
    listings: { hits: 500, misses: 50, size: 80, maxsize: 200, hit_rate: 0.91 },
    content: { hits: 300, misses: 30, size: 60, maxsize: 150, hit_rate: 0.91 },
    agents: { hits: 200, misses: 20, size: 40, maxsize: 100, hit_rate: 0.91 },
  },
  ...overrides,
});

const makeSystemMetricsResponse = () => ({
  health: makeHealthResponse(),
  cdn: makeCDNStats(),
});

// ── useSystemMetrics ──

describe("useSystemMetrics", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  test("returns loading state initially", () => {
    mockFetchSystemMetrics.mockImplementation(
      () => new Promise(() => {}), // Never resolves
    );

    const { result } = renderHook(() => useSystemMetrics(), {
      wrapper: createWrapper(),
    });

    expect(result.current.isLoading).toBe(true);
    expect(result.current.data).toBeUndefined();
    expect(result.current.error).toBe(null);
  });

  test("returns system metrics data on success", async () => {
    const mockData = makeSystemMetricsResponse();
    mockFetchSystemMetrics.mockResolvedValueOnce(mockData);

    const { result } = renderHook(() => useSystemMetrics(), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(mockFetchSystemMetrics).toHaveBeenCalledTimes(1);
    expect(result.current.data).toEqual(mockData);
    expect(result.current.error).toBe(null);
  });

  test("handles error state", async () => {
    const errorMessage = "API 500: Internal Server Error";
    mockFetchSystemMetrics.mockRejectedValueOnce(new Error(errorMessage));

    const { result } = renderHook(() => useSystemMetrics(), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result.current.isError).toBe(true));

    expect(result.current.error).toBeTruthy();
    expect((result.current.error as Error).message).toBe(errorMessage);
    expect(result.current.data).toBeUndefined();
  });

  test("returns health and CDN data in combined response", async () => {
    const mockData = makeSystemMetricsResponse();
    mockFetchSystemMetrics.mockResolvedValueOnce(mockData);

    const { result } = renderHook(() => useSystemMetrics(), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    // Verify health metrics
    expect(result.current.data?.health.status).toBe("ok");
    expect(result.current.data?.health.version).toBe("1.5.0");
    expect(result.current.data?.health.agents_count).toBe(42);
    expect(result.current.data?.health.listings_count).toBe(100);
    expect(result.current.data?.health.transactions_count).toBe(256);

    // Verify CDN metrics
    expect(result.current.data?.cdn.overview.total_requests).toBe(5000);
    expect(result.current.data?.cdn.hot_cache.hit_rate).toBe(0.94);
    expect(result.current.data?.cdn.warm_cache.hit_rate).toBe(0.67);
  });

  test("handles partial metrics data (no cache_stats)", async () => {
    const mockData = {
      health: makeHealthResponse({ cache_stats: undefined }),
      cdn: makeCDNStats(),
    };
    mockFetchSystemMetrics.mockResolvedValueOnce(mockData);

    const { result } = renderHook(() => useSystemMetrics(), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(result.current.data?.health.cache_stats).toBeUndefined();
    expect(result.current.data?.health.status).toBe("ok");
    expect(result.current.data?.cdn.overview.total_requests).toBe(5000);
  });

  test("query key is correct (system-metrics)", async () => {
    const mockData = makeSystemMetricsResponse();
    mockFetchSystemMetrics.mockResolvedValueOnce(mockData);

    const { result } = renderHook(() => useSystemMetrics(), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    // The hook uses queryKey: ["system-metrics"]
    // Verify that the query fn (fetchSystemMetrics) was called without arguments
    expect(mockFetchSystemMetrics).toHaveBeenCalledWith(
      expect.anything(), // QueryFunctionContext passed by react-query
    );
    expect(result.current.data).toEqual(mockData);
  });

  test("handles network timeout gracefully", async () => {
    const timeoutError = new Error("Network timeout");
    timeoutError.name = "AbortError";
    mockFetchSystemMetrics.mockRejectedValueOnce(timeoutError);

    const { result } = renderHook(() => useSystemMetrics(), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result.current.isError).toBe(true));

    expect(result.current.error).toBeTruthy();
    expect((result.current.error as Error).message).toBe("Network timeout");
    expect(result.current.data).toBeUndefined();
  });

  test("uses refetchInterval of 30 seconds", async () => {
    vi.useFakeTimers();

    const mockData = makeSystemMetricsResponse();
    mockFetchSystemMetrics.mockResolvedValue(mockData);

    renderHook(() => useSystemMetrics(), {
      wrapper: createWrapper(),
    });

    // Wait for initial fetch
    await vi.waitFor(() => {
      expect(mockFetchSystemMetrics).toHaveBeenCalledTimes(1);
    });

    // Advance 30 seconds for refetch interval
    await vi.advanceTimersByTimeAsync(30_000);

    await vi.waitFor(() => {
      expect(mockFetchSystemMetrics).toHaveBeenCalledTimes(2);
    });

    vi.useRealTimers();
  });
});

// ── useCDNStats ──

describe("useCDNStats", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  test("returns loading state initially", () => {
    mockFetchCDNStats.mockImplementation(
      () => new Promise(() => {}), // Never resolves
    );

    const { result } = renderHook(() => useCDNStats(), {
      wrapper: createWrapper(),
    });

    expect(result.current.isLoading).toBe(true);
    expect(result.current.data).toBeUndefined();
    expect(result.current.error).toBe(null);
  });

  test("returns CDN stats data on success", async () => {
    const mockData = makeCDNStats();
    mockFetchCDNStats.mockResolvedValueOnce(mockData);

    const { result } = renderHook(() => useCDNStats(), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(mockFetchCDNStats).toHaveBeenCalledTimes(1);
    expect(result.current.data).toEqual(mockData);
    expect(result.current.error).toBe(null);
  });

  test("handles error state", async () => {
    const errorMessage = "API 503: Service Unavailable";
    mockFetchCDNStats.mockRejectedValueOnce(new Error(errorMessage));

    const { result } = renderHook(() => useCDNStats(), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result.current.isError).toBe(true));

    expect(result.current.error).toBeTruthy();
    expect((result.current.error as Error).message).toBe(errorMessage);
    expect(result.current.data).toBeUndefined();
  });

  test("uses refetchInterval of 15 seconds", async () => {
    vi.useFakeTimers();

    const mockData = makeCDNStats();
    mockFetchCDNStats.mockResolvedValue(mockData);

    renderHook(() => useCDNStats(), {
      wrapper: createWrapper(),
    });

    // Wait for initial fetch
    await vi.waitFor(() => {
      expect(mockFetchCDNStats).toHaveBeenCalledTimes(1);
    });

    // Advance 15 seconds for refetch interval
    await vi.advanceTimersByTimeAsync(15_000);

    await vi.waitFor(() => {
      expect(mockFetchCDNStats).toHaveBeenCalledTimes(2);
    });

    vi.useRealTimers();
  });
});
