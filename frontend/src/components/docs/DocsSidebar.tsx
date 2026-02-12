import { Search } from "lucide-react";
import type { SidebarGroup } from "../../pages/docs-sections";

interface Section {
  id: string;
  title: string;
}

interface Props {
  sections: Section[];
  groups?: SidebarGroup[];
  activeId: string;
  onSelect: (id: string) => void;
  searchQuery: string;
  onSearch: (q: string) => void;
}

export default function DocsSidebar({ sections, groups, activeId, onSelect, searchQuery, onSearch }: Props) {
  const query = searchQuery.toLowerCase();
  const matchesSearch = (s: Section) => s.title.toLowerCase().includes(query);

  // Build a map for quick lookup
  const sectionMap = new Map(sections.map((s) => [s.id, s]));

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
        <nav className="space-y-3 max-h-[calc(100vh-160px)] overflow-y-auto">
          {groups ? (
            // Grouped navigation
            groups.map((group) => {
              const groupSections = group.sectionIds
                .map((id) => sectionMap.get(id))
                .filter((s): s is Section => !!s && matchesSearch(s));

              if (groupSections.length === 0) return null;

              return (
                <div key={group.label}>
                  <div className="text-[10px] font-semibold uppercase tracking-wider text-text-muted px-3 py-1">
                    {group.label}
                  </div>
                  <div className="space-y-0.5">
                    {groupSections.map((section) => (
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
                  </div>
                </div>
              );
            })
          ) : (
            // Flat fallback
            sections.filter(matchesSearch).map((section) => (
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
            ))
          )}
        </nav>
      </div>
    </div>
  );
}
