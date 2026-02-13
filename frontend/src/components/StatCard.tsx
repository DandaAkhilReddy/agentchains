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

/** Map a sparkColor / generic color hint to icon background + glow styles */
function getIconStyles(sparkColor?: string) {
  if (sparkColor?.includes("34d399") || sparkColor?.includes("green")) {
    return {
      bg: "rgba(52,211,153,0.15)",
      text: "#34d399",
      shadow: "0 0 12px rgba(52,211,153,0.25)",
    };
  }
  if (sparkColor?.includes("a78bfa") || sparkColor?.includes("purple")) {
    return {
      bg: "rgba(167,139,250,0.15)",
      text: "#a78bfa",
      shadow: "0 0 12px rgba(167,139,250,0.25)",
    };
  }
  if (sparkColor?.includes("f59e0b") || sparkColor?.includes("amber") || sparkColor?.includes("yellow")) {
    return {
      bg: "rgba(245,158,11,0.15)",
      text: "#f59e0b",
      shadow: "0 0 12px rgba(245,158,11,0.25)",
    };
  }
  if (sparkColor?.includes("f87171") || sparkColor?.includes("red")) {
    return {
      bg: "rgba(248,113,113,0.15)",
      text: "#f87171",
      shadow: "0 0 12px rgba(248,113,113,0.25)",
    };
  }
  // Default: electric blue
  return {
    bg: "rgba(96,165,250,0.15)",
    text: "#60a5fa",
    shadow: "0 0 12px rgba(96,165,250,0.25)",
  };
}

export default function StatCard({
  label, value, subtitle, icon: Icon, trend, trendValue,
  sparkData, sparkColor, progress, progressColor, onClick,
}: Props) {
  const TrendIcon = trend === "up" ? TrendingUp : trend === "down" ? TrendingDown : Minus;
  const trendTextColor =
    trend === "up" ? "text-[#34d399]" : trend === "down" ? "text-[#f87171]" : "text-[#64748b]";

  const iconStyles = getIconStyles(sparkColor);

  return (
    <div
      className={[
        "relative rounded-2xl border bg-[#141928] p-5",
        "border-[rgba(255,255,255,0.06)]",
        "transition-all duration-200 ease-out",
        "hover:border-[rgba(96,165,250,0.3)] hover:shadow-[0_0_20px_rgba(96,165,250,0.1)]",
        onClick ? "cursor-pointer active:scale-[0.98]" : "",
      ].join(" ")}
      onClick={onClick}
    >
      {/* Header row: label + icon */}
      <div className="flex items-center justify-between">
        <p className="text-xs font-semibold uppercase tracking-widest text-[#94a3b8]">
          {label}
        </p>
        {Icon && (
          <div
            className="flex h-8 w-8 items-center justify-center rounded-full"
            style={{
              backgroundColor: iconStyles.bg,
              boxShadow: iconStyles.shadow,
            }}
          >
            <Icon className="h-4 w-4" style={{ color: iconStyles.text }} />
          </div>
        )}
      </div>

      {/* Value row */}
      <div className="mt-3 flex items-end justify-between">
        <div>
          {progress !== undefined ? (
            <ProgressRing value={progress} size={56} color={progressColor || "cyan"} />
          ) : (
            <span className="text-2xl font-bold text-[#e2e8f0]" style={{ fontFamily: "var(--font-mono, ui-monospace, monospace)" }}>
              {typeof value === "number" ? <AnimatedCounter value={value} glow /> : value}
            </span>
          )}
          {trend && trendValue && (
            <span className={`mt-1.5 flex items-center gap-0.5 text-xs font-medium ${trendTextColor}`}>
              <TrendIcon className="h-3 w-3" />
              {trendValue}
            </span>
          )}
          {subtitle && (
            <p className="mt-1 text-xs text-[#64748b]">{subtitle}</p>
          )}
        </div>
        {sparkData && sparkData.length > 1 && (
          <MiniChart data={sparkData} color={sparkColor || "#60a5fa"} />
        )}
      </div>
    </div>
  );
}
