interface Props {
  latencyMs: number;
  maxMs?: number;
  showLabel?: boolean;
  size?: "sm" | "md";
  className?: string;
}

function barColor(ms: number): string {
  if (ms < 50) return "#16a34a";
  if (ms <= 100) return "#3b82f6";
  if (ms <= 300) return "#d97706";
  return "#dc2626";
}

/** Horizontal latency bar with color gradient (green -> yellow -> red). */
export default function LatencyBar({
  latencyMs,
  maxMs = 500,
  showLabel = true,
  size = "md",
  className = "",
}: Props) {
  const pct = Math.min((latencyMs / maxMs) * 100, 100);
  const color = barColor(latencyMs);
  const trackHeight = size === "sm" ? "h-1.5" : "h-2";

  return (
    <div className={`flex items-center gap-2 ${className}`}>
      <div
        className={`${trackHeight} flex-1 rounded-full bg-surface-overlay overflow-hidden`}
      >
        <div
          className="h-full rounded-full transition-all duration-500 animate-grow-bar"
          style={{
            width: `${pct}%`,
            backgroundColor: color,
          }}
        />
      </div>
      {showLabel && (
        <span
          className="text-xs font-mono font-medium shrink-0"
          style={{ color }}
        >
          {latencyMs}ms
        </span>
      )}
    </div>
  );
}
