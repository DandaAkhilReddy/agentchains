import { describe, expect, test, vi, beforeEach } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";
import { useTransactions } from "../useTransactions";
import { fetchTransactions } from "../../lib/api";
import { createWrapper } from "../../test/test-utils";
import type { TransactionListResponse } from "../../types/api";

// Mock the API module
vi.mock("../../lib/api", () => ({
  fetchTransactions: vi.fn(),
}));

const mockFetchTransactions = vi.mocked(fetchTransactions);

describe("useTransactions", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  test("returns loading state initially", () => {
    mockFetchTransactions.mockImplementation(
      () => new Promise(() => {}), // Never resolves
    );

    const { result } = renderHook(
      () => useTransactions("test-token", {}),
      { wrapper: createWrapper() },
    );

    expect(result.current.isLoading).toBe(true);
    expect(result.current.data).toBeUndefined();
    expect(result.current.error).toBe(null);
  });

  test("returns transaction data on success", async () => {
    const mockData: TransactionListResponse = {
      total: 2,
      page: 1,
      page_size: 20,
      transactions: [
        {
          id: "tx-1",
          listing_id: "listing-1",
          buyer_id: "buyer-1",
          seller_id: "seller-1",
          amount_usdc: 10.5,
          status: "completed",
          payment_tx_hash: "0xabc",
          payment_network: "ethereum",
          content_hash: "hash-1",
          delivered_hash: "dhash-1",
          verification_status: "verified",
          error_message: null,
          initiated_at: "2026-01-01T00:00:00Z",
          paid_at: "2026-01-01T00:01:00Z",
          delivered_at: "2026-01-01T00:02:00Z",
          verified_at: "2026-01-01T00:03:00Z",
          completed_at: "2026-01-01T00:04:00Z",
        },
        {
          id: "tx-2",
          listing_id: "listing-2",
          buyer_id: "buyer-2",
          seller_id: "seller-2",
          amount_usdc: 25.0,
          status: "pending",
          payment_tx_hash: null,
          payment_network: null,
          content_hash: "hash-2",
          delivered_hash: null,
          verification_status: "pending",
          error_message: null,
          initiated_at: "2026-01-02T00:00:00Z",
          paid_at: null,
          delivered_at: null,
          verified_at: null,
          completed_at: null,
        },
      ],
    };

    mockFetchTransactions.mockResolvedValueOnce(mockData);

    const { result } = renderHook(
      () => useTransactions("test-token", {}),
      { wrapper: createWrapper() },
    );

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(result.current.data).toEqual(mockData);
    expect(result.current.data?.transactions).toHaveLength(2);
    expect(result.current.data?.total).toBe(2);
    expect(result.current.error).toBe(null);
  });

  test("handles error state", async () => {
    const errorMessage = "API 500: Internal Server Error";
    mockFetchTransactions.mockRejectedValueOnce(new Error(errorMessage));

    const { result } = renderHook(
      () => useTransactions("test-token", {}),
      { wrapper: createWrapper() },
    );

    await waitFor(() => expect(result.current.isError).toBe(true));

    expect(result.current.error).toBeTruthy();
    expect((result.current.error as Error).message).toBe(errorMessage);
    expect(result.current.data).toBeUndefined();
  });

  test("does NOT fetch when token is null", () => {
    const { result } = renderHook(
      () => useTransactions(null, {}),
      { wrapper: createWrapper() },
    );

    expect(result.current.fetchStatus).toBe("idle");
    expect(mockFetchTransactions).not.toHaveBeenCalled();
    expect(result.current.data).toBeUndefined();
  });

  test("fetches when token is provided", async () => {
    const mockData: TransactionListResponse = {
      total: 0,
      page: 1,
      page_size: 20,
      transactions: [],
    };

    mockFetchTransactions.mockResolvedValueOnce(mockData);

    const { result } = renderHook(
      () => useTransactions("valid-token", {}),
      { wrapper: createWrapper() },
    );

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(mockFetchTransactions).toHaveBeenCalledTimes(1);
    expect(mockFetchTransactions).toHaveBeenCalledWith("valid-token", {});
  });

  test("handles empty transaction list", async () => {
    const mockData: TransactionListResponse = {
      total: 0,
      page: 1,
      page_size: 20,
      transactions: [],
    };

    mockFetchTransactions.mockResolvedValueOnce(mockData);

    const { result } = renderHook(
      () => useTransactions("test-token", {}),
      { wrapper: createWrapper() },
    );

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(result.current.data?.transactions).toHaveLength(0);
    expect(result.current.data?.total).toBe(0);
  });

  test("passes correct parameters to fetchTransactions", async () => {
    const mockData: TransactionListResponse = {
      total: 0,
      page: 2,
      page_size: 20,
      transactions: [],
    };

    mockFetchTransactions.mockResolvedValueOnce(mockData);

    const params = { status: "completed", page: 2 };

    renderHook(
      () => useTransactions("my-token", params),
      { wrapper: createWrapper() },
    );

    await waitFor(() => expect(mockFetchTransactions).toHaveBeenCalled());

    expect(mockFetchTransactions).toHaveBeenCalledWith("my-token", params);
  });

  test("query key includes token and params for cache differentiation", async () => {
    const mockData1: TransactionListResponse = {
      total: 1,
      page: 1,
      page_size: 20,
      transactions: [
        {
          id: "tx-1",
          listing_id: "listing-1",
          buyer_id: "buyer-1",
          seller_id: "seller-1",
          amount_usdc: 10.0,
          status: "completed",
          payment_tx_hash: null,
          payment_network: null,
          content_hash: "hash-1",
          delivered_hash: null,
          verification_status: "verified",
          error_message: null,
          initiated_at: "2026-01-01T00:00:00Z",
          paid_at: null,
          delivered_at: null,
          verified_at: null,
          completed_at: null,
        },
      ],
    };

    const mockData2: TransactionListResponse = {
      total: 1,
      page: 1,
      page_size: 20,
      transactions: [
        {
          id: "tx-2",
          listing_id: "listing-2",
          buyer_id: "buyer-2",
          seller_id: "seller-2",
          amount_usdc: 20.0,
          status: "pending",
          payment_tx_hash: null,
          payment_network: null,
          content_hash: "hash-2",
          delivered_hash: null,
          verification_status: "pending",
          error_message: null,
          initiated_at: "2026-01-02T00:00:00Z",
          paid_at: null,
          delivered_at: null,
          verified_at: null,
          completed_at: null,
        },
      ],
    };

    mockFetchTransactions.mockResolvedValueOnce(mockData1);
    mockFetchTransactions.mockResolvedValueOnce(mockData2);

    const { result, rerender } = renderHook(
      ({ token, params }) => useTransactions(token, params),
      {
        wrapper: createWrapper(),
        initialProps: {
          token: "token-a" as string | null,
          params: { status: "completed" },
        },
      },
    );

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(result.current.data).toEqual(mockData1);

    // Change params to trigger a new query key
    rerender({ token: "token-a", params: { status: "pending" } });

    await waitFor(() => {
      expect(mockFetchTransactions).toHaveBeenCalledTimes(2);
    });

    expect(mockFetchTransactions).toHaveBeenNthCalledWith(2, "token-a", {
      status: "pending",
    });

    await waitFor(() => expect(result.current.data).toEqual(mockData2));
  });

  test("refetches when token changes", async () => {
    const mockData1: TransactionListResponse = {
      total: 0,
      page: 1,
      page_size: 20,
      transactions: [],
    };

    const mockData2: TransactionListResponse = {
      total: 1,
      page: 1,
      page_size: 20,
      transactions: [
        {
          id: "tx-1",
          listing_id: "listing-1",
          buyer_id: "buyer-1",
          seller_id: "seller-1",
          amount_usdc: 5.0,
          status: "completed",
          payment_tx_hash: null,
          payment_network: null,
          content_hash: "hash-1",
          delivered_hash: null,
          verification_status: "verified",
          error_message: null,
          initiated_at: "2026-01-01T00:00:00Z",
          paid_at: null,
          delivered_at: null,
          verified_at: null,
          completed_at: null,
        },
      ],
    };

    mockFetchTransactions.mockResolvedValueOnce(mockData1);
    mockFetchTransactions.mockResolvedValueOnce(mockData2);

    const { result, rerender } = renderHook(
      ({ token, params }) => useTransactions(token, params),
      {
        wrapper: createWrapper(),
        initialProps: {
          token: "token-a" as string | null,
          params: {} as { status?: string; page?: number },
        },
      },
    );

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(mockFetchTransactions).toHaveBeenCalledWith("token-a", {});
    expect(result.current.data).toEqual(mockData1);

    // Change token
    rerender({ token: "token-b", params: {} });

    await waitFor(() => {
      expect(mockFetchTransactions).toHaveBeenCalledTimes(2);
    });

    expect(mockFetchTransactions).toHaveBeenNthCalledWith(2, "token-b", {});

    await waitFor(() => expect(result.current.data).toEqual(mockData2));
  });
});
