import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, fireEvent, act } from "@testing-library/react";
import SearchInput from "../SearchInput";

describe("SearchInput", () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("renders the input field with a search icon", () => {
    const { container } = render(
      <SearchInput value="" onChange={vi.fn()} />,
    );
    const input = screen.getByPlaceholderText("Search...");
    expect(input).toBeInTheDocument();
    // Search icon rendered as an SVG
    const svg = container.querySelector("svg");
    expect(svg).toBeInTheDocument();
  });

  it("shows custom placeholder text", () => {
    render(
      <SearchInput
        value=""
        onChange={vi.fn()}
        placeholder="Find agents..."
      />,
    );
    expect(screen.getByPlaceholderText("Find agents...")).toBeInTheDocument();
  });

  it("displays the controlled value", () => {
    render(<SearchInput value="hello" onChange={vi.fn()} />);
    const input = screen.getByPlaceholderText("Search...") as HTMLInputElement;
    expect(input.value).toBe("hello");
  });

  it("debounces onChange by 300ms", () => {
    const onChange = vi.fn();
    render(<SearchInput value="" onChange={onChange} />);
    const input = screen.getByPlaceholderText("Search...");

    fireEvent.change(input, { target: { value: "test" } });

    // Should NOT have called onChange yet
    expect(onChange).not.toHaveBeenCalled();

    // Advance time by 299ms — still should not fire
    act(() => {
      vi.advanceTimersByTime(299);
    });
    expect(onChange).not.toHaveBeenCalled();

    // Advance past the 300ms threshold
    act(() => {
      vi.advanceTimersByTime(1);
    });
    expect(onChange).toHaveBeenCalledTimes(1);
    expect(onChange).toHaveBeenCalledWith("test");
  });

  it("resets debounce timer on rapid successive inputs", () => {
    const onChange = vi.fn();
    render(<SearchInput value="" onChange={onChange} />);
    const input = screen.getByPlaceholderText("Search...");

    fireEvent.change(input, { target: { value: "a" } });
    act(() => {
      vi.advanceTimersByTime(200);
    });

    fireEvent.change(input, { target: { value: "ab" } });
    act(() => {
      vi.advanceTimersByTime(200);
    });

    fireEvent.change(input, { target: { value: "abc" } });
    act(() => {
      vi.advanceTimersByTime(300);
    });

    // Only the final value should have been emitted
    expect(onChange).toHaveBeenCalledTimes(1);
    expect(onChange).toHaveBeenCalledWith("abc");
  });

  it("does not call onChange when local value matches the controlled value", () => {
    const onChange = vi.fn();
    render(<SearchInput value="same" onChange={onChange} />);
    const input = screen.getByPlaceholderText("Search...");

    // Type the same value that was passed as prop
    fireEvent.change(input, { target: { value: "same" } });

    act(() => {
      vi.advanceTimersByTime(300);
    });

    // The effect guards with `if (local !== value)`, so onChange should NOT fire
    expect(onChange).not.toHaveBeenCalled();
  });

  it("syncs local state when the value prop changes externally", () => {
    const onChange = vi.fn();
    const { rerender } = render(
      <SearchInput value="initial" onChange={onChange} />,
    );
    const input = screen.getByPlaceholderText("Search...") as HTMLInputElement;
    expect(input.value).toBe("initial");

    // Parent clears the value (e.g., user presses a clear button)
    rerender(<SearchInput value="" onChange={onChange} />);

    // Input should reflect the new prop
    expect(input.value).toBe("");
  });
});
