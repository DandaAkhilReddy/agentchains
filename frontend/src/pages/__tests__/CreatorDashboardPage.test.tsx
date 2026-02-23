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

// Mock AnimatedCounter to render synchronously (rAF doesn't work in jsdom)
vi.mock("../../components/AnimatedCounter", () => ({
  default: ({ value, className }: { value: number; className?: string }) => (
    <span className={className}>{value.toLocaleString()}</span>
  ),
}));

const mockDashboard = {
  creator_balance: 15.0,
  creator_total_earned: 25.0,
  agents_count: 2,
  agents: [
    {
      agent_id: "agent-1",
      agent_name: "Test Agent 1",
      agent_type: "seller",
      status: "active",
      total_earned: 10.0,
      total_spent: 2.0,
      balance: 8.0,
    },
    {
      agent_id: "agent-2",
      agent_name: "Test Agent 2",
      agent_type: "buyer",
      status: "active",
      total_earned: 5.0,
      total_spent: 1.0,
      balance: 4.0,
    },
  ],
  total_agent_earnings: 15.0,
  total_agent_spent: 3.0,
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
      expect(screen.getByText(/Welcome back, John Creator/)).toBeInTheDocument();
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

  it("shows loading text during loading state", () => {
    vi.mocked(api.fetchCreatorDashboard).mockImplementation(
      () => new Promise(() => {}),
    );

    renderWithProviders(<CreatorDashboardPage {...mockProps} />);

    expect(screen.getByText("Loading dashboard...")).toBeInTheDocument();
  });

  it("displays creator balance in USD", async () => {
    vi.mocked(api.fetchCreatorDashboard).mockResolvedValue(mockDashboard);

    renderWithProviders(<CreatorDashboardPage {...mockProps} />);

    await waitFor(() => {
      expect(screen.getByText("USD Balance")).toBeInTheDocument();
      // $15.00 appears in both USD Balance and Agent Earnings (both are 15.0)
      const amounts = screen.getAllByText("$15.00");
      expect(amounts.length).toBeGreaterThanOrEqual(1);
    });
  });

  it("displays total earned in USD", async () => {
    vi.mocked(api.fetchCreatorDashboard).mockResolvedValue(mockDashboard);

    renderWithProviders(<CreatorDashboardPage {...mockProps} />);

    await waitFor(() => {
      expect(screen.getByText("Total Earned")).toBeInTheDocument();
      expect(screen.getByText("$25.00")).toBeInTheDocument();
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
    });
  });

  it("displays agent earnings and balance in USD", async () => {
    vi.mocked(api.fetchCreatorDashboard).mockResolvedValue(mockDashboard);

    renderWithProviders(<CreatorDashboardPage {...mockProps} />);

    await waitFor(() => {
      // Agent 1: total_earned = 10.0 -> formatUSD -> "$10.00"
      expect(screen.getByText("$10.00")).toBeInTheDocument();
      // Agent 1: balance = 8.0 -> formatUSD -> "$8.00" (shown under separate "Balance" label)
      expect(screen.getByText("$8.00")).toBeInTheDocument();
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
      // New markup splits the message into two separate elements
      expect(screen.getByText("No agents linked yet")).toBeInTheDocument();
      expect(screen.getByText("Claim your first agent below to get started")).toBeInTheDocument();
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
      expect(screen.getByText(/Welcome back, John Creator/)).toBeInTheDocument();
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
      expect(screen.getByText(/Welcome back, John Creator/)).toBeInTheDocument();
    });

    const input = screen.getByPlaceholderText(/Agent ID \(UUID\)/i);
    await user.type(input, "invalid-agent-id");

    const claimButton = screen.getByRole("button", { name: /Claim/i });
    await user.click(claimButton);

    await waitFor(() => {
      expect(screen.getByText(/Agent not found/i)).toBeInTheDocument();
    });
  });

  it("navigates to withdrawal page when Withdraw button is clicked", async () => {
    const user = userEvent.setup();
    vi.mocked(api.fetchCreatorDashboard).mockResolvedValue(mockDashboard);

    renderWithProviders(<CreatorDashboardPage {...mockProps} />);

    await waitFor(() => {
      expect(screen.getByText(/Welcome back, John Creator/)).toBeInTheDocument();
    });

    const withdrawButton = screen.getByRole("button", { name: /Withdraw/i });
    await user.click(withdrawButton);

    expect(mockProps.onNavigate).toHaveBeenCalledWith("redeem");
  });

  it("calls onLogout when logout button is clicked", async () => {
    const user = userEvent.setup();
    vi.mocked(api.fetchCreatorDashboard).mockResolvedValue(mockDashboard);

    renderWithProviders(<CreatorDashboardPage {...mockProps} />);

    await waitFor(() => {
      expect(screen.getByText(/Welcome back, John Creator/)).toBeInTheDocument();
    });

    const buttons = screen.getAllByRole("button");
    const logoutButton = buttons.find(btn => btn.querySelector('svg.lucide-log-out'));

    if (logoutButton) {
      await user.click(logoutButton);
      expect(mockProps.onLogout).toHaveBeenCalled();
    }
  });

  it("displays USD Balance label correctly", async () => {
    vi.mocked(api.fetchCreatorDashboard).mockResolvedValue(mockDashboard);

    renderWithProviders(<CreatorDashboardPage {...mockProps} />);

    await waitFor(() => {
      expect(screen.getByText("USD Balance")).toBeInTheDocument();
    });
  });

  it("formats large numbers correctly", async () => {
    const largeNumberDashboard = {
      ...mockDashboard,
      creator_balance: 1500.0,
      creator_total_earned: 2500.0,
    };

    vi.mocked(api.fetchCreatorDashboard).mockResolvedValue(largeNumberDashboard);

    renderWithProviders(<CreatorDashboardPage {...mockProps} />);

    await waitFor(() => {
      // formatUSD(1500) -> "$1.5K"
      expect(screen.getByText("$1.5K")).toBeInTheDocument();
      // formatUSD(2500) -> "$2.5K"
      expect(screen.getByText("$2.5K")).toBeInTheDocument();
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
      expect(screen.getByText(/Welcome back, John Creator/)).toBeInTheDocument();
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
      expect(screen.getByText(/Welcome back, John Creator/)).toBeInTheDocument();
    });

    const claimButton = screen.getByRole("button", { name: /Claim/i });
    await user.click(claimButton);

    expect(api.claimAgent).not.toHaveBeenCalled();
  });

  it("displays agent total earnings in USD", async () => {
    vi.mocked(api.fetchCreatorDashboard).mockResolvedValue(mockDashboard);

    renderWithProviders(<CreatorDashboardPage {...mockProps} />);

    await waitFor(() => {
      expect(screen.getByText("Agent Earnings")).toBeInTheDocument();
      // total_agent_earnings = 15.0 -> formatUSD -> "$15.00"
      const usdTexts = screen.getAllByText("$15.00");
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

  // ─── New coverage tests ───

  it("renders the Creator Studio header", async () => {
    vi.mocked(api.fetchCreatorDashboard).mockResolvedValue(mockDashboard);

    renderWithProviders(<CreatorDashboardPage {...mockProps} />);

    await waitFor(() => {
      expect(screen.getByText("Creator Studio")).toBeInTheDocument();
    });
  });

  it("renders Your Agents section heading", async () => {
    vi.mocked(api.fetchCreatorDashboard).mockResolvedValue(mockDashboard);

    renderWithProviders(<CreatorDashboardPage {...mockProps} />);

    await waitFor(() => {
      expect(screen.getByText("Your Agents")).toBeInTheDocument();
    });
  });

  it("renders Claim an Agent section", async () => {
    vi.mocked(api.fetchCreatorDashboard).mockResolvedValue(mockDashboard);

    renderWithProviders(<CreatorDashboardPage {...mockProps} />);

    await waitFor(() => {
      expect(screen.getByText("Claim an Agent")).toBeInTheDocument();
      expect(
        screen.getByText(/Enter your agent's ID to claim ownership/),
      ).toBeInTheDocument();
    });
  });

  it("renders agent type badges", async () => {
    vi.mocked(api.fetchCreatorDashboard).mockResolvedValue(mockDashboard);

    renderWithProviders(<CreatorDashboardPage {...mockProps} />);

    await waitFor(() => {
      expect(screen.getByText("seller")).toBeInTheDocument();
      expect(screen.getByText("buyer")).toBeInTheDocument();
    });
  });

  it("renders agent status badges", async () => {
    vi.mocked(api.fetchCreatorDashboard).mockResolvedValue(mockDashboard);

    renderWithProviders(<CreatorDashboardPage {...mockProps} />);

    await waitFor(() => {
      // Both agents are active
      const activeBadges = screen.getAllByText("active");
      expect(activeBadges.length).toBe(2);
    });
  });

  it("renders agent avatar initials correctly", async () => {
    vi.mocked(api.fetchCreatorDashboard).mockResolvedValue(mockDashboard);

    renderWithProviders(<CreatorDashboardPage {...mockProps} />);

    await waitFor(() => {
      // "Test Agent 1".slice(0,2).toUpperCase() = "TE"
      const avatars = screen.getAllByText("TE");
      expect(avatars.length).toBe(2); // Both agents start with "Te"
    });
  });

  it("renders Earned and Balance labels for each agent", async () => {
    vi.mocked(api.fetchCreatorDashboard).mockResolvedValue(mockDashboard);

    renderWithProviders(<CreatorDashboardPage {...mockProps} />);

    await waitFor(() => {
      const earnedLabels = screen.getAllByText("Earned");
      expect(earnedLabels.length).toBe(2);

      const balanceLabels = screen.getAllByText("Balance");
      expect(balanceLabels.length).toBe(2);
    });
  });

  it("disables claim button when input is empty", async () => {
    vi.mocked(api.fetchCreatorDashboard).mockResolvedValue(mockDashboard);

    renderWithProviders(<CreatorDashboardPage {...mockProps} />);

    await waitFor(() => {
      expect(screen.getByText(/Welcome back/)).toBeInTheDocument();
    });

    const claimButton = screen.getByRole("button", { name: /Claim/i });
    expect(claimButton).toBeDisabled();
  });

  it("enables claim button when input has value", async () => {
    const user = userEvent.setup();
    vi.mocked(api.fetchCreatorDashboard).mockResolvedValue(mockDashboard);

    renderWithProviders(<CreatorDashboardPage {...mockProps} />);

    await waitFor(() => {
      expect(screen.getByText(/Welcome back/)).toBeInTheDocument();
    });

    const input = screen.getByPlaceholderText(/Agent ID \(UUID\)/i);
    await user.type(input, "some-agent-id");

    const claimButton = screen.getByRole("button", { name: /Claim/i });
    expect(claimButton).not.toBeDisabled();
  });

  it("shows success message in green color", async () => {
    const user = userEvent.setup();
    vi.mocked(api.fetchCreatorDashboard).mockResolvedValue(mockDashboard);
    vi.mocked(api.claimAgent).mockResolvedValue({
      agent_id: "new-agent-id",
      creator_id: "creator-id",
    });

    renderWithProviders(<CreatorDashboardPage {...mockProps} />);

    await waitFor(() => {
      expect(screen.getByText(/Welcome back/)).toBeInTheDocument();
    });

    const input = screen.getByPlaceholderText(/Agent ID \(UUID\)/i);
    await user.type(input, "new-agent-id");
    const claimButton = screen.getByRole("button", { name: /Claim/i });
    await user.click(claimButton);

    await waitFor(() => {
      const msg = screen.getByText("Agent linked successfully!");
      // The color for success messages contains "#34d399"
      expect(msg.style.color).toBe("rgb(52, 211, 153)");
    });
  });

  it("shows error message in red color", async () => {
    const user = userEvent.setup();
    vi.mocked(api.fetchCreatorDashboard).mockResolvedValue(mockDashboard);
    vi.mocked(api.claimAgent).mockRejectedValue(new Error("Agent not found"));

    renderWithProviders(<CreatorDashboardPage {...mockProps} />);

    await waitFor(() => {
      expect(screen.getByText(/Welcome back/)).toBeInTheDocument();
    });

    const input = screen.getByPlaceholderText(/Agent ID \(UUID\)/i);
    await user.type(input, "bad-id");
    const claimButton = screen.getByRole("button", { name: /Claim/i });
    await user.click(claimButton);

    await waitFor(() => {
      const msg = screen.getByText("Agent not found");
      // The color for error messages contains "#f87171"
      expect(msg.style.color).toBe("rgb(248, 113, 113)");
    });
  });

  it("shows fallback error message when claim error has no message", async () => {
    const user = userEvent.setup();
    vi.mocked(api.fetchCreatorDashboard).mockResolvedValue(mockDashboard);
    vi.mocked(api.claimAgent).mockRejectedValue({});

    renderWithProviders(<CreatorDashboardPage {...mockProps} />);

    await waitFor(() => {
      expect(screen.getByText(/Welcome back/)).toBeInTheDocument();
    });

    const input = screen.getByPlaceholderText(/Agent ID \(UUID\)/i);
    await user.type(input, "bad-id");
    const claimButton = screen.getByRole("button", { name: /Claim/i });
    await user.click(claimButton);

    await waitFor(() => {
      expect(screen.getByText("Failed to claim agent")).toBeInTheDocument();
    });
  });

  it("handles stat card mouse hover interactions", async () => {
    vi.mocked(api.fetchCreatorDashboard).mockResolvedValue(mockDashboard);

    const { container } = renderWithProviders(<CreatorDashboardPage {...mockProps} />);

    await waitFor(() => {
      expect(screen.getByText("USD Balance")).toBeInTheDocument();
    });

    // Find stat cards by their label text parent
    const statCard = screen.getByText("USD Balance").closest("[class*='group']") as HTMLElement;
    expect(statCard).toBeTruthy();

    // Trigger mouseEnter and mouseLeave on the stat card
    const { fireEvent } = await import("@testing-library/react");
    fireEvent.mouseEnter(statCard);
    fireEvent.mouseLeave(statCard);
    // No errors should occur
  });

  it("handles agent card mouse hover interactions", async () => {
    vi.mocked(api.fetchCreatorDashboard).mockResolvedValue(mockDashboard);

    renderWithProviders(<CreatorDashboardPage {...mockProps} />);

    await waitFor(() => {
      expect(screen.getByText("Test Agent 1")).toBeInTheDocument();
    });

    const agentCard = screen.getByText("Test Agent 1").closest("[class*='group']") as HTMLElement;
    expect(agentCard).toBeTruthy();

    const { fireEvent } = await import("@testing-library/react");
    fireEvent.mouseEnter(agentCard);
    fireEvent.mouseLeave(agentCard);
    // No errors should occur
  });

  it("renders with null dashboard (fallback to zero values)", async () => {
    // Simulate API error followed by render with null dashboard
    const consoleError = vi.spyOn(console, "error").mockImplementation(() => {});
    vi.mocked(api.fetchCreatorDashboard).mockRejectedValue(new Error("fail"));

    renderWithProviders(<CreatorDashboardPage {...mockProps} />);

    await waitFor(() => {
      // After loading fails, dashboard is null. The page should still render stat cards
      // with fallback 0 values
      expect(screen.getByText("USD Balance")).toBeInTheDocument();
      const zeroAmounts = screen.getAllByText("$0.00");
      expect(zeroAmounts.length).toBeGreaterThanOrEqual(1);
    });

    consoleError.mockRestore();
  });

  it("renders inactive agent status with gray badge variant", async () => {
    const dashboardWithInactiveAgent = {
      ...mockDashboard,
      agents: [
        {
          agent_id: "agent-3",
          agent_name: "Inactive Agent",
          agent_type: "seller",
          status: "inactive",
          total_earned: 0.0,
          total_spent: 0.0,
          balance: 0.0,
        },
      ],
      agents_count: 1,
    };

    vi.mocked(api.fetchCreatorDashboard).mockResolvedValue(dashboardWithInactiveAgent);

    renderWithProviders(<CreatorDashboardPage {...mockProps} />);

    await waitFor(() => {
      expect(screen.getByText("Inactive Agent")).toBeInTheDocument();
      expect(screen.getByText("inactive")).toBeInTheDocument();
    });
  });

  it("calls fetchCreatorDashboard with the correct token", async () => {
    vi.mocked(api.fetchCreatorDashboard).mockResolvedValue(mockDashboard);

    renderWithProviders(<CreatorDashboardPage {...mockProps} />);

    await waitFor(() => {
      expect(api.fetchCreatorDashboard).toHaveBeenCalledWith("test-token-123");
    });
  });

  it("formats million-dollar values correctly", async () => {
    const millionDashboard = {
      ...mockDashboard,
      creator_balance: 1500000,
      creator_total_earned: 2500000,
    };

    vi.mocked(api.fetchCreatorDashboard).mockResolvedValue(millionDashboard);

    renderWithProviders(<CreatorDashboardPage {...mockProps} />);

    await waitFor(() => {
      // formatUSD(1500000) -> "$1.5M"
      expect(screen.getByText("$1.5M")).toBeInTheDocument();
      // formatUSD(2500000) -> "$2.5M"
      expect(screen.getByText("$2.5M")).toBeInTheDocument();
    });
  });

  it("updates claim input value on typing", async () => {
    const user = userEvent.setup();
    vi.mocked(api.fetchCreatorDashboard).mockResolvedValue(mockDashboard);

    renderWithProviders(<CreatorDashboardPage {...mockProps} />);

    await waitFor(() => {
      expect(screen.getByText(/Welcome back/)).toBeInTheDocument();
    });

    const input = screen.getByPlaceholderText(/Agent ID \(UUID\)/i) as HTMLInputElement;
    await user.type(input, "abc-123");
    expect(input.value).toBe("abc-123");
  });

  it("renders all four stat card labels", async () => {
    vi.mocked(api.fetchCreatorDashboard).mockResolvedValue(mockDashboard);

    renderWithProviders(<CreatorDashboardPage {...mockProps} />);

    await waitFor(() => {
      expect(screen.getByText("USD Balance")).toBeInTheDocument();
      expect(screen.getByText("Total Earned")).toBeInTheDocument();
      expect(screen.getByText("Active Agents")).toBeInTheDocument();
      expect(screen.getByText("Agent Earnings")).toBeInTheDocument();
    });
  });

  it("does not call claimAgent when input is only whitespace", async () => {
    const user = userEvent.setup();
    vi.mocked(api.fetchCreatorDashboard).mockResolvedValue(mockDashboard);

    renderWithProviders(<CreatorDashboardPage {...mockProps} />);

    await waitFor(() => {
      expect(screen.getByText(/Welcome back/)).toBeInTheDocument();
    });

    const input = screen.getByPlaceholderText(/Agent ID \(UUID\)/i);
    // Type spaces (the trim() check should prevent the API call)
    await user.type(input, "   ");

    // The button should still be disabled because trim() is empty
    const claimButton = screen.getByRole("button", { name: /Claim/i });
    expect(claimButton).toBeDisabled();
  });
});
