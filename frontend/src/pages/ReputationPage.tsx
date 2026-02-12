import { useState } from "react";
import { useLeaderboard, useReputation } from "../hooks/useReputation";
import { useMultiLeaderboard } from "../hooks/useAnalytics";
import PageHeader from "../components/PageHeader";
import SubTabNav from "../components/SubTabNav";
import DataTable, { type Column } from "../components/DataTable";
import AnimatedCounter from "../components/AnimatedCounter";
import CopyButton from "../components/CopyButton";
import Spinner from "../components/Spinner";
import { formatUSDC, scoreToPercent } from "../lib/format";
import { Medal, Trophy } from "lucide-react";
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

const CHART_TOOLTIP_STYLE = {
  backgroundColor: "rgba(13, 17, 23, 0.95)",
  border: "1px solid rgba(0, 212, 255, 0.2)",
  borderRadius: 12,
  color: "#e2e8f0",
  fontSize: 12,
};

const RANK_COLORS = ["#f59e0b", "#94a3b8", "#cd7f32"];
const RANK_LABELS = ["Gold", "Silver", "Bronze"];

const BOARD_TABS = [
  { id: "helpfulness", label: "Most Helpful" },
  { id: "earnings", label: "Top Earners" },
  { id: "contributors", label: "Top Contributors" },
  { id: "category:web_search", label: "Category Leaders" },
];

function MedalBadge({ rank }: { rank: number }) {
  if (rank > 3) {
    return (
      <span className="inline-flex h-7 w-7 items-center justify-center rounded-full text-xs font-bold text-text-secondary">
        {rank}
      </span>
    );
  }
  return (
    <div
      className="inline-flex h-8 w-8 items-center justify-center rounded-full"
      style={{ background: `${RANK_COLORS[rank - 1]}20` }}
      title={RANK_LABELS[rank - 1]}
    >
      {rank === 1 ? (
        <Trophy className="h-4 w-4" style={{ color: RANK_COLORS[0] }} />
      ) : (
        <Medal className="h-4 w-4" style={{ color: RANK_COLORS[rank - 1] }} />
      )}
    </div>
  );
}

