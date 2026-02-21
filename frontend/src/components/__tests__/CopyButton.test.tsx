import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, act, fireEvent, waitFor } from "@testing-library/react";
import CopyButton from "../CopyButton";

const writeTextMock = vi.fn().mockResolvedValue(undefined);

// Override clipboard at the global level before any tests run
Object.defineProperty(window.navigator, "clipboard", {
  value: { writeText: writeTextMock },
  writable: true,
  configurable: true,
});

describe("CopyButton", () => {
  beforeEach(() => {
    vi.useRealTimers();
    vi.clearAllMocks();
    writeTextMock.mockResolvedValue(undefined);
  });

  it("renders the copy button", () => {
    render(<CopyButton value="hello" />);
    expect(screen.getByTitle("Copy to clipboard")).toBeInTheDocument();
  });

  it("copies text to clipboard on click", async () => {
    render(<CopyButton value="test-value" />);
    fireEvent.click(screen.getByTitle("Copy to clipboard"));
    await waitFor(() => {
      expect(writeTextMock).toHaveBeenCalledWith("test-value");
    });
  });

  it("shows success state after copy", async () => {
    const { container } = render(<CopyButton value="hello" />);
    fireEvent.click(screen.getByTitle("Copy to clipboard"));
    await waitFor(() => {
      const checkIcon = container.querySelector(".text-\\[\\#34d399\\]");
      expect(checkIcon).toBeInTheDocument();
    });
  });

  it("resets to initial state after timeout", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    const { container } = render(<CopyButton value="hello" />);

    await act(async () => {
      fireEvent.click(screen.getByTitle("Copy to clipboard"));
      await Promise.resolve(); // flush microtask for writeText promise
    });

    expect(container.querySelector(".text-\\[\\#34d399\\]")).toBeInTheDocument();

    await act(async () => {
      vi.advanceTimersByTime(2100);
    });

    expect(container.querySelector(".text-\\[\\#34d399\\]")).not.toBeInTheDocument();
    vi.useRealTimers();
  });

  it("handles clipboard API failure gracefully", async () => {
    writeTextMock.mockRejectedValueOnce(new Error("Clipboard failed"));
    // Suppress the unhandled rejection from the component's async handler
    const handler = (e: PromiseRejectionEvent) => e.preventDefault();
    window.addEventListener("unhandledrejection", handler);
    render(<CopyButton value="fail-text" />);
    fireEvent.click(screen.getByTitle("Copy to clipboard"));
    await waitFor(() => {
      expect(writeTextMock).toHaveBeenCalledWith("fail-text");
    });
    expect(screen.getByTitle("Copy to clipboard")).toBeInTheDocument();
    window.removeEventListener("unhandledrejection", handler);
  });

  it("accepts custom text to copy via value prop", async () => {
    render(<CopyButton value="custom-clipboard-text" />);
    fireEvent.click(screen.getByTitle("Copy to clipboard"));
    await waitFor(() => {
      expect(writeTextMock).toHaveBeenCalledWith("custom-clipboard-text");
    });
  });
});
