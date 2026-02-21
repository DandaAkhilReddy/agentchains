import React from "react";
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import A2UIStepsWidget, { type StepItem } from "../A2UIStepsWidget";

describe("A2UIStepsWidget", () => {
  it("renders empty state when no steps are provided", () => {
    render(<A2UIStepsWidget steps={[]} />);
    expect(screen.getByText("No steps defined.")).toBeInTheDocument();
  });

  it("renders step labels", () => {
    const steps: StepItem[] = [
      { label: "Step One", status: "completed" },
      { label: "Step Two", status: "active" },
    ];
    render(<A2UIStepsWidget steps={steps} />);
    expect(screen.getByText("Step One")).toBeInTheDocument();
    expect(screen.getByText("Step Two")).toBeInTheDocument();
  });

  it("renders step descriptions when provided", () => {
    const steps: StepItem[] = [
      { label: "Init", status: "completed", description: "Initialize project" },
      { label: "Build", status: "pending", description: "Build the application" },
    ];
    render(<A2UIStepsWidget steps={steps} />);
    expect(screen.getByText("Initialize project")).toBeInTheDocument();
    expect(screen.getByText("Build the application")).toBeInTheDocument();
  });

  it("does not render description paragraph when description is omitted", () => {
    const steps: StepItem[] = [{ label: "No desc", status: "pending" }];
    const { container } = render(<A2UIStepsWidget steps={steps} />);
    const descParagraphs = container.querySelectorAll(".text-xs.leading-relaxed");
    expect(descParagraphs).toHaveLength(0);
  });

  it("renders title when provided", () => {
    const steps: StepItem[] = [{ label: "Task", status: "active" }];
    render(<A2UIStepsWidget steps={steps} title="Deployment Pipeline" />);
    expect(screen.getByText("Deployment Pipeline")).toBeInTheDocument();
  });

  it("does not render title heading when title is omitted", () => {
    const steps: StepItem[] = [{ label: "Task", status: "active" }];
    const { container } = render(<A2UIStepsWidget steps={steps} />);
    expect(container.querySelector("h3")).not.toBeInTheDocument();
  });

  it("renders status badges for each step", () => {
    const steps: StepItem[] = [
      { label: "A", status: "completed" },
      { label: "B", status: "active" },
      { label: "C", status: "pending" },
      { label: "D", status: "error" },
    ];
    render(<A2UIStepsWidget steps={steps} />);
    expect(screen.getByText("completed")).toBeInTheDocument();
    expect(screen.getByText("active")).toBeInTheDocument();
    expect(screen.getByText("pending")).toBeInTheDocument();
    expect(screen.getByText("error")).toBeInTheDocument();
  });

  it("renders progress summary with completed count", () => {
    const steps: StepItem[] = [
      { label: "A", status: "completed" },
      { label: "B", status: "completed" },
      { label: "C", status: "active" },
      { label: "D", status: "pending" },
    ];
    render(<A2UIStepsWidget steps={steps} />);
    expect(screen.getByText("2 of 4 completed")).toBeInTheDocument();
  });

  it("renders progress percentage", () => {
    const steps: StepItem[] = [
      { label: "A", status: "completed" },
      { label: "B", status: "pending" },
    ];
    render(<A2UIStepsWidget steps={steps} />);
    expect(screen.getByText("50%")).toBeInTheDocument();
  });

  it("renders 0% when no steps are completed", () => {
    const steps: StepItem[] = [
      { label: "A", status: "pending" },
      { label: "B", status: "active" },
    ];
    render(<A2UIStepsWidget steps={steps} />);
    expect(screen.getByText("0%")).toBeInTheDocument();
  });

  it("renders 100% when all steps are completed", () => {
    const steps: StepItem[] = [
      { label: "A", status: "completed" },
      { label: "B", status: "completed" },
      { label: "C", status: "completed" },
    ];
    render(<A2UIStepsWidget steps={steps} />);
    expect(screen.getByText("100%")).toBeInTheDocument();
  });

  it("displays error count when there are errors", () => {
    const steps: StepItem[] = [
      { label: "A", status: "completed" },
      { label: "B", status: "error" },
      { label: "C", status: "error" },
    ];
    render(<A2UIStepsWidget steps={steps} />);
    expect(screen.getByText("(2 errors)")).toBeInTheDocument();
  });

  it("displays singular error text for one error", () => {
    const steps: StepItem[] = [
      { label: "A", status: "completed" },
      { label: "B", status: "error" },
    ];
    render(<A2UIStepsWidget steps={steps} />);
    expect(screen.getByText("(1 error)")).toBeInTheDocument();
  });

  it("does not display error count when there are no errors", () => {
    const steps: StepItem[] = [
      { label: "A", status: "completed" },
      { label: "B", status: "pending" },
    ];
    render(<A2UIStepsWidget steps={steps} />);
    expect(screen.queryByText(/error/)).not.toBeInTheDocument();
  });

  it("renders connector lines between steps but not after the last", () => {
    const steps: StepItem[] = [
      { label: "First", status: "completed" },
      { label: "Second", status: "active" },
      { label: "Third", status: "pending" },
    ];
    const { container } = render(<A2UIStepsWidget steps={steps} />);
    // Connector lines have the class min-h-[24px]
    const connectors = container.querySelectorAll(".min-h-\\[24px\\]");
    // Should be 2 connectors (between step 1-2 and step 2-3, none after step 3)
    expect(connectors).toHaveLength(2);
  });
});
