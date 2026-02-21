import { describe, it, expect, vi, beforeEach } from "vitest";
import { screen, fireEvent, waitFor } from "@testing-library/react";
import { renderWithProviders } from "../../test/test-utils";
import TransactionsPage from "../TransactionsPage";
import * as useAuthModule from "../../hooks/useAuth";
import * as useTransactionsModule from "../../hooks/useTransactions";
import type { Transaction, TransactionListResponse } from "../../types/api";

// Mock hooks
vi.mock("../../hooks/useAuth");
vi.mock("../../hooks/useTransactions");

// Mock clipboard API
Object.assign(navigator, {
  clipboard: { writeText: vi.fn(() => Promise.resolve()) },
});

/* ── Test Data ──────────────────────────────────────────── */

const mockTransactions: Transaction[] = [
  {
    id: "tx-001-abcd",
    listing_id: "lst-001",
    buyer_id: "buyer-001-xyz",
    seller_id: "seller-001",
    amount_usdc: 0.0025,
    status: "completed",
    payment_tx_hash: null,
    payment_network: null,
    content_hash: "abc123",
    delivered_hash: "abc123",
    verification_status: "verified",
    error_message: null,
    initiated_at: new Date(Date.now() - 3600000).toISOString(),
    paid_at: new Date(Date.now() - 3500000).toISOString(),
    delivered_at: new Date(Date.now() - 3400000).toISOString(),
    verified_at: new Date(Date.now() - 3300000).toISOString(),
    completed_at: new Date(Date.now() - 3200000).toISOString(),
    payment_method: "balance",
  },
  {
    id: "tx-002-efgh",
    listing_id: "lst-002",
    buyer_id: "buyer-002-xyz",
    seller_id: "seller-002",
    amount_usdc: 0.005,
    status: "initiated",
    payment_tx_hash: null,
    payment_network: null,
    content_hash: "def456",
    delivered_hash: null,
    verification_status: "pending",
    error_message: null,
    initiated_at: new Date(Date.now() - 60000).toISOString(),
    paid_at: null,
    delivered_at: null,
    verified_at: null,
    completed_at: null,
    payment_method: "simulated",
  },
  {
    id: "tx-003-ijkl",
    listing_id: "lst-003",
    buyer_id: "buyer-003-xyz",
    seller_id: "seller-003",
    amount_usdc: 0.01,
    status: "failed",
    payment_tx_hash: null,
    payment_network: null,
    content_hash: "ghi789",
    delivered_hash: null,
    verification_status: "pending",
    error_message: "Delivery timeout",
    initiated_at: new Date(Date.now() - 7200000).toISOString(),
    paid_at: null,
    delivered_at: null,
    verified_at: null,
    completed_at: null,
    payment_method: "fiat",
  },
];

const mockResponse: TransactionListResponse = {
  total: 3,
  page: 1,
  page_size: 20,
  transactions: mockTransactions,
};

const mockResponseEmpty: TransactionListResponse = {
  total: 0,
  page: 1,
  page_size: 20,
  transactions: [],
};

const mockResponseLarge: TransactionListResponse = {
  total: 45,
  page: 1,
  page_size: 20,
  transactions: mockTransactions,
};

/* ── Tests ──────────────────────────────────────────────── */

