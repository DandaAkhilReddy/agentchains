import { useState, useMemo } from "react";
import {
  BarChart3,
  Flame,
  Search,
  Target,
  TrendingUp,
  ArrowUpRight,
  ArrowDownRight,
  Users,
  Calendar,
} from "lucide-react";
import PageHeader from "../components/PageHeader";
import SubTabNav from "../components/SubTabNav";
import DataTable from "../components/DataTable";
import type { Column } from "../components/DataTable";
import Badge, { categoryVariant } from "../components/Badge";
import UrgencyBadge from "../components/UrgencyBadge";
import { SkeletonCard } from "../components/Skeleton";
import { useTrending, useDemandGaps, useOpportunities } from "../hooks/useAnalytics";
import type { TrendingQuery, DemandGap, Opportunity } from "../types/api";

/* ---------- Sub-tab definitions ---------- */

const SUB_TABS = [
  { id: "trending", label: "Trending" },
  { id: "gaps", label: "Demand Gaps" },
  { id: "opportunities", label: "Opportunities" },
];

/* ---------- Fulfillment progress bar (dark themed, red->amber->green gradient) ---------- */

function FulfillmentBar({ rate }: { rate: number }) {
  const pct = Math.round(rate * 100);

  // Gradient color transitions: red (0%) -> amber (50%) -> green (100%)
  let barGradient: string;
  let glowColor: string;
  if (rate >= 0.7) {
    barGradient = "from-[#fbbf24] via-[#34d399] to-[#22d3ee]";
    glowColor = "shadow-[0_0_8px_rgba(52,211,153,0.3)]";
  } else if (rate >= 0.4) {
    barGradient = "from-[#f87171] via-[#fbbf24] to-[#fbbf24]";
    glowColor = "shadow-[0_0_6px_rgba(251,191,36,0.2)]";
  } else {
    barGradient = "from-[#f87171] to-[#fb923c]";
    glowColor = "";
  }

  return (
    <div className="flex items-center gap-2">
      <div
        className={`h-1.5 w-20 overflow-hidden rounded-full bg-[#1a2035] ${glowColor}`}
      >
        <div
          className={`h-full rounded-full bg-gradient-to-r ${barGradient} transition-all duration-700 ease-out`}
          style={{ width: `${pct}%` }}
        />
      </div>
      <span className="text-xs font-mono text-[#94a3b8]">{pct}%</span>
    </div>
  );
}

/* ---------- Main page ---------- */

