import { useHealth } from "../hooks/useHealth";
import { useLeaderboard } from "../hooks/useReputation";
import { useLiveFeed } from "../hooks/useLiveFeed";
import StatCard from "../components/StatCard";
import Spinner from "../components/Spinner";
import { relativeTime } from "../lib/format";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  Cell,
} from "recharts";

export default function DashboardPage() {
  const { data: health, isLoading } = useHealth();
  const { data: leaderboard } = useLeaderboard(5);
  const events = useLiveFeed();

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-20">
        <Spinner />
      </div>
    );
  }

  const topAgents = (leaderboard?.entries ?? []).map((e) => ({
    name: e.agent_name,
    score: Math.round(e.composite_score * 100),
  }));

  return (
    <div className="space-y-6">
      {/* Stat cards */}
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        <StatCard label="Agents" value={health?.agents_count ?? 0} />
        <StatCard label="Listings" value={health?.listings_count ?? 0} />
        <StatCard label="Transactions" value={health?.transactions_count ?? 0} />
        <StatCard
          label="Status"
          value={health?.status === "healthy" ? "Healthy" : "Down"}
          subtitle={health?.version}
        />
      </div>

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
              <div className="max-h-80 space-y-2 overflow-y-auto">
                {events.map((evt, i) => (
                  <div
                    key={`${evt.timestamp}-${i}`}
                    className="flex items-start gap-3 rounded-lg p-2 transition-colors hover:bg-zinc-800/50"
                  >
                    <div className="mt-1.5 h-2 w-2 flex-shrink-0 rounded-full bg-emerald-500" />
                    <div className="min-w-0 flex-1">
                      <p className="text-sm text-zinc-300">
                        <span className="font-medium text-white">
                          {evt.type.replace(/_/g, " ")}
                        </span>
                      </p>
                      <p className="text-xs text-zinc-600">
                        {relativeTime(evt.timestamp)}
                      </p>
                    </div>
                  </div>
                ))}
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
