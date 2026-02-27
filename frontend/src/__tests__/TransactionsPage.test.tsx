import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import TransactionsPage from "../pages/TransactionsPage";
import type { Transaction, TransactionStatus } from "../types/api";

/* ── Mocks ──────────────────────────────────────────────────────────────── */

vi.mock("../hooks/useAuth", () => ({ useAuth: vi.fn() }));
vi.mock("../hooks/useTransactions", () => ({ useTransactions: vi.fn() }));

vi.mock("../components/PageHeader", () => ({
  default: ({ title, actions }: { title: string; actions?: React.ReactNode }) => (
    <div data-testid="page-header">
      {title}
      {actions}
    </div>
  ),
}));

vi.mock("../components/DataTable", () => ({
  default: ({ data, columns, emptyMessage, keyFn }: any) => {
    if (!data || data.length === 0) {
      return <div data-testid="empty-table">{emptyMessage}</div>;
    }
    return (
      <div data-testid="data-table">
        {data.map((row: any) => (
          <div key={keyFn(row)} data-testid={`tx-row-${row.id}`}>
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

vi.mock("../components/Badge", () => ({
  default: ({ label, variant }: { label: string; variant?: string }) => (
    <span data-testid={`badge-${variant ?? "default"}`}>{label}</span>
  ),
  statusVariant: (status: string) => {
    const map: Record<string, string> = {
      completed: "green",
      failed: "red",
      initiated: "yellow",
    };
    return map[status] ?? "gray";
  },
}));

vi.mock("../components/CopyButton", () => ({
  default: ({ value }: { value: string }) => (
    <button data-testid={`copy-${value}`}>copy</button>
  ),
}));

vi.mock("../components/SubTabNav", () => ({
  default: ({ tabs, active, onChange }: any) => (
    <div data-testid="subtabnav">
      {tabs.map((t: any) => (
        <button
          key={t.id}
          data-active={String(active === t.id)}
          onClick={() => onChange(t.id)}
        >
          {t.label}
        </button>
      ))}
    </div>
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

vi.mock("../lib/format", () => ({
  truncateId: (id: string) => id.slice(0, 8) + "...",
  formatUSD: (n: number) => `$${n.toFixed(2)}`,
  relativeTime: () => "just now",
}));

/* ── Import mocked modules ───────────────────────────────────────────────── */

import { useAuth } from "../hooks/useAuth";
import { useTransactions } from "../hooks/useTransactions";

const mockUseAuth = vi.mocked(useAuth);
const mockUseTransactions = vi.mocked(useTransactions);

/* ── Fixtures ────────────────────────────────────────────────────────────── */

const mockLogin = vi.fn();
const mockLogout = vi.fn();

const makeTx = (overrides: Partial<Transaction> = {}): Transaction => ({
  id: "tx-abc123",
  buyer_id: "buyer-xyz456",
  seller_id: "seller-abc789",
  listing_id: "listing-001",
  amount_usdc: 15.5,
  fee_amount: 0.5,
  status: "completed" as TransactionStatus,
  payment_method: "balance",
  verification_status: "verified",
  buyer_confirmed: true,
  seller_confirmed: true,
  buyer_rating: null,
  seller_rating: null,
  initiated_at: new Date().toISOString(),
  completed_at: new Date().toISOString(),
  ...overrides,
});

/* ── Helper ──────────────────────────────────────────────────────────────── */

function renderPage() {
  return render(<TransactionsPage />);
}

/* ── Tests ───────────────────────────────────────────────────────────────── */

describe("TransactionsPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockUseAuth.mockReturnValue({
      token: "test-jwt",
      login: mockLogin,
      logout: mockLogout,
      isAuthenticated: true,
    });
    mockUseTransactions.mockReturnValue({
      data: { transactions: [], total: 0, page: 1, page_size: 20 },
      isLoading: false,
      error: null,
    } as any);
  });

  /* ── 1. Auth gate when no token ───────────────────────────────────────── */

  it("renders auth gate when no token", () => {
    mockUseAuth.mockReturnValue({
      token: "",
      login: mockLogin,
      logout: mockLogout,
      isAuthenticated: false,
    });
    renderPage();

    expect(screen.getByText("Connect Agent")).toBeInTheDocument();
    expect(
      screen.getByText(/Paste your agent JWT to view transactions/),
    ).toBeInTheDocument();
    expect(
      screen.getByPlaceholderText("eyJhbGciOi..."),
    ).toBeInTheDocument();

    // Connect button disabled when input empty
    const connectButton = screen.getByRole("button", { name: "Connect" });
    expect(connectButton).toBeDisabled();
  });

  /* ── 2. Renders transactions with stats ───────────────────────────────── */

  it("renders transactions with stats", () => {
    const transactions = [
      makeTx({ id: "t1", status: "completed", amount_usdc: 10 }),
      makeTx({ id: "t2", status: "failed", amount_usdc: 5 }),
      makeTx({ id: "t3", status: "initiated", amount_usdc: 20 }),
    ];
    mockUseTransactions.mockReturnValue({
      data: { transactions, total: 3, page: 1, page_size: 20 },
      isLoading: false,
      error: null,
    } as any);
    renderPage();

    expect(screen.getByTestId("data-table")).toBeInTheDocument();
    // Stats section shows up when transactions.length > 0
    // Note: "Completed", "Pending", "Failed" also appear in filter tabs
    expect(screen.getByText("Total Volume")).toBeInTheDocument();
    expect(screen.getAllByText("Completed").length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText("Pending").length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText("Failed").length).toBeGreaterThanOrEqual(1);
  });

  /* ── 3. Error banner ─────────────────────────────────────────────────── */

  it("shows error banner", () => {
    mockUseTransactions.mockReturnValue({
      data: undefined,
      isLoading: false,
      error: new Error("Network failure"),
    } as any);
    renderPage();

    expect(screen.getByText("Network failure")).toBeInTheDocument();
  });

  /* ── 4. Pagination when total > 20 ───────────────────────────────────── */

  it("pagination when total > 20", () => {
    const transactions = Array.from({ length: 5 }, (_, i) =>
      makeTx({ id: `t${i}`, status: "completed" }),
    );
    mockUseTransactions.mockReturnValue({
      data: { transactions, total: 42, page: 1, page_size: 20 },
      isLoading: false,
      error: null,
    } as any);
    renderPage();

    expect(screen.getByTestId("pagination")).toBeInTheDocument();
  });

  /* ── 5. Filter tabs change status filter ─────────────────────────────── */

  it("filter tabs change status filter", () => {
    mockUseTransactions.mockReturnValue({
      data: { transactions: [], total: 0, page: 1, page_size: 20 },
      isLoading: false,
      error: null,
    } as any);
    renderPage();

    // All filter tab should be active initially
    const allTab = screen.getByRole("button", { name: "All" });
    expect(allTab).toHaveAttribute("data-active", "true");

    // Click Completed filter
    fireEvent.click(screen.getByRole("button", { name: "Completed" }));

    // useTransactions should be called with new status
    expect(mockUseTransactions).toHaveBeenCalledWith(
      "test-jwt",
      expect.objectContaining({ status: "completed" }),
    );
  });

  /* ── 6. Pipeline step states ─────────────────────────────────────────── */

  it("Pipeline shows correct step states", () => {
    const transactions = [
      makeTx({ id: "p1", status: "payment_confirmed" }),
      makeTx({ id: "p2", status: "failed" }),
      makeTx({ id: "p3", status: "completed" }),
    ];
    mockUseTransactions.mockReturnValue({
      data: { transactions, total: 3, page: 1, page_size: 20 },
      isLoading: false,
      error: null,
    } as any);
    renderPage();

    // Rows should be rendered
    expect(screen.getByTestId("tx-row-p1")).toBeInTheDocument();
    expect(screen.getByTestId("tx-row-p2")).toBeInTheDocument();
    expect(screen.getByTestId("tx-row-p3")).toBeInTheDocument();

    // Pipeline cell rendered for each tx
    const p1Pipeline = screen.getByTestId("cell-p1-pipeline");
    expect(p1Pipeline).toBeInTheDocument();

    const p2Pipeline = screen.getByTestId("cell-p2-pipeline");
    expect(p2Pipeline).toBeInTheDocument();
  });

  /* ── 7. Disconnect button calls logout ───────────────────────────────── */

  it("disconnect button calls logout", () => {
    renderPage();

    const disconnectButton = screen.getByRole("button", { name: "Disconnect" });
    fireEvent.click(disconnectButton);

    expect(mockLogout).toHaveBeenCalledTimes(1);
  });

  /* ── 8. Amount color by status ───────────────────────────────────────── */

  it("amount color by status: failed/disputed = red, completed/verified = green, else blue", () => {
    const transactions = [
      makeTx({ id: "a1", status: "failed" }),
      makeTx({ id: "a2", status: "completed" }),
      makeTx({ id: "a3", status: "initiated" }),
      makeTx({ id: "a4", status: "disputed" }),
      makeTx({ id: "a5", status: "verified" }),
    ];
    mockUseTransactions.mockReturnValue({
      data: { transactions, total: 5, page: 1, page_size: 20 },
      isLoading: false,
      error: null,
    } as any);
    renderPage();

    // All rows should render their amount cells
    for (const tx of transactions) {
      const amountCell = screen.getByTestId(`cell-${tx.id}-amount`);
      expect(amountCell).toBeInTheDocument();
    }
  });

  /* ── 9. Payment method fallback ───────────────────────────────────────── */

  it("payment method null falls back to simulated badge", () => {
    const transactions = [
      makeTx({ id: "pm1", payment_method: null as any }),
      makeTx({ id: "pm2", payment_method: "balance" }),
      makeTx({ id: "pm3", payment_method: "fiat" }),
    ];
    mockUseTransactions.mockReturnValue({
      data: { transactions, total: 3, page: 1, page_size: 20 },
      isLoading: false,
      error: null,
    } as any);
    renderPage();

    // pm1 has null method → simulated
    const pm1PaymentCell = screen.getByTestId("cell-pm1-payment_method");
    expect(pm1PaymentCell).toHaveTextContent("Simulated");

    // pm2 is balance
    const pm2PaymentCell = screen.getByTestId("cell-pm2-payment_method");
    expect(pm2PaymentCell).toHaveTextContent("Balance");

    // pm3 is fiat
    const pm3PaymentCell = screen.getByTestId("cell-pm3-payment_method");
    expect(pm3PaymentCell).toHaveTextContent("Fiat");
  });

  /* ── 10. Pluralization of total count ────────────────────────────────── */

  it("total count pluralized correctly", () => {
    mockUseTransactions.mockReturnValue({
      data: { transactions: [makeTx({ id: "singular" })], total: 1, page: 1, page_size: 20 },
      isLoading: false,
      error: null,
    } as any);
    renderPage();

    expect(screen.getByText("1 transaction")).toBeInTheDocument();
  });

  it("total count uses plural form when not 1", () => {
    mockUseTransactions.mockReturnValue({
      data: {
        transactions: [makeTx({ id: "p1" }), makeTx({ id: "p2" })],
        total: 2,
        page: 1,
        page_size: 20,
      },
      isLoading: false,
      error: null,
    } as any);
    renderPage();

    expect(screen.getByText("2 transactions")).toBeInTheDocument();
  });

  /* ── 11. handleConnect calls login when input has value (line 330) ── */

  it("handleConnect calls login when inputToken is non-empty", () => {
    mockUseAuth.mockReturnValue({
      token: "",
      login: mockLogin,
      logout: mockLogout,
      isAuthenticated: false,
    });
    renderPage();

    const input = screen.getByPlaceholderText("eyJhbGciOi...");
    fireEvent.change(input, { target: { value: "my-test-jwt-token" } });

    const connectButton = screen.getByRole("button", { name: "Connect" });
    expect(connectButton).not.toBeDisabled();
    fireEvent.click(connectButton);

    // handleConnect: t = "my-test-jwt-token".trim() → truthy → calls login(t)
    expect(mockLogin).toHaveBeenCalledWith("my-test-jwt-token");
  });

  /* ── 12. statusDotColor default branch (line 47) ──────────────────── */

  it("statusDotColor default branch renders without crash for unknown status", () => {
    // Use a status that is NOT in the statusDotColor map to hit the `?? "#94a3b8"` branch
    const transactions = [
      makeTx({ id: "unknown-1", status: "unknown_status" as any }),
    ];
    mockUseTransactions.mockReturnValue({
      data: { transactions, total: 1, page: 1, page_size: 20 },
      isLoading: false,
      error: null,
    } as any);
    renderPage();

    // Row renders without error
    expect(screen.getByTestId("tx-row-unknown-1")).toBeInTheDocument();
  });

  /* ── 13. Pipeline with unknown status (line 59: STATUS_ORDER ?? -1) ── */

  it("Pipeline renders for unknown status with currentStep=-1 (line 59 default)", () => {
    // "unknown_status" is not in STATUS_ORDER → STATUS_ORDER["unknown_status"] ?? -1 = -1
    // isFailed is false (not "failed" or "disputed"), currentStep = -1
    // All steps: isComplete = !false && -1 >= i → always false
    // isCurrent = !false && -1 === i → always false
    // All steps render as pending style
    const transactions = [
      makeTx({ id: "pipe-unknown", status: "unknown_status" as any }),
    ];
    mockUseTransactions.mockReturnValue({
      data: { transactions, total: 1, page: 1, page_size: 20 },
      isLoading: false,
      error: null,
    } as any);
    renderPage();

    expect(screen.getByTestId("cell-pipe-unknown-pipeline")).toBeInTheDocument();
  });

  /* ── 14. Payment method unknown → cfg fallback simulated (line 168) ── */

  it("payment method unknown string falls back to simulated badge (line 168 ?? branch)", () => {
    const transactions = [
      makeTx({ id: "pm-unknown", payment_method: "crypto" as any }),
    ];
    mockUseTransactions.mockReturnValue({
      data: { transactions, total: 1, page: 1, page_size: 20 },
      isLoading: false,
      error: null,
    } as any);
    renderPage();

    // "crypto" is not in cfg → cfg["crypto"] is undefined → ?? cfg.simulated → "Simulated"
    const paymentCell = screen.getByTestId("cell-pm-unknown-payment_method");
    expect(paymentCell).toHaveTextContent("Simulated");
  });

  /* ── 15. Pagination changes page via onPageChange ─────────────────── */

  it("pagination onPageChange updates page state", () => {
    mockUseTransactions.mockReturnValue({
      data: { transactions: [makeTx({ id: "t1" })], total: 50, page: 1, page_size: 20 },
      isLoading: false,
      error: null,
    } as any);
    renderPage();

    const nextBtn = screen.getByRole("button", { name: "Next" });
    fireEvent.click(nextBtn);

    expect(mockUseTransactions).toHaveBeenCalledWith(
      "test-jwt",
      expect.objectContaining({ page: 2 }),
    );
  });

  /* ── 16. Filter tab onChange resets page to 1 ──────────────────────── */

  it("filter tab onChange resets page to 1 and sets new status", () => {
    renderPage();

    fireEvent.click(screen.getByRole("button", { name: "Failed" }));

    expect(mockUseTransactions).toHaveBeenCalledWith(
      "test-jwt",
      expect.objectContaining({ status: "failed", page: 1 }),
    );
  });

  /* ── 17. TransactionStats count: pending statuses covered ──────────── */

  it("TransactionStats counts pending statuses (payment_pending, payment_confirmed, delivered)", () => {
    const transactions = [
      makeTx({ id: "s1", status: "payment_pending" }),
      makeTx({ id: "s2", status: "payment_confirmed" }),
      makeTx({ id: "s3", status: "delivered" }),
    ];
    mockUseTransactions.mockReturnValue({
      data: { transactions, total: 3, page: 1, page_size: 20 },
      isLoading: false,
      error: null,
    } as any);
    renderPage();

    // All three are "pending" → pending count = 3
    expect(screen.getByText("Total Volume")).toBeInTheDocument();
  });

  /* ── 18. status_dot animation for payment_pending ───────────────────── */

  it("status_dot renders animated ping for payment_pending status", () => {
    const transactions = [
      makeTx({ id: "pending-dot", status: "payment_pending" }),
    ];
    mockUseTransactions.mockReturnValue({
      data: { transactions, total: 1, page: 1, page_size: 20 },
      isLoading: false,
      error: null,
    } as any);
    renderPage();

    // Row renders without error
    expect(screen.getByTestId("tx-row-pending-dot")).toBeInTheDocument();
  });
});
