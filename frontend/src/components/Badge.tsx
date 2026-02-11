const VARIANTS: Record<string, string> = {
  green:  "bg-[rgba(16,185,129,0.15)] text-[#10b981] shadow-[0_0_8px_rgba(16,185,129,0.15)]",
  blue:   "bg-[rgba(0,212,255,0.15)] text-[#00d4ff] shadow-[0_0_8px_rgba(0,212,255,0.15)]",
  purple: "bg-[rgba(139,92,246,0.15)] text-[#8b5cf6] shadow-[0_0_8px_rgba(139,92,246,0.15)]",
  cyan:   "bg-[rgba(0,212,255,0.15)] text-[#00d4ff] shadow-[0_0_8px_rgba(0,212,255,0.15)]",
  amber:  "bg-[rgba(245,158,11,0.15)] text-[#f59e0b] shadow-[0_0_8px_rgba(245,158,11,0.15)]",
  red:    "bg-[rgba(239,68,68,0.15)] text-[#ef4444] shadow-[0_0_8px_rgba(239,68,68,0.15)]",
  rose:   "bg-[rgba(244,63,94,0.15)] text-[#f43f5e] shadow-[0_0_8px_rgba(244,63,94,0.15)]",
  orange: "bg-[rgba(249,115,22,0.15)] text-[#f97316] shadow-[0_0_8px_rgba(249,115,22,0.15)]",
  yellow: "bg-[rgba(234,179,8,0.15)] text-[#eab308] shadow-[0_0_8px_rgba(234,179,8,0.15)]",
  gray:   "bg-[rgba(100,116,139,0.15)] text-[#94a3b8]",
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
