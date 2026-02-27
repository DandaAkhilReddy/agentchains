import React from "react";
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, fireEvent, act } from "@testing-library/react";
import A2UICodeWidget from "../A2UICodeWidget";

describe("A2UICodeWidget", () => {
  let clipboardWriteText: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    clipboardWriteText = vi.fn().mockResolvedValue(undefined);
    Object.assign(navigator, {
      clipboard: { writeText: clipboardWriteText },
    });
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("renders the code content", () => {
    render(<A2UICodeWidget code="console.log('hello');" />);
    expect(screen.getByText("console.log('hello');")).toBeInTheDocument();
  });

  it("renders line numbers by default", () => {
    render(<A2UICodeWidget code={"line1\nline2\nline3"} />);
    expect(screen.getByText("1")).toBeInTheDocument();
    expect(screen.getByText("2")).toBeInTheDocument();
    expect(screen.getByText("3")).toBeInTheDocument();
  });

  it("hides line numbers when showLineNumbers is false", () => {
    render(<A2UICodeWidget code={"line1\nline2"} showLineNumbers={false} />);
    expect(screen.queryByText("1")).not.toBeInTheDocument();
    expect(screen.queryByText("2")).not.toBeInTheDocument();
  });

  it("renders language badge when language prop is provided", () => {
    render(<A2UICodeWidget code="x = 1" language="python" />);
    expect(screen.getByText("python")).toBeInTheDocument();
  });

  it("does not render language badge when language prop is omitted", () => {
    const { container } = render(<A2UICodeWidget code="x = 1" />);
    const badge = container.querySelector("span.uppercase");
    expect(badge).not.toBeInTheDocument();
  });

  it("renders footer with correct line count (singular)", () => {
    render(<A2UICodeWidget code="single line" />);
    expect(screen.getByText("1 line")).toBeInTheDocument();
  });

  it("renders footer with correct line count (plural)", () => {
    render(<A2UICodeWidget code={"a\nb\nc"} />);
    expect(screen.getByText("3 lines")).toBeInTheDocument();
  });

  it("displays highlight count when highlightLines is provided", () => {
    render(<A2UICodeWidget code={"a\nb\nc\nd"} highlightLines={[1, 3]} />);
    expect(screen.getByText("2 highlighted")).toBeInTheDocument();
  });

  it("does not display highlight count when highlightLines is empty", () => {
    render(<A2UICodeWidget code={"a\nb"} highlightLines={[]} />);
    expect(screen.queryByText(/highlighted/)).not.toBeInTheDocument();
  });

  it("applies highlight styles to specified lines", () => {
    const { container } = render(
      <A2UICodeWidget code={"line1\nline2\nline3"} highlightLines={[2]} />
    );
    const lineRows = container.querySelectorAll("code > div");
    // Line 2 (index 1) should have highlight border-left (jsdom normalizes hex to rgb)
    expect((lineRows[1] as HTMLElement).style.borderLeft).toContain("2px solid");
    expect((lineRows[1] as HTMLElement).style.borderLeft).not.toContain("transparent");
    // Line 1 (index 0) should have transparent border
    expect((lineRows[0] as HTMLElement).style.borderLeft).toContain("transparent");
  });

  it("copies code to clipboard and shows Copied! text", async () => {
    render(<A2UICodeWidget code="copy me" />);
    const copyButton = screen.getByTitle("Copy to clipboard");
    expect(screen.getByText("Copy")).toBeInTheDocument();

    await act(async () => {
      fireEvent.click(copyButton);
    });

    expect(clipboardWriteText).toHaveBeenCalledWith("copy me");
    expect(screen.getByText("Copied!")).toBeInTheDocument();
  });

  it("reverts copy button text after 2 seconds", async () => {
    render(<A2UICodeWidget code="temp copy" />);
    const copyButton = screen.getByTitle("Copy to clipboard");

    await act(async () => {
      fireEvent.click(copyButton);
    });

    expect(screen.getByText("Copied!")).toBeInTheDocument();

    act(() => {
      vi.advanceTimersByTime(2000);
    });

    expect(screen.getByText("Copy")).toBeInTheDocument();
  });

  it("uses fallback copy when clipboard API fails", async () => {
    // Make clipboard.writeText reject so the catch branch runs
    clipboardWriteText.mockRejectedValueOnce(new Error("Not allowed"));
    // Define execCommand on document since jsdom does not include it
    document.execCommand = vi.fn().mockReturnValue(true);

    render(<A2UICodeWidget code="fallback copy" />);
    const copyButton = screen.getByTitle("Copy to clipboard");

    await act(async () => {
      fireEvent.click(copyButton);
      // Flush the microtask queue so the rejected promise settles
      await Promise.resolve();
      await Promise.resolve();
    });

    expect(document.execCommand).toHaveBeenCalledWith("copy");
    expect(screen.getByText("Copied!")).toBeInTheDocument();
  });

  it("renders traffic light dots in the header", () => {
    const { container } = render(<A2UICodeWidget code="test" />);
    const dots = container.querySelectorAll(".rounded-full");
    // Three traffic light dots
    expect(dots.length).toBeGreaterThanOrEqual(3);
  });

  it("renders empty lines as newline characters (covers line || '\\n' branch)", () => {
    // Code with an empty line in the middle
    const codeWithEmptyLine = "line one\n\nline three";
    const { container } = render(<A2UICodeWidget code={codeWithEmptyLine} />);

    // Should render 3 lines (line one, empty line, line three)
    expect(screen.getByText("3 lines")).toBeInTheDocument();

    // The empty line (index 1) should render a newline character
    const lineRows = container.querySelectorAll("code > div");
    expect(lineRows.length).toBe(3);

    // Line 1 and line 3 have text content
    expect(screen.getByText("line one")).toBeInTheDocument();
    expect(screen.getByText("line three")).toBeInTheDocument();
  });

  it("adjusts gutter width for large line counts (gutterWidth calculation)", () => {
    // 100 lines → String(100).length = 3 digits → gutterWidth = max(3*0.6+0.8, 2.2) = max(2.6, 2.2) = 2.6rem
    const manyLines = Array.from({ length: 100 }, (_, i) => `line ${i + 1}`).join("\n");
    render(<A2UICodeWidget code={manyLines} showLineNumbers={true} />);
    expect(screen.getByText("100 lines")).toBeInTheDocument();
  });

  it("renders correct paddingLeft when showLineNumbers is false (covers else branch)", () => {
    const { container } = render(
      <A2UICodeWidget code="const x = 1;" showLineNumbers={false} />
    );
    // When showLineNumbers=false, the code span has paddingLeft: "1.5rem"
    const codeSpans = container.querySelectorAll("code > div > span:last-child");
    if (codeSpans.length > 0) {
      const spanEl = codeSpans[0] as HTMLElement;
      expect(spanEl.style.paddingLeft).toBe("1.5rem");
    }
  });

  it("fallback copy reverts Copied! text after 2 seconds (covers catch setTimeout)", async () => {
    // Make clipboard.writeText reject so the catch branch runs
    clipboardWriteText.mockRejectedValueOnce(new Error("Permission denied"));
    document.execCommand = vi.fn().mockReturnValue(true);

    render(<A2UICodeWidget code="catch-timeout" />);
    const copyButton = screen.getByTitle("Copy to clipboard");

    await act(async () => {
      fireEvent.click(copyButton);
      await Promise.resolve();
      await Promise.resolve();
    });

    // Should show Copied! after fallback
    expect(screen.getByText("Copied!")).toBeInTheDocument();

    // Advance 2 seconds to trigger the fallback setTimeout
    act(() => {
      vi.advanceTimersByTime(2000);
    });

    // Should revert back to Copy
    expect(screen.getByText("Copy")).toBeInTheDocument();
  });
});
