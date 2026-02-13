import { useState, useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  Search,
  BookOpen,
  Server,
  Plug,
  Database,
  Tag,
  LayoutGrid,
  List,
} from "lucide-react";
import PageHeader from "../components/PageHeader";
import ProgressRing from "../components/ProgressRing";
import Badge from "../components/Badge";
import { searchCatalog, fetchCDNStats, fetchMCPHealth } from "../lib/api";
import type { CatalogEntry, CDNStats, MCPHealth } from "../types/api";

/* ── Helpers ─────────────────────────────────────────────── */

function formatPrice(min: number, max: number) {
  if (min === max) return `$${min.toFixed(4)}`;
  return `$${min.toFixed(4)} – $${max.toFixed(4)}`;
}

function qualityColor(score: number): string {
  if (score >= 0.8) return "#34d399";
  if (score >= 0.5) return "#fbbf24";
  return "#f87171";
}

function qualityLabel(score: number): string {
  if (score >= 0.8) return "text-[#34d399]";
  if (score >= 0.5) return "text-[#fbbf24]";
  return "text-[#f87171]";
}

const NAMESPACE_COLORS: Record<string, string> = {
  default: "#60a5fa",
};

function namespaceColor(ns: string): string {
  if (NAMESPACE_COLORS[ns]) return NAMESPACE_COLORS[ns];
  // Generate a stable hue from the namespace string
  let hash = 0;
  for (let i = 0; i < ns.length; i++) hash = ns.charCodeAt(i) + ((hash << 5) - hash);
  const hue = ((hash % 360) + 360) % 360;
  return `hsl(${hue}, 70%, 65%)`;
}

/* ── Status Cards ────────────────────────────────────────── */

function CDNCard({ stats }: { stats: CDNStats | null }) {
  if (!stats) {
    return (
      <div className="group relative rounded-2xl border border-[rgba(96,165,250,0.12)] bg-[#141928] p-5 transition-all duration-300 hover:border-[rgba(96,165,250,0.3)] hover:shadow-[0_0_24px_rgba(96,165,250,0.08)]">
        <div className="flex items-center gap-3 mb-4">
          <div className="rounded-xl bg-[rgba(96,165,250,0.1)] p-2.5">
            <Server className="h-5 w-5 text-[#60a5fa]" />
          </div>
          <span className="text-sm font-semibold text-[#e2e8f0]">CDN Performance</span>
        </div>
        <div className="flex items-center justify-center py-6">
          <div className="h-5 w-5 animate-spin rounded-full border-2 border-[#60a5fa] border-t-transparent" />
        </div>
      </div>
    );
  }

  const total = stats.overview.total_requests || 1;
  const hitRate = ((stats.overview.tier1_hits + stats.overview.tier2_hits) / total) * 100;

  return (
    <div className="group relative rounded-2xl border border-[rgba(96,165,250,0.12)] bg-[#141928] p-5 transition-all duration-300 hover:border-[rgba(96,165,250,0.3)] hover:shadow-[0_0_24px_rgba(96,165,250,0.08)]">
      {/* Blue accent line at top */}
      <div className="absolute inset-x-0 top-0 h-[2px] rounded-t-2xl bg-gradient-to-r from-transparent via-[#60a5fa] to-transparent opacity-60" />

      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-3">
          <div className="rounded-xl bg-[rgba(96,165,250,0.1)] p-2.5 shadow-[0_0_12px_rgba(96,165,250,0.1)]">
            <Server className="h-5 w-5 text-[#60a5fa]" />
          </div>
          <div>
            <span className="text-sm font-semibold text-[#e2e8f0]">CDN Performance</span>
            <p className="text-[11px] text-[#64748b]">Cache hit rate</p>
          </div>
        </div>
        <ProgressRing value={hitRate} size={52} strokeWidth={4} color="cyan" />
      </div>

      <div className="grid grid-cols-2 gap-3">
        <div className="rounded-lg bg-[#0a0e1a] px-3 py-2">
          <div className="text-[11px] text-[#64748b] mb-0.5">Hot Cache</div>
          <div className="text-sm font-mono font-semibold text-[#e2e8f0]">
            {stats.hot_cache.entries}
            <span className="ml-1 text-[11px] text-[#64748b] font-normal">items</span>
          </div>
        </div>
        <div className="rounded-lg bg-[#0a0e1a] px-3 py-2">
          <div className="text-[11px] text-[#64748b] mb-0.5">Tier 1 Hits</div>
          <div className="text-sm font-mono font-semibold text-[#34d399]">
            {stats.overview.tier1_hits.toLocaleString()}
          </div>
        </div>
        <div className="rounded-lg bg-[#0a0e1a] px-3 py-2">
          <div className="text-[11px] text-[#64748b] mb-0.5">Tier 2 Hits</div>
          <div className="text-sm font-mono font-semibold text-[#60a5fa]">
            {stats.overview.tier2_hits.toLocaleString()}
          </div>
        </div>
        <div className="rounded-lg bg-[#0a0e1a] px-3 py-2">
          <div className="text-[11px] text-[#64748b] mb-0.5">Disk (T3)</div>
          <div className="text-sm font-mono font-semibold text-[#fbbf24]">
            {stats.overview.tier3_hits.toLocaleString()}
          </div>
        </div>
      </div>
    </div>
  );
}

