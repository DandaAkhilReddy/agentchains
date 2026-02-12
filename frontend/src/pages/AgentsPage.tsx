import { useState } from "react";
import { useAgents } from "../hooks/useAgents";
import Badge, { agentTypeVariant, statusVariant } from "../components/Badge";
import { SkeletonCard } from "../components/Skeleton";
import CopyButton from "../components/CopyButton";
import PageHeader from "../components/PageHeader";
import Pagination from "../components/Pagination";
import { relativeTime, truncateId } from "../lib/format";
import { Bot } from "lucide-react";
import type { Agent } from "../types/api";

function AgentCard({ agent }: { agent: Agent }) {
  const isOnline = agent.last_seen_at
    ? Date.now() - new Date(agent.last_seen_at).getTime() < 5 * 60 * 1000
    : false;

  return (
    <div className="glass-card gradient-border-card glow-hover animate-scale-in p-5">
      {/* Header */}
      <div className="mb-3 flex items-start gap-3">
        <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-gradient-to-br from-[rgba(59,130,246,0.08)] to-[rgba(139,92,246,0.08)]">
          <Bot className="h-5 w-5 text-primary" />
        </div>
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2">
            <h4 className="truncate text-sm font-medium text-text-primary">{agent.name}</h4>
            <div
              className={`h-2 w-2 flex-shrink-0 rounded-full ${
                isOnline ? "bg-primary pulse-dot" : "bg-text-muted"
              }`}
              title={isOnline ? "Online" : "Offline"}
            />
          </div>
          <div className="flex items-center gap-1 text-xs text-text-secondary">
            <span style={{ fontFamily: "var(--font-mono)" }}>{truncateId(agent.id)}</span>
            <CopyButton value={agent.id} />
          </div>
        </div>
      </div>

      {/* Type + Status */}
      <div className="mb-3 flex gap-2">
        <Badge label={agent.agent_type} variant={agentTypeVariant(agent.agent_type)} />
        <Badge label={agent.status} variant={statusVariant(agent.status)} />
      </div>

      {/* Capabilities */}
      {agent.capabilities.length > 0 && (
        <div className="mb-3 flex flex-wrap gap-1">
          {agent.capabilities.slice(0, 4).map((cap) => (
            <span
              key={cap}
              className="rounded-full bg-primary-glow px-2 py-0.5 text-[10px] text-text-secondary border border-[rgba(59,130,246,0.12)]"
            >
              {cap}
            </span>
          ))}
          {agent.capabilities.length > 4 && (
            <span className="text-[10px] text-text-muted">
              +{agent.capabilities.length - 4}
            </span>
          )}
        </div>
      )}

      {/* Footer */}
      <div className="flex items-center justify-between text-[11px] text-text-muted">
        <span>
          {agent.last_seen_at ? `Seen ${relativeTime(agent.last_seen_at)}` : "Never seen"}
        </span>
        <span>Joined {relativeTime(agent.created_at)}</span>
      </div>
    </div>
  );
}

export default function AgentsPage() {
  const [typeFilter, setTypeFilter] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [page, setPage] = useState(1);

  const { data, isLoading } = useAgents({
    agent_type: typeFilter || undefined,
    status: statusFilter || undefined,
    page,
  });

  return (
    <div className="space-y-4">
      <PageHeader title="Agent Registry" subtitle="Browse and manage registered agents" icon={Bot} />
      {/* Filters */}
      <div className="flex flex-wrap gap-3">
        <select
          value={typeFilter}
          onChange={(e) => { setTypeFilter(e.target.value); setPage(1); }}
          className="futuristic-select px-3 py-2 text-sm"
        >
          <option value="">All Types</option>
          <option value="seller">Seller</option>
          <option value="buyer">Buyer</option>
          <option value="both">Both</option>
        </select>
        <select
          value={statusFilter}
          onChange={(e) => { setStatusFilter(e.target.value); setPage(1); }}
          className="futuristic-select px-3 py-2 text-sm"
        >
          <option value="">All Status</option>
          <option value="active">Active</option>
          <option value="inactive">Inactive</option>
        </select>
        {data && (
          <span className="ml-auto self-center text-sm text-text-secondary">
            {data.total} agent{data.total !== 1 && "s"}
          </span>
        )}
      </div>

      {/* Card grid */}
      {isLoading ? (
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
          {Array.from({ length: 6 }).map((_, i) => (
            <SkeletonCard key={i} />
          ))}
        </div>
      ) : !data || data.agents.length === 0 ? (
        <div className="flex flex-col items-center py-20 text-text-secondary">
          <Bot className="mb-3 h-8 w-8 text-text-muted" />
          <p className="text-sm">No agents registered</p>
        </div>
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
          {data.agents.map((agent) => (
            <AgentCard key={agent.id} agent={agent} />
          ))}
        </div>
      )}

      {/* Pagination */}
      {data && data.total > 20 && (
        <Pagination page={page} totalPages={Math.ceil(data.total / 20)} onPageChange={setPage} />
      )}
    </div>
  );
}
