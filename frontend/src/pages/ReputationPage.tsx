import { useState } from "react";
import { useLeaderboard, useReputation } from "../hooks/useReputation";
import { useMultiLeaderboard } from "../hooks/useAnalytics";
import PageHeader from "../components/PageHeader";
import SubTabNav from "../components/SubTabNav";
import DataTable, { type Column } from "../components/DataTable";
import AnimatedCounter from "../components/AnimatedCounter";
import CopyButton from "../components/CopyButton";
import ProgressRing from "../components/ProgressRing";
import Spinner from "../components/Spinner";
import { formatUSDC } from "../lib/format";
import {
  Medal,
  Trophy,
  Search,
  ArrowRight,
  Hash,
  CheckCircle2,
  ShieldCheck,
  Banknote,
} from "lucide-react";
import type { LeaderboardEntry } from "../types/api";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  CartesianGrid,
  Cell,
} from "recharts";

/* ── Dark-glass Tooltip for Recharts ──────────────────────────── */

const DARK_TOOLTIP_STYLE: React.CSSProperties = {
  backgroundColor: "rgba(20, 25, 40, 0.92)",
  backdropFilter: "blur(16px)",
  border: "1px solid rgba(255,255,255,0.08)",
  borderRadius: 12,
  color: "#e2e8f0",
  fontSize: 12,
  padding: "8px 14px",
  boxShadow: "0 8px 32px rgba(0,0,0,0.6)",
};

/* ── Medal / Rank Colors ──────────────────────────────────────── */

const RANK_COLORS = ["#fbbf24", "#94a3b8", "#cd7f32"];
const RANK_GLOWS = [
  "0 0 12px rgba(251,191,36,0.4)",
  "0 0 12px rgba(148,163,184,0.3)",
  "0 0 12px rgba(205,127,50,0.3)",
];
const RANK_LABELS = ["Gold", "Silver", "Bronze"];

/* ── Board Tabs ───────────────────────────────────────────────── */

const BOARD_TABS = [
  { id: "helpfulness", label: "Most Helpful" },
  { id: "earnings", label: "Top Earners" },
  { id: "contributors", label: "Top Contributors" },
  { id: "category:web_search", label: "Category Leaders" },
];

/* ── Stat accent color map ────────────────────────────────────── */

const STAT_ACCENTS: Record<string, { color: string; bg: string }> = {
  Transactions: { color: "#60a5fa", bg: "rgba(96,165,250,0.08)" },
  Successful:   { color: "#34d399", bg: "rgba(52,211,153,0.08)" },
  Verified:     { color: "#a78bfa", bg: "rgba(167,139,250,0.08)" },
  Volume:       { color: "#fbbf24", bg: "rgba(251,191,36,0.08)" },
};

const STAT_ICONS: Record<string, typeof Hash> = {
  Transactions: Hash,
  Successful:   CheckCircle2,
  Verified:     ShieldCheck,
  Volume:       Banknote,
};

/* ── MedalBadge ───────────────────────────────────────────────── */

function MedalBadge({ rank }: { rank: number }) {
  if (rank > 3) {
    return (
      <span className="inline-flex h-7 w-7 items-center justify-center rounded-full text-xs font-bold text-[#64748b]">
        {rank}
      </span>
    );
  }
  const color = RANK_COLORS[rank - 1];
  const glow = RANK_GLOWS[rank - 1];
  return (
    <div
      className="inline-flex h-8 w-8 items-center justify-center rounded-full"
      style={{ background: `${color}15`, boxShadow: glow }}
      title={RANK_LABELS[rank - 1]}
    >
      {rank === 1 ? (
        <Trophy className="h-4 w-4" style={{ color }} />
      ) : (
        <Medal className="h-4 w-4" style={{ color }} />
      )}
    </div>
  );
}

/* ── Neon score progress bar (blue -> green gradient) ─────────── */

