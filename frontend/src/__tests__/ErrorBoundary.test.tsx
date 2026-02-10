import { render, screen } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { ErrorBoundary } from "../components/shared/ErrorBoundary";

// Helper component that throws an error when shouldThrow is true
interface ThrowErrorProps {
  shouldThrow: boolean;
  errorMessage?: string;
}

function ThrowError({ shouldThrow, errorMessage = "Test error" }: ThrowErrorProps) {
  if (shouldThrow) {
    throw new Error(errorMessage);
  }
  return <div>Normal content</div>;
}

describe("ErrorBoundary", () => {
  let consoleErrorSpy: ReturnType<typeof vi.spyOn>;

  beforeEach(() => {
    // Suppress console.error in tests that expect errors
    consoleErrorSpy = vi.spyOn(console, "error").mockImplementation(() => {});
  });

  afterEach(() => {
    consoleErrorSpy.mockRestore();
  });

  it("renders children normally when no error occurs", () => {
    render(
      <ErrorBoundary>
        <div>Normal content</div>
      </ErrorBoundary>
    );

    expect(screen.getByText("Normal content")).toBeInTheDocument();
  });

  it("catches errors and shows default fallback UI with 'Something went wrong'", () => {
    render(
      <ErrorBoundary>
        <ThrowError shouldThrow={true} />
      </ErrorBoundary>
    );

    expect(screen.getByText("Something went wrong")).toBeInTheDocument();
  });

  it("shows error message in the fallback", () => {
    const errorMessage = "Custom test error message";

    render(
      <ErrorBoundary>
        <ThrowError shouldThrow={true} errorMessage={errorMessage} />
      </ErrorBoundary>
    );

    expect(screen.getByText(errorMessage)).toBeInTheDocument();
  });

  it("Reload Page button is present in error fallback", () => {
    render(
      <ErrorBoundary>
        <ThrowError shouldThrow={true} />
      </ErrorBoundary>
    );

    expect(screen.getByText("Something went wrong")).toBeInTheDocument();
    const reloadButton = screen.getByRole("button", { name: /reload page/i });
    expect(reloadButton).toBeInTheDocument();
  });

  it("custom fallback prop works (renders custom fallback instead of default)", () => {
    const customFallback = <div>Custom error message</div>;

    render(
      <ErrorBoundary fallback={customFallback}>
        <ThrowError shouldThrow={true} />
      </ErrorBoundary>
    );

    expect(screen.getByText("Custom error message")).toBeInTheDocument();
    expect(screen.queryByText("Something went wrong")).not.toBeInTheDocument();
  });

  it("componentDidCatch logs to console.error", () => {
    const errorMessage = "Logged error message";

    render(
      <ErrorBoundary>
        <ThrowError shouldThrow={true} errorMessage={errorMessage} />
      </ErrorBoundary>
    );

    // React also calls console.error, so find our specific call
    const boundaryCall = consoleErrorSpy.mock.calls.find(
      (call) => call[0] === "ErrorBoundary caught:"
    );
    expect(boundaryCall).toBeDefined();
    expect(boundaryCall![1]).toBeInstanceOf(Error);
    expect(boundaryCall![1].message).toBe(errorMessage);
  });

  it("default fallback has correct styling classes", () => {
    render(
      <ErrorBoundary>
        <ThrowError shouldThrow={true} />
      </ErrorBoundary>
    );

    const heading = screen.getByText("Something went wrong");
    expect(heading).toHaveClass("text-xl", "font-semibold", "text-red-600", "mb-2");

    const button = screen.getByRole("button", { name: /reload page/i });
    expect(button).toHaveClass("px-4", "py-2", "text-white", "rounded-lg");
  });

  it("maintains error boundary state across re-renders", () => {
    const { rerender } = render(
      <ErrorBoundary>
        <ThrowError shouldThrow={true} />
      </ErrorBoundary>
    );

    expect(screen.getByText("Something went wrong")).toBeInTheDocument();

    // Rerender with same props
    rerender(
      <ErrorBoundary>
        <ThrowError shouldThrow={true} />
      </ErrorBoundary>
    );

    // Should still show error state
    expect(screen.getByText("Something went wrong")).toBeInTheDocument();
  });
});
