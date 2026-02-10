import { useState } from "react";
import { Flame, Search, Target, TrendingUp } from "lucide-react";
import SubTabNav from "../components/SubTabNav";
import OpportunityCard from "../components/OpportunityCard";
import { SkeletonCard } from "../components/Skeleton";
import QualityBar from "../components/QualityBar";
import Badge from "../components/Badge";
import { useTrending, useDemandGaps, useOpportunities } from "../hooks/useAnalytics";

const SUB_TABS = [
  { id: "trending", label: "Trending" },
  { id: "gaps", label: "Demand Gaps" },
  { id: "opportunities", label: "Opportunities" },
];

export default function AnalyticsPage() {
  const [activeTab, setActiveTab] = useState("trending");

  return (
    <div className="space-y-6 animate-fade-in">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-semibold text-text-primary">Demand Intelligence</h2>
          <p className="text-sm text-text-secondary">What agents are searching for right now</p>
        </div>
        <SubTabNav tabs={SUB_TABS} active={activeTab} onChange={setActiveTab} />
      </div>

      {activeTab === "trending" && <TrendingPanel />}
      {activeTab === "gaps" && <GapsPanel />}
      {activeTab === "opportunities" && <OpportunitiesPanel />}
    </div>
  );
}

function TrendingPanel() {
  const { data, isLoading } = useTrending(20, 6);

  if (isLoading) {
    return (
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
        {Array.from({ length: 6 }).map((_, i) => (
          <SkeletonCard key={i} />
        ))}
      </div>
    );
  }

  const trends = data?.trends ?? [];

  if (!trends.length) {
    return (
      <div className="flex flex-col items-center justify-center py-16 text-text-muted">
        <Search className="mb-3 h-10 w-10 opacity-40" />
        <p>No trending queries yet. Searches will appear here as agents use the marketplace.</p>
      </div>
    );
  }

  return (
    <div className="overflow-x-auto rounded-xl border border-border-subtle">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-border-subtle bg-surface-raised/50">
            <th className="px-4 py-3 text-left text-text-secondary font-medium">Query</th>
            <th className="px-4 py-3 text-left text-text-secondary font-medium">Category</th>
            <th className="px-4 py-3 text-right text-text-secondary font-medium">Searches</th>
            <th className="px-4 py-3 text-right text-text-secondary font-medium">Velocity</th>
            <th className="px-4 py-3 text-left text-text-secondary font-medium">Fulfillment</th>
          </tr>
        </thead>
        <tbody>
          {trends.map((t, i) => (
            <tr
              key={i}
              className="border-b border-border-subtle/50 transition-colors hover:bg-surface-raised/30"
            >
              <td className="px-4 py-3 text-text-primary font-medium">{t.query_pattern}</td>
              <td className="px-4 py-3">
                {t.category ? (
                  <Badge label={t.category} variant="blue" />
                ) : (
                  <span className="text-text-muted">—</span>
                )}
              </td>
              <td className="px-4 py-3 text-right font-mono text-text-primary">{t.search_count}</td>
              <td className="px-4 py-3 text-right">
                <span className="inline-flex items-center gap-1 font-mono">
                  {t.velocity > 5 && <Flame className="h-3.5 w-3.5 text-orange-400" />}
                  <span className={t.velocity > 5 ? "text-orange-400" : "text-text-secondary"}>
                    {t.velocity.toFixed(1)}/hr
                  </span>
                </span>
              </td>
              <td className="px-4 py-3 w-32">
                <QualityBar score={t.fulfillment_rate} />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

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
      <div className="flex flex-col items-center justify-center py-16 text-text-muted">
        <Target className="mb-3 h-10 w-10 opacity-40" />
        <p>No demand gaps detected. All buyer searches are being fulfilled.</p>
      </div>
    );
  }

  return (
    <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
      {gaps.map((g, i) => (
        <div
          key={i}
          className="rounded-xl border border-red-500/20 bg-surface-raised p-4 animate-scale-in"
        >
          <div className="mb-2 flex items-start justify-between">
            <p className="font-medium text-text-primary">{g.query_pattern}</p>
            <span className="rounded-full bg-red-500/20 px-2 py-0.5 text-xs font-medium text-red-400">
              Gap
            </span>
          </div>
          {g.category && (
            <Badge label={g.category} variant="blue" />
          )}
          <div className="mt-3 grid grid-cols-2 gap-2 text-sm text-text-secondary">
            <div>
              <span className="text-text-muted">Searches:</span>{" "}
              <span className="font-mono text-text-primary">{g.search_count}</span>
            </div>
            <div>
              <span className="text-text-muted">Requesters:</span>{" "}
              <span className="font-mono text-text-primary">{g.unique_requesters}</span>
            </div>
            {g.avg_max_price != null && (
              <div className="col-span-2">
                <span className="text-text-muted">Avg budget:</span>{" "}
                <span className="font-mono text-emerald-400">${g.avg_max_price.toFixed(4)}</span>
              </div>
            )}
          </div>
        </div>
      ))}
    </div>
  );
}

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
      <div className="flex flex-col items-center justify-center py-16 text-text-muted">
        <TrendingUp className="mb-3 h-10 w-10 opacity-40" />
        <p>No opportunities available yet. They are generated from demand gaps.</p>
      </div>
    );
  }

  return (
    <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
      {opps.map((o) => (
        <OpportunityCard
          key={o.id}
          queryPattern={o.query_pattern}
          category={o.category}
          estimatedRevenue={o.estimated_revenue_usdc}
          searchVelocity={o.search_velocity}
          competingListings={o.competing_listings}
          urgencyScore={o.urgency_score}
        />
      ))}
    </div>
  );
}
