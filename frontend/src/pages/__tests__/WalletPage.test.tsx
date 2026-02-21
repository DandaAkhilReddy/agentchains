import { describe, it, expect, vi, beforeEach } from "vitest";
import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { renderWithProviders } from "../../test/test-utils";
import WalletPage from "../WalletPage";
import * as authModule from "../../hooks/useAuth";
import * as api from "../../lib/api";

vi.mock("../../hooks/useAuth");
vi.mock("../../components/Toast", () => ({
  useToast: () => ({ toast: vi.fn() }),
}));
vi.mock("../../lib/api", () => ({
  fetchWalletBalance: vi.fn(),
  fetchWalletHistory: vi.fn(),
  createDeposit: vi.fn(),
}));

describe("WalletPage", () => {
  const mockBalance = {
    balance: 125.5,
    total_deposited: 200.0,
    total_earned: 75.0,
    total_spent: 120.5,
    total_fees_paid: 29.0,
  };

  const mockHistory = {
    entries: [
      {
        id: "tx-1",
        from_account_id: null,
        to_account_id: "acct-1",
        amount: 50.0,
        fee_amount: 0,
        tx_type: "deposit",
        reference_id: "ref-1",
        memo: "Initial deposit",
        created_at: "2026-02-10T10:00:00Z",
      },
      {
        id: "tx-2",
        from_account_id: "acct-1",
        to_account_id: "acct-2",
        amount: 15.0,
        fee_amount: 0.75,
        tx_type: "purchase",
        reference_id: "ref-2",
        memo: "Bought listing",
        created_at: "2026-02-12T14:00:00Z",
      },
      {
        id: "tx-3",
        from_account_id: "acct-3",
        to_account_id: "acct-1",
        amount: 25.0,
        fee_amount: 1.25,
        tx_type: "sale",
        reference_id: "ref-3",
        memo: "Sold data pack",
        created_at: "2026-02-15T09:00:00Z",
      },
    ],
    total: 3,
    page: 1,
    page_size: 10,
  };

  function mockAuthenticated() {
    vi.spyOn(authModule, "useAuth").mockReturnValue({
      token: "test-wallet-token",
      login: vi.fn(),
      logout: vi.fn(),
      isAuthenticated: true,
    } as any);
  }

  function mockUnauthenticated() {
    vi.spyOn(authModule, "useAuth").mockReturnValue({
      token: "",
      login: vi.fn(),
      logout: vi.fn(),
      isAuthenticated: false,
    } as any);
  }

  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(api.fetchWalletBalance).mockResolvedValue(mockBalance);
    vi.mocked(api.fetchWalletHistory).mockResolvedValue(mockHistory);
    vi.mocked(api.createDeposit).mockResolvedValue({
      id: "dep-1",
      amount_usd: 10,
      status: "completed",
    });
  });

  it("shows auth gate when not authenticated", () => {
    mockUnauthenticated();
    renderWithProviders(<WalletPage />);

    expect(screen.getByRole("heading", { name: "Sign In" })).toBeInTheDocument();
    expect(
      screen.getByText("Paste your agent JWT token to access your wallet"),
    ).toBeInTheDocument();
  });

  it("renders wallet page with title when authenticated", async () => {
    mockAuthenticated();
    renderWithProviders(<WalletPage />);

    await waitFor(() => {
      expect(screen.getByText("Wallet")).toBeInTheDocument();
    });
    expect(
      screen.getByText("Manage your balance and credits"),
    ).toBeInTheDocument();
  });

  it("shows balance amount", async () => {
    mockAuthenticated();
    renderWithProviders(<WalletPage />);

    await waitFor(() => {
      expect(screen.getByText("$125.50")).toBeInTheDocument();
    });
    expect(screen.getByText("USD Balance")).toBeInTheDocument();
  });

  it("shows inline stats for deposited, earned, spent, fees", async () => {
    mockAuthenticated();
    renderWithProviders(<WalletPage />);

    await waitFor(() => {
      expect(screen.getByText("Deposited")).toBeInTheDocument();
    });
    expect(screen.getByText("$200.00")).toBeInTheDocument();
    expect(screen.getByText("Earned")).toBeInTheDocument();
    expect(screen.getByText("$75.00")).toBeInTheDocument();
    expect(screen.getByText("Spent")).toBeInTheDocument();
    expect(screen.getByText("$120.50")).toBeInTheDocument();
    // "Fees" appears in both inline stats and the filter tabs
    expect(screen.getAllByText("Fees").length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText("$29.00")).toBeInTheDocument();
  });

  it("shows transaction history section", async () => {
    mockAuthenticated();
    renderWithProviders(<WalletPage />);

    await waitFor(() => {
      expect(screen.getByText("Transaction History")).toBeInTheDocument();
    });
  });

  it("shows transaction filter tabs", async () => {
    mockAuthenticated();
    renderWithProviders(<WalletPage />);

    await waitFor(() => {
      expect(screen.getByText("All")).toBeInTheDocument();
    });
    expect(screen.getByText("Deposits")).toBeInTheDocument();
    expect(screen.getByText("Purchases")).toBeInTheDocument();
    expect(screen.getByText("Sales")).toBeInTheDocument();
    // "Fees" appears in both filter tabs and inline stats
    expect(screen.getAllByText("Fees").length).toBeGreaterThanOrEqual(1);
  });

  it("shows empty history message when no transactions", async () => {
    mockAuthenticated();
    vi.mocked(api.fetchWalletHistory).mockResolvedValue({
      entries: [],
      total: 0,
      page: 1,
      page_size: 10,
    });

    renderWithProviders(<WalletPage />);

    await waitFor(() => {
      expect(screen.getByText("No transactions yet")).toBeInTheDocument();
    });
  });

  it("shows add funds section with credit packages", async () => {
    mockAuthenticated();
    renderWithProviders(<WalletPage />);

    await waitFor(() => {
      expect(screen.getByText("Add Funds")).toBeInTheDocument();
    });
    expect(screen.getByText("Starter")).toBeInTheDocument();
    expect(screen.getByText("Builder")).toBeInTheDocument();
    expect(screen.getByText("Pro")).toBeInTheDocument();
    expect(screen.getByText("Scale")).toBeInTheDocument();
  });

  it("shows disconnect button", async () => {
    mockAuthenticated();
    renderWithProviders(<WalletPage />);

    await waitFor(() => {
      expect(screen.getByText("Disconnect")).toBeInTheDocument();
    });
  });

  it("calls logout when disconnect is clicked", async () => {
    const logoutFn = vi.fn();
    vi.spyOn(authModule, "useAuth").mockReturnValue({
      token: "test-wallet-token",
      login: vi.fn(),
      logout: logoutFn,
      isAuthenticated: true,
    } as any);

    const user = userEvent.setup();
    renderWithProviders(<WalletPage />);

    await waitFor(() => {
      expect(screen.getByText("Disconnect")).toBeInTheDocument();
    });

    await user.click(screen.getByText("Disconnect"));
    expect(logoutFn).toHaveBeenCalled();
  });

  it("login flow works from auth gate", async () => {
    const loginFn = vi.fn();
    vi.spyOn(authModule, "useAuth").mockReturnValue({
      token: "",
      login: loginFn,
      logout: vi.fn(),
      isAuthenticated: false,
    } as any);

    const user = userEvent.setup();
    renderWithProviders(<WalletPage />);

    const input = screen.getByPlaceholderText("eyJhbGciOi...");
    await user.type(input, "my-wallet-jwt");

    const signInBtn = screen.getByRole("button", { name: "Sign In" });
    await user.click(signInBtn);

    expect(loginFn).toHaveBeenCalledWith("my-wallet-jwt");
  });
});
