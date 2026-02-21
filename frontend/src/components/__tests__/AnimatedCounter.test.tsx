import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, act } from "@testing-library/react";
import AnimatedCounter from "../AnimatedCounter";

/**
 * AnimatedCounter relies on requestAnimationFrame to animate values.
 * We mock rAF so the animation completes synchronously in tests.
 */

let rafCallbacks: Array<(time: number) => void> = [];
let rafId = 0;

beforeEach(() => {
  rafCallbacks = [];
  rafId = 0;

  vi.spyOn(window, "requestAnimationFrame").mockImplementation((cb) => {
    rafCallbacks.push(cb);
    return ++rafId;
  });

  vi.spyOn(window, "cancelAnimationFrame").mockImplementation(() => {});

  vi.spyOn(performance, "now").mockReturnValue(0);
});

afterEach(() => {
  vi.restoreAllMocks();
});

/** Flush all queued rAF callbacks, simulating animation completion. */
function flushAnimation(endTime: number) {
  (performance.now as ReturnType<typeof vi.fn>).mockReturnValue(endTime);
  // Run callbacks repeatedly until none are queued (animation settles)
  let safety = 0;
  while (rafCallbacks.length > 0 && safety < 50) {
    const cbs = [...rafCallbacks];
    rafCallbacks = [];
    for (const cb of cbs) {
      cb(endTime);
    }
    safety++;
  }
}

describe("AnimatedCounter", () => {
  it("renders with initial value of zero before animation", () => {
    const { container } = render(<AnimatedCounter value={0} />);
    const span = container.querySelector("span");
    expect(span).toBeInTheDocument();
    // Value 0 means delta = 0, so display stays 0
    expect(span?.textContent).toBe("0");
  });

  it("displays formatted number with locale separators after animation", () => {
    render(<AnimatedCounter value={1234} />);

    act(() => {
      flushAnimation(700);
    });

    // toLocaleString on 1234 should produce "1,234" in en-US
    expect(screen.getByText("1,234")).toBeInTheDocument();
  });

  it("handles zero value", () => {
    const { container } = render(<AnimatedCounter value={0} />);

    act(() => {
      flushAnimation(700);
    });

    const span = container.querySelector("span");
    expect(span?.textContent).toBe("0");
  });

  it("handles negative values", () => {
    render(<AnimatedCounter value={-50} />);

    act(() => {
      flushAnimation(700);
    });

    // After animation completes, display should be -50
    const span = screen.getByText(
      (content) => content.includes("-50") || content.includes("\u221250")
    );
    expect(span).toBeInTheDocument();
  });

  it("handles large numbers with locale formatting", () => {
    render(<AnimatedCounter value={1000000} />);

    act(() => {
      flushAnimation(700);
    });

    expect(screen.getByText("1,000,000")).toBeInTheDocument();
  });

  it("applies custom className", () => {
    const { container } = render(
      <AnimatedCounter value={42} className="text-xl text-red-500" />
    );
    const span = container.querySelector("span");
    expect(span?.className).toContain("text-xl");
    expect(span?.className).toContain("text-red-500");
    // Also retains base classes
    expect(span?.className).toContain("font-mono");
  });

  it("applies glow text-shadow style when glow prop is true", () => {
    const { container } = render(<AnimatedCounter value={100} glow />);
    const span = container.querySelector("span");
    expect(span?.style.textShadow).toContain("rgba(96,165,250,0.3)");
  });

  it("does not apply text-shadow when glow is false", () => {
    const { container } = render(<AnimatedCounter value={100} />);
    const span = container.querySelector("span");
    expect(span?.style.textShadow).toBe("");
  });

  it("formats with fixed decimals when decimals prop is provided", () => {
    render(<AnimatedCounter value={3.14} decimals={2} />);

    act(() => {
      flushAnimation(700);
    });

    expect(screen.getByText("3.14")).toBeInTheDocument();
  });

  it("renders zero decimals with toFixed when decimals is 0", () => {
    render(<AnimatedCounter value={42} decimals={0} />);

    act(() => {
      flushAnimation(700);
    });

    expect(screen.getByText("42")).toBeInTheDocument();
  });

  it("uses default font-mono and text color classes", () => {
    const { container } = render(<AnimatedCounter value={10} />);
    const span = container.querySelector("span");
    expect(span?.className).toContain("font-mono");
    expect(span?.className).toContain("text-[#e2e8f0]");
  });
});
