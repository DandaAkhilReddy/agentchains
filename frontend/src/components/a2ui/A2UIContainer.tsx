import type { A2UIComponent, A2UIProgressMessage } from "../../types/a2ui";
import A2UICard from "./A2UICard";
import A2UITable from "./A2UITable";
import A2UIForm from "./A2UIForm";
import A2UIProgress from "./A2UIProgress";

/**
 * Top-level renderer that dispatches each A2UI component to the
 * correct widget based on its component_type.
 */
interface A2UIContainerProps {
  components: A2UIComponent[] | Map<string, A2UIComponent>;
  progress?: Map<string, A2UIProgressMessage>;
  onFormSubmit?: (componentId: string, values: Record<string, unknown>) => void;
}

export default function A2UIContainer({
  components,
  progress,
  onFormSubmit,
}: A2UIContainerProps) {
  const entries = Array.isArray(components)
    ? components
    : Array.from(components.values());

  if (entries.length === 0 && (!progress || progress.size === 0)) {
    return (
      <div className="flex items-center justify-center py-16 text-sm text-[#64748b]">
        No components rendered yet.
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-4">
      {/* Progress bars (pinned to top) */}
      {progress &&
        Array.from(progress.values()).map((p) => (
          <A2UIProgress key={p.task_id} progress={p} />
        ))}

      {/* Dynamic components */}
      {entries.map((component) => (
        <div key={component.component_id}>
          {renderComponent(component, onFormSubmit)}
        </div>
      ))}
    </div>
  );
}

function renderComponent(
  component: A2UIComponent,
  onFormSubmit?: (componentId: string, values: Record<string, unknown>) => void,
) {
  switch (component.component_type) {
    case "card":
      return <A2UICard data={component.data} metadata={component.metadata} />;

    case "table":
      return <A2UITable data={component.data} metadata={component.metadata} />;

    case "form":
      return (
        <A2UIForm
          componentId={component.component_id}
          data={component.data}
          metadata={component.metadata}
          onSubmit={onFormSubmit}
        />
      );

    case "chart":
      return (
        <div className="rounded-2xl border border-[rgba(255,255,255,0.06)] bg-[#141928] p-6">
          <p className="mb-2 text-xs font-medium uppercase tracking-wider text-[#64748b]">
            Chart
          </p>
          <p className="text-sm text-[#e2e8f0]">
            {component.data.title ?? "Chart component"}
          </p>
          <pre className="mt-2 overflow-x-auto rounded-lg bg-[#0d1220] p-4 text-xs text-[#94a3b8]">
            {JSON.stringify(component.data, null, 2)}
          </pre>
        </div>
      );

    case "markdown":
      return (
        <div className="rounded-2xl border border-[rgba(255,255,255,0.06)] bg-[#141928] p-6">
          <div className="prose prose-invert max-w-none text-sm text-[#e2e8f0]">
            {component.data.content ?? ""}
          </div>
        </div>
      );

    case "code":
      return (
        <div className="rounded-2xl border border-[rgba(255,255,255,0.06)] bg-[#0d1220] p-6">
          {component.data.language && (
            <span className="mb-2 inline-block rounded bg-[#1e293b] px-2 py-0.5 text-[10px] font-medium uppercase tracking-wider text-[#60a5fa]">
              {component.data.language}
            </span>
          )}
          <pre className="overflow-x-auto text-xs text-[#e2e8f0]">
            <code>{component.data.source ?? component.data.content ?? ""}</code>
          </pre>
        </div>
      );

    case "image":
      return (
        <div className="rounded-2xl border border-[rgba(255,255,255,0.06)] bg-[#141928] p-4">
          {component.data.alt && (
            <p className="mb-2 text-xs text-[#64748b]">{component.data.alt}</p>
          )}
          <img
            src={component.data.src ?? component.data.url}
            alt={component.data.alt ?? ""}
            className="max-w-full rounded-lg"
          />
        </div>
      );

    case "alert": {
      const levelColors: Record<string, string> = {
        info: "#60a5fa",
        success: "#34d399",
        warning: "#fbbf24",
        error: "#f87171",
      };
      const color = levelColors[component.data.level ?? "info"] ?? "#60a5fa";
      return (
        <div
          className="rounded-2xl border p-4"
          style={{
            borderColor: `${color}33`,
            backgroundColor: `${color}0a`,
          }}
        >
          <p className="text-sm font-semibold" style={{ color }}>
            {component.data.title ?? "Alert"}
          </p>
          {component.data.message && (
            <p className="mt-1 text-sm text-[#e2e8f0]">
              {component.data.message}
            </p>
          )}
        </div>
      );
    }

    case "steps": {
      const steps: Array<{ label: string; status?: string }> =
        component.data.steps ?? [];
      return (
        <div className="rounded-2xl border border-[rgba(255,255,255,0.06)] bg-[#141928] p-6">
          {component.data.title && (
            <p className="mb-4 text-sm font-semibold text-[#e2e8f0]">
              {component.data.title}
            </p>
          )}
          <ol className="flex flex-col gap-3">
            {steps.map((step, i) => {
              const done = step.status === "done";
              const active = step.status === "active";
              return (
                <li key={i} className="flex items-center gap-3">
                  <span
                    className="flex h-6 w-6 flex-shrink-0 items-center justify-center rounded-full text-xs font-bold"
                    style={{
                      backgroundColor: done
                        ? "#34d399"
                        : active
                          ? "#60a5fa"
                          : "#1e293b",
                      color: done || active ? "#0a0e1a" : "#64748b",
                    }}
                  >
                    {done ? "\u2713" : i + 1}
                  </span>
                  <span
                    className="text-sm"
                    style={{
                      color: done
                        ? "#34d399"
                        : active
                          ? "#e2e8f0"
                          : "#64748b",
                    }}
                  >
                    {step.label}
                  </span>
                </li>
              );
            })}
          </ol>
        </div>
      );
    }

    default:
      return (
        <div className="rounded-2xl border border-[rgba(255,255,255,0.06)] bg-[#141928] p-4">
          <p className="text-xs text-[#64748b]">
            Unknown component type: {component.component_type}
          </p>
          <pre className="mt-2 overflow-x-auto text-xs text-[#94a3b8]">
            {JSON.stringify(component.data, null, 2)}
          </pre>
        </div>
      );
  }
}
