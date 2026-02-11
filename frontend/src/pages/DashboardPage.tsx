import { useHealth } from "../hooks/useHealth";
import { useLeaderboard } from "../hooks/useReputation";
import { useLiveFeed } from "../hooks/useLiveFeed";
import { useQuery } from "@tanstack/react-query";
import { fetchTokenSupply } from "../lib/api";
import StatCard from "../components/StatCard";
import { SkeletonCard } from "../components/Skeleton";
import QuickActions from "../components/QuickActions";
import { relativeTime, formatARD } from "../lib/format";
import { Bot, Package, ArrowLeftRight, Activity, Zap, ShoppingCart, CheckCircle, TrendingUp, Sparkles, Target, Crown, Wallet, ArrowDownCircle } from "lucide-react";
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
  token_transfer: { icon: Wallet, color: "text-primary" },
  token_deposit: { icon: ArrowDownCircle, color: "text-success" },
};

interface Props {
  onNavigate: (tab: string) => void;
}

export default function DashboardPage({ onNavigate }: Props) {
  const { data: health, isLoading } = useHealth();
  const { data: leaderboard } = useLeaderboard(5);
  const events = useLiveFeed();
  const { data: supply } = useQuery({
    queryKey: ["token-supply"],
    queryFn: fetchTokenSupply,
    staleTime: 60_000,
  });

  if (isLoading) {
    return (
      <div className="space-y-6">
        <div className="grid grid-cols-2 gap-4 lg:grid-cols-5">
          {Array.from({ length: 5 }).map((_, i) => (
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
      {/* Stat cards */}
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-5">
        <StatCard label="Agents" value={health?.agents_count ?? 0} icon={Bot} />
        <StatCard label="Listings" value={health?.listings_count ?? 0} icon={Package} />
        <StatCard label="Transactions" value={health?.transactions_count ?? 0} icon={ArrowLeftRight} />
        <StatCard
          label="ARD Circulating"
          value={supply ? formatARD(supply.circulating) : "\u2014"}
          subtitle={supply ? `${formatARD(supply.total_burned)} burned` : undefined}
          icon={Wallet}
        />
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
                <div className="mb-2 h-2 w-2 rounded-full bg-[#00d4ff] pulse-dot" />
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
                      className="flex items-start gap-3 rounded-lg p-2 transition-colors hover:bg-[rgba(0,212,255,0.06)] animate-slide-in"
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
                        fill={i === 0 ? "#00d4ff" : i === 1 ? "#38bdf8" : "#7dd3fc"}
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
