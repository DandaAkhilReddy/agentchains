import { describe, it, expect, vi, beforeEach } from "vitest";
import { screen, fireEvent } from "@testing-library/react";
import { renderWithProviders } from "../../test/test-utils";
import TechnologyPage from "../TechnologyPage";
import * as useSystemMetricsModule from "../../hooks/useSystemMetrics";

// Mock the useSystemMetrics hook (used by ArchitectureOverview)
vi.mock("../../hooks/useSystemMetrics");

// Mock the heavy child visualization components to keep tests fast and focused
vi.mock("../../components/technology/SmartRouterViz", () => ({
  default: () => <div data-testid="smart-router-viz">SmartRouterViz</div>,
}));
vi.mock("../../components/technology/AutoMatchViz", () => ({
  default: () => <div data-testid="auto-match-viz">AutoMatchViz</div>,
}));
vi.mock("../../components/technology/CDNTiersViz", () => ({
  default: () => <div data-testid="cdn-tiers-viz">CDNTiersViz</div>,
}));
vi.mock("../../components/technology/ExpressDeliveryViz", () => ({
  default: () => <div data-testid="express-delivery-viz">ExpressDeliveryViz</div>,
}));
vi.mock("../../components/technology/ZKPVerificationViz", () => ({
  default: () => <div data-testid="zkp-verification-viz">ZKPVerificationViz</div>,
}));
vi.mock("../../components/technology/TokenEconomyViz", () => ({
  default: () => <div data-testid="token-economy-viz">TokenEconomyViz</div>,
}));

describe("TechnologyPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();

    // Provide a default mock for useSystemMetrics so ArchitectureOverview renders
    vi.spyOn(useSystemMetricsModule, "useSystemMetrics").mockReturnValue({
      data: {
        health: {
          agents_count: 10,
          listings_count: 25,
          transactions_count: 100,
          cache_stats: { listings: 25, content: 15, agents: 10 },
        },
        cdn: {
          overview: {
            total_requests: 1000,
            tier1_hits: 700,
            tier2_hits: 200,
            tier3_hits: 80,
            total_misses: 20,
          },
          hot_cache: { tier: "T1", entries: 150, bytes_used: 5000, bytes_max: 10000, utilization_pct: 50, hits: 700, misses: 100, promotions: 10, evictions: 5, hit_rate: 87.5 },
          warm_cache: { hits: 200, misses: 50, size: 80, maxsize: 200, hit_rate: 80 },
        },
      },
      isLoading: false,
      error: null,
      refetch: vi.fn(),
    } as any);
  });

  it("renders the page title", () => {
    renderWithProviders(<TechnologyPage />);
    expect(screen.getByText("System Design")).toBeInTheDocument();
  });

  it("renders the page subtitle", () => {
    renderWithProviders(<TechnologyPage />);
    expect(
      screen.getByText("Architecture, algorithms, and competitive advantages"),
    ).toBeInTheDocument();
  });

  it("shows all technology tab labels", () => {
    renderWithProviders(<TechnologyPage />);

    expect(screen.getByText("Architecture")).toBeInTheDocument();
    // "Smart Router" also appears in the ArchitectureOverview node card
    expect(screen.getAllByText("Smart Router").length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText("Auto-Match")).toBeInTheDocument();
    expect(screen.getByText("CDN Tiers")).toBeInTheDocument();
    expect(screen.getByText("Express")).toBeInTheDocument();
    expect(screen.getByText("ZKP")).toBeInTheDocument();
    expect(screen.getAllByText("USD Billing").length).toBeGreaterThanOrEqual(1);
  });

  it("renders ArchitectureOverview by default (overview tab)", () => {
    const { container } = renderWithProviders(<TechnologyPage />);

    // The Architecture tab should be active by default (overview tab)
    // ArchitectureOverview is NOT mocked, so it renders its real content
    // The mocked viz components should NOT be visible on the overview tab
    expect(screen.queryByTestId("smart-router-viz")).not.toBeInTheDocument();
    expect(screen.queryByTestId("auto-match-viz")).not.toBeInTheDocument();

    // The main container should exist
    expect(container.firstElementChild).toBeTruthy();
  });

  it("switches to Smart Router tab on click", () => {
    renderWithProviders(<TechnologyPage />);

    // "Smart Router" appears in both the tab and ArchitectureOverview node card;
    // the tab button is rendered by SubTabNav
    const smartRouterElements = screen.getAllByText("Smart Router");
    // Click the tab button (SubTabNav renders <button> elements)
    const tabButton = smartRouterElements.find(
      (el) => el.closest("button")?.className?.includes("rounded-lg"),
    );
    fireEvent.click(tabButton ?? smartRouterElements[0]);
    expect(screen.getByTestId("smart-router-viz")).toBeInTheDocument();
  });

  it("switches to each tab correctly", () => {
    renderWithProviders(<TechnologyPage />);

    // Auto-Match
    fireEvent.click(screen.getByText("Auto-Match"));
    expect(screen.getByTestId("auto-match-viz")).toBeInTheDocument();

    // CDN Tiers
    fireEvent.click(screen.getByText("CDN Tiers"));
    expect(screen.getByTestId("cdn-tiers-viz")).toBeInTheDocument();

    // Express
    fireEvent.click(screen.getByText("Express"));
    expect(screen.getByTestId("express-delivery-viz")).toBeInTheDocument();

    // ZKP
    fireEvent.click(screen.getByText("ZKP"));
    expect(screen.getByTestId("zkp-verification-viz")).toBeInTheDocument();

    // USD Billing
    fireEvent.click(screen.getByText("USD Billing"));
    expect(screen.getByTestId("token-economy-viz")).toBeInTheDocument();
  });

  it("hides previous tab content when switching tabs", () => {
    renderWithProviders(<TechnologyPage />);

    // Switch to Smart Router — "Smart Router" may appear in both tab and
    // ArchitectureOverview node card; find the SubTabNav button
    const srElements = screen.getAllByText("Smart Router");
    const srTab = srElements.find(
      (el) => el.closest("button")?.className?.includes("rounded-lg"),
    );
    fireEvent.click(srTab ?? srElements[0]);
    expect(screen.getByTestId("smart-router-viz")).toBeInTheDocument();

    // Switch to CDN Tiers — Smart Router viz should disappear
    fireEvent.click(screen.getByText("CDN Tiers"));
    expect(screen.queryByTestId("smart-router-viz")).not.toBeInTheDocument();
    expect(screen.getByTestId("cdn-tiers-viz")).toBeInTheDocument();
  });

  it("applies fade-in animation class to the main container", () => {
    const { container } = renderWithProviders(<TechnologyPage />);

    const mainDiv = container.firstElementChild;
    expect(mainDiv).toBeTruthy();
    expect(mainDiv?.className).toContain("animate-fade-in");
  });
});
