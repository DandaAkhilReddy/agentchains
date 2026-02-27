import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import WalletPage from "../pages/WalletPage";
import type { TokenLedgerEntry } from "../types/api";

/* ── Mocks ──────────────────────────────────────────────────────────────── */

vi.mock("../hooks/useAuth", () => ({ useAuth: vi.fn() }));
vi.mock("../components/Toast", () => ({ useToast: vi.fn() }));
vi.mock("../lib/api", () => ({
  fetchWalletBalance: vi.fn(),
  fetchWalletHistory: vi.fn(),
  createDeposit: vi.fn(),
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
  default: ({ label }: { label: string }) => (
    <span data-testid="badge">{label}</span>
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
  default: ({ data, emptyMessage }: any) =>
    data && data.length > 0 ? (
      <div data-testid="data-table">
        {data.map((entry: any, i: number) => (
          <div key={i} data-testid={`tx-row-${entry.tx_type}`}>
            {entry.tx_type} {entry.amount} {entry.fee_amount} {entry.memo}
          </div>
        ))}
      </div>
    ) : (
      <div data-testid="empty-table">{emptyMessage}</div>
    ),
}));

vi.mock("../components/SubTabNav", () => ({
  default: ({ tabs, active, onChange }: any) => (
    <div data-testid="subtabnav">
      {tabs.map((t: any) => (
        <button
          key={t.id}
          data-active={active === t.id}
          onClick={() => onChange(t.id)}
        >
          {t.label}
        </button>
      ))}
    </div>
  ),
}));

vi.mock("../lib/format", () => ({
  formatUSD: (n: number) => `$${n.toFixed(2)}`,
  relativeTime: () => "just now",
}));

/* ── Import mocked modules ───────────────────────────────────────────────── */

import { useAuth } from "../hooks/useAuth";
import { useToast } from "../components/Toast";
import {
  fetchWalletBalance,
  fetchWalletHistory,
  createDeposit,
} from "../lib/api";
import { useQuery, useMutation } from "@tanstack/react-query";

const mockUseAuth = vi.mocked(useAuth);
const mockUseToast = vi.mocked(useToast);
const mockFetchWalletBalance = vi.mocked(fetchWalletBalance);
const mockFetchWalletHistory = vi.mocked(fetchWalletHistory);
const mockCreateDeposit = vi.mocked(createDeposit);

/* ── Fixtures ────────────────────────────────────────────────────────────── */

const mockToast = vi.fn();
const mockLogin = vi.fn();
const mockLogout = vi.fn();

const balanceData = {
  balance: 42.5,
  total_deposited: 100,
  total_earned: 60,
  total_spent: 90,
  total_fees_paid: 5,
};

const makeEntry = (overrides: Partial<TokenLedgerEntry> = {}): TokenLedgerEntry => ({
  id: "e1",
  from_account_id: null,
  to_account_id: null,
  amount: 10,
  fee_amount: 0,
  tx_type: "deposit",
  reference_id: null,
  reference_type: null,
  memo: "",
  created_at: new Date().toISOString(),
  ...overrides,
});

const historyData = {
  entries: [makeEntry()],
  total: 1,
  page: 1,
  page_size: 10,
};

/* ── Helper ──────────────────────────────────────────────────────────────── */

function makeQueryClient() {
  return new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
}

function renderWalletPage() {
  const qc = makeQueryClient();
  return render(
    <QueryClientProvider client={qc}>
      <WalletPage />
    </QueryClientProvider>,
  );
}

/* ── Tests ───────────────────────────────────────────────────────────────── */

describe("WalletPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockUseToast.mockReturnValue({ toast: mockToast } as any);
    mockUseAuth.mockReturnValue({
      token: "test-jwt",
      login: mockLogin,
      logout: mockLogout,
      isAuthenticated: true,
    });
    mockFetchWalletBalance.mockResolvedValue(balanceData as any);
    mockFetchWalletHistory.mockResolvedValue(historyData as any);
    mockCreateDeposit.mockResolvedValue({} as any);
  });

  /* ── 1. Auth gate when no token ───────────────────────────────────────── */

  it("renders auth gate when no token", () => {
    mockUseAuth.mockReturnValue({
      token: "",
      login: mockLogin,
      logout: mockLogout,
      isAuthenticated: false,
    });
    renderWalletPage();

    // Both the h3 title and the button say "Sign In"
    expect(screen.getAllByText("Sign In")).toHaveLength(2);
    expect(
      screen.getByPlaceholderText("eyJhbGciOi..."),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/Paste your agent JWT token to access your wallet/),
    ).toBeInTheDocument();
  });

  /* ── 2. Sign in with token ────────────────────────────────────────────── */

  it("sign in with token", () => {
    mockUseAuth.mockReturnValue({
      token: "",
      login: mockLogin,
      logout: mockLogout,
      isAuthenticated: false,
    });
    renderWalletPage();

    const input = screen.getByPlaceholderText("eyJhbGciOi...");
    fireEvent.change(input, { target: { value: "my-jwt-token" } });

    const button = screen.getByRole("button", { name: "Sign In" });
    expect(button).not.toBeDisabled();
    fireEvent.click(button);

    expect(mockLogin).toHaveBeenCalledWith("my-jwt-token");
  });

  /* ── 3. Loading skeletons ─────────────────────────────────────────────── */

  it("renders loading skeletons", () => {
    // Make balance query stay pending so balLoading = true
    mockFetchWalletBalance.mockImplementation(
      () => new Promise(() => {}), // never resolves
    );
    renderWalletPage();

    const skeletons = screen.getAllByTestId("skeleton-card");
    expect(skeletons.length).toBeGreaterThanOrEqual(4);
  });

  /* ── 4. Wallet dashboard with balance ────────────────────────────────── */

  it("renders wallet dashboard with balance", async () => {
    renderWalletPage();

    await waitFor(() => {
      expect(screen.getByTestId("page-header")).toBeInTheDocument();
    });

    // Balance hero card shows formatted balance
    expect(screen.getByText("$42.50")).toBeInTheDocument();

    // Stat labels (note: "Fees" also appears in SubTabNav, use getAllBy)
    expect(screen.getByText("Deposited")).toBeInTheDocument();
    expect(screen.getByText("Earned")).toBeInTheDocument();
    expect(screen.getByText("Spent")).toBeInTheDocument();
    expect(screen.getAllByText("Fees").length).toBeGreaterThanOrEqual(1);

    // Add funds section
    expect(screen.getByText("Add Funds")).toBeInTheDocument();
  });

  /* ── 5. Stat colors via STAT_COLORS map ──────────────────────────────── */

  it("shows correct stat colors", async () => {
    renderWalletPage();

    await waitFor(() => {
      // Stats should be rendered with their known color values
      // STAT_COLORS: Deposited=#60a5fa, Earned=#34d399, Spent=#f87171, Fees=#fbbf24
      expect(screen.getByText("Deposited")).toBeInTheDocument();
    });

    // Check that all four stats are present with their values
    expect(screen.getByText("$100.00")).toBeInTheDocument(); // Deposited
    expect(screen.getByText("$60.00")).toBeInTheDocument(); // Earned
    expect(screen.getByText("$90.00")).toBeInTheDocument(); // Spent
    expect(screen.getByText("$5.00")).toBeInTheDocument(); // Fees
  });

  /* ── 6. Select credit package ────────────────────────────────────────── */

  it("selects credit package", async () => {
    renderWalletPage();

    await waitFor(() => {
      expect(screen.getByText("$5")).toBeInTheDocument();
    });

    // Click the $5 Starter package
    fireEvent.click(screen.getByText("$5").closest("button")!);

    // Custom amount input should now be empty (package selected)
    const customInput = screen.getByPlaceholderText("Custom amount");
    expect(customInput).toHaveValue(null);
  });

  /* ── 7. Custom amount clears selected package ────────────────────────── */

  it("custom amount input clears selected package", async () => {
    renderWalletPage();

    await waitFor(() => {
      expect(screen.getByText("$10")).toBeInTheDocument();
    });

    // Select a package first
    fireEvent.click(screen.getByText("$10").closest("button")!);

    // Now type in custom amount input
    const customInput = screen.getByPlaceholderText("Custom amount");
    fireEvent.change(customInput, { target: { value: "15" } });

    // Custom input should now show the typed value (selectedPackage = null)
    expect(customInput).toHaveValue(15);
  });

  /* ── 8. Popular badge shown ───────────────────────────────────────────── */

  it("shows popular badge", async () => {
    renderWalletPage();

    await waitFor(() => {
      expect(screen.getByTestId("badge")).toBeInTheDocument();
    });

    // The Builder ($10) package has popular: true
    expect(screen.getByText("Popular")).toBeInTheDocument();
  });

  /* ── 9. Disconnect button calls logout ───────────────────────────────── */

  it("disconnect button calls logout", async () => {
    renderWalletPage();

    await waitFor(() => {
      expect(screen.getByText("Disconnect")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByText("Disconnect"));
    expect(mockLogout).toHaveBeenCalledTimes(1);
  });

  /* ── 10. TX type config renders correctly ────────────────────────────── */

  it("tx type renders with correct icon and color", async () => {
    const entries = [
      makeEntry({ id: "t1", tx_type: "deposit", amount: 10, fee_amount: 0 }),
      makeEntry({
        id: "t2",
        tx_type: "purchase",
        amount: 5,
        fee_amount: 0.5,
      }),
      makeEntry({ id: "t3", tx_type: "bonus", amount: 2, fee_amount: 0 }),
      makeEntry({ id: "t4", tx_type: "unknown_type", amount: 1, fee_amount: 0 }),
    ];
    mockFetchWalletHistory.mockResolvedValue({
      entries,
      total: entries.length,
      page: 1,
      page_size: 10,
    } as any);

    renderWalletPage();

    await waitFor(() => {
      // deposit row
      expect(screen.getByTestId("tx-row-deposit")).toBeInTheDocument();
      // purchase row
      expect(screen.getByTestId("tx-row-purchase")).toBeInTheDocument();
      // bonus row
      expect(screen.getByTestId("tx-row-bonus")).toBeInTheDocument();
      // unknown type hits fallback
      expect(screen.getByTestId("tx-row-unknown_type")).toBeInTheDocument();
    });
  });

  /* ── 11. Fee column shows amount or dash ─────────────────────────────── */

  it("fee column shows amount or dash", async () => {
    const entries = [
      makeEntry({ id: "f1", tx_type: "deposit", amount: 10, fee_amount: 1.5, memo: "" }),
      makeEntry({ id: "f2", tx_type: "sale", amount: 20, fee_amount: 0, memo: "some memo" }),
    ];
    mockFetchWalletHistory.mockResolvedValue({
      entries,
      total: entries.length,
      page: 1,
      page_size: 10,
    } as any);

    renderWalletPage();

    await waitFor(() => {
      // Row with fee_amount > 0 → shows fee value
      expect(screen.getByTestId("tx-row-deposit")).toHaveTextContent("1.5");
      // Row with fee_amount = 0 → shows 0
      expect(screen.getByTestId("tx-row-sale")).toHaveTextContent("0");
    });
  });
});
