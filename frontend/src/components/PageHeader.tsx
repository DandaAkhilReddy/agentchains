import type { LucideIcon } from "lucide-react";
import type { ReactNode } from "react";

interface Props {
  title: string;
  subtitle?: string;
  icon?: LucideIcon;
  actions?: ReactNode;
}

export default function PageHeader({ title, subtitle, icon: Icon, actions }: Props) {
  return (
    <div className="mb-6 flex items-start justify-between">
      <div className="flex items-center gap-3">
        {Icon && (
          <div className="rounded-xl bg-[rgba(96,165,250,0.1)] p-2.5 shadow-[0_0_12px_rgba(96,165,250,0.15)]">
            <Icon className="h-5 w-5 text-[#60a5fa]" />
          </div>
        )}
        <div>
          <h1 className="text-xl font-bold tracking-tight gradient-text">{title}</h1>
          {subtitle && (
            <p className="mt-0.5 text-sm text-[#94a3b8]">{subtitle}</p>
          )}
        </div>
      </div>
      {actions && <div className="flex items-center gap-2">{actions}</div>}
    </div>
  );
}
