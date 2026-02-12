import { AreaChart, Area, ResponsiveContainer } from "recharts";

interface Props {
  data: number[];
  color?: string;
  height?: number;
}

export default function MiniChart({ data, color = "#00d4ff", height = 32 }: Props) {
  const chartData = data.map((v, i) => ({ i, v }));

  return (
    <div style={{ width: 64, height }}>
      <ResponsiveContainer width="100%" height="100%">
        <AreaChart data={chartData} margin={{ top: 0, right: 0, bottom: 0, left: 0 }}>
          <defs>
            <linearGradient id={`mg-${color.replace("#", "")}`} x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor={color} stopOpacity={0.3} />
              <stop offset="100%" stopColor={color} stopOpacity={0} />
            </linearGradient>
          </defs>
          <Area
            type="monotone"
            dataKey="v"
            stroke={color}
            strokeWidth={1.5}
            fill={`url(#mg-${color.replace("#", "")})`}
            isAnimationActive={false}
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}
