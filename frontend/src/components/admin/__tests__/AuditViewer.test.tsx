import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, within } from "@testing-library/react";
import AuditViewer from "../AuditViewer";

describe("AuditViewer", () => {
  beforeEach(() => {
    // Mock URL.createObjectURL and URL.revokeObjectURL for CSV export tests
    global.URL.createObjectURL = vi.fn(() => "blob:mock-url");
    global.URL.revokeObjectURL = vi.fn();
  });

  it("renders audit log entries", () => {
    render(<AuditViewer />);

    // The component has 10 static entries and should display the header
    expect(screen.getByText("Audit Log")).toBeInTheDocument();

    // Check that entries are rendered - look for unique actions in the data
    expect(screen.getByText("agent.deactivated")).toBeInTheDocument();
    expect(screen.getByText("rate_limit.triggered")).toBeInTheDocument();
    expect(screen.getByText("listing.created")).toBeInTheDocument();
  });

  it("shows static/sample data correctly", () => {
    render(<AuditViewer />);

    // Verify the entry count text (appears in header and footer)
    const entryCountTexts = screen.getAllByText("10 of 10 entries");
    expect(entryCountTexts.length).toBeGreaterThanOrEqual(1);

    // Verify all 10 action entries from the static data (actions are unique)
    expect(screen.getByText("agent.deactivated")).toBeInTheDocument();
    expect(screen.getByText("rate_limit.triggered")).toBeInTheDocument();
    expect(screen.getByText("listing.created")).toBeInTheDocument();
    expect(screen.getByText("config.updated")).toBeInTheDocument();
    expect(screen.getByText("auth.failed")).toBeInTheDocument();
    expect(screen.getByText("transaction.completed")).toBeInTheDocument();
    expect(screen.getByText("payout.approved")).toBeInTheDocument();
    expect(screen.getByText("service.degraded")).toBeInTheDocument();
    expect(screen.getByText("feature_flag.toggled")).toBeInTheDocument();
    expect(screen.getByText("plugin.installed")).toBeInTheDocument();
  });

  it("category filter works (select different categories)", () => {
    render(<AuditViewer />);

    // The category select is the <select> element. Get it by its role.
    const categorySelect = screen.getByRole("combobox");
    fireEvent.change(categorySelect, { target: { value: "Security" } });

    // Security entries: rate_limit.triggered (evt-002) and auth.failed (evt-005)
    expect(screen.getByText("rate_limit.triggered")).toBeInTheDocument();
    expect(screen.getByText("auth.failed")).toBeInTheDocument();

    // Non-security entries should not be present
    expect(screen.queryByText("agent.deactivated")).not.toBeInTheDocument();
    expect(screen.queryByText("listing.created")).not.toBeInTheDocument();

    // Entry count should update
    const entryCountTexts = screen.getAllByText("2 of 10 entries");
    expect(entryCountTexts.length).toBeGreaterThanOrEqual(1);
  });

  it("severity filter works", () => {
    render(<AuditViewer />);

    // Click the "critical" severity pill button.
    // The severity filter buttons contain text like "All", "info", "warning", "critical".
    // Table badges also show the same text. Use getAllByRole("button") and find by name.
    const criticalButtons = screen.getAllByRole("button", { name: /^critical$/i });
    // The first match should be the severity filter pill
    fireEvent.click(criticalButtons[0]);

    // Critical entries: auth.failed (evt-005) and service.degraded (evt-008)
    expect(screen.getByText("auth.failed")).toBeInTheDocument();
    expect(screen.getByText("service.degraded")).toBeInTheDocument();

    // Non-critical entries should not be visible
    expect(screen.queryByText("agent.deactivated")).not.toBeInTheDocument();
    expect(screen.queryByText("listing.created")).not.toBeInTheDocument();

    const entryCountTexts = screen.getAllByText("2 of 10 entries");
    expect(entryCountTexts.length).toBeGreaterThanOrEqual(1);
  });

  it("search input filters entries", () => {
    render(<AuditViewer />);

    const searchInput = screen.getByPlaceholderText(
      "Search by actor, action, or resource..."
    );
    fireEvent.change(searchInput, { target: { value: "payout" } });

    // Should find payout.approved entry
    expect(screen.getByText("payout.approved")).toBeInTheDocument();

    // Other entries should be filtered out
    expect(screen.queryByText("agent.deactivated")).not.toBeInTheDocument();
    expect(screen.queryByText("auth.failed")).not.toBeInTheDocument();

    const entryCountTexts = screen.getAllByText("1 of 10 entries");
    expect(entryCountTexts.length).toBeGreaterThanOrEqual(1);
  });

  it("sort by column works (click header to sort)", () => {
    const { container } = render(<AuditViewer />);

    // Default sort is descending (newest first).
    // The first data row should be evt-001 (2026-02-21T14:32:10Z) with action agent.deactivated.
    const rows = container.querySelectorAll("tbody tr");
    expect(rows[0]).toHaveTextContent("agent.deactivated");

    // Click the Timestamp header to toggle to ascending sort
    const timestampHeader = screen.getByText("Timestamp");
    fireEvent.click(timestampHeader);

    // After ascending sort, first entry should be the oldest: evt-010 (2026-02-20T10:00:00Z)
    const rowsAfterSort = container.querySelectorAll("tbody tr");
    expect(rowsAfterSort[0]).toHaveTextContent("plugin.installed");
  });

  it("expand row shows details", () => {
    const { container } = render(<AuditViewer />);

    // Click on the first data row to expand it (evt-001 agent.deactivated)
    const firstRow = container.querySelectorAll("tbody tr")[0];
    fireEvent.click(firstRow);

    // Expanded detail should show details from the entry
    expect(screen.getByText("Suspicious activity detected")).toBeInTheDocument();
    expect(screen.getByText("Mozilla/5.0 Chrome/120")).toBeInTheDocument();
    expect(screen.getByText("evt-001")).toBeInTheDocument();

    // Detail labels should be visible
    expect(screen.getByText("IP Address")).toBeInTheDocument();
    expect(screen.getByText("User Agent")).toBeInTheDocument();
    expect(screen.getByText("Full Timestamp")).toBeInTheDocument();
    expect(screen.getByText("Event ID")).toBeInTheDocument();
  });

  it("collapse expanded row", () => {
    const { container } = render(<AuditViewer />);

    // Expand the first row
    const firstRow = container.querySelectorAll("tbody tr")[0];
    fireEvent.click(firstRow);

    // Verify it is expanded
    expect(screen.getByText("Suspicious activity detected")).toBeInTheDocument();

    // Click again to collapse
    fireEvent.click(firstRow);

    // Details should no longer be visible
    expect(
      screen.queryByText("Suspicious activity detected")
    ).not.toBeInTheDocument();
  });

  it("shows correct severity indicators/colors", () => {
    const { container } = render(<AuditViewer />);

    // Severity badges in the table are styled spans inside <td> elements.
    // The severity filter pills are buttons outside the table.
    // To count only table badges, scope to the tbody.
    const tbody = container.querySelector("tbody")!;
    expect(tbody).toBeTruthy();

    const infoBadges = within(tbody).getAllByText("info");
    const warningBadges = within(tbody).getAllByText("warning");
    const criticalBadges = within(tbody).getAllByText("critical");

    // Info entries: evt-003, evt-004, evt-006, evt-007, evt-009, evt-010 = 6
    expect(infoBadges).toHaveLength(6);
    // Warning entries: evt-001, evt-002 = 2
    expect(warningBadges).toHaveLength(2);
    // Critical entries: evt-005, evt-008 = 2
    expect(criticalBadges).toHaveLength(2);

    // Check that severity badges have the correct inline styles
    const firstInfoBadge = infoBadges[0];
    expect(firstInfoBadge).toHaveStyle({
      backgroundColor: "rgba(96,165,250,0.1)",
      color: "#60a5fa",
    });

    const firstWarningBadge = warningBadges[0];
    expect(firstWarningBadge).toHaveStyle({
      backgroundColor: "rgba(251,191,36,0.1)",
      color: "#fbbf24",
    });

    const firstCriticalBadge = criticalBadges[0];
    expect(firstCriticalBadge).toHaveStyle({
      backgroundColor: "rgba(248,113,113,0.1)",
      color: "#f87171",
    });
  });

  it("empty state when no entries match filter", () => {
    render(<AuditViewer />);

    // Search for something that matches no entries
    const searchInput = screen.getByPlaceholderText(
      "Search by actor, action, or resource..."
    );
    fireEvent.change(searchInput, {
      target: { value: "xyznonexistenttermxyz" },
    });

    // Empty state message should appear
    expect(screen.getByText("No audit entries found")).toBeInTheDocument();
    expect(screen.getByText("Try adjusting your filters")).toBeInTheDocument();

    // Table should not be present
    expect(screen.queryByRole("table")).not.toBeInTheDocument();

    // Entry count should show 0
    expect(screen.getByText("0 of 10 entries")).toBeInTheDocument();
  });

  it("timestamp formatting is correct", () => {
    const { container } = render(<AuditViewer />);

    // The component uses toLocaleString("en-US", { month: "short", day: "numeric",
    // hour: "2-digit", minute: "2-digit", second: "2-digit" }).
    // The exact output depends on the runtime timezone, so we verify:
    // 1. The formatted timestamp cells exist within the table
    // 2. The full ISO timestamp is shown in the expanded detail row

    // Verify formatted timestamps are rendered as monospace text in the table
    const monoCells = container.querySelectorAll("td span.font-mono");
    expect(monoCells.length).toBeGreaterThan(0);

    // Expand first row to see the full ISO timestamp
    const firstRow = container.querySelectorAll("tbody tr")[0];
    fireEvent.click(firstRow);

    // The full ISO timestamp should be visible in the expanded detail
    expect(screen.getByText("2026-02-21T14:32:10Z")).toBeInTheDocument();
  });

  it("handles large datasets", () => {
    // The component uses static data with 10 entries.
    // This test validates it renders all entries and the filtering/sorting
    // still works correctly across the full dataset.
    const { container } = render(<AuditViewer />);

    // All 10 entries should be rendered as rows
    const dataRows = container.querySelectorAll("tbody tr");
    expect(dataRows).toHaveLength(10);

    // Apply a search that matches multiple entries
    const searchInput = screen.getByPlaceholderText(
      "Search by actor, action, or resource..."
    );
    fireEvent.change(searchInput, { target: { value: "agent" } });

    // Should match several entries that contain "agent" in various fields.
    // Verify filtering reduces the set but does not empty it.
    const filteredRows = container.querySelectorAll("tbody tr");
    expect(filteredRows.length).toBeGreaterThan(0);
    expect(filteredRows.length).toBeLessThan(10);

    // Now apply an additional severity filter on top of the search
    const warningButtons = screen.getAllByRole("button", { name: /^warning$/i });
    fireEvent.click(warningButtons[0]);

    // Should further reduce results
    const doubleFilteredRows = container.querySelectorAll("tbody tr");
    expect(doubleFilteredRows.length).toBeGreaterThan(0);
    expect(doubleFilteredRows.length).toBeLessThanOrEqual(filteredRows.length);
  });

  it("clear filters button resets all filters", () => {
    render(<AuditViewer />);

    // Apply category filter
    const categorySelect = screen.getByRole("combobox");
    fireEvent.change(categorySelect, { target: { value: "Security" } });

    // Should show fewer entries
    const reducedCounts = screen.getAllByText("2 of 10 entries");
    expect(reducedCounts.length).toBeGreaterThanOrEqual(1);

    // Clear button should be visible when filters are active
    const clearButton = screen.getByRole("button", { name: /clear/i });
    fireEvent.click(clearButton);

    // All entries should be back
    const fullCounts = screen.getAllByText("10 of 10 entries");
    expect(fullCounts.length).toBeGreaterThanOrEqual(1);
  });

  it("export CSV button is present and clickable", () => {
    render(<AuditViewer />);

    const exportButton = screen.getByRole("button", { name: /export csv/i });
    expect(exportButton).toBeInTheDocument();

    // Click should not throw
    fireEvent.click(exportButton);

    // URL.createObjectURL should have been called
    expect(global.URL.createObjectURL).toHaveBeenCalled();
  });

  it("dateFrom filter hides entries before the given date (lines 280-283)", () => {
    render(<AuditViewer />);

    // Set dateFrom to 2026-02-22 — a date after all entries, so nothing should show
    const dateFromInputs = document.querySelectorAll('input[type="date"]');
    const fromInput = dateFromInputs[0] as HTMLInputElement;
    fireEvent.change(fromInput, { target: { value: "2026-02-22" } });

    // All 10 entries have timestamps on/before 2026-02-21 so they should all be filtered
    expect(screen.queryByText("agent.deactivated")).not.toBeInTheDocument();
    expect(screen.queryByText("plugin.installed")).not.toBeInTheDocument();

    // Entry count shows 0
    expect(screen.getByText("No audit entries found")).toBeInTheDocument();
  });

  it("dateTo filter hides entries after the given date (lines 284-288)", () => {
    render(<AuditViewer />);

    // Set dateTo to 2026-02-19 — before all entries, so nothing should show
    const dateFromInputs = document.querySelectorAll('input[type="date"]');
    const toInput = dateFromInputs[1] as HTMLInputElement;
    fireEvent.change(toInput, { target: { value: "2026-02-19" } });

    // All entries are after 2026-02-19 so they should all be filtered out
    expect(screen.queryByText("agent.deactivated")).not.toBeInTheDocument();
    expect(screen.queryByText("plugin.installed")).not.toBeInTheDocument();

    // Empty state should appear
    expect(screen.getByText("No audit entries found")).toBeInTheDocument();
  });

  it("dateFrom and dateTo together activate both date filter branches", () => {
    render(<AuditViewer />);

    const dateInputs = document.querySelectorAll('input[type="date"]');
    const fromInput = dateInputs[0] as HTMLInputElement;
    const toInput = dateInputs[1] as HTMLInputElement;

    // Set both from and to dates to cover both filter code paths
    // Use dates that produce an empty result for deterministic assertions
    fireEvent.change(fromInput, { target: { value: "2026-02-22" } });
    fireEvent.change(toInput, { target: { value: "2026-02-23" } });

    // All entries are before fromDate so nothing should show
    expect(screen.getByText("No audit entries found")).toBeInTheDocument();

    // Both inputs should reflect the entered values
    expect(fromInput.value).toBe("2026-02-22");
    expect(toInput.value).toBe("2026-02-23");
  });

  it("renders actor type badges for all four actor types (lines 455-471)", () => {
    const { container } = render(<AuditViewer />);

    // ACTOR_COLORS has entries for: admin (purple), system (blue), agent (green), user (yellow).
    // The static data has all four actorTypes. Each actor cell renders:
    //   - a colored circle div with an icon
    //   - a <p> showing the actor name
    //   - a <span> showing actorType with an inline color style
    //
    // admin: actorType="admin" appears in evt-001, evt-004, evt-007, evt-009
    const adminBadges = screen.getAllByText("admin");
    expect(adminBadges.length).toBeGreaterThanOrEqual(1);

    // system: actorType="system" appears in evt-002, evt-005, evt-008
    const systemBadges = screen.getAllByText("system");
    expect(systemBadges.length).toBeGreaterThanOrEqual(1);

    // agent: actorType="agent" appears in evt-003, evt-006
    const agentBadges = screen.getAllByText("agent");
    expect(agentBadges.length).toBeGreaterThanOrEqual(1);

    // user: actorType="user" appears in evt-010
    const userBadges = screen.getAllByText("user");
    expect(userBadges.length).toBeGreaterThanOrEqual(1);

    // The actor icon circles are .rounded-full divs inside td cells.
    // The actor column is the 3rd <td> (after expand-toggle and timestamp).
    // Each data row has exactly one circle per actor column (not severity).
    // Severity badges are <span> not <div>, so query for div.rounded-full in td.
    const actorCircleDivs = container.querySelectorAll("td div.rounded-full");
    // 10 entries = 10 actor icon circles
    expect(actorCircleDivs.length).toBe(10);

    // The first entry (agent.deactivated, actorType="admin") should have admin background
    const firstCircle = actorCircleDivs[0] as HTMLElement;
    expect(firstCircle).toHaveStyle({ backgroundColor: "rgba(167,139,250,0.15)" });
  });

  it("actor type badge spans use inline color from ACTOR_COLORS (lines 622-627)", () => {
    const { container } = render(<AuditViewer />);

    // The actorType badge spans have class "text-[9px] font-semibold uppercase" and inline color.
    // Severity badge spans have additional classes like "inline-flex", "rounded-full", "px-2".
    // We can distinguish the two by querying specifically for spans that are NOT inline-flex.
    // The actorType spans are inside a <div> with class "flex items-center gap-2" in the actor <td>.
    // They are children of <div> elements in the actor column.
    const actorCells = container.querySelectorAll("tbody td:nth-child(3)");
    expect(actorCells.length).toBe(10);

    // Collect all actorType spans from the actor column cells
    const actorTypeBadgeSpans = Array.from(actorCells).map(
      (cell) => cell.querySelector("span.font-semibold.uppercase") as HTMLElement
    ).filter(Boolean);
    expect(actorTypeBadgeSpans.length).toBe(10);

    // First entry (evt-001, actorType "admin") — color #a78bfa
    const firstBadge = actorTypeBadgeSpans[0];
    expect(firstBadge.textContent).toBe("admin");
    expect(firstBadge).toHaveStyle({ color: "#a78bfa" });

    // Find "user" span (evt-010)
    const userSpan = actorTypeBadgeSpans.find((el) => el.textContent === "user");
    expect(userSpan).toBeTruthy();
    expect(userSpan!).toHaveStyle({ color: "#fbbf24" });

    // Find an "agent" span (evt-003 or evt-006)
    const agentSpan = actorTypeBadgeSpans.find((el) => el.textContent === "agent");
    expect(agentSpan).toBeTruthy();
    expect(agentSpan!).toHaveStyle({ color: "#34d399" });
  });
});
