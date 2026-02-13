import type { EndpointParam } from "../../pages/docs-sections";

interface Props {
  params: EndpointParam[];
}

export default function ParamList({ params }: Props) {
  return (
    <div className="space-y-0 divide-y divide-[rgba(255,255,255,0.06)]">
      {params.map((p) => (
        <div key={p.name} className="py-2.5 first:pt-0">
          <div className="flex items-center gap-2 mb-0.5">
            <code className="text-xs font-mono font-semibold text-[#e2e8f0]">
              {p.name}
            </code>
            <span className="text-[10px] text-[#64748b]">{p.type}</span>
            {p.required && (
              <span className="text-[9px] font-semibold uppercase tracking-wider text-[#f87171] bg-[rgba(248,113,113,0.1)] border border-[rgba(248,113,113,0.2)] rounded px-1 py-0.5">
                Required
              </span>
            )}
          </div>
          <p className="text-xs text-[#94a3b8] leading-relaxed">
            {p.desc}
          </p>
        </div>
      ))}
    </div>
  );
}
