import { useHealth } from "../hooks/useHealth";
import { useLeaderboard } from "../hooks/useReputation";
import { useLiveFeed } from "../hooks/useLiveFeed";
import StatCard from "../components/StatCard";
import PageHeader from "../components/PageHeader";
import { SkeletonCard } from "../components/Skeleton";
import QuickActions from "../components/QuickActions";
import { relativeTime } from "../lib/format";
import { Bot, Package, ArrowLeftRight, Activity, Zap, ShoppingCart, CheckCircle, TrendingUp, Sparkles, Target, Crown, Wallet, ArrowDownCircle, LayoutDashboard } from "lucide-react";
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
  backgroundColor: "rgba(255, 255, 255, 0.95)",
  border: "1px solid rgba(59, 130, 246, 0.15)",
  borderRadius: 12,
  color: "#0f172a",
  fontSize: 12,
};

const EVENT_CONFIG: Record<string, { icon: typeof Bot; color: string }> = {
  listing_created: { icon: Package, color: "text-blue-400" },
  express_purchase: { icon: Zap, color: "text-primary" },
  transaction_initiated: { icon: ShoppingCart, color: "text-yellow-400" },
  payment_confirmed: { icon: CheckCircle, color: "text-primary" },
  content_delivered: { icon: Package, color: "text-cyan-400" },
  transaction_completed: { icon: CheckCircle, color: "text-success" },
  demand_spike: { icon: TrendingUp, color: "text-orange-400" },
  opportunity_created: { icon: Sparkles, color: "text-yellow-400" },
  gap_filled: { icon: Target, color: "text-primary" },
  leaderboard_change: { icon: Crown, color: "text-purple-400" },
  payment: { icon: Wallet, color: "text-primary" },
  deposit: { icon: ArrowDownCircle, color: "text-success" },
};

interface Props {
  onNavigate: (tab: string) => void;
}

export default function DashboardPage({ onNavigate }: Props) {
  const { data: health, isLoading } = useHealth();
  const { data: leaderboard } = useLeaderboard(5);
  const events = useLiveFeed();
  if (isLoading) {
    return (
      <div className="space-y-6">
        <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
          {Array.from({ length: 4 }).map((_, i) => (
            <SkeletonCard key={i} />
          ))}
        </div>
      </div>
    );
  }

  const topAgents = (leaderboard?.entries ?? []).map((e) => ({
    name: e.agent_name,
    score: Math.round(e.composite_score * 100),
  }));

  return (
    <div className="space-y-6 animate-fade-in">
      <PageHeader title="Dashboard" subtitle="Platform overview and live activity" icon={LayoutDashboard} />
      {/* Stat cards */}
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        <StatCard label="Agents" value={health?.agents_count ?? 0} icon={Bot} sparkData={[3, 5, 4, 7, 6, 8, 9]} />
        <StatCard label="Listings" value={health?.listings_count ?? 0} icon={Package} sparkData={[2, 4, 3, 6, 5, 7, 8]} />
        <StatCard label="Transactions" value={health?.transactions_count ?? 0} icon={ArrowLeftRight} sparkData={[1, 3, 5, 4, 6, 8, 7]} />
        <StatCard
          label="Status"
          value={health?.status === "healthy" ? "Healthy" : "Down"}
          subtitle={health?.version}
          icon={Activity}
        />
      </div>

      {/* Quick actions */}
      <QuickActions onNavigate={onNavigate} />

      {/* Live feed + Top agents */}
      <div className="grid gap-6 lg:grid-cols-3">
        {/* Live feed */}
        <div className="lg:col-span-2">
          <h3 className="mb-3 text-xs font-semibold uppercase tracking-widest text-text-secondary">
            Live Activity
          </h3>
          <div className="glass-card gradient-border-card glow-hover p-4">
            {events.length === 0 ? (
              <div className="flex flex-col items-center py-12 text-text-muted">
                <div className="mb-2 h-2 w-2 rounded-full bg-primary pulse-dot" />
                <p className="text-sm">Waiting for marketplace activity...</p>
              </div>
            ) : (
              <div className="max-h-80 space-y-1 overflow-y-auto">
                {events.map((evt, i) => {
                  const config = EVENT_CONFIG[evt.type] ?? { icon: Activity, color: "text-text-secondary" };
                  const Icon = config.icon;
                  return (
                    <div
                      key={`${evt.timestamp}-${i}`}
                      className="flex items-start gap-3 rounded-lg p-2 transition-colors hover:bg-[rgba(59,130,246,0.04)] animate-slide-in"
                    >
                      <div className={`mt-0.5 ${config.color}`}>
                        <Icon className="h-4 w-4" />
                      </div>
                      <div className="min-w-0 flex-1">
                        <p className="text-sm text-text-secondary">
                          <span className="font-medium text-text-primary">
                            {evt.type.replace(/_/g, " ")}
                          </span>
                          {evt.data?.delivery_ms != null && (
                            <span className="ml-2 text-xs text-primary">
                              {String(evt.data.delivery_ms)}ms
                            </span>
                          )}
                        </p>
                        <p className="text-xs text-text-muted">
                          {relativeTime(evt.timestamp)}
                        </p>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        </div>

        {/* Top agents chart */}
        <div>
          <h3 className="mb-3 text-xs font-semibold uppercase tracking-widest text-text-secondary">
            Top Agents
          </h3>
          <div className="glass-card gradient-border-card glow-hover p-4">
            {topAgents.length === 0 ? (
              <p className="py-8 text-center text-sm text-text-muted">
                No reputation data yet
              </p>
            ) : (
              <ResponsiveContainer width="100%" height={200}>
                <BarChart
                  data={topAgents}
                  layout="vertical"
                  margin={{ left: 0, right: 10, top: 5, bottom: 5 }}
                >
                  <XAxis type="number" domain={[0, 100]} hide />
                  <YAxis
                    type="category"
                    dataKey="name"
                    width={80}
                    tick={{ fill: "#475569", fontSize: 11 }}
                    axisLine={false}
                    tickLine={false}
                  />
                  <Tooltip
                    contentStyle={CHART_TOOLTIP_STYLE}
                    formatter={(value) => [`${value}%`, "Score"]}
                  />
                  <Bar dataKey="score" radius={[0, 4, 4, 0]}>
                    {topAgents.map((_, i) => (
                      <Cell
                        key={i}
                        fill={i === 0 ? "#3b82f6" : i === 1 ? "#60a5fa" : "#93c5fd"}
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
