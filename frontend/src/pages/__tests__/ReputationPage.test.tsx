import { describe, it, expect, vi, beforeEach } from "vitest";
import { screen, fireEvent } from "@testing-library/react";
import { renderWithProviders } from "../../test/test-utils";
import ReputationPage from "../ReputationPage";
import * as useReputationModule from "../../hooks/useReputation";
import * as useAnalyticsModule from "../../hooks/useAnalytics";
import type {
  LeaderboardEntry,
  MultiLeaderboardEntry,
} from "../../types/api";

/* ── Mocks ── */

vi.mock("../../hooks/useReputation");
vi.mock("../../hooks/useAnalytics");

vi.mock("recharts", () => ({
  ResponsiveContainer: ({ children }: any) => <div>{children}</div>,
  AreaChart: ({ children }: any) => <svg data-testid="chart">{children}</svg>,
  PieChart: ({ children }: any) => <svg data-testid="chart">{children}</svg>,
  BarChart: ({ children }: any) => <svg data-testid="chart">{children}</svg>,
  Area: () => null,
  Pie: () => null,
  Bar: () => null,
  Cell: () => null,
  XAxis: () => null,
  YAxis: () => null,
  Tooltip: () => null,
  CartesianGrid: () => null,
  Legend: () => null,
  Line: () => null,
  LineChart: ({ children }: any) => <svg>{children}</svg>,
}));

vi.mock("../../components/AnimatedCounter", () => ({
  default: ({ value }: any) => <span>{value}</span>,
}));

/* ── Test Data ── */

const mockLeaderboardEntries: LeaderboardEntry[] = [
  {
    rank: 1,
    agent_id: "agent-001",
    agent_name: "Alpha Agent",
    composite_score: 0.95,
    total_transactions: 500,
    total_volume_usdc: 12345.6789,
  },
  {
    rank: 2,
    agent_id: "agent-002",
    agent_name: "Beta Agent",
    composite_score: 0.82,
    total_transactions: 300,
    total_volume_usdc: 8765.432,
  },
  {
    rank: 3,
    agent_id: "agent-003",
    agent_name: "Gamma Agent",
    composite_score: 0.71,
    total_transactions: 150,
    total_volume_usdc: 3210.99,
  },
];

const mockMultiBoardEntries: MultiLeaderboardEntry[] = [
  {
    rank: 1,
    agent_id: "agent-001",
    agent_name: "Alpha Agent",
    primary_score: 0.97,
    secondary_label: "Helpfulness",
    total_transactions: 500,
    helpfulness_score: 0.97,
    total_earned_usdc: 5000,
  },
  {
    rank: 2,
    agent_id: "agent-002",
    agent_name: "Beta Agent",
    primary_score: 0.85,
    secondary_label: "Helpfulness",
    total_transactions: 300,
    helpfulness_score: 0.85,
    total_earned_usdc: 3000,
  },
];

const mockReputationData = {
  agent_id: "agent-001",
  agent_name: "Alpha Agent",
  total_transactions: 500,
  successful_deliveries: 480,
  failed_deliveries: 20,
  verified_count: 450,
  verification_failures: 5,
  avg_response_ms: 150,
  total_volume_usdc: 12345.6789,
  composite_score: 0.95,
  last_calculated_at: "2025-02-01T00:00:00Z",
};

/* ── Setup ── */

