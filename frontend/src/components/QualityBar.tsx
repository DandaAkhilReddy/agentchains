interface Props {
  score: number;
}

export default function QualityBar({ score }: Props) {
  const pct = Math.round(score * 100);

  // Gradient fill color based on score range
  const barColor =
    score >= 0.7
      ? "bg-gradient-to-r from-[#34d399] to-[#22d3ee]"
      : score >= 0.4
        ? "bg-gradient-to-r from-[#fbbf24] to-[#fb923c]"
        : "bg-gradient-to-r from-[#f87171] to-[#fb923c]";

  // Subtle glow for high quality scores
  const glowClass =
    score >= 0.7
      ? "shadow-[0_0_8px_rgba(52,211,153,0.3)]"
      : "";

  return (
    <div className="flex items-center gap-2">
      <div
        className={`h-1.5 w-16 overflow-hidden rounded-full bg-[#1a2035] ${glowClass}`}
      >
        <div
          className={`h-full rounded-full ${barColor} transition-all duration-500`}
          style={{ width: `${pct}%` }}
        />
      </div>
      <span className="text-xs text-[#94a3b8]">{pct}%</span>
    </div>
  );
}
