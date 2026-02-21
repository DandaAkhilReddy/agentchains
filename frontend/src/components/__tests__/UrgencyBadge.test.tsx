import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import UrgencyBadge from "../UrgencyBadge";

describe("UrgencyBadge", () => {
  it("renders Critical label for score >= 0.8", () => {
    render(<UrgencyBadge score={0.9} />);
    expect(screen.getByText("Critical")).toBeInTheDocument();
  });

  it("renders High label for score >= 0.6 and < 0.8", () => {
    render(<UrgencyBadge score={0.7} />);
    expect(screen.getByText("High")).toBeInTheDocument();
  });

  it("renders Medium label for score >= 0.3 and < 0.6", () => {
    render(<UrgencyBadge score={0.45} />);
    expect(screen.getByText("Medium")).toBeInTheDocument();
  });

  it("renders Low label for score < 0.3", () => {
    render(<UrgencyBadge score={0.1} />);
    expect(screen.getByText("Low")).toBeInTheDocument();
  });

  it("applies red styling for Critical urgency", () => {
    const { container } = render(<UrgencyBadge score={0.85} />);
    const badge = container.querySelector("span");
    expect(badge?.className).toContain("text-[#f87171]");
    expect(badge?.className).toContain("pulse-dot");
  });

  it("applies red styling without pulse-dot for High urgency", () => {
    const { container } = render(<UrgencyBadge score={0.65} />);
    const badge = container.querySelector("span");
    expect(badge?.className).toContain("text-[#f87171]");
    expect(badge?.className).not.toContain("pulse-dot");
  });

  it("applies yellow styling for Medium urgency", () => {
    const { container } = render(<UrgencyBadge score={0.5} />);
    const badge = container.querySelector("span");
    expect(badge?.className).toContain("text-[#fbbf24]");
  });

  it("applies green styling for Low urgency", () => {
    const { container } = render(<UrgencyBadge score={0.2} />);
    const badge = container.querySelector("span");
    expect(badge?.className).toContain("text-[#34d399]");
  });

  it("includes base badge styling classes", () => {
    const { container } = render(<UrgencyBadge score={0.5} />);
    const badge = container.querySelector("span");
    expect(badge?.className).toContain("inline-flex");
    expect(badge?.className).toContain("items-center");
    expect(badge?.className).toContain("rounded-full");
    expect(badge?.className).toContain("px-2");
    expect(badge?.className).toContain("py-0.5");
    expect(badge?.className).toContain("text-xs");
    expect(badge?.className).toContain("font-medium");
  });

  it("renders Low for boundary score of 0", () => {
    render(<UrgencyBadge score={0} />);
    expect(screen.getByText("Low")).toBeInTheDocument();
  });

  it("renders Critical for boundary score of 1", () => {
    render(<UrgencyBadge score={1} />);
    expect(screen.getByText("Critical")).toBeInTheDocument();
  });
});
