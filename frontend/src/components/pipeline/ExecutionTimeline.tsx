import { Clock, Loader2, GitBranch, CheckCircle2 } from "lucide-react";
import type { AgentExecution } from "../../types/api";
import PipelineStepCard from "./PipelineStep";

interface Props {
  execution: AgentExecution | null;
}

export default function ExecutionTimeline({ execution }: Props) {
  if (!execution) {
    return (
      <div className="rounded-2xl border border-[rgba(255,255,255,0.06)] bg-[#141928] p-10 text-center">
        <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-2xl bg-[rgba(96,165,250,0.08)] mb-4">
          <Clock className="h-7 w-7 text-[#64748b]" />
        </div>
        <p className="text-sm font-semibold text-[#94a3b8]">
          Select an agent to view execution
        </p>
        <p className="text-xs text-[#64748b] mt-1 max-w-sm mx-auto">
          Click an agent on the left to see its step-by-step execution
          timeline with tool calls and latency data.
        </p>
      </div>
    );
  }

  const completedCount = execution.steps.filter(
    (s) => s.status === "completed",
  ).length;
  const avgLatency =
    execution.steps.length > 0
      ? Math.round(
          execution.steps.reduce(
            (sum, s) => sum + (s.latencyMs ?? 0),
            0,
          ) / execution.steps.length,
        )
      : 0;

  return (
    <div className="rounded-2xl border border-[rgba(255,255,255,0.06)] bg-[#141928] p-5">
      {/* Header */}
      <div className="flex items-center justify-between mb-5">
        <div className="flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-[rgba(96,165,250,0.1)]">
            <GitBranch className="h-5 w-5 text-[#60a5fa]" />
          </div>
          <div>
            <h3 className="text-sm font-bold text-[#e2e8f0]">
              {execution.agentName}
            </h3>
            <p className="text-xs text-[#64748b] mt-0.5">
              {execution.steps.length} steps &middot; Started{" "}
              {new Date(execution.startedAt).toLocaleTimeString()}
            </p>
          </div>
        </div>
        <div className="flex items-center gap-3">
          {/* Mini stats */}
          <div className="hidden sm:flex items-center gap-4 mr-3">
            <div className="text-center">
              <p className="text-xs font-bold text-[#34d399]">{completedCount}</p>
              <p className="text-[10px] text-[#64748b]">done</p>
            </div>
            <div className="text-center">
              <p className="text-xs font-bold text-[#fbbf24]">{avgLatency}ms</p>
              <p className="text-[10px] text-[#64748b]">avg</p>
            </div>
          </div>
          {/* Status badge */}
          <span
            className={`inline-flex items-center gap-1.5 rounded-full px-3 py-1 text-xs font-semibold ${
              execution.status === "active"
                ? "bg-[rgba(52,211,153,0.1)] text-[#34d399] border border-[rgba(52,211,153,0.2)]"
                : execution.status === "error"
                  ? "bg-[rgba(248,113,113,0.1)] text-[#f87171] border border-[rgba(248,113,113,0.2)]"
                  : "bg-[rgba(100,116,139,0.1)] text-[#64748b] border border-[rgba(100,116,139,0.2)]"
            }`}
          >
            {execution.status === "active" && (
              <Loader2 className="h-3 w-3 animate-spin" />
            )}
            {execution.status === "active" && (
              <span className="relative flex h-2 w-2">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-[#34d399] opacity-75" />
                <span className="relative inline-flex rounded-full h-2 w-2 bg-[#34d399]" />
              </span>
            )}
            {execution.status === "idle" && (
              <CheckCircle2 className="h-3 w-3" />
            )}
            <span className="capitalize">{execution.status}</span>
          </span>
        </div>
      </div>

      {/* Timeline divider */}
      <div className="h-px bg-gradient-to-r from-transparent via-[rgba(255,255,255,0.06)] to-transparent mb-4" />

      {/* Steps */}
      <div className="space-y-0">
        {execution.steps.map((step, i) => (
          <PipelineStepCard key={step.id} step={step} index={i + 1} />
        ))}
      </div>
    </div>
  );
}
