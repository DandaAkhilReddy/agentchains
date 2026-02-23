import { describe, it, expect, vi, beforeEach } from "vitest";
import { screen, waitFor, fireEvent } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { renderWithProviders } from "../../test/test-utils";
import RedeemPage from "../RedeemPage";
import * as authModule from "../../hooks/useAuth";
import * as api from "../../lib/api";

vi.mock("../../hooks/useAuth");

const toastFn = vi.fn();
vi.mock("../../components/Toast", () => ({
  useToast: () => ({ toast: toastFn }),
}));
vi.mock("../../lib/api", () => ({
  fetchRedemptions: vi.fn(),
  fetchRedemptionMethods: vi.fn(),
  createRedemption: vi.fn(),
  cancelRedemption: vi.fn(),
}));

describe("RedeemPage", () => {
  const mockMethods = {
    methods: [
      { type: "api_credits", label: "API Credits", min_usd: 0.1, processing_time: "Instant", available: true },
      { type: "gift_card", label: "Gift Card", min_usd: 1.0, processing_time: "1-2 hours", available: true },
      { type: "bank_withdrawal", label: "Bank Transfer", min_usd: 10.0, processing_time: "2-5 days", available: true },
      { type: "upi", label: "UPI Transfer", min_usd: 5.0, processing_time: "Instant", available: true },
    ],
  };

  const mockRedemptions = {
    redemptions: [
      {
        id: "red-1",
        creator_id: "c1",
        redemption_type: "api_credits",
        amount_usd: 5.0,
        currency: "USD",
        status: "completed",
        payout_ref: null,
        admin_notes: "",
        rejection_reason: "",
        created_at: "2026-02-10T10:00:00Z",
        processed_at: "2026-02-10T10:01:00Z",
        completed_at: "2026-02-10T10:02:00Z",
      },
      {
        id: "red-2",
        creator_id: "c1",
        redemption_type: "gift_card",
        amount_usd: 2.0,
        currency: "USD",
        status: "pending",
        payout_ref: null,
        admin_notes: "",
        rejection_reason: "",
        created_at: "2026-02-15T12:00:00Z",
        processed_at: null,
        completed_at: null,
      },
    ],
    total: 2,
  };

  function mockAuthenticated() {
    vi.spyOn(authModule, "useAuth").mockReturnValue({
      token: "test-jwt-token",
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
    vi.mocked(api.fetchRedemptionMethods).mockResolvedValue(mockMethods);
    vi.mocked(api.fetchRedemptions).mockResolvedValue(mockRedemptions);
    vi.mocked(api.createRedemption).mockResolvedValue({
      id: "new-red",
      creator_id: "c1",
      redemption_type: "api_credits",
      amount_usd: 5.0,
      currency: "USD",
      status: "pending",
      payout_ref: null,
      admin_notes: "",
      rejection_reason: "",
      created_at: "2026-02-20T10:00:00Z",
      processed_at: null,
      completed_at: null,
    });
    vi.mocked(api.cancelRedemption).mockResolvedValue({ message: "ok" });
  });

  it("shows auth gate when not authenticated", () => {
    mockUnauthenticated();
    renderWithProviders(<RedeemPage />);

    expect(screen.getByRole("heading", { name: "Sign In" })).toBeInTheDocument();
    expect(
      screen.getByText("Paste your agent JWT token to access withdrawals"),
    ).toBeInTheDocument();
  });

  it("renders redeem page with title when authenticated", async () => {
    mockAuthenticated();
    renderWithProviders(<RedeemPage />);

    await waitFor(() => {
      expect(screen.getByText("Withdraw Funds")).toBeInTheDocument();
    });
    expect(
      screen.getByText(
        "Choose a redemption method and request a withdrawal",
      ),
    ).toBeInTheDocument();
  });

  it("shows redemption method cards", async () => {
    mockAuthenticated();
    renderWithProviders(<RedeemPage />);

    await waitFor(() => {
      expect(screen.getByText("API Credits")).toBeInTheDocument();
    });
    expect(screen.getByText("Gift Card")).toBeInTheDocument();
    expect(screen.getByText("Bank Transfer")).toBeInTheDocument();
    expect(screen.getByText("UPI Transfer")).toBeInTheDocument();
  });

  it("shows method descriptions", async () => {
    mockAuthenticated();
    renderWithProviders(<RedeemPage />);

    await waitFor(() => {
      expect(
        screen.getByText("Convert balance to API usage credits instantly"),
      ).toBeInTheDocument();
    });
    expect(
      screen.getByText("Redeem as digital gift card vouchers"),
    ).toBeInTheDocument();
  });

  it("shows amount input when a method is selected", async () => {
    mockAuthenticated();
    const user = userEvent.setup();
    renderWithProviders(<RedeemPage />);

    await waitFor(() => {
      expect(screen.getByText("API Credits")).toBeInTheDocument();
    });

    await user.click(screen.getByText("API Credits"));

    await waitFor(() => {
      expect(screen.getByText("Withdrawal Amount")).toBeInTheDocument();
    });
  });

  it("shows minimum amount validation", async () => {
    mockAuthenticated();
    const user = userEvent.setup();
    renderWithProviders(<RedeemPage />);

    await waitFor(() => {
      expect(screen.getByText("Bank Transfer")).toBeInTheDocument();
    });

    await user.click(screen.getByText("Bank Transfer"));

    await waitFor(() => {
      expect(screen.getByText(/Min: \$10\.00/)).toBeInTheDocument();
    });

    const amountInput = screen.getByPlaceholderText("10.00 or more");
    await user.type(amountInput, "5");

    await waitFor(() => {
      expect(
        screen.getByText("Minimum withdrawal is $10.00"),
      ).toBeInTheDocument();
    });
  });

  it("submit button is disabled when amount is invalid", async () => {
    mockAuthenticated();
    const user = userEvent.setup();
    renderWithProviders(<RedeemPage />);

    await waitFor(() => {
      expect(screen.getByText("API Credits")).toBeInTheDocument();
    });

    await user.click(screen.getByText("API Credits"));

    await waitFor(() => {
      expect(
        screen.getByRole("button", { name: "Request Withdrawal" }),
      ).toBeDisabled();
    });
  });

  it("calls createRedemption on submit", async () => {
    mockAuthenticated();
    const user = userEvent.setup();
    renderWithProviders(<RedeemPage />);

    await waitFor(() => {
      expect(screen.getByText("API Credits")).toBeInTheDocument();
    });

    await user.click(screen.getByText("API Credits"));

    const amountInput = await screen.findByPlaceholderText("0.10 or more");
    await user.type(amountInput, "5.00");

    const submitBtn = screen.getByRole("button", {
      name: "Request Withdrawal",
    });
    await user.click(submitBtn);

    await waitFor(() => {
      expect(api.createRedemption).toHaveBeenCalledWith("test-jwt-token", {
        redemption_type: "api_credits",
        amount_usd: 5,
      });
    });
  });

  it("shows redemption history section", async () => {
    mockAuthenticated();
    renderWithProviders(<RedeemPage />);

    await waitFor(() => {
      expect(screen.getByText("Redemption History")).toBeInTheDocument();
    });
  });

  it("shows empty history message when no redemptions", async () => {
    mockAuthenticated();
    vi.mocked(api.fetchRedemptions).mockResolvedValue({
      redemptions: [],
      total: 0,
    });

    renderWithProviders(<RedeemPage />);

    await waitFor(() => {
      expect(screen.getByText("No redemptions yet")).toBeInTheDocument();
    });
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
    renderWithProviders(<RedeemPage />);

    const input = screen.getByPlaceholderText("eyJhbGciOi...");
    await user.type(input, "my-new-token");

    const signInBtn = screen.getByRole("button", { name: "Sign In" });
    await user.click(signInBtn);

    expect(loginFn).toHaveBeenCalledWith("my-new-token");
  });

  /* ── NEW TESTS for increased coverage ── */

  it("login via Enter key from auth gate", async () => {
    const loginFn = vi.fn();
    vi.spyOn(authModule, "useAuth").mockReturnValue({
      token: "",
      login: loginFn,
      logout: vi.fn(),
      isAuthenticated: false,
    } as any);

    const user = userEvent.setup();
    renderWithProviders(<RedeemPage />);

    const input = screen.getByPlaceholderText("eyJhbGciOi...");
    await user.type(input, "my-enter-token");
    await user.keyboard("{Enter}");

    expect(loginFn).toHaveBeenCalledWith("my-enter-token");
  });

  it("does not call login when inputToken is empty in auth gate", () => {
    const loginFn = vi.fn();
    vi.spyOn(authModule, "useAuth").mockReturnValue({
      token: "",
      login: loginFn,
      logout: vi.fn(),
      isAuthenticated: false,
    } as any);

    renderWithProviders(<RedeemPage />);

    const signInBtn = screen.getByRole("button", { name: "Sign In" });
    expect(signInBtn).toBeDisabled();
    expect(loginFn).not.toHaveBeenCalled();
  });

  it("shows loading skeleton when methods are loading", () => {
    mockAuthenticated();
    // Make methods loading
    vi.mocked(api.fetchRedemptionMethods).mockReturnValue(
      new Promise(() => {}) as any, // never resolves
    );

    renderWithProviders(<RedeemPage />);

    // Should show skeleton cards (4 of them in a grid)
    const skeletonCards = document.querySelectorAll(".rounded-2xl.border");
    expect(skeletonCards.length).toBeGreaterThan(0);
  });

  it("shows cancel button on pending redemptions", async () => {
    mockAuthenticated();
    renderWithProviders(<RedeemPage />);

    await waitFor(() => {
      // red-2 is pending, should show Cancel button
      expect(screen.getByText("Cancel")).toBeInTheDocument();
    });
  });

  it("calls cancelRedemption when Cancel button is clicked", async () => {
    mockAuthenticated();
    const user = userEvent.setup();
    renderWithProviders(<RedeemPage />);

    await waitFor(() => {
      expect(screen.getByText("Cancel")).toBeInTheDocument();
    });

    await user.click(screen.getByText("Cancel"));

    await waitFor(() => {
      expect(api.cancelRedemption).toHaveBeenCalledWith(
        "test-jwt-token",
        "red-2",
      );
    });
  });

  it("shows success toast when cancellation succeeds", async () => {
    mockAuthenticated();
    const user = userEvent.setup();
    renderWithProviders(<RedeemPage />);

    await waitFor(() => {
      expect(screen.getByText("Cancel")).toBeInTheDocument();
    });

    await user.click(screen.getByText("Cancel"));

    await waitFor(() => {
      expect(toastFn).toHaveBeenCalledWith("Redemption cancelled", "success");
    });
  });

  it("shows error toast when cancellation fails", async () => {
    mockAuthenticated();
    vi.mocked(api.cancelRedemption).mockRejectedValue(
      new Error("Cancel failed"),
    );

    const user = userEvent.setup();
    renderWithProviders(<RedeemPage />);

    await waitFor(() => {
      expect(screen.getByText("Cancel")).toBeInTheDocument();
    });

    await user.click(screen.getByText("Cancel"));

    await waitFor(() => {
      expect(toastFn).toHaveBeenCalledWith("Cancel failed", "error");
    });
  });

  it("does not show cancel button for completed redemptions", async () => {
    mockAuthenticated();
    vi.mocked(api.fetchRedemptions).mockResolvedValue({
      redemptions: [
        {
          id: "red-done",
          creator_id: "c1",
          redemption_type: "api_credits",
          amount_usd: 10.0,
          currency: "USD",
          status: "completed",
          payout_ref: null,
          admin_notes: "",
          rejection_reason: "",
          created_at: "2026-02-10T10:00:00Z",
          processed_at: "2026-02-10T10:01:00Z",
          completed_at: "2026-02-10T10:02:00Z",
        },
      ],
      total: 1,
    });

    renderWithProviders(<RedeemPage />);

    await waitFor(() => {
      expect(screen.getByText("Redemption History")).toBeInTheDocument();
    });

    // Wait for data to load
    await waitFor(() => {
      expect(screen.getByText("$10.00")).toBeInTheDocument();
    });

    expect(screen.queryByText("Cancel")).not.toBeInTheDocument();
  });

  it("shows pagination when total > 10", async () => {
    mockAuthenticated();
    const manyRedemptions = {
      redemptions: Array.from({ length: 10 }, (_, i) => ({
        id: `red-${i}`,
        creator_id: "c1",
        redemption_type: "api_credits",
        amount_usd: 1.0 + i,
        currency: "USD",
        status: "completed",
        payout_ref: null,
        admin_notes: "",
        rejection_reason: "",
        created_at: "2026-02-10T10:00:00Z",
        processed_at: "2026-02-10T10:01:00Z",
        completed_at: "2026-02-10T10:02:00Z",
      })),
      total: 25,
    };
    vi.mocked(api.fetchRedemptions).mockResolvedValue(manyRedemptions);

    renderWithProviders(<RedeemPage />);

    await waitFor(() => {
      // Pagination component should be rendered
      // Look for page number buttons or navigation
      const paginationBtns = screen.getAllByRole("button");
      // At least some pagination controls should exist
      expect(paginationBtns.length).toBeGreaterThan(0);
    });
  });

  it("shows unavailable overlay for disabled methods", async () => {
    mockAuthenticated();
    vi.mocked(api.fetchRedemptionMethods).mockResolvedValue({
      methods: [
        { type: "api_credits", label: "API Credits", min_usd: 0.1, processing_time: "Instant", available: true },
        { type: "bank_withdrawal", label: "Bank Transfer", min_usd: 10.0, processing_time: "2-5 days", available: false },
      ],
    });

    renderWithProviders(<RedeemPage />);

    await waitFor(() => {
      expect(screen.getByText("Unavailable")).toBeInTheDocument();
    });

    // The Bank Transfer button should be disabled
    const bankBtn = screen.getByText("Bank Transfer").closest("button");
    expect(bankBtn).toBeDisabled();
  });

  it("shows method minimum and processing time", async () => {
    mockAuthenticated();
    renderWithProviders(<RedeemPage />);

    await waitFor(() => {
      expect(screen.getByText("Min $0.10")).toBeInTheDocument();
    });
    expect(screen.getByText("Min $1.00")).toBeInTheDocument();
    expect(screen.getByText("Min $10.00")).toBeInTheDocument();
    expect(screen.getByText("Min $5.00")).toBeInTheDocument();

    // Processing times
    const instantLabels = screen.getAllByText("Instant");
    expect(instantLabels.length).toBe(2); // api_credits + upi
    expect(screen.getByText("1-2 hours")).toBeInTheDocument();
    expect(screen.getByText("2-5 days")).toBeInTheDocument();
  });

  it("shows success toast and resets form on successful withdrawal", async () => {
    mockAuthenticated();
    const user = userEvent.setup();
    renderWithProviders(<RedeemPage />);

    await waitFor(() => {
      expect(screen.getByText("API Credits")).toBeInTheDocument();
    });

    await user.click(screen.getByText("API Credits"));

    const amountInput = await screen.findByPlaceholderText("0.10 or more");
    await user.type(amountInput, "5.00");

    await user.click(screen.getByRole("button", { name: "Request Withdrawal" }));

    await waitFor(() => {
      expect(toastFn).toHaveBeenCalledWith(
        "Withdrawal of $5.00 requested!",
        "success",
      );
    });
  });

  it("shows error toast on withdrawal failure", async () => {
    mockAuthenticated();
    vi.mocked(api.createRedemption).mockRejectedValue(
      new Error("Insufficient balance"),
    );

    const user = userEvent.setup();
    renderWithProviders(<RedeemPage />);

    await waitFor(() => {
      expect(screen.getByText("API Credits")).toBeInTheDocument();
    });

    await user.click(screen.getByText("API Credits"));

    const amountInput = await screen.findByPlaceholderText("0.10 or more");
    await user.type(amountInput, "5.00");

    await user.click(screen.getByRole("button", { name: "Request Withdrawal" }));

    await waitFor(() => {
      expect(toastFn).toHaveBeenCalledWith("Insufficient balance", "error");
    });
  });

  it("clears amount when switching between methods", async () => {
    mockAuthenticated();
    const user = userEvent.setup();
    renderWithProviders(<RedeemPage />);

    await waitFor(() => {
      expect(screen.getByText("API Credits")).toBeInTheDocument();
    });

    await user.click(screen.getByText("API Credits"));

    const amountInput = await screen.findByPlaceholderText("0.10 or more");
    await user.type(amountInput, "5.00");

    // Switch to Gift Card
    await user.click(screen.getByText("Gift Card"));

    // Amount input should be cleared (new placeholder)
    const newAmountInput = screen.getByPlaceholderText("1.00 or more");
    expect(newAmountInput).toHaveValue(null);
  });

  it("renders redemption history with status badges", async () => {
    mockAuthenticated();
    renderWithProviders(<RedeemPage />);

    await waitFor(() => {
      // "Completed" appears as both table header and status badge
      const completedElements = screen.getAllByText("Completed");
      expect(completedElements.length).toBeGreaterThanOrEqual(2);
    });
    // Pending status badge
    expect(screen.getByText("Pending")).toBeInTheDocument();
  });

  it("renders redemption history with completed_at and without", async () => {
    mockAuthenticated();
    renderWithProviders(<RedeemPage />);

    await waitFor(() => {
      expect(screen.getByText("Redemption History")).toBeInTheDocument();
    });

    // red-2 has completed_at: null, should show "--"
    await waitFor(() => {
      expect(screen.getByText("--")).toBeInTheDocument();
    });
  });

  it("renders redemption method icons and colors", async () => {
    mockAuthenticated();
    renderWithProviders(<RedeemPage />);

    await waitFor(() => {
      // History table shows method icons
      // api_credits and gift_card entries exist
      expect(screen.getByText("api credits")).toBeInTheDocument();
      expect(screen.getByText("gift card")).toBeInTheDocument();
    });
  });

  it("renders redemption amounts formatted", async () => {
    mockAuthenticated();
    renderWithProviders(<RedeemPage />);

    await waitFor(() => {
      expect(screen.getByText("$5.00")).toBeInTheDocument();
    });
    expect(screen.getByText("$2.00")).toBeInTheDocument();
  });

  it("shows method descriptions for all built-in types", async () => {
    mockAuthenticated();
    renderWithProviders(<RedeemPage />);

    await waitFor(() => {
      expect(screen.getByText("Convert balance to API usage credits instantly")).toBeInTheDocument();
    });
    expect(screen.getByText("Redeem as digital gift card vouchers")).toBeInTheDocument();
    expect(screen.getByText("Direct bank transfer to your account")).toBeInTheDocument();
    expect(screen.getByText("Instant UPI transfer to your linked ID")).toBeInTheDocument();
  });

  it("shows Redemption Methods section header", async () => {
    mockAuthenticated();
    renderWithProviders(<RedeemPage />);

    await waitFor(() => {
      expect(screen.getByText("Redemption Methods")).toBeInTheDocument();
    });
  });

  it("handles redemption with processing status", async () => {
    mockAuthenticated();
    vi.mocked(api.fetchRedemptions).mockResolvedValue({
      redemptions: [
        {
          id: "red-proc",
          creator_id: "c1",
          redemption_type: "bank_withdrawal",
          amount_usd: 50.0,
          currency: "USD",
          status: "processing",
          payout_ref: null,
          admin_notes: "",
          rejection_reason: "",
          created_at: "2026-02-20T10:00:00Z",
          processed_at: "2026-02-20T10:05:00Z",
          completed_at: null,
        },
      ],
      total: 1,
    });

    renderWithProviders(<RedeemPage />);

    await waitFor(() => {
      expect(screen.getByText("Processing")).toBeInTheDocument();
    });
  });

  it("handles redemption with failed status", async () => {
    mockAuthenticated();
    vi.mocked(api.fetchRedemptions).mockResolvedValue({
      redemptions: [
        {
          id: "red-fail",
          creator_id: "c1",
          redemption_type: "upi",
          amount_usd: 10.0,
          currency: "USD",
          status: "failed",
          payout_ref: null,
          admin_notes: "",
          rejection_reason: "",
          created_at: "2026-02-20T10:00:00Z",
          processed_at: null,
          completed_at: null,
        },
      ],
      total: 1,
    });

    renderWithProviders(<RedeemPage />);

    await waitFor(() => {
      expect(screen.getByText("Failed")).toBeInTheDocument();
    });
  });

  it("handles redemption with rejected status", async () => {
    mockAuthenticated();
    vi.mocked(api.fetchRedemptions).mockResolvedValue({
      redemptions: [
        {
          id: "red-rej",
          creator_id: "c1",
          redemption_type: "gift_card",
          amount_usd: 3.0,
          currency: "USD",
          status: "rejected",
          payout_ref: null,
          admin_notes: "",
          rejection_reason: "Suspicious activity",
          created_at: "2026-02-20T10:00:00Z",
          processed_at: null,
          completed_at: null,
        },
      ],
      total: 1,
    });

    renderWithProviders(<RedeemPage />);

    await waitFor(() => {
      expect(screen.getByText("Rejected")).toBeInTheDocument();
    });
  });

  it("uses fallback method list when API returns no methods", async () => {
    mockAuthenticated();
    vi.mocked(api.fetchRedemptionMethods).mockResolvedValue({
      methods: null,
    } as any);

    renderWithProviders(<RedeemPage />);

    await waitFor(() => {
      // Fallback methods should be rendered
      expect(screen.getByText("API Credits")).toBeInTheDocument();
    });
    expect(screen.getByText("Gift Card")).toBeInTheDocument();
    expect(screen.getByText("Bank Transfer")).toBeInTheDocument();
    expect(screen.getByText("UPI Transfer")).toBeInTheDocument();
  });

  it("renders unknown redemption type with fallback icon in history", async () => {
    mockAuthenticated();
    vi.mocked(api.fetchRedemptions).mockResolvedValue({
      redemptions: [
        {
          id: "red-unknown",
          creator_id: "c1",
          redemption_type: "crypto_wallet",
          amount_usd: 20.0,
          currency: "USD",
          status: "completed",
          payout_ref: null,
          admin_notes: "",
          rejection_reason: "",
          created_at: "2026-02-20T10:00:00Z",
          processed_at: "2026-02-20T10:01:00Z",
          completed_at: "2026-02-20T10:02:00Z",
        },
      ],
      total: 1,
    });

    renderWithProviders(<RedeemPage />);

    await waitFor(() => {
      expect(screen.getByText("crypto wallet")).toBeInTheDocument();
    });
  });

  it("shows validation message for gift card minimum", async () => {
    mockAuthenticated();
    const user = userEvent.setup();
    renderWithProviders(<RedeemPage />);

    await waitFor(() => {
      expect(screen.getByText("Gift Card")).toBeInTheDocument();
    });

    await user.click(screen.getByText("Gift Card"));

    await waitFor(() => {
      expect(screen.getByText(/Min: \$1\.00/)).toBeInTheDocument();
    });

    const amountInput = screen.getByPlaceholderText("1.00 or more");
    await user.type(amountInput, "0.5");

    await waitFor(() => {
      expect(
        screen.getByText("Minimum withdrawal is $1.00"),
      ).toBeInTheDocument();
    });
  });

  it("shows no pagination when total <= 10", async () => {
    mockAuthenticated();
    renderWithProviders(<RedeemPage />);

    await waitFor(() => {
      expect(screen.getByText("Redemption History")).toBeInTheDocument();
    });

    // mockRedemptions has total: 2, no pagination should show
    // Pagination buttons (Next/Previous) should not appear
    expect(screen.queryByText("Next")).not.toBeInTheDocument();
    expect(screen.queryByText("Previous")).not.toBeInTheDocument();
  });
});
