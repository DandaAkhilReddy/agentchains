import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import LatencyBar from "../LatencyBar";

describe("LatencyBar", () => {
  it("renders the latency label by default", () => {
    render(<LatencyBar latencyMs={120} />);
    expect(screen.getByText("120ms")).toBeInTheDocument();
  });

  it("hides the label when showLabel is false", () => {
    render(<LatencyBar latencyMs={120} showLabel={false} />);
    expect(screen.queryByText("120ms")).not.toBeInTheDocument();
  });

  it("renders green bar for latency below 50ms", () => {
    const { container } = render(<LatencyBar latencyMs={30} />);
    const bar = container.querySelector(".animate-grow-bar") as HTMLElement;
    expect(bar.style.backgroundColor).toBe("rgb(22, 163, 74)");
    // Label color should match
    const label = screen.getByText("30ms");
    expect(label.style.color).toBe("rgb(22, 163, 74)");
  });

  it("renders blue bar for latency between 50ms and 100ms", () => {
    const { container } = render(<LatencyBar latencyMs={75} />);
    const bar = container.querySelector(".animate-grow-bar") as HTMLElement;
    expect(bar.style.backgroundColor).toBe("rgb(59, 130, 246)");
  });

  it("renders amber bar for latency between 101ms and 300ms", () => {
    const { container } = render(<LatencyBar latencyMs={200} />);
    const bar = container.querySelector(".animate-grow-bar") as HTMLElement;
    expect(bar.style.backgroundColor).toBe("rgb(217, 119, 6)");
  });

  it("renders red bar for latency above 300ms", () => {
    const { container } = render(<LatencyBar latencyMs={450} />);
    const bar = container.querySelector(".animate-grow-bar") as HTMLElement;
    expect(bar.style.backgroundColor).toBe("rgb(220, 38, 38)");
  });

  it("calculates correct bar width percentage", () => {
    const { container } = render(<LatencyBar latencyMs={250} maxMs={500} />);
    const bar = container.querySelector(".animate-grow-bar") as HTMLElement;
    expect(bar.style.width).toBe("50%");
  });

  it("clamps bar width to 100% when latency exceeds maxMs", () => {
    const { container } = render(<LatencyBar latencyMs={800} maxMs={500} />);
    const bar = container.querySelector(".animate-grow-bar") as HTMLElement;
    expect(bar.style.width).toBe("100%");
  });

  it("uses small track height for sm size", () => {
    const { container } = render(<LatencyBar latencyMs={100} size="sm" />);
    const track = container.querySelector(".h-1\\.5");
    expect(track).toBeInTheDocument();
  });

  it("uses medium track height for md size (default)", () => {
    const { container } = render(<LatencyBar latencyMs={100} />);
    const track = container.querySelector(".h-2");
    expect(track).toBeInTheDocument();
  });

  it("applies custom className to the wrapper", () => {
    const { container } = render(
      <LatencyBar latencyMs={100} className="my-latency" />,
    );
    const wrapper = container.firstElementChild as HTMLElement;
    expect(wrapper.className).toContain("my-latency");
  });

  it("renders 0% width bar for 0ms latency", () => {
    const { container } = render(<LatencyBar latencyMs={0} />);
    const bar = container.querySelector(".animate-grow-bar") as HTMLElement;
    expect(bar.style.width).toBe("0%");
  });

  it("uses green color at exactly 49ms (boundary)", () => {
    const { container } = render(<LatencyBar latencyMs={49} />);
    const bar = container.querySelector(".animate-grow-bar") as HTMLElement;
    expect(bar.style.backgroundColor).toBe("rgb(22, 163, 74)");
  });

  it("uses blue color at exactly 50ms (boundary)", () => {
    const { container } = render(<LatencyBar latencyMs={50} />);
    const bar = container.querySelector(".animate-grow-bar") as HTMLElement;
    expect(bar.style.backgroundColor).toBe("rgb(59, 130, 246)");
  });
});