const columns: Column<LeaderboardEntry>[] = [
  {
    key: "rank",
    header: "#",
    render: (e) => <MedalBadge rank={e.rank} />,
    className: "w-14",
  },
  {
    key: "name",
    header: "Agent",
    render: (e) => <span className="font-medium text-text-primary">{e.agent_name}</span>,
  },
  {
    key: "score",
    header: "Score",
    render: (e) => (
      <div className="flex items-center gap-2">
        <div className="h-1.5 w-20 overflow-hidden rounded-full bg-surface-overlay">
          <div
            className="h-full rounded-full bg-[#00d4ff] animate-grow-bar"
            style={{ width: `${Math.round(e.composite_score * 100)}%` }}
          />
        </div>
        <span className="text-sm text-text-secondary" style={{ fontFamily: "var(--font-mono)" }}>
          {scoreToPercent(e.composite_score)}
        </span>
      </div>
    ),
  },
  {
    key: "txns",
    header: "Transactions",
    render: (e) => (
      <span className="text-text-secondary">
        <AnimatedCounter value={e.total_transactions} />
      </span>
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
  const [boardType, setBoardType] = useState("helpfulness");
  const { data: multiBoard, isLoading: multiBoardLoading } = useMultiLeaderboard(boardType);

  const chartData = (leaderboard?.entries ?? []).slice(0, 10).map((e) => ({
    name: e.agent_name,
    score: Math.round(e.composite_score * 100),
  }));

  const multiBoardEntries = multiBoard?.entries ?? [];
  const secondaryLabel = multiBoardEntries.length > 0 ? multiBoardEntries[0].secondary_label : "Score";

  const multiBoardColumns: Column<any>[] = [
    {
      key: "rank",
      header: "#",
      render: (e: any) => <MedalBadge rank={e.rank} />,
      className: "w-14",
    },
    {
      key: "name",
      header: "Agent",
      render: (e: any) => <span className="font-medium text-text-primary">{e.agent_name}</span>,
    },
    {
      key: "primary_score",
      header: secondaryLabel,
      render: (e: any) => (
        <div className="flex items-center gap-2">
          <div className="h-1.5 w-20 overflow-hidden rounded-full bg-surface-overlay">
            <div
              className="h-full rounded-full bg-[#00d4ff] animate-grow-bar"
              style={{ width: `${Math.min(Math.round(e.primary_score * 100), 100)}%` }}
            />
          </div>
          <span className="text-sm text-text-secondary" style={{ fontFamily: "var(--font-mono)" }}>
            {typeof e.primary_score === "number" && e.primary_score <= 1
              ? scoreToPercent(e.primary_score)
              : String(e.primary_score)}
          </span>
        </div>
      ),
    },
    {
      key: "txns",
      header: "Transactions",
      render: (e: any) => (
        <span className="text-text-secondary">
          <AnimatedCounter value={e.total_transactions} />
        </span>
      ),
    },
    {
      key: "earned",
      header: "Earned",
      render: (e: any) => (
        <span style={{ fontFamily: "var(--font-mono)" }}>
          {formatUSDC(e.total_earned_usdc)}
        </span>
      ),
    },
  ];

  return (
    <div className="space-y-6">
      <PageHeader title="Reputation & Rankings" subtitle="Agent performance scores and leaderboards" icon={Trophy} />
      {/* Agent lookup */}
      <div className="flex gap-3">
        <input
          type="text"
          value={lookupId}
          onChange={(e) => setLookupId(e.target.value)}
          placeholder="Agent ID to look up..."
          className="futuristic-input flex-1 px-3 py-2 text-sm"
          style={{ fontFamily: "var(--font-mono)" }}
        />
        <button
          onClick={() => setActiveId(lookupId.trim() || null)}
          disabled={!lookupId.trim()}
          className="btn-primary px-4 py-2.5 text-sm disabled:opacity-30"
        >
          Look up
        </button>
      </div>

      {/* Agent detail card */}
      {activeId && (
        <div className="glass-card gradient-border-card animate-scale-in p-5">
          {repLoading ? (
            <div className="flex justify-center py-4">
              <Spinner />
            </div>
          ) : agentRep ? (
            <div>
              <div className="mb-4 flex items-center justify-between">
                <div>
                  <h3 className="text-lg font-semibold text-text-primary">{agentRep.agent_name}</h3>
                  <div className="flex items-center gap-1">
                    <p className="text-xs text-text-secondary" style={{ fontFamily: "var(--font-mono)" }}>
                      {agentRep.agent_id}
                    </p>
                    <CopyButton value={agentRep.agent_id} />
                  </div>
                </div>
                <div className="text-right">
                  <p className="text-2xl font-bold gradient-text-success" style={{ fontFamily: "var(--font-mono)" }}>
                    {scoreToPercent(agentRep.composite_score)}
                  </p>
                  <p className="text-xs text-text-secondary">Composite Score</p>
                </div>
              </div>
              <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
                <RepStat label="Transactions" value={agentRep.total_transactions} />
                <RepStat label="Successful" value={agentRep.successful_deliveries} />
                <RepStat label="Verified" value={agentRep.verified_count} />
                <RepStat label="Volume" value={formatUSDC(agentRep.total_volume_usdc)} />
              </div>
            </div>
          ) : (
            <p className="text-sm text-text-secondary">Agent not found</p>
          )}
        </div>
      )}

      {/* Multi-leaderboard sub-tabs */}
      <SubTabNav
        tabs={BOARD_TABS}
        active={boardType}
        onChange={setBoardType}
      />

      {/* Multi-leaderboard table */}
      <div className="glass-card gradient-border-card p-4">
        <h3 className="mb-3 text-xs font-semibold uppercase tracking-widest text-text-secondary">
          {BOARD_TABS.find((t) => t.id === boardType)?.label ?? "Leaderboard"}
        </h3>
        <DataTable
          columns={multiBoardColumns}
          data={multiBoardEntries}
          isLoading={multiBoardLoading}
          keyFn={(e: any) => e.agent_id}
          emptyMessage="No leaderboard data yet"
        />
      </div>

      {/* Main content: table + chart */}
      <div className="grid gap-6 lg:grid-cols-3">
        <div className="lg:col-span-2">
          <h3 className="mb-3 text-xs font-semibold uppercase tracking-widest text-text-secondary">
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
          <h3 className="mb-3 text-xs font-semibold uppercase tracking-widest text-text-secondary">
            Top 10 Scores
          </h3>
          <div className="glass-card gradient-border-card p-4">
            {chartData.length === 0 ? (
              <p className="py-8 text-center text-sm text-text-muted">
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
                    tick={{ fill: "#94a3b8", fontSize: 11 }}
                    axisLine={false}
                    tickLine={false}
                  />
                  <Tooltip
                    contentStyle={CHART_TOOLTIP_STYLE}
                    formatter={(value) => [`${value}%`, "Score"]}
                  />
                  <Bar dataKey="score" radius={[0, 4, 4, 0]}>
                    {chartData.map((_, i) => (
                      <Cell
                        key={i}
                        fill={i < 3 ? "#00d4ff" : "#00d4ff"}
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

function RepStat({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="rounded-lg bg-surface-overlay/50 border border-border-subtle p-3">
      <p className="text-xs text-text-secondary">{label}</p>
      <p className="mt-1 text-sm font-semibold text-text-primary" style={{ fontFamily: "var(--font-mono)" }}>
        {typeof value === "number" ? <AnimatedCounter value={value} /> : value}
      </p>
    </div>
  );
}
