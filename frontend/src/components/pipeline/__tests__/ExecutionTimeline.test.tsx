import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import ExecutionTimeline from "../ExecutionTimeline";
import type { AgentExecution, PipelineStep } from "../../../types/api";

// Mock the PipelineStepCard child component so we can inspect what is rendered
vi.mock("../PipelineStep", () => ({
  default: ({ step, index }: { step: PipelineStep; index: number }) => (
    <div data-testid={`step-${step.id}`}>
      <span data-testid="step-action">{step.action}</span>
      <span data-testid="step-status">{step.status}</span>
      <span data-testid="step-index">{index}</span>
      {step.latencyMs !== undefined && (
        <span data-testid="step-latency">{step.latencyMs}ms</span>
      )}
      {step.error && <span data-testid="step-error">{step.error}</span>}
    </div>
  ),
}));

function makeStep(overrides: Partial<PipelineStep> = {}): PipelineStep {
  return {
    id: "step-1",
    agentId: "agent-1",
    agentName: "TestAgent",
    action: "analyze_market",
    status: "completed",
    startedAt: "2026-02-21T10:00:00.000Z",
    completedAt: "2026-02-21T10:00:00.120Z",
    latencyMs: 120,
    ...overrides,
  };
}

function makeExecution(overrides: Partial<AgentExecution> = {}): AgentExecution {
  return {
    agentId: "agent-1",
    agentName: "TestAgent",
    status: "active",
    steps: [makeStep()],
    startedAt: "2026-02-21T10:00:00.000Z",
    lastActivityAt: "2026-02-21T10:00:00.120Z",
    ...overrides,
  };
}

describe("ExecutionTimeline", () => {
  it("shows placeholder when no execution is selected", () => {
    render(<ExecutionTimeline execution={null} />);
    expect(
      screen.getByText("Select an agent to view execution")
    ).toBeInTheDocument();
    expect(
      screen.getByText(/Click an agent on the left/)
    ).toBeInTheDocument();
  });

  it("renders timeline with steps and shows agent name", () => {
    const execution = makeExecution({
      agentName: "PriceWatcher",
      steps: [
        makeStep({ id: "s1", action: "fetch_prices" }),
        makeStep({ id: "s2", action: "compare_prices" }),
      ],
    });
    render(<ExecutionTimeline execution={execution} />);
    expect(screen.getByText("PriceWatcher")).toBeInTheDocument();
    expect(screen.getByTestId("step-s1")).toBeInTheDocument();
    expect(screen.getByTestId("step-s2")).toBeInTheDocument();
  });

  it("shows step statuses via PipelineStepCard", () => {
    const execution = makeExecution({
      steps: [
        makeStep({ id: "s1", status: "completed", action: "step_done" }),
        makeStep({ id: "s2", status: "running", action: "step_running" }),
        makeStep({ id: "s3", status: "failed", action: "step_failed" }),
        makeStep({ id: "s4", status: "waiting", action: "step_waiting" }),
      ],
    });
    render(<ExecutionTimeline execution={execution} />);
    const statuses = screen.getAllByTestId("step-status");
    expect(statuses[0].textContent).toBe("completed");
    expect(statuses[1].textContent).toBe("running");
    expect(statuses[2].textContent).toBe("failed");
    expect(statuses[3].textContent).toBe("waiting");
  });

  it("shows step durations via PipelineStepCard", () => {
    const execution = makeExecution({
      steps: [
        makeStep({ id: "s1", latencyMs: 50 }),
        makeStep({ id: "s2", latencyMs: 200 }),
      ],
    });
    render(<ExecutionTimeline execution={execution} />);
    const latencies = screen.getAllByTestId("step-latency");
    expect(latencies[0].textContent).toBe("50ms");
    expect(latencies[1].textContent).toBe("200ms");
  });

  it("displays completed count and average latency stats", () => {
    const execution = makeExecution({
      steps: [
        makeStep({ id: "s1", status: "completed", latencyMs: 100 }),
        makeStep({ id: "s2", status: "completed", latencyMs: 300 }),
        makeStep({ id: "s3", status: "running", latencyMs: 500 }),
      ],
    });
    render(<ExecutionTimeline execution={execution} />);
    // Find the mini-stats area (hidden sm:flex) which contains the completed count and avg
    expect(screen.getByText("done")).toBeInTheDocument();
    expect(screen.getByText("avg")).toBeInTheDocument();
    // 2 completed out of 3 — look specifically in the stats section
    const doneLabel = screen.getByText("done");
    const doneStatContainer = doneLabel.parentElement!;
    expect(doneStatContainer.textContent).toContain("2");
    // avg = (100 + 300 + 500) / 3 = 300
    const avgLabel = screen.getByText("avg");
    const avgStatContainer = avgLabel.parentElement!;
    expect(avgStatContainer.textContent).toContain("300ms");
  });

  it("shows active status badge with capitalize text", () => {
    const execution = makeExecution({ status: "active" });
    render(<ExecutionTimeline execution={execution} />);
    // The status badge text is capitalized via CSS; the raw text is lowercase
    const statusBadges = screen.getAllByText("active");
    // At least one should be in the badge (not the step mock)
    expect(statusBadges.length).toBeGreaterThanOrEqual(1);
  });

  it("shows error status badge styling", () => {
    const execution = makeExecution({
      status: "error",
      steps: [makeStep({ id: "s1", status: "failed", error: "timeout" })],
    });
    render(<ExecutionTimeline execution={execution} />);
    // The badge renders the status text "error" inside a <span class="capitalize">
    const errorBadgeText = screen.getByText("error");
    expect(errorBadgeText).toBeInTheDocument();
    // The outer badge span (parent of the capitalize span) has error styling
    const badge = errorBadgeText.parentElement;
    expect(badge).not.toBeNull();
    expect(badge!.className).toContain("text-[#f87171]");
    expect(badge!.className).toContain("border");
  });

  it("shows idle status badge with CheckCircle icon indicator", () => {
    const execution = makeExecution({
      status: "idle",
      steps: [makeStep({ id: "s1", status: "completed" })],
    });
    render(<ExecutionTimeline execution={execution} />);
    const statusText = screen.getByText("idle");
    expect(statusText).toBeInTheDocument();
  });

  it("passes correct 1-based index to each PipelineStepCard", () => {
    const execution = makeExecution({
      steps: [
        makeStep({ id: "s1" }),
        makeStep({ id: "s2" }),
        makeStep({ id: "s3" }),
      ],
    });
    render(<ExecutionTimeline execution={execution} />);
    const indices = screen.getAllByTestId("step-index");
    expect(indices[0].textContent).toBe("1");
    expect(indices[1].textContent).toBe("2");
    expect(indices[2].textContent).toBe("3");
  });

  it("renders step count and start time in the header", () => {
    const execution = makeExecution({
      steps: [makeStep({ id: "s1" }), makeStep({ id: "s2" })],
      startedAt: "2026-02-21T10:30:00.000Z",
    });
    render(<ExecutionTimeline execution={execution} />);
    expect(screen.getByText(/2 steps/)).toBeInTheDocument();
    expect(screen.getByText(/Started/)).toBeInTheDocument();
  });
});
