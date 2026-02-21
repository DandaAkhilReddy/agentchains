import { useState, useMemo } from "react";
import {
  Bot,
  Search,
  Eye,
  Power,
  PowerOff,
  ChevronDown,
  ChevronUp,
  Shield,
} from "lucide-react";
import Spinner from "../Spinner";
import EmptyState from "../EmptyState";
import { formatUSD } from "../../lib/format";

/**
 * Agent CRUD management panel for platform administrators.
 *
 * Displays a searchable table of agents with activate/deactivate controls
 * and an expandable detail view per row.
 */

export interface AdminAgent {
  agent_id: string;
  agent_name: string;
  status: string;
  agent_type?: string;
  trust_status: string;
  trust_tier: string;
  trust_score: number;
  money_received_usd: number;
  info_used_count: number;
  other_agents_served_count: number;
  data_served_bytes: number;
  created_at?: string;
  last_seen_at?: string;
}

interface AgentManagementProps {
  agents: AdminAgent[];
  total: number;
  page: number;
  pageSize: number;
  isLoading: boolean;
  onPageChange: (page: number) => void;
  onActivate: (agentId: string) => void;
  onDeactivate: (agentId: string) => void;
  onViewDetails?: (agentId: string) => void;
}

const TRUST_TIER_COLORS: Record<string, string> = {
  T0: "#64748b",
  T1: "#60a5fa",
  T2: "#a78bfa",
  T3: "#34d399",
};

const STATUS_COLORS: Record<string, string> = {
  active: "#34d399",
  inactive: "#64748b",
  suspended: "#f87171",
  restricted: "#fbbf24",
};

