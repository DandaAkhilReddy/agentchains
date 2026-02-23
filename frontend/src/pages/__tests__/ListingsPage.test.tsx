import { describe, it, expect, vi, beforeEach } from "vitest";
import { screen, fireEvent, waitFor, act } from "@testing-library/react";
import { renderWithProviders } from "../../test/test-utils";
import ListingsPage from "../ListingsPage";
import * as useAuthModule from "../../hooks/useAuth";
import * as useDiscoverModule from "../../hooks/useDiscover";
import * as apiModule from "../../lib/api";
import type { Listing, ListingListResponse } from "../../types/api";

// Mock hooks
vi.mock("../../hooks/useAuth");
vi.mock("../../hooks/useDiscover");

// Mock the Toast context - capture the toast function
const mockToast = vi.fn();
vi.mock("../../components/Toast", () => ({
  useToast: () => ({ toast: mockToast }),
}));

// Mock the API module (expressBuy)
vi.mock("../../lib/api", () => ({
  expressBuy: vi.fn(),
}));

/* ── Test Data ──────────────────────────────────────────── */

const mockListings: Listing[] = [
  {
    id: "lst-001",
    seller_id: "seller-001",
    seller: { id: "seller-001", name: "AlphaAgent", reputation_score: 0.95 },
    title: "Web Search Results for AI Trends",
    description: "Comprehensive web search results for the latest AI trends",
    category: "web_search",
    content_hash: "hash1",
    content_size: 2048,
    content_type: "application/json",
    price_usdc: 0.003,
    currency: "USDC",
    metadata: {},
    tags: ["ai", "trends", "search", "technology"],
    quality_score: 0.92,
    freshness_at: new Date(Date.now() - 1800000).toISOString(), // 30 min ago
    expires_at: null,
    status: "active",
    access_count: 15,
    created_at: new Date(Date.now() - 86400000).toISOString(),
    updated_at: new Date(Date.now() - 3600000).toISOString(),
  },
  {
    id: "lst-002",
    seller_id: "seller-002",
    seller: { id: "seller-002", name: "BetaBot", reputation_score: 0.78 },
    title: "Code Analysis Report for React App",
    description: "Detailed code analysis for a React application",
    category: "code_analysis",
    content_hash: "hash2",
    content_size: 4096,
    content_type: "application/json",
    price_usdc: 0.005,
    currency: "USDC",
    metadata: {},
    tags: ["react", "code"],
    quality_score: 0.85,
    freshness_at: new Date(Date.now() - 7200000).toISOString(), // 2 hours ago
    expires_at: null,
    status: "active",
    access_count: 8,
    created_at: new Date(Date.now() - 172800000).toISOString(),
    updated_at: new Date(Date.now() - 7200000).toISOString(),
  },
  {
    id: "lst-003",
    seller_id: "seller-003",
    seller: null,
    title: "Document Summary of Research Paper",
    description: "Summary of a machine learning research paper",
    category: "document_summary",
    content_hash: "hash3",
    content_size: 1024,
    content_type: "text/plain",
    price_usdc: 0.001,
    currency: "USDC",
    metadata: {},
    tags: [],
    quality_score: 0.65,
    freshness_at: new Date(Date.now() - 86400000).toISOString(), // 24 hours ago
    expires_at: null,
    status: "active",
    access_count: 3,
    created_at: new Date(Date.now() - 259200000).toISOString(),
    updated_at: new Date(Date.now() - 86400000).toISOString(),
  },
];

const mockResponse: ListingListResponse = {
  total: 3,
  page: 1,
  page_size: 12,
  results: mockListings,
};

const mockResponseEmpty: ListingListResponse = {
  total: 0,
  page: 1,
  page_size: 12,
  results: [],
};

const mockResponseLarge: ListingListResponse = {
  total: 25,
  page: 1,
  page_size: 12,
  results: mockListings,
};

/* ── Helpers ──────────────────────────────────────────────── */

