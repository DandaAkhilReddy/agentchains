const VARIANTS: Record<string, string> = {
  green:
    "bg-[rgba(52,211,153,0.1)] text-[#34d399] border border-[rgba(52,211,153,0.2)] shadow-[0_0_8px_rgba(52,211,153,0.08)]",
  blue:
    "bg-[rgba(96,165,250,0.1)] text-[#60a5fa] border border-[rgba(96,165,250,0.2)] shadow-[0_0_8px_rgba(96,165,250,0.08)]",
  purple:
    "bg-[rgba(167,139,250,0.1)] text-[#a78bfa] border border-[rgba(167,139,250,0.2)] shadow-[0_0_8px_rgba(167,139,250,0.08)]",
  cyan:
    "bg-[rgba(34,211,238,0.1)] text-[#22d3ee] border border-[rgba(34,211,238,0.2)] shadow-[0_0_8px_rgba(34,211,238,0.08)]",
  amber:
    "bg-[rgba(251,191,36,0.1)] text-[#fbbf24] border border-[rgba(251,191,36,0.2)] shadow-[0_0_8px_rgba(251,191,36,0.08)]",
  red:
    "bg-[rgba(248,113,113,0.1)] text-[#f87171] border border-[rgba(248,113,113,0.2)] shadow-[0_0_8px_rgba(248,113,113,0.08)]",
  rose:
    "bg-[rgba(251,113,133,0.1)] text-[#fb7185] border border-[rgba(251,113,133,0.2)] shadow-[0_0_8px_rgba(251,113,133,0.08)]",
  orange:
    "bg-[rgba(251,146,60,0.1)] text-[#fb923c] border border-[rgba(251,146,60,0.2)] shadow-[0_0_8px_rgba(251,146,60,0.08)]",
  yellow:
    "bg-[rgba(250,204,21,0.1)] text-[#facc15] border border-[rgba(250,204,21,0.2)] shadow-[0_0_8px_rgba(250,204,21,0.08)]",
  gray:
    "bg-[rgba(148,163,184,0.1)] text-[#94a3b8] border border-[rgba(148,163,184,0.2)]",
  pink:
    "bg-[rgba(244,114,182,0.1)] text-[#f472b6] border border-[rgba(244,114,182,0.2)] shadow-[0_0_8px_rgba(244,114,182,0.08)]",
  indigo:
    "bg-[rgba(129,140,248,0.1)] text-[#818cf8] border border-[rgba(129,140,248,0.2)] shadow-[0_0_8px_rgba(129,140,248,0.08)]",
  emerald:
    "bg-[rgba(52,211,153,0.1)] text-[#34d399] border border-[rgba(52,211,153,0.2)] shadow-[0_0_8px_rgba(52,211,153,0.08)]",
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
