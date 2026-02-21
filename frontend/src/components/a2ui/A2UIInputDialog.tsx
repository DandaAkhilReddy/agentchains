import { useState, type FormEvent } from "react";
import type { A2UIRequestInputMessage, A2UIInputType } from "../../types/a2ui";

/**
 * A2UI Input request dialog.
 *
 * Renders a modal with the appropriate input field based on the
 * requested input_type (text, select, number, date, file).
 */
interface A2UIInputDialogProps {
  request: A2UIRequestInputMessage;
  onRespond: (requestId: string, value: any) => void;
}

export default function A2UIInputDialog({
  request,
  onRespond,
}: A2UIInputDialogProps) {
  const { request_id, input_type, prompt, options, validation } = request;
  const [value, setValue] = useState<any>(input_type === "file" ? null : "");
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = (e: FormEvent) => {
    e.preventDefault();
    setError(null);

    // Basic required validation
    if (input_type !== "file" && (value === "" || value == null)) {
      setError("This field is required.");
      return;
    }

    // Min/max validation for numbers
    if (input_type === "number" && validation) {
      const num = Number(value);
      if (validation.min != null && num < validation.min) {
        setError(`Minimum value is ${validation.min}.`);
        return;
      }
      if (validation.max != null && num > validation.max) {
        setError(`Maximum value is ${validation.max}.`);
        return;
      }
    }

    // Pattern validation for text
    if (input_type === "text" && validation?.pattern) {
      const re = new RegExp(validation.pattern);
      if (!re.test(String(value))) {
        setError(validation.pattern_message ?? "Invalid format.");
        return;
      }
    }

    onRespond(request_id, value);
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm">
      <div className="mx-4 w-full max-w-md rounded-2xl border border-[rgba(96,165,250,0.25)] bg-[#141928] p-6 shadow-2xl">
        {/* Prompt */}
        <h3 className="mb-1 text-sm font-semibold text-[#e2e8f0]">
          Input Requested
        </h3>
        <p className="mb-5 text-sm text-[#94a3b8]">{prompt}</p>

        <form onSubmit={handleSubmit} className="flex flex-col gap-4">
          {renderInputField(input_type, value, setValue, options, validation)}

          {/* Error message */}
          {error && (
            <p className="text-xs text-[#f87171]">{error}</p>
          )}

          {/* Actions */}
          <div className="flex gap-3">
            <button
              type="button"
              onClick={() => onRespond(request_id, null)}
              className="flex-1 rounded-lg border border-[rgba(255,255,255,0.1)] px-4 py-2.5 text-sm font-medium text-[#94a3b8] transition-colors hover:bg-[rgba(255,255,255,0.04)] hover:text-[#e2e8f0]"
            >
              Cancel
            </button>
            <button
              type="submit"
              className="flex-1 rounded-lg bg-[#60a5fa] px-4 py-2.5 text-sm font-medium text-[#0a0e1a] transition-colors hover:bg-[#3b82f6]"
            >
              Submit
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

function renderInputField(
  inputType: A2UIInputType,
  value: any,
  setValue: (v: any) => void,
  options?: string[],
  validation?: Record<string, any>,
) {
  const baseClasses =
    "w-full rounded-lg border border-[rgba(255,255,255,0.1)] bg-[#0d1220] px-3 py-2.5 text-sm text-[#e2e8f0] placeholder-[#475569] outline-none transition-colors focus:border-[#60a5fa]";

  switch (inputType) {
    case "text":
      return (
        <input
          type="text"
          value={String(value ?? "")}
          onChange={(e) => setValue(e.target.value)}
          placeholder="Enter text..."
          autoFocus
          maxLength={validation?.max_length}
          className={baseClasses}
        />
      );

    case "number":
      return (
        <input
          type="number"
          value={value === "" ? "" : Number(value)}
          onChange={(e) => setValue(e.target.value)}
          placeholder="Enter number..."
          autoFocus
          min={validation?.min}
          max={validation?.max}
          step={validation?.step ?? "any"}
          className={baseClasses}
        />
      );

    case "date":
      return (
        <input
          type="date"
          value={String(value ?? "")}
          onChange={(e) => setValue(e.target.value)}
          autoFocus
          className={baseClasses}
        />
      );

    case "select":
      return (
        <select
          value={String(value ?? "")}
          onChange={(e) => setValue(e.target.value)}
          autoFocus
          className={baseClasses}
        >
          <option value="">Select an option...</option>
          {(options ?? []).map((opt) => (
            <option key={opt} value={opt}>
              {opt}
            </option>
          ))}
        </select>
      );

    case "file":
      return (
        <div>
          <input
            type="file"
            onChange={(e) => {
              const file = e.target.files?.[0] ?? null;
              setValue(file);
            }}
            accept={validation?.accept}
            className="block w-full text-sm text-[#94a3b8] file:mr-4 file:rounded-lg file:border-0 file:bg-[#1e293b] file:px-4 file:py-2 file:text-sm file:font-medium file:text-[#60a5fa] hover:file:bg-[#334155]"
          />
          {value && (
            <p className="mt-1 text-xs text-[#64748b]">
              Selected: {(value as File).name}
            </p>
          )}
        </div>
      );

    default:
      return (
        <input
          type="text"
          value={String(value ?? "")}
          onChange={(e) => setValue(e.target.value)}
          placeholder="Enter value..."
          autoFocus
          className={baseClasses}
        />
      );
  }
}
