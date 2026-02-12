interface Props {
  score: number;
}

export default function UrgencyBadge({ score }: Props) {
  let label: string;
  let color: string;

  if (score >= 0.8) {
    label = "Critical";
    color = "bg-[rgba(220,38,38,0.08)] text-[#dc2626] shadow-[0_0_8px_rgba(220,38,38,0.15)] pulse-dot";
  } else if (score >= 0.6) {
    label = "High";
    color = "bg-[rgba(249,115,22,0.08)] text-[#ea580c] shadow-[0_0_8px_rgba(249,115,22,0.12)]";
  } else if (score >= 0.3) {
    label = "Medium";
    color = "bg-[rgba(202,138,4,0.08)] text-[#ca8a04] shadow-[0_0_8px_rgba(202,138,4,0.1)]";
  } else {
    label = "Low";
    color = "bg-[rgba(100,116,139,0.08)] text-[#64748b] shadow-[0_0_6px_rgba(100,116,139,0.08)]";
  }

  return (
    <span className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${color}`}>
      {label}
    </span>
  );
}
