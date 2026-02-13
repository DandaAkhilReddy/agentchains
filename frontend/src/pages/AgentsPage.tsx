import { useState } from "react";
import { useAgents } from "../hooks/useAgents";
import Badge, { agentTypeVariant, statusVariant } from "../components/Badge";
import CopyButton from "../components/CopyButton";
import PageHeader from "../components/PageHeader";
import Pagination from "../components/Pagination";
import ProgressRing from "../components/ProgressRing";
import { relativeTime, truncateId } from "../lib/format";
import { Bot, Search, Clock, CalendarDays, Cpu, Wifi, WifiOff } from "lucide-react";
import type { Agent } from "../types/api";

/* ------------------------------------------------------------------ */
/*  Avatar gradient pairs keyed by agent_type                         */
/* ------------------------------------------------------------------ */
const AVATAR_GRADIENTS: Record<string, string> = {
  seller: "from-[#60a5fa] to-[#a78bfa]",
  buyer: "from-[#34d399] to-[#60a5fa]",
  both: "from-[#fbbf24] to-[#f87171]",
};

/* ------------------------------------------------------------------ */
/*  Agent Card                                                        */
/* ------------------------------------------------------------------ */
function AgentCard({ agent }: { agent: Agent }) {
  const isOnline = agent.last_seen_at
    ? Date.now() - new Date(agent.last_seen_at).getTime() < 5 * 60 * 1000
    : false;

  const initial = agent.name.charAt(0).toUpperCase();
  const gradientCls = AVATAR_GRADIENTS[agent.agent_type] ?? AVATAR_GRADIENTS.seller;

  // Derive a deterministic "power score" from the agent's capabilities count (0-100)
  const powerScore = Math.min(agent.capabilities.length * 20, 100);

  return (
    <div
      className="group relative flex flex-col rounded-2xl border border-[rgba(255,255,255,0.06)] bg-[#141928] p-6 transition-all duration-300 hover:border-[rgba(96,165,250,0.3)] hover:shadow-[0_0_30px_rgba(96,165,250,0.08)] hover:-translate-y-1"
    >
      {/* ---- Top section: Avatar + name + id ---- */}
      <div className="mb-4 flex items-start gap-4">
        {/* Avatar */}
        <div className="relative flex-shrink-0">
          <div
            className={`flex h-14 w-14 items-center justify-center rounded-full bg-gradient-to-br ${gradientCls} text-xl font-bold text-white shadow-[0_0_20px_rgba(96,165,250,0.2)] transition-shadow duration-300 group-hover:shadow-[0_0_28px_rgba(96,165,250,0.35)]`}
          >
            {initial}
          </div>
          {/* Online indicator */}
          <div
            className={`absolute bottom-0.5 right-0.5 h-3.5 w-3.5 rounded-full border-2 border-[#141928] ${
              isOnline ? "bg-[#00ff88] pulse-dot shadow-[0_0_8px_rgba(0,255,136,0.6)]" : "bg-text-muted"
            }`}
            title={isOnline ? "Online" : "Offline"}
          />
        </div>

        {/* Name + ID */}
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2">
            <h4 className="truncate text-lg font-semibold text-[#e2e8f0]">
              {agent.name}
            </h4>
            {isOnline ? (
              <Wifi className="h-3.5 w-3.5 flex-shrink-0 text-[#00ff88]" />
            ) : (
              <WifiOff className="h-3.5 w-3.5 flex-shrink-0 text-[#64748b]" />
            )}
          </div>
          <div className="mt-1 flex items-center gap-1">
            <span className="font-mono text-xs text-[#64748b]">{truncateId(agent.id)}</span>
            <CopyButton value={agent.id} />
          </div>
        </div>

        {/* Power score ring */}
        {agent.capabilities.length > 0 && (
          <div className="flex-shrink-0 opacity-70 transition-opacity duration-300 group-hover:opacity-100">
            <ProgressRing
              value={powerScore}
              size={40}
              strokeWidth={3}
              color={powerScore >= 80 ? "green" : powerScore >= 40 ? "cyan" : "amber"}
              showLabel
            />
          </div>
        )}
      </div>

      {/* ---- Type + Status badges ---- */}
      <div className="mb-4 flex gap-2">
        <Badge label={agent.agent_type} variant={agentTypeVariant(agent.agent_type)} />
        <Badge label={agent.status} variant={statusVariant(agent.status)} />
      </div>

      {/* ---- Capabilities ---- */}
      {agent.capabilities.length > 0 && (
        <div className="mb-4 flex flex-wrap gap-1.5">
          {agent.capabilities.slice(0, 4).map((cap) => (
            <span
              key={cap}
              className="inline-flex items-center gap-1 rounded-full border border-[rgba(96,165,250,0.12)] bg-[rgba(96,165,250,0.06)] px-2.5 py-0.5 text-[11px] font-medium text-[#94a3b8] transition-colors duration-200 group-hover:border-[rgba(96,165,250,0.2)] group-hover:text-[#e2e8f0]"
            >
              <Cpu className="h-2.5 w-2.5" />
              {cap}
            </span>
          ))}
          {agent.capabilities.length > 4 && (
            <span className="inline-flex items-center rounded-full border border-[rgba(255,255,255,0.04)] bg-[rgba(255,255,255,0.03)] px-2.5 py-0.5 text-[11px] font-medium text-[#64748b]">
              +{agent.capabilities.length - 4}
            </span>
          )}
        </div>
      )}

      {/* ---- Footer ---- */}
      <div className="mt-auto flex items-center justify-between border-t border-[rgba(255,255,255,0.04)] pt-3 text-[11px] text-[#64748b]">
        <span className="inline-flex items-center gap-1">
          <Clock className="h-3 w-3" />
          {agent.last_seen_at ? `Seen ${relativeTime(agent.last_seen_at)}` : "Never seen"}
        </span>
        <span className="inline-flex items-center gap-1">
          <CalendarDays className="h-3 w-3" />
          Joined {relativeTime(agent.created_at)}
        </span>
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  Skeleton card — dark shimmer variant                              */
/* ------------------------------------------------------------------ */
function AgentSkeletonCard() {
  return (
    <div className="rounded-2xl border border-[rgba(255,255,255,0.06)] bg-[#141928] p-6 space-y-4">
      <div className="flex items-start gap-4">
        <div className="h-14 w-14 rounded-full bg-[#1a2035] animate-pulse" />
        <div className="flex-1 space-y-2 pt-1">
          <div className="h-5 w-2/3 rounded-lg bg-[#1a2035] animate-pulse" />
          <div className="h-3 w-1/3 rounded-lg bg-[#1a2035] animate-pulse" />
        </div>
      </div>
      <div className="flex gap-2">
        <div className="h-5 w-16 rounded-full bg-[#1a2035] animate-pulse" />
        <div className="h-5 w-16 rounded-full bg-[#1a2035] animate-pulse" />
      </div>
      <div className="flex gap-1.5">
        <div className="h-5 w-20 rounded-full bg-[#1a2035] animate-pulse" />
        <div className="h-5 w-20 rounded-full bg-[#1a2035] animate-pulse" />
        <div className="h-5 w-20 rounded-full bg-[#1a2035] animate-pulse" />
      </div>
      <div className="border-t border-[rgba(255,255,255,0.04)] pt-3 flex justify-between">
        <div className="h-3 w-24 rounded bg-[#1a2035] animate-pulse" />
        <div className="h-3 w-24 rounded bg-[#1a2035] animate-pulse" />
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  Agents Page                                                       */
/* ------------------------------------------------------------------ */
export default function AgentsPage() {
  const [typeFilter, setTypeFilter] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(1);

  const { data, isLoading } = useAgents({
    agent_type: typeFilter || undefined,
    status: statusFilter || undefined,
    page,
  });

  /* Client-side search filter (API doesn't support search param) */
  const filteredAgents = data?.agents.filter((a) => {
    if (!search) return true;
    const q = search.toLowerCase();
    return (
      a.name.toLowerCase().includes(q) ||
      a.id.toLowerCase().includes(q) ||
      a.capabilities.some((c) => c.toLowerCase().includes(q))
    );
  });

  const selectCls =
    "appearance-none rounded-xl bg-[#1a2035] border border-[rgba(255,255,255,0.06)] px-4 py-2.5 pr-8 text-sm text-[#e2e8f0] outline-none transition-all duration-200 focus:border-[rgba(96,165,250,0.5)] focus:shadow-[0_0_0_3px_rgba(96,165,250,0.1)] cursor-pointer";

  return (
    <div className="space-y-6">
      {/* ============ Header ============ */}
      <PageHeader
        title="Agent Registry"
        subtitle={
          data
            ? `${data.total} agent${data.total !== 1 ? "s" : ""} registered on the network`
            : "Browse and manage registered agents"
        }
        icon={Bot}
      />

      {/* ============ Filter bar ============ */}
      <div className="rounded-2xl border border-[rgba(255,255,255,0.06)] bg-[#141928] p-4">
        <div className="flex flex-wrap items-center gap-3">
          {/* Type filter */}
          <div className="relative">
            <select
              value={typeFilter}
              onChange={(e) => {
                setTypeFilter(e.target.value);
                setPage(1);
              }}
              className={selectCls}
            >
              <option value="">All Types</option>
              <option value="seller">Seller</option>
              <option value="buyer">Buyer</option>
              <option value="both">Both</option>
            </select>
            {/* Custom dropdown caret */}
            <div className="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 text-[#64748b]">
              <svg width="12" height="12" viewBox="0 0 12 12" fill="none">
                <path d="M3 4.5L6 7.5L9 4.5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
            </div>
          </div>

          {/* Status filter */}
          <div className="relative">
            <select
              value={statusFilter}
              onChange={(e) => {
                setStatusFilter(e.target.value);
                setPage(1);
              }}
              className={selectCls}
            >
              <option value="">All Status</option>
              <option value="active">Active</option>
              <option value="inactive">Inactive</option>
            </select>
            <div className="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 text-[#64748b]">
              <svg width="12" height="12" viewBox="0 0 12 12" fill="none">
                <path d="M3 4.5L6 7.5L9 4.5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
            </div>
          </div>

          {/* Search input */}
          <div className="relative flex-1 min-w-[200px]">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-[#64748b]" />
            <input
              type="text"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search agents by name, ID, or capability..."
              className="w-full rounded-xl border border-[rgba(255,255,255,0.06)] bg-[#1a2035] py-2.5 pl-10 pr-4 text-sm text-[#e2e8f0] placeholder-[#64748b] outline-none transition-all duration-200 focus:border-[rgba(96,165,250,0.5)] focus:shadow-[0_0_0_3px_rgba(96,165,250,0.1)]"
            />
          </div>

          {/* Agent count */}
          {data && (
            <span className="ml-auto flex items-center gap-2 whitespace-nowrap rounded-xl border border-[rgba(255,255,255,0.06)] bg-[#1a2035] px-4 py-2.5 text-sm font-medium text-[#94a3b8]">
              <Bot className="h-4 w-4 text-[#60a5fa]" />
              {data.total} agent{data.total !== 1 && "s"}
            </span>
          )}
        </div>
      </div>

      {/* ============ Card grid ============ */}
      {isLoading ? (
        <div className="grid gap-5 sm:grid-cols-2 xl:grid-cols-3">
          {Array.from({ length: 6 }).map((_, i) => (
            <AgentSkeletonCard key={i} />
          ))}
        </div>
      ) : !data || !filteredAgents || filteredAgents.length === 0 ? (
        /* ---------- Empty state ---------- */
        <div className="flex flex-col items-center rounded-2xl border border-[rgba(255,255,255,0.06)] bg-[#141928] py-24">
          <div className="mb-4 flex h-16 w-16 items-center justify-center rounded-2xl bg-[rgba(96,165,250,0.08)] shadow-[0_0_24px_rgba(96,165,250,0.1)]">
            <Bot className="h-8 w-8 text-[#60a5fa]" />
          </div>
          <p className="text-base font-medium text-[#94a3b8]">No agents registered</p>
          <p className="mt-1 text-sm text-[#64748b]">
            {search
              ? "Try adjusting your search query"
              : "Agents will appear here once they register on the network"}
          </p>
        </div>
      ) : (
        <div className="grid gap-5 sm:grid-cols-2 xl:grid-cols-3">
          {filteredAgents.map((agent) => (
            <AgentCard key={agent.id} agent={agent} />
          ))}
        </div>
      )}

      {/* ============ Pagination ============ */}
      {data && data.total > 20 && (
        <Pagination
          page={page}
          totalPages={Math.ceil(data.total / 20)}
          onPageChange={setPage}
        />
      )}
    </div>
  );
}
