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
      <div className="glass-card p-6 text-center">
        <Bot className="mx-auto h-10 w-10 text-text-muted mb-3" />
        <p className="text-sm font-medium text-text-secondary">No agent activity yet</p>
        <p className="text-xs text-text-muted mt-1">
          Agent executions will appear here in real-time as marketplace events flow in via WebSocket.
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-2">
      <p className="text-xs font-semibold uppercase tracking-widest text-text-muted px-1">
        Active Agents ({executions.length})
      </p>
      {executions.map((exec) => {
        const isSelected = exec.agentId === selectedId;
        const statusColor = exec.status === "active" ? "bg-success" : exec.status === "error" ? "bg-danger" : "bg-text-muted";
        const ago = getRelativeTime(exec.lastActivityAt);
        return (
          <button
            key={exec.agentId}
            onClick={() => onSelect(exec.agentId)}
            className={`w-full text-left glass-card-subtle p-3 rounded-xl transition-all duration-200 ${
              isSelected
                ? "border-primary/30 shadow-[0_0_12px_rgba(59,130,246,0.08)]"
                : "hover:border-primary/15"
            }`}
          >
            <div className="flex items-center gap-3">
              <div className="relative">
                <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-primary-glow">
                  <Bot className="h-4 w-4 text-primary" />
                </div>
                <span className={`absolute -bottom-0.5 -right-0.5 h-2.5 w-2.5 rounded-full border-2 border-white ${statusColor} ${exec.status === "active" ? "animate-pulse" : ""}`} />
              </div>
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium text-text-primary truncate">{exec.agentName}</p>
                <div className="flex items-center gap-2 text-xs text-text-muted">
                  <span>{exec.steps.length} steps</span>
                  <span>&middot;</span>
                  <span>{ago}</span>
                </div>
              </div>
              {exec.status === "active" && (
                <Activity className="h-3.5 w-3.5 text-success shrink-0" />
              )}
              {exec.status === "error" && (
                <AlertCircle className="h-3.5 w-3.5 text-danger shrink-0" />
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
