import { useMemo } from "react";
import { Check, Circle, Loader2, AlertTriangle } from "lucide-react";

/**
 * A2UI Steps/Timeline Widget.
 *
 * Renders a vertical timeline of steps with status indicators
 * (pending, active, completed, error) and animated transitions
 * for status changes.
 */

export type StepStatus = "pending" | "active" | "completed" | "error";

export interface StepItem {
  label: string;
  description?: string;
  status: StepStatus;
}

interface A2UIStepsWidgetProps {
  steps: StepItem[];
  title?: string;
}

/** Color + icon configuration per status */
const STATUS_CONFIG: Record<
  StepStatus,
  {
    color: string;
    bgColor: string;
    borderColor: string;
    glowColor: string;
    lineColor: string;
  }
> = {
  completed: {
    color: "#34d399",
    bgColor: "rgba(52,211,153,0.15)",
    borderColor: "rgba(52,211,153,0.4)",
    glowColor: "0 0 8px rgba(52,211,153,0.3)",
    lineColor: "#34d399",
  },
  active: {
    color: "#60a5fa",
    bgColor: "rgba(96,165,250,0.15)",
    borderColor: "rgba(96,165,250,0.4)",
    glowColor: "0 0 12px rgba(96,165,250,0.4)",
    lineColor: "#60a5fa",
  },
  error: {
    color: "#f87171",
    bgColor: "rgba(248,113,113,0.15)",
    borderColor: "rgba(248,113,113,0.4)",
    glowColor: "0 0 8px rgba(248,113,113,0.3)",
    lineColor: "#f87171",
  },
  pending: {
    color: "#64748b",
    bgColor: "rgba(100,116,139,0.08)",
    borderColor: "rgba(100,116,139,0.2)",
    glowColor: "none",
    lineColor: "#1e293b",
  },
};

function StatusIcon({ status }: { status: StepStatus }) {
  switch (status) {
    case "completed":
      return <Check className="h-3.5 w-3.5" style={{ color: "#34d399" }} />;
    case "active":
      return (
        <Loader2
          className="h-3.5 w-3.5 animate-spin"
          style={{ color: "#60a5fa" }}
        />
      );
    case "error":
      return (
        <AlertTriangle className="h-3.5 w-3.5" style={{ color: "#f87171" }} />
      );
    case "pending":
    default:
      return <Circle className="h-3 w-3" style={{ color: "#64748b" }} />;
  }
}

export default function A2UIStepsWidget({
  steps,
  title,
}: A2UIStepsWidgetProps) {
  // Compute progress summary
  const summary = useMemo(() => {
    const completed = steps.filter((s) => s.status === "completed").length;
    const errors = steps.filter((s) => s.status === "error").length;
    const total = steps.length;
    const percent = total > 0 ? Math.round((completed / total) * 100) : 0;
    return { completed, errors, total, percent };
  }, [steps]);

  if (steps.length === 0) {
    return (
      <div className="rounded-2xl border border-[rgba(255,255,255,0.06)] bg-[#141928] p-6">
        <p className="text-sm text-[#64748b]">No steps defined.</p>
      </div>
    );
  }

  return (
    <div className="rounded-2xl border border-[rgba(255,255,255,0.06)] bg-[#141928] overflow-hidden">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-[rgba(255,255,255,0.06)] px-6 py-4">
        <div>
          {title && (
            <h3 className="text-sm font-semibold text-[#e2e8f0]">{title}</h3>
          )}
          <p className="text-[10px] text-[#64748b] mt-0.5">
            {summary.completed} of {summary.total} completed
            {summary.errors > 0 && (
              <span className="text-[#f87171]">
                {" "}
                ({summary.errors} error{summary.errors !== 1 ? "s" : ""})
              </span>
            )}
          </p>
        </div>

        {/* Progress pill */}
        <div className="flex items-center gap-2">
          <div className="h-1.5 w-20 overflow-hidden rounded-full bg-[#1e293b]">
            <div
              className="h-full rounded-full transition-all duration-500 ease-out"
              style={{
                width: `${summary.percent}%`,
                background:
                  summary.errors > 0
                    ? "linear-gradient(90deg, #34d399, #f87171)"
                    : "linear-gradient(90deg, #34d399, #60a5fa)",
              }}
            />
          </div>
          <span className="text-[10px] font-mono font-medium text-[#94a3b8]">
            {summary.percent}%
          </span>
        </div>
      </div>

      {/* Steps timeline */}
      <div className="px-6 py-5">
        <div className="flex flex-col">
          {steps.map((step, index) => {
            const config = STATUS_CONFIG[step.status];
            const isLast = index === steps.length - 1;

            return (
              <div
                key={index}
                className="relative flex gap-4"
                style={{
                  animation: `step-appear 0.3s ease-out ${index * 80}ms both`,
                }}
              >
                {/* Timeline column (icon + connector line) */}
                <div className="flex flex-col items-center">
                  {/* Status icon circle */}
                  <div
                    className="relative z-10 flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-full border-2 transition-all duration-300"
                    style={{
                      backgroundColor: config.bgColor,
                      borderColor: config.borderColor,
                      boxShadow: config.glowColor,
                    }}
                  >
                    <StatusIcon status={step.status} />

                    {/* Active pulse ring */}
                    {step.status === "active" && (
                      <div
                        className="absolute inset-0 rounded-full"
                        style={{
                          border: "2px solid rgba(96,165,250,0.3)",
                          animation: "step-pulse 2s ease-in-out infinite",
                        }}
                      />
                    )}
                  </div>

                  {/* Connector line */}
                  {!isLast && (
                    <div
                      className="w-0.5 flex-1 min-h-[24px] transition-colors duration-300"
                      style={{
                        backgroundColor: config.lineColor,
                        opacity: step.status === "pending" ? 0.3 : 0.6,
                      }}
                    />
                  )}
                </div>

                {/* Step content */}
                <div className={`flex-1 ${isLast ? "pb-0" : "pb-6"}`}>
                  <div className="flex items-center gap-2">
                    <p
                      className="text-sm font-medium transition-colors duration-300"
                      style={{
                        color:
                          step.status === "completed"
                            ? "#34d399"
                            : step.status === "active"
                              ? "#e2e8f0"
                              : step.status === "error"
                                ? "#f87171"
                                : "#64748b",
                      }}
                    >
                      {step.label}
                    </p>

                    {/* Status badge */}
                    <span
                      className="inline-flex rounded-full px-2 py-0.5 text-[9px] font-semibold uppercase tracking-wider transition-all duration-300"
                      style={{
                        backgroundColor: config.bgColor,
                        color: config.color,
                      }}
                    >
                      {step.status}
                    </span>
                  </div>

                  {step.description && (
                    <p
                      className="mt-1 text-xs leading-relaxed transition-colors duration-300"
                      style={{
                        color:
                          step.status === "pending" ? "#475569" : "#94a3b8",
                      }}
                    >
                      {step.description}
                    </p>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Inline animations */}
      <style>{`
        @keyframes step-appear {
          from {
            opacity: 0;
            transform: translateX(-8px);
          }
          to {
            opacity: 1;
            transform: translateX(0);
          }
        }
        @keyframes step-pulse {
          0%, 100% {
            transform: scale(1);
            opacity: 0.4;
          }
          50% {
            transform: scale(1.4);
            opacity: 0;
          }
        }
      `}</style>
    </div>
  );
}
