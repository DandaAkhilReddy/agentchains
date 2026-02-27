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

  it("date input onChange updates value and can be submitted", () => {
    const onRespond = vi.fn();
    const { container } = render(
      <A2UIInputDialog
        request={makeRequest({ input_type: "date" })}
        onRespond={onRespond}
      />,
    );
    const input = container.querySelector('input[type="date"]') as HTMLInputElement;
    // Cover line 141: onChange={(e) => setValue(e.target.value)}
    fireEvent.change(input, { target: { value: "2026-01-15" } });
    fireEvent.click(screen.getByText("Submit"));
    expect(onRespond).toHaveBeenCalledWith("req-1", "2026-01-15");
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

  it("file input onChange triggers setValue with selected file (lines 169-170)", () => {
    const { container } = render(
      <A2UIInputDialog
        request={makeRequest({ input_type: "file" })}
        onRespond={vi.fn()}
      />,
    );
    const fileInput = container.querySelector('input[type="file"]') as HTMLInputElement;

    // Simulate a file selection — cover line 170: const file = e.target.files?.[0] ?? null
    const fakeFile = new File(["content"], "test-upload.txt", { type: "text/plain" });
    Object.defineProperty(fileInput, "files", {
      value: [fakeFile],
      configurable: true,
    });
    fireEvent.change(fileInput);

    // After selecting a file, the "Selected:" text should appear (lines 176-180)
    expect(screen.getByText(/Selected:/)).toBeInTheDocument();
    expect(screen.getByText(/test-upload\.txt/)).toBeInTheDocument();
  });

  it("file input onChange when no file selected sets null (files?.[0] ?? null)", () => {
    const { container } = render(
      <A2UIInputDialog
        request={makeRequest({ input_type: "file" })}
        onRespond={vi.fn()}
      />,
    );
    const fileInput = container.querySelector('input[type="file"]') as HTMLInputElement;

    // Simulate change with empty files list — covers the ?? null branch
    Object.defineProperty(fileInput, "files", {
      value: [],
      configurable: true,
    });
    fireEvent.change(fileInput);

    // No "Selected:" text should appear when no file is chosen
    expect(screen.queryByText(/Selected:/)).not.toBeInTheDocument();
  });

  it("file input with accept validation attribute", () => {
    const { container } = render(
      <A2UIInputDialog
        request={makeRequest({
          input_type: "file",
          validation: { accept: ".pdf,.docx" },
        })}
        onRespond={vi.fn()}
      />,
    );
    const fileInput = container.querySelector('input[type="file"]') as HTMLInputElement;
    expect(fileInput).toHaveAttribute("accept", ".pdf,.docx");
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

  it("number input with both min and max validation attributes", () => {
    const { container } = render(
      <A2UIInputDialog
        request={makeRequest({
          input_type: "number",
          validation: { min: 5, max: 50, step: 0.5 },
        })}
        onRespond={vi.fn()}
      />,
    );
    const input = container.querySelector('input[type="number"]') as HTMLInputElement;
    expect(input).toHaveAttribute("min", "5");
    expect(input).toHaveAttribute("max", "50");
    expect(input).toHaveAttribute("step", "0.5");
  });

  it("text input with maxLength validation attribute", () => {
    const { container } = render(
      <A2UIInputDialog
        request={makeRequest({
          input_type: "text",
          validation: { max_length: 100 },
        })}
        onRespond={vi.fn()}
      />,
    );
    const input = container.querySelector('input[type="text"]') as HTMLInputElement;
    expect(input).toHaveAttribute("maxLength", "100");
  });

  it("renders default text input for unknown input_type (default switch branch lines 185-189)", () => {
    // The `default` case renders a text input with placeholder "Enter value..."
    // Cast to bypass TypeScript to pass an unknown input_type.
    const onRespond = vi.fn();
    render(
      <A2UIInputDialog
        request={makeRequest({ input_type: "unknown" as any })}
        onRespond={onRespond}
      />,
    );
    const input = screen.getByPlaceholderText("Enter value...");
    expect(input).toBeInTheDocument();
    expect(input).toHaveAttribute("type", "text");

    // onChange updates the value
    fireEvent.change(input, { target: { value: "test-val" } });

    // Submit calls onRespond with the typed value
    fireEvent.click(screen.getByText("Submit"));
    expect(onRespond).toHaveBeenCalledWith("req-1", "test-val");
  });

  it("default input type empty submit shows required error (branch covers lines 28-31)", () => {
    render(
      <A2UIInputDialog
        request={makeRequest({ input_type: "unknown" as any })}
        onRespond={vi.fn()}
      />,
    );
    // Submit without entering a value — input_type is not "file", value is ""
    fireEvent.click(screen.getByText("Submit"));
    expect(screen.getByText("This field is required.")).toBeInTheDocument();
  });

  it("text input renders correctly with initial empty value (covers line 112: String(value ?? '') with value='')", () => {
    // The text input initial value is "" which renders as String("" ?? "") = "".
    // This exercises the value attribute on the text input (line 112).
    const { container } = render(
      <A2UIInputDialog
        request={makeRequest({ input_type: "text" })}
        onRespond={vi.fn()}
      />,
    );
    const input = container.querySelector('input[type="text"]') as HTMLInputElement;
    expect(input).toBeInTheDocument();
    expect(input.value).toBe("");
  });

  it("date input renders with initial value and onChange correctly (covers lines 140-156)", () => {
    // Covers the date case rendering (lines 140-156 in renderInputField).
    // The initial value is "" (from useState("")).
    // String("" ?? "") = "" covers the value attribute.
    // The onChange handler at line 141 updates value.
    const onRespond = vi.fn();
    const { container } = render(
      <A2UIInputDialog
        request={makeRequest({ input_type: "date" })}
        onRespond={onRespond}
      />,
    );
    const dateInput = container.querySelector('input[type="date"]') as HTMLInputElement;
    expect(dateInput).toBeInTheDocument();
    // Initial value is "" — this exercises String("" ?? "") = ""
    expect(dateInput.value).toBe("");

    // onChange: setValue(e.target.value) — line 141
    fireEvent.change(dateInput, { target: { value: "2026-03-15" } });
    expect(dateInput.value).toBe("2026-03-15");

    // Submit with the date value
    fireEvent.click(screen.getByText("Submit"));
    expect(onRespond).toHaveBeenCalledWith("req-1", "2026-03-15");
  });

  it("default case input renders with initial empty value (covers line 188: String(value ?? '') with empty value)", () => {
    // The default switch case at line 185 renders a text input.
    // Initial value is "" — String("" ?? "") = "" exercises the value attribute (line 188).
    const { container } = render(
      <A2UIInputDialog
        request={makeRequest({ input_type: "unknown" as any })}
        onRespond={vi.fn()}
      />,
    );
    const input = container.querySelector('input[placeholder="Enter value..."]') as HTMLInputElement;
    expect(input).toBeInTheDocument();
    // The value attribute (line 188) renders with empty string
    expect(input.value).toBe("");
  });

  it("select input onChange covers ?? '' for empty initial value (covers select branch lines 149-162)", () => {
    // Select case: initial value is "" so String("" ?? "") = "".
    // This exercises the value attribute on the select (line 150: String(value ?? "")).
    const { container } = render(
      <A2UIInputDialog
        request={makeRequest({ input_type: "select", options: ["X", "Y"] })}
        onRespond={vi.fn()}
      />,
    );
    const select = container.querySelector("select") as HTMLSelectElement;
    expect(select).toBeInTheDocument();
    // Initial value is "" which renders the "Select an option..." default
    expect(select.value).toBe("");
  });
});
