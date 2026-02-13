import { Bot, Store } from "lucide-react";

interface Props {
  onNavigate: (tab: string) => void;
}

export default function QuickActions({ onNavigate }: Props) {
  const actions = [
    {
      label: "View Agents",
      icon: Bot,
      tab: "agents",
      iconColor: "text-[#60a5fa]",
      iconBg: "bg-[rgba(96,165,250,0.1)]",
    },
    {
      label: "Browse Listings",
      icon: Store,
      tab: "listings",
      iconColor: "text-[#a78bfa]",
      iconBg: "bg-[rgba(167,139,250,0.1)]",
    },
  ];

  return (
    <div className="flex gap-3">
      {actions.map((action) => (
        <button
          key={action.label}
          onClick={() => onNavigate(action.tab)}
          className="flex items-center gap-2.5 rounded-xl bg-[#141928] border border-[rgba(255,255,255,0.06)] px-4 py-2.5 text-sm text-[#94a3b8] transition-all duration-200 hover:text-[#e2e8f0] hover:border-[rgba(96,165,250,0.2)] hover:shadow-[0_0_16px_rgba(96,165,250,0.08)] group"
        >
          <span
            className={`inline-flex items-center justify-center rounded-lg p-1.5 ${action.iconBg} transition-shadow duration-200 group-hover:shadow-[0_0_8px_rgba(96,165,250,0.15)]`}
          >
            <action.icon size={14} className={`${action.iconColor} transition-colors`} />
          </span>
          {action.label}
        </button>
      ))}
    </div>
  );
}
