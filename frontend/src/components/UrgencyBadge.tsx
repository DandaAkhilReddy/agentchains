interface Props {
  score: number;
}

export default function UrgencyBadge({ score }: Props) {
  let label: string;
  let color: string;

  if (score >= 0.8) {
    label = "Critical";
    color = "bg-red-500/20 text-red-400";
  } else if (score >= 0.6) {
    label = "High";
    color = "bg-orange-500/20 text-orange-400";
  } else if (score >= 0.3) {
    label = "Medium";
    color = "bg-yellow-500/20 text-yellow-400";
  } else {
    label = "Low";
    color = "bg-zinc-500/20 text-zinc-400";
  }

  return (
    <span className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${color}`}>
      {label}
    </span>
  );
}
