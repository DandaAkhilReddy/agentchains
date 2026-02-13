import type { EndpointParam } from "../../pages/docs-sections";

interface Props {
  params: EndpointParam[];
}

export default function ParamList({ params }: Props) {
  return (
    <div className="space-y-0 divide-y divide-border-subtle">
      {params.map((p) => (
        <div key={p.name} className="py-2.5 first:pt-0">
          <div className="flex items-center gap-2 mb-0.5">
            <code className="text-xs font-mono font-semibold text-text-primary">
              {p.name}
            </code>
            <span className="text-[10px] text-text-muted">{p.type}</span>
            {p.required && (
              <span className="text-[9px] font-semibold uppercase tracking-wider text-danger bg-danger/10 rounded px-1 py-0.5">
                Required
              </span>
            )}
          </div>
          <p className="text-xs text-text-secondary leading-relaxed">
            {p.desc}
          </p>
        </div>
      ))}
    </div>
  );
}
