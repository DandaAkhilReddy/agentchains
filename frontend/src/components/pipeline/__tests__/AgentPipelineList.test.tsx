import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import AgentPipelineList from "../AgentPipelineList";
import type { AgentExecution } from "../../../types/api";

function makeExecution(overrides: Partial<AgentExecution> = {}): AgentExecution {
  return {
    agentId: "agent-1",
    agentName: "PriceWatcher",
    status: "active",
    steps: [
      {
        id: "s1",
        agentId: "agent-1",
        agentName: "PriceWatcher",
        action: "fetch_prices",
        status: "completed",
        startedAt: new Date().toISOString(),
        completedAt: new Date().toISOString(),
        latencyMs: 120,
      },
    ],
    startedAt: new Date().toISOString(),
    lastActivityAt: new Date().toISOString(),
    ...overrides,
  };
}

describe("AgentPipelineList", () => {
  it("renders empty state when no executions are provided", () => {
    render(
      <AgentPipelineList executions={[]} selectedId={null} onSelect={vi.fn()} />
    );
    expect(screen.getByText("No agent activity yet")).toBeInTheDocument();
    expect(
      screen.getByText(/Agent executions will appear here/)
    ).toBeInTheDocument();
  });

  it("renders a list of pipelines with agent names", () => {
    const executions = [
      makeExecution({ agentId: "a1", agentName: "PriceWatcher" }),
      makeExecution({ agentId: "a2", agentName: "InventoryBot" }),
    ];
    render(
      <AgentPipelineList
        executions={executions}
        selectedId={null}
        onSelect={vi.fn()}
      />
    );
    expect(screen.getByText("PriceWatcher")).toBeInTheDocument();
    expect(screen.getByText("InventoryBot")).toBeInTheDocument();
  });

  it("shows the active agent count in the header", () => {
    const executions = [
      makeExecution({ agentId: "a1" }),
      makeExecution({ agentId: "a2" }),
      makeExecution({ agentId: "a3" }),
    ];
    render(
      <AgentPipelineList
        executions={executions}
        selectedId={null}
        onSelect={vi.fn()}
      />
    );
    expect(screen.getByText("Active Agents (3)")).toBeInTheDocument();
  });

  it("displays step count and relative time for each execution", () => {
    const executions = [
      makeExecution({
        agentId: "a1",
        agentName: "Bot",
        steps: [
          {
            id: "s1",
            agentId: "a1",
            agentName: "Bot",
            action: "step1",
            status: "completed",
            startedAt: new Date().toISOString(),
            latencyMs: 50,
          },
          {
            id: "s2",
            agentId: "a1",
            agentName: "Bot",
            action: "step2",
            status: "running",
            startedAt: new Date().toISOString(),
            latencyMs: 80,
          },
        ],
        lastActivityAt: new Date().toISOString(),
      }),
    ];
    render(
      <AgentPipelineList
        executions={executions}
        selectedId={null}
        onSelect={vi.fn()}
      />
    );
    expect(screen.getByText("2 steps")).toBeInTheDocument();
    expect(screen.getByText("just now")).toBeInTheDocument();
  });

  it("calls onSelect with the agent id when a pipeline is clicked", () => {
    const onSelect = vi.fn();
    const executions = [makeExecution({ agentId: "a1", agentName: "Bot" })];
    render(
      <AgentPipelineList
        executions={executions}
        selectedId={null}
        onSelect={onSelect}
      />
    );
    fireEvent.click(screen.getByText("Bot"));
    expect(onSelect).toHaveBeenCalledWith("a1");
  });

  it("applies selected styling to the currently selected pipeline", () => {
    const executions = [
      makeExecution({ agentId: "a1", agentName: "Selected Agent" }),
      makeExecution({ agentId: "a2", agentName: "Other Agent" }),
    ];
    const { container } = render(
      <AgentPipelineList
        executions={executions}
        selectedId="a1"
        onSelect={vi.fn()}
      />
    );
    const buttons = container.querySelectorAll("button");
    expect(buttons[0].className).toContain("bg-[#1a2035]");
    expect(buttons[0].className).toContain("border-[rgba(96,165,250,0.3)]");
    expect(buttons[1].className).not.toContain("border-[rgba(96,165,250,0.3)]");
  });

  it("shows correct status indicator colors for active, error, and idle", () => {
    const executions = [
      makeExecution({ agentId: "a1", agentName: "Active Bot", status: "active" }),
      makeExecution({ agentId: "a2", agentName: "Error Bot", status: "error" }),
      makeExecution({ agentId: "a3", agentName: "Idle Bot", status: "idle" }),
    ];
    const { container } = render(
      <AgentPipelineList
        executions={executions}
        selectedId={null}
        onSelect={vi.fn()}
      />
    );
    const dots = container.querySelectorAll(".rounded-full");
    // Active agent dot should be green
    expect(dots[0].className).toContain("bg-[#34d399]");
    // Error agent dot should be red
    expect(dots[1].className).toContain("bg-[#f87171]");
    // Idle agent dot should be gray
    expect(dots[2].className).toContain("bg-[#64748b]");
  });
});
