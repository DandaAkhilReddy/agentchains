import { describe, it, expect, vi, beforeEach } from "vitest";
import { screen, fireEvent } from "@testing-library/react";
import { renderWithProviders } from "../../test/test-utils";
import AgentProfilePage from "../AgentProfilePage";
import * as useAnalyticsModule from "../../hooks/useAnalytics";
import * as useAuthModule from "../../hooks/useAuth";
import type { AgentProfile, EarningsBreakdown } from "../../types/api";

// Mock hooks
vi.mock("../../hooks/useAuth");
vi.mock("../../hooks/useAnalytics");

// Mock AnimatedCounter to render value directly
vi.mock("../../components/AnimatedCounter", () => ({
  default: ({ value }: { value: number }) => <span>{value}</span>,
}));

// Mock chart components since they use canvas/SVG that jsdom cannot render
vi.mock("../../components/EarningsChart", () => ({
  default: ({ data }: any) => <div data-testid="earnings-chart">EarningsChart ({data?.length ?? 0} points)</div>,
}));

vi.mock("../../components/CategoryPieChart", () => ({
  default: ({ data }: any) => <div data-testid="category-pie-chart">CategoryPieChart</div>,
}));

vi.mock("../../components/ProgressRing", () => ({
  default: ({ value }: { value: number }) => <div data-testid="progress-ring">{value}%</div>,
}));

/* ── Test Data ──────────────────────────────────────────── */

const mockProfile: AgentProfile = {
  agent_id: "agent-001",
  agent_name: "AlphaSearch Agent",
  unique_buyers_served: 42,
  total_listings_created: 128,
  total_cache_hits: 350,
  category_count: 3,
  categories: ["web_search", "code_analysis", "document_summary"],
  total_earned_usdc: 1.2345,
  total_spent_usdc: 0.4567,
  demand_gaps_filled: 15,
  avg_listing_quality: 0.88,
  total_data_bytes: 1048576,
  helpfulness_score: 0.92,
  helpfulness_rank: 3,
  earnings_rank: 5,
  primary_specialization: "web_search",
  specialization_tags: ["search", "analysis"],
  last_calculated_at: new Date().toISOString(),
};

const mockEarnings: EarningsBreakdown = {
  agent_id: "agent-001",
  total_earned_usdc: 1.2345,
  total_spent_usdc: 0.4567,
  net_revenue_usdc: 0.7778,
  earnings_by_category: {
    web_search: 0.8,
    code_analysis: 0.3,
    document_summary: 0.1345,
  },
  earnings_timeline: [
    { date: "2025-01-01", earned: 0.5, spent: 0.2 },
    { date: "2025-01-02", earned: 0.7345, spent: 0.2567 },
  ],
};

/* ── Tests ──────────────────────────────────────────────── */

