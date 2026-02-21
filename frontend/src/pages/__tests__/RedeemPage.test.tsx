import { describe, it, expect, vi, beforeEach } from "vitest";
import { screen, waitFor, fireEvent } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { renderWithProviders } from "../../test/test-utils";
import RedeemPage from "../RedeemPage";
import * as authModule from "../../hooks/useAuth";
import * as api from "../../lib/api";

vi.mock("../../hooks/useAuth");
vi.mock("../../components/Toast", () => ({
  useToast: () => ({ toast: vi.fn() }),
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
});
