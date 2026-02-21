import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, fireEvent, act } from "@testing-library/react";
import A2UIConfirmDialog from "../A2UIConfirmDialog";
import type { A2UIConfirmMessage } from "../../../types/a2ui";

const makeConfirm = (overrides?: Partial<A2UIConfirmMessage>): A2UIConfirmMessage => ({
  request_id: "req-001",
  title: "Confirm Action",
  description: "Are you sure you want to proceed?",
  severity: "info",
  timeout_seconds: 30,
  ...overrides,
});

describe("A2UIConfirmDialog", () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("renders dialog with title and message", () => {
    const onApprove = vi.fn();
    render(<A2UIConfirmDialog confirm={makeConfirm()} onApprove={onApprove} />);
    expect(screen.getByText("Confirm Action")).toBeInTheDocument();
    expect(screen.getByText("Are you sure you want to proceed?")).toBeInTheDocument();
  });

  it("renders severity label text", () => {
    const onApprove = vi.fn();
    render(
      <A2UIConfirmDialog confirm={makeConfirm({ severity: "warning" })} onApprove={onApprove} />
    );
    expect(screen.getByText("Severity: warning")).toBeInTheDocument();
  });

  it("shows info severity styles with blue color", () => {
    const onApprove = vi.fn();
    const { container } = render(
      <A2UIConfirmDialog confirm={makeConfirm({ severity: "info" })} onApprove={onApprove} />
    );
    const titleEl = screen.getByText("Confirm Action");
    expect(titleEl).toHaveStyle({ color: "#60a5fa" });
    // Approve button should have blue background
    const approveBtn = screen.getByText("Approve");
    expect(approveBtn).toHaveStyle({ backgroundColor: "#60a5fa" });
  });

  it("shows warning severity styles with yellow color", () => {
    const onApprove = vi.fn();
    render(
      <A2UIConfirmDialog
        confirm={makeConfirm({ severity: "warning" })}
        onApprove={onApprove}
      />
    );
    const titleEl = screen.getByText("Confirm Action");
    expect(titleEl).toHaveStyle({ color: "#fbbf24" });
    const approveBtn = screen.getByText("Approve");
    expect(approveBtn).toHaveStyle({ backgroundColor: "#fbbf24" });
  });

  it("shows critical severity styles with red color", () => {
    const onApprove = vi.fn();
    render(
      <A2UIConfirmDialog
        confirm={makeConfirm({ severity: "critical" })}
        onApprove={onApprove}
      />
    );
    const titleEl = screen.getByText("Confirm Action");
    expect(titleEl).toHaveStyle({ color: "#f87171" });
    const approveBtn = screen.getByText("Approve");
    expect(approveBtn).toHaveStyle({ backgroundColor: "#f87171" });
  });

  it("countdown timer displays initial value and decrements", () => {
    const onApprove = vi.fn();
    render(
      <A2UIConfirmDialog confirm={makeConfirm({ timeout_seconds: 10 })} onApprove={onApprove} />
    );
    expect(screen.getByText("10s")).toBeInTheDocument();

    act(() => {
      vi.advanceTimersByTime(1000);
    });
    expect(screen.getByText("9s")).toBeInTheDocument();

    act(() => {
      vi.advanceTimersByTime(1000);
    });
    expect(screen.getByText("8s")).toBeInTheDocument();
  });

  it("approve button calls onApprove with request_id and true", () => {
    const onApprove = vi.fn();
    render(
      <A2UIConfirmDialog confirm={makeConfirm({ request_id: "req-approve" })} onApprove={onApprove} />
    );
    fireEvent.click(screen.getByText("Approve"));
    expect(onApprove).toHaveBeenCalledWith("req-approve", true);
  });

  it("reject button calls onApprove with request_id and false", () => {
    const onApprove = vi.fn();
    render(
      <A2UIConfirmDialog confirm={makeConfirm({ request_id: "req-reject" })} onApprove={onApprove} />
    );
    fireEvent.click(screen.getByText("Reject"));
    expect(onApprove).toHaveBeenCalledWith("req-reject", false);
  });

  it("auto-timeout triggers reject after countdown reaches zero", () => {
    const onApprove = vi.fn();
    render(
      <A2UIConfirmDialog confirm={makeConfirm({ timeout_seconds: 3 })} onApprove={onApprove} />
    );
    expect(onApprove).not.toHaveBeenCalled();

    // Advance through 3 seconds to reach 0
    act(() => {
      vi.advanceTimersByTime(1000);
    });
    act(() => {
      vi.advanceTimersByTime(1000);
    });
    act(() => {
      vi.advanceTimersByTime(1000);
    });

    expect(onApprove).toHaveBeenCalledWith("req-001", false, "timeout");
  });

  it("defaults timeout to 30 seconds when timeout_seconds is undefined", () => {
    const onApprove = vi.fn();
    render(
      <A2UIConfirmDialog
        confirm={makeConfirm({ timeout_seconds: undefined })}
        onApprove={onApprove}
      />
    );
    expect(screen.getByText("30s")).toBeInTheDocument();

    // Advance 5 seconds, should still be counting
    for (let i = 0; i < 5; i++) {
      act(() => {
        vi.advanceTimersByTime(1000);
      });
    }
    expect(screen.getByText("25s")).toBeInTheDocument();
    expect(onApprove).not.toHaveBeenCalled();
  });

  it("renders approve and reject buttons", () => {
    const onApprove = vi.fn();
    render(<A2UIConfirmDialog confirm={makeConfirm()} onApprove={onApprove} />);
    expect(screen.getByText("Approve")).toBeInTheDocument();
    expect(screen.getByText("Reject")).toBeInTheDocument();
  });

  it("renders countdown progress bar with correct width", () => {
    const onApprove = vi.fn();
    const { container } = render(
      <A2UIConfirmDialog confirm={makeConfirm({ timeout_seconds: 10 })} onApprove={onApprove} />
    );
    // Progress bar starts at 100%
    const progressBar = container.querySelector(".h-full.rounded-full.transition-all");
    expect(progressBar).toHaveStyle({ width: "100%" });

    // After 5 seconds it should be at 50%
    for (let i = 0; i < 5; i++) {
      act(() => {
        vi.advanceTimersByTime(1000);
      });
    }
    expect(progressBar).toHaveStyle({ width: "50%" });
  });

  it("renders auto-reject label text", () => {
    const onApprove = vi.fn();
    render(<A2UIConfirmDialog confirm={makeConfirm()} onApprove={onApprove} />);
    expect(screen.getByText("Auto-reject in")).toBeInTheDocument();
  });

  it("renders backdrop overlay with fixed positioning", () => {
    const onApprove = vi.fn();
    const { container } = render(
      <A2UIConfirmDialog confirm={makeConfirm()} onApprove={onApprove} />
    );
    const overlay = container.firstChild as HTMLElement;
    expect(overlay.className).toContain("fixed");
    expect(overlay.className).toContain("inset-0");
    expect(overlay.className).toContain("z-50");
  });

  it("falls back to info severity config for unknown severity", () => {
    const onApprove = vi.fn();
    // Force an unknown severity value to test the fallback
    const confirm = makeConfirm({ severity: "unknown" as any });
    render(<A2UIConfirmDialog confirm={confirm} onApprove={onApprove} />);
    // Should fall back to info color (#60a5fa)
    const titleEl = screen.getByText("Confirm Action");
    expect(titleEl).toHaveStyle({ color: "#60a5fa" });
  });
});
