import { describe, it, expect, vi, beforeEach } from "vitest";
import { screen, fireEvent, waitFor } from "@testing-library/react";
import { renderWithProviders } from "../../test/test-utils";
import ActionsPage from "../ActionsPage";
import * as useActionsModule from "../../hooks/useActions";
import type { WebMCPAction, ActionListResponse, ExecutionListResponse } from "../../hooks/useActions";

/* ── Mocks ── */

vi.mock("../../hooks/useActions");

vi.mock("../../components/AnimatedCounter", () => ({
  default: ({ value }: any) => <span>{value}</span>,
}));

// Mock the Toast hook
vi.mock("../../components/Toast", () => ({
  useToast: () => ({ toast: vi.fn() }),
  ToastProvider: ({ children }: any) => <>{children}</>,
}));

/* ── Test Data ── */

const mockActions: WebMCPAction[] = [
  {
    id: "action-001",
    title: "Web Scraper Pro",
    description: "Advanced web scraping with headless browser",
    price_per_execution: 0.5,
    tags: ["automation", "scraping", "data"],
    access_count: 1200,
    status: "active",
    domain: "scraper.example.com",
    category: "web_automation",
  },
  {
    id: "action-002",
    title: "AI Text Summarizer",
    description: "Summarize long text using AI models",
    price_per_execution: 0.25,
    tags: ["ai", "nlp"],
    access_count: 800,
    status: "active",
    domain: "ai.example.com",
    category: "ai_inference",
  },
  {
    id: "action-003",
    title: "Data Pipeline Runner",
    description: "Execute ETL data pipelines",
    price_per_execution: 1.0,
    tags: ["data", "finance"],
    access_count: 400,
    status: "beta",
    category: "data_extraction",
  },
];

const mockActionsResponse: ActionListResponse = {
  actions: mockActions,
  total: 3,
  page: 1,
  page_size: 12,
};

const mockActionsResponseEmpty: ActionListResponse = {
  actions: [],
  total: 0,
  page: 1,
  page_size: 12,
};

const mockActionsResponsePaginated: ActionListResponse = {
  actions: mockActions,
  total: 30,
  page: 1,
  page_size: 12,
};

const mockExecutionsResponse: ExecutionListResponse = {
  executions: [
    {
      id: "exec-001",
      action_id: "action-001",
      status: "completed",
      amount: 0.5,
      created_at: new Date(Date.now() - 60000).toISOString(),
      proof_verified: true,
    },
    {
      id: "exec-002",
      action_id: "action-002",
      status: "failed",
      amount: 0.25,
      created_at: new Date(Date.now() - 120000).toISOString(),
      proof_verified: false,
    },
  ],
  total: 2,
  page: 1,
  page_size: 20,
};

const mockEmptyExecutionsResponse: ExecutionListResponse = {
  executions: [],
  total: 0,
  page: 1,
  page_size: 20,
};

/* ── Setup ── */

