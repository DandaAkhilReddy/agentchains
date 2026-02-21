import { describe, it, expect, vi, beforeEach } from "vitest";
import { screen, fireEvent, waitFor } from "@testing-library/react";
import { renderWithProviders } from "../../test/test-utils";
import AnalyticsPage from "../AnalyticsPage";
import * as useAnalyticsModule from "../../hooks/useAnalytics";
import type {
  TrendingResponse,
  DemandGapsResponse,
  OpportunitiesResponse,
} from "../../types/api";

// Mock the analytics hooks
vi.mock("../../hooks/useAnalytics");

/* ── Test Data ──────────────────────────────────────────── */

const mockTrendingData: TrendingResponse = {
  time_window_hours: 6,
  trends: [
    {
      query_pattern: "latest AI research papers",
      category: "web_search",
      search_count: 150,
      unique_requesters: 12,
      velocity: 8.5,
      fulfillment_rate: 0.75,
      last_searched_at: new Date().toISOString(),
    },
    {
      query_pattern: "react performance optimization",
      category: "code_analysis",
      search_count: 90,
      unique_requesters: 8,
      velocity: 3.2,
      fulfillment_rate: 0.45,
      last_searched_at: new Date().toISOString(),
    },
    {
      query_pattern: "machine learning pipeline",
      category: null,
      search_count: 60,
      unique_requesters: 5,
      velocity: 1.8,
      fulfillment_rate: 0.9,
      last_searched_at: new Date().toISOString(),
    },
  ],
};

const mockGapsData: DemandGapsResponse = {
  gaps: [
    {
      query_pattern: "quantum computing basics",
      category: "document_summary",
      search_count: 45,
      unique_requesters: 10,
      avg_max_price: 0.005,
      fulfillment_rate: 0.1,
      first_searched_at: new Date(Date.now() - 86400000).toISOString(),
    },
    {
      query_pattern: "blockchain smart contracts",
      category: "code_analysis",
      search_count: 30,
      unique_requesters: 7,
      avg_max_price: null,
      fulfillment_rate: 0.0,
      first_searched_at: new Date(Date.now() - 172800000).toISOString(),
    },
  ],
};

const mockOpportunitiesData: OpportunitiesResponse = {
  opportunities: [
    {
      id: "opp-001",
      query_pattern: "API integration guide",
      category: "api_response",
      estimated_revenue_usdc: 0.025,
      search_velocity: 5.2,
      competing_listings: 2,
      urgency_score: 0.85,
      created_at: new Date().toISOString(),
    },
    {
      id: "opp-002",
      query_pattern: "data pipeline architecture",
      category: "computation",
      estimated_revenue_usdc: 0.018,
      search_velocity: 2.1,
      competing_listings: 0,
      urgency_score: 0.65,
      created_at: new Date().toISOString(),
    },
  ],
};

/* ── Tests ──────────────────────────────────────────────── */

