import { describe, it, expect, vi, afterEach } from "vitest";
import { render, screen, fireEvent, act } from "@testing-library/react";
import CodeBlock from "../CodeBlock";
import type { CodeExample } from "../CodeBlock";

// Mock navigator.clipboard
const writeTextMock = vi.fn().mockResolvedValue(undefined);
Object.defineProperty(navigator, "clipboard", {
  value: { writeText: writeTextMock },
  writable: true,
});

afterEach(() => {
  writeTextMock.mockClear();
  vi.restoreAllMocks();
});

const pythonExample: CodeExample = {
  language: "Python",
  code: 'import requests\nresponse = requests.get("/api")',
};

const jsExample: CodeExample = {
  language: "JavaScript",
  code: 'const res = await fetch("/api");',
};

describe("CodeBlock", () => {
  it("renders nothing when examples array is empty", () => {
    const { container } = render(<CodeBlock examples={[]} />);
    expect(container.innerHTML).toBe("");
  });

  it("renders the code block with a single example", () => {
    render(<CodeBlock examples={[pythonExample]} />);
    expect(screen.getByText("Python")).toBeInTheDocument();
    expect(screen.getByText("Copy")).toBeInTheDocument();
  });

  it("renders title when provided", () => {
    render(<CodeBlock examples={[pythonExample]} title="Example Request" />);
    expect(screen.getByText("Example Request")).toBeInTheDocument();
  });

  it("does not render title element when not provided", () => {
    const { container } = render(<CodeBlock examples={[pythonExample]} />);
    // The title is an 11px span — should not exist
    const titleSpan = container.querySelector(".text-\\[11px\\]");
    expect(titleSpan).toBeNull();
  });

  it("renders language tabs for multiple examples", () => {
    render(<CodeBlock examples={[pythonExample, jsExample]} />);
    expect(screen.getByText("Python")).toBeInTheDocument();
    expect(screen.getByText("JavaScript")).toBeInTheDocument();
  });

  it("switches active language tab on click", () => {
    render(<CodeBlock examples={[pythonExample, jsExample]} />);

    const jsTab = screen.getByText("JavaScript");
    fireEvent.click(jsTab);

    // JS tab should be active, Python tab should not
    expect(jsTab.className).toContain("active");
    const pyTab = screen.getByText("Python");
    expect(pyTab.className).not.toContain("active");
  });

  it("copies code to clipboard and shows Copied feedback", async () => {
    render(<CodeBlock examples={[pythonExample]} />);
    const copyBtn = screen.getByTitle("Copy to clipboard");

    // Click and flush the resolved clipboard promise
    await act(async () => {
      fireEvent.click(copyBtn);
    });

    expect(writeTextMock).toHaveBeenCalledWith(pythonExample.code);
    // "Copied" text should appear after successful copy
    expect(screen.getByText("Copied")).toBeInTheDocument();
  });

  it("reverts Copied text back to Copy after 2 seconds", async () => {
    vi.useFakeTimers();

    render(<CodeBlock examples={[pythonExample]} />);
    const copyBtn = screen.getByTitle("Copy to clipboard");

    // Click and flush the resolved clipboard promise
    await act(async () => {
      fireEvent.click(copyBtn);
    });

    expect(screen.getByText("Copied")).toBeInTheDocument();

    // Advance timers past the 2-second reset
    act(() => {
      vi.advanceTimersByTime(2100);
    });

    expect(screen.getByText("Copy")).toBeInTheDocument();

    vi.useRealTimers();
  });

  it("applies custom className to the root element", () => {
    const { container } = render(
      <CodeBlock examples={[pythonExample]} className="my-custom-class" />,
    );
    const root = container.firstElementChild;
    expect(root?.className).toContain("my-custom-class");
    expect(root?.className).toContain("code-block");
  });

  it("applies syntax highlighting to code content", () => {
    const example: CodeExample = {
      language: "Python",
      code: 'import os\nx = 42\nprint("hello")',
    };
    const { container } = render(<CodeBlock examples={[example]} />);

    const codeEl = container.querySelector("code");
    expect(codeEl).not.toBeNull();

    // The highlight function wraps keywords, numbers, and strings in spans
    expect(codeEl!.innerHTML).toContain("hl-keyword");
    expect(codeEl!.innerHTML).toContain("hl-number");
    expect(codeEl!.innerHTML).toContain("hl-string");
  });
});
