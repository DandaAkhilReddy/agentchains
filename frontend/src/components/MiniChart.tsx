import { useMemo } from "react";
import { AreaChart, Area, ResponsiveContainer } from "recharts";

interface Props {
  data: number[];
  color?: string;
  height?: number;
}

export default function MiniChart({ data, color = "#60a5fa", height = 32 }: Props) {
  const gradientId = useMemo(
    () => `mg-${color.replace("#", "")}-${Math.random().toString(36).slice(2, 8)}`,
    [color],
  );

  const chartData = data.map((v, i) => ({ i, v }));

  return (
    <div style={{ width: 72, height }}>
      <ResponsiveContainer width="100%" height="100%">
        <AreaChart data={chartData} margin={{ top: 0, right: 0, bottom: 0, left: 0 }}>
          <defs>
            <linearGradient id={gradientId} x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor={color} stopOpacity={0.35} />
              <stop offset="50%" stopColor={color} stopOpacity={0.12} />
              <stop offset="100%" stopColor={color} stopOpacity={0} />
            </linearGradient>
            <filter id={`glow-${gradientId}`}>
              <feGaussianBlur stdDeviation="2" result="blur" />
              <feMerge>
                <feMergeNode in="blur" />
                <feMergeNode in="SourceGraphic" />
              </feMerge>
            </filter>
          </defs>
          <Area
            type="monotone"
            dataKey="v"
            stroke={color}
            strokeWidth={1.5}
            fill={`url(#${gradientId})`}
            isAnimationActive={false}
            style={{ filter: `url(#glow-${gradientId})` }}
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}
