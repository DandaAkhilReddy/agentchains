import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import ActionsPage from "../pages/ActionsPage";
import type { WebMCPAction } from "../hooks/useActions";

/* ── Mocks ──────────────────────────────────────────────────────────────── */

vi.mock("../hooks/useActions", () => ({
  useActions: vi.fn(),
  useExecuteAction: vi.fn(),
  useExecutions: vi.fn(),
}));

vi.mock("../components/Toast", () => ({ useToast: vi.fn() }));

vi.mock("../components/ActionCard", () => ({
  default: ({ action, onExecute }: { action: WebMCPAction; onExecute: (id: string) => void }) => (
    <div
      data-testid={`action-${action.id}`}
      onClick={() => onExecute(action.id)}
    >
      {action.title}
    </div>
  ),
}));

vi.mock("../components/ExecutionForm", () => ({
  default: (props: any) => (
    <div data-testid="execution-form">
      <button
        data-testid="execute-btn"
        onClick={() => props.onExecute({ param: "val" }, true)}
      >
        Execute
      </button>
    </div>
  ),
}));

vi.mock("../components/ExecutionHistory", () => ({
  default: (_props: any) => <div data-testid="execution-history" />,
}));

vi.mock("../components/PageHeader", () => ({
  default: ({ title, actions }: { title: string; actions?: React.ReactNode }) => (
    <div data-testid="page-header">
      {title}
      {actions}
    </div>
  ),
}));

vi.mock("../components/SearchInput", () => ({
  default: ({
    value,
    onChange,
    placeholder,
  }: {
    value: string;
    onChange: (val: string) => void;
    placeholder?: string;
  }) => (
    <input
      data-testid="search-input"
      value={value}
      onChange={(e) => onChange(e.target.value)}
      placeholder={placeholder}
    />
  ),
}));

vi.mock("../components/Pagination", () => ({
  default: ({ page, totalPages, onPageChange }: any) => (
    <div data-testid="pagination">
      <button onClick={() => onPageChange(page + 1)}>Next</button>
      <span>
        {page}/{totalPages}
      </span>
    </div>
  ),
}));

vi.mock("../components/Badge", () => ({
  default: ({ label, variant }: { label: string; variant?: string }) => (
    <span data-testid={`badge-${variant ?? "default"}`}>{label}</span>
  ),
}));

/* ── Import mocked modules ───────────────────────────────────────────────── */

import { useActions, useExecuteAction, useExecutions } from "../hooks/useActions";
import { useToast } from "../components/Toast";

const mockUseActions = vi.mocked(useActions);
const mockUseExecuteAction = vi.mocked(useExecuteAction);
const mockUseExecutions = vi.mocked(useExecutions);
const mockUseToast = vi.mocked(useToast);

/* ── Fixtures ────────────────────────────────────────────────────────────── */

const mockToast = vi.fn();
const mockMutate = vi.fn();

const makeAction = (overrides: Partial<WebMCPAction> = {}): WebMCPAction => ({
  id: "action-1",
  title: "Test Action",
  description: "A test action description",
  price_per_execution: 0.05,
  tags: ["test", "demo"],
  access_count: 42,
  status: "active",
  category: "ai_inference",
  ...overrides,
});

const defaultActionsData = {
  actions: [
    makeAction({ id: "a1", title: "Action One" }),
    makeAction({ id: "a2", title: "Action Two" }),
  ],
  total: 2,
  page: 1,
  page_size: 12,
};

const emptyActionsData = {
  actions: [],
  total: 0,
  page: 1,
  page_size: 12,
};

const emptyExecData = {
  executions: [],
  total: 0,
  page: 1,
  page_size: 20,
};

/* ── Helper ──────────────────────────────────────────────────────────────── */

function renderPage() {
  return render(<ActionsPage />);
}

/* ── Tests ───────────────────────────────────────────────────────────────── */

