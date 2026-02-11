interface Props {
  score: number;
}

export default function UrgencyBadge({ score }: Props) {
  let label: string;
  let color: string;

  if (score >= 0.8) {
    label = "Critical";
    color = "bg-[rgba(239,68,68,0.15)] text-[#ef4444] shadow-[0_0_8px_rgba(239,68,68,0.3)] pulse-dot";
  } else if (score >= 0.6) {
    label = "High";
    color = "bg-[rgba(249,115,22,0.15)] text-[#f97316] shadow-[0_0_8px_rgba(249,115,22,0.25)]";
  } else if (score >= 0.3) {
    label = "Medium";
    color = "bg-[rgba(234,179,8,0.15)] text-[#eab308] shadow-[0_0_8px_rgba(234,179,8,0.2)]";
  } else {
    label = "Low";
    color = "bg-[rgba(100,116,139,0.15)] text-[#94a3b8] shadow-[0_0_6px_rgba(100,116,139,0.15)]";
  }

  return (
    <span className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${color}`}>
      {label}
    </span>
  );
}
