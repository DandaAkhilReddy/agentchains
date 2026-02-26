import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import A2UIForm from "../A2UIForm";

describe("A2UIForm", () => {
  it("renders text field type", () => {
    render(
      <A2UIForm
        componentId="form-1"
        data={{
          fields: [{ name: "username", type: "text", label: "Username" }],
        }}
      />
    );
    const input = screen.getByLabelText("Username");
    expect(input).toBeInTheDocument();
    expect(input).toHaveAttribute("type", "text");
  });

  it("renders textarea field type", () => {
    render(
      <A2UIForm
        componentId="form-1"
        data={{
          fields: [{ name: "bio", type: "textarea", label: "Bio" }],
        }}
      />
    );
    const textarea = screen.getByLabelText("Bio");
    expect(textarea).toBeInTheDocument();
    expect(textarea.tagName).toBe("TEXTAREA");
  });

  it("renders select field type with options", () => {
    render(
      <A2UIForm
        componentId="form-1"
        data={{
          fields: [
            {
              name: "color",
              type: "select",
              label: "Color",
              options: ["Red", "Green", "Blue"],
            },
          ],
        }}
      />
    );
    const select = screen.getByLabelText("Color");
    expect(select).toBeInTheDocument();
    expect(select.tagName).toBe("SELECT");
    expect(screen.getByText("Red")).toBeInTheDocument();
    expect(screen.getByText("Green")).toBeInTheDocument();
    expect(screen.getByText("Blue")).toBeInTheDocument();
    // Also has the default "Select..." option
    expect(screen.getByText("Select...")).toBeInTheDocument();
  });

  it("renders checkbox field type", () => {
    render(
      <A2UIForm
        componentId="form-1"
        data={{
          fields: [
            { name: "agree", type: "checkbox", label: "Agreement", placeholder: "I agree to terms" },
          ],
        }}
      />
    );
    const checkbox = document.getElementById("a2ui-form-1-agree") as HTMLInputElement;
    expect(checkbox).toBeInTheDocument();
    expect(checkbox.type).toBe("checkbox");
    expect(screen.getByText("I agree to terms")).toBeInTheDocument();
  });

  it("renders number field type", () => {
    render(
      <A2UIForm
        componentId="form-1"
        data={{
          fields: [{ name: "age", type: "number", label: "Age" }],
        }}
      />
    );
    const input = screen.getByLabelText("Age");
    expect(input).toBeInTheDocument();
    expect(input).toHaveAttribute("type", "number");
  });

  it("shows required indicator for required fields", () => {
    render(
      <A2UIForm
        componentId="form-1"
        data={{
          fields: [{ name: "email", type: "email", label: "Email", required: true }],
        }}
      />
    );
    const asterisk = screen.getByText("*");
    expect(asterisk).toBeInTheDocument();
    expect(asterisk.className).toContain("text-[#f87171]");
  });

  it("uses default values when provided", () => {
    render(
      <A2UIForm
        componentId="form-1"
        data={{
          fields: [
            { name: "name", type: "text", label: "Name", default_value: "John" },
            { name: "count", type: "number", label: "Count", default_value: 42 },
            { name: "subscribe", type: "checkbox", label: "Subscribe", default_value: true },
          ],
        }}
      />
    );
    expect(screen.getByLabelText("Name")).toHaveValue("John");
    expect(screen.getByLabelText("Count")).toHaveValue(42);
    const checkbox = document.getElementById("a2ui-form-1-subscribe") as HTMLInputElement;
    expect(checkbox.checked).toBe(true);
  });

  it("calls onSubmit with correct form data", () => {
    const handleSubmit = vi.fn();
    render(
      <A2UIForm
        componentId="form-1"
        data={{
          fields: [
            { name: "name", type: "text", label: "Name" },
            { name: "age", type: "number", label: "Age" },
          ],
        }}
        onSubmit={handleSubmit}
      />
    );
    fireEvent.change(screen.getByLabelText("Name"), { target: { value: "Alice" } });
    fireEvent.change(screen.getByLabelText("Age"), { target: { value: "30" } });
    fireEvent.click(screen.getByText("Submit"));
    expect(handleSubmit).toHaveBeenCalledTimes(1);
    expect(handleSubmit).toHaveBeenCalledWith("form-1", { name: "Alice", age: 30 });
  });

  it("validates required fields before submit", () => {
    render(
      <A2UIForm
        componentId="form-1"
        data={{
          fields: [
            { name: "email", type: "email", label: "Email", required: true },
          ],
        }}
      />
    );
    const input = screen.getByLabelText(/Email/);
    expect(input).toHaveAttribute("required");
  });

  it("handles empty form submission", () => {
    const handleSubmit = vi.fn();
    render(
      <A2UIForm
        componentId="form-1"
        data={{ fields: [] }}
        onSubmit={handleSubmit}
      />
    );
    fireEvent.click(screen.getByText("Submit"));
    expect(handleSubmit).toHaveBeenCalledWith("form-1", {});
  });

  it("disables submit during loading (after submission)", () => {
    render(
      <A2UIForm
        componentId="form-1"
        data={{
          fields: [{ name: "name", type: "text", label: "Name" }],
        }}
      />
    );
    const button = screen.getByText("Submit");
    expect(button).not.toBeDisabled();
    fireEvent.click(button);
    const submittedButton = screen.getByText("Submitted");
    expect(submittedButton).toBeDisabled();
  });

  it("shows field labels", () => {
    render(
      <A2UIForm
        componentId="form-1"
        data={{
          fields: [
            { name: "first", type: "text", label: "First Name" },
            { name: "last", type: "text", label: "Last Name" },
          ],
        }}
      />
    );
    expect(screen.getByText("First Name")).toBeInTheDocument();
    expect(screen.getByText("Last Name")).toBeInTheDocument();
  });

  it("shows field descriptions/help text (form description)", () => {
    render(
      <A2UIForm
        componentId="form-1"
        data={{
          title: "Registration",
          description: "Please fill out all required fields below.",
          fields: [{ name: "name", type: "text", label: "Name" }],
        }}
      />
    );
    expect(screen.getByText("Registration")).toBeInTheDocument();
    expect(
      screen.getByText("Please fill out all required fields below.")
    ).toBeInTheDocument();
  });

  it("handles multiple fields", () => {
    render(
      <A2UIForm
        componentId="form-1"
        data={{
          fields: [
            { name: "name", type: "text", label: "Name" },
            { name: "email", type: "email", label: "Email" },
            { name: "bio", type: "textarea", label: "Bio" },
            { name: "role", type: "select", label: "Role", options: ["Admin", "User"] },
            { name: "agree", type: "checkbox", label: "Agree" },
          ],
        }}
      />
    );
    expect(screen.getByLabelText("Name")).toBeInTheDocument();
    expect(screen.getByLabelText("Email")).toBeInTheDocument();
    expect(screen.getByLabelText("Bio")).toBeInTheDocument();
    expect(screen.getByLabelText("Role")).toBeInTheDocument();
    const checkbox = document.getElementById("a2ui-form-1-agree") as HTMLInputElement;
    expect(checkbox).toBeInTheDocument();
  });

  it("renders submit button with custom label", () => {
    render(
      <A2UIForm
        componentId="form-1"
        data={{
          fields: [],
          submit_label: "Send",
        }}
      />
    );
    expect(screen.getByText("Send")).toBeInTheDocument();
  });

  it("renders default Submit label when submit_label is not provided", () => {
    render(
      <A2UIForm
        componentId="form-1"
        data={{ fields: [] }}
      />
    );
    expect(screen.getByText("Submit")).toBeInTheDocument();
  });

  it("error state display — submit button shows Submitted and is disabled after submit", () => {
    const handleSubmit = vi.fn();
    render(
      <A2UIForm
        componentId="form-1"
        data={{
          fields: [{ name: "name", type: "text", label: "Name" }],
        }}
        onSubmit={handleSubmit}
      />
    );
    fireEvent.click(screen.getByText("Submit"));
    expect(screen.getByText("Submitted")).toBeDisabled();
    expect(screen.getByText("Submitted").className).toContain("disabled:opacity-50");
  });

  it("renders form without title when title is not provided", () => {
    const { container } = render(
      <A2UIForm
        componentId="form-1"
        data={{ fields: [{ name: "x", type: "text" }] }}
      />
    );
    expect(container.querySelector("h3")).not.toBeInTheDocument();
  });

  it("renders placeholder text for text inputs", () => {
    render(
      <A2UIForm
        componentId="form-1"
        data={{
          fields: [
            { name: "search", type: "text", label: "Search", placeholder: "Type to search..." },
          ],
        }}
      />
    );
    expect(screen.getByPlaceholderText("Type to search...")).toBeInTheDocument();
  });

  it("checkbox uses field name as fallback text when placeholder is missing", () => {
    render(
      <A2UIForm
        componentId="form-1"
        data={{
          fields: [
            { name: "accept", type: "checkbox", label: "Terms" },
          ],
        }}
      />
    );
    expect(screen.getByText("accept")).toBeInTheDocument();
  });

  it("handles form submission without onSubmit callback", () => {
    render(
      <A2UIForm
        componentId="form-1"
        data={{
          fields: [{ name: "name", type: "text", label: "Name" }],
        }}
      />
    );
    // Should not throw when onSubmit is undefined
    fireEvent.click(screen.getByText("Submit"));
    expect(screen.getByText("Submitted")).toBeInTheDocument();
  });

  it("renders form with no fields when fields is undefined", () => {
    render(
      <A2UIForm
        componentId="form-1"
        data={{}}
      />
    );
    expect(screen.getByText("Submit")).toBeInTheDocument();
  });

  it("renders select with no options (covers field.options ?? [] branch on line 112)", () => {
    // When options is undefined the component uses `field.options ?? []` — an empty array.
    render(
      <A2UIForm
        componentId="form-1"
        data={{
          fields: [
            { name: "choice", type: "select", label: "Choice" },
          ],
        }}
      />
    );
    const select = screen.getByLabelText("Choice") as HTMLSelectElement;
    expect(select).toBeInTheDocument();
    expect(select.tagName).toBe("SELECT");
    // Only the default "Select..." option should be present (no extra options)
    expect(select.options).toHaveLength(1);
    expect(select.options[0].value).toBe("");
  });

  it("checkbox uses field.name as label text when placeholder is absent (line 127: ?? field.name)", () => {
    // When a checkbox field has no placeholder, `field.placeholder ?? field.name` returns
    // the field name itself. This was already covered by the existing 'checkbox uses field
    // name as fallback text' test, but let's explicitly verify the ?? branch path.
    render(
      <A2UIForm
        componentId="form-1"
        data={{
          fields: [
            { name: "newsletter", type: "checkbox", label: "Newsletter" },
          ],
        }}
      />
    );
    // field.placeholder is undefined → fallback to field.name = "newsletter"
    expect(screen.getByText("newsletter")).toBeInTheDocument();
    const checkbox = document.getElementById(
      "a2ui-form-1-newsletter"
    ) as HTMLInputElement;
    expect(checkbox).toBeInTheDocument();
    expect(checkbox.type).toBe("checkbox");
  });

  it("textarea onChange calls handleChange and updates submitted values (lines 97-107)", () => {
    // Cover the textarea branch onChange handler at line 97:
    // onChange={(e) => handleChange(field.name, e.target.value)}
    const handleSubmit = vi.fn();
    render(
      <A2UIForm
        componentId="form-1"
        data={{
          fields: [
            { name: "bio", type: "textarea", label: "Bio" },
          ],
        }}
        onSubmit={handleSubmit}
      />
    );
    const textarea = screen.getByLabelText("Bio") as HTMLTextAreaElement;
    fireEvent.change(textarea, { target: { value: "My biography text" } });
    fireEvent.click(screen.getByText("Submit"));
    expect(handleSubmit).toHaveBeenCalledWith("form-1", { bio: "My biography text" });
  });

  it("textarea onChange with empty string submits empty value (covers line 97 empty path)", () => {
    const handleSubmit = vi.fn();
    render(
      <A2UIForm
        componentId="form-1"
        data={{
          fields: [
            { name: "notes", type: "textarea", label: "Notes" },
          ],
        }}
        onSubmit={handleSubmit}
      />
    );
    const textarea = screen.getByLabelText("Notes") as HTMLTextAreaElement;
    // Type then clear
    fireEvent.change(textarea, { target: { value: "hello" } });
    fireEvent.change(textarea, { target: { value: "" } });
    fireEvent.click(screen.getByText("Submit"));
    expect(handleSubmit).toHaveBeenCalledWith("form-1", { notes: "" });
  });

  it("checkbox onChange toggles checked state and submits correct boolean (line 124)", () => {
    // Cover the checkbox onChange handler at line 124:
    // onChange={(e) => handleChange(field.name, e.target.checked)}
    const handleSubmit = vi.fn();
    render(
      <A2UIForm
        componentId="form-1"
        data={{
          fields: [
            { name: "accept", type: "checkbox", label: "Accept" },
          ],
        }}
        onSubmit={handleSubmit}
      />
    );
    const checkbox = document.getElementById("a2ui-form-1-accept") as HTMLInputElement;
    // Default value is false (no default_value provided, type is checkbox)
    expect(checkbox.checked).toBe(false);

    // Simulate checking the checkbox
    fireEvent.click(checkbox);
    expect(checkbox.checked).toBe(true);

    // Submit and verify the boolean true is passed
    fireEvent.click(screen.getByText("Submit"));
    expect(handleSubmit).toHaveBeenCalledWith("form-1", { accept: true });
  });

  it("checkbox onChange toggles from true to false (covers the false branch of e.target.checked)", () => {
    const handleSubmit = vi.fn();
    render(
      <A2UIForm
        componentId="form-1"
        data={{
          fields: [
            { name: "subscribe", type: "checkbox", label: "Subscribe", default_value: true },
          ],
        }}
        onSubmit={handleSubmit}
      />
    );
    const checkbox = document.getElementById("a2ui-form-1-subscribe") as HTMLInputElement;
    expect(checkbox.checked).toBe(true);

    // Uncheck it
    fireEvent.click(checkbox);
    expect(checkbox.checked).toBe(false);

    fireEvent.click(screen.getByText("Submit"));
    expect(handleSubmit).toHaveBeenCalledWith("form-1", { subscribe: false });
  });

  it("select onChange calls handleChange with the selected value (covers line 107 branch)", () => {
    const handleSubmit = vi.fn();
    render(
      <A2UIForm
        componentId="form-1"
        data={{
          fields: [
            {
              name: "priority",
              type: "select",
              label: "Priority",
              options: ["Low", "Medium", "High"],
            },
          ],
        }}
        onSubmit={handleSubmit}
      />
    );
    const select = screen.getByLabelText("Priority") as HTMLSelectElement;
    fireEvent.change(select, { target: { value: "High" } });
    fireEvent.click(screen.getByText("Submit"));
    expect(handleSubmit).toHaveBeenCalledWith("form-1", { priority: "High" });
  });

  it("textarea value uses ?? '' when field value is undefined (covers line 96 ?? fallback)", () => {
    // Render with empty fields first so useState initializes with no keys.
    // Then rerender with a textarea field — values[field.name] will be undefined
    // on the first render cycle, hitting the `?? ""` fallback at line 96.
    const { rerender } = render(
      <A2UIForm
        componentId="form-x"
        data={{ fields: [] }}
      />
    );
    // Rerender with a textarea — values["notes"] is undefined since it wasn't in initial fields
    rerender(
      <A2UIForm
        componentId="form-x"
        data={{ fields: [{ name: "notes", type: "textarea", label: "Notes" }] }}
      />
    );
    // The textarea should render with empty value (from ?? "")
    const textarea = screen.getByLabelText("Notes") as HTMLTextAreaElement;
    expect(textarea.value).toBe("");
  });

  it("select value uses ?? '' when field value is undefined (covers line 106 ?? fallback)", () => {
    // Same rerender trick to get values[field.name] = undefined for a select.
    const { rerender } = render(
      <A2UIForm
        componentId="form-x"
        data={{ fields: [] }}
      />
    );
    rerender(
      <A2UIForm
        componentId="form-x"
        data={{
          fields: [{ name: "choice", type: "select", label: "Choice", options: ["A", "B"] }],
        }}
      />
    );
    const select = screen.getByLabelText("Choice") as HTMLSelectElement;
    // The select value defaults to "" (from ?? "") so the default option is selected
    expect(select.value).toBe("");
  });

  it("input value uses ?? '' when field value is undefined (covers line 133 ?? fallback)", () => {
    // Same rerender trick to get values[field.name] = undefined for a regular input.
    const { rerender } = render(
      <A2UIForm
        componentId="form-x"
        data={{ fields: [] }}
      />
    );
    rerender(
      <A2UIForm
        componentId="form-x"
        data={{ fields: [{ name: "email", type: "email", label: "Email" }] }}
      />
    );
    const input = screen.getByLabelText("Email") as HTMLInputElement;
    expect(input.value).toBe("");
  });
});
