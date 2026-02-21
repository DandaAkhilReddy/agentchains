import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import ProgressRing from "../ProgressRing";

describe("ProgressRing", () => {
  it("renders an SVG with two circles (track and progress)", () => {
    const { container } = render(<ProgressRing value={50} />);
    const svg = container.querySelector("svg");
    expect(svg).toBeInTheDocument();

    const circles = container.querySelectorAll("circle");
    expect(circles.length).toBe(2);
  });

  it("shows correct percentage label by default", () => {
    render(<ProgressRing value={75} />);
    expect(screen.getByText("75")).toBeInTheDocument();
  });

  it("renders 0% as an empty ring with full offset", () => {
    const { container } = render(<ProgressRing value={0} />);
    const circles = container.querySelectorAll("circle");
    const progressCircle = circles[1];

    // For 0%, strokeDashoffset should equal the circumference (full offset)
    const defaultSize = 48;
    const defaultStrokeWidth = 4;
    const radius = (defaultSize - defaultStrokeWidth) / 2;
    const circumference = 2 * Math.PI * radius;

    const offset = Number(progressCircle.getAttribute("stroke-dashoffset"));
    expect(offset).toBeCloseTo(circumference, 1);
  });

  it("renders 100% as a full ring with zero offset", () => {
    const { container } = render(<ProgressRing value={100} />);
    const circles = container.querySelectorAll("circle");
    const progressCircle = circles[1];

    const offset = Number(progressCircle.getAttribute("stroke-dashoffset"));
    expect(offset).toBeCloseTo(0, 1);
  });

  it("computes correct offset for 50%", () => {
    const { container } = render(<ProgressRing value={50} />);
    const circles = container.querySelectorAll("circle");
    const progressCircle = circles[1];

    const defaultSize = 48;
    const defaultStrokeWidth = 4;
    const radius = (defaultSize - defaultStrokeWidth) / 2;
    const circumference = 2 * Math.PI * radius;
    const expectedOffset = circumference - (50 / 100) * circumference;

    const offset = Number(progressCircle.getAttribute("stroke-dashoffset"));
    expect(offset).toBeCloseTo(expectedOffset, 1);
  });

  it("applies custom size to the SVG and container", () => {
    const customSize = 80;
    const { container } = render(<ProgressRing value={60} size={customSize} />);

    const svg = container.querySelector("svg");
    expect(svg?.getAttribute("width")).toBe(String(customSize));
    expect(svg?.getAttribute("height")).toBe(String(customSize));

    const wrapper = container.firstElementChild as HTMLElement;
    expect(wrapper.style.width).toBe(`${customSize}px`);
    expect(wrapper.style.height).toBe(`${customSize}px`);
  });

  it("applies custom strokeWidth", () => {
    const customStroke = 8;
    const customSize = 60;
    const { container } = render(
      <ProgressRing value={50} size={customSize} strokeWidth={customStroke} />
    );

    const circles = container.querySelectorAll("circle");
    // Both circles should use the custom stroke width
    expect(circles[0].getAttribute("stroke-width")).toBe(String(customStroke));
    expect(circles[1].getAttribute("stroke-width")).toBe(String(customStroke));

    // Radius should reflect custom strokeWidth
    const expectedRadius = (customSize - customStroke) / 2;
    expect(Number(circles[0].getAttribute("r"))).toBeCloseTo(expectedRadius, 1);
  });

  it("uses named color from the COLORS map", () => {
    const { container } = render(<ProgressRing value={50} color="cyan" />);
    const progressCircle = container.querySelectorAll("circle")[1];
    expect(progressCircle.getAttribute("stroke")).toBe("#60a5fa");
  });

  it("uses raw color string when not found in COLORS map", () => {
    const { container } = render(<ProgressRing value={50} color="#ff00ff" />);
    const progressCircle = container.querySelectorAll("circle")[1];
    expect(progressCircle.getAttribute("stroke")).toBe("#ff00ff");
  });

  it("auto-colors red for values below 30 when no color prop", () => {
    const { container } = render(<ProgressRing value={20} />);
    const progressCircle = container.querySelectorAll("circle")[1];
    expect(progressCircle.getAttribute("stroke")).toBe("#f87171");
  });

  it("auto-colors amber for values between 30 and 70 when no color prop", () => {
    const { container } = render(<ProgressRing value={50} />);
    const progressCircle = container.querySelectorAll("circle")[1];
    expect(progressCircle.getAttribute("stroke")).toBe("#fbbf24");
  });

  it("auto-colors green for values above 70 when no color prop", () => {
    const { container } = render(<ProgressRing value={85} />);
    const progressCircle = container.querySelectorAll("circle")[1];
    expect(progressCircle.getAttribute("stroke")).toBe("#34d399");
  });

  it("hides the label when showLabel is false", () => {
    render(<ProgressRing value={42} showLabel={false} />);
    expect(screen.queryByText("42")).not.toBeInTheDocument();
  });

  it("clamps values above 100 for ring calculation", () => {
    const { container } = render(<ProgressRing value={150} />);
    const circles = container.querySelectorAll("circle");
    const progressCircle = circles[1];

    // Offset should be 0 (clamped to 100%)
    const offset = Number(progressCircle.getAttribute("stroke-dashoffset"));
    expect(offset).toBeCloseTo(0, 1);

    // But the label shows the raw value rounded
    expect(screen.getByText("150")).toBeInTheDocument();
  });

  it("clamps values below 0 for ring calculation", () => {
    const { container } = render(<ProgressRing value={-20} />);
    const circles = container.querySelectorAll("circle");
    const progressCircle = circles[1];

    // Offset should equal circumference (clamped to 0%)
    const defaultSize = 48;
    const defaultStrokeWidth = 4;
    const radius = (defaultSize - defaultStrokeWidth) / 2;
    const circumference = 2 * Math.PI * radius;

    const offset = Number(progressCircle.getAttribute("stroke-dashoffset"));
    expect(offset).toBeCloseTo(circumference, 1);
  });

  it("uses track circle with correct background color", () => {
    const { container } = render(<ProgressRing value={50} />);
    const trackCircle = container.querySelectorAll("circle")[0];
    expect(trackCircle.getAttribute("stroke")).toBe("#1a2035");
    expect(trackCircle.getAttribute("fill")).toBe("none");
  });
});
