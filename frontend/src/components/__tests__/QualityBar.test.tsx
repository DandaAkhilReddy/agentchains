import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import QualityBar from "../QualityBar";

describe("QualityBar", () => {
  it("renders bar with percentage text", () => {
    render(<QualityBar score={0.75} />);
    expect(screen.getByText("75%")).toBeInTheDocument();
  });

  it("shows correct width for a mid-range score", () => {
    const { container } = render(<QualityBar score={0.5} />);
    const innerBar = container.querySelector(
      "[style]",
    ) as HTMLElement;
    expect(innerBar).toBeInTheDocument();
    expect(innerBar.style.width).toBe("50%");
  });

  it("applies green/cyan gradient for high scores (>= 0.7)", () => {
    const { container } = render(<QualityBar score={0.85} />);
    const innerBar = container.querySelector(
      ".bg-gradient-to-r",
    ) as HTMLElement;
    expect(innerBar).toBeInTheDocument();
    expect(innerBar.className).toContain("from-[#34d399]");
    expect(innerBar.className).toContain("to-[#22d3ee]");
  });

  it("applies yellow/orange gradient for medium scores (0.4 - 0.69)", () => {
    const { container } = render(<QualityBar score={0.5} />);
    const innerBar = container.querySelector(
      ".bg-gradient-to-r",
    ) as HTMLElement;
    expect(innerBar).toBeInTheDocument();
    expect(innerBar.className).toContain("from-[#fbbf24]");
    expect(innerBar.className).toContain("to-[#fb923c]");
  });

  it("applies red/orange gradient for low scores (< 0.4)", () => {
    const { container } = render(<QualityBar score={0.2} />);
    const innerBar = container.querySelector(
      ".bg-gradient-to-r",
    ) as HTMLElement;
    expect(innerBar).toBeInTheDocument();
    expect(innerBar.className).toContain("from-[#f87171]");
    expect(innerBar.className).toContain("to-[#fb923c]");
  });

  it("handles edge case score of 0", () => {
    const { container } = render(<QualityBar score={0} />);
    expect(screen.getByText("0%")).toBeInTheDocument();
    const innerBar = container.querySelector(
      "[style]",
    ) as HTMLElement;
    expect(innerBar.style.width).toBe("0%");
  });

  it("handles edge case score of 1 (100%)", () => {
    const { container } = render(<QualityBar score={1} />);
    expect(screen.getByText("100%")).toBeInTheDocument();
    const innerBar = container.querySelector(
      "[style]",
    ) as HTMLElement;
    expect(innerBar.style.width).toBe("100%");
  });

  it("adds glow class for high quality scores (>= 0.7)", () => {
    const { container } = render(<QualityBar score={0.8} />);
    const outerBar = container.querySelector(".w-16");
    expect(outerBar?.className).toContain(
      "shadow-[0_0_8px_rgba(52,211,153,0.3)]",
    );
  });

  it("does not add glow class for low quality scores (< 0.7)", () => {
    const { container } = render(<QualityBar score={0.5} />);
    const outerBar = container.querySelector(".w-16");
    expect(outerBar?.className).not.toContain(
      "shadow-[0_0_8px_rgba(52,211,153,0.3)]",
    );
  });
});
