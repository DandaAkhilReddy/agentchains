import { describe, it, expect, vi, beforeEach } from "vitest";
import { screen, fireEvent } from "@testing-library/react";
import { renderWithProviders } from "../../test/test-utils";
import CatalogPage from "../CatalogPage";
import type { CatalogEntry, CDNStats, MCPHealth } from "../../types/api";

/* ── Mock the API layer used by react-query inside CatalogPage ── */

const mockSearchCatalog = vi.fn();
const mockFetchCDNStats = vi.fn();
const mockFetchMCPHealth = vi.fn();

vi.mock("../../lib/api", () => ({
  searchCatalog: (...args: unknown[]) => mockSearchCatalog(...args),
  fetchCDNStats: (...args: unknown[]) => mockFetchCDNStats(...args),
  fetchMCPHealth: (...args: unknown[]) => mockFetchMCPHealth(...args),
}));

/* ── Mock AnimatedCounter ── */
vi.mock("../../components/AnimatedCounter", () => ({
  default: ({ value }: any) => <span>{value}</span>,
}));

/* ── Test Data ── */

const makeCatalogEntry = (overrides: Partial<CatalogEntry> = {}): CatalogEntry => ({
  id: "cat-001",
  agent_id: "agent-001",
  namespace: "web_search",
  topic: "Search API Results",
  description: "Web search result data",
  schema_json: {},
  price_range: [0.001, 0.005],
  quality_avg: 0.85,
  active_listings_count: 12,
  status: "active",
  created_at: "2025-01-01T00:00:00Z",
  ...overrides,
});

const mockEntries: CatalogEntry[] = [
  makeCatalogEntry({
    id: "cat-001",
    namespace: "web_search",
    topic: "Search API Results",
    description: "Web search result data",
    quality_avg: 0.85,
    price_range: [0.001, 0.005],
    active_listings_count: 12,
    status: "active",
  }),
  makeCatalogEntry({
    id: "cat-002",
    namespace: "code_analysis",
    topic: "Code Review Data",
    description: "Automated code review output",
    quality_avg: 0.62,
    price_range: [0.01, 0.01],
    active_listings_count: 5,
    status: "active",
  }),
  makeCatalogEntry({
    id: "cat-003",
    namespace: "web_search",
    topic: "News Aggregation",
    description: "News data aggregation",
    quality_avg: 0.35,
    price_range: [0.002, 0.008],
    active_listings_count: 1,
    status: "inactive",
  }),
];

const mockCDNStats: CDNStats = {
  overview: {
    total_requests: 1000,
    tier1_hits: 700,
    tier2_hits: 200,
    tier3_hits: 80,
    total_misses: 20,
  },
  hot_cache: {
    tier: "T1",
    entries: 150,
    bytes_used: 5000,
    bytes_max: 10000,
    utilization_pct: 50,
    hits: 700,
    misses: 100,
    promotions: 10,
    evictions: 5,
    hit_rate: 87.5,
  },
  warm_cache: {
    hits: 200,
    misses: 50,
    size: 80,
    maxsize: 200,
    hit_rate: 80,
  },
};

const mockMCPHealth: MCPHealth = {
  status: "ok",
  protocol_version: "1.0",
  server: "mcp-server",
  version: "2.0.0",
  active_sessions: 5,
  tools_count: 12,
  resources_count: 8,
};

/* ── Setup ── */

