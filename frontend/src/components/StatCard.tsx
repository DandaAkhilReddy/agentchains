import type { LucideIcon } from "lucide-react";
import { TrendingUp, TrendingDown, Minus } from "lucide-react";
import AnimatedCounter from "./AnimatedCounter";
import MiniChart from "./MiniChart";
import ProgressRing from "./ProgressRing";

interface Props {
  label: string;
  value: string | number;
  subtitle?: string;
  icon?: LucideIcon;
  trend?: "up" | "down" | "flat";
  trendValue?: string;
  sparkData?: number[];
  sparkColor?: string;
  progress?: number;
  progressColor?: string;
  onClick?: () => void;
}

export default function StatCard({
  label, value, subtitle, icon: Icon, trend, trendValue,
  sparkData, sparkColor, progress, progressColor, onClick,
}: Props) {
  const TrendIcon = trend === "up" ? TrendingUp : trend === "down" ? TrendingDown : Minus;
  const trendColor = trend === "up" ? "text-success" : trend === "down" ? "text-danger" : "text-text-muted";

  return (
    <div
      className={`glass-card gradient-border-card glow-hover card-hover-lift p-5 ${onClick ? "cursor-pointer" : ""}`}
      onClick={onClick}
    >
      <div className="flex items-center justify-between">
        <p className="text-xs font-semibold uppercase tracking-widest text-text-muted">
          {label}
        </p>
        {Icon && (
          <div className="rounded-lg bg-primary-glow p-2">
            <Icon className="h-4 w-4 text-primary" />
          </div>
        )}
      </div>
      <div className="mt-2 flex items-end justify-between">
        <div>
          {progress !== undefined ? (
            <ProgressRing value={progress} size={56} color={progressColor || "cyan"} />
          ) : (
            <span className="text-2xl font-semibold tracking-tight" style={{ fontFamily: "var(--font-mono)" }}>
              {typeof value === "number" ? <AnimatedCounter value={value} /> : value}
            </span>
          )}
          {trend && trendValue && (
            <span className={`mt-1 flex items-center gap-0.5 text-xs ${trendColor}`}>
              <TrendIcon className="h-3 w-3" />
              {trendValue}
            </span>
          )}
          {subtitle && (
            <p className="mt-1 text-xs text-text-muted">{subtitle}</p>
          )}
        </div>
        {sparkData && sparkData.length > 1 && (
          <MiniChart data={sparkData} color={sparkColor} />
        )}
      </div>
    </div>
  );
}