describe("AgentProfilePage", () => {
  const mockOnBack = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders agent profile with name and details", () => {
    vi.spyOn(useAuthModule, "useAuth").mockReturnValue({
      token: "test-jwt",
      login: vi.fn(),
      logout: vi.fn(),
      isAuthenticated: true,
    });
    vi.spyOn(useAnalyticsModule, "useAgentProfile").mockReturnValue({
      data: mockProfile,
      isLoading: false,
      error: null,
    } as any);
    vi.spyOn(useAnalyticsModule, "useMyEarnings").mockReturnValue({
      data: mockEarnings,
      isLoading: false,
      error: null,
    } as any);

    renderWithProviders(
      <AgentProfilePage agentId="agent-001" onBack={mockOnBack} />,
    );

    // Agent name should appear in both PageHeader and hero card
    expect(screen.getAllByText("AlphaSearch Agent").length).toBeGreaterThanOrEqual(1);
    // Primary specialization badge
    expect(screen.getAllByText("web_search").length).toBeGreaterThanOrEqual(1);
  });

  it("shows agent stats with animated counters", () => {
    vi.spyOn(useAuthModule, "useAuth").mockReturnValue({
      token: "test-jwt",
      login: vi.fn(),
      logout: vi.fn(),
      isAuthenticated: true,
    });
    vi.spyOn(useAnalyticsModule, "useAgentProfile").mockReturnValue({
      data: mockProfile,
      isLoading: false,
      error: null,
    } as any);
    vi.spyOn(useAnalyticsModule, "useMyEarnings").mockReturnValue({
      data: mockEarnings,
      isLoading: false,
      error: null,
    } as any);

    renderWithProviders(
      <AgentProfilePage agentId="agent-001" onBack={mockOnBack} />,
    );

    // Stat labels
    expect(screen.getByText("Unique Buyers Served")).toBeInTheDocument();
    expect(screen.getByText("Listings Created")).toBeInTheDocument();
    expect(screen.getByText("Cache Hits (Reuse)")).toBeInTheDocument();
    expect(screen.getByText("Gaps Filled")).toBeInTheDocument();

    // Stat values (AnimatedCounter is mocked to show value directly)
    expect(screen.getByText("42")).toBeInTheDocument();
    expect(screen.getByText("128")).toBeInTheDocument();
    expect(screen.getByText("350")).toBeInTheDocument();
    expect(screen.getByText("15")).toBeInTheDocument();
  });

  it("shows helpfulness score as progress ring", () => {
    vi.spyOn(useAuthModule, "useAuth").mockReturnValue({
      token: "test-jwt",
      login: vi.fn(),
      logout: vi.fn(),
      isAuthenticated: true,
    });
    vi.spyOn(useAnalyticsModule, "useAgentProfile").mockReturnValue({
      data: mockProfile,
      isLoading: false,
      error: null,
    } as any);
    vi.spyOn(useAnalyticsModule, "useMyEarnings").mockReturnValue({
      data: mockEarnings,
      isLoading: false,
      error: null,
    } as any);

    renderWithProviders(
      <AgentProfilePage agentId="agent-001" onBack={mockOnBack} />,
    );

    // ProgressRing is mocked and should show 92%
    expect(screen.getByTestId("progress-ring")).toBeInTheDocument();
    expect(screen.getByText("92%")).toBeInTheDocument();
    expect(screen.getByText("Helpfulness")).toBeInTheDocument();
  });

  it("shows loading skeleton state", () => {
    vi.spyOn(useAuthModule, "useAuth").mockReturnValue({
      token: "test-jwt",
      login: vi.fn(),
      logout: vi.fn(),
      isAuthenticated: true,
    });
    vi.spyOn(useAnalyticsModule, "useAgentProfile").mockReturnValue({
      data: undefined,
      isLoading: true,
      error: null,
    } as any);
    vi.spyOn(useAnalyticsModule, "useMyEarnings").mockReturnValue({
      data: undefined,
      isLoading: false,
      error: null,
    } as any);

    const { container } = renderWithProviders(
      <AgentProfilePage agentId="agent-001" onBack={mockOnBack} />,
    );

    // Skeleton cards should be rendered (SkeletonCard uses the grid layout)
    const grid = container.querySelector(".grid");
    expect(grid).toBeInTheDocument();
  });

  it("shows agent not found state when profile is null", () => {
    vi.spyOn(useAuthModule, "useAuth").mockReturnValue({
      token: "",
      login: vi.fn(),
      logout: vi.fn(),
      isAuthenticated: false,
    });
    vi.spyOn(useAnalyticsModule, "useAgentProfile").mockReturnValue({
      data: null,
      isLoading: false,
      error: null,
    } as any);
    vi.spyOn(useAnalyticsModule, "useMyEarnings").mockReturnValue({
      data: undefined,
      isLoading: false,
      error: null,
    } as any);

    renderWithProviders(
      <AgentProfilePage agentId="nonexistent" onBack={mockOnBack} />,
    );

    expect(screen.getByText("Agent not found")).toBeInTheDocument();
    expect(screen.getByText("Go back")).toBeInTheDocument();
  });

  it("calls onBack when back button is clicked on profile page", () => {
    vi.spyOn(useAuthModule, "useAuth").mockReturnValue({
      token: "test-jwt",
      login: vi.fn(),
      logout: vi.fn(),
      isAuthenticated: true,
    });
    vi.spyOn(useAnalyticsModule, "useAgentProfile").mockReturnValue({
      data: mockProfile,
      isLoading: false,
      error: null,
    } as any);
    vi.spyOn(useAnalyticsModule, "useMyEarnings").mockReturnValue({
      data: mockEarnings,
      isLoading: false,
      error: null,
    } as any);

    renderWithProviders(
      <AgentProfilePage agentId="agent-001" onBack={mockOnBack} />,
    );

    // Click the Back button in the PageHeader actions
    fireEvent.click(screen.getByText("Back"));

    expect(mockOnBack).toHaveBeenCalledTimes(1);
  });

  it("calls onBack when Go back link is clicked on not found page", () => {
    vi.spyOn(useAuthModule, "useAuth").mockReturnValue({
      token: "",
      login: vi.fn(),
      logout: vi.fn(),
      isAuthenticated: false,
    });
    vi.spyOn(useAnalyticsModule, "useAgentProfile").mockReturnValue({
      data: null,
      isLoading: false,
      error: null,
    } as any);
    vi.spyOn(useAnalyticsModule, "useMyEarnings").mockReturnValue({
      data: undefined,
      isLoading: false,
      error: null,
    } as any);

    renderWithProviders(
      <AgentProfilePage agentId="nonexistent" onBack={mockOnBack} />,
    );

    fireEvent.click(screen.getByText("Go back"));

    expect(mockOnBack).toHaveBeenCalledTimes(1);
  });

  it("shows financial overview with earned, spent, and net revenue", () => {
    vi.spyOn(useAuthModule, "useAuth").mockReturnValue({
      token: "test-jwt",
      login: vi.fn(),
      logout: vi.fn(),
      isAuthenticated: true,
    });
    vi.spyOn(useAnalyticsModule, "useAgentProfile").mockReturnValue({
      data: mockProfile,
      isLoading: false,
      error: null,
    } as any);
    vi.spyOn(useAnalyticsModule, "useMyEarnings").mockReturnValue({
      data: mockEarnings,
      isLoading: false,
      error: null,
    } as any);

    renderWithProviders(
      <AgentProfilePage agentId="agent-001" onBack={mockOnBack} />,
    );

    expect(screen.getByText("Total Earned")).toBeInTheDocument();
    expect(screen.getByText("Total Spent")).toBeInTheDocument();
    expect(screen.getByText("Net Revenue")).toBeInTheDocument();
    expect(screen.getByText("$1.2345")).toBeInTheDocument();
    expect(screen.getByText("$0.4567")).toBeInTheDocument();
    expect(screen.getByText("$0.7778")).toBeInTheDocument();
  });
});
