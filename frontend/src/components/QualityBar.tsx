interface Props {
  score: number;
}

export default function QualityBar({ score }: Props) {
  const color =
    score >= 0.7
      ? "bg-emerald-500"
      : score >= 0.4
        ? "bg-yellow-500"
        : "bg-red-500";

  const glowClass = score >= 0.7 ? "shadow-[0_0_6px_rgba(16,185,129,0.3)]" : "";

  return (
    <div className="flex items-center gap-2">
      <div className={`h-1.5 w-16 overflow-hidden rounded-full bg-surface-overlay ${glowClass}`}>
        <div
          className={`h-full rounded-full ${color}`}
          style={{ width: `${Math.round(score * 100)}%` }}
        />
      </div>
      <span className="text-xs text-text-secondary">{Math.round(score * 100)}%</span>
    </div>
  );
}
