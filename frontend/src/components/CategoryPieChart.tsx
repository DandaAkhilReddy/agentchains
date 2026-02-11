import { PieChart, Pie, Cell, ResponsiveContainer, Tooltip } from "recharts";

const COLORS = ["#00d4ff", "#8b5cf6", "#10b981", "#f59e0b", "#f43f5e"];

const CHART_TOOLTIP_STYLE = {
  backgroundColor: "rgba(13, 17, 23, 0.95)",
  border: "1px solid rgba(0, 212, 255, 0.2)",
  borderRadius: 12,
  color: "#e2e8f0",
  fontSize: 12,
};

interface Props {
  data: Record<string, number>;
}

export default function CategoryPieChart({ data }: Props) {
  const entries = Object.entries(data)
    .map(([name, value]) => ({ name, value }))
    .sort((a, b) => b.value - a.value);

  if (!entries.length) {
    return (
      <div className="flex h-48 items-center justify-center text-text-muted">
        No category data
      </div>
    );
  }

  return (
    <ResponsiveContainer width="100%" height={200}>
      <PieChart>
        <Pie
          data={entries}
          cx="50%"
          cy="50%"
          innerRadius={50}
          outerRadius={80}
          paddingAngle={2}
          dataKey="value"
        >
          {entries.map((_, index) => (
            <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
          ))}
        </Pie>
        <Tooltip
          contentStyle={CHART_TOOLTIP_STYLE}
          formatter={(value: number | undefined) => [`$${(value ?? 0).toFixed(4)}`, ""]}
        />
      </PieChart>
    </ResponsiveContainer>
  );
}
