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

  return (
    <div className="flex items-center gap-2">
      <div className="h-1.5 w-16 overflow-hidden rounded-full bg-zinc-800">
        <div
          className={`h-full rounded-full ${color}`}
          style={{ width: `${Math.round(score * 100)}%` }}
        />
      </div>
      <span className="text-xs text-zinc-500">{Math.round(score * 100)}%</span>
    </div>
  );
}