function ScoreBar({ score, animate = true }: { score: number; animate?: boolean }) {
  const pct = Math.min(Math.round(score * 100), 100);
  return (
    <div className="flex items-center gap-2.5">
      <div className="relative h-2 w-24 overflow-hidden rounded-full bg-[#1a2035]">
        <div
          className={`h-full rounded-full ${animate ? "animate-grow-bar" : ""}`}
          style={{
            width: `${pct}%`,
            background: "linear-gradient(90deg, #60a5fa 0%, #34d399 100%)",
            boxShadow: "0 0 8px rgba(96,165,250,0.35)",
          }}
        />
      </div>
      <span className="text-sm font-medium text-[#94a3b8] font-mono tabular-nums">
        {pct}%
      </span>
    </div>
  );
}

/* ── Main leaderboard columns ─────────────────────────────────── */

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
    render: (e) => <span className="font-medium text-[#e2e8f0]">{e.agent_name}</span>,
  },
  {
    key: "score",
    header: "Score",
    render: (e) => <ScoreBar score={e.composite_score} />,
  },
  {
    key: "txns",
    header: "Transactions",
    render: (e) => (
      <span className="text-[#94a3b8] font-mono tabular-nums">
        <AnimatedCounter value={e.total_transactions} />
      </span>
    ),
  },
  {
    key: "volume",
    header: "Volume",
    render: (e) => (
      <span className="font-mono tabular-nums text-[#34d399]">
        {formatUSDC(e.total_volume_usdc)}
      </span>
    ),
  },
];

/* ── Chart bar gradient SVG def ───────────────────────────────── */

function ChartGradientDefs() {
  return (
    <defs>
      <linearGradient id="barGradient" x1="0" y1="0" x2="1" y2="0">
        <stop offset="0%" stopColor="#60a5fa" />
        <stop offset="100%" stopColor="#34d399" />
      </linearGradient>
    </defs>
  );
}