describe("ActionsPage", () => {
  const mockExecuteMutate = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();

    vi.spyOn(useActionsModule, "useActions").mockReturnValue({
      data: mockActionsResponse,
      isLoading: false,
      error: null,
    } as any);

    vi.spyOn(useActionsModule, "useExecuteAction").mockReturnValue({
      mutate: mockExecuteMutate,
      isPending: false,
    } as any);

    vi.spyOn(useActionsModule, "useExecutions").mockReturnValue({
      data: mockExecutionsResponse,
    } as any);
  });

  it("renders the actions page header", () => {
    renderWithProviders(<ActionsPage />);

    expect(screen.getByText("WebMCP Actions")).toBeInTheDocument();
    expect(
      screen.getByText(
        "Discover and execute WebMCP-powered actions across the agent network",
      ),
    ).toBeInTheDocument();
  });

  it("displays action cards with titles and descriptions", () => {
    renderWithProviders(<ActionsPage />);

    expect(screen.getByText("Web Scraper Pro")).toBeInTheDocument();
    expect(screen.getByText("AI Text Summarizer")).toBeInTheDocument();
    expect(screen.getByText("Data Pipeline Runner")).toBeInTheDocument();

    expect(
      screen.getByText("Advanced web scraping with headless browser"),
    ).toBeInTheDocument();
  });

  it("shows search input and allows typing", () => {
    renderWithProviders(<ActionsPage />);

    const searchInput = screen.getByPlaceholderText("Search actions...");
    expect(searchInput).toBeInTheDocument();

    fireEvent.change(searchInput, { target: { value: "scraper" } });
    expect(searchInput).toHaveValue("scraper");
  });

  it("displays execute buttons on action cards", () => {
    renderWithProviders(<ActionsPage />);

    // Each ActionCard has an "Execute" button
    const executeButtons = screen.getAllByText("Execute");
    expect(executeButtons.length).toBe(3);
  });

  it("shows loading skeleton when data is loading", () => {
    vi.spyOn(useActionsModule, "useActions").mockReturnValue({
      data: undefined,
      isLoading: true,
      error: null,
    } as any);

    const { container } = renderWithProviders(<ActionsPage />);

    // SkeletonCard renders divs with animate-pulse
    const pulsingElements = container.querySelectorAll(".animate-pulse");
    expect(pulsingElements.length).toBeGreaterThan(0);
  });

  it("shows empty state when no actions returned", () => {
    vi.spyOn(useActionsModule, "useActions").mockReturnValue({
      data: mockActionsResponseEmpty,
      isLoading: false,
      error: null,
    } as any);

    renderWithProviders(<ActionsPage />);

    expect(screen.getByText("No actions found")).toBeInTheDocument();
    expect(
      screen.getByText("Try adjusting your filters or search query"),
    ).toBeInTheDocument();
  });

  it("displays category filter with all options", () => {
    renderWithProviders(<ActionsPage />);

    const categorySelect = screen.getByDisplayValue("All Categories");
    expect(categorySelect).toBeInTheDocument();

    const options = categorySelect.querySelectorAll("option");
    expect(options).toHaveLength(6);
    expect(options[0]).toHaveTextContent("All Categories");
    expect(options[1]).toHaveTextContent("Web Automation");
    expect(options[2]).toHaveTextContent("Data Extraction");
    expect(options[3]).toHaveTextContent("AI Inference");
  });

  it("displays price filter with all options", () => {
    renderWithProviders(<ActionsPage />);

    const priceSelect = screen.getByDisplayValue("Any Price");
    expect(priceSelect).toBeInTheDocument();

    const options = priceSelect.querySelectorAll("option");
    expect(options).toHaveLength(5);
    expect(options[0]).toHaveTextContent("Any Price");
    expect(options[1]).toHaveTextContent("Under $0.10");
  });

  it("renders the Execution History section", () => {
    renderWithProviders(<ActionsPage />);

    expect(screen.getByText("Execution History")).toBeInTheDocument();
    expect(
      screen.getByText("Recent action executions and their results"),
    ).toBeInTheDocument();
  });

  it("shows pagination when total exceeds page size", () => {
    vi.spyOn(useActionsModule, "useActions").mockReturnValue({
      data: mockActionsResponsePaginated,
      isLoading: false,
      error: null,
    } as any);

    renderWithProviders(<ActionsPage />);

    // 30 actions / 12 per page = 3 pages -> pagination should show
    expect(
      screen.getByRole("button", { name: "Previous page" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Next page" }),
    ).toBeInTheDocument();
  });

  it("does not show pagination when total fits in one page", () => {
    renderWithProviders(<ActionsPage />);

    // 3 actions / 12 per page = 1 page -> no pagination
    expect(
      screen.queryByRole("button", { name: "Previous page" }),
    ).not.toBeInTheDocument();
  });

  it("displays total actions badge in header", () => {
    renderWithProviders(<ActionsPage />);

    expect(screen.getByText("3 actions")).toBeInTheDocument();
  });

  it("displays singular 'action' for count of 1", () => {
    vi.spyOn(useActionsModule, "useActions").mockReturnValue({
      data: {
        actions: [mockActions[0]],
        total: 1,
        page: 1,
        page_size: 12,
      },
      isLoading: false,
      error: null,
    } as any);

    renderWithProviders(<ActionsPage />);

    expect(screen.getByText("1 action")).toBeInTheDocument();
  });

  it("shows execution history entries in table", () => {
    renderWithProviders(<ActionsPage />);

    // The execution history shows status badges
    expect(screen.getByText("completed")).toBeInTheDocument();
    expect(screen.getByText("failed")).toBeInTheDocument();
  });

  it("shows empty execution history message when no executions", () => {
    vi.spyOn(useActionsModule, "useExecutions").mockReturnValue({
      data: mockEmptyExecutionsResponse,
    } as any);

    renderWithProviders(<ActionsPage />);

    expect(screen.getByText("No executions yet")).toBeInTheDocument();
  });

  it("changes category filter and resets page", async () => {
    const mockUseActions = vi.fn().mockReturnValue({
      data: mockActionsResponse,
      isLoading: false,
      error: null,
    });
    vi.spyOn(useActionsModule, "useActions").mockImplementation(mockUseActions);

    renderWithProviders(<ActionsPage />);

    const categorySelect = screen.getByDisplayValue("All Categories");
    fireEvent.change(categorySelect, { target: { value: "web_automation" } });

    await waitFor(() => {
      expect(mockUseActions).toHaveBeenCalledWith(
        undefined,
        "web_automation",
        undefined,
        1,
      );
    });
  });
});
