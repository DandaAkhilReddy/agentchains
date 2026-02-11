import { AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer } from "recharts";

const CHART_TOOLTIP_STYLE = {
  backgroundColor: "rgba(13, 17, 23, 0.95)",
  border: "1px solid rgba(0, 212, 255, 0.2)",
  borderRadius: 12,
  color: "#e2e8f0",
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
            <stop offset="5%" stopColor="#00d4ff" stopOpacity={0.3} />
            <stop offset="95%" stopColor="#00d4ff" stopOpacity={0} />
          </linearGradient>
          <linearGradient id="spentGradient" x1="0" y1="0" x2="0" y2="1">
            <stop offset="5%" stopColor="#f43f5e" stopOpacity={0.3} />
            <stop offset="95%" stopColor="#f43f5e" stopOpacity={0} />
          </linearGradient>
        </defs>
        <XAxis
          dataKey="date"
          tick={{ fill: "#475569", fontSize: 11 }}
          axisLine={false}
          tickLine={false}
        />
        <YAxis
          tick={{ fill: "#475569", fontSize: 11 }}
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
          stroke="#00d4ff"
          fill="url(#earnedGradient)"
          strokeWidth={2}
          name="Earned"
        />
        <Area
          type="monotone"
          dataKey="spent"
          stroke="#f43f5e"
          fill="url(#spentGradient)"
          strokeWidth={2}
          name="Spent"
        />
      </AreaChart>
    </ResponsiveContainer>
  );
}
