import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Search, BookOpen, Zap, Shield } from "lucide-react";
import { searchCatalog, fetchCDNStats, fetchMCPHealth } from "../lib/api";
import type { CatalogEntry, CDNStats, MCPHealth } from "../types/api";

function formatPrice(min: number, max: number) {
  if (min === max) return `$${min.toFixed(4)}`;
  return `$${min.toFixed(4)} – $${max.toFixed(4)}`;
}

function QualityBadge({ score }: { score: number }) {
  const color =
    score >= 0.8 ? "text-success" : score >= 0.5 ? "text-warning" : "text-danger";
  return <span className={`font-mono text-sm ${color}`}>{(score * 100).toFixed(0)}%</span>;
}

export default function CatalogPage() {
  const [search, setSearch] = useState("");
  const [namespace, setNamespace] = useState("");

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

  return (
    <div className="space-y-6">
      {/* Infrastructure Status Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <CDNCard stats={cdnStats ?? null} />
        <MCPCard health={mcpHealth ?? null} />
        <CatalogSummaryCard entries={entries} total={data?.total ?? 0} />
      </div>

      {/* Search Bar */}
      <div className="flex gap-3">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-text-muted" />
          <input
            type="text"
            placeholder="Search capabilities..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="futuristic-input pl-10 pr-4 py-2 text-sm w-full"
          />
        </div>
        <select
          value={namespace}
          onChange={(e) => setNamespace(e.target.value)}
          className="futuristic-select px-3 py-2 text-sm"
        >
          <option value="">All namespaces</option>
          {namespaces.map((ns) => (
            <option key={ns} value={ns}>
              {ns}
            </option>
          ))}
        </select>
      </div>

      {/* Catalog Grid */}
      {isLoading ? (
        <div className="text-text-muted text-center py-12">Loading catalog...</div>
      ) : entries.length === 0 ? (
        <div className="text-text-muted text-center py-12">
          No catalog entries found. Agents register capabilities here.
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {entries.map((entry) => (
            <CatalogCard key={entry.id} entry={entry} />
          ))}
        </div>
      )}
    </div>
  );
}

function CatalogCard({ entry }: { entry: CatalogEntry }) {
  return (
    <div className="glass-card gradient-border-card glow-hover p-4 transition-colors">
      <div className="flex items-start justify-between mb-2">
        <span className="bg-primary-glow text-primary text-xs font-medium px-2 py-0.5 rounded">
          {entry.namespace}
        </span>
        <QualityBadge score={entry.quality_avg} />
      </div>
      <h3 className="text-sm font-semibold text-text-primary mb-1 line-clamp-1">{entry.topic}</h3>
      <p className="text-xs text-text-muted mb-3 line-clamp-2">{entry.description || "No description"}</p>
      <div className="flex items-center justify-between text-xs text-text-muted">
        <span>{formatPrice(entry.price_range[0], entry.price_range[1])}</span>
        <span>{entry.active_listings_count} listings</span>
      </div>
    </div>
  );
}

function CDNCard({ stats }: { stats: CDNStats | null }) {
  if (!stats) {
    return (
      <div className="glass-card gradient-border-card glow-hover p-4">
        <div className="flex items-center gap-2 mb-2">
          <Zap className="w-4 h-4 text-yellow-400" />
          <span className="text-sm font-semibold text-text-primary">CDN</span>
        </div>
        <p className="text-xs text-text-muted">Loading...</p>
      </div>
    );
  }

  const total = stats.overview.total_requests || 1;
  const hitRate = ((stats.overview.tier1_hits + stats.overview.tier2_hits) / total * 100).toFixed(1);

  return (
    <div className="glass-card gradient-border-card glow-hover p-4">
      <div className="flex items-center gap-2 mb-3">
        <Zap className="w-4 h-4 text-yellow-400" />
        <span className="text-sm font-semibold text-text-primary">CDN Performance</span>
      </div>
      <div className="grid grid-cols-2 gap-2 text-xs">
        <div>
          <div className="text-text-muted">Hit Rate</div>
          <div className="text-text-primary font-mono">{hitRate}%</div>
        </div>
        <div>
          <div className="text-text-muted">Hot Cache</div>
          <div className="text-text-primary font-mono">{stats.hot_cache.entries} items</div>
        </div>
        <div>
          <div className="text-text-muted">Tier 1 Hits</div>
          <div className="text-success font-mono">{stats.overview.tier1_hits}</div>
        </div>
        <div>
          <div className="text-text-muted">Tier 3 (Disk)</div>
          <div className="text-orange-400 font-mono">{stats.overview.tier3_hits}</div>
        </div>
      </div>
    </div>
  );
}

function MCPCard({ health }: { health: MCPHealth | null }) {
  return (
    <div className="glass-card gradient-border-card glow-hover p-4">
      <div className="flex items-center gap-2 mb-3">
        <Shield className="w-4 h-4 text-primary" />
        <span className="text-sm font-semibold text-text-primary">MCP Server</span>
      </div>
      {health ? (
        <div className="grid grid-cols-2 gap-2 text-xs">
          <div>
            <div className="text-text-muted">Status</div>
            <div className="text-success font-mono">{health.status}</div>
          </div>
          <div>
            <div className="text-text-muted">Sessions</div>
            <div className="text-text-primary font-mono">{health.active_sessions}</div>
          </div>
          <div>
            <div className="text-text-muted">Tools</div>
            <div className="text-text-primary font-mono">{health.tools_count}</div>
          </div>
          <div>
            <div className="text-text-muted">Resources</div>
            <div className="text-text-primary font-mono">{health.resources_count}</div>
          </div>
        </div>
      ) : (
        <p className="text-xs text-text-muted">Loading...</p>
      )}
    </div>
  );
}

function CatalogSummaryCard({ entries, total }: { entries: CatalogEntry[]; total: number }) {
  const uniqueAgents = new Set(entries.map((e) => e.agent_id)).size;
  const uniqueNamespaces = new Set(entries.map((e) => e.namespace)).size;

  return (
    <div className="glass-card gradient-border-card glow-hover p-4">
      <div className="flex items-center gap-2 mb-3">
        <BookOpen className="w-4 h-4 text-secondary" />
        <span className="text-sm font-semibold text-text-primary">Data Catalog</span>
      </div>
      <div className="grid grid-cols-2 gap-2 text-xs">
        <div>
          <div className="text-text-muted">Entries</div>
          <div className="text-text-primary font-mono">{total}</div>
        </div>
        <div>
          <div className="text-text-muted">Agents</div>
          <div className="text-text-primary font-mono">{uniqueAgents}</div>
        </div>
        <div>
          <div className="text-text-muted">Namespaces</div>
          <div className="text-text-primary font-mono">{uniqueNamespaces}</div>
        </div>
        <div>
          <div className="text-text-muted">Active</div>
          <div className="text-success font-mono">{entries.filter((e) => e.status === "active").length}</div>
        </div>
      </div>
    </div>
  );
}
