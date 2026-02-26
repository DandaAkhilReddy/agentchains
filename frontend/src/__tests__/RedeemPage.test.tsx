import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import RedeemPage from "../pages/RedeemPage";
import type { RedemptionRequest } from "../types/api";

/* ── Mocks ──────────────────────────────────────────────────────────────── */

vi.mock("../hooks/useAuth", () => ({ useAuth: vi.fn() }));
vi.mock("../components/Toast", () => ({ useToast: vi.fn() }));
vi.mock("../lib/api", () => ({
  fetchRedemptions: vi.fn(),
  fetchRedemptionMethods: vi.fn(),
  createRedemption: vi.fn(),
  cancelRedemption: vi.fn(),
}));

vi.mock("../components/PageHeader", () => ({
  default: ({ title }: { title: string }) => (
    <div data-testid="page-header">{title}</div>
  ),
}));

vi.mock("../components/Skeleton", () => ({
  SkeletonCard: () => <div data-testid="skeleton-card" />,
}));

vi.mock("../components/Badge", () => ({
  default: ({ label, variant }: { label: string; variant: string }) => (
    <span data-testid={`badge-${variant}`}>{label}</span>
  ),
}));

vi.mock("../components/Pagination", () => ({
  default: ({ page, totalPages, onPageChange }: any) => (
    <div data-testid="pagination">
      <button onClick={() => onPageChange(page + 1)}>Next</button>
      <span>
        {page}/{totalPages}
      </span>
    </div>
  ),
}));

vi.mock("../components/DataTable", () => ({
  default: ({
    data,
    columns,
    emptyMessage,
    keyFn,
  }: {
    data: any[];
    columns: any[];
    emptyMessage: string;
    keyFn: (row: any) => string;
  }) => {
    if (!data || data.length === 0) {
      return <div data-testid="empty-table">{emptyMessage}</div>;
    }
    return (
      <div data-testid="data-table">
        {data.map((row: any) => (
          <div key={keyFn(row)} data-testid={`row-${row.id}`}>
            {columns.map((col: any) => (
              <span key={col.key} data-testid={`cell-${row.id}-${col.key}`}>
                {col.render ? col.render(row) : null}
              </span>
            ))}
          </div>
        ))}
      </div>
    );
  },
}));

vi.mock("../lib/format", () => ({
  formatUSD: (n: number) => `$${n.toFixed(2)}`,
  relativeTime: (iso: string | null) => (iso ? "just now" : "—"),
}));

/* ── Import mocked modules ───────────────────────────────────────────────── */

import { useAuth } from "../hooks/useAuth";
import { useToast } from "../components/Toast";
import {
  fetchRedemptions,
  fetchRedemptionMethods,
  createRedemption,
  cancelRedemption,
} from "../lib/api";

const mockUseAuth = vi.mocked(useAuth);
const mockUseToast = vi.mocked(useToast);
const mockFetchRedemptions = vi.mocked(fetchRedemptions);
const mockFetchRedemptionMethods = vi.mocked(fetchRedemptionMethods);
const mockCreateRedemption = vi.mocked(createRedemption);
const mockCancelRedemption = vi.mocked(cancelRedemption);

/* ── Fixtures ────────────────────────────────────────────────────────────── */

const mockToast = vi.fn();
const mockLogin = vi.fn();
const mockLogout = vi.fn();

const defaultMethods = {
  methods: [
    {
      type: "api_credits",
      label: "API Credits",
      min_usd: 0.1,
      processing_time: "Instant",
      available: true,
    },
    {
      type: "gift_card",
      label: "Gift Card",
      min_usd: 1.0,
      processing_time: "1-2 hours",
      available: true,
    },
    {
      type: "bank_withdrawal",
      label: "Bank Transfer",
      min_usd: 10.0,
      processing_time: "2-5 days",
      available: false,
    },
    {
      type: "upi",
      label: "UPI Transfer",
      min_usd: 5.0,
      processing_time: "Instant",
      available: true,
    },
  ],
};

const emptyHistory = { redemptions: [], total: 0, page: 1, page_size: 10 };

const makeRedemption = (
  overrides: Partial<RedemptionRequest> = {},
): RedemptionRequest => ({
  id: "r1",
  creator_id: "c1",
  redemption_type: "gift_card",
  amount_usd: 5.0,
  currency: "USD",
  status: "pending",
  payout_ref: null,
  admin_notes: "",
  rejection_reason: "",
  created_at: new Date().toISOString(),
  processed_at: null,
  completed_at: null,
  ...overrides,
});

/* ── Helper ──────────────────────────────────────────────────────────────── */

function makeQueryClient() {
  return new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
}

function renderRedeemPage() {
  const qc = makeQueryClient();
  return render(
    <QueryClientProvider client={qc}>
      <RedeemPage />
    </QueryClientProvider>,
  );
}

/* ── Tests ───────────────────────────────────────────────────────────────── */

