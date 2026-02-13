import { Bot, Activity, AlertCircle } from "lucide-react";
import type { AgentExecution } from "../../types/api";

interface Props {
  executions: AgentExecution[];
  selectedId: string | null;
  onSelect: (id: string) => void;
}

export default function AgentPipelineList({ executions, selectedId, onSelect }: Props) {
  if (executions.length === 0) {
    return (
      <div className="rounded-2xl border border-[rgba(255,255,255,0.06)] bg-[#141928] p-6 text-center">
        <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-2xl bg-[rgba(96,165,250,0.08)] mb-3">
          <Bot className="h-6 w-6 text-[#64748b]" />
        </div>
        <p className="text-sm font-semibold text-[#94a3b8]">No agent activity yet</p>
        <p className="text-xs text-[#64748b] mt-1">
          Agent executions will appear here in real-time as marketplace events flow in via WebSocket.
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-2">
      <p className="text-[10px] font-bold uppercase tracking-widest text-[#64748b] px-1 mb-1">
        Active Agents ({executions.length})
      </p>
      {executions.map((exec) => {
        const isSelected = exec.agentId === selectedId;
        const statusColor =
          exec.status === "active"
            ? "bg-[#34d399]"
            : exec.status === "error"
              ? "bg-[#f87171]"
              : "bg-[#64748b]";
        const ago = getRelativeTime(exec.lastActivityAt);
        return (
          <button
            key={exec.agentId}
            onClick={() => onSelect(exec.agentId)}
            className={`w-full text-left rounded-xl p-3 transition-all duration-200 border ${
              isSelected
                ? "bg-[#1a2035] border-[rgba(96,165,250,0.3)] shadow-[0_0_16px_rgba(96,165,250,0.08)]"
                : "bg-[#141928] border-[rgba(255,255,255,0.06)] hover:border-[rgba(96,165,250,0.15)] hover:bg-[#1a2035]"
            }`}
          >
            <div className="flex items-center gap-3">
              <div className="relative">
                <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-[rgba(96,165,250,0.1)]">
                  <Bot className="h-4 w-4 text-[#60a5fa]" />
                </div>
                <span
                  className={`absolute -bottom-0.5 -right-0.5 h-2.5 w-2.5 rounded-full border-2 border-[#141928] ${statusColor} ${exec.status === "active" ? "animate-pulse" : ""}`}
                />
              </div>
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium text-[#e2e8f0] truncate">{exec.agentName}</p>
                <div className="flex items-center gap-2 text-xs text-[#64748b]">
                  <span>{exec.steps.length} steps</span>
                  <span>&middot;</span>
                  <span>{ago}</span>
                </div>
              </div>
              {exec.status === "active" && (
                <Activity className="h-3.5 w-3.5 text-[#34d399] shrink-0" />
              )}
              {exec.status === "error" && (
                <AlertCircle className="h-3.5 w-3.5 text-[#f87171] shrink-0" />
              )}
            </div>
          </button>
        );
      })}
    </div>
  );
}

function getRelativeTime(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime();
  if (diff < 60000) return "just now";
  if (diff < 3600000) return `${Math.floor(diff / 60000)}m ago`;
  if (diff < 86400000) return `${Math.floor(diff / 3600000)}h ago`;
  return `${Math.floor(diff / 86400000)}d ago`;
}
