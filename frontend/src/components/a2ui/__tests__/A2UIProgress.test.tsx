import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import A2UIProgress from "../A2UIProgress";
import type { A2UIProgressMessage } from "../../../types/a2ui";

const makeDeterminate = (overrides?: Partial<A2UIProgressMessage>): A2UIProgressMessage => ({
  task_id: "task-1",
  progress_type: "determinate",
  value: 50,
  total: 100,
  message: "Processing...",
  ...overrides,
});

const makeIndeterminate = (overrides?: Partial<A2UIProgressMessage>): A2UIProgressMessage => ({
  task_id: "task-2",
  progress_type: "indeterminate",
  message: "Loading...",
  ...overrides,
});

const makeStreaming = (overrides?: Partial<A2UIProgressMessage>): A2UIProgressMessage => ({
  task_id: "task-3",
  progress_type: "streaming",
  message: "Streaming data...",
  ...overrides,
});

describe("A2UIProgress", () => {
  describe("determinate progress", () => {
    it("renders message text", () => {
      render(<A2UIProgress progress={makeDeterminate()} />);
      expect(screen.getByText("Processing...")).toBeInTheDocument();
    });

    it("displays correct percentage", () => {
      render(<A2UIProgress progress={makeDeterminate({ value: 75, total: 100 })} />);
      expect(screen.getByText("75%")).toBeInTheDocument();
    });

    it("calculates percentage correctly for partial values", () => {
      render(<A2UIProgress progress={makeDeterminate({ value: 1, total: 3 })} />);
      expect(screen.getByText("33%")).toBeInTheDocument();
    });

    it("caps percentage at 100%", () => {
      render(<A2UIProgress progress={makeDeterminate({ value: 150, total: 100 })} />);
      expect(screen.getByText("100%")).toBeInTheDocument();
    });

    it("shows value/total detail", () => {
      render(<A2UIProgress progress={makeDeterminate({ value: 25, total: 50 })} />);
      expect(screen.getByText("25 / 50")).toBeInTheDocument();
    });

    it("shows 0 when value is undefined", () => {
      render(<A2UIProgress progress={makeDeterminate({ value: undefined, total: 100 })} />);
      expect(screen.getByText("0%")).toBeInTheDocument();
      expect(screen.getByText("0 / 100")).toBeInTheDocument();
    });

    it("renders progress bar with correct width", () => {
      const { container } = render(
        <A2UIProgress progress={makeDeterminate({ value: 60, total: 100 })} />
      );
      const bar = container.querySelector(".bg-gradient-to-r.from-\\[\\#3b82f6\\]");
      expect(bar).toHaveStyle({ width: "60%" });
    });

    it("renders 0% bar when total is 0", () => {
      render(<A2UIProgress progress={makeDeterminate({ value: 50, total: 0 })} />);
      // total is 0, so percentage defaults to 0
      expect(screen.getByText("0%")).toBeInTheDocument();
    });
  });

  describe("indeterminate progress", () => {
    it("renders message text", () => {
      render(<A2UIProgress progress={makeIndeterminate()} />);
      expect(screen.getByText("Loading...")).toBeInTheDocument();
    });

    it("does not display percentage", () => {
      render(<A2UIProgress progress={makeIndeterminate()} />);
      expect(screen.queryByText("%")).not.toBeInTheDocument();
    });

    it("renders animated bar element", () => {
      const { container } = render(<A2UIProgress progress={makeIndeterminate()} />);
      expect(container.querySelector(".animate-indeterminate")).toBeInTheDocument();
    });

    it("does not show value/total detail", () => {
      render(<A2UIProgress progress={makeIndeterminate()} />);
      expect(screen.queryByText("/")).not.toBeInTheDocument();
    });
  });

  describe("streaming progress", () => {
    it("renders message text", () => {
      render(<A2UIProgress progress={makeStreaming()} />);
      expect(screen.getByText("Streaming data...")).toBeInTheDocument();
    });

    it("shows Streaming label", () => {
      render(<A2UIProgress progress={makeStreaming()} />);
      expect(screen.getByText("Streaming")).toBeInTheDocument();
    });

    it("renders animated dots", () => {
      const { container } = render(<A2UIProgress progress={makeStreaming()} />);
      const dots = container.querySelectorAll(".animate-bounce");
      expect(dots.length).toBe(3);
    });

    it("renders pulse bar", () => {
      const { container } = render(<A2UIProgress progress={makeStreaming()} />);
      expect(container.querySelector(".animate-pulse")).toBeInTheDocument();
    });
  });

  describe("common behavior", () => {
    it("falls back to task_id when message is not provided", () => {
      render(
        <A2UIProgress
          progress={{ task_id: "my-task", progress_type: "indeterminate" }}
        />
      );
      expect(screen.getByText("Task my-task")).toBeInTheDocument();
    });

    it("renders container with correct styling", () => {
      const { container } = render(<A2UIProgress progress={makeDeterminate()} />);
      const wrapper = container.firstChild as HTMLElement;
      expect(wrapper.className).toContain("rounded-2xl");
      expect(wrapper.className).toContain("bg-[#141928]");
    });

    it("includes indeterminate keyframes style block", () => {
      const { container } = render(<A2UIProgress progress={makeIndeterminate()} />);
      const style = container.querySelector("style");
      expect(style?.textContent).toContain("@keyframes indeterminate");
    });
  });
});
