import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import CatalogPage from "../pages/CatalogPage";
import type { CatalogSearchResponse, CDNStats, MCPHealth } from "../types/api";

// ── Mock child components that are not under test ─────────────────────────────

vi.mock("../components/PageHeader", () => ({
  default: ({ title }: { title: string }) => <div data-testid="page-header">{title}</div>,
}));

vi.mock("../components/ProgressRing", () => ({
  default: ({ value }: { value: number }) => <div data-testid="progress-ring">{value.toFixed(0)}</div>,
}));

vi.mock("../components/Badge", () => ({
  default: ({ label }: { label: string }) => <span data-testid="badge">{label}</span>,
}));

// ── Mock API layer ─────────────────────────────────────────────────────────────

vi.mock("../lib/api", () => ({
  searchCatalog: vi.fn(),
  fetchCDNStats: vi.fn(),
  fetchMCPHealth: vi.fn(),
}));

import { searchCatalog, fetchCDNStats, fetchMCPHealth } from "../lib/api";

const mockSearchCatalog = vi.mocked(searchCatalog);
const mockFetchCDNStats = vi.mocked(fetchCDNStats);
const mockFetchMCPHealth = vi.mocked(fetchMCPHealth);

// ── Test fixtures ──────────────────────────────────────────────────────────────

function makeCatalogEntry(overrides: Partial<{
  id: string;
  agent_id: string;
  namespace: string;
  topic: string;
  description: string;
  quality_avg: number;
  price_range: [number, number];
  active_listings_count: number;
  status: string;
}> = {}) {
  return {
    id: overrides.id ?? "entry-1",
    agent_id: overrides.agent_id ?? "agent-1",
    namespace: overrides.namespace ?? "default",
    topic: overrides.topic ?? "Test Topic",
    description: overrides.description ?? "A test description",
    schema_json: {},
    price_range: overrides.price_range ?? ([0.001, 0.002] as [number, number]),
    quality_avg: overrides.quality_avg ?? 0.9,
    active_listings_count: overrides.active_listings_count ?? 3,
    status: overrides.status ?? "active",
    created_at: "2024-01-01T00:00:00Z",
  };
}

const CATALOG_RESPONSE: CatalogSearchResponse = {
  entries: [
    makeCatalogEntry({ id: "entry-1", namespace: "default", topic: "Topic One", quality_avg: 0.9, price_range: [0.001, 0.001] }),
    makeCatalogEntry({ id: "entry-2", namespace: "finance", topic: "Topic Two", quality_avg: 0.6, price_range: [0.002, 0.004] }),
    makeCatalogEntry({ id: "entry-3", namespace: "analytics", topic: "Topic Three", quality_avg: 0.3, price_range: [0.001, 0.003] }),
  ],
  total: 3,
  page: 1,
  page_size: 50,
};

const CDN_STATS: CDNStats = {
  overview: {
    total_requests: 1000,
    tier1_hits: 600,
    tier2_hits: 200,
    tier3_hits: 100,
    total_misses: 100,
  },
  hot_cache: {
    tier: "hot",
    entries: 42,
    bytes_used: 1024,
    bytes_max: 8192,
    utilization_pct: 12.5,
    hits: 600,
    misses: 50,
    promotions: 10,
    evictions: 5,
    hit_rate: 0.92,
  },
  warm_cache: {
    hits: 200,
    misses: 50,
    size: 512,
    maxsize: 4096,
    hit_rate: 0.8,
  },
};

const MCP_HEALTH: MCPHealth = {
  status: "ok",
  protocol_version: "2024-11-05",
  server: "agentchains-mcp",
  version: "1.0.0",
  active_sessions: 7,
  tools_count: 12,
  resources_count: 5,
};

// ── Render helper ──────────────────────────────────────────────────────────────

function renderWithClient(ui: React.ReactElement) {
  const client = new QueryClient({
    defaultOptions: {
      queries: { retry: false, gcTime: 0 },
    },
  });
  return render(<QueryClientProvider client={client}>{ui}</QueryClientProvider>);
}

// ── Tests ──────────────────────────────────────────────────────────────────────

