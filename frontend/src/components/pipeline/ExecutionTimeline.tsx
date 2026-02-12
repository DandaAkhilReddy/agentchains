import { Clock, Loader2 } from "lucide-react";
import type { AgentExecution } from "../../types/api";
import PipelineStepCard from "./PipelineStep";

interface Props {
  execution: AgentExecution | null;
}

export default function ExecutionTimeline({ execution }: Props) {
  if (!execution) {
    return (
      <div className="glass-card p-8 text-center">
        <Clock className="mx-auto h-10 w-10 text-text-muted mb-3" />
        <p className="text-sm font-medium text-text-secondary">Select an agent to view execution</p>
        <p className="text-xs text-text-muted mt-1">
          Click an agent on the left to see its step-by-step execution timeline.
        </p>
      </div>
    );
  }

  return (
    <div className="glass-card p-5">
      <div className="flex items-center justify-between mb-4">
        <div>
          <h3 className="text-sm font-semibold text-text-primary">{execution.agentName}</h3>
          <p className="text-xs text-text-muted mt-0.5">
            {execution.steps.length} steps &middot; Started {new Date(execution.startedAt).toLocaleTimeString()}
          </p>
        </div>
        <span className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-medium ${
          execution.status === "active"
            ? "bg-success/10 text-success"
            : execution.status === "error"
              ? "bg-danger/10 text-danger"
              : "bg-surface-overlay text-text-muted"
        }`}>
          {execution.status === "active" && <Loader2 className="h-3 w-3 animate-spin" />}
          {execution.status}
        </span>
      </div>
      <div className="space-y-0">
        {execution.steps.map((step, i) => (
          <PipelineStepCard key={step.id} step={step} index={i + 1} />
        ))}
      </div>
    </div>
  );
}