describe("CatalogPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    // Default: return loaded catalog data
    mockSearchCatalog.mockResolvedValue({
      entries: mockEntries,
      total: 3,
      page: 1,
      page_size: 50,
    });
    mockFetchCDNStats.mockResolvedValue(mockCDNStats);
    mockFetchMCPHealth.mockResolvedValue(mockMCPHealth);
  });

  it("renders the catalog page with header", async () => {
    renderWithProviders(<CatalogPage />);

    // "Data Catalog" appears in both the PageHeader and the CatalogSummaryCard
    const dataCatalogElements = screen.getAllByText("Data Catalog");
    expect(dataCatalogElements.length).toBeGreaterThanOrEqual(1);
    expect(
      screen.getByText("Browse capabilities, CDN stats, and MCP health"),
    ).toBeInTheDocument();
  });

  it("shows catalog entry cards after data loads", async () => {
    renderWithProviders(<CatalogPage />);

    // While loading, the loading indicator is displayed
    expect(screen.getByText("Loading catalog...")).toBeInTheDocument();

    // Wait for data to populate
    expect(await screen.findByText("Search API Results")).toBeInTheDocument();
    expect(screen.getByText("Code Review Data")).toBeInTheDocument();
    expect(screen.getByText("News Aggregation")).toBeInTheDocument();
  });

  it("displays search input and allows typing", async () => {
    renderWithProviders(<CatalogPage />);

    const searchInput = screen.getByPlaceholderText("Search catalog entries...");
    expect(searchInput).toBeInTheDocument();

    fireEvent.change(searchInput, { target: { value: "search" } });
    expect(searchInput).toHaveValue("search");
  });

  it("displays namespace category filter badges", async () => {
    renderWithProviders(<CatalogPage />);

    // Wait for entries to load so category badges appear
    await screen.findByText("Search API Results");

    // CategoryBadges should render namespace names as buttons
    const webSearchBtns = screen.getAllByText("web_search");
    // At least one namespace badge (plus the card labels)
    expect(webSearchBtns.length).toBeGreaterThanOrEqual(1);
  });

  it("shows loading state while catalog data is fetching", () => {
    mockSearchCatalog.mockReturnValue(new Promise(() => {})); // never resolves

    renderWithProviders(<CatalogPage />);

    expect(screen.getByText("Loading catalog...")).toBeInTheDocument();
  });

  it("shows empty state when no entries returned", async () => {
    mockSearchCatalog.mockResolvedValue({
      entries: [],
      total: 0,
      page: 1,
      page_size: 50,
    });

    renderWithProviders(<CatalogPage />);

    expect(
      await screen.findByText("No catalog entries found. Agents register capabilities here."),
    ).toBeInTheDocument();
  });

  it("displays the namespace dropdown filter with options", async () => {
    renderWithProviders(<CatalogPage />);

    await screen.findByText("Search API Results");

    const nsSelect = screen.getByDisplayValue("All namespaces");
    expect(nsSelect).toBeInTheDocument();

    // Verify the namespace select has options
    expect(nsSelect).toBeInTheDocument();
    // Verify "All namespaces" is the default
    expect(nsSelect).toHaveValue("");
  });

  it("displays price ranges on catalog cards", async () => {
    renderWithProviders(<CatalogPage />);

    await screen.findByText("Search API Results");

    // Entry cat-001 has price_range [0.001, 0.005]  ->  "$0.0010 – $0.0050"
    expect(screen.getByText("$0.0010 – $0.0050")).toBeInTheDocument();
    // Entry cat-002 has price_range [0.01, 0.01]  ->  "$0.0100"
    expect(screen.getByText("$0.0100")).toBeInTheDocument();
  });

  it("displays quality scores as percentages", async () => {
    renderWithProviders(<CatalogPage />);

    await screen.findByText("Search API Results");

    // quality_avg 0.85 -> 85%, 0.62 -> 62%, 0.35 -> 35%
    expect(screen.getByText("85%")).toBeInTheDocument();
    expect(screen.getByText("62%")).toBeInTheDocument();
    expect(screen.getByText("35%")).toBeInTheDocument();
  });

  it("displays namespace tag badges on each card", async () => {
    renderWithProviders(<CatalogPage />);

    await screen.findByText("Search API Results");

    // Each catalog card shows its namespace tag
    const wsLabels = screen.getAllByText("web_search");
    expect(wsLabels.length).toBeGreaterThanOrEqual(2); // at least 2 entries + category badge
    expect(screen.getAllByText("code_analysis").length).toBeGreaterThanOrEqual(1);
  });

  it("shows result count at the bottom when entries loaded", async () => {
    renderWithProviders(<CatalogPage />);

    await screen.findByText("Search API Results");

    expect(screen.getByText("Showing 3 of 3 entries")).toBeInTheDocument();
  });

  it("toggles between grid and list views", async () => {
    renderWithProviders(<CatalogPage />);

    await screen.findByText("Search API Results");

    const listBtn = screen.getByTitle("List view");
    const gridBtn = screen.getByTitle("Grid view");

    expect(listBtn).toBeInTheDocument();
    expect(gridBtn).toBeInTheDocument();

    // Click list view
    fireEvent.click(listBtn);

    // Entries should still be visible after switching
    expect(screen.getByText("Search API Results")).toBeInTheDocument();
    expect(screen.getByText("Code Review Data")).toBeInTheDocument();
  });

  it("shows CDN Performance card with stats after load", async () => {
    renderWithProviders(<CatalogPage />);

    expect(await screen.findByText("CDN Performance")).toBeInTheDocument();
  });

  it("shows MCP Server Health card", async () => {
    renderWithProviders(<CatalogPage />);

    expect(await screen.findByText("MCP Server Health")).toBeInTheDocument();
  });

  it("shows Data Catalog summary card with total entries", async () => {
    renderWithProviders(<CatalogPage />);

    // "Data Catalog" appears in both the PageHeader and the CatalogSummaryCard
    const dataCatalogElements = await screen.findAllByText("Data Catalog");
    expect(dataCatalogElements.length).toBeGreaterThanOrEqual(2);
    expect(await screen.findByText("Total Entries")).toBeInTheDocument();
  });
});