describe("ReputationPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();

    vi.spyOn(useReputationModule, "useLeaderboard").mockReturnValue({
      data: { entries: mockLeaderboardEntries },
      isLoading: false,
    } as any);

    vi.spyOn(useReputationModule, "useReputation").mockReturnValue({
      data: undefined,
      isLoading: false,
    } as any);

    vi.spyOn(useAnalyticsModule, "useMultiLeaderboard").mockReturnValue({
      data: { board_type: "helpfulness", entries: mockMultiBoardEntries },
      isLoading: false,
    } as any);
  });

  it("renders the reputation page header", () => {
    renderWithProviders(<ReputationPage />);

    expect(screen.getByText("Reputation & Leaderboard")).toBeInTheDocument();
    expect(
      screen.getByText(
        "Agent performance scores, rankings, and multi-category leaderboards",
      ),
    ).toBeInTheDocument();
  });

  it("shows leaderboard with agent names and scores", () => {
    renderWithProviders(<ReputationPage />);

    expect(screen.getByText("Global Leaderboard")).toBeInTheDocument();
    // Agent names appear in both global and multi-leaderboard
    expect(screen.getAllByText("Alpha Agent").length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText("Beta Agent").length).toBeGreaterThanOrEqual(1);
  });

  it("shows multi-leaderboard sub-tabs", () => {
    renderWithProviders(<ReputationPage />);

    // "Most Helpful" appears in both the SubTabNav button and the section
    // heading for the active board type, so use getAllByText
    expect(screen.getAllByText("Most Helpful").length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText("Top Earners")).toBeInTheDocument();
    expect(screen.getByText("Top Contributors")).toBeInTheDocument();
    expect(screen.getByText("Category Leaders")).toBeInTheDocument();
  });

  it("shows loading state when leaderboard is loading", () => {
    vi.spyOn(useReputationModule, "useLeaderboard").mockReturnValue({
      data: undefined,
      isLoading: true,
    } as any);

    renderWithProviders(<ReputationPage />);

    // DataTable shows a Spinner with role="status" when isLoading = true
    const spinners = screen.getAllByRole("status");
    expect(spinners.length).toBeGreaterThanOrEqual(1);
  });

  it("shows empty leaderboard message when no entries", () => {
    vi.spyOn(useReputationModule, "useLeaderboard").mockReturnValue({
      data: { entries: [] },
      isLoading: false,
    } as any);

    renderWithProviders(<ReputationPage />);

    expect(screen.getByText("No reputation data yet")).toBeInTheDocument();
  });

  it("shows Top 10 Scores chart section", () => {
    renderWithProviders(<ReputationPage />);

    expect(screen.getByText("Top 10 Scores")).toBeInTheDocument();
  });

  it("renders rank medals for top 3 entries", () => {
    renderWithProviders(<ReputationPage />);

    // MedalBadge renders title attributes for top 3
    // Rank 1 = Gold, Rank 2 = Silver, Rank 3 = Bronze
    const goldBadges = screen.getAllByTitle("Gold");
    expect(goldBadges.length).toBeGreaterThanOrEqual(1);
    const silverBadges = screen.getAllByTitle("Silver");
    expect(silverBadges.length).toBeGreaterThanOrEqual(1);
    const bronzeBadges = screen.getAllByTitle("Bronze");
    expect(bronzeBadges.length).toBeGreaterThanOrEqual(1);
  });

  it("displays agent lookup section with input", () => {
    renderWithProviders(<ReputationPage />);

    expect(screen.getByText("Agent Lookup")).toBeInTheDocument();
    expect(
      screen.getByPlaceholderText("Enter agent ID to look up..."),
    ).toBeInTheDocument();
    expect(screen.getByText("Look Up")).toBeInTheDocument();
  });

  it("shows agent reputation detail when lookup triggered", async () => {
    // First render without lookup active
    vi.spyOn(useReputationModule, "useReputation").mockReturnValue({
      data: mockReputationData,
      isLoading: false,
    } as any);

    renderWithProviders(<ReputationPage />);

    // Type in an agent ID and press lookup
    const lookupInput = screen.getByPlaceholderText(
      "Enter agent ID to look up...",
    );
    fireEvent.change(lookupInput, { target: { value: "agent-001" } });

    const lookupBtn = screen.getByText("Look Up");
    fireEvent.click(lookupBtn);

    // After clicking, the component sets activeId, which enables useReputation
    // Since we mocked useReputation to return data, the detail card should show
    expect(await screen.findByText("Composite Score")).toBeInTheDocument();
  });

  it("switches multi-leaderboard tab on click", () => {
    const mockMultiLeaderboard = vi.fn().mockReturnValue({
      data: { board_type: "helpfulness", entries: mockMultiBoardEntries },
      isLoading: false,
    });
    vi.spyOn(useAnalyticsModule, "useMultiLeaderboard").mockImplementation(
      mockMultiLeaderboard,
    );

    renderWithProviders(<ReputationPage />);

    // Click on "Top Earners" tab
    const topEarnersTab = screen.getByText("Top Earners");
    fireEvent.click(topEarnersTab);

    // The hook should be called with 'earnings' board type
    expect(mockMultiLeaderboard).toHaveBeenCalledWith("earnings");
  });

  it("shows empty multi-leaderboard message when no data", () => {
    vi.spyOn(useAnalyticsModule, "useMultiLeaderboard").mockReturnValue({
      data: { board_type: "helpfulness", entries: [] },
      isLoading: false,
    } as any);

    renderWithProviders(<ReputationPage />);

    expect(screen.getByText("No leaderboard data yet")).toBeInTheDocument();
  });

  it("shows chart no-data message when leaderboard is empty", () => {
    vi.spyOn(useReputationModule, "useLeaderboard").mockReturnValue({
      data: { entries: [] },
      isLoading: false,
    } as any);

    renderWithProviders(<ReputationPage />);

    expect(screen.getByText("No data yet")).toBeInTheDocument();
  });
});
