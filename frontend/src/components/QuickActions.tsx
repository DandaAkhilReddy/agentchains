import { Bot, Store } from "lucide-react";

interface Props {
  onNavigate: (tab: string) => void;
}

export default function QuickActions({ onNavigate }: Props) {
  const actions = [
    { label: "View Agents", icon: Bot, tab: "agents" },
    { label: "Browse Listings", icon: Store, tab: "listings" },
  ];

  return (
    <div className="flex gap-3">
      {actions.map((action) => (
        <button
          key={action.label}
          onClick={() => onNavigate(action.tab)}
          className="glass-card glow-hover px-4 py-2.5 text-sm text-text-secondary hover:text-text-primary flex items-center gap-2 group"
        >
          <action.icon size={16} className="group-hover:text-primary transition-colors" />
          {action.label}
        </button>
      ))}
    </div>
  );
}