describe("RedeemPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockUseToast.mockReturnValue({ toast: mockToast } as any);
    mockUseAuth.mockReturnValue({
      token: "test-jwt",
      login: mockLogin,
      logout: mockLogout,
      isAuthenticated: true,
    });
    mockFetchRedemptionMethods.mockResolvedValue(defaultMethods as any);
    mockFetchRedemptions.mockResolvedValue(emptyHistory as any);
    mockCreateRedemption.mockResolvedValue({} as any);
    mockCancelRedemption.mockResolvedValue({} as any);
  });

  /* ── 1. Auth gate when no token ───────────────────────────────────────── */

  it("renders auth gate when no token", () => {
    mockUseAuth.mockReturnValue({
      token: "",
      login: mockLogin,
      logout: mockLogout,
      isAuthenticated: false,
    });
    renderRedeemPage();

    // Both the h3 heading and the button say "Sign In"
    expect(screen.getAllByText("Sign In")).toHaveLength(2);
    expect(screen.getByPlaceholderText("eyJhbGciOi...")).toBeInTheDocument();
    expect(
      screen.getByText(/Paste your agent JWT token to access withdrawals/),
    ).toBeInTheDocument();
  });

  /* ── 2. Loading skeletons when methods loading ────────────────────────── */

  it("renders loading skeletons when methods loading", () => {
    mockFetchRedemptionMethods.mockImplementation(() => new Promise(() => {}));
    renderRedeemPage();

    const skeletons = screen.getAllByTestId("skeleton-card");
    expect(skeletons.length).toBeGreaterThanOrEqual(4);
  });

  /* ── 3. Method cards rendered ────────────────────────────────────────── */

  it("renders method cards", async () => {
    renderRedeemPage();

    await waitFor(() => {
      expect(screen.getByText("API Credits")).toBeInTheDocument();
    });

    expect(screen.getByText("Gift Card")).toBeInTheDocument();
    expect(screen.getByText("Bank Transfer")).toBeInTheDocument();
    expect(screen.getByText("UPI Transfer")).toBeInTheDocument();
  });

  /* ── 4. Unavailable methods show overlay ─────────────────────────────── */

  it("disabled unavailable methods", async () => {
    renderRedeemPage();

    await waitFor(() => {
      expect(screen.getByText("Unavailable")).toBeInTheDocument();
    });

    // Bank Transfer is available: false — its button should be disabled
    const bankButton = screen
      .getByText("Bank Transfer")
      .closest("button") as HTMLButtonElement;
    expect(bankButton).toBeDisabled();
  });

  /* ── 5. Amount input shows when method selected ───────────────────────── */

  it("shows amount input when method selected", async () => {
    renderRedeemPage();

    await waitFor(() => {
      expect(screen.getByText("API Credits")).toBeInTheDocument();
    });

    // Amount section hidden initially
    expect(screen.queryByText("Withdrawal Amount")).toBeNull();

    // Click API Credits
    fireEvent.click(screen.getByText("API Credits").closest("button")!);

    await waitFor(() => {
      expect(screen.getByText("Withdrawal Amount")).toBeInTheDocument();
    });

    // Min amount shown
    expect(screen.getByText("Min: $0.10")).toBeInTheDocument();
  });

  /* ── 6. Validation error for too-low amount ───────────────────────────── */

  it("shows validation error for too-low amount", async () => {
    renderRedeemPage();

    await waitFor(() => {
      expect(screen.getByText("API Credits")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByText("API Credits").closest("button")!);

    await waitFor(() => {
      expect(screen.getByText("Withdrawal Amount")).toBeInTheDocument();
    });

    // Enter amount below minimum (0.05 < 0.10)
    const input = screen.getByPlaceholderText(/0.10 or more/);
    fireEvent.change(input, { target: { value: "0.05" } });

    await waitFor(() => {
      expect(
        screen.getByText(/Minimum withdrawal is \$0\.10/),
      ).toBeInTheDocument();
    });

    // Submit button should be disabled
    const submitBtn = screen.getByRole("button", { name: "Request Withdrawal" });
    expect(submitBtn).toBeDisabled();
  });

  /* ── 7. Cancel button on pending redemption ───────────────────────────── */

  it("cancel button on pending redemption", async () => {
    const redemptions = [makeRedemption({ id: "pending-1", status: "pending" })];
    mockFetchRedemptions.mockResolvedValue({
      redemptions,
      total: 1,
      page: 1,
      page_size: 10,
    } as any);
    renderRedeemPage();

    await waitFor(() => {
      expect(screen.getByText("Cancel")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByText("Cancel"));

    await waitFor(() => {
      expect(mockCancelRedemption).toHaveBeenCalledWith(
        "test-jwt",
        "pending-1",
      );
    });
  });

  /* ── 8. completed_at shows relative time or dash ─────────────────────── */

  it("completed_at shows relative time or dash", async () => {
    const redemptions = [
      makeRedemption({
        id: "c1",
        status: "completed",
        completed_at: new Date().toISOString(),
      }),
      makeRedemption({ id: "c2", status: "pending", completed_at: null }),
    ];
    mockFetchRedemptions.mockResolvedValue({
      redemptions,
      total: 2,
      page: 1,
      page_size: 10,
    } as any);
    renderRedeemPage();

    await waitFor(() => {
      expect(screen.getByTestId("row-c1")).toBeInTheDocument();
    });

    // c1 has completed_at → "just now"
    const c1CompletedCell = screen.getByTestId("cell-c1-completed_at");
    expect(c1CompletedCell).toHaveTextContent("just now");

    // c2 has no completed_at → "--" (double dash, as written in the source)
    const c2CompletedCell = screen.getByTestId("cell-c2-completed_at");
    expect(c2CompletedCell).toHaveTextContent("--");
  });
});