describe("AnalyticsPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();

    // Default mocks for all analytics hooks
    vi.spyOn(useAnalyticsModule, "useTrending").mockReturnValue({
      data: mockTrendingData,
      isLoading: false,
      error: null,
    } as any);
    vi.spyOn(useAnalyticsModule, "useDemandGaps").mockReturnValue({
      data: mockGapsData,
      isLoading: false,
      error: null,
    } as any);
    vi.spyOn(useAnalyticsModule, "useOpportunities").mockReturnValue({
      data: mockOpportunitiesData,
      isLoading: false,
      error: null,
    } as any);
  });

  it("renders analytics dashboard with header", () => {
    renderWithProviders(<AnalyticsPage />);

    expect(screen.getByText("Demand Intelligence")).toBeInTheDocument();
    expect(screen.getByText("What agents are searching for right now")).toBeInTheDocument();
  });

  it("shows trending tab as default active tab", () => {
    renderWithProviders(<AnalyticsPage />);

    // Trending data should be visible by default
    expect(screen.getByText("latest AI research papers")).toBeInTheDocument();
    expect(screen.getByText("react performance optimization")).toBeInTheDocument();
  });

  it("renders all sub-tab navigation options", () => {
    renderWithProviders(<AnalyticsPage />);

    expect(screen.getByText("Trending")).toBeInTheDocument();
    expect(screen.getByText("Demand Gaps")).toBeInTheDocument();
    expect(screen.getByText("Opportunities")).toBeInTheDocument();
  });

  it("shows trending table with query data and velocity", () => {
    renderWithProviders(<AnalyticsPage />);

    // Check table headers
    expect(screen.getByText("Query")).toBeInTheDocument();
    expect(screen.getByText("Searches")).toBeInTheDocument();
    expect(screen.getByText("Velocity")).toBeInTheDocument();
    expect(screen.getByText("Fulfillment")).toBeInTheDocument();

    // Check velocity values (sorted by velocity desc: 8.5, 3.2, 1.8)
    expect(screen.getByText("8.5/hr")).toBeInTheDocument();
    expect(screen.getByText("3.2/hr")).toBeInTheDocument();
    expect(screen.getByText("1.8/hr")).toBeInTheDocument();
  });

  it("shows loading spinner when trending data is loading", () => {
    vi.spyOn(useAnalyticsModule, "useTrending").mockReturnValue({
      data: undefined,
      isLoading: true,
      error: null,
    } as any);

    renderWithProviders(<AnalyticsPage />);

    // DataTable shows a Spinner with role="status" when loading
    const spinner = screen.getByRole("status", { name: "Loading" });
    expect(spinner).toBeInTheDocument();
  });

  it("shows empty state for trending when no data", () => {
    vi.spyOn(useAnalyticsModule, "useTrending").mockReturnValue({
      data: { time_window_hours: 6, trends: [] },
      isLoading: false,
      error: null,
    } as any);

    renderWithProviders(<AnalyticsPage />);

    expect(
      screen.getByText(
        "No trending queries yet. Searches will appear here as agents use the marketplace.",
      ),
    ).toBeInTheDocument();
  });

  it("switches to demand gaps tab and shows gap cards", async () => {
    renderWithProviders(<AnalyticsPage />);

    // Click on Demand Gaps tab
    fireEvent.click(screen.getByText("Demand Gaps"));

    await waitFor(() => {
      expect(screen.getByText("quantum computing basics")).toBeInTheDocument();
      expect(screen.getByText("blockchain smart contracts")).toBeInTheDocument();
    });
  });

  it("shows empty state for gaps when no gaps detected", async () => {
    vi.spyOn(useAnalyticsModule, "useDemandGaps").mockReturnValue({
      data: { gaps: [] },
      isLoading: false,
      error: null,
    } as any);

    renderWithProviders(<AnalyticsPage />);

    fireEvent.click(screen.getByText("Demand Gaps"));

    await waitFor(() => {
      expect(
        screen.getByText("No demand gaps detected. All buyer searches are being fulfilled."),
      ).toBeInTheDocument();
    });
  });

  it("switches to opportunities tab and shows opportunity cards", async () => {
    renderWithProviders(<AnalyticsPage />);

    fireEvent.click(screen.getByText("Opportunities"));

    await waitFor(() => {
      expect(screen.getByText("API integration guide")).toBeInTheDocument();
      expect(screen.getByText("data pipeline architecture")).toBeInTheDocument();
    });
  });

  it("shows empty state for opportunities when none available", async () => {
    vi.spyOn(useAnalyticsModule, "useOpportunities").mockReturnValue({
      data: { opportunities: [] },
      isLoading: false,
      error: null,
    } as any);

    renderWithProviders(<AnalyticsPage />);

    fireEvent.click(screen.getByText("Opportunities"));

    await waitFor(() => {
      expect(
        screen.getByText(
          "No opportunities available yet. They are generated from demand gaps.",
        ),
      ).toBeInTheDocument();
    });
  });
});
