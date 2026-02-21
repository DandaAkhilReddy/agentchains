import { describe, it, expect, vi, beforeEach } from "vitest";
import { screen, fireEvent, waitFor } from "@testing-library/react";
import { renderWithProviders } from "../../test/test-utils";
import ListingsPage from "../ListingsPage";
import * as useAuthModule from "../../hooks/useAuth";
import * as useDiscoverModule from "../../hooks/useDiscover";
import type { Listing, ListingListResponse } from "../../types/api";

// Mock hooks
vi.mock("../../hooks/useAuth");
vi.mock("../../hooks/useDiscover");

// Mock the Toast context
vi.mock("../../components/Toast", () => ({
  useToast: () => ({ toast: vi.fn() }),
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
    freshness_at: new Date(Date.now() - 1800000).toISOString(),
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
    freshness_at: new Date(Date.now() - 7200000).toISOString(),
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
    freshness_at: new Date(Date.now() - 86400000).toISOString(),
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

/* ── Tests ──────────────────────────────────────────────── */

describe("ListingsPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders marketplace page header", () => {
    vi.spyOn(useAuthModule, "useAuth").mockReturnValue({
      token: "test-jwt",
      login: vi.fn(),
      logout: vi.fn(),
      isAuthenticated: true,
    });
    vi.spyOn(useDiscoverModule, "useDiscover").mockReturnValue({
      data: mockResponse,
      isLoading: false,
      error: null,
    } as any);

    renderWithProviders(<ListingsPage />);

    expect(screen.getByText("Marketplace")).toBeInTheDocument();
    expect(screen.getByText("Discover and purchase cached computation results")).toBeInTheDocument();
  });

  it("shows listing cards with titles", () => {
    vi.spyOn(useAuthModule, "useAuth").mockReturnValue({
      token: "test-jwt",
      login: vi.fn(),
      logout: vi.fn(),
      isAuthenticated: true,
    });
    vi.spyOn(useDiscoverModule, "useDiscover").mockReturnValue({
      data: mockResponse,
      isLoading: false,
      error: null,
    } as any);

    renderWithProviders(<ListingsPage />);

    expect(screen.getByText("Web Search Results for AI Trends")).toBeInTheDocument();
    expect(screen.getByText("Code Analysis Report for React App")).toBeInTheDocument();
    expect(screen.getByText("Document Summary of Research Paper")).toBeInTheDocument();
  });

  it("shows auth gate banner when not authenticated", () => {
    vi.spyOn(useAuthModule, "useAuth").mockReturnValue({
      token: "",
      login: vi.fn(),
      logout: vi.fn(),
      isAuthenticated: false,
    });
    vi.spyOn(useDiscoverModule, "useDiscover").mockReturnValue({
      data: mockResponse,
      isLoading: false,
      error: null,
    } as any);

    renderWithProviders(<ListingsPage />);

    expect(
      screen.getByText("Connect your agent JWT in the Transactions tab to enable Express Buy"),
    ).toBeInTheDocument();
  });

  it("shows loading skeleton cards when loading", () => {
    vi.spyOn(useAuthModule, "useAuth").mockReturnValue({
      token: "test-jwt",
      login: vi.fn(),
      logout: vi.fn(),
      isAuthenticated: true,
    });
    vi.spyOn(useDiscoverModule, "useDiscover").mockReturnValue({
      data: undefined,
      isLoading: true,
      error: null,
    } as any);

    const { container } = renderWithProviders(<ListingsPage />);

    // Skeleton cards use animate-pulse class
    const skeletonElements = container.querySelectorAll(".animate-pulse");
    expect(skeletonElements.length).toBeGreaterThan(0);
  });

  it("shows empty state when no listings found", () => {
    vi.spyOn(useAuthModule, "useAuth").mockReturnValue({
      token: "test-jwt",
      login: vi.fn(),
      logout: vi.fn(),
      isAuthenticated: true,
    });
    vi.spyOn(useDiscoverModule, "useDiscover").mockReturnValue({
      data: mockResponseEmpty,
      isLoading: false,
      error: null,
    } as any);

    renderWithProviders(<ListingsPage />);

    expect(screen.getByText("No listings found")).toBeInTheDocument();
    expect(screen.getByText("Try adjusting your filters or search query")).toBeInTheDocument();
  });

  it("renders category filter select with correct options", () => {
    vi.spyOn(useAuthModule, "useAuth").mockReturnValue({
      token: "test-jwt",
      login: vi.fn(),
      logout: vi.fn(),
      isAuthenticated: true,
    });
    vi.spyOn(useDiscoverModule, "useDiscover").mockReturnValue({
      data: mockResponse,
      isLoading: false,
      error: null,
    } as any);

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
    vi.spyOn(useAuthModule, "useAuth").mockReturnValue({
      token: "test-jwt",
      login: vi.fn(),
      logout: vi.fn(),
      isAuthenticated: true,
    });
    vi.spyOn(useDiscoverModule, "useDiscover").mockReturnValue({
      data: mockResponse,
      isLoading: false,
      error: null,
    } as any);

    renderWithProviders(<ListingsPage />);

    const sortSelect = screen.getByDisplayValue("Freshest");
    expect(sortSelect).toBeInTheDocument();

    const options = sortSelect.querySelectorAll("option");
    expect(options).toHaveLength(4);
    expect(options[0]).toHaveTextContent("Freshest");
    expect(options[3]).toHaveTextContent("Highest Quality");
  });

  it("shows search input for listing search", () => {
    vi.spyOn(useAuthModule, "useAuth").mockReturnValue({
      token: "test-jwt",
      login: vi.fn(),
      logout: vi.fn(),
      isAuthenticated: true,
    });
    vi.spyOn(useDiscoverModule, "useDiscover").mockReturnValue({
      data: mockResponse,
      isLoading: false,
      error: null,
    } as any);

    renderWithProviders(<ListingsPage />);

    expect(screen.getByPlaceholderText("Search listings...")).toBeInTheDocument();
  });

  it("shows pagination when total exceeds 12", () => {
    vi.spyOn(useAuthModule, "useAuth").mockReturnValue({
      token: "test-jwt",
      login: vi.fn(),
      logout: vi.fn(),
      isAuthenticated: true,
    });
    vi.spyOn(useDiscoverModule, "useDiscover").mockReturnValue({
      data: mockResponseLarge,
      isLoading: false,
      error: null,
    } as any);

    renderWithProviders(<ListingsPage />);

    expect(screen.getByRole("button", { name: "Previous page" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Next page" })).toBeInTheDocument();
  });

  it("does not show pagination when total is 12 or less", () => {
    vi.spyOn(useAuthModule, "useAuth").mockReturnValue({
      token: "test-jwt",
      login: vi.fn(),
      logout: vi.fn(),
      isAuthenticated: true,
    });
    vi.spyOn(useDiscoverModule, "useDiscover").mockReturnValue({
      data: mockResponse,
      isLoading: false,
      error: null,
    } as any);

    renderWithProviders(<ListingsPage />);

    expect(screen.queryByRole("button", { name: "Previous page" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Next page" })).not.toBeInTheDocument();
  });

  it("shows listing count in header", () => {
    vi.spyOn(useAuthModule, "useAuth").mockReturnValue({
      token: "test-jwt",
      login: vi.fn(),
      logout: vi.fn(),
      isAuthenticated: true,
    });
    vi.spyOn(useDiscoverModule, "useDiscover").mockReturnValue({
      data: mockResponse,
      isLoading: false,
      error: null,
    } as any);

    renderWithProviders(<ListingsPage />);

    expect(screen.getByText("3 listings")).toBeInTheDocument();
  });
});
