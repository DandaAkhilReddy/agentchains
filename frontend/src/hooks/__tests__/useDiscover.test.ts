import { describe, expect, test, vi, beforeEach } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";
import { useDiscover } from "../useDiscover";
import { fetchDiscover } from "../../lib/api";
import { createWrapper } from "../../test/test-utils";
import type {
  ListingListResponse,
  DiscoverParams,
  Listing,
} from "../../types/api";

// Mock the API module
vi.mock("../../lib/api", () => ({
  fetchDiscover: vi.fn(),
}));

const mockFetchDiscover = vi.mocked(fetchDiscover);

function makeListing(overrides: Partial<Listing> = {}): Listing {
  return {
    id: "lst-1",
    seller_id: "agent-1",
    seller: { id: "agent-1", name: "Seller One", reputation_score: 4.5 },
    title: "Test Listing",
    description: "A test listing",
    category: "web_search",
    content_hash: "abc123",
    content_size: 1024,
    content_type: "application/json",
    price_usdc: 10,
    currency: "USDC",
    metadata: {},
    tags: [],
    quality_score: 0.9,
    freshness_at: "2026-01-01T00:00:00Z",
    expires_at: null,
    status: "active",
    access_count: 5,
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
    ...overrides,
  };
}

function makeMockResponse(
  overrides: Partial<ListingListResponse> = {},
): ListingListResponse {
  return {
    total: 0,
    page: 1,
    page_size: 20,
    results: [],
    ...overrides,
  };
}

describe("useDiscover", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  test("returns loading state initially", () => {
    mockFetchDiscover.mockImplementation(
      () => new Promise(() => {}), // Never resolves
    );

    const { result } = renderHook(() => useDiscover({}), {
      wrapper: createWrapper(),
    });

    expect(result.current.isLoading).toBe(true);
    expect(result.current.data).toBeUndefined();
    expect(result.current.error).toBe(null);
  });

  test("returns data on successful fetch", async () => {
    const mockData = makeMockResponse({
      total: 2,
      results: [
        makeListing({ id: "lst-1", title: "Premium Dataset" }),
        makeListing({
          id: "lst-2",
          seller_id: "agent-2",
          title: "Image Collection",
          category: "code_analysis",
          price_usdc: 25,
        }),
      ],
    });

    mockFetchDiscover.mockResolvedValueOnce(mockData);

    const { result } = renderHook(() => useDiscover({}), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(result.current.data).toEqual(mockData);
    expect(result.current.data?.results).toHaveLength(2);
    expect(result.current.data?.total).toBe(2);
    expect(result.current.error).toBe(null);
  });

  test("returns error on failed fetch", async () => {
    const errorMessage = "API 500: Internal Server Error";
    mockFetchDiscover.mockRejectedValueOnce(new Error(errorMessage));

    const { result } = renderHook(() => useDiscover({}), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result.current.isError).toBe(true));

    expect(result.current.error).toBeTruthy();
    expect((result.current.error as Error).message).toBe(errorMessage);
    expect(result.current.data).toBeUndefined();
  });

  test("handles empty results", async () => {
    const mockData = makeMockResponse({
      total: 0,
      page: 1,
      page_size: 20,
      results: [],
    });

    mockFetchDiscover.mockResolvedValueOnce(mockData);

    const { result } = renderHook(() => useDiscover({}), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(result.current.data).toEqual(mockData);
    expect(result.current.data?.results).toHaveLength(0);
    expect(result.current.data?.total).toBe(0);
  });

  test("passes correct parameters to API", async () => {
    mockFetchDiscover.mockResolvedValueOnce(makeMockResponse());

    const params: DiscoverParams = {
      q: "dataset",
      category: "web_search",
      min_price: 5,
      max_price: 50,
      min_quality: 0.8,
      max_age_hours: 48,
      seller_id: "agent-1",
      sort_by: "price_asc",
      page: 2,
      page_size: 10,
    };

    renderHook(() => useDiscover(params), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(mockFetchDiscover).toHaveBeenCalled());

    expect(mockFetchDiscover).toHaveBeenCalledWith(params);
  });

  test("refetch works correctly", async () => {
    const mockData1 = makeMockResponse({
      total: 1,
      results: [makeListing({ id: "lst-1", title: "First Result" })],
    });

    const mockData2 = makeMockResponse({
      total: 1,
      results: [makeListing({ id: "lst-2", title: "Refreshed Result" })],
    });

    mockFetchDiscover.mockResolvedValueOnce(mockData1);

    const { result } = renderHook(() => useDiscover({}), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data).toEqual(mockData1);

    mockFetchDiscover.mockResolvedValueOnce(mockData2);

    await result.current.refetch();

    await waitFor(() =>
      expect(result.current.data?.results[0].id).toBe("lst-2"),
    );

    expect(mockFetchDiscover).toHaveBeenCalledTimes(2);
    expect(result.current.data).toEqual(mockData2);
  });

  test("query key structure causes refetch when params change", async () => {
    const mockData1 = makeMockResponse({ total: 5 });
    const mockData2 = makeMockResponse({ total: 3 });

    mockFetchDiscover.mockResolvedValueOnce(mockData1);
    mockFetchDiscover.mockResolvedValueOnce(mockData2);

    const { result, rerender } = renderHook(
      ({ params }: { params: DiscoverParams }) => useDiscover(params),
      {
        wrapper: createWrapper(),
        initialProps: { params: { q: "text" } as DiscoverParams },
      },
    );

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(mockFetchDiscover).toHaveBeenCalledWith({ q: "text" });
    expect(result.current.data).toEqual(mockData1);

    // Change params to trigger refetch via query key ["discover", params]
    rerender({
      params: { q: "image", category: "code_analysis" } as DiscoverParams,
    });

    await waitFor(() => {
      expect(mockFetchDiscover).toHaveBeenCalledTimes(2);
    });

    expect(mockFetchDiscover).toHaveBeenNthCalledWith(2, {
      q: "image",
      category: "code_analysis",
    });

    await waitFor(() => expect(result.current.data).toEqual(mockData2));
  });

  test("handles partial params (only some fields set)", async () => {
    mockFetchDiscover.mockResolvedValueOnce(makeMockResponse({ total: 10 }));

    const params: DiscoverParams = {
      category: "web_search",
      min_quality: 0.7,
    };

    const { result } = renderHook(() => useDiscover(params), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(mockFetchDiscover).toHaveBeenCalledWith(params);
    expect(result.current.data?.total).toBe(10);
  });
});
