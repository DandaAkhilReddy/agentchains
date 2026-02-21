import type { A2UIProgressMessage } from "../../types/a2ui";

/**
 * A2UI Progress bar widget.
 *
 * Renders one of three progress styles:
 *   - determinate: shows a percentage bar with value/total
 *   - indeterminate: animated pulsing bar
 *   - streaming: animated dots to indicate ongoing streaming
 */
interface A2UIProgressProps {
  progress: A2UIProgressMessage;
}

export default function A2UIProgress({ progress }: A2UIProgressProps) {
  const { progress_type, value, total, message, task_id } = progress;

  const percent =
    progress_type === "determinate" && total && total > 0
      ? Math.min(100, Math.round(((value ?? 0) / total) * 100))
      : 0;

  return (
    <div className="rounded-2xl border border-[rgba(255,255,255,0.06)] bg-[#141928] p-4">
      {/* Header: message + percentage */}
      <div className="mb-2 flex items-center justify-between">
        <span className="text-sm text-[#e2e8f0]">
          {message ?? `Task ${task_id}`}
        </span>
        {progress_type === "determinate" && (
          <span className="text-xs font-medium text-[#60a5fa]">
            {percent}%
          </span>
        )}
        {progress_type === "streaming" && (
          <span className="flex items-center gap-1 text-xs text-[#64748b]">
            Streaming
            <span className="inline-flex gap-0.5">
              <span className="h-1 w-1 animate-bounce rounded-full bg-[#60a5fa]" style={{ animationDelay: "0ms" }} />
              <span className="h-1 w-1 animate-bounce rounded-full bg-[#60a5fa]" style={{ animationDelay: "150ms" }} />
              <span className="h-1 w-1 animate-bounce rounded-full bg-[#60a5fa]" style={{ animationDelay: "300ms" }} />
            </span>
          </span>
        )}
      </div>

      {/* Bar track */}
      <div className="h-2 w-full overflow-hidden rounded-full bg-[#0d1220]">
        {progress_type === "determinate" && (
          <div
            className="h-full rounded-full bg-gradient-to-r from-[#3b82f6] to-[#60a5fa] transition-all duration-300 ease-out"
            style={{ width: `${percent}%` }}
          />
        )}
        {progress_type === "indeterminate" && (
          <div className="h-full w-1/3 animate-indeterminate rounded-full bg-gradient-to-r from-[#3b82f6] to-[#60a5fa]" />
        )}
        {progress_type === "streaming" && (
          <div className="h-full w-full animate-pulse rounded-full bg-gradient-to-r from-[#3b82f6]/30 via-[#60a5fa]/60 to-[#3b82f6]/30" />
        )}
      </div>

      {/* Value detail for determinate */}
      {progress_type === "determinate" && total != null && (
        <p className="mt-1.5 text-xs text-[#64748b]">
          {value ?? 0} / {total}
        </p>
      )}

      {/* Inline style for the indeterminate animation */}
      <style>{`
        @keyframes indeterminate {
          0% { transform: translateX(-100%); }
          100% { transform: translateX(400%); }
        }
        .animate-indeterminate {
          animation: indeterminate 1.5s ease-in-out infinite;
        }
      `}</style>
    </div>
  );
}
