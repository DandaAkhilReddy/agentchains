import { describe, it, expect } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import PipelineStepCard from "../PipelineStep";
import type { PipelineStep } from "../../../types/api";

function makeStep(overrides: Partial<PipelineStep> = {}): PipelineStep {
  return {
    id: "step-1",
    agentId: "agent-1",
    agentName: "MarketAgent",
    action: "fetch_listings",
    status: "completed",
    startedAt: "2026-02-21T10:00:00Z",
    completedAt: "2026-02-21T10:00:01Z",
    latencyMs: 150,
    ...overrides,
  };
}

describe("PipelineStepCard", () => {
  it("renders step card with action name", () => {
    render(<PipelineStepCard step={makeStep()} index={1} />);
    expect(screen.getByText("fetch_listings")).toBeInTheDocument();
    // The step index badge should be visible
    expect(screen.getByText("1")).toBeInTheDocument();
  });

  it("shows correct status icons for each status", () => {
    const statuses: PipelineStep["status"][] = [
      "waiting",
      "running",
      "completed",
      "failed",
    ];

    for (const status of statuses) {
      const { container, unmount } = render(
        <PipelineStepCard step={makeStep({ status })} index={0} />
      );
      // Each status maps to a specific dot color class
      const dotEl = container.querySelector(".pipeline-step-dot");
      expect(dotEl).toBeInTheDocument();

      if (status === "completed") {
        expect(dotEl?.className).toContain("border-[#34d399]");
      } else if (status === "failed") {
        expect(dotEl?.className).toContain("border-[#f87171]");
      } else if (status === "running") {
        expect(dotEl?.className).toContain("border-[#60a5fa]");
      } else if (status === "waiting") {
        expect(dotEl?.className).toContain("border-[rgba(255,255,255,0.06)]");
      }
      unmount();
    }
  });

  it("shows step duration when latencyMs is provided", () => {
    render(<PipelineStepCard step={makeStep({ latencyMs: 320 })} index={0} />);
    expect(screen.getByText("320ms")).toBeInTheDocument();
  });

  it("shows step inputs and outputs when expanded", () => {
    const step = makeStep({
      toolCall: {
        name: "search_market",
        input: { query: "widgets" },
        output: { results: 42 },
      },
    });
    render(<PipelineStepCard step={step} index={0} />);

    // Click to expand
    const button = screen.getByRole("button");
    fireEvent.click(button);

    // Tool name visible
    expect(screen.getByText("search_market")).toBeInTheDocument();
    // Input section
    expect(screen.getByText("Input")).toBeInTheDocument();
    // Output section
    expect(screen.getByText("Output")).toBeInTheDocument();
    // Actual input content
    expect(screen.getByText(/widgets/)).toBeInTheDocument();
    // Actual output content
    expect(screen.getByText(/42/)).toBeInTheDocument();
  });

  it("handles click to expand and collapse details", () => {
    const step = makeStep({
      toolCall: {
        name: "analyze",
        input: { data: "test" },
      },
    });
    render(<PipelineStepCard step={step} index={0} />);
    const button = screen.getByRole("button");

    // Initially collapsed -- tool name should not be shown
    expect(screen.queryByText("analyze")).not.toBeInTheDocument();

    // Click to expand
    fireEvent.click(button);
    expect(screen.getByText("analyze")).toBeInTheDocument();
    expect(screen.getByText("Input")).toBeInTheDocument();

    // Click again to collapse
    fireEvent.click(button);
    expect(screen.queryByText("Input")).not.toBeInTheDocument();
  });

  it("shows error message in expanded state", () => {
    const step = makeStep({
      status: "failed",
      error: "Connection timed out",
      toolCall: {
        name: "call_api",
        input: { url: "/market" },
      },
    });
    render(<PipelineStepCard step={step} index={0} />);

    // Expand
    fireEvent.click(screen.getByRole("button"));

    expect(screen.getByText(/Connection timed out/)).toBeInTheDocument();
  });
});
