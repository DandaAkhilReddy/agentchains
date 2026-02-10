import { AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer } from "recharts";

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
            <stop offset="5%" stopColor="#10b981" stopOpacity={0.3} />
            <stop offset="95%" stopColor="#10b981" stopOpacity={0} />
          </linearGradient>
          <linearGradient id="spentGradient" x1="0" y1="0" x2="0" y2="1">
            <stop offset="5%" stopColor="#ef4444" stopOpacity={0.3} />
            <stop offset="95%" stopColor="#ef4444" stopOpacity={0} />
          </linearGradient>
        </defs>
        <XAxis
          dataKey="date"
          tick={{ fill: "#71717a", fontSize: 11 }}
          axisLine={false}
          tickLine={false}
        />
        <YAxis
          tick={{ fill: "#71717a", fontSize: 11 }}
          axisLine={false}
          tickLine={false}
          tickFormatter={(v) => `$${v}`}
        />
        <Tooltip
          contentStyle={{
            background: "#18181b",
            border: "1px solid #3f3f46",
            borderRadius: 8,
            color: "#fafafa",
            fontSize: 12,
          }}
          formatter={(value: number | undefined) => [`$${(value ?? 0).toFixed(4)}`, ""]}
        />
        <Area
          type="monotone"
          dataKey="earned"
          stroke="#10b981"
          fill="url(#earnedGradient)"
          strokeWidth={2}
          name="Earned"
        />
        <Area
          type="monotone"
          dataKey="spent"
          stroke="#ef4444"
          fill="url(#spentGradient)"
          strokeWidth={2}
          name="Spent"
        />
      </AreaChart>
    </ResponsiveContainer>
  );
}
