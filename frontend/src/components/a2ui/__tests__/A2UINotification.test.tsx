import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, fireEvent, act } from "@testing-library/react";
import A2UINotification from "../A2UINotification";
import type { A2UINotifyMessage } from "../../../types/a2ui";

const makeNotification = (overrides?: Partial<A2UINotifyMessage>): A2UINotifyMessage => ({
  level: "info",
  title: "Test Notification",
  message: "This is a test",
  duration_ms: 5000,
  ...overrides,
});

describe("A2UINotification", () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("returns null when notifications array is empty", () => {
    const { container } = render(<A2UINotification notifications={[]} />);
    expect(container.firstChild).toBeNull();
  });

  it("renders notification title", () => {
    render(<A2UINotification notifications={[makeNotification()]} />);
    expect(screen.getByText("Test Notification")).toBeInTheDocument();
  });

  it("renders notification message", () => {
    render(<A2UINotification notifications={[makeNotification()]} />);
    expect(screen.getByText("This is a test")).toBeInTheDocument();
  });

  it("renders without message when message is undefined", () => {
    render(
      <A2UINotification notifications={[makeNotification({ message: undefined })]} />
    );
    expect(screen.getByText("Test Notification")).toBeInTheDocument();
  });

  it("renders multiple notifications", () => {
    render(
      <A2UINotification
        notifications={[
          makeNotification({ title: "First" }),
          makeNotification({ title: "Second" }),
          makeNotification({ title: "Third" }),
        ]}
      />
    );
    expect(screen.getByText("First")).toBeInTheDocument();
    expect(screen.getByText("Second")).toBeInTheDocument();
    expect(screen.getByText("Third")).toBeInTheDocument();
  });

  it("renders info level notification with blue border", () => {
    const { container } = render(
      <A2UINotification notifications={[makeNotification({ level: "info" })]} />
    );
    const toast = container.querySelector(".animate-slide-in");
    expect(toast).toHaveStyle({ borderLeft: "4px solid #60a5fa" });
  });

  it("renders success level notification with green border", () => {
    const { container } = render(
      <A2UINotification notifications={[makeNotification({ level: "success" })]} />
    );
    const toast = container.querySelector(".animate-slide-in");
    expect(toast).toHaveStyle({ borderLeft: "4px solid #34d399" });
  });

  it("renders warning level notification with yellow border", () => {
    const { container } = render(
      <A2UINotification notifications={[makeNotification({ level: "warning" })]} />
    );
    const toast = container.querySelector(".animate-slide-in");
    expect(toast).toHaveStyle({ borderLeft: "4px solid #fbbf24" });
  });

  it("renders error level notification with red border", () => {
    const { container } = render(
      <A2UINotification notifications={[makeNotification({ level: "error" })]} />
    );
    const toast = container.querySelector(".animate-slide-in");
    expect(toast).toHaveStyle({ borderLeft: "4px solid #f87171" });
  });

  it("dismisses notification on close button click", () => {
    render(
      <A2UINotification notifications={[makeNotification({ duration_ms: 0 })]} />
    );
    const closeBtn = screen.getByRole("button");
    fireEvent.click(closeBtn);
    expect(screen.queryByText("Test Notification")).not.toBeInTheDocument();
  });

  it("auto-dismisses after duration elapses", () => {
    render(
      <A2UINotification notifications={[makeNotification({ duration_ms: 1000 })]} />
    );
    expect(screen.getByText("Test Notification")).toBeInTheDocument();
    act(() => {
      vi.advanceTimersByTime(1100);
    });
    expect(screen.queryByText("Test Notification")).not.toBeInTheDocument();
  });

  it("defaults to 5000ms duration when duration_ms is undefined", () => {
    render(
      <A2UINotification notifications={[makeNotification({ duration_ms: undefined })]} />
    );
    expect(screen.getByText("Test Notification")).toBeInTheDocument();
    act(() => {
      vi.advanceTimersByTime(4000);
    });
    expect(screen.getByText("Test Notification")).toBeInTheDocument();
    act(() => {
      vi.advanceTimersByTime(1200);
    });
    expect(screen.queryByText("Test Notification")).not.toBeInTheDocument();
  });

  it("renders in fixed position at bottom-right", () => {
    const { container } = render(
      <A2UINotification notifications={[makeNotification()]} />
    );
    const wrapper = container.firstChild as HTMLElement;
    expect(wrapper.className).toContain("fixed");
    expect(wrapper.className).toContain("bottom-4");
    expect(wrapper.className).toContain("right-4");
    expect(wrapper.className).toContain("z-50");
  });

  it("renders countdown bar for timed notifications", () => {
    const { container } = render(
      <A2UINotification notifications={[makeNotification({ duration_ms: 5000 })]} />
    );
    const bar = container.querySelector(".absolute.bottom-0");
    expect(bar).toBeInTheDocument();
  });

  it("does not start timer when duration is 0", () => {
    render(
      <A2UINotification notifications={[makeNotification({ duration_ms: 0 })]} />
    );
    act(() => {
      vi.advanceTimersByTime(10000);
    });
    // Still visible because duration 0 means no auto-dismiss
    expect(screen.getByText("Test Notification")).toBeInTheDocument();
  });
});
