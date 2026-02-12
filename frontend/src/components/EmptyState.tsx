import type { LucideIcon } from "lucide-react";
import { Inbox } from "lucide-react";

interface Props {
  message?: string;
  icon?: LucideIcon;
  action?: { label: string; onClick: () => void };
}

export default function EmptyState({
  message = "No data found",
  icon: Icon = Inbox,
  action,
}: Props) {
  return (
    <div className="flex flex-col items-center justify-center rounded-xl border border-dashed border-border-subtle py-16">
      <div className="mb-3 rounded-2xl bg-surface-overlay/50 p-4">
        <Icon className="h-8 w-8 text-text-muted animate-float" />
      </div>
      <p className="text-sm text-text-secondary">{message}</p>
      {action && (
        <button
          onClick={action.onClick}
          className="btn-primary mt-4 px-4 py-2 text-sm"
        >
          {action.label}
        </button>
      )}
    </div>
  );
}
