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
          className="flex items-center gap-2 rounded-lg border border-zinc-800 bg-zinc-900 px-4 py-2.5 text-sm text-zinc-300 transition-all hover:border-zinc-700 hover:text-white"
        >
          <action.icon size={16} />
          {action.label}
        </button>
      ))}
    </div>
  );
}
