import { useState } from "react";
import { CheckCircle2, XCircle, Loader2, Clock, ChevronDown, ChevronRight } from "lucide-react";
import type { PipelineStep } from "../../types/api";

interface Props {
  step: PipelineStep;
  index: number;
}

export default function PipelineStepCard({ step, index }: Props) {
  const [expanded, setExpanded] = useState(false);

  const statusIcon = {
    completed: <CheckCircle2 className="h-4 w-4 text-success" />,
    failed: <XCircle className="h-4 w-4 text-danger" />,
    running: <Loader2 className="h-4 w-4 text-primary animate-spin" />,
    waiting: <Clock className="h-4 w-4 text-text-muted" />,
  }[step.status];

  const dotColor = {
    completed: "border-success bg-success/10",
    failed: "border-danger bg-danger/10",
    running: "border-primary bg-primary-glow",
    waiting: "border-border-subtle bg-surface-raised",
  }[step.status];

  return (
    <div className="pipeline-step">
      <div className={`pipeline-step-dot flex items-center justify-center ${dotColor}`}>
        {statusIcon}
      </div>
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full text-left py-3 group"
      >
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <span className="text-xs font-mono text-text-muted">#{index}</span>
            <span className="text-sm font-medium text-text-primary capitalize">{step.action}</span>
          </div>
          <div className="flex items-center gap-2">
            {step.latencyMs !== undefined && (
              <span className="text-xs font-mono text-text-muted">{step.latencyMs}ms</span>
            )}
            {step.toolCall && (
              expanded
                ? <ChevronDown className="h-3.5 w-3.5 text-text-muted" />
                : <ChevronRight className="h-3.5 w-3.5 text-text-muted" />
            )}
          </div>
        </div>
        <p className="text-xs text-text-muted mt-0.5">
          {new Date(step.startedAt).toLocaleTimeString()}
          {step.completedAt && ` \u2192 ${new Date(step.completedAt).toLocaleTimeString()}`}
        </p>
      </button>
      {expanded && step.toolCall && (
        <div className="ml-6 mb-3 rounded-lg bg-[#0f172a] p-3 text-xs font-mono animate-scale-in">
          <p className="text-[#60a5fa] mb-1">Tool: {step.toolCall.name}</p>
          <p className="text-[#64748b] mb-1">Input:</p>
          <pre className="text-[#e2e8f0] overflow-x-auto whitespace-pre-wrap">{JSON.stringify(step.toolCall.input, null, 2)}</pre>
          {step.toolCall.output && (
            <>
              <p className="text-[#64748b] mt-2 mb-1">Output:</p>
              <pre className="text-[#86efac] overflow-x-auto whitespace-pre-wrap">
                {typeof step.toolCall.output === "string"
                  ? step.toolCall.output
                  : JSON.stringify(step.toolCall.output, null, 2)}
              </pre>
            </>
          )}
          {step.error && (
            <p className="text-[#f87171] mt-2">Error: {step.error}</p>
          )}
        </div>
      )}
    </div>
  );
}
