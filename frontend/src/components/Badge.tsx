const VARIANTS: Record<string, string> = {
  green: "bg-emerald-500/10 text-emerald-400",
  yellow: "bg-yellow-500/10 text-yellow-400",
  red: "bg-red-500/10 text-red-400",
  blue: "bg-blue-500/10 text-blue-400",
  purple: "bg-purple-500/10 text-purple-400",
  cyan: "bg-cyan-500/10 text-cyan-400",
  amber: "bg-amber-500/10 text-amber-400",
  rose: "bg-rose-500/10 text-rose-400",
  orange: "bg-orange-500/10 text-orange-400",
  gray: "bg-zinc-500/10 text-zinc-400",
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