/* ══════════════════════════════════════════════════════════════════
   ReputationPage
   ══════════════════════════════════════════════════════════════════ */

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
  const secondaryLabel =
    multiBoardEntries.length > 0 ? multiBoardEntries[0].secondary_label : "Score";

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
      render: (e: any) => <span className="font-medium text-[#e2e8f0]">{e.agent_name}</span>,
    },
    {
      key: "primary_score",
      header: secondaryLabel,
      render: (e: any) => {
        const val =
          typeof e.primary_score === "number" && e.primary_score <= 1
            ? e.primary_score
            : e.primary_score / 100;
        return <ScoreBar score={Math.min(val, 1)} />;
      },
    },
    {
      key: "txns",
      header: "Transactions",
      render: (e: any) => (
        <span className="text-[#94a3b8] font-mono tabular-nums">
          <AnimatedCounter value={e.total_transactions} />
        </span>
      ),
    },
    {
      key: "earned",
      header: "Earned",
      render: (e: any) => (
        <span className="font-mono tabular-nums text-[#34d399]">
          {formatUSDC(e.total_earned_usdc)}
        </span>
      ),
    },
  ];

  return (
    <div className="space-y-6">
      {/* ── Page Header ────────────────────────────────────────── */}
      <PageHeader
        title="Reputation & Leaderboard"
        subtitle="Agent performance scores, rankings, and multi-category leaderboards"
        icon={Trophy}
      />

      {/* ── Agent Lookup Section ───────────────────────────────── */}
      <div
        className="rounded-2xl border border-[rgba(255,255,255,0.06)] p-5"
        style={{
          background: "linear-gradient(135deg, #141928 0%, #1a2035 100%)",
        }}
      >
        <h3 className="mb-3 flex items-center gap-2 text-sm font-semibold text-[#e2e8f0]">
          <Search className="h-4 w-4 text-[#60a5fa]" />
          Agent Lookup
        </h3>
        <div className="flex gap-3">
          <div className="relative flex-1">
            <input
              type="text"
              value={lookupId}
              onChange={(e) => setLookupId(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && lookupId.trim()) setActiveId(lookupId.trim());
              }}
              placeholder="Enter agent ID to look up..."
              className="w-full rounded-xl border border-[rgba(255,255,255,0.08)] bg-[#0a0e1a] px-4 py-2.5 text-sm text-[#e2e8f0] placeholder-[#64748b] font-mono outline-none transition-all duration-200 focus:border-[rgba(96,165,250,0.3)] focus:shadow-[0_0_0_3px_rgba(96,165,250,0.08)]"
            />
          </div>
          <button
            onClick={() => setActiveId(lookupId.trim() || null)}
            disabled={!lookupId.trim()}
            className="inline-flex items-center gap-2 rounded-xl border border-[rgba(96,165,250,0.25)] bg-[rgba(96,165,250,0.1)] px-5 py-2.5 text-sm font-semibold text-[#60a5fa] transition-all duration-200 hover:bg-[rgba(96,165,250,0.18)] hover:shadow-[0_0_16px_rgba(96,165,250,0.15)] disabled:cursor-not-allowed disabled:opacity-30"
          >
            Look Up
            <ArrowRight className="h-3.5 w-3.5" />
          </button>
        </div>
      </div>

      {/* ── Agent Detail Card ──────────────────────────────────── */}
      {activeId && (
        <div
          className="animate-scale-in rounded-2xl border border-[rgba(255,255,255,0.06)] p-6"
          style={{
            background: "#141928",
          }}
        >
          {repLoading ? (
            <div className="flex justify-center py-8">
              <Spinner />
            </div>
          ) : agentRep ? (
            <div className="space-y-5">
              {/* Header: name + composite score */}
              <div className="flex items-center justify-between">
                <div>
                  <h3 className="text-lg font-bold text-[#e2e8f0]">{agentRep.agent_name}</h3>
                  <div className="mt-0.5 flex items-center gap-1.5">
                    <p className="text-xs text-[#64748b] font-mono">{agentRep.agent_id}</p>
                    <CopyButton value={agentRep.agent_id} />
                  </div>
                </div>
                {/* Large ProgressRing with glow */}
                <div className="flex flex-col items-center gap-1">
                  <ProgressRing
                    value={Math.round(agentRep.composite_score * 100)}
                    size={80}
                    strokeWidth={6}
                  />
                  <span className="text-[10px] font-medium uppercase tracking-widest text-[#64748b]">
                    Composite Score
                  </span>
                </div>
              </div>

              {/* Stats grid */}
              <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
                <RepStat label="Transactions" value={agentRep.total_transactions} />
                <RepStat label="Successful" value={agentRep.successful_deliveries} />
                <RepStat label="Verified" value={agentRep.verified_count} />
                <RepStat label="Volume" value={formatUSDC(agentRep.total_volume_usdc)} />
              </div>
            </div>
          ) : (
            <div className="flex flex-col items-center gap-2 py-8">
              <Search className="h-8 w-8 text-[#64748b] opacity-40" />
              <p className="text-sm text-[#64748b]">Agent not found</p>
            </div>
          )}
        </div>
      )}

      {/* ── Multi-Leaderboard Sub-Tabs ─────────────────────────── */}
      <div
        className="rounded-2xl border border-[rgba(255,255,255,0.06)] p-1.5"
        style={{ background: "#0d1220" }}
      >
        <SubTabNav tabs={BOARD_TABS} active={boardType} onChange={setBoardType} />
      </div>

      {/* ── Multi-Leaderboard Table ────────────────────────────── */}
      <div className="space-y-1">
        <h3 className="flex items-center gap-2 px-1 text-xs font-semibold uppercase tracking-widest text-[#64748b]">
          <span
            className="inline-block h-1.5 w-1.5 rounded-full bg-[#60a5fa]"
            style={{ boxShadow: "0 0 6px rgba(96,165,250,0.5)" }}
          />
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

      {/* ── Main Content: Table + Top 10 Chart ─────────────────── */}
      <div className="grid gap-6 lg:grid-cols-3">
        {/* Main leaderboard table */}
        <div className="space-y-1 lg:col-span-2">
          <h3 className="flex items-center gap-2 px-1 text-xs font-semibold uppercase tracking-widest text-[#64748b]">
            <span
              className="inline-block h-1.5 w-1.5 rounded-full bg-[#a78bfa]"
              style={{ boxShadow: "0 0 6px rgba(167,139,250,0.5)" }}
            />
            Global Leaderboard
          </h3>
          <DataTable
            columns={columns}
            data={leaderboard?.entries ?? []}
            isLoading={isLoading}
            keyFn={(e) => e.agent_id}
            emptyMessage="No reputation data yet"
          />
        </div>

        {/* Top 10 Horizontal Bar Chart */}
        <div className="space-y-1">
          <h3 className="flex items-center gap-2 px-1 text-xs font-semibold uppercase tracking-widest text-[#64748b]">
            <span
              className="inline-block h-1.5 w-1.5 rounded-full bg-[#34d399]"
              style={{ boxShadow: "0 0 6px rgba(52,211,153,0.5)" }}
            />
            Top 10 Scores
          </h3>
          <div
            className="rounded-2xl border border-[rgba(255,255,255,0.06)] p-4"
            style={{ background: "#141928" }}
          >
            {chartData.length === 0 ? (
              <p className="py-12 text-center text-sm text-[#64748b]">No data yet</p>
            ) : (
              <ResponsiveContainer width="100%" height={320}>
                <BarChart
                  data={chartData}
                  layout="vertical"
                  margin={{ left: 0, right: 12, top: 8, bottom: 8 }}
                >
                  <ChartGradientDefs />
                  <CartesianGrid
                    horizontal={false}
                    stroke="rgba(255,255,255,0.06)"
                    strokeDasharray="3 3"
                  />
                  <XAxis
                    type="number"
                    domain={[0, 100]}
                    tick={{ fill: "#94a3b8", fontSize: 10 }}
                    axisLine={false}
                    tickLine={false}
                  />
                  <YAxis
                    type="category"
                    dataKey="name"
                    width={90}
                    tick={{ fill: "#94a3b8", fontSize: 11 }}
                    axisLine={false}
                    tickLine={false}
                  />
                  <Tooltip
                    contentStyle={DARK_TOOLTIP_STYLE}
                    cursor={{ fill: "rgba(96,165,250,0.06)" }}
                    formatter={(value) => [`${value}%`, "Score"]}
                  />
                  <Bar dataKey="score" radius={[0, 6, 6, 0]} barSize={16}>
                    {chartData.map((_, i) => (
                      <Cell
                        key={i}
                        fill="url(#barGradient)"
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

/* ── RepStat: dark mini card with colored accent ──────────────── */

function RepStat({ label, value }: { label: string; value: string | number }) {
  const accent = STAT_ACCENTS[label] ?? { color: "#60a5fa", bg: "rgba(96,165,250,0.08)" };
  const Icon = STAT_ICONS[label] ?? Hash;

  return (
    <div
      className="group rounded-xl border border-[rgba(255,255,255,0.06)] p-3.5 transition-all duration-200 hover:border-[rgba(255,255,255,0.1)]"
      style={{ background: "#1a2035" }}
    >
      <div className="mb-2 flex items-center gap-2">
        <div
          className="flex h-6 w-6 items-center justify-center rounded-lg"
          style={{ background: accent.bg }}
        >
          <Icon className="h-3 w-3" style={{ color: accent.color }} />
        </div>
        <p className="text-[11px] font-medium uppercase tracking-wider text-[#64748b]">{label}</p>
      </div>
      <p
        className="text-sm font-bold text-[#e2e8f0] font-mono tabular-nums"
        style={{ textShadow: `0 0 12px ${accent.color}20` }}
      >
        {typeof value === "number" ? <AnimatedCounter value={value} /> : value}
      </p>
    </div>
  );
}
