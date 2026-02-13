import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, waitFor, act } from "@testing-library/react";
import { ToastProvider, useToast } from "../Toast";

// Helper component to trigger toast from within provider
function ToastTrigger({
  message,
  variant,
}: {
  message: string;
  variant?: "success" | "error" | "info";
}) {
  const { toast } = useToast();
  return (
    <button onClick={() => toast(message, variant)}>Trigger Toast</button>
  );
}

describe("Toast Component", () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.restoreAllMocks();
    vi.useRealTimers();
  });

  it("renders toast message when triggered", () => {
    render(
      <ToastProvider>
        <ToastTrigger message="Test message" />
      </ToastProvider>
    );

    const button = screen.getByText("Trigger Toast");
    act(() => {
      button.click();
    });

    expect(screen.getByText("Test message")).toBeInTheDocument();
  });

  it("shows toast with default info variant", () => {
    render(
      <ToastProvider>
        <ToastTrigger message="Info message" />
      </ToastProvider>
    );

    const button = screen.getByText("Trigger Toast");
    act(() => {
      button.click();
    });

    const toast = screen.getByText("Info message").closest("div");
    expect(toast?.getAttribute("style")).toContain("border-left: 4px solid rgb(96, 165, 250)");
  });

  it("shows success toast with green styling", () => {
    render(
      <ToastProvider>
        <ToastTrigger message="Success message" variant="success" />
      </ToastProvider>
    );

    const button = screen.getByText("Trigger Toast");
    act(() => {
      button.click();
    });

    const toast = screen.getByText("Success message").closest("div");
    expect(toast?.getAttribute("style")).toContain("border-left: 4px solid rgb(52, 211, 153)");
  });

  it("shows error toast with red styling", () => {
    render(
      <ToastProvider>
        <ToastTrigger message="Error message" variant="error" />
      </ToastProvider>
    );

    const button = screen.getByText("Trigger Toast");
    act(() => {
      button.click();
    });

    const toast = screen.getByText("Error message").closest("div");
    expect(toast?.getAttribute("style")).toContain("border-left: 4px solid rgb(248, 113, 113)");
  });

  it("auto-dismisses toast after 4 seconds", async () => {
    render(
      <ToastProvider>
        <ToastTrigger message="Auto dismiss" />
      </ToastProvider>
    );

    const button = screen.getByText("Trigger Toast");
    act(() => {
      button.click();
    });

    expect(screen.getByText("Auto dismiss")).toBeInTheDocument();

    // Fast-forward time by 4 seconds and flush microtasks
    await act(async () => {
      vi.advanceTimersByTime(4000);
    });

    expect(screen.queryByText("Auto dismiss")).not.toBeInTheDocument();
  });

  it("allows multiple toasts to stack", () => {
    function MultiToastTrigger() {
      const { toast } = useToast();
      return (
        <>
          <button onClick={() => toast("First toast", "success")}>
            First
          </button>
          <button onClick={() => toast("Second toast", "error")}>
            Second
          </button>
          <button onClick={() => toast("Third toast", "info")}>Third</button>
        </>
      );
    }

    render(
      <ToastProvider>
        <MultiToastTrigger />
      </ToastProvider>
    );

    act(() => {
      screen.getByText("First").click();
      screen.getByText("Second").click();
      screen.getByText("Third").click();
    });

    expect(screen.getByText("First toast")).toBeInTheDocument();
    expect(screen.getByText("Second toast")).toBeInTheDocument();
    expect(screen.getByText("Third toast")).toBeInTheDocument();
  });

  it("dismisses toast when close button is clicked", () => {
    render(
      <ToastProvider>
        <ToastTrigger message="Dismissible toast" />
      </ToastProvider>
    );

    const button = screen.getByText("Trigger Toast");
    act(() => {
      button.click();
    });

    expect(screen.getByText("Dismissible toast")).toBeInTheDocument();

    // Find and click the close button (X icon button)
    const closeButton = screen
      .getByText("Dismissible toast")
      .closest("div")!
      .querySelector("button");

    act(() => {
      closeButton!.click();
    });

    expect(screen.queryByText("Dismissible toast")).not.toBeInTheDocument();
  });

  it("useToast hook returns toast function", () => {
    function TestComponent() {
      const { toast } = useToast();
      expect(typeof toast).toBe("function");
      return <div>Test</div>;
    }

    render(
      <ToastProvider>
        <TestComponent />
      </ToastProvider>
    );
  });

  it("does not show toast initially", () => {
    render(
      <ToastProvider>
        <div>No toast</div>
      </ToastProvider>
    );

    expect(screen.queryByText(/toast/i)).toBeInTheDocument(); // Only "No toast" text
    expect(screen.queryByRole("button")).not.toBeInTheDocument(); // No close buttons
  });

  it("toasts auto-dismiss independently", async () => {
    function StaggeredToasts() {
      const { toast } = useToast();
      return (
        <>
          <button onClick={() => toast("First", "info")}>Add First</button>
          <button onClick={() => toast("Second", "info")}>Add Second</button>
        </>
      );
    }

    render(
      <ToastProvider>
        <StaggeredToasts />
      </ToastProvider>
    );

    // Add first toast
    act(() => {
      screen.getByText("Add First").click();
    });

    expect(screen.getByText("First")).toBeInTheDocument();

    // Wait 2 seconds, then add second toast
    await act(async () => {
      vi.advanceTimersByTime(2000);
    });

    act(() => {
      screen.getByText("Add Second").click();
    });

    expect(screen.getByText("First")).toBeInTheDocument();
    expect(screen.getByText("Second")).toBeInTheDocument();

    // Advance 2 more seconds (4 total for first toast)
    await act(async () => {
      vi.advanceTimersByTime(2000);
    });

    expect(screen.queryByText("First")).not.toBeInTheDocument();

    // Second toast should still be visible
    expect(screen.getByText("Second")).toBeInTheDocument();

    // Advance 2 more seconds (4 total for second toast)
    await act(async () => {
      vi.advanceTimersByTime(2000);
    });

    expect(screen.queryByText("Second")).not.toBeInTheDocument();
  });
});
