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
    balance: 15000,
    balance_usd: 15.0,
  };

  const mockRedemptions = [
    {
      id: "red-1",
      redemption_type: "api_credits",
      amount_ard: 500,
      amount_fiat: 0.5,
      currency: "USD",
      status: "completed",
      created_at: "2026-01-15T10:00:00Z",
      completed_at: "2026-01-15T10:05:00Z",
    },
    {
      id: "red-2",
      redemption_type: "gift_card",
      amount_ard: 2000,
      amount_fiat: 2.0,
      currency: "USD",
      status: "pending",
      created_at: "2026-02-01T12:00:00Z",
      completed_at: null,
    },
    {
      id: "red-3",
      redemption_type: "bank_withdrawal",
      amount_ard: 10000,
      amount_fiat: 10.0,
      currency: "USD",
      status: "processing",
      created_at: "2026-02-05T14:00:00Z",
      completed_at: null,
    },
  ];

  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(api.fetchCreatorWallet).mockResolvedValue(mockWallet);
    vi.mocked(api.fetchRedemptions).mockResolvedValue({ redemptions: mockRedemptions });
    vi.mocked(api.createRedemption).mockResolvedValue({ id: "new-red", status: "pending" });
    vi.mocked(api.cancelRedemption).mockResolvedValue({ success: true });
  });

  it("renders page title and description", async () => {
    renderWithProviders(<RedemptionPage token={mockToken} />);

    expect(screen.getByText("Redeem ARD Tokens")).toBeInTheDocument();
    expect(screen.getByText(/Convert your earnings to real value/)).toBeInTheDocument();
  });

  it("displays balance banner with ARD and USD amounts", async () => {
    renderWithProviders(<RedemptionPage token={mockToken} />);

    await waitFor(() => {
      expect(screen.getByText("15.0K ARD")).toBeInTheDocument();
      expect(screen.getByText("$15.00 USD")).toBeInTheDocument();
    });
  });

  it("renders all 4 redemption method tabs", async () => {
    renderWithProviders(<RedemptionPage token={mockToken} />);

    await waitFor(() => {
      expect(screen.getByText("API Credits")).toBeInTheDocument();
      expect(screen.getByText("Gift Card")).toBeInTheDocument();
      expect(screen.getByText("UPI Transfer")).toBeInTheDocument();
      expect(screen.getByText("Bank Transfer")).toBeInTheDocument();
    });

    expect(screen.getByText("Convert ARD to API call credits")).toBeInTheDocument();
    expect(screen.getByText("Amazon gift card delivery")).toBeInTheDocument();
    expect(screen.getByText("Direct to your UPI ID (India)")).toBeInTheDocument();
    expect(screen.getByText("Wire to your bank account")).toBeInTheDocument();
  });

  it("shows minimum threshold for each redemption method", async () => {
    renderWithProviders(<RedemptionPage token={mockToken} />);

    await waitFor(() => {
      expect(screen.getByText("Min: 100 ARD")).toBeInTheDocument();
      expect(screen.getByText("Min: 1.0K ARD")).toBeInTheDocument();
      expect(screen.getByText("Min: 5.0K ARD")).toBeInTheDocument();
      expect(screen.getByText("Min: 10.0K ARD")).toBeInTheDocument();
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
      expect(screen.getByPlaceholderText("Amount in ARD")).toBeInTheDocument();
      expect(screen.getByText("Enter Amount")).toBeInTheDocument();
    });
  });

  it("allows user to enter amount and shows USD conversion", async () => {
    renderWithProviders(<RedemptionPage token={mockToken} />);

    await waitFor(() => {
      expect(screen.getByText("API Credits")).toBeInTheDocument();
    });

    const apiCreditsButton = screen.getByRole("button", { name: /API Credits/ });
    fireEvent.click(apiCreditsButton);

    const amountInput = await screen.findByPlaceholderText("Amount in ARD");
    fireEvent.change(amountInput, { target: { value: "500" } });

    await waitFor(() => {
      expect(screen.getByText("= $0.50 USD")).toBeInTheDocument();
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

    const amountInput = screen.getByPlaceholderText("Amount in ARD") as HTMLInputElement;
    await waitFor(() => {
      expect(amountInput.value).toBe("15000");
    });
  });

  it("successfully submits redemption and shows success message", async () => {
    renderWithProviders(<RedemptionPage token={mockToken} />);

    await waitFor(() => {
      expect(screen.getByText("API Credits")).toBeInTheDocument();
    });

    const apiCreditsButton = screen.getByRole("button", { name: /API Credits/ });
    fireEvent.click(apiCreditsButton);

    const amountInput = await screen.findByPlaceholderText("Amount in ARD");
    fireEvent.change(amountInput, { target: { value: "500" } });

    const redeemButton = screen.getByRole("button", { name: /Redeem/ });
    fireEvent.click(redeemButton);

    await waitFor(() => {
      expect(api.createRedemption).toHaveBeenCalledWith(mockToken, {
        redemption_type: "api_credits",
        amount_ard: 500,
      });
    });

    // Reload data and check wallet was called again
    await waitFor(() => {
      expect(api.fetchCreatorWallet).toHaveBeenCalledTimes(2);
    });
  });

  it("shows loading state during redemption submission", async () => {
    vi.mocked(api.createRedemption).mockImplementation(() =>
      new Promise((resolve) => setTimeout(() => resolve({ id: "new-red", status: "pending" }), 100))
    );

    renderWithProviders(<RedemptionPage token={mockToken} />);

    await waitFor(() => {
      expect(screen.getByText("API Credits")).toBeInTheDocument();
    });

    const apiCreditsButton = screen.getByRole("button", { name: /API Credits/ });
    fireEvent.click(apiCreditsButton);

    const amountInput = await screen.findByPlaceholderText("Amount in ARD");
    fireEvent.change(amountInput, { target: { value: "500" } });

    const redeemButton = screen.getByRole("button", { name: /Redeem/ });
    fireEvent.click(redeemButton);

    // Check for loading state (button should be disabled)
    await waitFor(() => {
      expect(redeemButton).toBeDisabled();
    });
  });

  it("shows error message when redemption fails", async () => {
    vi.mocked(api.createRedemption).mockRejectedValue(new Error("Insufficient balance"));

    renderWithProviders(<RedemptionPage token={mockToken} />);

    await waitFor(() => {
      expect(screen.getByText("API Credits")).toBeInTheDocument();
    });

    const apiCreditsButton = screen.getByRole("button", { name: /API Credits/ });
    fireEvent.click(apiCreditsButton);

    const amountInput = await screen.findByPlaceholderText("Amount in ARD");
    fireEvent.change(amountInput, { target: { value: "500" } });

    const redeemButton = screen.getByRole("button", { name: /Redeem/ });
    fireEvent.click(redeemButton);

    await waitFor(() => {
      expect(screen.getByText("Insufficient balance")).toBeInTheDocument();
    });
  });

  it("displays redemption history with correct statuses", async () => {
    renderWithProviders(<RedemptionPage token={mockToken} />);

    await waitFor(() => {
      expect(screen.getByText("Redemption History")).toBeInTheDocument();
      expect(screen.getByText(/api credits — 500 ARD/i)).toBeInTheDocument();
      expect(screen.getByText(/gift card — 2.0K ARD/i)).toBeInTheDocument();
      expect(screen.getByText(/bank withdrawal — 10.0K ARD/i)).toBeInTheDocument();
    });

    expect(screen.getByText(/completed/i)).toBeInTheDocument();
    expect(screen.getByText(/pending/i)).toBeInTheDocument();
    expect(screen.getByText(/processing/i)).toBeInTheDocument();
  });

  it("shows empty state when no redemption history exists", async () => {
    vi.mocked(api.fetchRedemptions).mockResolvedValue({ redemptions: [] });

    renderWithProviders(<RedemptionPage token={mockToken} />);

    await waitFor(() => {
      expect(screen.getByText("Redemption History")).toBeInTheDocument();
      expect(screen.getByText("No redemptions yet.")).toBeInTheDocument();
    });
  });

  it("allows canceling pending redemptions", async () => {
    renderWithProviders(<RedemptionPage token={mockToken} />);

    await waitFor(() => {
      expect(screen.getByText(/gift card — 2.0K ARD/i)).toBeInTheDocument();
    });

    const cancelButton = screen.getByRole("button", { name: /Cancel/i });
    fireEvent.click(cancelButton);

    await waitFor(() => {
      expect(api.cancelRedemption).toHaveBeenCalledWith(mockToken, "red-2");
    });
  });

  it("does not show cancel button for non-pending redemptions", async () => {
    renderWithProviders(<RedemptionPage token={mockToken} />);

    await waitFor(() => {
      expect(screen.getByText(/api credits — 500 ARD/i)).toBeInTheDocument();
      expect(screen.getByText(/bank withdrawal — 10.0K ARD/i)).toBeInTheDocument();
    });

    // Only one Cancel button should exist (for the pending redemption)
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
      expect(screen.getByPlaceholderText("Amount in ARD")).toBeInTheDocument();
    });

    // Click on Gift Card
    const giftCardButton = screen.getByRole("button", { name: /Gift Card/ });
    fireEvent.click(giftCardButton);

    // Amount input should still be visible
    await waitFor(() => {
      expect(screen.getByPlaceholderText("Amount in ARD")).toBeInTheDocument();
    });

    // Click on UPI Transfer
    const upiButton = screen.getByRole("button", { name: /UPI Transfer/ });
    fireEvent.click(upiButton);

    await waitFor(() => {
      expect(screen.getByPlaceholderText("Amount in ARD")).toBeInTheDocument();
    });
  });

  it("disables methods when balance is below minimum threshold", async () => {
    vi.mocked(api.fetchCreatorWallet).mockResolvedValue({
      balance: 500,
      balance_usd: 0.5,
    });

    renderWithProviders(<RedemptionPage token={mockToken} />);

    await waitFor(() => {
      expect(screen.getByText("API Credits")).toBeInTheDocument();
    });

    // API Credits should be enabled (min 100)
    const apiCreditsButton = screen.getByRole("button", { name: /API Credits/ });
    expect(apiCreditsButton).not.toBeDisabled();

    // Gift Card should be disabled (min 1000)
    const giftCardButton = screen.getByRole("button", { name: /Gift Card/ });
    expect(giftCardButton).toBeDisabled();

    // UPI should be disabled (min 5000)
    const upiButton = screen.getByRole("button", { name: /UPI Transfer/ });
    expect(upiButton).toBeDisabled();

    // Bank Transfer should be disabled (min 10000)
    const bankButton = screen.getByRole("button", { name: /Bank Transfer/ });
    expect(bankButton).toBeDisabled();
  });

  it("clears amount and selected type after successful redemption", async () => {
    renderWithProviders(<RedemptionPage token={mockToken} />);

    await waitFor(() => {
      expect(screen.getByText("API Credits")).toBeInTheDocument();
    });

    const apiCreditsButton = screen.getByRole("button", { name: /API Credits/ });
    fireEvent.click(apiCreditsButton);

    const amountInput = await screen.findByPlaceholderText("Amount in ARD") as HTMLInputElement;
    fireEvent.change(amountInput, { target: { value: "500" } });

    const redeemButton = screen.getByRole("button", { name: /Redeem/ });
    fireEvent.click(redeemButton);

    // Wait for API call to complete
    await waitFor(() => {
      expect(api.createRedemption).toHaveBeenCalled();
    });

    // Amount input should no longer be visible (selectedType was cleared)
    await waitFor(() => {
      expect(screen.queryByPlaceholderText("Amount in ARD")).not.toBeInTheDocument();
    });
  });

  it("disables redeem button when amount is invalid", async () => {
    renderWithProviders(<RedemptionPage token={mockToken} />);

    await waitFor(() => {
      expect(screen.getByText("API Credits")).toBeInTheDocument();
    });

    const apiCreditsButton = screen.getByRole("button", { name: /API Credits/ });
    fireEvent.click(apiCreditsButton);

    const redeemButton = await screen.findByRole("button", { name: /Redeem/ });

    // Should be disabled when no amount
    expect(redeemButton).toBeDisabled();

    // Enter 0
    const amountInput = screen.getByPlaceholderText("Amount in ARD");
    fireEvent.change(amountInput, { target: { value: "0" } });

    // Should still be disabled
    await waitFor(() => {
      expect(redeemButton).toBeDisabled();
    });
  });

  it("fetches data on mount", async () => {
    renderWithProviders(<RedemptionPage token={mockToken} />);

    await waitFor(() => {
      expect(api.fetchCreatorWallet).toHaveBeenCalledWith(mockToken);
      expect(api.fetchRedemptions).toHaveBeenCalledWith(mockToken);
    });
  });

  it("reloads data after successful redemption", async () => {
    renderWithProviders(<RedemptionPage token={mockToken} />);

    await waitFor(() => {
      expect(api.fetchCreatorWallet).toHaveBeenCalledTimes(1);
      expect(api.fetchRedemptions).toHaveBeenCalledTimes(1);
    });

    const apiCreditsButton = screen.getByRole("button", { name: /API Credits/ });
    fireEvent.click(apiCreditsButton);

    const amountInput = await screen.findByPlaceholderText("Amount in ARD");
    fireEvent.change(amountInput, { target: { value: "500" } });

    const redeemButton = screen.getByRole("button", { name: /Redeem/ });
    fireEvent.click(redeemButton);

    // Wait for redemption to complete
    await waitFor(() => {
      expect(api.createRedemption).toHaveBeenCalled();
    });

    // Should have called the fetch functions again
    await waitFor(() => {
      expect(api.fetchCreatorWallet).toHaveBeenCalledTimes(2);
      expect(api.fetchRedemptions).toHaveBeenCalledTimes(2);
    });
  });

  it("formats large ARD amounts with K suffix", async () => {
    vi.mocked(api.fetchCreatorWallet).mockResolvedValue({
      balance: 25500,
      balance_usd: 25.5,
    });

    renderWithProviders(<RedemptionPage token={mockToken} />);

    await waitFor(() => {
      expect(screen.getByText("25.5K ARD")).toBeInTheDocument();
    });
  });

  it("formats small ARD amounts without K suffix", async () => {
    vi.mocked(api.fetchCreatorWallet).mockResolvedValue({
      balance: 150,
      balance_usd: 0.15,
    });

    renderWithProviders(<RedemptionPage token={mockToken} />);

    await waitFor(() => {
      expect(screen.getByText("150 ARD")).toBeInTheDocument();
    });
  });
});
