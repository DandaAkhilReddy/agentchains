import { useState, type FormEvent } from "react";

/**
 * A2UI Form widget.
 *
 * Renders dynamic form fields described by the agent and submits
 * collected values back via the onSubmit callback.
 */

interface FormField {
  name: string;
  label?: string;
  type?: "text" | "number" | "email" | "password" | "textarea" | "select" | "checkbox";
  placeholder?: string;
  required?: boolean;
  options?: string[];
  default_value?: string | number | boolean;
}

interface A2UIFormProps {
  componentId: string;
  data: Record<string, any>;
  metadata?: Record<string, any>;
  onSubmit?: (componentId: string, values: Record<string, any>) => void;
}

export default function A2UIForm({
  componentId,
  data,
  metadata,
  onSubmit,
}: A2UIFormProps) {
  const {
    title,
    description,
    fields,
    submit_label,
  } = data as {
    title?: string;
    description?: string;
    fields?: FormField[];
    submit_label?: string;
  };

  const formFields = fields ?? [];

  // Initialise form values from defaults
  const [values, setValues] = useState<Record<string, any>>(() => {
    const init: Record<string, any> = {};
    for (const f of formFields) {
      init[f.name] = f.default_value ?? (f.type === "checkbox" ? false : "");
    }
    return init;
  });

  const [submitted, setSubmitted] = useState(false);

  const handleChange = (name: string, value: any) => {
    setValues((prev) => ({ ...prev, [name]: value }));
  };

  const handleSubmit = (e: FormEvent) => {
    e.preventDefault();
    setSubmitted(true);
    onSubmit?.(componentId, values);
  };

  return (
    <div className="rounded-2xl border border-[rgba(255,255,255,0.06)] bg-[#141928] p-6">
      {title && (
        <h3 className="text-base font-semibold text-[#e2e8f0]">{title}</h3>
      )}
      {description && (
        <p className="mt-1 text-sm text-[#64748b]">{description}</p>
      )}

      <form onSubmit={handleSubmit} className="mt-5 flex flex-col gap-4">
        {formFields.map((field) => (
          <div key={field.name} className="flex flex-col gap-1.5">
            {field.label && (
              <label
                htmlFor={`a2ui-${componentId}-${field.name}`}
                className="text-xs font-medium text-[#94a3b8]"
              >
                {field.label}
                {field.required && (
                  <span className="ml-0.5 text-[#f87171]">*</span>
                )}
              </label>
            )}

            {field.type === "textarea" ? (
              <textarea
                id={`a2ui-${componentId}-${field.name}`}
                value={String(values[field.name] ?? "")}
                onChange={(e) => handleChange(field.name, e.target.value)}
                placeholder={field.placeholder}
                required={field.required}
                rows={4}
                className="rounded-lg border border-[rgba(255,255,255,0.1)] bg-[#0d1220] px-3 py-2 text-sm text-[#e2e8f0] placeholder-[#475569] outline-none transition-colors focus:border-[#60a5fa]"
              />
            ) : field.type === "select" ? (
              <select
                id={`a2ui-${componentId}-${field.name}`}
                value={String(values[field.name] ?? "")}
                onChange={(e) => handleChange(field.name, e.target.value)}
                required={field.required}
                className="rounded-lg border border-[rgba(255,255,255,0.1)] bg-[#0d1220] px-3 py-2 text-sm text-[#e2e8f0] outline-none transition-colors focus:border-[#60a5fa]"
              >
                <option value="">Select...</option>
                {(field.options ?? []).map((opt) => (
                  <option key={opt} value={opt}>
                    {opt}
                  </option>
                ))}
              </select>
            ) : field.type === "checkbox" ? (
              <label className="flex items-center gap-2 text-sm text-[#e2e8f0]">
                <input
                  id={`a2ui-${componentId}-${field.name}`}
                  type="checkbox"
                  checked={Boolean(values[field.name])}
                  onChange={(e) => handleChange(field.name, e.target.checked)}
                  className="h-4 w-4 rounded border-[rgba(255,255,255,0.1)] bg-[#0d1220] accent-[#60a5fa]"
                />
                {field.placeholder ?? field.name}
              </label>
            ) : (
              <input
                id={`a2ui-${componentId}-${field.name}`}
                type={field.type ?? "text"}
                value={String(values[field.name] ?? "")}
                onChange={(e) =>
                  handleChange(
                    field.name,
                    field.type === "number"
                      ? Number(e.target.value)
                      : e.target.value,
                  )
                }
                placeholder={field.placeholder}
                required={field.required}
                className="rounded-lg border border-[rgba(255,255,255,0.1)] bg-[#0d1220] px-3 py-2 text-sm text-[#e2e8f0] placeholder-[#475569] outline-none transition-colors focus:border-[#60a5fa]"
              />
            )}
          </div>
        ))}

        <button
          type="submit"
          disabled={submitted}
          className="mt-2 self-start rounded-lg bg-[#60a5fa] px-5 py-2 text-sm font-medium text-[#0a0e1a] transition-colors hover:bg-[#3b82f6] disabled:cursor-not-allowed disabled:opacity-50"
        >
          {submitted ? "Submitted" : (submit_label ?? "Submit")}
        </button>
      </form>
    </div>
  );
}
