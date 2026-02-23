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

/* -- Test Data ------------------------------------------------- */

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

/* -- Tests ------------------------------------------------- */

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

  /* ── NEW TESTS for increased coverage ── */

  it("renders FulfillmentBar with high rate (>= 0.7) showing green gradient", () => {
    vi.spyOn(useAnalyticsModule, "useTrending").mockReturnValue({
      data: {
        time_window_hours: 6,
        trends: [
          {
            query_pattern: "high-fulfillment query",
            category: "web_search",
            search_count: 100,
            unique_requesters: 10,
            velocity: 5.0,
            fulfillment_rate: 0.85,
            last_searched_at: new Date().toISOString(),
          },
        ],
      },
      isLoading: false,
      error: null,
    } as any);

    renderWithProviders(<AnalyticsPage />);

    expect(screen.getByText("85%")).toBeInTheDocument();
  });

  it("renders FulfillmentBar with medium rate (0.4-0.7) showing amber gradient", () => {
    vi.spyOn(useAnalyticsModule, "useTrending").mockReturnValue({
      data: {
        time_window_hours: 6,
        trends: [
          {
            query_pattern: "mid-fulfillment query",
            category: "web_search",
            search_count: 100,
            unique_requesters: 10,
            velocity: 5.0,
            fulfillment_rate: 0.55,
            last_searched_at: new Date().toISOString(),
          },
        ],
      },
      isLoading: false,
      error: null,
    } as any);

    renderWithProviders(<AnalyticsPage />);

    expect(screen.getByText("55%")).toBeInTheDocument();
  });

  it("renders FulfillmentBar with low rate (< 0.4) showing red gradient", () => {
    vi.spyOn(useAnalyticsModule, "useTrending").mockReturnValue({
      data: {
        time_window_hours: 6,
        trends: [
          {
            query_pattern: "low-fulfillment query",
            category: "web_search",
            search_count: 100,
            unique_requesters: 10,
            velocity: 5.0,
            fulfillment_rate: 0.2,
            last_searched_at: new Date().toISOString(),
          },
        ],
      },
      isLoading: false,
      error: null,
    } as any);

    renderWithProviders(<AnalyticsPage />);

    expect(screen.getByText("20%")).toBeInTheDocument();
  });

  it("renders trending query with null category as mdash", () => {
    renderWithProviders(<AnalyticsPage />);

    // machine learning pipeline has null category
    expect(screen.getByText("machine learning pipeline")).toBeInTheDocument();
    // Should render an mdash for null category - check it exists
    const mdashElements = document.querySelectorAll("span");
    const mdash = Array.from(mdashElements).find(
      (el) => el.textContent === "\u2014",
    );
    expect(mdash).toBeTruthy();
  });

  it("shows hot flame icon for trending query with velocity > 5", () => {
    renderWithProviders(<AnalyticsPage />);

    // The first trend has velocity 8.5 (> 5) - should show flame icon
    // 8.5/hr should be rendered with hot styling
    expect(screen.getByText("8.5/hr")).toBeInTheDocument();
  });

  it("renders search count with locale formatting", () => {
    renderWithProviders(<AnalyticsPage />);

    // search_count: 150 should be rendered with toLocaleString()
    expect(screen.getByText("150")).toBeInTheDocument();
    expect(screen.getByText("90")).toBeInTheDocument();
    expect(screen.getByText("60")).toBeInTheDocument();
  });

  it("shows loading skeleton for gaps panel", async () => {
    vi.spyOn(useAnalyticsModule, "useDemandGaps").mockReturnValue({
      data: undefined,
      isLoading: true,
      error: null,
    } as any);

    renderWithProviders(<AnalyticsPage />);

    fireEvent.click(screen.getByText("Demand Gaps"));

    await waitFor(() => {
      // SkeletonCard renders a grid of skeleton cards with shimmer animation
      const skeletonCards = document.querySelectorAll(".rounded-2xl.border");
      expect(skeletonCards.length).toBeGreaterThan(0);
    });
  });

  it("shows loading skeleton for opportunities panel", async () => {
    vi.spyOn(useAnalyticsModule, "useOpportunities").mockReturnValue({
      data: undefined,
      isLoading: true,
      error: null,
    } as any);

    renderWithProviders(<AnalyticsPage />);

    fireEvent.click(screen.getByText("Opportunities"));

    await waitFor(() => {
      const skeletonCards = document.querySelectorAll(".rounded-2xl.border");
      expect(skeletonCards.length).toBeGreaterThan(0);
    });
  });

  it("renders gap card with category badge", async () => {
    renderWithProviders(<AnalyticsPage />);

    fireEvent.click(screen.getByText("Demand Gaps"));

    await waitFor(() => {
      expect(screen.getByText("quantum computing basics")).toBeInTheDocument();
    });
    // Category badge for document_summary
    expect(screen.getByText("document_summary")).toBeInTheDocument();
  });

  it("renders gap card with avg_max_price", async () => {
    renderWithProviders(<AnalyticsPage />);

    fireEvent.click(screen.getByText("Demand Gaps"));

    await waitFor(() => {
      // quantum computing basics has avg_max_price: 0.005
      expect(screen.getByText("$0.0050")).toBeInTheDocument();
    });
    // "Avg budget" label
    expect(screen.getByText("Avg budget")).toBeInTheDocument();
  });

  it("renders gap card without avg_max_price (null) - no budget section", async () => {
    vi.spyOn(useAnalyticsModule, "useDemandGaps").mockReturnValue({
      data: {
        gaps: [
          {
            query_pattern: "no-budget gap",
            category: null,
            search_count: 20,
            unique_requesters: 3,
            avg_max_price: null,
            fulfillment_rate: 0.0,
            first_searched_at: null,
          },
        ],
      },
      isLoading: false,
      error: null,
    } as any);

    renderWithProviders(<AnalyticsPage />);
    fireEvent.click(screen.getByText("Demand Gaps"));

    await waitFor(() => {
      expect(screen.getByText("no-budget gap")).toBeInTheDocument();
    });
    // Should NOT show "Avg budget" text
    expect(screen.queryByText("Avg budget")).not.toBeInTheDocument();
  });

  it("renders gap card without category (null) - no category badge", async () => {
    vi.spyOn(useAnalyticsModule, "useDemandGaps").mockReturnValue({
      data: {
        gaps: [
          {
            query_pattern: "no-category gap",
            category: null,
            search_count: 15,
            unique_requesters: 2,
            avg_max_price: 0.01,
            fulfillment_rate: 0.0,
            first_searched_at: new Date().toISOString(),
          },
        ],
      },
      isLoading: false,
      error: null,
    } as any);

    renderWithProviders(<AnalyticsPage />);
    fireEvent.click(screen.getByText("Demand Gaps"));

    await waitFor(() => {
      expect(screen.getByText("no-category gap")).toBeInTheDocument();
    });
  });

  it("renders gap card without first_searched_at (null) - no date footer", async () => {
    vi.spyOn(useAnalyticsModule, "useDemandGaps").mockReturnValue({
      data: {
        gaps: [
          {
            query_pattern: "no-date gap",
            category: "web_search",
            search_count: 10,
            unique_requesters: 1,
            avg_max_price: null,
            fulfillment_rate: 0.0,
            first_searched_at: null,
          },
        ],
      },
      isLoading: false,
      error: null,
    } as any);

    renderWithProviders(<AnalyticsPage />);
    fireEvent.click(screen.getByText("Demand Gaps"));

    await waitFor(() => {
      expect(screen.getByText("no-date gap")).toBeInTheDocument();
    });
    // Should NOT show "First searched" text
    expect(screen.queryByText(/First searched/)).not.toBeInTheDocument();
  });

  it("renders gap card with first_searched_at date footer", async () => {
    renderWithProviders(<AnalyticsPage />);
    fireEvent.click(screen.getByText("Demand Gaps"));

    await waitFor(() => {
      expect(screen.getByText("quantum computing basics")).toBeInTheDocument();
    });
    // Should show "First searched" with a date
    const firstSearchedElements = screen.getAllByText(/First searched/);
    expect(firstSearchedElements.length).toBeGreaterThan(0);
  });

  it("renders gap card search count and unique requesters", async () => {
    renderWithProviders(<AnalyticsPage />);
    fireEvent.click(screen.getByText("Demand Gaps"));

    await waitFor(() => {
      expect(screen.getByText("45")).toBeInTheDocument();
    });
    expect(screen.getByText("10")).toBeInTheDocument(); // unique_requesters for first gap
    // "Searches" appears multiple times (once per gap card)
    const searchLabels = screen.getAllByText("Searches");
    expect(searchLabels.length).toBeGreaterThan(0);
    const requesterLabels = screen.getAllByText("Requesters");
    expect(requesterLabels.length).toBeGreaterThan(0);
  });

  it("renders opportunity card with high velocity trend (>3) showing up arrow", async () => {
    renderWithProviders(<AnalyticsPage />);
    fireEvent.click(screen.getByText("Opportunities"));

    await waitFor(() => {
      expect(screen.getByText("API integration guide")).toBeInTheDocument();
    });
    // opp-001 has velocity 5.2 (> 3) - should show ArrowUpRight
    expect(screen.getByText("5.2/hr")).toBeInTheDocument();
  });

  it("renders opportunity card with low velocity trend (<=3) showing down arrow", async () => {
    renderWithProviders(<AnalyticsPage />);
    fireEvent.click(screen.getByText("Opportunities"));

    await waitFor(() => {
      expect(screen.getByText("data pipeline architecture")).toBeInTheDocument();
    });
    // opp-002 has velocity 2.1 (<= 3) - should show ArrowDownRight
    expect(screen.getByText("2.1/hr")).toBeInTheDocument();
  });

  it("renders opportunity card with estimated revenue", async () => {
    renderWithProviders(<AnalyticsPage />);
    fireEvent.click(screen.getByText("Opportunities"));

    await waitFor(() => {
      // opp-001: estimated_revenue_usdc: 0.025
      expect(screen.getByText("$0.0250")).toBeInTheDocument();
    });
    // opp-002: estimated_revenue_usdc: 0.018
    expect(screen.getByText("$0.0180")).toBeInTheDocument();
  });

  it("renders opportunity card with competing listings count", async () => {
    renderWithProviders(<AnalyticsPage />);
    fireEvent.click(screen.getByText("Opportunities"));

    await waitFor(() => {
      expect(screen.getByText("API integration guide")).toBeInTheDocument();
    });
    // Competing text and values
    expect(screen.getAllByText("Competing").length).toBeGreaterThan(0);
  });

  it("renders opportunity card with category badge", async () => {
    renderWithProviders(<AnalyticsPage />);
    fireEvent.click(screen.getByText("Opportunities"));

    await waitFor(() => {
      expect(screen.getByText("api_response")).toBeInTheDocument();
    });
    expect(screen.getByText("computation")).toBeInTheDocument();
  });

  it("renders opportunity card without category (null) - no category badge", async () => {
    vi.spyOn(useAnalyticsModule, "useOpportunities").mockReturnValue({
      data: {
        opportunities: [
          {
            id: "opp-nc",
            query_pattern: "no-category opp",
            category: null,
            estimated_revenue_usdc: 0.01,
            search_velocity: 1.0,
            competing_listings: 0,
            urgency_score: 0.5,
            created_at: new Date().toISOString(),
          },
        ],
      },
      isLoading: false,
      error: null,
    } as any);

    renderWithProviders(<AnalyticsPage />);
    fireEvent.click(screen.getByText("Opportunities"));

    await waitFor(() => {
      expect(screen.getByText("no-category opp")).toBeInTheDocument();
    });
  });

  it("renders Est. Revenue label in opportunity cards", async () => {
    renderWithProviders(<AnalyticsPage />);
    fireEvent.click(screen.getByText("Opportunities"));

    await waitFor(() => {
      const labels = screen.getAllByText("Est. Revenue");
      expect(labels.length).toBeGreaterThan(0);
    });
  });

  it("renders Velocity label in opportunity cards", async () => {
    renderWithProviders(<AnalyticsPage />);
    fireEvent.click(screen.getByText("Opportunities"));

    await waitFor(() => {
      const labels = screen.getAllByText("Velocity");
      expect(labels.length).toBeGreaterThan(0);
    });
  });

  it("renders Gap badge on demand gap cards", async () => {
    renderWithProviders(<AnalyticsPage />);
    fireEvent.click(screen.getByText("Demand Gaps"));

    await waitFor(() => {
      const gapBadges = screen.getAllByText("Gap");
      expect(gapBadges.length).toBe(2);
    });
  });

  it("sorts trending data by velocity descending", () => {
    renderWithProviders(<AnalyticsPage />);

    // All three rows should be present, sorted by velocity desc
    const rows = screen.getAllByText(/\/hr/);
    expect(rows[0].textContent).toContain("8.5");
    expect(rows[1].textContent).toContain("3.2");
    expect(rows[2].textContent).toContain("1.8");
  });

  it("handles trending data being undefined gracefully", () => {
    vi.spyOn(useAnalyticsModule, "useTrending").mockReturnValue({
      data: undefined,
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

  it("handles gaps data being undefined when not loading", async () => {
    vi.spyOn(useAnalyticsModule, "useDemandGaps").mockReturnValue({
      data: undefined,
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

  it("handles opportunities data being undefined when not loading", async () => {
    vi.spyOn(useAnalyticsModule, "useOpportunities").mockReturnValue({
      data: undefined,
      isLoading: false,
      error: null,
    } as any);

    renderWithProviders(<AnalyticsPage />);
    fireEvent.click(screen.getByText("Opportunities"));

    await waitFor(() => {
      expect(
        screen.getByText("No opportunities available yet. They are generated from demand gaps."),
      ).toBeInTheDocument();
    });
  });

  it("renders FulfillmentBar at exact boundary rates (0.4 and 0.7)", () => {
    vi.spyOn(useAnalyticsModule, "useTrending").mockReturnValue({
      data: {
        time_window_hours: 6,
        trends: [
          {
            query_pattern: "boundary-low query",
            category: "web_search",
            search_count: 50,
            unique_requesters: 5,
            velocity: 2.0,
            fulfillment_rate: 0.4,
            last_searched_at: new Date().toISOString(),
          },
          {
            query_pattern: "boundary-high query",
            category: "web_search",
            search_count: 80,
            unique_requesters: 8,
            velocity: 6.0,
            fulfillment_rate: 0.7,
            last_searched_at: new Date().toISOString(),
          },
        ],
      },
      isLoading: false,
      error: null,
    } as any);

    renderWithProviders(<AnalyticsPage />);

    // 0.4 -> 40%, 0.7 -> 70%
    expect(screen.getByText("40%")).toBeInTheDocument();
    expect(screen.getByText("70%")).toBeInTheDocument();
  });

  it("renders FulfillmentBar at zero rate", () => {
    vi.spyOn(useAnalyticsModule, "useTrending").mockReturnValue({
      data: {
        time_window_hours: 6,
        trends: [
          {
            query_pattern: "zero-rate query",
            category: "web_search",
            search_count: 50,
            unique_requesters: 5,
            velocity: 2.0,
            fulfillment_rate: 0.0,
            last_searched_at: new Date().toISOString(),
          },
        ],
      },
      isLoading: false,
      error: null,
    } as any);

    renderWithProviders(<AnalyticsPage />);

    expect(screen.getByText("0%")).toBeInTheDocument();
  });

  it("renders FulfillmentBar at 100% rate", () => {
    vi.spyOn(useAnalyticsModule, "useTrending").mockReturnValue({
      data: {
        time_window_hours: 6,
        trends: [
          {
            query_pattern: "full-rate query",
            category: "web_search",
            search_count: 50,
            unique_requesters: 5,
            velocity: 2.0,
            fulfillment_rate: 1.0,
            last_searched_at: new Date().toISOString(),
          },
        ],
      },
      isLoading: false,
      error: null,
    } as any);

    renderWithProviders(<AnalyticsPage />);

    expect(screen.getByText("100%")).toBeInTheDocument();
  });
});
