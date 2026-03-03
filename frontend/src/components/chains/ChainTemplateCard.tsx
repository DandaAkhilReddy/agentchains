import { Play, Eye, Archive } from "lucide-react";
import type { ChainTemplate } from "../../types/chain";
import Badge, { statusVariant } from "../Badge";

interface Props {
  template: ChainTemplate;
  onView: (id: string) => void;
  onExecute: (id: string) => void;
  onArchive: (id: string) => void;
}

export default function ChainTemplateCard({ template, onView, onExecute, onArchive }: Props) {
  return (
    <div
      className="overflow-hidden rounded-2xl border transition-all hover:border-[rgba(96,165,250,0.3)]"
      style={{ backgroundColor: "#141928", borderColor: "rgba(255,255,255,0.06)" }}
    >
      <div
        className="h-[3px] w-full"
        style={{ background: "linear-gradient(90deg, #60a5fa, #a78bfa)" }}
      />
      <div className="p-4 space-y-3">
        <div className="flex items-start justify-between gap-2">
          <h3 className="text-sm font-semibold text-[#e2e8f0] line-clamp-2">
            {template.name}
          </h3>
          <Badge label={template.status} variant={statusVariant(template.status)} />
        </div>

        {template.description && (
          <p className="text-xs text-[#475569] line-clamp-2">{template.description}</p>
        )}

        <div className="flex items-center gap-4 text-xs text-[#64748b]">
          <span>{template.execution_count} runs</span>
          <span>${template.avg_cost_usd.toFixed(4)} avg</span>
          {template.tags.length > 0 && (
            <span className="truncate">{template.tags.slice(0, 3).join(", ")}</span>
          )}
        </div>

        <div className="flex items-center gap-2 pt-1">
          <button
            onClick={() => onView(template.id)}
            className="flex items-center gap-1 rounded-lg px-2.5 py-1.5 text-xs text-[#60a5fa] transition-colors hover:bg-[rgba(96,165,250,0.1)]"
          >
            <Eye className="h-3.5 w-3.5" /> View
          </button>
          <button
            onClick={() => onExecute(template.id)}
            className="flex items-center gap-1 rounded-lg px-2.5 py-1.5 text-xs text-[#34d399] transition-colors hover:bg-[rgba(52,211,153,0.1)]"
          >
            <Play className="h-3.5 w-3.5" /> Execute
          </button>
          {template.status !== "archived" && (
            <button
              onClick={() => onArchive(template.id)}
              className="ml-auto flex items-center gap-1 rounded-lg px-2.5 py-1.5 text-xs text-[#475569] transition-colors hover:text-[#f87171] hover:bg-[rgba(248,113,113,0.1)]"
            >
              <Archive className="h-3.5 w-3.5" /> Archive
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
