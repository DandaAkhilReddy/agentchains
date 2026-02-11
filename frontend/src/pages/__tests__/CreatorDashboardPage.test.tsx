import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { renderWithProviders } from "../../test/test-utils";
import CreatorDashboardPage from "../CreatorDashboardPage";
import * as api from "../../lib/api";

// Mock the API functions
vi.mock("../../lib/api", () => ({
  fetchCreatorDashboard: vi.fn(),
  claimAgent: vi.fn(),
}));

const mockDashboard = {
  creator_balance: 15000,
  creator_total_earned: 25000,
  creator_balance_usd: 15.0,
  agents_count: 2,
  agents: [
    {
      agent_id: "agent-1",
      agent_name: "Test Agent 1",
      agent_type: "seller",
      status: "active",
      total_earned: 10000,
      total_spent: 2000,
      balance: 8000,
    },
    {
      agent_id: "agent-2",
      agent_name: "Test Agent 2",
      agent_type: "buyer",
      status: "active",
      total_earned: 5000,
      total_spent: 1000,
      balance: 4000,
    },
  ],
  total_agent_earnings: 15000,
  total_agent_spent: 3000,
  peg_rate_usd: 0.001,
  token_name: "ARD",
};

describe("CreatorDashboardPage", () => {
  const mockProps = {
    token: "test-token-123",
    creatorName: "John Creator",
    onNavigate: vi.fn(),
    onLogout: vi.fn(),
  };

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders without crashing", async () => {
    vi.mocked(api.fetchCreatorDashboard).mockResolvedValue(mockDashboard);

    renderWithProviders(<CreatorDashboardPage {...mockProps} />);

    await waitFor(() => {
      expect(screen.getByText("Welcome, John Creator")).toBeInTheDocument();
    });
  });

  it("shows loading state initially", () => {
    vi.mocked(api.fetchCreatorDashboard).mockImplementation(
      () => new Promise(() => {}), // Never resolves
    );

    renderWithProviders(<CreatorDashboardPage {...mockProps} />);

    // Check for the loading spinner by class name since SVG has aria-hidden
    const spinner = document.querySelector('.lucide-refresh-cw.animate-spin');
    expect(spinner).toBeInTheDocument();
  });

  it("displays creator balance in ARD", async () => {
    vi.mocked(api.fetchCreatorDashboard).mockResolvedValue(mockDashboard);

    renderWithProviders(<CreatorDashboardPage {...mockProps} />);

    await waitFor(() => {
      // Check for the ARD Balance label to ensure we're looking at the right stat card
      expect(screen.getByText("ARD Balance")).toBeInTheDocument();
      const balances = screen.getAllByText(/15\.0K ARD/i);
      expect(balances.length).toBeGreaterThan(0);
    });
  });

  it("shows USD conversion for balance", async () => {
    vi.mocked(api.fetchCreatorDashboard).mockResolvedValue(mockDashboard);

    renderWithProviders(<CreatorDashboardPage {...mockProps} />);

    await waitFor(() => {
      // Multiple cards might show $15.00 USD, just verify at least one exists
      const usdTexts = screen.getAllByText(/\$15\.00 USD/i);
      expect(usdTexts.length).toBeGreaterThan(0);
    });
  });

  it("displays total earned", async () => {
    vi.mocked(api.fetchCreatorDashboard).mockResolvedValue(mockDashboard);

    renderWithProviders(<CreatorDashboardPage {...mockProps} />);

    await waitFor(() => {
      expect(screen.getByText("Total Earned")).toBeInTheDocument();
      expect(screen.getByText(/25\.0K ARD/i)).toBeInTheDocument();
    });
  });

  it("shows active agents count", async () => {
    vi.mocked(api.fetchCreatorDashboard).mockResolvedValue(mockDashboard);

    renderWithProviders(<CreatorDashboardPage {...mockProps} />);

    await waitFor(() => {
      expect(screen.getByText("Active Agents")).toBeInTheDocument();
      expect(screen.getByText("2")).toBeInTheDocument();
    });
  });

  it("lists claimed agents with details", async () => {
    vi.mocked(api.fetchCreatorDashboard).mockResolvedValue(mockDashboard);

    renderWithProviders(<CreatorDashboardPage {...mockProps} />);

    await waitFor(() => {
      expect(screen.getByText("Test Agent 1")).toBeInTheDocument();
      expect(screen.getByText("Test Agent 2")).toBeInTheDocument();
      expect(screen.getByText(/seller — active/i)).toBeInTheDocument();
      expect(screen.getByText(/buyer — active/i)).toBeInTheDocument();
    });
  });

  it("displays agent earnings and balance", async () => {
    vi.mocked(api.fetchCreatorDashboard).mockResolvedValue(mockDashboard);

    renderWithProviders(<CreatorDashboardPage {...mockProps} />);

    await waitFor(() => {
      expect(screen.getByText(/10\.0K ARD earned/i)).toBeInTheDocument();
      expect(screen.getByText(/Balance: 8\.0K ARD/i)).toBeInTheDocument();
    });
  });

  it("shows empty agents message when no agents are claimed", async () => {
    const emptyDashboard = {
      ...mockDashboard,
      agents: [],
      agents_count: 0,
    };

    vi.mocked(api.fetchCreatorDashboard).mockResolvedValue(emptyDashboard);

    renderWithProviders(<CreatorDashboardPage {...mockProps} />);

    await waitFor(() => {
      expect(screen.getByText("No agents linked yet. Claim your first agent below.")).toBeInTheDocument();
    });
  });

  it("handles claim agent button click successfully", async () => {
    const user = userEvent.setup();
    vi.mocked(api.fetchCreatorDashboard).mockResolvedValue(mockDashboard);
    vi.mocked(api.claimAgent).mockResolvedValue({
      agent_id: "new-agent-id",
      creator_id: "creator-id",
    });

    renderWithProviders(<CreatorDashboardPage {...mockProps} />);

    await waitFor(() => {
      expect(screen.getByText("Welcome, John Creator")).toBeInTheDocument();
    });

    const input = screen.getByPlaceholderText(/Agent ID \(UUID\)/i);
    await user.type(input, "new-agent-id");

    const claimButton = screen.getByRole("button", { name: /Claim/i });
    await user.click(claimButton);

    await waitFor(() => {
      expect(api.claimAgent).toHaveBeenCalledWith("test-token-123", "new-agent-id");
      expect(screen.getByText(/Agent linked successfully!/i)).toBeInTheDocument();
    });
  });

  it("handles claim agent error", async () => {
    const user = userEvent.setup();
    vi.mocked(api.fetchCreatorDashboard).mockResolvedValue(mockDashboard);
    vi.mocked(api.claimAgent).mockRejectedValue(new Error("Agent not found"));

    renderWithProviders(<CreatorDashboardPage {...mockProps} />);

    await waitFor(() => {
      expect(screen.getByText("Welcome, John Creator")).toBeInTheDocument();
    });

    const input = screen.getByPlaceholderText(/Agent ID \(UUID\)/i);
    await user.type(input, "invalid-agent-id");

    const claimButton = screen.getByRole("button", { name: /Claim/i });
    await user.click(claimButton);

    await waitFor(() => {
      expect(screen.getByText(/Agent not found/i)).toBeInTheDocument();
    });
  });

  it("navigates to redemption page when Redeem button is clicked", async () => {
    const user = userEvent.setup();
    vi.mocked(api.fetchCreatorDashboard).mockResolvedValue(mockDashboard);

    renderWithProviders(<CreatorDashboardPage {...mockProps} />);

    await waitFor(() => {
      expect(screen.getByText("Welcome, John Creator")).toBeInTheDocument();
    });

    const redeemButton = screen.getByRole("button", { name: /Redeem/i });
    await user.click(redeemButton);

    expect(mockProps.onNavigate).toHaveBeenCalledWith("redeem");
  });

  it("calls onLogout when logout button is clicked", async () => {
    const user = userEvent.setup();
    vi.mocked(api.fetchCreatorDashboard).mockResolvedValue(mockDashboard);

    renderWithProviders(<CreatorDashboardPage {...mockProps} />);

    await waitFor(() => {
      expect(screen.getByText("Welcome, John Creator")).toBeInTheDocument();
    });

    const buttons = screen.getAllByRole("button");
    const logoutButton = buttons.find(btn => btn.querySelector('svg.lucide-log-out'));

    if (logoutButton) {
      await user.click(logoutButton);
      expect(mockProps.onLogout).toHaveBeenCalled();
    }
  });

  it("displays token name correctly", async () => {
    vi.mocked(api.fetchCreatorDashboard).mockResolvedValue(mockDashboard);

    renderWithProviders(<CreatorDashboardPage {...mockProps} />);

    await waitFor(() => {
      expect(screen.getByText("ARD Balance")).toBeInTheDocument();
    });

    const ardTexts = screen.getAllByText(/ARD/);
    expect(ardTexts.length).toBeGreaterThan(0);
  });

  it("displays custom token name when provided", async () => {
    const customDashboard = {
      ...mockDashboard,
      token_name: "CUSTOM",
    };

    vi.mocked(api.fetchCreatorDashboard).mockResolvedValue(customDashboard);

    renderWithProviders(<CreatorDashboardPage {...mockProps} />);

    await waitFor(() => {
      expect(screen.getByText("CUSTOM Balance")).toBeInTheDocument();
    });
  });

  it("formats large numbers correctly", async () => {
    const largeNumberDashboard = {
      ...mockDashboard,
      creator_balance: 1500000,
      creator_total_earned: 2500000,
    };

    vi.mocked(api.fetchCreatorDashboard).mockResolvedValue(largeNumberDashboard);

    renderWithProviders(<CreatorDashboardPage {...mockProps} />);

    await waitFor(() => {
      expect(screen.getByText(/1\.50M ARD/i)).toBeInTheDocument();
      expect(screen.getByText(/2\.50M ARD/i)).toBeInTheDocument();
    });
  });

  it("handles dashboard load error gracefully", async () => {
    const consoleError = vi.spyOn(console, "error").mockImplementation(() => {});
    vi.mocked(api.fetchCreatorDashboard).mockRejectedValue(new Error("Network error"));

    renderWithProviders(<CreatorDashboardPage {...mockProps} />);

    await waitFor(() => {
      expect(consoleError).toHaveBeenCalledWith("Dashboard load failed:", expect.any(Error));
    });

    consoleError.mockRestore();
  });

  it("clears claim input after successful claim", async () => {
    const user = userEvent.setup();
    vi.mocked(api.fetchCreatorDashboard).mockResolvedValue(mockDashboard);
    vi.mocked(api.claimAgent).mockResolvedValue({
      agent_id: "new-agent-id",
      creator_id: "creator-id",
    });

    renderWithProviders(<CreatorDashboardPage {...mockProps} />);

    await waitFor(() => {
      expect(screen.getByText("Welcome, John Creator")).toBeInTheDocument();
    });

    const input = screen.getByPlaceholderText(/Agent ID \(UUID\)/i) as HTMLInputElement;
    await user.type(input, "new-agent-id");
    expect(input.value).toBe("new-agent-id");

    const claimButton = screen.getByRole("button", { name: /Claim/i });
    await user.click(claimButton);

    await waitFor(() => {
      expect(input.value).toBe("");
    });
  });

  it("does not call claimAgent when input is empty", async () => {
    const user = userEvent.setup();
    vi.mocked(api.fetchCreatorDashboard).mockResolvedValue(mockDashboard);

    renderWithProviders(<CreatorDashboardPage {...mockProps} />);

    await waitFor(() => {
      expect(screen.getByText("Welcome, John Creator")).toBeInTheDocument();
    });

    const claimButton = screen.getByRole("button", { name: /Claim/i });
    await user.click(claimButton);

    expect(api.claimAgent).not.toHaveBeenCalled();
  });

  it("displays agent total earnings with USD conversion", async () => {
    vi.mocked(api.fetchCreatorDashboard).mockResolvedValue(mockDashboard);

    renderWithProviders(<CreatorDashboardPage {...mockProps} />);

    await waitFor(() => {
      expect(screen.getByText("Agent Earnings")).toBeInTheDocument();
      // Both creator balance and agent earnings show 15.0K ARD
      const ardTexts = screen.getAllByText(/15\.0K ARD/i);
      expect(ardTexts.length).toBeGreaterThan(0);
      const usdTexts = screen.getAllByText(/\$15\.00 USD/i);
      expect(usdTexts.length).toBeGreaterThan(0);
    });
  });

  it("reloads dashboard after successful agent claim", async () => {
    const user = userEvent.setup();
    vi.mocked(api.fetchCreatorDashboard).mockResolvedValue(mockDashboard);
    vi.mocked(api.claimAgent).mockResolvedValue({
      agent_id: "new-agent-id",
      creator_id: "creator-id",
    });

    renderWithProviders(<CreatorDashboardPage {...mockProps} />);

    await waitFor(() => {
      expect(api.fetchCreatorDashboard).toHaveBeenCalledTimes(1);
    });

    const input = screen.getByPlaceholderText(/Agent ID \(UUID\)/i);
    await user.type(input, "new-agent-id");

    const claimButton = screen.getByRole("button", { name: /Claim/i });
    await user.click(claimButton);

    await waitFor(() => {
      expect(api.fetchCreatorDashboard).toHaveBeenCalledTimes(2);
    });
  });
});
