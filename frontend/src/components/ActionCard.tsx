import { DollarSign, Eye, Globe, Play, Tag } from "lucide-react";
import Badge from "./Badge";
import type { WebMCPAction } from "../hooks/useActions";

/* ── Tag → Badge variant mapping ── */

const TAG_VARIANTS: Record<string, string> = {
  automation: "blue",
  scraping: "purple",
  ai: "cyan",
  data: "amber",
  finance: "green",
  security: "red",
};

function tagVariant(tag: string): string {
  return TAG_VARIANTS[tag.toLowerCase()] ?? "gray";
}

/* ── Status color ── */

function statusColor(status: string): string {
  const map: Record<string, string> = {
    active: "#34d399",
    inactive: "#94a3b8",
    deprecated: "#f87171",
    beta: "#fbbf24",
  };
  return map[status] ?? "#94a3b8";
}

/* ── Component ── */

interface Props {
  action: WebMCPAction;
  onExecute: (id: string) => void;
}

export default function ActionCard({ action, onExecute }: Props) {
  const color = statusColor(action.status);

  return (
    <div
      className="group relative flex flex-col overflow-hidden rounded-2xl border transition-all duration-300 hover:-translate-y-1"
      style={{
        backgroundColor: "#141928",
        borderColor: "rgba(96,165,250,0.12)",
      }}
      onMouseEnter={(e) => {
        (e.currentTarget as HTMLDivElement).style.borderColor =
          "rgba(96,165,250,0.3)";
        (e.currentTarget as HTMLDivElement).style.boxShadow =
          "0 0 24px rgba(96,165,250,0.08)";
      }}
      onMouseLeave={(e) => {
        (e.currentTarget as HTMLDivElement).style.borderColor =
          "rgba(96,165,250,0.12)";
        (e.currentTarget as HTMLDivElement).style.boxShadow = "none";
      }}
    >
      {/* Top accent bar */}
      <div
        className="h-[3px] w-full"
        style={{
          background:
            "linear-gradient(90deg, #60a5fa, #60a5fa80, transparent)",
        }}
      />

      {/* Card content */}
      <div className="flex flex-1 flex-col p-5">
        {/* Title + status dot */}
        <div className="mb-3 flex items-start gap-3">
          <div className="flex-shrink-0 rounded-xl bg-[rgba(96,165,250,0.1)] p-2.5 shadow-[0_0_12px_rgba(96,165,250,0.15)]">
            <Globe className="h-4 w-4 text-[#60a5fa]" />
          </div>
          <div className="min-w-0 flex-1">
            <h4 className="line-clamp-2 text-sm font-semibold leading-snug text-[#e2e8f0] group-hover:text-white transition-colors">
              {action.title}
            </h4>
            {action.domain && (
              <span className="mt-0.5 block text-[11px] text-[#64748b] truncate">
                {action.domain}
              </span>
            )}
          </div>
          <span
            className="mt-1 flex-shrink-0 h-2 w-2 rounded-full"
            style={{ backgroundColor: color }}
            title={action.status}
          />
        </div>

        {/* Description */}
        {action.description && (
          <p className="mb-4 line-clamp-2 text-xs leading-relaxed text-[#64748b]">
            {action.description}
          </p>
        )}

        {/* Price + Access count */}
        <div className="mb-3 flex items-center justify-between">
          <span className="flex items-center gap-1 text-lg font-bold font-mono tracking-tight text-[#34d399]">
            <DollarSign className="h-4 w-4" />
            {action.price_per_execution.toFixed(2)}
          </span>
          <span className="flex items-center gap-1 text-xs text-[#64748b]">
            <Eye className="h-3 w-3" />
            {action.access_count.toLocaleString()}
          </span>
        </div>

        {/* Tags */}
        {action.tags.length > 0 && (
          <div className="mb-4 flex flex-wrap gap-1.5">
            {action.tags.slice(0, 4).map((tag) => (
              <Badge key={tag} label={tag} variant={tagVariant(tag)} />
            ))}
            {action.tags.length > 4 && (
              <span className="flex items-center gap-0.5 rounded-full px-1.5 py-0.5 text-[10px] text-[#64748b]">
                <Tag className="h-2.5 w-2.5" />+{action.tags.length - 4}
              </span>
            )}
          </div>
        )}

        {/* Spacer */}
        <div className="flex-1" />

        {/* Execute button */}
        <button
          onClick={() => onExecute(action.id)}
          className="mt-2 flex w-full items-center justify-center gap-2 rounded-xl px-4 py-2.5 text-sm font-semibold text-white opacity-0 transition-all duration-300 group-hover:opacity-100 group-hover:translate-y-0 translate-y-2"
          style={{
            background: "linear-gradient(135deg, #60a5fa, #34d399)",
            boxShadow: "0 0 0px rgba(96,165,250,0)",
          }}
          onMouseEnter={(e) => {
            (e.currentTarget as HTMLButtonElement).style.boxShadow =
              "0 0 24px rgba(96,165,250,0.35), 0 0 48px rgba(52,211,153,0.2)";
          }}
          onMouseLeave={(e) => {
            (e.currentTarget as HTMLButtonElement).style.boxShadow =
              "0 0 0px rgba(96,165,250,0)";
          }}
        >
          <Play className="h-4 w-4" />
          Execute
        </button>
      </div>
    </div>
  );
}