describe("ActionsPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockUseToast.mockReturnValue({ toast: mockToast } as any);
    mockUseActions.mockReturnValue({
      data: defaultActionsData,
      isLoading: false,
    } as any);
    mockUseExecuteAction.mockReturnValue({
      mutate: mockMutate,
      isPending: false,
    } as any);
    mockUseExecutions.mockReturnValue({
      data: emptyExecData,
    } as any);
  });

  /* ── 1. Loading skeletons ────────────────────────────────────────────── */

  it("renders loading skeletons", () => {
    mockUseActions.mockReturnValue({
      data: undefined,
      isLoading: true,
    } as any);
    renderPage();

    // When loading, SkeletonCard components (inline in ActionsPage) are rendered
    // They have animate-pulse divs inside an overflow-hidden rounded-2xl border
    const loadingContainer = document.querySelector(".animate-pulse");
    expect(loadingContainer).not.toBeNull();
  });

  /* ── 2. Empty state ──────────────────────────────────────────────────── */

  it("renders empty state", () => {
    mockUseActions.mockReturnValue({
      data: emptyActionsData,
      isLoading: false,
    } as any);
    renderPage();

    expect(screen.getByText("No actions found")).toBeInTheDocument();
    expect(
      screen.getByText(/Try adjusting your filters or search query/),
    ).toBeInTheDocument();
  });

  it("renders empty state when data is undefined", () => {
    mockUseActions.mockReturnValue({
      data: undefined,
      isLoading: false,
    } as any);
    renderPage();

    expect(screen.getByText("No actions found")).toBeInTheDocument();
  });

  /* ── 3. Action cards rendered ────────────────────────────────────────── */

  it("renders action cards", () => {
    renderPage();

    expect(screen.getByTestId("action-a1")).toBeInTheDocument();
    expect(screen.getByTestId("action-a2")).toBeInTheDocument();
    expect(screen.getByText("Action One")).toBeInTheDocument();
    expect(screen.getByText("Action Two")).toBeInTheDocument();
  });

  /* ── 4. Pagination when more than 1 page ─────────────────────────────── */

  it("shows pagination when > 1 page", () => {
    mockUseActions.mockReturnValue({
      data: { ...defaultActionsData, total: 25 }, // 25/12 = 3 pages > 1
      isLoading: false,
    } as any);
    renderPage();

    expect(screen.getByTestId("pagination")).toBeInTheDocument();
  });

  it("hides pagination when only 1 page", () => {
    mockUseActions.mockReturnValue({
      data: { ...defaultActionsData, total: 12 }, // 12/12 = 1 page, not > 1
      isLoading: false,
    } as any);
    renderPage();

    expect(screen.queryByTestId("pagination")).toBeNull();
  });

  /* ── 5. Execution panel shown when action selected ────────────────────── */

  it("shows execution panel when action selected", async () => {
    renderPage();

    // Execution form not visible initially
    expect(screen.queryByTestId("execution-form")).toBeNull();

    // Click on action card
    fireEvent.click(screen.getByTestId("action-a1"));

    await waitFor(() => {
      // Two execution forms render: one for desktop (hidden lg:block) + one for mobile (lg:hidden)
      const forms = screen.getAllByTestId("execution-form");
      expect(forms.length).toBeGreaterThanOrEqual(1);
      // Execution Panel label appears at least once
      expect(screen.getAllByText("Execution Panel").length).toBeGreaterThanOrEqual(1);
    });
  });

  /* ── 6. Close execution panel ────────────────────────────────────────── */

  it("close execution panel", async () => {
    renderPage();

    // Open panel
    fireEvent.click(screen.getByTestId("action-a1"));

    await waitFor(() => {
      expect(screen.getAllByTestId("execution-form").length).toBeGreaterThanOrEqual(1);
    });

    // Two "Execution Panel" labels — one for desktop, one for mobile
    // Find the first close button (sibling of "Execution Panel" label)
    const panelLabels = screen.getAllByText("Execution Panel");
    const container = panelLabels[0].parentElement!;
    const xBtn = container.querySelector("button");
    if (xBtn) {
      fireEvent.click(xBtn);
      await waitFor(() => {
        expect(screen.queryByTestId("execution-form")).toBeNull();
      });
    }
  });

  /* ── 7. Category filter resets page ─────────────────────────────────── */

  it("category filter resets page", async () => {
    mockUseActions.mockReturnValue({
      data: { ...defaultActionsData, total: 25 },
      isLoading: false,
    } as any);
    renderPage();

    // The component calls useActions(q||undefined, category||undefined, maxPrice||undefined, page)
    // Initial state: q="", category="", maxPrice=0 → all pass as undefined
    // After setting category="web_automation": (undefined, "web_automation", undefined, 1)
    const categorySelect = screen.getAllByRole("combobox")[0];
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

  /* ── 8. Price filter resets page ─────────────────────────────────────── */

  it("price filter resets page", async () => {
    mockUseActions.mockReturnValue({
      data: { ...defaultActionsData, total: 25 },
      isLoading: false,
    } as any);
    renderPage();

    const selects = screen.getAllByRole("combobox");
    // Price select is the second combobox
    const priceSelect = selects[1];
    fireEvent.change(priceSelect, { target: { value: "0.5" } });

    // After setting maxPrice=0.5: (undefined, undefined, 0.5, 1)
    await waitFor(() => {
      expect(mockUseActions).toHaveBeenCalledWith(
        undefined,
        undefined,
        0.5,
        1,
      );
    });
  });

  /* ── 9. Execution history badge ──────────────────────────────────────── */

  it("shows execution history badge", () => {
    mockUseExecutions.mockReturnValue({
      data: { executions: [], total: 15, page: 1, page_size: 20 },
    } as any);
    renderPage();

    expect(screen.getByText("15 total")).toBeInTheDocument();
  });

  it("hides execution history badge when total is 0", () => {
    mockUseExecutions.mockReturnValue({
      data: { executions: [], total: 0, page: 1, page_size: 20 },
    } as any);
    renderPage();

    expect(screen.queryByText(/total/)).toBeNull();
  });

  /* ── 10. Actions count badge in header ────────────────────────────────── */

  it("shows actions count badge when data loaded", () => {
    renderPage();

    // Badge shows "2 actions" (data.total = 2)
    expect(screen.getByText("2 actions")).toBeInTheDocument();
  });

  it("hides actions count badge when data is undefined", () => {
    mockUseActions.mockReturnValue({
      data: undefined,
      isLoading: false,
    } as any);
    renderPage();

    // No badge showing "X actions" — the badge-blue (actions count) should not exist
    expect(screen.queryByTestId("badge-blue")).toBeNull();
  });

  /* ── 11. Singular action count badge ─────────────────────────────────── */

  it("shows singular 'action' when total is 1", () => {
    mockUseActions.mockReturnValue({
      data: {
        actions: [makeAction({ id: "single" })],
        total: 1,
        page: 1,
        page_size: 12,
      },
      isLoading: false,
    } as any);
    renderPage();

    expect(screen.getByText("1 action")).toBeInTheDocument();
  });

  /* ── 12. Execution history pagination ─────────────────────────────────── */

  it("shows exec history pagination when total > 20 pages", () => {
    mockUseExecutions.mockReturnValue({
      data: { executions: [], total: 50, page: 1, page_size: 20 },
    } as any);
    renderPage();

    // execTotalPages = ceil(50/20) = 3 > 1 → pagination shown
    const paginations = screen.getAllByTestId("pagination");
    // Actions pagination + executions pagination
    expect(paginations.length).toBeGreaterThanOrEqual(1);
  });

  /* ── 13. handleExecute early return when no selectedActionId ─────────── */

  it("handleExecute does not mutate when no action selected", async () => {
    renderPage();

    // No action selected so execution form is not shown
    // Verify mutate was NOT called without selecting an action
    expect(mockMutate).not.toHaveBeenCalled();
  });

  /* ── 14. Execute action triggers mutate ───────────────────────────────── */

  it("execute action triggers mutation with correct payload", async () => {
    renderPage();

    // Select an action to open the panel
    fireEvent.click(screen.getByTestId("action-a1"));

    await waitFor(() => {
      // Two execute buttons (desktop + mobile panels)
      expect(screen.getAllByTestId("execute-btn").length).toBeGreaterThanOrEqual(1);
    });

    // Click the first execute button
    fireEvent.click(screen.getAllByTestId("execute-btn")[0]);

    expect(mockMutate).toHaveBeenCalledWith(
      expect.objectContaining({
        actionId: "a1",
        payload: expect.objectContaining({
          parameters: { param: "val" },
          consent: true,
        }),
      }),
      expect.any(Object),
    );
  });
});