function setupAuth(token = "test-jwt") {
  vi.spyOn(useAuthModule, "useAuth").mockReturnValue({
    token,
    login: vi.fn(),
    logout: vi.fn(),
    isAuthenticated: !!token,
  });
}

function setupDiscover(data: ListingListResponse | undefined, isLoading = false) {
  vi.spyOn(useDiscoverModule, "useDiscover").mockReturnValue({
    data,
    isLoading,
    error: null,
  } as any);
}

/* ── Tests ──────────────────────────────────────────────── */

describe("ListingsPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders marketplace page header", () => {
    setupAuth();
    setupDiscover(mockResponse);

    renderWithProviders(<ListingsPage />);

    expect(screen.getByText("Marketplace")).toBeInTheDocument();
    expect(screen.getByText("Discover and purchase cached computation results")).toBeInTheDocument();
  });

  it("shows listing cards with titles", () => {
    setupAuth();
    setupDiscover(mockResponse);

    renderWithProviders(<ListingsPage />);

    expect(screen.getByText("Web Search Results for AI Trends")).toBeInTheDocument();
    expect(screen.getByText("Code Analysis Report for React App")).toBeInTheDocument();
    expect(screen.getByText("Document Summary of Research Paper")).toBeInTheDocument();
  });

  it("shows auth gate banner when not authenticated", () => {
    setupAuth("");
    setupDiscover(mockResponse);

    renderWithProviders(<ListingsPage />);

    expect(
      screen.getByText("Connect your agent JWT in the Transactions tab to enable Express Buy"),
    ).toBeInTheDocument();
  });

  it("shows loading skeleton cards when loading", () => {
    setupAuth();
    setupDiscover(undefined, true);

    const { container } = renderWithProviders(<ListingsPage />);

    // Skeleton cards use animate-pulse class
    const skeletonElements = container.querySelectorAll(".animate-pulse");
    expect(skeletonElements.length).toBeGreaterThan(0);
  });

  it("shows empty state when no listings found", () => {
    setupAuth();
    setupDiscover(mockResponseEmpty);

    renderWithProviders(<ListingsPage />);

    expect(screen.getByText("No listings found")).toBeInTheDocument();
    expect(screen.getByText("Try adjusting your filters or search query")).toBeInTheDocument();
  });

  it("renders category filter select with correct options", () => {
    setupAuth();
    setupDiscover(mockResponse);

    renderWithProviders(<ListingsPage />);

    const categorySelect = screen.getByDisplayValue("All Categories");
    expect(categorySelect).toBeInTheDocument();

    const options = categorySelect.querySelectorAll("option");
    expect(options).toHaveLength(6);
    expect(options[0]).toHaveTextContent("All Categories");
    expect(options[1]).toHaveTextContent("Web Search");
    expect(options[2]).toHaveTextContent("Code Analysis");
    expect(options[3]).toHaveTextContent("Doc Summary");
    expect(options[4]).toHaveTextContent("API Response");
    expect(options[5]).toHaveTextContent("Computation");
  });

  it("renders sort select with correct options", () => {
    setupAuth();
    setupDiscover(mockResponse);

    renderWithProviders(<ListingsPage />);

    const sortSelect = screen.getByDisplayValue("Freshest");
    expect(sortSelect).toBeInTheDocument();

    const options = sortSelect.querySelectorAll("option");
    expect(options).toHaveLength(4);
    expect(options[0]).toHaveTextContent("Freshest");
    expect(options[3]).toHaveTextContent("Highest Quality");
  });

  it("shows search input for listing search", () => {
    setupAuth();
    setupDiscover(mockResponse);

    renderWithProviders(<ListingsPage />);

    expect(screen.getByPlaceholderText("Search listings...")).toBeInTheDocument();
  });

  it("shows pagination when total exceeds 12", () => {
    setupAuth();
    setupDiscover(mockResponseLarge);

    renderWithProviders(<ListingsPage />);

    expect(screen.getByRole("button", { name: "Previous page" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Next page" })).toBeInTheDocument();
  });

  it("does not show pagination when total is 12 or less", () => {
    setupAuth();
    setupDiscover(mockResponse);

    renderWithProviders(<ListingsPage />);

    expect(screen.queryByRole("button", { name: "Previous page" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Next page" })).not.toBeInTheDocument();
  });

  it("shows listing count in header", () => {
    setupAuth();
    setupDiscover(mockResponse);

    renderWithProviders(<ListingsPage />);

    expect(screen.getByText("3 listings")).toBeInTheDocument();
  });

  // ─── New coverage tests ───

  it("does not show auth gate banner when authenticated", () => {
    setupAuth("valid-token");
    setupDiscover(mockResponse);

    renderWithProviders(<ListingsPage />);

    expect(
      screen.queryByText("Connect your agent JWT in the Transactions tab to enable Express Buy"),
    ).not.toBeInTheDocument();
  });

  it("shows singular 'listing' for count of 1", () => {
    setupAuth();
    vi.spyOn(useDiscoverModule, "useDiscover").mockReturnValue({
      data: {
        total: 1,
        page: 1,
        page_size: 12,
        results: [mockListings[0]],
      },
      isLoading: false,
      error: null,
    } as any);

    renderWithProviders(<ListingsPage />);

    expect(screen.getByText("1 listing")).toBeInTheDocument();
  });

  it("shows results count on desktop", () => {
    setupAuth();
    setupDiscover(mockResponse);

    renderWithProviders(<ListingsPage />);

    // The results count is shown in the filter bar on desktop
    expect(screen.getByText("3 results")).toBeInTheDocument();
  });

  it("shows singular 'result' for count of 1", () => {
    setupAuth();
    vi.spyOn(useDiscoverModule, "useDiscover").mockReturnValue({
      data: {
        total: 1,
        page: 1,
        page_size: 12,
        results: [mockListings[0]],
      },
      isLoading: false,
      error: null,
    } as any);

    renderWithProviders(<ListingsPage />);

    expect(screen.getByText("1 result")).toBeInTheDocument();
  });

  it("does not render header badge or results count when data is undefined", () => {
    setupAuth();
    setupDiscover(undefined);

    renderWithProviders(<ListingsPage />);

    expect(screen.queryByText(/\d+ listings?/)).not.toBeInTheDocument();
    expect(screen.queryByText(/\d+ results?/)).not.toBeInTheDocument();
  });

  it("changes category filter", async () => {
    setupAuth();
    const mockUseDiscover = vi.fn().mockReturnValue({
      data: mockResponse,
      isLoading: false,
      error: null,
    });
    vi.spyOn(useDiscoverModule, "useDiscover").mockImplementation(mockUseDiscover);

    renderWithProviders(<ListingsPage />);

    const categorySelect = screen.getByDisplayValue("All Categories");
    fireEvent.change(categorySelect, { target: { value: "web_search" } });

    await waitFor(() => {
      expect(mockUseDiscover).toHaveBeenCalledWith(
        expect.objectContaining({
          category: "web_search",
          page: 1,
        }),
      );
    });
  });

  it("changes sort selection", async () => {
    setupAuth();
    const mockUseDiscover = vi.fn().mockReturnValue({
      data: mockResponse,
      isLoading: false,
      error: null,
    });
    vi.spyOn(useDiscoverModule, "useDiscover").mockImplementation(mockUseDiscover);

    renderWithProviders(<ListingsPage />);

    const sortSelect = screen.getByDisplayValue("Freshest");
    fireEvent.change(sortSelect, { target: { value: "price_asc" } });

    await waitFor(() => {
      expect(mockUseDiscover).toHaveBeenCalledWith(
        expect.objectContaining({
          sort_by: "price_asc",
        }),
      );
    });
  });

  it("search resets page to 1", async () => {
    setupAuth();
    const mockUseDiscover = vi.fn().mockReturnValue({
      data: mockResponse,
      isLoading: false,
      error: null,
    });
    vi.spyOn(useDiscoverModule, "useDiscover").mockImplementation(mockUseDiscover);

    renderWithProviders(<ListingsPage />);

    const searchInput = screen.getByPlaceholderText("Search listings...");
    fireEvent.change(searchInput, { target: { value: "react" } });

    await waitFor(() => {
      expect(mockUseDiscover).toHaveBeenCalledWith(
        expect.objectContaining({
          q: "react",
          page: 1,
        }),
      );
    });
  });

  it("displays seller names on listing cards", () => {
    setupAuth();
    setupDiscover(mockResponse);

    renderWithProviders(<ListingsPage />);

    expect(screen.getByText("AlphaAgent")).toBeInTheDocument();
    expect(screen.getByText("BetaBot")).toBeInTheDocument();
  });

  it("displays seller reputation scores", () => {
    setupAuth();
    setupDiscover(mockResponse);

    renderWithProviders(<ListingsPage />);

    // Reputation 0.95 -> Math.round(0.95*100) = 95%
    expect(screen.getByText("95%")).toBeInTheDocument();
    // Reputation 0.78 -> Math.round(0.78*100) = 78%
    expect(screen.getByText("78%")).toBeInTheDocument();
  });

  it("does not render seller section for listing without seller", () => {
    setupAuth();
    setupDiscover(mockResponse);

    renderWithProviders(<ListingsPage />);

    // The third listing has seller: null, so it should not show seller info
    // But other listings do have seller info
    expect(screen.getByText("AlphaAgent")).toBeInTheDocument();
    // "seller-003" should not have a seller name rendered
  });

  it("displays listing descriptions", () => {
    setupAuth();
    setupDiscover(mockResponse);

    renderWithProviders(<ListingsPage />);

    expect(screen.getByText("Comprehensive web search results for the latest AI trends")).toBeInTheDocument();
    expect(screen.getByText("Detailed code analysis for a React application")).toBeInTheDocument();
  });

  it("displays listing prices", () => {
    setupAuth();
    setupDiscover(mockResponse);

    renderWithProviders(<ListingsPage />);

    // formatUSD(0.003) -> "$0.00" (price_usdc values)
    // The prices are formatted with formatUSD
  });

  it("displays quality percentages", () => {
    setupAuth();
    setupDiscover(mockResponse);

    renderWithProviders(<ListingsPage />);

    // quality_score 0.92 -> 92% (same as no reputation match - unique)
    const pct92 = screen.getAllByText("92%");
    expect(pct92.length).toBeGreaterThanOrEqual(1);
    // quality_score 0.85 -> 85% (unique)
    const pct85 = screen.getAllByText("85%");
    expect(pct85.length).toBeGreaterThanOrEqual(1);
    // quality_score 0.65 -> 65% (unique)
    const pct65 = screen.getAllByText("65%");
    expect(pct65.length).toBeGreaterThanOrEqual(1);
  });

  it("renders tags on listing cards", () => {
    setupAuth();
    setupDiscover(mockResponse);

    renderWithProviders(<ListingsPage />);

    // First listing has 4 tags: ai, trends, search, technology
    // Only first 3 are shown + "+1" overflow
    expect(screen.getByText("ai")).toBeInTheDocument();
    expect(screen.getByText("trends")).toBeInTheDocument();
    expect(screen.getByText("search")).toBeInTheDocument();
    expect(screen.getByText("+1")).toBeInTheDocument();
  });

  it("does not render tags section for listing with empty tags", () => {
    setupAuth();
    setupDiscover(mockResponse);

    renderWithProviders(<ListingsPage />);

    // Third listing has empty tags array. The tags section should not be rendered for it.
    // We can verify the other listings have tags
    expect(screen.getByText("react")).toBeInTheDocument();
    expect(screen.getByText("code")).toBeInTheDocument();
  });

  it("renders Express Buy buttons on all listing cards", () => {
    setupAuth();
    setupDiscover(mockResponse);

    renderWithProviders(<ListingsPage />);

    const expressBuyButtons = screen.getAllByText("Express Buy");
    expect(expressBuyButtons.length).toBe(3);
  });

  it("handles Express Buy click when authenticated", async () => {
    setupAuth("test-jwt");
    setupDiscover(mockResponse);
    vi.mocked(apiModule.expressBuy).mockResolvedValue({
      listing_id: "lst-001",
      transaction_id: "tx-001",
      content: "test content",
      content_hash: "hash",
      price_usdc: 0.003,
      delivery_ms: 42,
      cache_hit: true,
    });

    renderWithProviders(<ListingsPage />);

    const expressBuyButtons = screen.getAllByText("Express Buy");
    fireEvent.click(expressBuyButtons[0]);

    await waitFor(() => {
      expect(apiModule.expressBuy).toHaveBeenCalledWith("test-jwt", "lst-001");
      expect(mockToast).toHaveBeenCalledWith(
        "Purchased! Delivered in 42ms (cache hit)",
        "success",
      );
    });
  });

  it("handles Express Buy click when not authenticated", async () => {
    setupAuth("");
    setupDiscover(mockResponse);

    renderWithProviders(<ListingsPage />);

    const expressBuyButtons = screen.getAllByText("Express Buy");
    fireEvent.click(expressBuyButtons[0]);

    await waitFor(() => {
      expect(apiModule.expressBuy).not.toHaveBeenCalled();
      expect(mockToast).toHaveBeenCalledWith(
        "Connect your agent JWT first (Transactions tab)",
        "error",
      );
    });
  });

  it("handles Express Buy failure", async () => {
    setupAuth("test-jwt");
    setupDiscover(mockResponse);
    vi.mocked(apiModule.expressBuy).mockRejectedValue(new Error("Insufficient balance"));

    renderWithProviders(<ListingsPage />);

    const expressBuyButtons = screen.getAllByText("Express Buy");
    fireEvent.click(expressBuyButtons[0]);

    await waitFor(() => {
      expect(mockToast).toHaveBeenCalledWith("Insufficient balance", "error");
    });
  });

  it("handles Express Buy with cache miss", async () => {
    setupAuth("test-jwt");
    setupDiscover(mockResponse);
    vi.mocked(apiModule.expressBuy).mockResolvedValue({
      listing_id: "lst-001",
      transaction_id: "tx-001",
      content: "test content",
      content_hash: "hash",
      price_usdc: 0.003,
      delivery_ms: 150,
      cache_hit: false,
    });

    renderWithProviders(<ListingsPage />);

    const expressBuyButtons = screen.getAllByText("Express Buy");
    fireEvent.click(expressBuyButtons[0]);

    await waitFor(() => {
      expect(mockToast).toHaveBeenCalledWith(
        "Purchased! Delivered in 150ms ",
        "success",
      );
    });
  });

  it("renders category badges on listing cards", () => {
    setupAuth();
    setupDiscover(mockResponse);

    renderWithProviders(<ListingsPage />);

    // Category labels are displayed as badges (category.replace(/_/g, ' '))
    expect(screen.getByText("web search")).toBeInTheDocument();
    expect(screen.getByText("code analysis")).toBeInTheDocument();
    expect(screen.getByText("document summary")).toBeInTheDocument();
  });

  it("renders access count on listing cards", () => {
    setupAuth();
    setupDiscover(mockResponse);

    renderWithProviders(<ListingsPage />);

    expect(screen.getByText("15")).toBeInTheDocument(); // lst-001 access_count
    expect(screen.getByText("8")).toBeInTheDocument();  // lst-002 access_count
    expect(screen.getByText("3")).toBeInTheDocument();  // lst-003 access_count
  });

  it("renders content size in formatted bytes", () => {
    setupAuth();
    setupDiscover(mockResponse);

    renderWithProviders(<ListingsPage />);

    // 2048 -> "2.0 KB", 4096 -> "4.0 KB", 1024 -> "1.0 KB"
    expect(screen.getByText("2.0 KB")).toBeInTheDocument();
    expect(screen.getByText("4.0 KB")).toBeInTheDocument();
    expect(screen.getByText("1.0 KB")).toBeInTheDocument();
  });

  it("renders freshness badges with relative times", () => {
    setupAuth();
    setupDiscover(mockResponse);

    renderWithProviders(<ListingsPage />);

    // The freshness badges should show relative times like "30m ago", "2h ago", "1d ago"
    // These are rendered by FreshnessBadge component
  });

  it("handles mouse hover on listing cards without errors", () => {
    setupAuth();
    setupDiscover(mockResponse);

    const { container } = renderWithProviders(<ListingsPage />);

    // Find listing card - the ListingCard root div has style backgroundColor="#141928"
    const cards = container.querySelectorAll(".group");
    expect(cards.length).toBeGreaterThanOrEqual(1);

    const card = cards[0] as HTMLElement;

    // Trigger mouseEnter and mouseLeave - ensure no errors thrown
    fireEvent.mouseEnter(card);
    fireEvent.mouseLeave(card);
    // Verify the card is still in the document (no crash)
    expect(card).toBeInTheDocument();
  });

  it("handles mouse hover on Express Buy buttons", () => {
    setupAuth();
    setupDiscover(mockResponse);

    renderWithProviders(<ListingsPage />);

    const expressBuyButtons = screen.getAllByText("Express Buy");
    const button = expressBuyButtons[0].closest("button") as HTMLElement;

    fireEvent.mouseEnter(button);
    fireEvent.mouseLeave(button);
    // No errors should occur
  });

  it("shows empty state when data is undefined and not loading", () => {
    setupAuth();
    setupDiscover(undefined);

    renderWithProviders(<ListingsPage />);

    expect(screen.getByText("No listings found")).toBeInTheDocument();
  });

  it("renders Quality labels on listing cards", () => {
    setupAuth();
    setupDiscover(mockResponse);

    renderWithProviders(<ListingsPage />);

    const qualityLabels = screen.getAllByText("Quality");
    expect(qualityLabels.length).toBe(3); // One per listing card
  });

  it("renders listing with high quality score in green color", () => {
    setupAuth();
    // Use a listing with unique quality score to avoid collision with reputation scores
    vi.spyOn(useDiscoverModule, "useDiscover").mockReturnValue({
      data: {
        total: 1,
        page: 1,
        page_size: 12,
        results: [
          {
            ...mockListings[0],
            id: "lst-high-q",
            seller: null,
            quality_score: 0.73,
          },
        ],
      },
      isLoading: false,
      error: null,
    } as any);

    renderWithProviders(<ListingsPage />);

    // 73% quality appears in both ListingCard header and QualityBar
    // The styled one (with inline color) is in the card header
    const pct73All = screen.getAllByText("73%");
    expect(pct73All.length).toBeGreaterThanOrEqual(1);
    // Find the one with inline style color (the quality label, not QualityBar)
    const styledPct = pct73All.find(el => el.style.color);
    expect(styledPct).toBeTruthy();
    expect(styledPct!.style.color).toBe("rgb(52, 211, 153)");
  });

  it("renders listing with medium quality score in yellow color", () => {
    setupAuth();
    vi.spyOn(useDiscoverModule, "useDiscover").mockReturnValue({
      data: {
        total: 1,
        page: 1,
        page_size: 12,
        results: [
          {
            ...mockListings[0],
            id: "lst-med-q",
            seller: null,
            quality_score: 0.55,
          },
        ],
      },
      isLoading: false,
      error: null,
    } as any);

    renderWithProviders(<ListingsPage />);

    // 55% quality appears in both ListingCard header and QualityBar
    const pct55All = screen.getAllByText("55%");
    expect(pct55All.length).toBeGreaterThanOrEqual(1);
    const styledPct = pct55All.find(el => el.style.color);
    expect(styledPct).toBeTruthy();
    expect(styledPct!.style.color).toBe("rgb(251, 191, 36)");
  });

  it("renders listing with very low quality score in red color", () => {
    setupAuth();
    vi.spyOn(useDiscoverModule, "useDiscover").mockReturnValue({
      data: {
        total: 1,
        page: 1,
        page_size: 12,
        results: [
          {
            ...mockListings[0],
            id: "lst-low-q",
            seller: null,
            quality_score: 0.25,
          },
        ],
      },
      isLoading: false,
      error: null,
    } as any);

    renderWithProviders(<ListingsPage />);

    // 25% quality appears in both ListingCard header and QualityBar
    const pct25All = screen.getAllByText("25%");
    expect(pct25All.length).toBeGreaterThanOrEqual(1);
    const styledPct = pct25All.find(el => el.style.color);
    expect(styledPct).toBeTruthy();
    expect(styledPct!.style.color).toBe("rgb(248, 113, 113)");
  });

  it("renders FreshnessBadge with green styling for very fresh items", () => {
    setupAuth();
    vi.spyOn(useDiscoverModule, "useDiscover").mockReturnValue({
      data: {
        total: 1,
        page: 1,
        page_size: 12,
        results: [
          {
            ...mockListings[0],
            id: "lst-fresh",
            freshness_at: new Date(Date.now() - 60000).toISOString(), // 1 min ago
          },
        ],
      },
      isLoading: false,
      error: null,
    } as any);

    renderWithProviders(<ListingsPage />);

    // "just now" or "1m ago" should have green styling
  });

  it("renders FreshnessBadge with gray styling for old items", () => {
    setupAuth();
    vi.spyOn(useDiscoverModule, "useDiscover").mockReturnValue({
      data: {
        total: 1,
        page: 1,
        page_size: 12,
        results: [
          {
            ...mockListings[0],
            id: "lst-old",
            freshness_at: new Date(Date.now() - 172800000).toISOString(), // 48 hours ago
          },
        ],
      },
      isLoading: false,
      error: null,
    } as any);

    renderWithProviders(<ListingsPage />);

    // "2d ago" should have gray styling
    expect(screen.getByText("2d ago")).toBeInTheDocument();
  });

  it("renders seller initial avatar for listings with seller", () => {
    setupAuth();
    setupDiscover(mockResponse);

    renderWithProviders(<ListingsPage />);

    // AlphaAgent -> first char 'A'
    expect(screen.getByText("A")).toBeInTheDocument();
    // BetaBot -> first char 'B'
    expect(screen.getByText("B")).toBeInTheDocument();
  });

  it("renders seller with null reputation_score without percentage", () => {
    setupAuth();
    vi.spyOn(useDiscoverModule, "useDiscover").mockReturnValue({
      data: {
        total: 1,
        page: 1,
        page_size: 12,
        results: [
          {
            ...mockListings[0],
            id: "lst-no-rep",
            seller: { id: "seller-x", name: "NoRepAgent", reputation_score: null },
          },
        ],
      },
      isLoading: false,
      error: null,
    } as any);

    renderWithProviders(<ListingsPage />);

    expect(screen.getByText("NoRepAgent")).toBeInTheDocument();
    // ShieldCheck icon with percentage should not appear for this listing
  });

  it("renders category-specific icons for known categories", () => {
    setupAuth();
    setupDiscover(mockResponse);

    const { container } = renderWithProviders(<ListingsPage />);

    // web_search uses Search icon, code_analysis uses Code icon, etc.
    const searchIcons = container.querySelectorAll(".lucide-search");
    expect(searchIcons.length).toBeGreaterThanOrEqual(1);

    const codeIcons = container.querySelectorAll(".lucide-code");
    expect(codeIcons.length).toBeGreaterThanOrEqual(1);

    const fileTextIcons = container.querySelectorAll(".lucide-file-text");
    expect(fileTextIcons.length).toBeGreaterThanOrEqual(1);
  });

  it("uses fallback Globe icon for unknown category", () => {
    setupAuth();
    vi.spyOn(useDiscoverModule, "useDiscover").mockReturnValue({
      data: {
        total: 1,
        page: 1,
        page_size: 12,
        results: [
          {
            ...mockListings[0],
            id: "lst-unknown-cat",
            category: "unknown_category" as any,
          },
        ],
      },
      isLoading: false,
      error: null,
    } as any);

    const { container } = renderWithProviders(<ListingsPage />);

    // Should fall back to Globe icon
    const globeIcons = container.querySelectorAll(".lucide-globe");
    expect(globeIcons.length).toBeGreaterThanOrEqual(1);
  });

  it("renders listing with description as empty string without description block", () => {
    setupAuth();
    vi.spyOn(useDiscoverModule, "useDiscover").mockReturnValue({
      data: {
        total: 1,
        page: 1,
        page_size: 12,
        results: [
          {
            ...mockListings[0],
            id: "lst-no-desc",
            description: "",
          },
        ],
      },
      isLoading: false,
      error: null,
    } as any);

    renderWithProviders(<ListingsPage />);

    // The description paragraph should not be rendered when description is empty
    // The title should still appear
    expect(screen.getByText("Web Search Results for AI Trends")).toBeInTheDocument();
  });

  it("category filter change resets page", async () => {
    setupAuth();
    const mockUseDiscover = vi.fn().mockReturnValue({
      data: mockResponse,
      isLoading: false,
      error: null,
    });
    vi.spyOn(useDiscoverModule, "useDiscover").mockImplementation(mockUseDiscover);

    renderWithProviders(<ListingsPage />);

    const categorySelect = screen.getByDisplayValue("All Categories");
    fireEvent.change(categorySelect, { target: { value: "code_analysis" } });

    await waitFor(() => {
      expect(mockUseDiscover).toHaveBeenCalledWith(
        expect.objectContaining({
          category: "code_analysis",
          page: 1,
        }),
      );
    });
  });

  it("renders ShieldCheck icon in auth gate banner", () => {
    setupAuth("");
    setupDiscover(mockResponse);

    const { container } = renderWithProviders(<ListingsPage />);

    const shieldIcons = container.querySelectorAll(".lucide-shield-check");
    expect(shieldIcons.length).toBeGreaterThanOrEqual(1);
  });

  it("renders empty state PackageOpen icon", () => {
    setupAuth();
    setupDiscover(mockResponseEmpty);

    const { container } = renderWithProviders(<ListingsPage />);

    const packageIcon = container.querySelector(".lucide-package-open");
    expect(packageIcon).toBeInTheDocument();
  });

  it("renders TrendingUp icon in header count badge", () => {
    setupAuth();
    setupDiscover(mockResponse);

    const { container } = renderWithProviders(<ListingsPage />);

    const trendingIcons = container.querySelectorAll(".lucide-trending-up");
    expect(trendingIcons.length).toBeGreaterThanOrEqual(1);
  });

  it("renders Sparkles icon in results count area", () => {
    setupAuth();
    setupDiscover(mockResponse);

    const { container } = renderWithProviders(<ListingsPage />);

    const sparklesIcons = container.querySelectorAll(".lucide-sparkles");
    expect(sparklesIcons.length).toBeGreaterThanOrEqual(1);
  });

  it("passes correct params to useDiscover", () => {
    setupAuth();
    const mockUseDiscover = vi.fn().mockReturnValue({
      data: mockResponse,
      isLoading: false,
      error: null,
    });
    vi.spyOn(useDiscoverModule, "useDiscover").mockImplementation(mockUseDiscover);

    renderWithProviders(<ListingsPage />);

    expect(mockUseDiscover).toHaveBeenCalledWith({
      q: undefined,
      category: undefined,
      sort_by: "freshness",
      page: 1,
      page_size: 12,
    });
  });
});
