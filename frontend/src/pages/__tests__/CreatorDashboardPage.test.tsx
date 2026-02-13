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
      // Agent 1: balance = 8.0 -> formatUSD -> "Balance: $8.00"
      expect(screen.getByText("Balance: $8.00")).toBeInTheDocument();
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
});
