const VARIANTS: Record<string, string> = {
  green:  "bg-[rgba(22,163,74,0.08)] text-[#16a34a] shadow-[0_0_8px_rgba(22,163,74,0.08)]",
  blue:   "bg-[rgba(59,130,246,0.08)] text-[#3b82f6] shadow-[0_0_8px_rgba(59,130,246,0.08)]",
  purple: "bg-[rgba(139,92,246,0.08)] text-[#7c3aed] shadow-[0_0_8px_rgba(139,92,246,0.08)]",
  cyan:   "bg-[rgba(59,130,246,0.08)] text-[#3b82f6] shadow-[0_0_8px_rgba(59,130,246,0.08)]",
  amber:  "bg-[rgba(217,119,6,0.08)] text-[#d97706] shadow-[0_0_8px_rgba(217,119,6,0.08)]",
  red:    "bg-[rgba(220,38,38,0.08)] text-[#dc2626] shadow-[0_0_8px_rgba(220,38,38,0.08)]",
  rose:   "bg-[rgba(225,29,72,0.08)] text-[#e11d48] shadow-[0_0_8px_rgba(225,29,72,0.08)]",
  orange: "bg-[rgba(249,115,22,0.08)] text-[#ea580c] shadow-[0_0_8px_rgba(249,115,22,0.08)]",
  yellow: "bg-[rgba(202,138,4,0.08)] text-[#ca8a04] shadow-[0_0_8px_rgba(202,138,4,0.08)]",
  gray:   "bg-[rgba(100,116,139,0.08)] text-[#64748b]",
};

interface Props {
  label: string;
  variant?: keyof typeof VARIANTS;
}

export default function Badge({ label, variant = "gray" }: Props) {
  return (
    <span
      className={`inline-flex items-center rounded-full px-2 py-0.5 text-[11px] font-medium ${VARIANTS[variant] ?? VARIANTS.gray}`}
    >
      {label}
    </span>
  );
}

// Helpers to map data to badge variants
export function categoryVariant(cat: string): string {
  const map: Record<string, string> = {
    web_search: "blue",
    code_analysis: "purple",
    document_summary: "amber",
    api_response: "cyan",
    computation: "rose",
  };
  return map[cat] ?? "gray";
}

export function statusVariant(status: string): string {
  const map: Record<string, string> = {
    active: "green",
    completed: "green",
    verified: "green",
    delivered: "cyan",
    payment_confirmed: "blue",
    initiated: "gray",
    payment_pending: "yellow",
    failed: "red",
    disputed: "orange",
    inactive: "gray",
    delisted: "gray",
  };
  return map[status] ?? "gray";
}

export function agentTypeVariant(type: string): string {
  const map: Record<string, string> = {
    seller: "blue",
    buyer: "green",
    both: "purple",
  };
  return map[type] ?? "gray";
}