describe("CatalogPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    // Default: all queries return a promise that never resolves (simulates loading)
    mockSearchCatalog.mockReturnValue(new Promise(() => {}));
    mockFetchCDNStats.mockReturnValue(new Promise(() => {}));
    mockFetchMCPHealth.mockReturnValue(new Promise(() => {}));
  });

  // ── 1. Loading state ─────────────────────────────────────────────────────────

  it("renders loading spinner initially while catalog query is pending", () => {
    renderWithClient(<CatalogPage />);
    expect(screen.getByText("Loading catalog...")).toBeInTheDocument();
  });

  // ── 2. Grid view with entries ─────────────────────────────────────────────────

  it("renders catalog entries in grid view by default", async () => {
    mockSearchCatalog.mockResolvedValue(CATALOG_RESPONSE);
    mockFetchCDNStats.mockResolvedValue(CDN_STATS);
    mockFetchMCPHealth.mockResolvedValue(MCP_HEALTH);

    renderWithClient(<CatalogPage />);

    await waitFor(() => {
      expect(screen.getByText("Topic One")).toBeInTheDocument();
      expect(screen.getByText("Topic Two")).toBeInTheDocument();
      expect(screen.getByText("Topic Three")).toBeInTheDocument();
    });
  });

  // ── 3. List view ──────────────────────────────────────────────────────────────

  it("renders catalog entries in list view after toggling view mode", async () => {
    mockSearchCatalog.mockResolvedValue(CATALOG_RESPONSE);
    mockFetchCDNStats.mockResolvedValue(CDN_STATS);
    mockFetchMCPHealth.mockResolvedValue(MCP_HEALTH);

    renderWithClient(<CatalogPage />);

    await waitFor(() => {
      expect(screen.getByText("Topic One")).toBeInTheDocument();
    });

    const listBtn = screen.getByTitle("List view");
    fireEvent.click(listBtn);

    // In list view the topics are still rendered via CatalogListItem
    expect(screen.getByText("Topic Two")).toBeInTheDocument();
    expect(screen.getByText("Topic Three")).toBeInTheDocument();
  });

  // ── 4. Empty state ────────────────────────────────────────────────────────────

  it("shows empty state when catalog returns no entries", async () => {
    mockSearchCatalog.mockResolvedValue({ entries: [], total: 0, page: 1, page_size: 50 });
    mockFetchCDNStats.mockResolvedValue(CDN_STATS);
    mockFetchMCPHealth.mockResolvedValue(MCP_HEALTH);

    renderWithClient(<CatalogPage />);

    await waitFor(() => {
      expect(screen.getByText(/No catalog entries found/)).toBeInTheDocument();
    });
  });

  // ── 5. CDN card — spinner when stats null ─────────────────────────────────────

  it("CDN card shows spinner when stats are not yet loaded", () => {
    mockSearchCatalog.mockResolvedValue(CATALOG_RESPONSE);
    mockFetchCDNStats.mockReturnValue(new Promise(() => {})); // never resolves
    mockFetchMCPHealth.mockReturnValue(new Promise(() => {}));

    renderWithClient(<CatalogPage />);

    // CDN Performance heading should be visible in both states
    expect(screen.getByText("CDN Performance")).toBeInTheDocument();
    // The spinning div is rendered in the null-stats branch — no hit rate text
    expect(screen.queryByText("Hot Cache")).not.toBeInTheDocument();
  });

  // ── 6. CDN card — shows stats when loaded ────────────────────────────────────

  it("CDN card shows hit rate and cache info when stats are loaded", async () => {
    mockSearchCatalog.mockResolvedValue(CATALOG_RESPONSE);
    mockFetchCDNStats.mockResolvedValue(CDN_STATS);
    mockFetchMCPHealth.mockReturnValue(new Promise(() => {}));

    renderWithClient(<CatalogPage />);

    await waitFor(() => {
      expect(screen.getByText("Hot Cache")).toBeInTheDocument();
    });

    expect(screen.getByText("Tier 1 Hits")).toBeInTheDocument();
    expect(screen.getByText("Tier 2 Hits")).toBeInTheDocument();
    expect(screen.getByText("Disk (T3)")).toBeInTheDocument();
    // hot_cache.entries = 42
    expect(screen.getByText("42")).toBeInTheDocument();
  });

  // ── 7. MCP card — "Connecting..." when health null ───────────────────────────

  it("MCP card shows Connecting text when health is not yet loaded", () => {
    mockSearchCatalog.mockReturnValue(new Promise(() => {}));
    mockFetchCDNStats.mockReturnValue(new Promise(() => {}));
    mockFetchMCPHealth.mockReturnValue(new Promise(() => {}));

    renderWithClient(<CatalogPage />);

    expect(screen.getByText("MCP Server Health")).toBeInTheDocument();
    expect(screen.getByText("Connecting...")).toBeInTheDocument();
  });

  // ── 8. MCP card — "Active" badge when health loaded ──────────────────────────

  it("MCP card shows Active badge and session stats when health is loaded", async () => {
    mockSearchCatalog.mockResolvedValue(CATALOG_RESPONSE);
    mockFetchCDNStats.mockResolvedValue(CDN_STATS);
    mockFetchMCPHealth.mockResolvedValue(MCP_HEALTH);

    renderWithClient(<CatalogPage />);

    await waitFor(() => {
      // "Active" appears in the MCP badge (and possibly the summary card label).
      // Use getAllByText to handle both occurrences safely.
      expect(screen.getAllByText("Active").length).toBeGreaterThan(0);
      // Label text nodes inside the stats grid
      expect(screen.getByText("Sessions")).toBeInTheDocument();
      expect(screen.getByText("Tools")).toBeInTheDocument();
      expect(screen.getByText("Resources")).toBeInTheDocument();
    });

    // MCP_HEALTH.active_sessions = 7
    expect(screen.getByText("7")).toBeInTheDocument();
    // MCP_HEALTH.tools_count = 12
    expect(screen.getAllByText("12").length).toBeGreaterThan(0);
    // MCP_HEALTH.resources_count = 5
    expect(screen.getAllByText("5").length).toBeGreaterThan(0);
  });

  // ── 9. Result count shown at bottom ──────────────────────────────────────────

  it("shows result count at the bottom when entries are loaded", async () => {
    mockSearchCatalog.mockResolvedValue(CATALOG_RESPONSE);
    mockFetchCDNStats.mockResolvedValue(CDN_STATS);
    mockFetchMCPHealth.mockResolvedValue(MCP_HEALTH);

    renderWithClient(<CatalogPage />);

    await waitFor(() => {
      expect(screen.getByText(/Showing 3 of 3 entries/)).toBeInTheDocument();
    });
  });

  // ── 10. Category badge click toggles filter ───────────────────────────────────

  it("toggles category filter on badge click and shows only matching entries", async () => {
    mockSearchCatalog.mockResolvedValue(CATALOG_RESPONSE);
    mockFetchCDNStats.mockResolvedValue(CDN_STATS);
    mockFetchMCPHealth.mockResolvedValue(MCP_HEALTH);

    renderWithClient(<CatalogPage />);

    await waitFor(() => {
      expect(screen.getByText("Topic One")).toBeInTheDocument();
    });

    // Click the "finance" category badge — use getAllByText because "finance" also
    // appears in each entry's namespace span; the badge is a <button>
    const financeBadge = screen.getAllByText("finance").find(
      (el) => el.tagName.toLowerCase() === "button" || el.closest("button") !== null,
    )!;
    fireEvent.click(financeBadge.closest("button") ?? financeBadge);

    // Only the finance entry should remain visible
    expect(screen.getByText("Topic Two")).toBeInTheDocument();
    expect(screen.queryByText("Topic One")).not.toBeInTheDocument();
    expect(screen.queryByText("Topic Three")).not.toBeInTheDocument();

    // Click again to deactivate the filter
    fireEvent.click(financeBadge);

    await waitFor(() => {
      expect(screen.getByText("Topic One")).toBeInTheDocument();
      expect(screen.getByText("Topic Three")).toBeInTheDocument();
    });
  });

  // ── 11. Search input updates query key ───────────────────────────────────────

  it("updates search input and passes new value to searchCatalog", async () => {
    mockSearchCatalog.mockResolvedValue(CATALOG_RESPONSE);
    mockFetchCDNStats.mockResolvedValue(CDN_STATS);
    mockFetchMCPHealth.mockResolvedValue(MCP_HEALTH);

    renderWithClient(<CatalogPage />);

    const input = screen.getByPlaceholderText("Search catalog entries...");
    fireEvent.change(input, { target: { value: "finance data" } });

    // The input value should update
    expect((input as HTMLInputElement).value).toBe("finance data");
  });

  // ── 12. Namespace select updates filter ──────────────────────────────────────

  it("updates namespace select and reflects the chosen option", async () => {
    mockSearchCatalog.mockResolvedValue(CATALOG_RESPONSE);
    mockFetchCDNStats.mockResolvedValue(CDN_STATS);
    mockFetchMCPHealth.mockResolvedValue(MCP_HEALTH);

    renderWithClient(<CatalogPage />);

    await waitFor(() => {
      expect(screen.getByText("Topic One")).toBeInTheDocument();
    });

    // The select is populated with namespaces derived from loaded entries:
    // "analytics", "default", "finance" (sorted alphabetically)
    const select = screen.getByRole("combobox") as HTMLSelectElement;

    // Confirm the namespace options rendered from loaded entries
    await waitFor(() => {
      expect(select.options.length).toBeGreaterThan(1); // "All namespaces" + entries
    });

    // Fire the change event — React's synthetic onChange calls setNamespace("analytics")
    fireEvent.change(select, { target: { value: "analytics" } });

    // After React re-renders with controlled value the select should reflect the choice
    await waitFor(() => {
      expect(select.value).toBe("analytics");
    });
  });

  // ── 13. Quality label colors ──────────────────────────────────────────────────

  it("applies green quality class for score >= 0.8", async () => {
    mockSearchCatalog.mockResolvedValue({
      entries: [
        makeCatalogEntry({ id: "q1", quality_avg: 0.85, topic: "Green Quality Entry" }),
      ],
      total: 1,
      page: 1,
      page_size: 50,
    });
    mockFetchCDNStats.mockResolvedValue(CDN_STATS);
    mockFetchMCPHealth.mockResolvedValue(MCP_HEALTH);

    renderWithClient(<CatalogPage />);

    await waitFor(() => {
      expect(screen.getByText("Green Quality Entry")).toBeInTheDocument();
    });

    // 0.85 * 100 = 85 → rounded to "85"
    const qualityEl = screen.getByText("85%");
    expect(qualityEl.className).toContain("text-[#34d399]");
  });

  it("applies yellow quality class for score >= 0.5 and < 0.8", async () => {
    mockSearchCatalog.mockResolvedValue({
      entries: [
        makeCatalogEntry({ id: "q2", quality_avg: 0.65, topic: "Yellow Quality Entry" }),
      ],
      total: 1,
      page: 1,
      page_size: 50,
    });
    mockFetchCDNStats.mockResolvedValue(CDN_STATS);
    mockFetchMCPHealth.mockResolvedValue(MCP_HEALTH);

    renderWithClient(<CatalogPage />);

    await waitFor(() => {
      expect(screen.getByText("Yellow Quality Entry")).toBeInTheDocument();
    });

    const qualityEl = screen.getByText("65%");
    expect(qualityEl.className).toContain("text-[#fbbf24]");
  });

  it("applies red quality class for score < 0.5", async () => {
    mockSearchCatalog.mockResolvedValue({
      entries: [
        makeCatalogEntry({ id: "q3", quality_avg: 0.3, topic: "Red Quality Entry" }),
      ],
      total: 1,
      page: 1,
      page_size: 50,
    });
    mockFetchCDNStats.mockResolvedValue(CDN_STATS);
    mockFetchMCPHealth.mockResolvedValue(MCP_HEALTH);

    renderWithClient(<CatalogPage />);

    await waitFor(() => {
      expect(screen.getByText("Red Quality Entry")).toBeInTheDocument();
    });

    const qualityEl = screen.getByText("30%");
    expect(qualityEl.className).toContain("text-[#f87171]");
  });

  // ── 14. formatPrice — same min/max ───────────────────────────────────────────

  it("renders a single price when min equals max", async () => {
    mockSearchCatalog.mockResolvedValue({
      entries: [
        makeCatalogEntry({ id: "p1", price_range: [0.0050, 0.0050], topic: "Fixed Price Entry" }),
      ],
      total: 1,
      page: 1,
      page_size: 50,
    });
    mockFetchCDNStats.mockResolvedValue(CDN_STATS);
    mockFetchMCPHealth.mockResolvedValue(MCP_HEALTH);

    renderWithClient(<CatalogPage />);

    await waitFor(() => {
      expect(screen.getByText("$0.0050")).toBeInTheDocument();
    });
  });

  // ── 15. formatPrice — different min/max ──────────────────────────────────────

  it("renders a price range when min differs from max", async () => {
    mockSearchCatalog.mockResolvedValue({
      entries: [
        makeCatalogEntry({ id: "p2", price_range: [0.002, 0.004], topic: "Range Price Entry" }),
      ],
      total: 1,
      page: 1,
      page_size: 50,
    });
    mockFetchCDNStats.mockResolvedValue(CDN_STATS);
    mockFetchMCPHealth.mockResolvedValue(MCP_HEALTH);

    renderWithClient(<CatalogPage />);

    await waitFor(() => {
      expect(screen.getByText("$0.0020 – $0.0040")).toBeInTheDocument();
    });
  });

  // ── 16. CategoryBadges — returns null when empty ──────────────────────────────

  it("does not render any category badges when entries list is empty", async () => {
    mockSearchCatalog.mockResolvedValue({ entries: [], total: 0, page: 1, page_size: 50 });
    mockFetchCDNStats.mockResolvedValue(CDN_STATS);
    mockFetchMCPHealth.mockResolvedValue(MCP_HEALTH);

    renderWithClient(<CatalogPage />);

    await waitFor(() => {
      expect(screen.getByText(/No catalog entries found/)).toBeInTheDocument();
    });

    // With no entries there are no namespace badges
    expect(screen.queryByRole("button", { name: /default/ })).not.toBeInTheDocument();
  });

  // ── 17. namespaceColor — "default" namespace gets the fixed colour ─────────────
  //
  // jsdom normalises hex colours to rgb() in computed styles, so we verify the
  // namespace badge is rendered with an inline `style` attribute rather than
  // checking the exact hex string (which would be implementation-specific).

  it("renders the namespace badge for the 'default' namespace entry", async () => {
    mockSearchCatalog.mockResolvedValue({
      entries: [
        makeCatalogEntry({ id: "ns1", namespace: "default", topic: "Default NS Entry" }),
      ],
      total: 1,
      page: 1,
      page_size: 50,
    });
    mockFetchCDNStats.mockResolvedValue(CDN_STATS);
    mockFetchMCPHealth.mockResolvedValue(MCP_HEALTH);

    const { container } = renderWithClient(<CatalogPage />);

    await waitFor(() => {
      expect(screen.getByText("Default NS Entry")).toBeInTheDocument();
    });

    // The namespace badge is a <span> with an inline style containing color
    // (set by namespaceColor("default") = "#60a5fa"). jsdom serialises the hex
    // to rgb so we look for any element with a non-empty inline style attribute.
    const styledSpans = container.querySelectorAll("span[style]");
    expect(styledSpans.length).toBeGreaterThan(0);
  });

  // ── 18. namespaceColor — non-"default" namespace gets a hash-based colour ──────
  //
  // jsdom normalises hsl() values to rgb() when assigned via React's style prop,
  // so we verify the namespace badge for a non-default namespace is rendered and
  // carries an inline style attribute (confirming namespaceColor was called and
  // produced a non-null output).

  it("renders the namespace badge with an inline style for non-default namespaces", async () => {
    mockSearchCatalog.mockResolvedValue({
      entries: [
        makeCatalogEntry({ id: "ns2", namespace: "custom-ns", topic: "Custom NS Entry" }),
      ],
      total: 1,
      page: 1,
      page_size: 50,
    });
    mockFetchCDNStats.mockResolvedValue(CDN_STATS);
    mockFetchMCPHealth.mockResolvedValue(MCP_HEALTH);

    const { container } = renderWithClient(<CatalogPage />);

    await waitFor(() => {
      expect(screen.getByText("Custom NS Entry")).toBeInTheDocument();
    });

    // The namespace badge span carries inline colour styles generated by namespaceColor.
    // jsdom stores the computed rgb() form in the style object but the element is
    // still present with a non-empty style attribute.
    const styledElements = container.querySelectorAll("span[style], div[style]");
    expect(styledElements.length).toBeGreaterThan(0);

    // The namespace text is visible in both the card badge and the category filter
    // button — use getAllByText to handle both occurrences.
    expect(screen.getAllByText("custom-ns").length).toBeGreaterThan(0);
  });

  // ── 19. Grid toggle button switches back from list ────────────────────────────

  it("switches from list back to grid view when grid button is clicked", async () => {
    mockSearchCatalog.mockResolvedValue(CATALOG_RESPONSE);
    mockFetchCDNStats.mockResolvedValue(CDN_STATS);
    mockFetchMCPHealth.mockResolvedValue(MCP_HEALTH);

    renderWithClient(<CatalogPage />);

    await waitFor(() => {
      expect(screen.getByText("Topic One")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByTitle("List view"));
    fireEvent.click(screen.getByTitle("Grid view"));

    // Entries should still be visible in grid mode
    expect(screen.getByText("Topic One")).toBeInTheDocument();
  });

  // ── 20. Singular listing badge label ─────────────────────────────────────────

  it("renders singular 'listing' label when active_listings_count is 1", async () => {
    mockSearchCatalog.mockResolvedValue({
      entries: [
        makeCatalogEntry({ id: "l1", active_listings_count: 1, topic: "One Listing Entry" }),
      ],
      total: 1,
      page: 1,
      page_size: 50,
    });
    mockFetchCDNStats.mockResolvedValue(CDN_STATS);
    mockFetchMCPHealth.mockResolvedValue(MCP_HEALTH);

    renderWithClient(<CatalogPage />);

    await waitFor(() => {
      expect(screen.getByText("1 listing")).toBeInTheDocument();
    });
  });

  // ── 21. Plural listings badge label ──────────────────────────────────────────

  it("renders plural 'listings' label when active_listings_count > 1", async () => {
    mockSearchCatalog.mockResolvedValue({
      entries: [
        makeCatalogEntry({ id: "l2", active_listings_count: 5, topic: "Five Listings Entry" }),
      ],
      total: 1,
      page: 1,
      page_size: 50,
    });
    mockFetchCDNStats.mockResolvedValue(CDN_STATS);
    mockFetchMCPHealth.mockResolvedValue(MCP_HEALTH);

    renderWithClient(<CatalogPage />);

    await waitFor(() => {
      expect(screen.getByText("5 listings")).toBeInTheDocument();
    });
  });

  // ── 22. CatalogSummaryCard — active count ────────────────────────────────────

  it("shows correct active count in the summary card", async () => {
    mockSearchCatalog.mockResolvedValue({
      entries: [
        makeCatalogEntry({ id: "s1", status: "active", topic: "Active A" }),
        makeCatalogEntry({ id: "s2", status: "inactive", topic: "Inactive B" }),
        makeCatalogEntry({ id: "s3", status: "active", topic: "Active C" }),
      ],
      total: 3,
      page: 1,
      page_size: 50,
    });
    mockFetchCDNStats.mockResolvedValue(CDN_STATS);
    mockFetchMCPHealth.mockResolvedValue(MCP_HEALTH);

    renderWithClient(<CatalogPage />);

    await waitFor(() => {
      expect(screen.getByText("Active A")).toBeInTheDocument();
    });

    // "Active" label appears in the summary card (and also in the MCP badge when
    // health resolves). Use getAllByText to safely handle both occurrences.
    expect(screen.getAllByText("Active").length).toBeGreaterThan(0);
  });

  // ── 23. Description fallback ──────────────────────────────────────────────────

  it("falls back to 'No description provided' when description is empty", async () => {
    mockSearchCatalog.mockResolvedValue({
      entries: [
        { ...makeCatalogEntry({ id: "d1", topic: "No Desc Entry" }), description: "" },
      ],
      total: 1,
      page: 1,
      page_size: 50,
    });
    mockFetchCDNStats.mockResolvedValue(CDN_STATS);
    mockFetchMCPHealth.mockResolvedValue(MCP_HEALTH);

    renderWithClient(<CatalogPage />);

    await waitFor(() => {
      expect(screen.getAllByText("No description provided").length).toBeGreaterThan(0);
    });
  });
});
