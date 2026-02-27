import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import ExecutionForm from "../ExecutionForm";

describe("ExecutionForm", () => {
  const defaultProps = {
    actionId: "action-abc-123",
    onExecute: vi.fn(),
  };

  it("renders form fields (textarea, consent checkbox, submit button)", () => {
    render(<ExecutionForm {...defaultProps} />);

    // Action ID is displayed
    expect(screen.getByText("action-abc-123")).toBeInTheDocument();

    // Header h3
    const heading = screen.getByRole("heading", { name: "Execute Action" });
    expect(heading).toBeInTheDocument();

    // Label for parameters
    expect(screen.getByText("Parameters (JSON)")).toBeInTheDocument();

    // Textarea with default value
    const textarea = screen.getByPlaceholderText('{ "key": "value" }');
    expect(textarea).toBeInTheDocument();
    expect(textarea).toHaveValue("{}");

    // Consent checkbox
    const checkbox = screen.getByRole("checkbox");
    expect(checkbox).toBeInTheDocument();
    expect(checkbox).not.toBeChecked();

    // Consent label text
    expect(
      screen.getByText("I consent to this execution"),
    ).toBeInTheDocument();
  });

  it("calls onExecute with parsed params and consent on submit", () => {
    const onExecute = vi.fn();
    render(<ExecutionForm actionId="act-1" onExecute={onExecute} />);

    // Type valid JSON in the textarea
    const textarea = screen.getByPlaceholderText('{ "key": "value" }');
    fireEvent.change(textarea, {
      target: { value: '{"foo":"bar"}' },
    });

    // Check consent
    const checkbox = screen.getByRole("checkbox");
    fireEvent.click(checkbox);

    // Submit the form
    const submitButton = screen.getByRole("button", {
      name: /Execute Action/i,
    });
    fireEvent.click(submitButton);

    expect(onExecute).toHaveBeenCalledTimes(1);
    expect(onExecute).toHaveBeenCalledWith({ foo: "bar" }, true);
  });

  it("shows parse error for invalid JSON and does not call onExecute", () => {
    const onExecute = vi.fn();
    render(<ExecutionForm actionId="act-2" onExecute={onExecute} />);

    // Type invalid JSON
    const textarea = screen.getByPlaceholderText('{ "key": "value" }');
    fireEvent.change(textarea, { target: { value: "not json" } });

    // Check consent
    const checkbox = screen.getByRole("checkbox");
    fireEvent.click(checkbox);

    // Submit
    const submitButton = screen.getByRole("button", {
      name: /Execute Action/i,
    });
    fireEvent.click(submitButton);

    expect(
      screen.getByText("Invalid JSON. Please check your parameters."),
    ).toBeInTheDocument();
    expect(onExecute).not.toHaveBeenCalled();
  });

  it("does not call onExecute when consent is not checked", () => {
    const onExecute = vi.fn();
    render(<ExecutionForm actionId="act-3" onExecute={onExecute} />);

    // Submit without checking consent — button should be disabled
    const submitButton = screen.getByRole("button", {
      name: /Execute Action/i,
    });
    expect(submitButton).toBeDisabled();

    fireEvent.click(submitButton);
    expect(onExecute).not.toHaveBeenCalled();
  });

  it("shows loading state when isLoading is true", () => {
    render(
      <ExecutionForm
        actionId="act-4"
        onExecute={vi.fn()}
        isLoading={true}
      />,
    );

    expect(screen.getByText("Executing...")).toBeInTheDocument();
    const submitButton = screen.getByRole("button");
    expect(submitButton).toBeDisabled();
  });

  it("does not call onExecute when consent is false but JSON is valid (covers line 31 branch)", () => {
    // This test submits the form via the form's submit event rather than the button
    // to exercise the path where JSON parses correctly but consent=false returns early.
    const onExecute = vi.fn();
    const { container } = render(
      <ExecutionForm actionId="act-5" onExecute={onExecute} />,
    );

    // JSON is already valid "{}" — don't change consent (stays false)
    // Submit the form directly to bypass the disabled-button guard
    const form = container.querySelector("form")!;
    form.dispatchEvent(new Event("submit", { bubbles: true, cancelable: true }));

    // consent is still false so onExecute should NOT be called
    expect(onExecute).not.toHaveBeenCalled();
    // No parse error shown (JSON was valid)
    expect(
      screen.queryByText("Invalid JSON. Please check your parameters."),
    ).not.toBeInTheDocument();
  });

  it("clears parse error when textarea content changes after a failed parse", () => {
    const onExecute = vi.fn();
    render(<ExecutionForm actionId="act-6" onExecute={onExecute} />);

    // First: type invalid JSON and trigger error
    const textarea = screen.getByPlaceholderText('{ "key": "value" }');
    fireEvent.change(textarea, { target: { value: "bad json" } });

    const checkbox = screen.getByRole("checkbox");
    fireEvent.click(checkbox);

    // Submit to trigger error
    const submitButton = screen.getByRole("button", { name: /Execute Action/i });
    fireEvent.click(submitButton);
    expect(
      screen.getByText("Invalid JSON. Please check your parameters."),
    ).toBeInTheDocument();

    // Now change the textarea — error should clear
    fireEvent.change(textarea, { target: { value: '{"key": "value"}' } });
    expect(
      screen.queryByText("Invalid JSON. Please check your parameters."),
    ).not.toBeInTheDocument();
  });
});
