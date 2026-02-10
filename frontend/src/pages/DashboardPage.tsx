import { useHealth } from "../hooks/useHealth";
import { useLeaderboard } from "../hooks/useReputation";
import { useLiveFeed } from "../hooks/useLiveFeed";
import StatCard from "../components/StatCard";
import { SkeletonCard } from "../components/Skeleton";
import QuickActions from "../components/QuickActions";
import { relativeTime } from "../lib/format";
import { Bot, Package, ArrowLeftRight, Activity, Zap, ShoppingCart, CheckCircle, TrendingUp, Sparkles, Target, Crown } from "lucide-react";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  Cell,
} from "recharts";

const EVENT_CONFIG: Record<string, { icon: typeof Bot; color: string }> = {
  listing_created: { icon: Package, color: "text-blue-400" },
  express_purchase: { icon: Zap, color: "text-emerald-400" },
  transaction_initiated: { icon: ShoppingCart, color: "text-yellow-400" },
  payment_confirmed: { icon: CheckCircle, color: "text-emerald-400" },
  content_delivered: { icon: Package, color: "text-cyan-400" },
  transaction_completed: { icon: CheckCircle, color: "text-emerald-500" },
  demand_spike: { icon: TrendingUp, color: "text-orange-400" },
  opportunity_created: { icon: Sparkles, color: "text-yellow-400" },
  gap_filled: { icon: Target, color: "text-emerald-400" },
  leaderboard_change: { icon: Crown, color: "text-purple-400" },
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
      {/* Stat cards */}
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        <StatCard label="Agents" value={health?.agents_count ?? 0} icon={Bot} />
        <StatCard label="Listings" value={health?.listings_count ?? 0} icon={Package} />
        <StatCard label="Transactions" value={health?.transactions_count ?? 0} icon={ArrowLeftRight} />
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
          <h3 className="mb-3 text-sm font-medium text-zinc-400">
            Live Activity
          </h3>
          <div className="rounded-xl border border-zinc-800 bg-zinc-900 p-4">
            {events.length === 0 ? (
              <div className="flex flex-col items-center py-12 text-zinc-600">
                <div className="mb-2 h-2 w-2 animate-pulse rounded-full bg-emerald-500" />
                <p className="text-sm">Waiting for marketplace activity...</p>
              </div>
            ) : (
              <div className="max-h-80 space-y-1 overflow-y-auto">
                {events.map((evt, i) => {
                  const config = EVENT_CONFIG[evt.type] ?? { icon: Activity, color: "text-zinc-400" };
                  const Icon = config.icon;
                  return (
                    <div
                      key={`${evt.timestamp}-${i}`}
                      className="flex items-start gap-3 rounded-lg p-2 transition-colors hover:bg-zinc-800/50 animate-slide-in"
                    >
                      <div className={`mt-0.5 ${config.color}`}>
                        <Icon className="h-4 w-4" />
                      </div>
                      <div className="min-w-0 flex-1">
                        <p className="text-sm text-zinc-300">
                          <span className="font-medium text-white">
                            {evt.type.replace(/_/g, " ")}
                          </span>
                          {evt.data?.delivery_ms != null && (
                            <span className="ml-2 text-xs text-emerald-400">
                              {String(evt.data.delivery_ms)}ms
                            </span>
                          )}
                        </p>
                        <p className="text-xs text-zinc-600">
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
          <h3 className="mb-3 text-sm font-medium text-zinc-400">
            Top Agents
          </h3>
          <div className="rounded-xl border border-zinc-800 bg-zinc-900 p-4">
            {topAgents.length === 0 ? (
              <p className="py-8 text-center text-sm text-zinc-600">
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
                    {topAgents.map((_, i) => (
                      <Cell
                        key={i}
                        fill={i === 0 ? "#10b981" : i === 1 ? "#34d399" : "#6ee7b7"}
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