export default function AnalyticsPage() {
  const [activeTab, setActiveTab] = useState("trending");

  return (
    <div className="min-h-screen space-y-6 animate-fade-in">
      {/* Header row */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <PageHeader
          title="Demand Intelligence"
          subtitle="What agents are searching for right now"
          icon={BarChart3}
        />
        <SubTabNav tabs={SUB_TABS} active={activeTab} onChange={setActiveTab} />
      </div>

      {/* Tab content */}
      {activeTab === "trending" && <TrendingPanel />}
      {activeTab === "gaps" && <GapsPanel />}
      {activeTab === "opportunities" && <OpportunitiesPanel />}
    </div>
  );
}

/* ============================================================
   TRENDING PANEL -- DataTable with dark styling
   ============================================================ */

function TrendingPanel() {
  const { data, isLoading } = useTrending(20, 6);

  // Sort by velocity descending
  const trends = useMemo(() => {
    const raw = data?.trends ?? [];
    return [...raw].sort((a, b) => b.velocity - a.velocity);
  }, [data]);

  const columns: Column<TrendingQuery>[] = useMemo(
    () => [
      {
        key: "query",
        header: "Query",
        align: "left" as const,
        render: (row) => (
          <span className="font-medium text-[#e2e8f0]">{row.query_pattern}</span>
        ),
      },
      {
        key: "category",
        header: "Category",
        align: "left" as const,
        render: (row) =>
          row.category ? (
            <Badge label={row.category} variant={categoryVariant(row.category)} />
          ) : (
            <span className="text-[#64748b]">&mdash;</span>
          ),
      },
      {
        key: "searches",
        header: "Searches",
        align: "right" as const,
        render: (row) => (
          <span className="font-mono text-[#e2e8f0]">{row.search_count.toLocaleString()}</span>
        ),
      },
      {
        key: "velocity",
        header: "Velocity",
        align: "right" as const,
        render: (row) => {
          const isHot = row.velocity > 5;
          return (
            <span className="inline-flex items-center gap-1.5 font-mono">
              {isHot && (
                <Flame className="h-3.5 w-3.5 text-[#fbbf24] drop-shadow-[0_0_4px_rgba(251,191,36,0.6)]" />
              )}
              <span className={isHot ? "text-[#fbbf24] font-semibold" : "text-[#94a3b8]"}>
                {row.velocity.toFixed(1)}/hr
              </span>
            </span>
          );
        },
      },
      {
        key: "fulfillment",
        header: "Fulfillment",
        align: "left" as const,
        className: "w-36",
        render: (row) => <FulfillmentBar rate={row.fulfillment_rate} />,
      },
    ],
    [],
  );

  if (!isLoading && trends.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center rounded-2xl border border-[rgba(255,255,255,0.06)] bg-[#141928] py-20 text-[#64748b]">
        <Search className="mb-3 h-10 w-10 opacity-40" />
        <p className="text-sm">No trending queries yet. Searches will appear here as agents use the marketplace.</p>
      </div>
    );
  }

  return (
    <DataTable
      columns={columns}
      data={trends}
      isLoading={isLoading}
      keyFn={(row) => `${row.query_pattern}-${row.category ?? "all"}`}
      emptyMessage="No trending queries yet"
    />
  );
}

/* ============================================================
   DEMAND GAPS PANEL -- Card grid with red accent
   ============================================================ */

function GapsPanel() {
  const { data, isLoading } = useDemandGaps(20);

  if (isLoading) {
    return (
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
        {Array.from({ length: 6 }).map((_, i) => (
          <SkeletonCard key={i} />
        ))}
      </div>
    );
  }

  const gaps = data?.gaps ?? [];

  if (!gaps.length) {
    return (
      <div className="flex flex-col items-center justify-center rounded-2xl border border-[rgba(255,255,255,0.06)] bg-[#141928] py-20 text-[#64748b]">
        <Target className="mb-3 h-10 w-10 opacity-40" />
        <p className="text-sm">No demand gaps detected. All buyer searches are being fulfilled.</p>
      </div>
    );
  }

  return (
    <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
      {gaps.map((g, i) => (
        <GapCard key={`${g.query_pattern}-${i}`} gap={g} index={i} />
      ))}
    </div>
  );
}

function GapCard({ gap, index }: { gap: DemandGap; index: number }) {
  const firstSearched = gap.first_searched_at
    ? new Date(gap.first_searched_at).toLocaleDateString("en-US", {
        month: "short",
        day: "numeric",
      })
    : null;

  return (
    <div
      className="group relative overflow-hidden rounded-2xl border border-[rgba(248,113,113,0.15)] bg-[#141928] p-5 transition-all duration-300 hover:border-[rgba(248,113,113,0.35)] hover:shadow-[0_0_30px_rgba(248,113,113,0.08)]"
      style={{ animationDelay: `${index * 60}ms` }}
    >
      {/* Red accent bar at top */}
      <div className="absolute inset-x-0 top-0 h-[2px] bg-gradient-to-r from-transparent via-[#f87171] to-transparent opacity-60 transition-opacity group-hover:opacity-100" />

      {/* Header */}
      <div className="mb-3 flex items-start justify-between gap-2">
        <p className="flex-1 font-medium leading-snug text-[#e2e8f0]">
          {gap.query_pattern}
        </p>
        <Badge label="Gap" variant="red" />
      </div>

      {/* Category badge */}
      {gap.category && (
        <div className="mb-3">
          <Badge label={gap.category} variant={categoryVariant(gap.category)} />
        </div>
      )}

      {/* Stats grid */}
      <div className="grid grid-cols-2 gap-x-4 gap-y-2 text-sm">
        <div className="flex items-center gap-1.5">
          <Search className="h-3.5 w-3.5 text-[#64748b]" />
          <span className="text-[#64748b]">Searches</span>
        </div>
        <div className="text-right font-mono text-[#e2e8f0]">
          {gap.search_count.toLocaleString()}
        </div>

        <div className="flex items-center gap-1.5">
          <Users className="h-3.5 w-3.5 text-[#64748b]" />
          <span className="text-[#64748b]">Requesters</span>
        </div>
        <div className="text-right font-mono text-[#e2e8f0]">
          {gap.unique_requesters}
        </div>

        {gap.avg_max_price != null && (
          <>
            <div className="col-span-2 mt-1 border-t border-[rgba(255,255,255,0.04)] pt-2">
              <span className="text-[#64748b] text-xs">Avg budget</span>
              <p className="mt-0.5 font-mono text-lg font-semibold text-[#fbbf24] drop-shadow-[0_0_6px_rgba(251,191,36,0.3)]">
                ${gap.avg_max_price.toFixed(4)}
              </p>
            </div>
          </>
        )}
      </div>

      {/* First searched footer */}
      {firstSearched && (
        <div className="mt-3 flex items-center gap-1.5 border-t border-[rgba(255,255,255,0.04)] pt-3 text-xs text-[#64748b]">
          <Calendar className="h-3 w-3" />
          <span>First searched {firstSearched}</span>
        </div>
      )}
    </div>
  );
}

/* ============================================================
   OPPORTUNITIES PANEL -- Card grid with green accent
   ============================================================ */

function OpportunitiesPanel() {
  const { data, isLoading } = useOpportunities(20);

  if (isLoading) {
    return (
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
        {Array.from({ length: 6 }).map((_, i) => (
          <SkeletonCard key={i} />
        ))}
      </div>
    );
  }

  const opps = data?.opportunities ?? [];

  if (!opps.length) {
    return (
      <div className="flex flex-col items-center justify-center rounded-2xl border border-[rgba(255,255,255,0.06)] bg-[#141928] py-20 text-[#64748b]">
        <TrendingUp className="mb-3 h-10 w-10 opacity-40" />
        <p className="text-sm">No opportunities available yet. They are generated from demand gaps.</p>
      </div>
    );
  }

  return (
    <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
      {opps.map((o, i) => (
        <OpportunityCardDark key={o.id} opp={o} index={i} />
      ))}
    </div>
  );
}

function OpportunityCardDark({ opp, index }: { opp: Opportunity; index: number }) {
  const velocityTrend = opp.search_velocity > 3;

  return (
    <div
      className="group relative overflow-hidden rounded-2xl border border-[rgba(52,211,153,0.15)] bg-[#141928] p-5 transition-all duration-300 hover:border-[rgba(52,211,153,0.35)] hover:shadow-[0_0_30px_rgba(52,211,153,0.08)]"
      style={{ animationDelay: `${index * 60}ms` }}
    >
      {/* Green accent bar at top */}
      <div className="absolute inset-x-0 top-0 h-[2px] bg-gradient-to-r from-transparent via-[#34d399] to-transparent opacity-60 transition-opacity group-hover:opacity-100" />

      {/* Header */}
      <div className="mb-3 flex items-start justify-between gap-2">
        <div className="flex-1">
          <p className="font-medium leading-snug text-[#e2e8f0]">
            {opp.query_pattern}
          </p>
          {opp.category && (
            <div className="mt-1.5">
              <Badge label={opp.category} variant={categoryVariant(opp.category)} />
            </div>
          )}
        </div>
        <UrgencyBadge score={opp.urgency_score} />
      </div>

      {/* Estimated revenue -- large display */}
      <div className="mb-4 rounded-xl bg-[rgba(52,211,153,0.06)] px-4 py-3 border border-[rgba(52,211,153,0.08)]">
        <span className="text-xs text-[#64748b] uppercase tracking-wider">Est. Revenue</span>
        <p className="mt-0.5 font-mono text-2xl font-bold text-[#34d399] drop-shadow-[0_0_12px_rgba(52,211,153,0.4)]">
          ${opp.estimated_revenue_usdc.toFixed(4)}
        </p>
      </div>

      {/* Metrics */}
      <div className="space-y-2.5 text-sm">
        {/* Search velocity */}
        <div className="flex items-center justify-between">
          <span className="flex items-center gap-1.5 text-[#64748b]">
            <TrendingUp className="h-3.5 w-3.5" />
            Velocity
          </span>
          <span className="inline-flex items-center gap-1 font-mono text-[#e2e8f0]">
            {opp.search_velocity.toFixed(1)}/hr
            {velocityTrend ? (
              <ArrowUpRight className="h-3.5 w-3.5 text-[#34d399]" />
            ) : (
              <ArrowDownRight className="h-3.5 w-3.5 text-[#64748b]" />
            )}
          </span>
        </div>

        {/* Competing listings */}
        <div className="flex items-center justify-between">
          <span className="flex items-center gap-1.5 text-[#64748b]">
            <Users className="h-3.5 w-3.5" />
            Competing
          </span>
          <span className="font-mono text-[#e2e8f0]">
            {opp.competing_listings}
          </span>
        </div>
      </div>
    </div>
  );
}
