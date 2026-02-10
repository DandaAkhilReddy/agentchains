import { useState } from "react";
import { useAgents } from "../hooks/useAgents";
import DataTable, { type Column } from "../components/DataTable";
import Badge, { agentTypeVariant, statusVariant } from "../components/Badge";
import { relativeTime } from "../lib/format";
import type { Agent } from "../types/api";

const columns: Column<Agent>[] = [
  {
    key: "name",
    header: "Name",
    render: (a) => <span className="font-medium">{a.name}</span>,
  },
  {
    key: "type",
    header: "Type",
    render: (a) => (
      <Badge label={a.agent_type} variant={agentTypeVariant(a.agent_type)} />
    ),
  },
  {
    key: "status",
    header: "Status",
    render: (a) => (
      <Badge label={a.status} variant={statusVariant(a.status)} />
    ),
  },
  {
    key: "capabilities",
    header: "Capabilities",
    render: (a) => (
      <span className="text-zinc-400">
        {a.capabilities.slice(0, 3).join(", ")}
        {a.capabilities.length > 3 && ` +${a.capabilities.length - 3}`}
      </span>
    ),
  },
  {
    key: "last_seen",
    header: "Last Seen",
    render: (a) => (
      <span className="text-zinc-500">{relativeTime(a.last_seen_at)}</span>
    ),
  },
  {
    key: "created",
    header: "Registered",
    render: (a) => (
      <span className="text-zinc-500">{relativeTime(a.created_at)}</span>
    ),
  },
];

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
      {/* Filters */}
      <div className="flex flex-wrap gap-3">
        <select
          value={typeFilter}
          onChange={(e) => { setTypeFilter(e.target.value); setPage(1); }}
          className="rounded-lg border border-zinc-700 bg-zinc-900 px-3 py-2 text-sm text-white outline-none"
        >
          <option value="">All Types</option>
          <option value="seller">Seller</option>
          <option value="buyer">Buyer</option>
          <option value="both">Both</option>
        </select>
        <select
          value={statusFilter}
          onChange={(e) => { setStatusFilter(e.target.value); setPage(1); }}
          className="rounded-lg border border-zinc-700 bg-zinc-900 px-3 py-2 text-sm text-white outline-none"
        >
          <option value="">All Status</option>
          <option value="active">Active</option>
          <option value="inactive">Inactive</option>
        </select>
      </div>

      <DataTable
        columns={columns}
        data={data?.agents ?? []}
        isLoading={isLoading}
        keyFn={(a) => a.id}
        emptyMessage="No agents registered"
      />

      {/* Pagination */}
      {data && data.total > 20 && (
        <div className="flex items-center justify-between">
          <span className="text-sm text-zinc-500">
            {data.total} agent{data.total !== 1 && "s"}
          </span>
          <div className="flex gap-2">
            <button
              disabled={page <= 1}
              onClick={() => setPage((p) => p - 1)}
              className="rounded-lg border border-zinc-700 px-3 py-1.5 text-sm text-zinc-400 transition-colors hover:bg-zinc-800 disabled:opacity-30"
            >
              Prev
            </button>
            <button
              disabled={page * 20 >= data.total}
              onClick={() => setPage((p) => p + 1)}
              className="rounded-lg border border-zinc-700 px-3 py-1.5 text-sm text-zinc-400 transition-colors hover:bg-zinc-800 disabled:opacity-30"
            >
              Next
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
