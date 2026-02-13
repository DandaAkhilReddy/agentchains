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
    <div className="bg-[#0d1220] border-r border-[rgba(255,255,255,0.06)] pr-0 hidden md:block">
      <div className="sticky top-[4.5rem] p-4 space-y-4">
        {/* Search input */}
        <div className="relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-[#64748b]" />
          <input
            type="text"
            placeholder="Search docs..."
            value={searchQuery}
            onChange={(e) => onSearch(e.target.value)}
            className="w-full rounded-lg bg-[#141928] border border-[rgba(255,255,255,0.06)] py-2 pl-9 pr-3 text-xs text-[#e2e8f0] placeholder:text-[#64748b] focus:border-[rgba(96,165,250,0.4)] focus:shadow-[0_0_0_2px_rgba(96,165,250,0.1)] focus:outline-none transition-all"
          />
        </div>

        {/* Navigation */}
        <nav className="space-y-3 max-h-[calc(100vh-160px)] overflow-y-auto scrollbar-thin">
          {groups ? (
            // Grouped navigation
            groups.map((group) => {
              const groupSections = group.sectionIds
                .map((id) => sectionMap.get(id))
                .filter((s): s is Section => !!s && matchesSearch(s));

              if (groupSections.length === 0) return null;

              return (
                <div key={group.label}>
                  <div className="text-[10px] font-bold uppercase tracking-wider text-[#64748b] px-3 py-1.5">
                    {group.label}
                  </div>
                  <div className="space-y-0.5">
                    {groupSections.map((section) => (
                      <button
                        key={section.id}
                        onClick={() => onSelect(section.id)}
                        className={`w-full text-left rounded-lg px-3 py-1.5 text-xs font-medium transition-all duration-200 ${
                          activeId === section.id
                            ? "text-[#60a5fa] bg-[rgba(96,165,250,0.08)] border-l-2 border-[#60a5fa] pl-2.5"
                            : "text-[#64748b] hover:text-[#94a3b8] hover:bg-[rgba(255,255,255,0.03)] border-l-2 border-transparent pl-2.5"
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
                className={`w-full text-left rounded-lg px-3 py-1.5 text-xs font-medium transition-all duration-200 ${
                  activeId === section.id
                    ? "text-[#60a5fa] bg-[rgba(96,165,250,0.08)] border-l-2 border-[#60a5fa] pl-2.5"
                    : "text-[#64748b] hover:text-[#94a3b8] hover:bg-[rgba(255,255,255,0.03)] border-l-2 border-transparent pl-2.5"
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
