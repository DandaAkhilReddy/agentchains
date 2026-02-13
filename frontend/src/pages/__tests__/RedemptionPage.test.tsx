import { describe, it, expect, vi, beforeEach } from "vitest";
import { screen, fireEvent, waitFor } from "@testing-library/react";
import { renderWithProviders } from "../../test/test-utils";
import RedemptionPage from "../RedemptionPage";
import * as api from "../../lib/api";

// Mock API functions
vi.mock("../../lib/api", () => ({
  fetchCreatorWallet: vi.fn(),
  createRedemption: vi.fn(),
  fetchRedemptions: vi.fn(),
  cancelRedemption: vi.fn(),
  fetchRedemptionMethods: vi.fn(),
}));

describe("RedemptionPage", () => {
  const mockToken = "test-token-123";

  const mockWallet = {
    balance: 15.0,
    total_earned: 0,
    total_spent: 0,
    total_deposited: 0,
    total_fees_paid: 0,
  };

  const mockRedemptions: import("../../types/api").RedemptionRequest[] = [
    {
      id: "red-1",
      creator_id: "creator-1",
      redemption_type: "api_credits",
      amount_usd: 0.50,
      currency: "USD",
      status: "completed",
      payout_ref: null,
      admin_notes: "",
      rejection_reason: "",
      created_at: "2026-01-15T10:00:00Z",
      processed_at: "2026-01-15T10:03:00Z",
      completed_at: "2026-01-15T10:05:00Z",
    },
    {
      id: "red-2",
      creator_id: "creator-1",
      redemption_type: "gift_card",
      amount_usd: 2.0,
      currency: "USD",
      status: "pending",
      payout_ref: null,
      admin_notes: "",
      rejection_reason: "",
      created_at: "2026-02-01T12:00:00Z",
      processed_at: null,
      completed_at: null,
    },
    {
      id: "red-3",
      creator_id: "creator-1",
      redemption_type: "bank_withdrawal",
      amount_usd: 10.0,
      currency: "USD",
      status: "processing",
      payout_ref: null,
      admin_notes: "",
      rejection_reason: "",
      created_at: "2026-02-05T14:00:00Z",
      processed_at: "2026-02-05T14:01:00Z",
      completed_at: null,
    },
  ];

  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(api.fetchCreatorWallet).mockResolvedValue(mockWallet);
    vi.mocked(api.fetchRedemptions).mockResolvedValue({ redemptions: mockRedemptions, total: mockRedemptions.length });
    vi.mocked(api.createRedemption).mockResolvedValue({
      id: "new-red",
      creator_id: "creator-1",
      redemption_type: "api_credits",
      amount_usd: 5.0,
      currency: "USD",
      status: "pending",
      payout_ref: null,
      admin_notes: "",
      rejection_reason: "",
      created_at: "2026-02-10T10:00:00Z",
      processed_at: null,
      completed_at: null,
    });
    vi.mocked(api.cancelRedemption).mockResolvedValue({ message: "Redemption cancelled" });
  });

  it("renders page title and description", async () => {
    renderWithProviders(<RedemptionPage token={mockToken} />);

    expect(screen.getByText("Withdraw Funds")).toBeInTheDocument();
    expect(screen.getByText(/Convert your earnings to API credits, gift cards, or cash/)).toBeInTheDocument();
  });

  it("displays balance banner with USD amount", async () => {
    renderWithProviders(<RedemptionPage token={mockToken} />);

    await waitFor(() => {
      expect(screen.getByText("Available Balance")).toBeInTheDocument();
    });
  });

  it("renders all 4 withdrawal method tabs", async () => {
    renderWithProviders(<RedemptionPage token={mockToken} />);

    await waitFor(() => {
      expect(screen.getByText("API Credits")).toBeInTheDocument();
      expect(screen.getByText("Gift Card")).toBeInTheDocument();
      expect(screen.getByText("UPI Transfer")).toBeInTheDocument();
      expect(screen.getByText("Bank Transfer")).toBeInTheDocument();
    });

    expect(screen.getByText("Convert to API call credits")).toBeInTheDocument();
    expect(screen.getByText("Amazon gift card delivery")).toBeInTheDocument();
    expect(screen.getByText("Direct to your UPI ID (India)")).toBeInTheDocument();
    expect(screen.getByText("Wire to your bank account")).toBeInTheDocument();
  });

  it("shows minimum threshold for each withdrawal method in USD", async () => {
    renderWithProviders(<RedemptionPage token={mockToken} />);

    await waitFor(() => {
      // formatUSD(0.10) -> "$0.10", formatUSD(1.00) -> "$1.00",
      // formatUSD(5.00) -> "$5.00", formatUSD(10.00) -> "$10.00"
      expect(screen.getByText("Min: $0.10")).toBeInTheDocument();
      expect(screen.getByText("Min: $1.00")).toBeInTheDocument();
      expect(screen.getByText("Min: $5.00")).toBeInTheDocument();
      expect(screen.getByText("Min: $10.00")).toBeInTheDocument();
    });
  });

  it("shows estimated delivery times for each method", async () => {
    renderWithProviders(<RedemptionPage token={mockToken} />);

    await waitFor(() => {
      expect(screen.getByText("Instant")).toBeInTheDocument();
      expect(screen.getByText("24 hours")).toBeInTheDocument();
      expect(screen.getByText("Minutes")).toBeInTheDocument();
      expect(screen.getByText("3-7 days")).toBeInTheDocument();
    });
  });

  it("displays amount input field when a method is selected", async () => {
    renderWithProviders(<RedemptionPage token={mockToken} />);

    await waitFor(() => {
      expect(screen.getByText("API Credits")).toBeInTheDocument();
    });

    const apiCreditsButton = screen.getByRole("button", { name: /API Credits/ });
    fireEvent.click(apiCreditsButton);

    await waitFor(() => {
      expect(screen.getByPlaceholderText("Amount in USD")).toBeInTheDocument();
      expect(screen.getByText("Enter Amount")).toBeInTheDocument();
    });
  });

  it("allows user to enter amount", async () => {
    renderWithProviders(<RedemptionPage token={mockToken} />);

    await waitFor(() => {
      expect(screen.getByText("API Credits")).toBeInTheDocument();
    });

    const apiCreditsButton = screen.getByRole("button", { name: /API Credits/ });
    fireEvent.click(apiCreditsButton);

    const amountInput = await screen.findByPlaceholderText("Amount in USD");
    fireEvent.change(amountInput, { target: { value: "5.00" } });

    await waitFor(() => {
      expect((amountInput as HTMLInputElement).value).toBe("5.00");
    });
  });

  it("allows user to click Max button to fill balance", async () => {
    renderWithProviders(<RedemptionPage token={mockToken} />);

    await waitFor(() => {
      expect(screen.getByText("API Credits")).toBeInTheDocument();
    });

    const apiCreditsButton = screen.getByRole("button", { name: /API Credits/ });
    fireEvent.click(apiCreditsButton);

    const maxButton = await screen.findByRole("button", { name: /Max/ });
    fireEvent.click(maxButton);

    const amountInput = screen.getByPlaceholderText("Amount in USD") as HTMLInputElement;
    await waitFor(() => {
      expect(amountInput.value).toBe("15");
    });
  });

  it("successfully submits withdrawal and shows success message", async () => {
    renderWithProviders(<RedemptionPage token={mockToken} />);

    await waitFor(() => {
      expect(screen.getByText("API Credits")).toBeInTheDocument();
    });

    const apiCreditsButton = screen.getByRole("button", { name: /API Credits/ });
    fireEvent.click(apiCreditsButton);

    const amountInput = await screen.findByPlaceholderText("Amount in USD");
    fireEvent.change(amountInput, { target: { value: "5.00" } });

    const withdrawButton = screen.getByRole("button", { name: /Withdraw/ });
    fireEvent.click(withdrawButton);

    await waitFor(() => {
      expect(api.createRedemption).toHaveBeenCalledWith(mockToken, {
        redemption_type: "api_credits",
        amount_usd: 5.0,
      });
    });

    // Reload data and check wallet was called again
    await waitFor(() => {
      expect(api.fetchCreatorWallet).toHaveBeenCalledTimes(2);
    });
  });

  it("shows loading state during withdrawal submission", async () => {
    vi.mocked(api.createRedemption).mockImplementation(() =>
      new Promise((resolve) => setTimeout(() => resolve({
        id: "new-red",
        creator_id: "creator-1",
        redemption_type: "api_credits",
        amount_usd: 5.0,
        currency: "USD",
        status: "pending",
        payout_ref: null,
        admin_notes: "",
        rejection_reason: "",
        created_at: "2026-02-10T10:00:00Z",
        processed_at: null,
        completed_at: null,
      }), 100))
    );

    renderWithProviders(<RedemptionPage token={mockToken} />);

    await waitFor(() => {
      expect(screen.getByText("API Credits")).toBeInTheDocument();
    });

    const apiCreditsButton = screen.getByRole("button", { name: /API Credits/ });
    fireEvent.click(apiCreditsButton);

    const amountInput = await screen.findByPlaceholderText("Amount in USD");
    fireEvent.change(amountInput, { target: { value: "5.00" } });

    const withdrawButton = screen.getByRole("button", { name: /Withdraw/ });
    fireEvent.click(withdrawButton);

    // Check for loading state (button should be disabled)
    await waitFor(() => {
      expect(withdrawButton).toBeDisabled();
    });
  });

  it("shows error message when withdrawal fails", async () => {
    vi.mocked(api.createRedemption).mockRejectedValue(new Error("Insufficient balance"));

    renderWithProviders(<RedemptionPage token={mockToken} />);

    await waitFor(() => {
      expect(screen.getByText("API Credits")).toBeInTheDocument();
    });

    const apiCreditsButton = screen.getByRole("button", { name: /API Credits/ });
    fireEvent.click(apiCreditsButton);

    const amountInput = await screen.findByPlaceholderText("Amount in USD");
    fireEvent.change(amountInput, { target: { value: "5.00" } });

    const withdrawButton = screen.getByRole("button", { name: /Withdraw/ });
    fireEvent.click(withdrawButton);

    await waitFor(() => {
      expect(screen.getByText("Insufficient balance")).toBeInTheDocument();
    });
  });

  it("displays withdrawal history with correct statuses", async () => {
    renderWithProviders(<RedemptionPage token={mockToken} />);

    await waitFor(() => {
      expect(screen.getByText("Withdrawal History")).toBeInTheDocument();
      // History entries use formatUSD for amount_usd
      expect(screen.getByText(/api credits — \$0\.50/i)).toBeInTheDocument();
      expect(screen.getByText(/gift card — \$2\.00/i)).toBeInTheDocument();
      expect(screen.getByText(/bank withdrawal — \$10\.00/i)).toBeInTheDocument();
    });

    expect(screen.getByText(/completed/i)).toBeInTheDocument();
    expect(screen.getByText(/pending/i)).toBeInTheDocument();
    expect(screen.getByText(/processing/i)).toBeInTheDocument();
  });

  it("shows empty state when no withdrawal history exists", async () => {
    vi.mocked(api.fetchRedemptions).mockResolvedValue({ redemptions: [], total: 0 });

    renderWithProviders(<RedemptionPage token={mockToken} />);

    await waitFor(() => {
      expect(screen.getByText("Withdrawal History")).toBeInTheDocument();
      expect(screen.getByText("No withdrawals yet.")).toBeInTheDocument();
    });
  });

  it("allows canceling pending withdrawals", async () => {
    renderWithProviders(<RedemptionPage token={mockToken} />);

    await waitFor(() => {
      expect(screen.getByText(/gift card — \$2\.00/i)).toBeInTheDocument();
    });

    const cancelButton = screen.getByRole("button", { name: /Cancel/i });
    fireEvent.click(cancelButton);

    await waitFor(() => {
      expect(api.cancelRedemption).toHaveBeenCalledWith(mockToken, "red-2");
    });
  });

  it("does not show cancel button for non-pending withdrawals", async () => {
    renderWithProviders(<RedemptionPage token={mockToken} />);

    await waitFor(() => {
      expect(screen.getByText(/api credits — \$0\.50/i)).toBeInTheDocument();
      expect(screen.getByText(/bank withdrawal — \$10\.00/i)).toBeInTheDocument();
    });

    // Only one Cancel button should exist (for the pending withdrawal)
    const cancelButtons = screen.getAllByRole("button", { name: /Cancel/i });
    expect(cancelButtons).toHaveLength(1);
  });

  it("switches between different method tabs correctly", async () => {
    renderWithProviders(<RedemptionPage token={mockToken} />);

    await waitFor(() => {
      expect(screen.getByText("API Credits")).toBeInTheDocument();
    });

    // Click on API Credits
    const apiCreditsButton = screen.getByRole("button", { name: /API Credits/ });
    fireEvent.click(apiCreditsButton);

    await waitFor(() => {
      expect(screen.getByPlaceholderText("Amount in USD")).toBeInTheDocument();
    });

    // Click on Gift Card
    const giftCardButton = screen.getByRole("button", { name: /Gift Card/ });
    fireEvent.click(giftCardButton);

    // Amount input should still be visible
    await waitFor(() => {
      expect(screen.getByPlaceholderText("Amount in USD")).toBeInTheDocument();
    });

    // Click on UPI Transfer
    const upiButton = screen.getByRole("button", { name: /UPI Transfer/ });
    fireEvent.click(upiButton);

    await waitFor(() => {
      expect(screen.getByPlaceholderText("Amount in USD")).toBeInTheDocument();
    });
  });

  it("disables methods when balance is below minimum threshold", async () => {
    vi.mocked(api.fetchCreatorWallet).mockResolvedValue({
      balance: 0.50,
      total_earned: 0,
      total_spent: 0,
      total_deposited: 0,
      total_fees_paid: 0,
    });

    renderWithProviders(<RedemptionPage token={mockToken} />);

    await waitFor(() => {
      expect(screen.getByText("API Credits")).toBeInTheDocument();
    });

    // API Credits should be enabled (min $0.10)
    const apiCreditsButton = screen.getByRole("button", { name: /API Credits/ });
    expect(apiCreditsButton).not.toBeDisabled();

    // Gift Card should be disabled (min $1.00)
    const giftCardButton = screen.getByRole("button", { name: /Gift Card/ });
    expect(giftCardButton).toBeDisabled();

    // UPI should be disabled (min $5.00)
    const upiButton = screen.getByRole("button", { name: /UPI Transfer/ });
    expect(upiButton).toBeDisabled();

    // Bank Transfer should be disabled (min $10.00)
    const bankButton = screen.getByRole("button", { name: /Bank Transfer/ });
    expect(bankButton).toBeDisabled();
  });

  it("clears amount and selected type after successful withdrawal", async () => {
    renderWithProviders(<RedemptionPage token={mockToken} />);

    await waitFor(() => {
      expect(screen.getByText("API Credits")).toBeInTheDocument();
    });

    const apiCreditsButton = screen.getByRole("button", { name: /API Credits/ });
    fireEvent.click(apiCreditsButton);

    const amountInput = await screen.findByPlaceholderText("Amount in USD") as HTMLInputElement;
    fireEvent.change(amountInput, { target: { value: "5.00" } });

    const withdrawButton = screen.getByRole("button", { name: /Withdraw/ });
    fireEvent.click(withdrawButton);

    // Wait for API call to complete
    await waitFor(() => {
      expect(api.createRedemption).toHaveBeenCalled();
    });

    // Amount input should no longer be visible (selectedType was cleared)
    await waitFor(() => {
      expect(screen.queryByPlaceholderText("Amount in USD")).not.toBeInTheDocument();
    });
  });

  it("disables withdraw button when amount is invalid", async () => {
    renderWithProviders(<RedemptionPage token={mockToken} />);

    await waitFor(() => {
      expect(screen.getByText("API Credits")).toBeInTheDocument();
    });

    const apiCreditsButton = screen.getByRole("button", { name: /API Credits/ });
    fireEvent.click(apiCreditsButton);

    const withdrawButton = await screen.findByRole("button", { name: /Withdraw/ });

    // Should be disabled when no amount
    expect(withdrawButton).toBeDisabled();

    // Enter 0
    const amountInput = screen.getByPlaceholderText("Amount in USD");
    fireEvent.change(amountInput, { target: { value: "0" } });

    // Should still be disabled
    await waitFor(() => {
      expect(withdrawButton).toBeDisabled();
    });
  });

  it("fetches data on mount", async () => {
    renderWithProviders(<RedemptionPage token={mockToken} />);

    await waitFor(() => {
      expect(api.fetchCreatorWallet).toHaveBeenCalledWith(mockToken);
      expect(api.fetchRedemptions).toHaveBeenCalledWith(mockToken);
    });
  });

  it("reloads data after successful withdrawal", async () => {
    renderWithProviders(<RedemptionPage token={mockToken} />);

    await waitFor(() => {
      expect(api.fetchCreatorWallet).toHaveBeenCalledTimes(1);
      expect(api.fetchRedemptions).toHaveBeenCalledTimes(1);
    });

    const apiCreditsButton = screen.getByRole("button", { name: /API Credits/ });
    fireEvent.click(apiCreditsButton);

    const amountInput = await screen.findByPlaceholderText("Amount in USD");
    fireEvent.change(amountInput, { target: { value: "5.00" } });

    const withdrawButton = screen.getByRole("button", { name: /Withdraw/ });
    fireEvent.click(withdrawButton);

    // Wait for withdrawal to complete
    await waitFor(() => {
      expect(api.createRedemption).toHaveBeenCalled();
    });

    // Should have called the fetch functions again
    await waitFor(() => {
      expect(api.fetchCreatorWallet).toHaveBeenCalledTimes(2);
      expect(api.fetchRedemptions).toHaveBeenCalledTimes(2);
    });
  });
});
