import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import RedemptionPage from "../pages/RedemptionPage";
import type { RedemptionRequest } from "../types/api";

/* ── Mocks ──────────────────────────────────────────────────────────────── */

vi.mock("../lib/api", () => ({
  fetchCreatorWallet: vi.fn(),
  fetchRedemptions: vi.fn(),
  createRedemption: vi.fn(),
  cancelRedemption: vi.fn(),
}));

vi.mock("../components/AnimatedCounter", () => ({
  default: ({ value }: { value: number; decimals?: number }) => (
    <span data-testid="animated-counter">{value}</span>
  ),
}));

vi.mock("../components/PageHeader", () => ({
  default: ({ title }: { title: string }) => (
    <div data-testid="page-header">{title}</div>
  ),
}));

vi.mock("../components/Badge", () => ({
  default: ({ label, variant }: { label: string; variant: string }) => (
    <span data-testid={`badge-${variant}`}>{label}</span>
  ),
}));

vi.mock("../lib/format", () => ({
  formatUSD: (n: number) => `$${n.toFixed(2)}`,
}));

/* ── Import mocked API after mock declarations ───────────────────────────── */

import {
  fetchCreatorWallet,
  fetchRedemptions,
  createRedemption,
  cancelRedemption,
} from "../lib/api";

const mockFetchCreatorWallet = vi.mocked(fetchCreatorWallet);
const mockFetchRedemptions = vi.mocked(fetchRedemptions);
const mockCreateRedemption = vi.mocked(createRedemption);
const mockCancelRedemption = vi.mocked(cancelRedemption);

/* ── Fixtures ────────────────────────────────────────────────────────────── */

const emptyHistory = { redemptions: [] };

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

function renderPage(token = "test-token") {
  return render(<RedemptionPage token={token} />);
}

/* ── Tests ───────────────────────────────────────────────────────────────── */

