import { describe, it, expect, vi, beforeEach } from "vitest";
import { screen, fireEvent } from "@testing-library/react";
import { renderWithProviders } from "../../test/test-utils";
import PipelinePage from "../PipelinePage";
import * as usePipelineFeedModule from "../../hooks/usePipelineFeed";
import type { AgentExecution } from "../../types/api";

// Mock the usePipelineFeed hook
vi.mock("../../hooks/usePipelineFeed");

// Mock the heavy child components to keep tests focused
vi.mock("../../components/pipeline/AgentPipelineList", () => ({
  default: ({ executions, selectedId, onSelect }: any) => (
    <div data-testid="agent-pipeline-list">
      {executions.map((e: any) => (
        <button key={e.agentId} data-testid={`agent-${e.agentId}`} onClick={() => onSelect(e.agentId)}>
          {e.agentName}
        </button>
      ))}
    </div>
  ),
}));

vi.mock("../../components/pipeline/ExecutionTimeline", () => ({
  default: ({ execution }: any) => (
    <div data-testid="execution-timeline">
      {execution ? execution.agentName : "No execution selected"}
    </div>
  ),
}));

vi.mock("../../components/pipeline/LiveEventFeed", () => ({
  default: ({ events }: any) => (
    <div data-testid="live-event-feed">
      {events.length} events
    </div>
  ),
}));

const mockExecutions: AgentExecution[] = [
  {
    agentId: "agent-1",
    agentName: "Search Agent",
    status: "active",
    steps: [
      {
        id: "step-1",
        agentId: "agent-1",
        agentName: "Search Agent",
        action: "listing created",
        status: "completed",
        startedAt: "2025-01-01T00:00:00Z",
        completedAt: "2025-01-01T00:00:01Z",
        latencyMs: 150,
        toolCall: { name: "listing_created", input: {} },
      },
    ],
    startedAt: "2025-01-01T00:00:00Z",
    lastActivityAt: "2025-01-01T00:00:01Z",
  },
  {
    agentId: "agent-2",
    agentName: "Data Agent",
    status: "error",
    steps: [
      {
        id: "step-2",
        agentId: "agent-2",
        agentName: "Data Agent",
        action: "transaction completed",
        status: "failed",
        startedAt: "2025-01-01T00:00:00Z",
        completedAt: "2025-01-01T00:00:02Z",
        latencyMs: 200,
        toolCall: { name: "transaction_completed", input: {} },
      },
    ],
    startedAt: "2025-01-01T00:00:00Z",
    lastActivityAt: "2025-01-01T00:00:02Z",
  },
];

describe("PipelinePage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  function mockPipelineFeed(overrides: Partial<ReturnType<typeof usePipelineFeedModule.usePipelineFeed>> = {}) {
    vi.spyOn(usePipelineFeedModule, "usePipelineFeed").mockReturnValue({
      executions: mockExecutions,
      liveEvents: [],
      totalSteps: 2,
      ...overrides,
    });
  }

  it("renders the page title and subtitle", () => {
    mockPipelineFeed();
    renderWithProviders(<PipelinePage />);

    expect(screen.getByText("Agent Pipeline")).toBeInTheDocument();
    expect(screen.getByText(/2 agents tracked/)).toBeInTheDocument();
    expect(screen.getByText(/2 steps recorded/)).toBeInTheDocument();
  });

  it("shows the agent pipeline list when executions exist", () => {
    mockPipelineFeed();
    renderWithProviders(<PipelinePage />);

    expect(screen.getByTestId("agent-pipeline-list")).toBeInTheDocument();
    // "Search Agent" appears in both the AgentPipelineList button and the
    // ExecutionTimeline (which shows the first execution by default)
    expect(screen.getAllByText("Search Agent").length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText("Data Agent")).toBeInTheDocument();
  });

  it("shows execution timeline for the first agent by default", () => {
    mockPipelineFeed();
    renderWithProviders(<PipelinePage />);

    const timeline = screen.getByTestId("execution-timeline");
    // When no agent is manually selected, the first execution is shown
    expect(timeline).toHaveTextContent("Search Agent");
  });

  it("shows empty state when there are no executions", () => {
    mockPipelineFeed({ executions: [], totalSteps: 0 });
    renderWithProviders(<PipelinePage />);

    expect(screen.getByText("Waiting for agent activity")).toBeInTheDocument();
    expect(
      screen.getByText(/Agent executions will appear here in real-time/),
    ).toBeInTheDocument();
  });

  it("renders metric cards with correct values", () => {
    mockPipelineFeed();
    renderWithProviders(<PipelinePage />);

    expect(screen.getByText("Total Steps")).toBeInTheDocument();
    expect(screen.getByText("Active Executions")).toBeInTheDocument();
    expect(screen.getByText("Avg Latency")).toBeInTheDocument();
    expect(screen.getByText("Success Rate")).toBeInTheDocument();

    // 1 active execution (agent-1 is "active")
    expect(screen.getByText("1")).toBeInTheDocument();

    // Avg latency: only completed steps count. step-1 has latencyMs 150, so avg = 150ms
    expect(screen.getByText("150ms")).toBeInTheDocument();
  });

  it("switches to Live Feed tab", () => {
    mockPipelineFeed({ liveEvents: [{ type: "test" } as any] });
    renderWithProviders(<PipelinePage />);

    fireEvent.click(screen.getByText("Live Feed"));
    expect(screen.getByTestId("live-event-feed")).toBeInTheDocument();
    expect(screen.getByTestId("live-event-feed")).toHaveTextContent("1 events");
  });

  it("shows error summary when agents have errors", () => {
    mockPipelineFeed();
    renderWithProviders(<PipelinePage />);

    // agent-2 has status "error", so errorCount = 1
    expect(screen.getByText(/1 agent reporting errors/)).toBeInTheDocument();
  });

  it("does not show error summary when no errors exist", () => {
    const noErrorExecutions = mockExecutions.map((e) => ({
      ...e,
      status: "active" as const,
    }));
    mockPipelineFeed({ executions: noErrorExecutions });
    renderWithProviders(<PipelinePage />);

    expect(screen.queryByText(/reporting errors/)).not.toBeInTheDocument();
  });

  it("shows both Executions and Live Feed tab buttons", () => {
    mockPipelineFeed();
    renderWithProviders(<PipelinePage />);

    expect(screen.getByText("Executions")).toBeInTheDocument();
    expect(screen.getByText("Live Feed")).toBeInTheDocument();
  });

  it("applies fade-in animation class to the main container", () => {
    mockPipelineFeed();
    const { container } = renderWithProviders(<PipelinePage />);

    const mainDiv = container.firstElementChild;
    expect(mainDiv).toBeTruthy();
    expect(mainDiv?.className).toContain("animate-fade-in");
  });
});