function MCPCard({ health }: { health: MCPHealth | null }) {
  return (
    <div className="group relative rounded-2xl border border-[rgba(167,139,250,0.12)] bg-[#141928] p-5 transition-all duration-300 hover:border-[rgba(167,139,250,0.3)] hover:shadow-[0_0_24px_rgba(167,139,250,0.08)]">
      {/* Purple accent line at top */}
      <div className="absolute inset-x-0 top-0 h-[2px] rounded-t-2xl bg-gradient-to-r from-transparent via-[#a78bfa] to-transparent opacity-60" />

      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-3">
          <div className="rounded-xl bg-[rgba(167,139,250,0.1)] p-2.5 shadow-[0_0_12px_rgba(167,139,250,0.1)]">
            <Plug className="h-5 w-5 text-[#a78bfa]" />
          </div>
          <div>
            <span className="text-sm font-semibold text-[#e2e8f0]">MCP Server Health</span>
            <p className="text-[11px] text-[#64748b]">Protocol server</p>
          </div>
        </div>
        {health ? (
          <div className="flex items-center gap-1.5">
            <span className="relative flex h-2.5 w-2.5">
              <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-[#34d399] opacity-40" />
              <span className="relative inline-flex h-2.5 w-2.5 rounded-full bg-[#34d399]" />
            </span>
            <span className="text-xs font-medium text-[#34d399]">Active</span>
          </div>
        ) : (
          <div className="h-5 w-5 animate-spin rounded-full border-2 border-[#a78bfa] border-t-transparent" />
        )}
      </div>

      {health ? (
        <div className="grid grid-cols-3 gap-3">
          <div className="rounded-lg bg-[#0a0e1a] px-3 py-2 text-center">
            <div className="text-lg font-mono font-bold text-[#e2e8f0]">
              {health.active_sessions}
            </div>
            <div className="text-[11px] text-[#64748b]">Sessions</div>
          </div>
          <div className="rounded-lg bg-[#0a0e1a] px-3 py-2 text-center">
            <div className="text-lg font-mono font-bold text-[#e2e8f0]">
              {health.tools_count}
            </div>
            <div className="text-[11px] text-[#64748b]">Tools</div>
          </div>
          <div className="rounded-lg bg-[#0a0e1a] px-3 py-2 text-center">
            <div className="text-lg font-mono font-bold text-[#e2e8f0]">
              {health.resources_count}
            </div>
            <div className="text-[11px] text-[#64748b]">Resources</div>
          </div>
        </div>
      ) : (
        <div className="flex items-center justify-center py-4">
          <span className="text-xs text-[#64748b]">Connecting...</span>
        </div>
      )}
    </div>
  );
}

function CatalogSummaryCard({
  entries,
  total,
}: {
  entries: CatalogEntry[];
  total: number;
}) {
  const uniqueAgents = new Set(entries.map((e) => e.agent_id)).size;
  const uniqueNamespaces = new Set(entries.map((e) => e.namespace)).size;
  const activeCount = entries.filter((e) => e.status === "active").length;

  return (
    <div className="group relative rounded-2xl border border-[rgba(52,211,153,0.12)] bg-[#141928] p-5 transition-all duration-300 hover:border-[rgba(52,211,153,0.3)] hover:shadow-[0_0_24px_rgba(52,211,153,0.08)]">
      {/* Green accent line at top */}
      <div className="absolute inset-x-0 top-0 h-[2px] rounded-t-2xl bg-gradient-to-r from-transparent via-[#34d399] to-transparent opacity-60" />

      <div className="flex items-center gap-3 mb-4">
        <div className="rounded-xl bg-[rgba(52,211,153,0.1)] p-2.5 shadow-[0_0_12px_rgba(52,211,153,0.1)]">
          <Database className="h-5 w-5 text-[#34d399]" />
        </div>
        <div>
          <span className="text-sm font-semibold text-[#e2e8f0]">Data Catalog</span>
          <p className="text-[11px] text-[#64748b]">Registry overview</p>
        </div>
      </div>

      <div className="grid grid-cols-2 gap-3">
        <div className="rounded-lg bg-[#0a0e1a] px-3 py-2">
          <div className="text-[11px] text-[#64748b] mb-0.5">Total Entries</div>
          <div className="text-sm font-mono font-semibold text-[#e2e8f0]">{total}</div>
        </div>
        <div className="rounded-lg bg-[#0a0e1a] px-3 py-2">
          <div className="text-[11px] text-[#64748b] mb-0.5">Agents</div>
          <div className="text-sm font-mono font-semibold text-[#e2e8f0]">{uniqueAgents}</div>
        </div>
        <div className="rounded-lg bg-[#0a0e1a] px-3 py-2">
          <div className="text-[11px] text-[#64748b] mb-0.5">Namespaces</div>
          <div className="text-sm font-mono font-semibold text-[#e2e8f0]">{uniqueNamespaces}</div>
        </div>
        <div className="rounded-lg bg-[#0a0e1a] px-3 py-2">
          <div className="text-[11px] text-[#64748b] mb-0.5">Active</div>
          <div className="text-sm font-mono font-semibold text-[#34d399]">{activeCount}</div>
        </div>
      </div>
    </div>
  );
}

/* ── Catalog Card ────────────────────────────────────────── */

function CatalogCard({ entry }: { entry: CatalogEntry }) {
  const nsColor = namespaceColor(entry.namespace);

  return (
    <div className="group relative rounded-2xl border border-[rgba(255,255,255,0.06)] bg-[#141928] overflow-hidden transition-all duration-300 hover:-translate-y-0.5 hover:border-[rgba(255,255,255,0.12)] hover:shadow-[0_8px_32px_rgba(0,0,0,0.3)]">
      {/* Namespace-colored top accent */}
      <div className="h-[3px]" style={{ background: `linear-gradient(90deg, transparent, ${nsColor}, transparent)` }} />

      <div className="p-4">
        <div className="flex items-start justify-between mb-2.5">
          <span
            className="inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[11px] font-medium border"
            style={{
              color: nsColor,
              backgroundColor: `${nsColor}15`,
              borderColor: `${nsColor}30`,
            }}
          >
            <Tag className="h-3 w-3" />
            {entry.namespace}
          </span>
          <span className={`font-mono text-sm font-semibold ${qualityLabel(entry.quality_avg)}`}>
            {(entry.quality_avg * 100).toFixed(0)}%
          </span>
        </div>

        <h3 className="text-sm font-semibold text-[#e2e8f0] mb-1 line-clamp-1 group-hover:text-white transition-colors">
          {entry.topic}
        </h3>
        <p className="text-xs text-[#64748b] mb-3 line-clamp-2 leading-relaxed">
          {entry.description || "No description provided"}
        </p>

        <div className="flex items-center justify-between">
          <span className="text-xs font-mono text-[#94a3b8]">
            {formatPrice(entry.price_range[0], entry.price_range[1])}
          </span>
          <Badge
            label={`${entry.active_listings_count} listing${entry.active_listings_count !== 1 ? "s" : ""}`}
            variant="blue"
          />
        </div>
      </div>
    </div>
  );
}

/* ── Category Badges ─────────────────────────────────────── */

function CategoryBadges({
  entries,
  selected,
  onSelect,
}: {
  entries: CatalogEntry[];
  selected: string;
  onSelect: (ns: string) => void;
}) {
  const categories = useMemo(() => {
    const map = new Map<string, number>();
    for (const e of entries) {
      map.set(e.namespace, (map.get(e.namespace) ?? 0) + 1);
    }
    return [...map.entries()].sort((a, b) => b[1] - a[1]);
  }, [entries]);

  if (categories.length === 0) return null;

  return (
    <div className="flex flex-wrap gap-2">
      {categories.map(([ns, count]) => {
        const isActive = selected === ns;
        const color = namespaceColor(ns);
        return (
          <button
            key={ns}
            onClick={() => onSelect(isActive ? "" : ns)}
            className="inline-flex items-center gap-1.5 rounded-full px-3 py-1 text-xs font-medium border transition-all duration-200"
            style={{
              color: isActive ? "#0a0e1a" : color,
              backgroundColor: isActive ? color : `${color}10`,
              borderColor: isActive ? color : `${color}25`,
            }}
          >
            {ns}
            <span
              className="rounded-full px-1.5 py-0.5 text-[10px]"
              style={{
                backgroundColor: isActive ? "rgba(0,0,0,0.2)" : `${color}20`,
              }}
            >
              {count}
            </span>
          </button>
        );
      })}
    </div>
  );
}

/* ── Main Page ───────────────────────────────────────────── */

export default function CatalogPage() {
  const [search, setSearch] = useState("");
  const [namespace, setNamespace] = useState("");
  const [categoryFilter, setCategoryFilter] = useState("");
  const [viewMode, setViewMode] = useState<"grid" | "list">("grid");

  const { data, isLoading } = useQuery({
    queryKey: ["catalog", search, namespace],
    queryFn: () =>
      searchCatalog({
        q: search || undefined,
        namespace: namespace || undefined,
        page_size: 50,
      }),
    staleTime: 15_000,
  });

  const { data: cdnStats } = useQuery({
    queryKey: ["cdn-stats"],
    queryFn: fetchCDNStats,
    staleTime: 10_000,
  });

  const { data: mcpHealth } = useQuery({
    queryKey: ["mcp-health"],
    queryFn: fetchMCPHealth,
    staleTime: 30_000,
  });

  const entries = data?.entries ?? [];
  const namespaces = [...new Set(entries.map((e) => e.namespace))].sort();

  // Apply the category badge filter client-side
  const filteredEntries = categoryFilter
    ? entries.filter((e) => e.namespace === categoryFilter)
    : entries;

  return (
    <div className="space-y-6">
      <PageHeader
        title="Data Catalog"
        subtitle="Browse capabilities, CDN stats, and MCP health"
        icon={BookOpen}
      />

      {/* ── Status Cards ──────────────────────────────── */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <CDNCard stats={cdnStats ?? null} />
        <MCPCard health={mcpHealth ?? null} />
        <CatalogSummaryCard entries={entries} total={data?.total ?? 0} />
      </div>

      {/* ── Search & Filter ───────────────────────────── */}
      <div className="rounded-2xl border border-[rgba(255,255,255,0.06)] bg-[#141928] p-4 space-y-4">
        <div className="flex gap-3">
          <div className="relative flex-1">
            <Search className="absolute left-3.5 top-1/2 -translate-y-1/2 w-4 h-4 text-[#64748b]" />
            <input
              type="text"
              placeholder="Search catalog entries..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="w-full rounded-xl border border-[rgba(255,255,255,0.06)] bg-[#0a0e1a] pl-10 pr-4 py-2.5 text-sm text-[#e2e8f0] placeholder-[#64748b] outline-none transition-all duration-200 focus:border-[rgba(96,165,250,0.3)] focus:shadow-[0_0_16px_rgba(96,165,250,0.06)]"
            />
          </div>

          <select
            value={namespace}
            onChange={(e) => setNamespace(e.target.value)}
            className="rounded-xl border border-[rgba(255,255,255,0.06)] bg-[#0a0e1a] px-3 py-2.5 text-sm text-[#e2e8f0] outline-none transition-all duration-200 focus:border-[rgba(96,165,250,0.3)] min-w-[160px] appearance-none cursor-pointer"
          >
            <option value="">All namespaces</option>
            {namespaces.map((ns) => (
              <option key={ns} value={ns}>
                {ns}
              </option>
            ))}
          </select>

          {/* View Toggle */}
          <div className="flex rounded-xl border border-[rgba(255,255,255,0.06)] bg-[#0a0e1a] overflow-hidden">
            <button
              onClick={() => setViewMode("grid")}
              className={`p-2.5 transition-all duration-200 ${
                viewMode === "grid"
                  ? "bg-[rgba(96,165,250,0.1)] text-[#60a5fa]"
                  : "text-[#64748b] hover:text-[#94a3b8]"
              }`}
              title="Grid view"
            >
              <LayoutGrid className="h-4 w-4" />
            </button>
            <button
              onClick={() => setViewMode("list")}
              className={`p-2.5 transition-all duration-200 ${
                viewMode === "list"
                  ? "bg-[rgba(96,165,250,0.1)] text-[#60a5fa]"
                  : "text-[#64748b] hover:text-[#94a3b8]"
              }`}
              title="List view"
            >
              <List className="h-4 w-4" />
            </button>
          </div>
        </div>

        {/* Category Badges */}
        <CategoryBadges
          entries={entries}
          selected={categoryFilter}
          onSelect={setCategoryFilter}
        />
      </div>

      {/* ── Catalog Grid ──────────────────────────────── */}
      {isLoading ? (
        <div className="flex flex-col items-center justify-center py-16">
          <div className="h-8 w-8 animate-spin rounded-full border-2 border-[#60a5fa] border-t-transparent mb-3" />
          <span className="text-sm text-[#64748b]">Loading catalog...</span>
        </div>
      ) : filteredEntries.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-16 rounded-2xl border border-[rgba(255,255,255,0.06)] bg-[#141928]">
          <Database className="h-10 w-10 text-[#1e2844] mb-3" />
          <span className="text-sm text-[#64748b]">
            No catalog entries found. Agents register capabilities here.
          </span>
        </div>
      ) : viewMode === "grid" ? (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {filteredEntries.map((entry) => (
            <CatalogCard key={entry.id} entry={entry} />
          ))}
        </div>
      ) : (
        <div className="space-y-2">
          {filteredEntries.map((entry) => (
            <CatalogListItem key={entry.id} entry={entry} />
          ))}
        </div>
      )}

      {/* Result count */}
      {!isLoading && filteredEntries.length > 0 && (
        <div className="text-center">
          <span className="text-xs text-[#64748b]">
            Showing {filteredEntries.length} of {data?.total ?? 0} entries
          </span>
        </div>
      )}
    </div>
  );
}

/* ── List View Item ──────────────────────────────────────── */

function CatalogListItem({ entry }: { entry: CatalogEntry }) {
  const nsColor = namespaceColor(entry.namespace);

  return (
    <div className="group flex items-center gap-4 rounded-xl border border-[rgba(255,255,255,0.06)] bg-[#141928] p-4 transition-all duration-200 hover:border-[rgba(255,255,255,0.12)] hover:bg-[#1a2035]">
      {/* Namespace dot */}
      <div className="h-2 w-2 rounded-full flex-shrink-0" style={{ backgroundColor: nsColor }} />

      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 mb-0.5">
          <h3 className="text-sm font-semibold text-[#e2e8f0] truncate">{entry.topic}</h3>
          <span
            className="inline-flex items-center rounded-full px-1.5 py-0.5 text-[10px] font-medium border flex-shrink-0"
            style={{
              color: nsColor,
              backgroundColor: `${nsColor}15`,
              borderColor: `${nsColor}30`,
            }}
          >
            {entry.namespace}
          </span>
        </div>
        <p className="text-xs text-[#64748b] truncate">
          {entry.description || "No description provided"}
        </p>
      </div>

      <span className={`font-mono text-sm font-semibold flex-shrink-0 ${qualityLabel(entry.quality_avg)}`}>
        {(entry.quality_avg * 100).toFixed(0)}%
      </span>

      <span className="text-xs font-mono text-[#94a3b8] flex-shrink-0 w-32 text-right">
        {formatPrice(entry.price_range[0], entry.price_range[1])}
      </span>

      <Badge
        label={`${entry.active_listings_count}`}
        variant="blue"
      />
    </div>
  );
}