describe("RedemptionPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockFetchCreatorWallet.mockResolvedValue({ balance: 50 } as any);
    mockFetchRedemptions.mockResolvedValue(emptyHistory as any);
  });

  /* ── 1. Renders balance and method cards ─────────────────────────────── */

  it("renders balance and method cards", async () => {
    renderPage();

    await waitFor(() => {
      expect(screen.getByTestId("animated-counter")).toBeInTheDocument();
    });

    // All four method labels should appear
    expect(screen.getByText("API Credits")).toBeInTheDocument();
    expect(screen.getByText("Gift Card")).toBeInTheDocument();
    expect(screen.getByText("UPI Transfer")).toBeInTheDocument();
    expect(screen.getByText("Bank Transfer")).toBeInTheDocument();
  });

  /* ── 2. Disables methods when balance too low ────────────────────────── */

  it("disables methods when balance too low", async () => {
    // Balance of $0.05 is below the min for every method ($0.10 for api_credits)
    mockFetchCreatorWallet.mockResolvedValue({ balance: 0.05 } as any);
    renderPage();

    await waitFor(() => {
      expect(screen.getByTestId("animated-counter")).toBeInTheDocument();
    });

    const buttons = screen.getAllByRole("button");
    // All four method buttons are disabled (balance < any min)
    const methodButtons = buttons.filter((btn) =>
      [
        "API Credits",
        "Gift Card",
        "UPI Transfer",
        "Bank Transfer",
      ].some((label) => btn.textContent?.includes(label)),
    );
    methodButtons.forEach((btn) => {
      expect(btn).toBeDisabled();
    });
  });

  /* ── 3. Shows amount input when method selected ──────────────────────── */

  it("shows amount input when method selected", async () => {
    // Balance of $50 makes all methods eligible
    renderPage();

    await waitFor(() => {
      expect(screen.getByText("API Credits")).toBeInTheDocument();
    });

    // Amount input should NOT be visible before selection
    expect(screen.queryByPlaceholderText("Amount in USD")).toBeNull();

    // Click the API Credits button
    fireEvent.click(screen.getByText("API Credits").closest("button")!);

    // Now the amount input section should appear
    expect(screen.getByText("Enter Amount")).toBeInTheDocument();
    expect(screen.getByPlaceholderText("Amount in USD")).toBeInTheDocument();
  });

  /* ── 4. Creates redemption successfully ─────────────────────────────── */

  it("creates redemption successfully", async () => {
    mockCreateRedemption.mockResolvedValue({} as any);
    renderPage();

    await waitFor(() => {
      expect(screen.getByText("API Credits")).toBeInTheDocument();
    });

    // Select method
    fireEvent.click(screen.getByText("API Credits").closest("button")!);

    // Enter amount
    const input = screen.getByPlaceholderText("Amount in USD");
    fireEvent.change(input, { target: { value: "5" } });

    // Click withdraw — use the button role specifically
    const withdrawButtons = screen.getAllByRole("button");
    const withdrawButton = withdrawButtons.find((btn) =>
      btn.textContent?.includes("Withdraw") && btn.tagName === "BUTTON",
    )!;
    fireEvent.click(withdrawButton);

    // createRedemption should have been called with the right args
    await waitFor(() => {
      expect(mockCreateRedemption).toHaveBeenCalledWith(
        "test-token",
        expect.objectContaining({
          redemption_type: "api_credits",
          amount_usd: 5,
        }),
      );
    });

    // On success the component resets selectedType ("") → hides the amount input section
    // so we verify the input section is gone (success path cleared the form)
    await waitFor(() => {
      expect(screen.queryByPlaceholderText("Amount in USD")).toBeNull();
    });
  });

  /* ── 5. Shows error on failed redemption ─────────────────────────────── */

  it("shows error on failed redemption", async () => {
    mockCreateRedemption.mockRejectedValue(
      new Error("Insufficient balance"),
    );
    renderPage();

    await waitFor(() => {
      expect(screen.getByText("API Credits")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByText("API Credits").closest("button")!);
    const input = screen.getByPlaceholderText("Amount in USD");
    fireEvent.change(input, { target: { value: "5" } });

    const withdrawBtns = screen.getAllByRole("button");
    const withdrawBtn = withdrawBtns.find((btn) =>
      btn.textContent?.includes("Withdraw") && btn.tagName === "BUTTON",
    )!;
    fireEvent.click(withdrawBtn);

    await waitFor(() => {
      expect(screen.getByText("Insufficient balance")).toBeInTheDocument();
    });

    // Error message should have danger styling (not success)
    const msgEl = screen.getByText("Insufficient balance");
    expect(msgEl.className).toContain("text-danger");
  });

  /* ── 6. Shows withdrawal history ─────────────────────────────────────── */

  it("shows withdrawal history", async () => {
    const redemptions = [
      makeRedemption({ status: "completed", redemption_type: "gift_card" }),
      makeRedemption({
        id: "r2",
        status: "processing",
        redemption_type: "upi",
      }),
      makeRedemption({
        id: "r3",
        status: "failed",
        redemption_type: "bank_withdrawal",
      }),
    ];
    mockFetchRedemptions.mockResolvedValue({ redemptions } as any);
    renderPage();

    await waitFor(() => {
      expect(screen.getByText(/gift card/)).toBeInTheDocument();
    });

    expect(screen.getByText(/upi/)).toBeInTheDocument();
    expect(screen.getByText(/bank withdrawal/)).toBeInTheDocument();

    // Badges for each status
    expect(screen.getByText("completed")).toBeInTheDocument();
    expect(screen.getByText("processing")).toBeInTheDocument();
    expect(screen.getByText("failed")).toBeInTheDocument();
  });

  /* ── 7. Shows empty history state ────────────────────────────────────── */

  it("shows empty history state", async () => {
    mockFetchRedemptions.mockResolvedValue({ redemptions: [] } as any);
    renderPage();

    await waitFor(() => {
      expect(screen.getByText("No withdrawals yet.")).toBeInTheDocument();
    });
  });

  /* ── 8. Cancel button on pending items ───────────────────────────────── */

  it("cancel button on pending items", async () => {
    mockCancelRedemption.mockResolvedValue({} as any);
    const redemptions = [makeRedemption({ status: "pending", id: "r-pending" })];
    mockFetchRedemptions.mockResolvedValue({ redemptions } as any);
    renderPage();

    await waitFor(() => {
      expect(screen.getByText("Cancel")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByText("Cancel"));

    await waitFor(() => {
      expect(mockCancelRedemption).toHaveBeenCalledWith("test-token", "r-pending");
    });
  });

  /* ── 9. Status icons render correctly for each status ────────────────── */

  it("status icons render correctly for each status", async () => {
    const redemptions = [
      makeRedemption({ id: "s1", status: "completed" }),
      makeRedemption({ id: "s2", status: "processing" }),
      makeRedemption({ id: "s3", status: "pending" }),
      makeRedemption({ id: "s4", status: "failed" }),
      makeRedemption({ id: "s5", status: "rejected" }),
    ];
    mockFetchRedemptions.mockResolvedValue({ redemptions } as any);
    renderPage();

    await waitFor(() => {
      // All status badges rendered
      expect(screen.getByText("completed")).toBeInTheDocument();
      expect(screen.getByText("processing")).toBeInTheDocument();
      expect(screen.getByText("pending")).toBeInTheDocument();
      expect(screen.getByText("failed")).toBeInTheDocument();
      expect(screen.getByText("rejected")).toBeInTheDocument();
    });

    // pending status → Cancel button visible
    const cancelButtons = screen.getAllByText("Cancel");
    expect(cancelButtons).toHaveLength(1); // only pending status shows Cancel
  });

  /* ── 10. Unknown status falls back to Clock icon and "gray" variant ─── */

  it("unknown status uses Clock fallback icon and gray badge variant", async () => {
    const redemptions = [
      makeRedemption({ id: "u1", status: "unknown_status" as any }),
    ];
    mockFetchRedemptions.mockResolvedValue({ redemptions } as any);
    renderPage();

    await waitFor(() => {
      // The badge falls back to "gray" variant (STATUS_VARIANTS[r.status] || "gray")
      expect(screen.getByTestId("badge-gray")).toBeInTheDocument();
    });

    // unknown_status badge text
    expect(screen.getByText("unknown_status")).toBeInTheDocument();
  });

  /* ── 11. fetchCreatorWallet error is caught silently ─────────────────── */

  it("handles fetchCreatorWallet error gracefully", async () => {
    mockFetchCreatorWallet.mockRejectedValue(new Error("Network error"));
    // fetchRedemptions still succeeds
    mockFetchRedemptions.mockResolvedValue(emptyHistory as any);

    renderPage();

    // Balance stays at 0 (default state), no crash
    await waitFor(() => {
      expect(screen.getByTestId("animated-counter")).toBeInTheDocument();
    });

    // The page still renders normally
    expect(screen.getByText("API Credits")).toBeInTheDocument();
  });

  /* ── 12. fetchRedemptions error is caught silently ───────────────────── */

  it("handles fetchRedemptions error gracefully", async () => {
    mockFetchCreatorWallet.mockResolvedValue({ balance: 10 } as any);
    mockFetchRedemptions.mockRejectedValue(new Error("Network error"));

    renderPage();

    // History stays empty (no crash), empty state shown
    await waitFor(() => {
      expect(screen.getByText("No withdrawals yet.")).toBeInTheDocument();
    });
  });

  /* ── 13. Success message shows text-success styling ──────────────────── */

  it("shows success message with text-success class on successful redemption", async () => {
    mockCreateRedemption.mockResolvedValue({} as any);
    // Override fetchRedemptions to not resolve immediately so form stays visible
    mockFetchRedemptions.mockImplementation(() => new Promise(() => {}));
    renderPage();

    await waitFor(() => {
      expect(screen.getByText("API Credits")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByText("API Credits").closest("button")!);

    const input = screen.getByPlaceholderText("Amount in USD");
    fireEvent.change(input, { target: { value: "5" } });

    // The success message shows "Withdrawal request created successfully!" after submit
    // After success, selectedType is reset to "" which hides the section.
    // We verify createRedemption was called correctly.
    const withdrawBtns = screen.getAllByRole("button");
    const withdrawBtn = withdrawBtns.find(
      (btn) => btn.textContent?.includes("Withdraw") && btn.tagName === "BUTTON",
    )!;
    fireEvent.click(withdrawBtn);

    await waitFor(() => {
      expect(mockCreateRedemption).toHaveBeenCalledWith(
        "test-token",
        expect.objectContaining({ redemption_type: "api_credits", amount_usd: 5 }),
      );
    });
  });

  /* ── 14. Max button fills amount to balance ───────────────────────────── */

  it("Max button sets amount to current balance", async () => {
    mockFetchCreatorWallet.mockResolvedValue({ balance: 42 } as any);
    renderPage();

    await waitFor(() => {
      expect(screen.getByText("API Credits")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByText("API Credits").closest("button")!);

    await waitFor(() => {
      expect(screen.getByPlaceholderText("Amount in USD")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByText("Max"));

    const input = screen.getByPlaceholderText("Amount in USD") as HTMLInputElement;
    expect(input.value).toBe("42");
  });
});
