import { useEffect, useState } from "react";
import type { A2UIConfirmMessage, A2UISeverity } from "../../types/a2ui";

/**
 * A2UI Confirmation dialog.
 *
 * Displays a severity-colored modal with approve / reject buttons.
 * Auto-rejects when timeout expires.
 */
interface A2UIConfirmDialogProps {
  confirm: A2UIConfirmMessage;
  onApprove: (requestId: string, approved: boolean, reason?: string) => void;
}

const SEVERITY_CONFIG: Record<
  A2UISeverity,
  { color: string; bg: string; border: string; icon: string }
> = {
  info: {
    color: "#60a5fa",
    bg: "rgba(96, 165, 250, 0.08)",
    border: "rgba(96, 165, 250, 0.25)",
    icon: "\u2139",
  },
  warning: {
    color: "#fbbf24",
    bg: "rgba(251, 191, 36, 0.08)",
    border: "rgba(251, 191, 36, 0.25)",
    icon: "\u26A0",
  },
  critical: {
    color: "#f87171",
    bg: "rgba(248, 113, 113, 0.08)",
    border: "rgba(248, 113, 113, 0.25)",
    icon: "\u26D4",
  },
};

export default function A2UIConfirmDialog({
  confirm,
  onApprove,
}: A2UIConfirmDialogProps) {
  const { request_id, title, description, severity, timeout_seconds } = confirm;
  const config = SEVERITY_CONFIG[severity] ?? SEVERITY_CONFIG.info;
  const effectiveTimeout = timeout_seconds ?? 30;

  const [remaining, setRemaining] = useState(effectiveTimeout);

  useEffect(() => {
    if (remaining <= 0) {
      onApprove(request_id, false, "timeout");
      return;
    }
    const timer = setTimeout(() => setRemaining((r) => r - 1), 1000);
    return () => clearTimeout(timer);
  }, [remaining, request_id, onApprove]);

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm">
      <div
        className="mx-4 w-full max-w-md rounded-2xl border p-6 shadow-2xl"
        style={{
          backgroundColor: "#141928",
          borderColor: config.border,
        }}
      >
        {/* Severity header */}
        <div
          className="mb-4 flex items-center gap-3 rounded-lg px-4 py-3"
          style={{ backgroundColor: config.bg }}
        >
          <span className="text-xl" style={{ color: config.color }}>
            {config.icon}
          </span>
          <div>
            <h3
              className="text-sm font-semibold"
              style={{ color: config.color }}
            >
              {title}
            </h3>
            <p className="mt-0.5 text-xs text-[#94a3b8]">
              Severity: {severity}
            </p>
          </div>
        </div>

        {/* Description */}
        <p className="mb-4 text-sm leading-relaxed text-[#e2e8f0]">
          {description}
        </p>

        {/* Timeout countdown */}
        <div className="mb-5">
          <div className="flex items-center justify-between text-xs text-[#64748b]">
            <span>Auto-reject in</span>
            <span className="font-mono" style={{ color: config.color }}>
              {remaining}s
            </span>
          </div>
          <div className="mt-1 h-1 w-full overflow-hidden rounded-full bg-[#0d1220]">
            <div
              className="h-full rounded-full transition-all duration-1000 ease-linear"
              style={{
                width: `${(remaining / effectiveTimeout) * 100}%`,
                backgroundColor: config.color,
              }}
            />
          </div>
        </div>

        {/* Action buttons */}
        <div className="flex gap-3">
          <button
            onClick={() => onApprove(request_id, false)}
            className="flex-1 rounded-lg border border-[rgba(255,255,255,0.1)] px-4 py-2.5 text-sm font-medium text-[#94a3b8] transition-colors hover:bg-[rgba(255,255,255,0.04)] hover:text-[#e2e8f0]"
          >
            Reject
          </button>
          <button
            onClick={() => onApprove(request_id, true)}
            className="flex-1 rounded-lg px-4 py-2.5 text-sm font-medium text-[#0a0e1a] transition-colors"
            style={{ backgroundColor: config.color }}
          >
            Approve
          </button>
        </div>
      </div>
    </div>
  );
}
