import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import A2UIInputDialog from "../A2UIInputDialog";
import type { A2UIRequestInputMessage } from "../../../types/a2ui";

const makeRequest = (
  overrides?: Partial<A2UIRequestInputMessage>,
): A2UIRequestInputMessage => ({
  request_id: "req-1",
  input_type: "text",
  prompt: "Enter your name",
  ...overrides,
});

describe("A2UIInputDialog", () => {
  it("renders dialog with title and prompt message", () => {
    render(
      <A2UIInputDialog request={makeRequest()} onRespond={vi.fn()} />,
    );
    expect(screen.getByText("Input Requested")).toBeInTheDocument();
    expect(screen.getByText("Enter your name")).toBeInTheDocument();
  });

  it("renders text input type", () => {
    render(
      <A2UIInputDialog
        request={makeRequest({ input_type: "text" })}
        onRespond={vi.fn()}
      />,
    );
    const input = screen.getByPlaceholderText("Enter text...");
    expect(input).toBeInTheDocument();
    expect(input).toHaveAttribute("type", "text");
  });

  it("renders number input type", () => {
    render(
      <A2UIInputDialog
        request={makeRequest({ input_type: "number" })}
        onRespond={vi.fn()}
      />,
    );
    const input = screen.getByPlaceholderText("Enter number...");
    expect(input).toBeInTheDocument();
    expect(input).toHaveAttribute("type", "number");
  });

  it("renders date input type", () => {
    const { container } = render(
      <A2UIInputDialog
        request={makeRequest({ input_type: "date" })}
        onRespond={vi.fn()}
      />,
    );
    const input = container.querySelector('input[type="date"]');
    expect(input).toBeInTheDocument();
  });

  it("renders select input type with options", () => {
    render(
      <A2UIInputDialog
        request={makeRequest({
          input_type: "select",
          options: ["Red", "Green", "Blue"],
        })}
        onRespond={vi.fn()}
      />,
    );
    expect(screen.getByText("Select an option...")).toBeInTheDocument();
    expect(screen.getByText("Red")).toBeInTheDocument();
    expect(screen.getByText("Green")).toBeInTheDocument();
    expect(screen.getByText("Blue")).toBeInTheDocument();
  });

  it("renders file input type", () => {
    const { container } = render(
      <A2UIInputDialog
        request={makeRequest({ input_type: "file" })}
        onRespond={vi.fn()}
      />,
    );
    const input = container.querySelector('input[type="file"]');
    expect(input).toBeInTheDocument();
  });

  it("validates required input before submit", () => {
    render(
      <A2UIInputDialog request={makeRequest()} onRespond={vi.fn()} />,
    );
    fireEvent.click(screen.getByText("Submit"));
    expect(screen.getByText("This field is required.")).toBeInTheDocument();
  });

  it("cancel button calls onRespond with null", () => {
    const onRespond = vi.fn();
    render(
      <A2UIInputDialog request={makeRequest()} onRespond={onRespond} />,
    );
    fireEvent.click(screen.getByText("Cancel"));
    expect(onRespond).toHaveBeenCalledWith("req-1", null);
  });

  it("submit button calls onRespond with input value", () => {
    const onRespond = vi.fn();
    render(
      <A2UIInputDialog request={makeRequest()} onRespond={onRespond} />,
    );
    const input = screen.getByPlaceholderText("Enter text...");
    fireEvent.change(input, { target: { value: "Alice" } });
    fireEvent.click(screen.getByText("Submit"));
    expect(onRespond).toHaveBeenCalledWith("req-1", "Alice");
  });

  it("handles default value by allowing typed input to be submitted", () => {
    const onRespond = vi.fn();
    render(
      <A2UIInputDialog
        request={makeRequest({ input_type: "number" })}
        onRespond={onRespond}
      />,
    );
    const input = screen.getByPlaceholderText("Enter number...");
    fireEvent.change(input, { target: { value: "42" } });
    fireEvent.click(screen.getByText("Submit"));
    expect(onRespond).toHaveBeenCalledWith("req-1", "42");
  });

  it("shows min validation error for number input", () => {
    render(
      <A2UIInputDialog
        request={makeRequest({
          input_type: "number",
          validation: { min: 10 },
        })}
        onRespond={vi.fn()}
      />,
    );
    const input = screen.getByPlaceholderText("Enter number...");
    fireEvent.change(input, { target: { value: "5" } });
    // Use fireEvent.submit to bypass HTML5 native min constraint validation
    const form = input.closest("form")!;
    fireEvent.submit(form);
    expect(screen.getByText("Minimum value is 10.")).toBeInTheDocument();
  });

  it("shows max validation error for number input", () => {
    render(
      <A2UIInputDialog
        request={makeRequest({
          input_type: "number",
          validation: { max: 100 },
        })}
        onRespond={vi.fn()}
      />,
    );
    const input = screen.getByPlaceholderText("Enter number...");
    fireEvent.change(input, { target: { value: "200" } });
    const form = input.closest("form")!;
    fireEvent.submit(form);
    expect(screen.getByText("Maximum value is 100.")).toBeInTheDocument();
  });

  it("shows pattern validation error for text input", () => {
    render(
      <A2UIInputDialog
        request={makeRequest({
          input_type: "text",
          validation: { pattern: "^[A-Z]+$", pattern_message: "Uppercase only." },
        })}
        onRespond={vi.fn()}
      />,
    );
    const input = screen.getByPlaceholderText("Enter text...");
    fireEvent.change(input, { target: { value: "abc" } });
    fireEvent.click(screen.getByText("Submit"));
    expect(screen.getByText("Uppercase only.")).toBeInTheDocument();
  });

  it("shows default pattern error when pattern_message is not provided", () => {
    render(
      <A2UIInputDialog
        request={makeRequest({
          input_type: "text",
          validation: { pattern: "^\\d+$" },
        })}
        onRespond={vi.fn()}
      />,
    );
    const input = screen.getByPlaceholderText("Enter text...");
    fireEvent.change(input, { target: { value: "abc" } });
    fireEvent.click(screen.getByText("Submit"));
    expect(screen.getByText("Invalid format.")).toBeInTheDocument();
  });

  it("dialog is always rendered (component has no open/close toggle)", () => {
    const { container } = render(
      <A2UIInputDialog request={makeRequest()} onRespond={vi.fn()} />,
    );
    // The dialog overlay is always present when the component mounts
    const overlay = container.querySelector(".fixed.inset-0");
    expect(overlay).toBeInTheDocument();
    expect(screen.getByText("Input Requested")).toBeInTheDocument();
    expect(screen.getByText("Submit")).toBeInTheDocument();
    expect(screen.getByText("Cancel")).toBeInTheDocument();
  });

  it("clears previous error on successful submit", () => {
    const onRespond = vi.fn();
    render(
      <A2UIInputDialog request={makeRequest()} onRespond={onRespond} />,
    );
    // First submit empty to trigger error
    fireEvent.click(screen.getByText("Submit"));
    expect(screen.getByText("This field is required.")).toBeInTheDocument();

    // Type a value and submit again
    const input = screen.getByPlaceholderText("Enter text...");
    fireEvent.change(input, { target: { value: "hello" } });
    fireEvent.click(screen.getByText("Submit"));

    expect(screen.queryByText("This field is required.")).not.toBeInTheDocument();
    expect(onRespond).toHaveBeenCalledWith("req-1", "hello");
  });

  it("renders select with correct value after change", () => {
    const onRespond = vi.fn();
    render(
      <A2UIInputDialog
        request={makeRequest({
          input_type: "select",
          options: ["Apple", "Banana", "Cherry"],
        })}
        onRespond={onRespond}
      />,
    );
    const select = screen.getByRole("combobox");
    fireEvent.change(select, { target: { value: "Banana" } });
    fireEvent.click(screen.getByText("Submit"));
    expect(onRespond).toHaveBeenCalledWith("req-1", "Banana");
  });
});
