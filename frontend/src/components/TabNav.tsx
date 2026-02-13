import type { LucideIcon } from "lucide-react";

export interface Tab {
  id: string;
  label: string;
  icon?: LucideIcon;
}

interface Props {
  tabs: Tab[];
  activeTab: string;
  onTabChange: (id: string) => void;
}

export default function TabNav({ tabs, activeTab, onTabChange }: Props) {
  return (
    <nav className="border-b border-[rgba(255,255,255,0.06)]">
      <div className="mx-auto flex max-w-7xl gap-1 px-6">
        {tabs.map((tab) => {
          const Icon = tab.icon;
          const isActive = activeTab === tab.id;
          return (
            <button
              key={tab.id}
              onClick={() => onTabChange(tab.id)}
              className={`relative flex items-center gap-2 px-4 py-3 text-sm font-medium transition-all duration-200 ${
                isActive
                  ? "text-[#60a5fa]"
                  : "text-[#64748b] hover:text-[#94a3b8]"
              }`}
            >
              {Icon && <Icon className={`h-4 w-4 ${isActive ? "text-[#60a5fa]" : ""}`} />}
              {tab.label}
              {isActive && (
                <span className="absolute bottom-0 left-0 right-0 h-0.5 rounded-full bg-[#60a5fa] shadow-[0_2px_8px_rgba(96,165,250,0.3)]" />
              )}
            </button>
          );
        })}
      </div>
    </nav>
  );
}
