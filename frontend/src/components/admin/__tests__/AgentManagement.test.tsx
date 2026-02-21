import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import AgentManagement, { type AdminAgent } from "../AgentManagement";

/* ------------------------------------------------------------------ */
/*  Factory helpers                                                    */
/* ------------------------------------------------------------------ */

const mockAgent = (overrides?: Partial<AdminAgent>): AdminAgent => ({
  agent_id: "aaaabbbb-cccc-dddd-eeee-ffffffffffff",
  agent_name: "TestAgent",
  status: "active",
  agent_type: "worker",
  trust_status: "verified",
  trust_tier: "T2",
  trust_score: 0.85,
  money_received_usd: 1250.5,
  info_used_count: 42,
  other_agents_served_count: 7,
  data_served_bytes: 102400,
  created_at: "2026-01-15T10:00:00Z",
  last_seen_at: "2026-02-20T12:00:00Z",
  ...overrides,
});

const defaultProps = {
  agents: [mockAgent()],
  total: 1,
  page: 1,
  pageSize: 10,
  isLoading: false,
  onPageChange: vi.fn(),
  onActivate: vi.fn(),
  onDeactivate: vi.fn(),
  onViewDetails: vi.fn(),
};

/* ------------------------------------------------------------------ */
/*  Tests                                                              */
/* ------------------------------------------------------------------ */

