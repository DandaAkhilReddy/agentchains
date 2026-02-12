import { AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer } from "recharts";

const CHART_TOOLTIP_STYLE = {
  backgroundColor: "rgba(255, 255, 255, 0.95)",
  border: "1px solid rgba(59, 130, 246, 0.15)",
  borderRadius: 12,
  color: "#0f172a",
  fontSize: 12,
};

interface DataPoint {
  date: string;
  earned: number;
  spent: number;
}

interface Props {
  data: DataPoint[];
}

export default function EarningsChart({ data }: Props) {
  if (!data.length) {
    return (
      <div className="flex h-48 items-center justify-center text-text-muted">
        No earnings data yet
      </div>
    );
  }

  return (
    <ResponsiveContainer width="100%" height={200}>
      <AreaChart data={data} margin={{ top: 5, right: 5, bottom: 5, left: 5 }}>
        <defs>
          <linearGradient id="earnedGradient" x1="0" y1="0" x2="0" y2="1">
            <stop offset="5%" stopColor="#3b82f6" stopOpacity={0.3} />
            <stop offset="95%" stopColor="#3b82f6" stopOpacity={0} />
          </linearGradient>
          <linearGradient id="spentGradient" x1="0" y1="0" x2="0" y2="1">
            <stop offset="5%" stopColor="#e11d48" stopOpacity={0.3} />
            <stop offset="95%" stopColor="#e11d48" stopOpacity={0} />
          </linearGradient>
        </defs>
        <XAxis
          dataKey="date"
          tick={{ fill: "#94a3b8", fontSize: 11 }}
          axisLine={false}
          tickLine={false}
        />
        <YAxis
          tick={{ fill: "#94a3b8", fontSize: 11 }}
          axisLine={false}
          tickLine={false}
          tickFormatter={(v) => `$${v}`}
        />
        <Tooltip
          contentStyle={CHART_TOOLTIP_STYLE}
          formatter={(value: number | undefined) => [`$${(value ?? 0).toFixed(4)}`, ""]}
        />
        <Area
          type="monotone"
          dataKey="earned"
          stroke="#3b82f6"
          fill="url(#earnedGradient)"
          strokeWidth={2}
          name="Earned"
        />
        <Area
          type="monotone"
          dataKey="spent"
          stroke="#e11d48"
          fill="url(#spentGradient)"
          strokeWidth={2}
          name="Spent"
        />
      </AreaChart>
    </ResponsiveContainer>
  );
}
