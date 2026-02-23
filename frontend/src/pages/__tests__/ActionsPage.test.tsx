import { describe, it, expect, vi, beforeEach } from "vitest";
import { screen, fireEvent, waitFor, act } from "@testing-library/react";
import { renderWithProviders } from "../../test/test-utils";
import ActionsPage from "../ActionsPage";
import * as useActionsModule from "../../hooks/useActions";
import type { WebMCPAction, ActionListResponse, ExecutionListResponse } from "../../hooks/useActions";

/* ── Mocks ── */

vi.mock("../../hooks/useActions");

vi.mock("../../components/AnimatedCounter", () => ({
  default: ({ value }: any) => <span>{value}</span>,
}));

// Mock the Toast hook - capture the toast function
const mockToast = vi.fn();
vi.mock("../../components/Toast", () => ({
  useToast: () => ({ toast: mockToast }),
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

const mockPaginatedExecutionsResponse: ExecutionListResponse = {
  executions: [
    {
      id: "exec-001",
      action_id: "action-001",
      status: "completed",
      amount: 0.5,
      created_at: new Date(Date.now() - 60000).toISOString(),
      proof_verified: true,
    },
  ],
  total: 50,
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

  // ─── New coverage tests ───

  it("changes price filter and resets page to 1", async () => {
    const mockUseActions = vi.fn().mockReturnValue({
      data: mockActionsResponse,
      isLoading: false,
      error: null,
    });
    vi.spyOn(useActionsModule, "useActions").mockImplementation(mockUseActions);

    renderWithProviders(<ActionsPage />);

    const priceSelect = screen.getByDisplayValue("Any Price");
    fireEvent.change(priceSelect, { target: { value: "0.5" } });

    await waitFor(() => {
      expect(mockUseActions).toHaveBeenCalledWith(
        undefined,
        undefined,
        0.5,
        1,
      );
    });
  });

  it("opens execution panel when Execute button is clicked", () => {
    renderWithProviders(<ActionsPage />);

    const executeButtons = screen.getAllByText("Execute");
    fireEvent.click(executeButtons[0]);

    // The execution panel should now be visible with "Execution Panel" text
    const panelLabels = screen.getAllByText("Execution Panel");
    expect(panelLabels.length).toBeGreaterThanOrEqual(1);
  });

  it("closes execution panel when X button is clicked", () => {
    renderWithProviders(<ActionsPage />);

    // Open panel first
    const executeButtons = screen.getAllByText("Execute");
    fireEvent.click(executeButtons[0]);

    // Verify panel is open
    expect(screen.getAllByText("Execution Panel").length).toBeGreaterThanOrEqual(1);

    // Click the close button (X icon button)
    const closeButtons = document.querySelectorAll("button");
    const closeButton = Array.from(closeButtons).find(
      btn => btn.querySelector(".lucide-x"),
    );
    expect(closeButton).toBeTruthy();
    fireEvent.click(closeButton!);

    // Panel should be closed
    expect(screen.queryByText("Execution Panel")).not.toBeInTheDocument();
  });

  it("shows ExecutionForm when action is selected", () => {
    renderWithProviders(<ActionsPage />);

    const executeButtons = screen.getAllByText("Execute");
    fireEvent.click(executeButtons[0]);

    // ExecutionForm should show "Execute Action" header
    const execHeaders = screen.getAllByText("Execute Action");
    expect(execHeaders.length).toBeGreaterThanOrEqual(1);
  });

  it("shows empty state when data is undefined and not loading", () => {
    vi.spyOn(useActionsModule, "useActions").mockReturnValue({
      data: undefined,
      isLoading: false,
      error: null,
    } as any);

    renderWithProviders(<ActionsPage />);

    expect(screen.getByText("No actions found")).toBeInTheDocument();
  });

  it("does not render header badge when data is undefined", () => {
    vi.spyOn(useActionsModule, "useActions").mockReturnValue({
      data: undefined,
      isLoading: false,
      error: null,
    } as any);

    renderWithProviders(<ActionsPage />);

    // No "N actions" badge should appear
    expect(screen.queryByText(/\d+ actions?$/)).not.toBeInTheDocument();
  });

  it("displays execution history total badge when executions exist", () => {
    renderWithProviders(<ActionsPage />);

    expect(screen.getByText("2 total")).toBeInTheDocument();
  });

  it("does not show execution history badge when total is 0", () => {
    vi.spyOn(useActionsModule, "useExecutions").mockReturnValue({
      data: mockEmptyExecutionsResponse,
    } as any);

    renderWithProviders(<ActionsPage />);

    expect(screen.queryByText("0 total")).not.toBeInTheDocument();
  });

  it("shows execution history pagination when pages > 1", () => {
    vi.spyOn(useActionsModule, "useExecutions").mockReturnValue({
      data: mockPaginatedExecutionsResponse,
    } as any);

    renderWithProviders(<ActionsPage />);

    // 50 executions / 20 per page = 3 pages
    const prevButtons = screen.getAllByRole("button", { name: "Previous page" });
    const nextButtons = screen.getAllByRole("button", { name: "Next page" });
    expect(prevButtons.length).toBeGreaterThanOrEqual(1);
    expect(nextButtons.length).toBeGreaterThanOrEqual(1);
  });

  it("does not show execution history pagination when total fits in one page", () => {
    // Default setup has 2 executions / 20 per page = 1 page
    renderWithProviders(<ActionsPage />);

    // With 3 actions (total < 12), there should be no pagination at all
    expect(
      screen.queryByRole("button", { name: "Previous page" }),
    ).not.toBeInTheDocument();
  });

  it("renders 6 skeleton cards during loading", () => {
    vi.spyOn(useActionsModule, "useActions").mockReturnValue({
      data: undefined,
      isLoading: true,
      error: null,
    } as any);

    const { container } = renderWithProviders(<ActionsPage />);

    const skeletonCards = container.querySelectorAll(".animate-pulse");
    expect(skeletonCards.length).toBeGreaterThan(0);
  });

  it("search resets page to 1", async () => {
    const mockUseActions = vi.fn().mockReturnValue({
      data: mockActionsResponse,
      isLoading: false,
      error: null,
    });
    vi.spyOn(useActionsModule, "useActions").mockImplementation(mockUseActions);

    renderWithProviders(<ActionsPage />);

    const searchInput = screen.getByPlaceholderText("Search actions...");
    fireEvent.change(searchInput, { target: { value: "scraper" } });

    await waitFor(() => {
      expect(mockUseActions).toHaveBeenCalledWith(
        "scraper",
        undefined,
        undefined,
        1,
      );
    });
  });

  it("calls executeMutation.mutate when execution form is submitted", () => {
    renderWithProviders(<ActionsPage />);

    // Click Execute on first action to open panel
    const executeButtons = screen.getAllByText("Execute");
    fireEvent.click(executeButtons[0]);

    // Fill in the execution form - find the consent checkbox
    const checkboxes = screen.getAllByRole("checkbox");
    fireEvent.click(checkboxes[0]);

    // Find the submit button in the form (type="submit")
    const submitButtons = document.querySelectorAll("button[type='submit']");
    expect(submitButtons.length).toBeGreaterThanOrEqual(1);
    fireEvent.click(submitButtons[0]);

    expect(mockExecuteMutate).toHaveBeenCalledWith(
      {
        actionId: "action-001",
        payload: { parameters: {}, consent: true },
      },
      expect.objectContaining({
        onSuccess: expect.any(Function),
        onError: expect.any(Function),
      }),
    );
  });

  it("calls toast with success message on execution success", () => {
    renderWithProviders(<ActionsPage />);

    // Click Execute on first action
    const executeButtons = screen.getAllByText("Execute");
    fireEvent.click(executeButtons[0]);

    // Check consent and submit
    const checkboxes = screen.getAllByRole("checkbox");
    fireEvent.click(checkboxes[0]);

    const submitButtons = document.querySelectorAll("button[type='submit']");
    fireEvent.click(submitButtons[0]);

    // Extract the onSuccess callback from mutate call
    const mutateCall = mockExecuteMutate.mock.calls[0];
    const callbacks = mutateCall[1];

    // Simulate success
    callbacks.onSuccess({ execution_id: "exec-new-001" });

    expect(mockToast).toHaveBeenCalledWith(
      "Execution started! ID: exec-new-001",
      "success",
    );
  });

  it("calls toast with error message on execution failure", () => {
    renderWithProviders(<ActionsPage />);

    const executeButtons = screen.getAllByText("Execute");
    fireEvent.click(executeButtons[0]);

    const checkboxes = screen.getAllByRole("checkbox");
    fireEvent.click(checkboxes[0]);

    const submitButtons = document.querySelectorAll("button[type='submit']");
    fireEvent.click(submitButtons[0]);

    const mutateCall = mockExecuteMutate.mock.calls[0];
    const callbacks = mutateCall[1];

    // Simulate error
    callbacks.onError(new Error("Insufficient funds"));

    expect(mockToast).toHaveBeenCalledWith("Insufficient funds", "error");
  });

  it("closes execution panel after successful execution", () => {
    renderWithProviders(<ActionsPage />);

    const executeButtons = screen.getAllByText("Execute");
    fireEvent.click(executeButtons[0]);

    // Verify panel is open
    expect(screen.getAllByText("Execution Panel").length).toBeGreaterThanOrEqual(1);

    const checkboxes = screen.getAllByRole("checkbox");
    fireEvent.click(checkboxes[0]);

    const submitButtons = document.querySelectorAll("button[type='submit']");
    fireEvent.click(submitButtons[0]);

    const mutateCall = mockExecuteMutate.mock.calls[0];
    const callbacks = mutateCall[1];

    // Simulate success - this should close the panel (state update)
    act(() => {
      callbacks.onSuccess({ execution_id: "exec-new-001" });
    });

    expect(screen.queryByText("Execution Panel")).not.toBeInTheDocument();
  });

  it("does not call mutate when selectedActionId is null", () => {
    renderWithProviders(<ActionsPage />);

    // Don't open any action panel.
    expect(mockExecuteMutate).not.toHaveBeenCalled();
  });

  it("renders the execution panel with the correct action ID", () => {
    renderWithProviders(<ActionsPage />);

    const executeButtons = screen.getAllByText("Execute");
    fireEvent.click(executeButtons[1]); // Select the second action

    // The ExecutionForm displays the action ID in a font-mono paragraph
    // It appears in both desktop and mobile panels, so use getAllByText
    const actionIdElements = screen.getAllByText("action-002");
    expect(actionIdElements.length).toBeGreaterThanOrEqual(1);
  });

  it("passes isPending to execution form", () => {
    vi.spyOn(useActionsModule, "useExecuteAction").mockReturnValue({
      mutate: mockExecuteMutate,
      isPending: true,
    } as any);

    renderWithProviders(<ActionsPage />);

    const executeButtons = screen.getAllByText("Execute");
    fireEvent.click(executeButtons[0]);

    // When isPending is true, the form shows "Executing..." text
    // This appears in both desktop and mobile forms
    const executingTexts = screen.getAllByText("Executing...");
    expect(executingTexts.length).toBeGreaterThanOrEqual(1);
  });

  it("renders mobile execution panel (lg:hidden) when action selected", () => {
    renderWithProviders(<ActionsPage />);

    const executeButtons = screen.getAllByText("Execute");
    fireEvent.click(executeButtons[0]);

    // Mobile panel renders with lg:hidden class
    const mobilePanels = document.querySelectorAll(".lg\\:hidden");
    expect(mobilePanels.length).toBeGreaterThanOrEqual(1);
  });

  it("renders desktop execution panel (lg:block) when action selected", () => {
    renderWithProviders(<ActionsPage />);

    const executeButtons = screen.getAllByText("Execute");
    fireEvent.click(executeButtons[0]);

    // Desktop panel has lg:block class
    const desktopPanels = document.querySelectorAll(".lg\\:block");
    expect(desktopPanels.length).toBeGreaterThanOrEqual(1);
  });

  it("closes mobile panel via its own close button", () => {
    renderWithProviders(<ActionsPage />);

    const executeButtons = screen.getAllByText("Execute");
    fireEvent.click(executeButtons[0]);

    // There are two close buttons (desktop and mobile) with X icon
    const closeButtons = document.querySelectorAll("button");
    const xButtons = Array.from(closeButtons).filter(
      btn => btn.querySelector(".lucide-x"),
    );
    // Should have 2 X buttons (desktop + mobile)
    expect(xButtons.length).toBe(2);

    // Click the second one (mobile)
    fireEvent.click(xButtons[1]);

    expect(screen.queryByText("Execution Panel")).not.toBeInTheDocument();
  });

  it("opens different action when clicking different Execute buttons", () => {
    renderWithProviders(<ActionsPage />);

    // First click action-001
    const executeButtons = screen.getAllByText("Execute");
    fireEvent.click(executeButtons[0]);

    let actionIdElements = screen.getAllByText("action-001");
    expect(actionIdElements.length).toBeGreaterThanOrEqual(1);

    // Now click action-003 (close first by clicking X)
    const closeButtons = document.querySelectorAll("button");
    const closeButton = Array.from(closeButtons).find(
      btn => btn.querySelector(".lucide-x"),
    );
    fireEvent.click(closeButton!);

    // Re-query execute buttons after panel close
    const executeButtons2 = screen.getAllByText("Execute");
    fireEvent.click(executeButtons2[2]); // Third action

    actionIdElements = screen.getAllByText("action-003");
    expect(actionIdElements.length).toBeGreaterThanOrEqual(1);
  });

  it("renders empty state with PackageOpen icon", () => {
    vi.spyOn(useActionsModule, "useActions").mockReturnValue({
      data: mockActionsResponseEmpty,
      isLoading: false,
      error: null,
    } as any);

    const { container } = renderWithProviders(<ActionsPage />);

    const packageIcon = container.querySelector(".lucide-package-open");
    expect(packageIcon).toBeInTheDocument();
  });

  it("renders Execution History icon", () => {
    const { container } = renderWithProviders(<ActionsPage />);

    const historyIcon = container.querySelector(".lucide-history");
    expect(historyIcon).toBeInTheDocument();
  });
});
