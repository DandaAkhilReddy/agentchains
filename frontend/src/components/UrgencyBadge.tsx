interface Props {
  score: number;
}

export default function UrgencyBadge({ score }: Props) {
  let label: string;
  let color: string;

  if (score >= 0.8) {
    label = "Critical";
    color =
      "bg-[rgba(248,113,113,0.1)] text-[#f87171] border border-[rgba(248,113,113,0.25)] shadow-[0_0_10px_rgba(248,113,113,0.2)] pulse-dot";
  } else if (score >= 0.6) {
    label = "High";
    color =
      "bg-[rgba(248,113,113,0.08)] text-[#f87171] border border-[rgba(248,113,113,0.15)] shadow-[0_0_8px_rgba(248,113,113,0.12)]";
  } else if (score >= 0.3) {
    label = "Medium";
    color =
      "bg-[rgba(251,191,36,0.1)] text-[#fbbf24] border border-[rgba(251,191,36,0.15)] shadow-[0_0_8px_rgba(251,191,36,0.1)]";
  } else {
    label = "Low";
    color =
      "bg-[rgba(52,211,153,0.08)] text-[#34d399] border border-[rgba(52,211,153,0.15)] shadow-[0_0_6px_rgba(52,211,153,0.08)]";
  }

  return (
    <span
      className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${color}`}
    >
      {label}
    </span>
  );
}