describe("TransactionsPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders page header when authenticated", () => {
    vi.spyOn(useAuthModule, "useAuth").mockReturnValue({
      token: "test-jwt-token",
      login: vi.fn(),
      logout: vi.fn(),
      isAuthenticated: true,
    });
    vi.spyOn(useTransactionsModule, "useTransactions").mockReturnValue({
      data: mockResponse,
      isLoading: false,
      error: null,
    } as any);

    renderWithProviders(<TransactionsPage />);

    expect(screen.getByText("Transactions")).toBeInTheDocument();
    expect(screen.getByText("Track purchases and deliveries")).toBeInTheDocument();
  });

  it("shows auth gate when not authenticated", () => {
    vi.spyOn(useAuthModule, "useAuth").mockReturnValue({
      token: "",
      login: vi.fn(),
      logout: vi.fn(),
      isAuthenticated: false,
    });
    vi.spyOn(useTransactionsModule, "useTransactions").mockReturnValue({
      data: undefined,
      isLoading: false,
      error: null,
    } as any);

    renderWithProviders(<TransactionsPage />);

    expect(screen.getByText("Connect Agent")).toBeInTheDocument();
    expect(screen.getByText("Paste your agent JWT to view transactions")).toBeInTheDocument();
    expect(screen.getByPlaceholderText("eyJhbGciOi...")).toBeInTheDocument();
  });

  it("shows transaction list with data", () => {
    vi.spyOn(useAuthModule, "useAuth").mockReturnValue({
      token: "test-jwt-token",
      login: vi.fn(),
      logout: vi.fn(),
      isAuthenticated: true,
    });
    vi.spyOn(useTransactionsModule, "useTransactions").mockReturnValue({
      data: mockResponse,
      isLoading: false,
      error: null,
    } as any);

    renderWithProviders(<TransactionsPage />);

    // Check transaction count text
    expect(screen.getByText("3 transactions")).toBeInTheDocument();
    // Check status badges are rendered (completed replaces underscores)
    expect(screen.getByText("completed")).toBeInTheDocument();
    expect(screen.getByText("initiated")).toBeInTheDocument();
    expect(screen.getByText("failed")).toBeInTheDocument();
  });

  it("shows loading spinner state", () => {
    vi.spyOn(useAuthModule, "useAuth").mockReturnValue({
      token: "test-jwt-token",
      login: vi.fn(),
      logout: vi.fn(),
      isAuthenticated: true,
    });
    vi.spyOn(useTransactionsModule, "useTransactions").mockReturnValue({
      data: undefined,
      isLoading: true,
      error: null,
    } as any);

    renderWithProviders(<TransactionsPage />);

    // DataTable shows Spinner when isLoading is true
    const spinner = screen.getByRole("status", { name: "Loading" });
    expect(spinner).toBeInTheDocument();
  });

  it("shows empty state when no transactions found", () => {
    vi.spyOn(useAuthModule, "useAuth").mockReturnValue({
      token: "test-jwt-token",
      login: vi.fn(),
      logout: vi.fn(),
      isAuthenticated: true,
    });
    vi.spyOn(useTransactionsModule, "useTransactions").mockReturnValue({
      data: mockResponseEmpty,
      isLoading: false,
      error: null,
    } as any);

    renderWithProviders(<TransactionsPage />);

    expect(screen.getByText("No transactions found")).toBeInTheDocument();
  });

  it("renders filter tabs for status filtering", () => {
    vi.spyOn(useAuthModule, "useAuth").mockReturnValue({
      token: "test-jwt-token",
      login: vi.fn(),
      logout: vi.fn(),
      isAuthenticated: true,
    });
    vi.spyOn(useTransactionsModule, "useTransactions").mockReturnValue({
      data: mockResponse,
      isLoading: false,
      error: null,
    } as any);

    renderWithProviders(<TransactionsPage />);

    expect(screen.getByText("All")).toBeInTheDocument();
    // "Pending", "Completed", "Failed" appear in both filter tabs and TransactionStats
    expect(screen.getAllByText(/Pending/).length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText(/Completed/).length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText(/Failed/).length).toBeGreaterThanOrEqual(1);
  });

  it("changes filter tab and resets page", async () => {
    const mockUseTransactions = vi.fn().mockReturnValue({
      data: mockResponse,
      isLoading: false,
      error: null,
    });
    vi.spyOn(useAuthModule, "useAuth").mockReturnValue({
      token: "test-jwt-token",
      login: vi.fn(),
      logout: vi.fn(),
      isAuthenticated: true,
    });
    vi.spyOn(useTransactionsModule, "useTransactions").mockImplementation(mockUseTransactions);

    renderWithProviders(<TransactionsPage />);

    // "Failed" appears in both filter tabs and TransactionStats; target the button
    const failedButtons = screen.getAllByText("Failed");
    const failedTab = failedButtons.find((el) => el.tagName === "BUTTON") ?? failedButtons[0];
    fireEvent.click(failedTab);

    await waitFor(() => {
      expect(mockUseTransactions).toHaveBeenCalledWith("test-jwt-token", {
        status: "failed",
        page: 1,
      });
    });
  });

  it("shows pagination when total exceeds 20", () => {
    vi.spyOn(useAuthModule, "useAuth").mockReturnValue({
      token: "test-jwt-token",
      login: vi.fn(),
      logout: vi.fn(),
      isAuthenticated: true,
    });
    vi.spyOn(useTransactionsModule, "useTransactions").mockReturnValue({
      data: mockResponseLarge,
      isLoading: false,
      error: null,
    } as any);

    renderWithProviders(<TransactionsPage />);

    expect(screen.getByRole("button", { name: "Previous page" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Next page" })).toBeInTheDocument();
  });

  it("does not show pagination when total is 20 or less", () => {
    vi.spyOn(useAuthModule, "useAuth").mockReturnValue({
      token: "test-jwt-token",
      login: vi.fn(),
      logout: vi.fn(),
      isAuthenticated: true,
    });
    vi.spyOn(useTransactionsModule, "useTransactions").mockReturnValue({
      data: mockResponse,
      isLoading: false,
      error: null,
    } as any);

    renderWithProviders(<TransactionsPage />);

    expect(screen.queryByRole("button", { name: "Previous page" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Next page" })).not.toBeInTheDocument();
  });

  it("shows error message when error occurs", () => {
    vi.spyOn(useAuthModule, "useAuth").mockReturnValue({
      token: "test-jwt-token",
      login: vi.fn(),
      logout: vi.fn(),
      isAuthenticated: true,
    });
    vi.spyOn(useTransactionsModule, "useTransactions").mockReturnValue({
      data: undefined,
      isLoading: false,
      error: new Error("Network error occurred"),
    } as any);

    renderWithProviders(<TransactionsPage />);

    expect(screen.getByText("Network error occurred")).toBeInTheDocument();
  });

  it("calls login when connect button is clicked with JWT", async () => {
    const mockLogin = vi.fn();
    vi.spyOn(useAuthModule, "useAuth").mockReturnValue({
      token: "",
      login: mockLogin,
      logout: vi.fn(),
      isAuthenticated: false,
    });
    vi.spyOn(useTransactionsModule, "useTransactions").mockReturnValue({
      data: undefined,
      isLoading: false,
      error: null,
    } as any);

    renderWithProviders(<TransactionsPage />);

    const input = screen.getByPlaceholderText("eyJhbGciOi...");
    fireEvent.change(input, { target: { value: "my-jwt-token" } });

    const connectButton = screen.getByText("Connect");
    fireEvent.click(connectButton);

    expect(mockLogin).toHaveBeenCalledWith("my-jwt-token");
  });

  it("shows transaction summary stats when transactions exist", () => {
    vi.spyOn(useAuthModule, "useAuth").mockReturnValue({
      token: "test-jwt-token",
      login: vi.fn(),
      logout: vi.fn(),
      isAuthenticated: true,
    });
    vi.spyOn(useTransactionsModule, "useTransactions").mockReturnValue({
      data: mockResponse,
      isLoading: false,
      error: null,
    } as any);

    renderWithProviders(<TransactionsPage />);

    // TransactionStats renders stat labels
    expect(screen.getByText("Total Volume")).toBeInTheDocument();
    // "Completed" appears as both a filter tab and a stat label
    expect(screen.getAllByText(/Completed/).length).toBeGreaterThanOrEqual(1);
    // "Pending" appears as both a filter tab and a stat label
    expect(screen.getAllByText(/Pending/).length).toBeGreaterThanOrEqual(1);
    // "Failed" appears as both a filter tab and a stat label
    expect(screen.getAllByText(/Failed/).length).toBeGreaterThanOrEqual(1);
  });
});
