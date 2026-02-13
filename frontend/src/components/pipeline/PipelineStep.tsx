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
    completed: <CheckCircle2 className="h-4 w-4 text-[#34d399]" />,
    failed: <XCircle className="h-4 w-4 text-[#f87171]" />,
    running: <Loader2 className="h-4 w-4 text-[#60a5fa] animate-spin" />,
    waiting: <Clock className="h-4 w-4 text-[#64748b]" />,
  }[step.status];

  const dotColor = {
    completed: "border-[#34d399] bg-[rgba(52,211,153,0.1)]",
    failed: "border-[#f87171] bg-[rgba(248,113,113,0.1)]",
    running: "border-[#60a5fa] bg-[rgba(96,165,250,0.1)] shadow-[0_0_8px_rgba(96,165,250,0.3)]",
    waiting: "border-[rgba(255,255,255,0.06)] bg-[#1a2035]",
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
            <span className="inline-flex items-center justify-center h-5 w-5 rounded-md bg-[rgba(255,255,255,0.04)] text-[10px] font-mono font-bold text-[#64748b]">
              {index}
            </span>
            <span className="text-sm font-medium text-[#e2e8f0] capitalize group-hover:text-[#60a5fa] transition-colors">
              {step.action}
            </span>
          </div>
          <div className="flex items-center gap-2">
            {step.latencyMs !== undefined && (
              <span className="text-xs font-mono text-[#64748b]">{step.latencyMs}ms</span>
            )}
            {step.toolCall && (
              expanded
                ? <ChevronDown className="h-3.5 w-3.5 text-[#64748b]" />
                : <ChevronRight className="h-3.5 w-3.5 text-[#64748b]" />
            )}
          </div>
        </div>
        <p className="text-xs text-[#64748b] mt-0.5 ml-7">
          {new Date(step.startedAt).toLocaleTimeString()}
          {step.completedAt && ` \u2192 ${new Date(step.completedAt).toLocaleTimeString()}`}
        </p>
      </button>
      {expanded && step.toolCall && (
        <div className="ml-7 mb-3 rounded-xl border border-[rgba(255,255,255,0.06)] bg-[#0a0e1a] p-4 text-xs font-mono animate-scale-in">
          <p className="text-[#60a5fa] mb-2 font-semibold">
            Tool: <span className="text-[#a78bfa]">{step.toolCall.name}</span>
          </p>
          <div className="mb-2">
            <p className="text-[10px] font-bold uppercase tracking-wider text-[#64748b] mb-1">Input</p>
            <pre className="text-[#e2e8f0] overflow-x-auto whitespace-pre-wrap rounded-lg bg-[rgba(255,255,255,0.02)] p-2">
              {JSON.stringify(step.toolCall.input, null, 2)}
            </pre>
          </div>
          {step.toolCall.output != null && (
            <div className="mt-3">
              <p className="text-[10px] font-bold uppercase tracking-wider text-[#64748b] mb-1">Output</p>
              <pre className="text-[#34d399] overflow-x-auto whitespace-pre-wrap rounded-lg bg-[rgba(255,255,255,0.02)] p-2">
                {typeof step.toolCall.output === "string"
                  ? step.toolCall.output
                  : JSON.stringify(step.toolCall.output, null, 2)}
              </pre>
            </div>
          )}
          {step.error && (
            <div className="mt-3 rounded-lg bg-[rgba(248,113,113,0.06)] border border-[rgba(248,113,113,0.15)] p-2">
              <p className="text-[#f87171]">Error: {step.error}</p>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
