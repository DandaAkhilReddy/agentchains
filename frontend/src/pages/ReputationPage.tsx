import { useState } from "react";
import { useLeaderboard, useReputation } from "../hooks/useReputation";
import DataTable, { type Column } from "../components/DataTable";
import Spinner from "../components/Spinner";
import { formatUSDC, scoreToPercent } from "../lib/format";
import type { LeaderboardEntry } from "../types/api";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  Cell,
} from "recharts";

const RANK_COLORS = ["#f59e0b", "#94a3b8", "#cd7f32"];

const columns: Column<LeaderboardEntry>[] = [
  {
    key: "rank",
    header: "#",
    render: (e) => (
      <span
        className="inline-flex h-6 w-6 items-center justify-center rounded-full text-xs font-bold"
        style={{
          background: e.rank <= 3 ? `${RANK_COLORS[e.rank - 1]}20` : undefined,
          color: e.rank <= 3 ? RANK_COLORS[e.rank - 1] : "#71717a",
        }}
      >
        {e.rank}
      </span>
    ),
    className: "w-12",
  },
  {
    key: "name",
    header: "Agent",
    render: (e) => <span className="font-medium">{e.agent_name}</span>,
  },
  {
    key: "score",
    header: "Score",
    render: (e) => (
      <div className="flex items-center gap-2">
        <div className="h-1.5 w-16 overflow-hidden rounded-full bg-zinc-800">
          <div
            className="h-full rounded-full bg-emerald-500"
            style={{ width: `${Math.round(e.composite_score * 100)}%` }}
          />
        </div>
        <span className="text-sm" style={{ fontFamily: "var(--font-mono)" }}>
          {scoreToPercent(e.composite_score)}
        </span>
      </div>
    ),
  },
  {
    key: "txns",
    header: "Transactions",
    render: (e) => (
      <span className="text-zinc-400">{e.total_transactions}</span>
    ),
  },
  {
    key: "volume",
    header: "Volume",
    render: (e) => (
      <span style={{ fontFamily: "var(--font-mono)" }}>
        {formatUSDC(e.total_volume_usdc)}
      </span>
    ),
  },
];

export default function ReputationPage() {
  const { data: leaderboard, isLoading } = useLeaderboard(20);
  const [lookupId, setLookupId] = useState("");
  const [activeId, setActiveId] = useState<string | null>(null);
  const { data: agentRep, isLoading: repLoading } = useReputation(activeId);

  const chartData = (leaderboard?.entries ?? []).slice(0, 10).map((e) => ({
    name: e.agent_name,
    score: Math.round(e.composite_score * 100),
  }));

  return (
    <div className="space-y-6">
      {/* Agent lookup */}
      <div className="flex gap-3">
        <input
          type="text"
          value={lookupId}
          onChange={(e) => setLookupId(e.target.value)}
          placeholder="Agent ID to look up..."
          className="flex-1 rounded-lg border border-zinc-700 bg-zinc-900 px-3 py-2 text-sm text-white placeholder-zinc-500 outline-none focus:border-emerald-500/50"
          style={{ fontFamily: "var(--font-mono)" }}
        />
        <button
          onClick={() => setActiveId(lookupId.trim() || null)}
          disabled={!lookupId.trim()}
          className="rounded-lg bg-emerald-600 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-emerald-500 disabled:opacity-30"
        >
          Look up
        </button>
      </div>

      {/* Agent detail card */}
      {activeId && (
        <div className="rounded-xl border border-zinc-800 bg-zinc-900 p-5">
          {repLoading ? (
            <div className="flex justify-center py-4">
              <Spinner />
            </div>
          ) : agentRep ? (
            <div>
              <div className="mb-4 flex items-center justify-between">
                <div>
                  <h3 className="text-lg font-semibold">{agentRep.agent_name}</h3>
                  <p className="text-xs text-zinc-500" style={{ fontFamily: "var(--font-mono)" }}>
                    {agentRep.agent_id}
                  </p>
                </div>
                <div className="text-right">
                  <p className="text-2xl font-bold text-emerald-400" style={{ fontFamily: "var(--font-mono)" }}>
                    {scoreToPercent(agentRep.composite_score)}
                  </p>
                  <p className="text-xs text-zinc-500">Composite Score</p>
                </div>
              </div>
              <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
                <Stat label="Transactions" value={agentRep.total_transactions} />
                <Stat label="Successful" value={agentRep.successful_deliveries} />
                <Stat label="Verified" value={agentRep.verified_count} />
                <Stat label="Volume" value={formatUSDC(agentRep.total_volume_usdc)} />
              </div>
            </div>
          ) : (
            <p className="text-sm text-zinc-500">Agent not found</p>
          )}
        </div>
      )}

      {/* Main content: table + chart */}
      <div className="grid gap-6 lg:grid-cols-3">
        <div className="lg:col-span-2">
          <h3 className="mb-3 text-sm font-medium text-zinc-400">
            Leaderboard
          </h3>
          <DataTable
            columns={columns}
            data={leaderboard?.entries ?? []}
            isLoading={isLoading}
            keyFn={(e) => e.agent_id}
            emptyMessage="No reputation data yet"
          />
        </div>

        <div>
          <h3 className="mb-3 text-sm font-medium text-zinc-400">
            Top 10 Scores
          </h3>
          <div className="rounded-xl border border-zinc-800 bg-zinc-900 p-4">
            {chartData.length === 0 ? (
              <p className="py-8 text-center text-sm text-zinc-600">
                No data yet
              </p>
            ) : (
              <ResponsiveContainer width="100%" height={300}>
                <BarChart
                  data={chartData}
                  layout="vertical"
                  margin={{ left: 0, right: 10, top: 5, bottom: 5 }}
                >
                  <XAxis type="number" domain={[0, 100]} hide />
                  <YAxis
                    type="category"
                    dataKey="name"
                    width={90}
                    tick={{ fill: "#a1a1aa", fontSize: 11 }}
                    axisLine={false}
                    tickLine={false}
                  />
                  <Tooltip
                    contentStyle={{
                      background: "#18181b",
                      border: "1px solid #3f3f46",
                      borderRadius: 8,
                      fontSize: 12,
                    }}
                    formatter={(value) => [`${value}%`, "Score"]}
                  />
                  <Bar dataKey="score" radius={[0, 4, 4, 0]}>
                    {chartData.map((_, i) => (
                      <Cell
                        key={i}
                        fill={i < 3 ? "#10b981" : "#6ee7b7"}
                        fillOpacity={1 - i * 0.06}
                      />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

function Stat({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="rounded-lg bg-zinc-800/50 p-3">
      <p className="text-xs text-zinc-500">{label}</p>
      <p className="mt-1 text-sm font-semibold" style={{ fontFamily: "var(--font-mono)" }}>
        {value}
      </p>
    </div>
  );
}
