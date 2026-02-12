import { Search } from "lucide-react";

interface Section {
  id: string;
  title: string;
  icon?: string;
}

interface Props {
  sections: Section[];
  activeId: string;
  onSelect: (id: string) => void;
  searchQuery: string;
  onSearch: (q: string) => void;
}

export default function DocsSidebar({ sections, activeId, onSelect, searchQuery, onSearch }: Props) {
  const filtered = sections.filter((s) =>
    s.title.toLowerCase().includes(searchQuery.toLowerCase())
  );

  return (
    <div className="border-r border-border-subtle pr-4 hidden lg:block">
      <div className="sticky top-4 space-y-4">
        <div className="relative">
          <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-text-muted" />
          <input
            type="text"
            placeholder="Search docs..."
            value={searchQuery}
            onChange={(e) => onSearch(e.target.value)}
            className="w-full rounded-lg bg-surface-overlay/50 border border-border-subtle py-1.5 pl-8 pr-3 text-xs text-text-primary placeholder:text-text-muted focus:border-primary/30 focus:outline-none"
          />
        </div>
        <nav className="space-y-0.5">
          {filtered.map((section) => (
            <button
              key={section.id}
              onClick={() => onSelect(section.id)}
              className={`w-full text-left rounded-lg px-3 py-1.5 text-xs font-medium transition-colors ${
                activeId === section.id
                  ? "bg-primary-glow text-primary"
                  : "text-text-secondary hover:text-text-primary hover:bg-surface-overlay/50"
              }`}
            >
              {section.title}
            </button>
          ))}
        </nav>
      </div>
    </div>
  );
}
