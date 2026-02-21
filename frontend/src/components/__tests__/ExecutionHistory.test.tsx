import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import ExecutionHistory from "../ExecutionHistory";
import type { Execution } from "../../hooks/useActions";

// Mock format utilities so tests don't depend on time
vi.mock("../../lib/format", () => ({
  truncateId: (id: string) => `${id.slice(0, 8)}...`,
  relativeTime: () => "2m ago",
  formatUSD: (amount: number) => `$${amount.toFixed(2)}`,
}));

describe("ExecutionHistory", () => {
  const sampleExecutions: Execution[] = [
    {
      id: "exec-abc-123-def-456",
      action_id: "action-1",
      status: "completed",
      amount: 0.05,
      created_at: "2026-01-15T10:00:00Z",
      proof_verified: true,
    },
    {
      id: "exec-xyz-789-ghi-012",
      action_id: "action-2",
      status: "failed",
      amount: 0.12,
      created_at: "2026-01-15T09:30:00Z",
      proof_verified: false,
    },
    {
      id: "exec-pqr-345-stu-678",
      action_id: "action-3",
      status: "executing",
      amount: 1.5,
      created_at: "2026-01-15T09:00:00Z",
    },
  ];

  it("renders the history table with column headers", () => {
    const { container } = render(
      <ExecutionHistory executions={sampleExecutions} />,
    );

    const table = container.querySelector("table");
    expect(table).toBeInTheDocument();

    expect(screen.getByText("ID")).toBeInTheDocument();
    expect(screen.getByText("Status")).toBeInTheDocument();
    expect(screen.getByText("Amount")).toBeInTheDocument();
    expect(screen.getByText("Time")).toBeInTheDocument();
    expect(screen.getByText("Proof")).toBeInTheDocument();
  });

  it("shows all execution entries with correct data", () => {
    const { container } = render(
      <ExecutionHistory executions={sampleExecutions} />,
    );

    // Check that rows are rendered
    const rows = container.querySelectorAll("tbody tr");
    expect(rows).toHaveLength(3);

    // Truncated IDs
    expect(screen.getByText("exec-abc...")).toBeInTheDocument();
    expect(screen.getByText("exec-xyz...")).toBeInTheDocument();
    expect(screen.getByText("exec-pqr...")).toBeInTheDocument();

    // Amounts
    expect(screen.getByText("$0.05")).toBeInTheDocument();
    expect(screen.getByText("$0.12")).toBeInTheDocument();
    expect(screen.getByText("$1.50")).toBeInTheDocument();

    // Time column
    const timeTexts = screen.getAllByText("2m ago");
    expect(timeTexts).toHaveLength(3);
  });

  it("shows empty state when there are no executions", () => {
    render(<ExecutionHistory executions={[]} />);

    expect(screen.getByText("No executions yet")).toBeInTheDocument();
    expect(
      screen.getByText("Execute an action to see history here"),
    ).toBeInTheDocument();

    // No table should be rendered
    expect(screen.queryByRole("table")).not.toBeInTheDocument();
  });

  it("renders status badges for each execution", () => {
    render(<ExecutionHistory executions={sampleExecutions} />);

    expect(screen.getByText("completed")).toBeInTheDocument();
    expect(screen.getByText("failed")).toBeInTheDocument();
    expect(screen.getByText("executing")).toBeInTheDocument();
  });

  it("shows verified badge for proof_verified executions", () => {
    render(<ExecutionHistory executions={sampleExecutions} />);

    // First execution has proof_verified = true
    expect(screen.getByText("Verified")).toBeInTheDocument();

    // Non-verified ones show "--"
    const dashes = screen.getAllByText("--");
    expect(dashes.length).toBeGreaterThanOrEqual(1);
  });
});