export default function AgentManagement({
  agents,
  total,
  page,
  pageSize,
  isLoading,
  onPageChange,
  onActivate,
  onDeactivate,
  onViewDetails,
}: AgentManagementProps) {
  const [searchQuery, setSearchQuery] = useState("");
  const [expandedId, setExpandedId] = useState<string | null>(null);

  const filteredAgents = useMemo(() => {
    if (!searchQuery.trim()) return agents;
    const q = searchQuery.toLowerCase();
    return agents.filter(
      (a) =>
        a.agent_name.toLowerCase().includes(q) ||
        a.agent_id.toLowerCase().includes(q) ||
        a.trust_status.toLowerCase().includes(q) ||
        a.status.toLowerCase().includes(q),
    );
  }, [agents, searchQuery]);

  const totalPages = Math.ceil(total / pageSize);

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-20 bg-[#141928] rounded-2xl border border-[rgba(255,255,255,0.06)]">
        <Spinner label="Loading agents..." />
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-[rgba(167,139,250,0.1)]">
            <Bot className="h-4 w-4 text-[#a78bfa]" />
          </div>
          <div>
            <h3 className="text-sm font-semibold text-[#e2e8f0]">
              Agent Management
            </h3>
            <p className="text-xs text-[#64748b]">
              {total} total agent{total !== 1 ? "s" : ""}
            </p>
          </div>
        </div>
      </div>

      {/* Search */}
      <div className="relative">
        <Search className="absolute left-3 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-[#64748b]" />
        <input
          type="text"
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          placeholder="Search agents by name, ID, or status..."
          className="w-full rounded-lg border border-[rgba(255,255,255,0.1)] bg-[#0d1220] py-2 pl-9 pr-4 text-sm text-[#e2e8f0] placeholder-[#475569] outline-none transition-colors focus:border-[#60a5fa]"
        />
      </div>

      {/* Table */}
      {filteredAgents.length === 0 ? (
        <EmptyState message="No agents match your search." />
      ) : (
        <div className="rounded-2xl border border-[rgba(255,255,255,0.06)] bg-[#141928] overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-[rgba(255,255,255,0.06)] bg-[#0d1220]">
                  <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-[#64748b]">
                    Agent
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-[#64748b]">
                    Status
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-[#64748b]">
                    Trust
                  </th>
                  <th className="px-4 py-3 text-right text-xs font-medium uppercase tracking-wider text-[#64748b]">
                    Revenue
                  </th>
                  <th className="px-4 py-3 text-right text-xs font-medium uppercase tracking-wider text-[#64748b]">
                    Served
                  </th>
                  <th className="px-4 py-3 text-center text-xs font-medium uppercase tracking-wider text-[#64748b]">
                    Actions
                  </th>
                </tr>
              </thead>
              <tbody>
                {filteredAgents.map((agent, idx) => {
                  const isExpanded = expandedId === agent.agent_id;
                  const statusColor =
                    STATUS_COLORS[agent.status] ?? "#64748b";
                  const tierColor =
                    TRUST_TIER_COLORS[agent.trust_tier] ?? "#64748b";

                  return (
                    <>
                      <tr
                        key={agent.agent_id}
                        className={`border-b border-[rgba(255,255,255,0.04)] transition-colors hover:bg-[rgba(96,165,250,0.04)] ${
                          idx % 2 === 1 ? "bg-[rgba(255,255,255,0.01)]" : ""
                        }`}
                      >
                        {/* Agent name + ID */}
                        <td className="px-4 py-3">
                          <div className="flex items-center gap-2">
                            <button
                              onClick={() =>
                                setExpandedId(
                                  isExpanded ? null : agent.agent_id,
                                )
                              }
                              className="text-[#64748b] transition-colors hover:text-[#e2e8f0]"
                            >
                              {isExpanded ? (
                                <ChevronUp className="h-3.5 w-3.5" />
                              ) : (
                                <ChevronDown className="h-3.5 w-3.5" />
                              )}
                            </button>
                            <div>
                              <p className="font-medium text-[#e2e8f0]">
                                {agent.agent_name}
                              </p>
                              <p className="text-[10px] font-mono text-[#475569]">
                                {agent.agent_id.slice(0, 12)}...
                              </p>
                            </div>
                          </div>
                        </td>

                        {/* Status */}
                        <td className="px-4 py-3">
                          <span
                            className="inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[10px] font-semibold uppercase"
                            style={{
                              backgroundColor: `${statusColor}15`,
                              color: statusColor,
                            }}
                          >
                            <span
                              className="h-1.5 w-1.5 rounded-full"
                              style={{ backgroundColor: statusColor }}
                            />
                            {agent.status}
                          </span>
                        </td>

                        {/* Trust */}
                        <td className="px-4 py-3">
                          <div className="flex items-center gap-2">
                            <Shield
                              className="h-3.5 w-3.5"
                              style={{ color: tierColor }}
                            />
                            <div>
                              <span
                                className="text-xs font-semibold"
                                style={{ color: tierColor }}
                              >
                                {agent.trust_tier}
                              </span>
                              <span className="ml-1 text-[10px] text-[#64748b]">
                                ({Math.round(agent.trust_score * 100)}%)
                              </span>
                            </div>
                          </div>
                        </td>

                        {/* Revenue */}
                        <td className="px-4 py-3 text-right text-[#34d399]">
                          {formatUSD(agent.money_received_usd)}
                        </td>

                        {/* Served */}
                        <td className="px-4 py-3 text-right text-[#94a3b8]">
                          {agent.other_agents_served_count}
                        </td>

                        {/* Actions */}
                        <td className="px-4 py-3">
                          <div className="flex items-center justify-center gap-1.5">
                            {onViewDetails && (
                              <button
                                onClick={() =>
                                  onViewDetails(agent.agent_id)
                                }
                                className="rounded p-1.5 text-[#64748b] transition-colors hover:bg-[rgba(255,255,255,0.04)] hover:text-[#60a5fa]"
                                title="View Details"
                              >
                                <Eye className="h-3.5 w-3.5" />
                              </button>
                            )}
                            {agent.status === "active" ? (
                              <button
                                onClick={() =>
                                  onDeactivate(agent.agent_id)
                                }
                                className="rounded p-1.5 text-[#64748b] transition-colors hover:bg-[rgba(248,113,113,0.1)] hover:text-[#f87171]"
                                title="Deactivate Agent"
                              >
                                <PowerOff className="h-3.5 w-3.5" />
                              </button>
                            ) : (
                              <button
                                onClick={() =>
                                  onActivate(agent.agent_id)
                                }
                                className="rounded p-1.5 text-[#64748b] transition-colors hover:bg-[rgba(52,211,153,0.1)] hover:text-[#34d399]"
                                title="Activate Agent"
                              >
                                <Power className="h-3.5 w-3.5" />
                              </button>
                            )}
                          </div>
                        </td>
                      </tr>

                      {/* Expanded details row */}
                      {isExpanded && (
                        <tr key={`${agent.agent_id}-details`}>
                          <td
                            colSpan={6}
                            className="border-b border-[rgba(255,255,255,0.04)] bg-[rgba(96,165,250,0.02)] px-6 py-4"
                          >
                            <div className="grid gap-4 md:grid-cols-4">
                              <div>
                                <p className="text-[10px] uppercase tracking-wider text-[#64748b]">
                                  Agent ID
                                </p>
                                <p className="mt-0.5 text-xs font-mono text-[#94a3b8]">
                                  {agent.agent_id}
                                </p>
                              </div>
                              <div>
                                <p className="text-[10px] uppercase tracking-wider text-[#64748b]">
                                  Trust Status
                                </p>
                                <p className="mt-0.5 text-xs text-[#e2e8f0]">
                                  {agent.trust_status}
                                </p>
                              </div>
                              <div>
                                <p className="text-[10px] uppercase tracking-wider text-[#64748b]">
                                  Info Used
                                </p>
                                <p className="mt-0.5 text-xs text-[#e2e8f0]">
                                  {agent.info_used_count.toLocaleString()}
                                </p>
                              </div>
                              <div>
                                <p className="text-[10px] uppercase tracking-wider text-[#64748b]">
                                  Data Served
                                </p>
                                <p className="mt-0.5 text-xs text-[#e2e8f0]">
                                  {(agent.data_served_bytes / 1024).toFixed(1)}{" "}
                                  KB
                                </p>
                              </div>
                            </div>
                          </td>
                        </tr>
                      )}
                    </>
                  );
                })}
              </tbody>
            </table>
          </div>

          {/* Pagination */}
          {totalPages > 1 && (
            <div className="flex items-center justify-between border-t border-[rgba(255,255,255,0.06)] px-4 py-3">
              <p className="text-xs text-[#64748b]">
                Page {page} of {totalPages} ({total} agents)
              </p>
              <div className="flex items-center gap-1">
                <button
                  onClick={() => onPageChange(page - 1)}
                  disabled={page <= 1}
                  className="rounded-lg border border-[rgba(255,255,255,0.1)] px-3 py-1 text-xs text-[#94a3b8] transition-colors hover:text-[#e2e8f0] disabled:opacity-40 disabled:cursor-not-allowed"
                >
                  Previous
                </button>
                <button
                  onClick={() => onPageChange(page + 1)}
                  disabled={page >= totalPages}
                  className="rounded-lg border border-[rgba(255,255,255,0.1)] px-3 py-1 text-xs text-[#94a3b8] transition-colors hover:text-[#e2e8f0] disabled:opacity-40 disabled:cursor-not-allowed"
                >
                  Next
                </button>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