describe("AgentManagement", () => {
  /* 1. Renders table structure */
  it("renders agent management table with header and columns", () => {
    const { container } = render(<AgentManagement {...defaultProps} />);

    expect(screen.getByText("Agent Management")).toBeInTheDocument();
    expect(screen.getByText("1 total agent")).toBeInTheDocument();

    const table = container.querySelector("table");
    expect(table).toBeInTheDocument();

    // Column headers
    expect(screen.getByText("Agent")).toBeInTheDocument();
    expect(screen.getByText("Status")).toBeInTheDocument();
    expect(screen.getByText("Trust")).toBeInTheDocument();
    expect(screen.getByText("Revenue")).toBeInTheDocument();
    expect(screen.getByText("Served")).toBeInTheDocument();
    expect(screen.getByText("Actions")).toBeInTheDocument();
  });

  /* 2. Displays agent names and statuses */
  it("displays agent names and statuses", () => {
    const agents = [
      mockAgent({ agent_id: "id-1", agent_name: "Alpha", status: "active" }),
      mockAgent({
        agent_id: "id-2",
        agent_name: "Bravo",
        status: "inactive",
      }),
    ];
    render(
      <AgentManagement {...defaultProps} agents={agents} total={2} />,
    );

    expect(screen.getByText("Alpha")).toBeInTheDocument();
    expect(screen.getByText("Bravo")).toBeInTheDocument();
    expect(screen.getByText("active")).toBeInTheDocument();
    expect(screen.getByText("inactive")).toBeInTheDocument();
  });

  /* 3. Search input renders and accepts text */
  it("renders a search input that accepts text", () => {
    render(<AgentManagement {...defaultProps} />);

    const input = screen.getByPlaceholderText(
      "Search agents by name, ID, or status...",
    );
    expect(input).toBeInTheDocument();

    fireEvent.change(input, { target: { value: "hello" } });
    expect(input).toHaveValue("hello");
  });

  /* 4. Filters agents by search term */
  it("filters agents by search term on name", () => {
    const agents = [
      mockAgent({ agent_id: "id-1", agent_name: "Alpha" }),
      mockAgent({ agent_id: "id-2", agent_name: "Bravo" }),
      mockAgent({ agent_id: "id-3", agent_name: "Charlie" }),
    ];
    render(
      <AgentManagement {...defaultProps} agents={agents} total={3} />,
    );

    const input = screen.getByPlaceholderText(
      "Search agents by name, ID, or status...",
    );
    fireEvent.change(input, { target: { value: "bravo" } });

    expect(screen.getByText("Bravo")).toBeInTheDocument();
    expect(screen.queryByText("Alpha")).not.toBeInTheDocument();
    expect(screen.queryByText("Charlie")).not.toBeInTheDocument();
  });

  /* 5. Pagination renders correct number of pages */
  it("shows pagination when totalPages > 1", () => {
    render(
      <AgentManagement
        {...defaultProps}
        total={25}
        pageSize={10}
        page={1}
      />,
    );

    expect(screen.getByText("Page 1 of 3 (25 agents)")).toBeInTheDocument();
    expect(screen.getByText("Previous")).toBeInTheDocument();
    expect(screen.getByText("Next")).toBeInTheDocument();
  });

  /* 6. Pagination hides when only 1 page */
  it("hides pagination when only one page", () => {
    render(
      <AgentManagement
        {...defaultProps}
        total={5}
        pageSize={10}
        page={1}
      />,
    );

    expect(screen.queryByText("Previous")).not.toBeInTheDocument();
    expect(screen.queryByText("Next")).not.toBeInTheDocument();
  });

  /* 7. Next/prev pagination calls onPageChange */
  it("calls onPageChange when Next / Previous are clicked", () => {
    const onPageChange = vi.fn();
    render(
      <AgentManagement
        {...defaultProps}
        total={30}
        pageSize={10}
        page={2}
        onPageChange={onPageChange}
      />,
    );

    fireEvent.click(screen.getByText("Next"));
    expect(onPageChange).toHaveBeenCalledWith(3);

    fireEvent.click(screen.getByText("Previous"));
    expect(onPageChange).toHaveBeenCalledWith(1);
  });

  /* 8. Previous disabled on first page */
  it("disables Previous button on first page", () => {
    render(
      <AgentManagement
        {...defaultProps}
        total={20}
        pageSize={10}
        page={1}
      />,
    );

    expect(screen.getByText("Previous")).toBeDisabled();
    expect(screen.getByText("Next")).not.toBeDisabled();
  });

  /* 9. Next disabled on last page */
  it("disables Next button on last page", () => {
    render(
      <AgentManagement
        {...defaultProps}
        total={20}
        pageSize={10}
        page={2}
      />,
    );

    expect(screen.getByText("Next")).toBeDisabled();
    expect(screen.getByText("Previous")).not.toBeDisabled();
  });

  /* 10. Activate agent button triggers callback */
  it("calls onActivate for an inactive agent", () => {
    const onActivate = vi.fn();
    const agents = [
      mockAgent({
        agent_id: "inactive-agent-1",
        agent_name: "InactiveBot",
        status: "inactive",
      }),
    ];
    render(
      <AgentManagement
        {...defaultProps}
        agents={agents}
        total={1}
        onActivate={onActivate}
      />,
    );

    const activateBtn = screen.getByTitle("Activate Agent");
    fireEvent.click(activateBtn);
    expect(onActivate).toHaveBeenCalledWith("inactive-agent-1");
  });

  /* 11. Deactivate agent button triggers callback */
  it("calls onDeactivate for an active agent", () => {
    const onDeactivate = vi.fn();
    const agents = [
      mockAgent({
        agent_id: "active-agent-1",
        agent_name: "ActiveBot",
        status: "active",
      }),
    ];
    render(
      <AgentManagement
        {...defaultProps}
        agents={agents}
        total={1}
        onDeactivate={onDeactivate}
      />,
    );

    const deactivateBtn = screen.getByTitle("Deactivate Agent");
    fireEvent.click(deactivateBtn);
    expect(onDeactivate).toHaveBeenCalledWith("active-agent-1");
  });

  /* 12. Shows loading state */
  it("shows loading state with spinner", () => {
    render(<AgentManagement {...defaultProps} isLoading={true} />);

    // Spinner has role="status" with label "Loading agents..."
    expect(screen.getByRole("status")).toBeInTheDocument();
    expect(screen.getByText("Loading agents...")).toBeInTheDocument();

    // Table should NOT be visible
    expect(screen.queryByText("Agent Management")).not.toBeInTheDocument();
  });

  /* 13. Shows empty state when no agents match search */
  it("shows empty state when filtered agents list is empty", () => {
    const agents = [mockAgent({ agent_id: "id-1", agent_name: "Alpha" })];
    render(
      <AgentManagement {...defaultProps} agents={agents} total={1} />,
    );

    const input = screen.getByPlaceholderText(
      "Search agents by name, ID, or status...",
    );
    fireEvent.change(input, { target: { value: "zzzzz" } });

    expect(
      screen.getByText("No agents match your search."),
    ).toBeInTheDocument();
  });

  /* 14. Shows empty state when agents array is empty */
  it("shows empty state when agents array is empty", () => {
    render(
      <AgentManagement {...defaultProps} agents={[]} total={0} />,
    );

    expect(
      screen.getByText("No agents match your search."),
    ).toBeInTheDocument();
  });

  /* 15. Expand/collapse agent details */
  it("expands and collapses agent detail row on chevron click", () => {
    const agent = mockAgent({
      agent_id: "expand-test-id-000000",
      agent_name: "ExpandBot",
      trust_status: "verified",
      info_used_count: 999,
      data_served_bytes: 2048,
    });
    render(
      <AgentManagement
        {...defaultProps}
        agents={[agent]}
        total={1}
      />,
    );

    // Detail should NOT be visible initially
    expect(screen.queryByText("expand-test-id-000000")).not.toBeInTheDocument();

    // Click the expand/collapse button (inside the first cell)
    const expandButtons = document.querySelectorAll(
      "table tbody button",
    );
    // The first button in the row (with ChevronDown) is the expand toggle
    const chevronBtn = expandButtons[0] as HTMLButtonElement;
    fireEvent.click(chevronBtn);

    // Full Agent ID should now appear in the expanded detail
    expect(screen.getByText("expand-test-id-000000")).toBeInTheDocument();
    expect(screen.getByText("verified")).toBeInTheDocument();

    // Collapse
    fireEvent.click(chevronBtn);
    expect(screen.queryByText("expand-test-id-000000")).not.toBeInTheDocument();
  });

  /* 16. Shows agent metadata when expanded */
  it("shows agent metadata (info used, data served) when expanded", () => {
    const agent = mockAgent({
      agent_id: "meta-agent-id-1234567",
      info_used_count: 5000,
      data_served_bytes: 10240,
    });
    render(
      <AgentManagement
        {...defaultProps}
        agents={[agent]}
        total={1}
      />,
    );

    // Expand
    const chevronBtn = document.querySelector(
      "table tbody button",
    ) as HTMLButtonElement;
    fireEvent.click(chevronBtn);

    expect(screen.getByText("Info Used")).toBeInTheDocument();
    expect(screen.getByText("5,000")).toBeInTheDocument();
    expect(screen.getByText("Data Served")).toBeInTheDocument();
    expect(screen.getByText("10.0 KB")).toBeInTheDocument();
  });

  /* 17. Handles large number of agents (renders many rows) */
  it("handles large number of agents without crashing", () => {
    const agents = Array.from({ length: 50 }, (_, i) =>
      mockAgent({
        agent_id: `agent-${i}-xxxxxxxxxxxx`,
        agent_name: `Agent-${i}`,
      }),
    );
    const { container } = render(
      <AgentManagement
        {...defaultProps}
        agents={agents}
        total={200}
        pageSize={50}
        page={1}
      />,
    );

    const rows = container.querySelectorAll("tbody tr");
    expect(rows.length).toBe(50);
    expect(screen.getByText("Page 1 of 4 (200 agents)")).toBeInTheDocument();
  });

  /* 18. Search with no results shows empty state */
  it("shows empty state for non-matching search across all fields", () => {
    const agents = [
      mockAgent({
        agent_id: "id-1",
        agent_name: "Foo",
        status: "active",
        trust_status: "verified",
      }),
    ];
    render(
      <AgentManagement {...defaultProps} agents={agents} total={1} />,
    );

    fireEvent.change(
      screen.getByPlaceholderText("Search agents by name, ID, or status..."),
      { target: { value: "nonexistent" } },
    );

    expect(
      screen.getByText("No agents match your search."),
    ).toBeInTheDocument();
  });

  /* 19. Status badges show correct inline colors */
  it("renders correct status badge colors via inline styles", () => {
    const agents = [
      mockAgent({ agent_id: "id-a", agent_name: "Active", status: "active" }),
      mockAgent({
        agent_id: "id-s",
        agent_name: "Suspended",
        status: "suspended",
      }),
    ];
    const { container } = render(
      <AgentManagement {...defaultProps} agents={agents} total={2} />,
    );

    // Status badges use inline style backgroundColor and color
    const activeBadge = screen.getByText("active").closest("span");
    expect(activeBadge).toHaveStyle({ color: "#34d399" });

    const suspendedBadge = screen.getByText("suspended").closest("span");
    expect(suspendedBadge).toHaveStyle({ color: "#f87171" });
  });

  /* 20. Trust tier badge colors */
  it("renders correct trust tier colors", () => {
    const agents = [
      mockAgent({
        agent_id: "id-t0",
        agent_name: "T0Agent",
        trust_tier: "T0",
        trust_score: 0.1,
      }),
      mockAgent({
        agent_id: "id-t3",
        agent_name: "T3Agent",
        trust_tier: "T3",
        trust_score: 0.95,
      }),
    ];
    render(
      <AgentManagement {...defaultProps} agents={agents} total={2} />,
    );

    // T0 text rendered with tier color #64748b
    const t0Span = screen.getByText("T0");
    expect(t0Span).toHaveStyle({ color: "#64748b" });

    // T3 text rendered with tier color #34d399
    const t3Span = screen.getByText("T3");
    expect(t3Span).toHaveStyle({ color: "#34d399" });
  });

  /* 21. View Details button triggers onViewDetails */
  it("calls onViewDetails when view button is clicked", () => {
    const onViewDetails = vi.fn();
    const agents = [
      mockAgent({ agent_id: "view-detail-id", agent_name: "DetailBot" }),
    ];
    render(
      <AgentManagement
        {...defaultProps}
        agents={agents}
        total={1}
        onViewDetails={onViewDetails}
      />,
    );

    const viewBtn = screen.getByTitle("View Details");
    fireEvent.click(viewBtn);
    expect(onViewDetails).toHaveBeenCalledWith("view-detail-id");
  });

  /* 22. onViewDetails button hidden when prop not provided */
  it("hides View Details button when onViewDetails is not provided", () => {
    const agents = [mockAgent({ agent_id: "id-no-view" })];
    render(
      <AgentManagement
        {...defaultProps}
        agents={agents}
        total={1}
        onViewDetails={undefined}
      />,
    );

    expect(screen.queryByTitle("View Details")).not.toBeInTheDocument();
  });

  /* 23. Revenue column shows formatted USD */
  it("renders formatted revenue values", () => {
    const agents = [
      mockAgent({
        agent_id: "id-r1",
        agent_name: "RichBot",
        money_received_usd: 2500,
      }),
    ];
    render(
      <AgentManagement {...defaultProps} agents={agents} total={1} />,
    );

    // formatUSD(2500) => "$2.5K"
    expect(screen.getByText("$2.5K")).toBeInTheDocument();
  });

  /* 24. Served count column shows numeric value */
  it("renders served count for each agent", () => {
    const agents = [
      mockAgent({
        agent_id: "id-served",
        agent_name: "ServeBot",
        other_agents_served_count: 42,
      }),
    ];
    render(
      <AgentManagement {...defaultProps} agents={agents} total={1} />,
    );

    expect(screen.getByText("42")).toBeInTheDocument();
  });

  /* 25. Total count plural vs singular */
  it("shows singular 'agent' for total=1 and plural for total > 1", () => {
    const { rerender } = render(
      <AgentManagement {...defaultProps} total={1} />,
    );
    expect(screen.getByText("1 total agent")).toBeInTheDocument();

    rerender(
      <AgentManagement
        {...defaultProps}
        agents={[
          mockAgent({ agent_id: "id-1" }),
          mockAgent({ agent_id: "id-2" }),
        ]}
        total={2}
      />,
    );
    expect(screen.getByText("2 total agents")).toBeInTheDocument();
  });

  /* 26. Filters by agent ID */
  it("filters agents by agent_id", () => {
    const agents = [
      mockAgent({ agent_id: "abc-unique-xyz", agent_name: "FindMe" }),
      mockAgent({ agent_id: "other-id-000", agent_name: "HideMe" }),
    ];
    render(
      <AgentManagement {...defaultProps} agents={agents} total={2} />,
    );

    fireEvent.change(
      screen.getByPlaceholderText("Search agents by name, ID, or status..."),
      { target: { value: "abc-unique" } },
    );

    expect(screen.getByText("FindMe")).toBeInTheDocument();
    expect(screen.queryByText("HideMe")).not.toBeInTheDocument();
  });

  /* 27. Filters by status */
  it("filters agents by status field", () => {
    const agents = [
      mockAgent({
        agent_id: "id-1",
        agent_name: "ActiveOne",
        status: "active",
      }),
      mockAgent({
        agent_id: "id-2",
        agent_name: "SuspendedOne",
        status: "suspended",
      }),
    ];
    render(
      <AgentManagement {...defaultProps} agents={agents} total={2} />,
    );

    fireEvent.change(
      screen.getByPlaceholderText("Search agents by name, ID, or status..."),
      { target: { value: "suspended" } },
    );

    expect(screen.getByText("SuspendedOne")).toBeInTheDocument();
    expect(screen.queryByText("ActiveOne")).not.toBeInTheDocument();
  });

  /* 28. Agent ID truncated to 12 chars + "..." in the row */
  it("shows truncated agent ID in the table row", () => {
    const agent = mockAgent({
      agent_id: "abcdefghijklmnopqrst",
      agent_name: "TruncBot",
    });
    render(
      <AgentManagement {...defaultProps} agents={[agent]} total={1} />,
    );

    // agent_id.slice(0, 12) => "abcdefghijkl" + "..."
    expect(screen.getByText("abcdefghijkl...")).toBeInTheDocument();
  });

  /* 29. Only one row can be expanded at a time */
  it("collapses previously expanded row when a new row is expanded", () => {
    const agents = [
      mockAgent({
        agent_id: "first-expand-id-0000",
        agent_name: "First",
        trust_status: "trust-first",
      }),
      mockAgent({
        agent_id: "second-expand-id-000",
        agent_name: "Second",
        trust_status: "trust-second",
      }),
    ];
    render(
      <AgentManagement {...defaultProps} agents={agents} total={2} />,
    );

    const buttons = document.querySelectorAll("table tbody button");
    // Find the chevron expand buttons (first button in each row's action set)
    // Buttons order: row1-chevron, row1-view, row1-deactivate, row2-chevron, row2-view, row2-deactivate
    // Actually the chevron is the first button in the first <td>.
    // Let's find them by traversing rows.
    const rows = document.querySelectorAll("table tbody tr");
    const chevron1 = rows[0].querySelector("button") as HTMLButtonElement;
    const chevron2 = rows[1].querySelector("button") as HTMLButtonElement;

    // Expand first
    fireEvent.click(chevron1);
    expect(screen.getByText("first-expand-id-0000")).toBeInTheDocument();

    // Expand second -- first should collapse
    fireEvent.click(chevron2);
    expect(screen.getByText("second-expand-id-000")).toBeInTheDocument();
    // The first agent's full ID should no longer be in the expanded detail
    // (the truncated version "first-expand" is still visible in the row itself)
    expect(
      screen.queryByText("first-expand-id-0000"),
    ).not.toBeInTheDocument();
  });
});
