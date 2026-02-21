import { useState, useMemo, useCallback } from "react";
import {
  Puzzle,
  Search,
  Download,
  Trash2,
  Star,
  User,
  X,
  Filter,
  Grid3X3,
  Check,
  Loader2,
} from "lucide-react";
import PageHeader from "../components/PageHeader";

/**
 * Plugin Marketplace Page.
 *
 * URL: /plugins
 *
 * Grid of plugin cards with search, category filter, install/uninstall,
 * and plugin detail modal.
 */

/* ── Data Types ─────────────────────────────────────────────────── */

interface Plugin {
  id: string;
  name: string;
  author: string;
  description: string;
  longDescription?: string;
  category: string;
  version: string;
  installCount: number;
  rating: number;
  icon: string;
  installed: boolean;
  tags?: string[];
}

/* ── Static Plugin Data ─────────────────────────────────────────── */

const CATEGORIES = [
  "All",
  "AI / ML",
  "Data Processing",
  "Communication",
  "Security",
  "Analytics",
  "Utilities",
];

const INITIAL_PLUGINS: Plugin[] = [
  {
    id: "plugin-llm-router",
    name: "LLM Router",
    author: "AgentChains Core",
    description: "Intelligent routing of prompts to the optimal LLM provider based on cost and latency.",
    longDescription: "The LLM Router plugin analyzes incoming prompts and automatically routes them to the most suitable LLM provider. It considers factors like cost, latency, model specialization, and current load to make optimal decisions. Supports OpenAI, Anthropic, Google, and custom endpoints.",
    category: "AI / ML",
    version: "2.1.0",
    installCount: 12_450,
    rating: 4.8,
    icon: "R",
    installed: true,
    tags: ["llm", "routing", "optimization"],
  },
  {
    id: "plugin-vector-store",
    name: "Vector Store",
    author: "DataForge Labs",
    description: "High-performance vector storage and similarity search for agent memory.",
    longDescription: "Provides agents with persistent vector memory using efficient approximate nearest neighbor search. Supports multiple backends including FAISS, Pinecone, and Qdrant. Enables semantic search, RAG pipelines, and long-term agent memory.",
    category: "Data Processing",
    version: "1.4.2",
    installCount: 8_920,
    rating: 4.6,
    icon: "V",
    installed: false,
    tags: ["vectors", "memory", "search"],
  },
  {
    id: "plugin-webhook-bridge",
    name: "Webhook Bridge",
    author: "NetConnect",
    description: "Connect agents to external services via configurable webhook endpoints.",
    longDescription: "Enables bidirectional communication between agents and external services through webhooks. Supports custom headers, authentication, retry logic, and payload transformation. Ideal for integrating with Slack, Discord, GitHub, and custom APIs.",
    category: "Communication",
    version: "3.0.1",
    installCount: 6_340,
    rating: 4.3,
    icon: "W",
    installed: true,
    tags: ["webhooks", "integration", "api"],
  },
  {
    id: "plugin-auth-guard",
    name: "Auth Guard",
    author: "SecureStack",
    description: "Advanced authentication and authorization middleware for agent endpoints.",
    longDescription: "Comprehensive security plugin that adds JWT validation, API key management, RBAC, and rate limiting to agent endpoints. Supports OAuth 2.0, SAML, and custom authentication flows with audit logging.",
    category: "Security",
    version: "1.8.0",
    installCount: 5_120,
    rating: 4.9,
    icon: "A",
    installed: false,
    tags: ["auth", "security", "jwt"],
  },
  {
    id: "plugin-usage-analytics",
    name: "Usage Analytics",
    author: "InsightAI",
    description: "Real-time analytics and dashboards for agent performance and usage patterns.",
    longDescription: "Track and visualize agent performance metrics, usage patterns, and cost analysis in real-time. Features customizable dashboards, anomaly detection, cost alerts, and exportable reports. Integrates with popular observability platforms.",
    category: "Analytics",
    version: "2.3.0",
    installCount: 4_580,
    rating: 4.5,
    icon: "U",
    installed: false,
    tags: ["analytics", "metrics", "dashboards"],
  },
  {
    id: "plugin-task-scheduler",
    name: "Task Scheduler",
    author: "AgentChains Core",
    description: "Cron-like scheduler for recurring agent tasks and automated workflows.",
    longDescription: "Schedule agents to perform recurring tasks using cron expressions or interval-based triggers. Supports dependencies, retry policies, concurrency limits, and timezone-aware scheduling. Includes a visual timeline for monitoring scheduled tasks.",
    category: "Utilities",
    version: "1.2.4",
    installCount: 7_210,
    rating: 4.4,
    icon: "T",
    installed: true,
    tags: ["scheduling", "cron", "automation"],
  },
  {
    id: "plugin-data-pipeline",
    name: "Data Pipeline",
    author: "StreamFlow",
    description: "Build and manage data transformation pipelines between agents and services.",
    longDescription: "Visual data pipeline builder that lets you create ETL workflows between agents, databases, and external services. Supports streaming and batch processing, schema validation, data masking, and error recovery.",
    category: "Data Processing",
    version: "1.0.3",
    installCount: 3_150,
    rating: 4.2,
    icon: "D",
    installed: false,
    tags: ["etl", "pipeline", "streaming"],
  },
  {
    id: "plugin-anomaly-detector",
    name: "Anomaly Detector",
    author: "InsightAI",
    description: "ML-powered anomaly detection for agent behavior and system metrics.",
    longDescription: "Uses machine learning models to detect anomalous agent behavior, unusual traffic patterns, and system metric deviations in real-time. Supports custom thresholds, alert channels, and automated remediation actions.",
    category: "AI / ML",
    version: "1.1.0",
    installCount: 2_890,
    rating: 4.7,
    icon: "X",
    installed: false,
    tags: ["anomaly", "ml", "monitoring"],
  },
  {
    id: "plugin-cache-turbo",
    name: "Cache Turbo",
    author: "SpeedStack",
    description: "Multi-layer caching with Redis, in-memory, and CDN support for agent responses.",
    longDescription: "Dramatically improve agent response times with intelligent multi-layer caching. Supports Redis, in-memory LRU, and CDN edge caching. Features cache invalidation strategies, TTL management, and cache hit rate monitoring.",
    category: "Utilities",
    version: "2.0.0",
    installCount: 5_670,
    rating: 4.6,
    icon: "C",
    installed: false,
    tags: ["cache", "redis", "performance"],
  },
];

/* ── Icon gradient colors ───────────────────────────────────────── */

const ICON_GRADIENTS: Record<string, string> = {
  "AI / ML": "from-[#a78bfa] to-[#60a5fa]",
  "Data Processing": "from-[#34d399] to-[#22d3ee]",
  Communication: "from-[#60a5fa] to-[#38bdf8]",
  Security: "from-[#f87171] to-[#fbbf24]",
  Analytics: "from-[#fbbf24] to-[#fb923c]",
  Utilities: "from-[#64748b] to-[#94a3b8]",
};

/* ── Component ──────────────────────────────────────────────────── */

export default function PluginMarketplacePage() {
  const [plugins, setPlugins] = useState<Plugin[]>(INITIAL_PLUGINS);
  const [searchQuery, setSearchQuery] = useState("");
  const [selectedCategory, setSelectedCategory] = useState("All");
  const [selectedPlugin, setSelectedPlugin] = useState<Plugin | null>(null);
  const [installingId, setInstallingId] = useState<string | null>(null);

  const filteredPlugins = useMemo(() => {
    return plugins.filter((p) => {
      const matchesCategory =
        selectedCategory === "All" || p.category === selectedCategory;
      const matchesSearch =
        !searchQuery.trim() ||
        p.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
        p.author.toLowerCase().includes(searchQuery.toLowerCase()) ||
        p.description.toLowerCase().includes(searchQuery.toLowerCase()) ||
        p.tags?.some((t) => t.toLowerCase().includes(searchQuery.toLowerCase()));
      return matchesCategory && matchesSearch;
    });
  }, [plugins, searchQuery, selectedCategory]);

  const handleToggleInstall = useCallback(
    async (pluginId: string) => {
      setInstallingId(pluginId);
      // Simulate async install/uninstall
      await new Promise((resolve) => setTimeout(resolve, 1200));
      setPlugins((prev) =>
        prev.map((p) =>
          p.id === pluginId
            ? {
                ...p,
                installed: !p.installed,
                installCount: p.installed
                  ? p.installCount - 1
                  : p.installCount + 1,
              }
            : p,
        ),
      );
      // Also update selected plugin if open
      setSelectedPlugin((prev) =>
        prev && prev.id === pluginId
          ? {
              ...prev,
              installed: !prev.installed,
              installCount: prev.installed
                ? prev.installCount - 1
                : prev.installCount + 1,
            }
          : prev,
      );
      setInstallingId(null);
    },
    [],
  );

  const formatInstallCount = (count: number) => {
    if (count >= 1000) {
      return `${(count / 1000).toFixed(1)}k`;
    }
    return String(count);
  };

  return (
    <div className="space-y-6">
      {/* Page header */}
      <PageHeader
        title="Plugin Marketplace"
        subtitle="Discover and install plugins to extend agent capabilities"
        icon={Puzzle}
      />

      {/* ── Search & Filter Bar ─────────────────────────────── */}
      <div className="rounded-2xl border border-[rgba(255,255,255,0.06)] bg-[#141928] p-4">
        <div className="flex flex-wrap items-center gap-3">
          {/* Search input */}
          <div className="relative flex-1 min-w-[240px]">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-[#64748b]" />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search plugins by name, author, or tag..."
              className="w-full rounded-xl border border-[rgba(255,255,255,0.06)] bg-[#1a2035] py-2.5 pl-10 pr-4 text-sm text-[#e2e8f0] placeholder-[#64748b] outline-none transition-all duration-200 focus:border-[rgba(96,165,250,0.5)] focus:shadow-[0_0_0_3px_rgba(96,165,250,0.1)]"
            />
          </div>

          {/* Category filter */}
          <div className="flex items-center gap-1.5 overflow-x-auto">
            <Filter className="h-3.5 w-3.5 flex-shrink-0 text-[#64748b]" />
            {CATEGORIES.map((cat) => (
              <button
                key={cat}
                onClick={() => setSelectedCategory(cat)}
                className={`flex-shrink-0 rounded-lg px-3 py-1.5 text-xs font-medium transition-all duration-200 ${
                  selectedCategory === cat
                    ? "bg-[rgba(96,165,250,0.15)] text-[#60a5fa] border border-[rgba(96,165,250,0.3)]"
                    : "border border-transparent text-[#64748b] hover:bg-[rgba(255,255,255,0.04)] hover:text-[#94a3b8]"
                }`}
              >
                {cat}
              </button>
            ))}
          </div>

          {/* Result count */}
          <span className="ml-auto flex items-center gap-2 whitespace-nowrap rounded-xl border border-[rgba(255,255,255,0.06)] bg-[#1a2035] px-4 py-2.5 text-sm font-medium text-[#94a3b8]">
            <Grid3X3 className="h-4 w-4 text-[#60a5fa]" />
            {filteredPlugins.length} plugin{filteredPlugins.length !== 1 && "s"}
          </span>
        </div>
      </div>

      {/* ── Plugin Grid ─────────────────────────────────────── */}
      {filteredPlugins.length === 0 ? (
        <div className="flex flex-col items-center rounded-2xl border border-[rgba(255,255,255,0.06)] bg-[#141928] py-24">
          <div className="mb-4 flex h-16 w-16 items-center justify-center rounded-2xl bg-[rgba(96,165,250,0.08)]">
            <Puzzle className="h-8 w-8 text-[#60a5fa]" />
          </div>
          <p className="text-base font-medium text-[#94a3b8]">
            No plugins found
          </p>
          <p className="mt-1 text-sm text-[#64748b]">
            Try adjusting your search or filter criteria
          </p>
        </div>
      ) : (
        <div className="grid gap-5 sm:grid-cols-2 xl:grid-cols-3">
          {filteredPlugins.map((plugin) => {
            const gradient =
              ICON_GRADIENTS[plugin.category] ?? ICON_GRADIENTS.Utilities;
            const isInstalling = installingId === plugin.id;

            return (
              <div
                key={plugin.id}
                className="group relative flex flex-col rounded-2xl border border-[rgba(255,255,255,0.06)] bg-[#141928] p-5 transition-all duration-300 hover:border-[rgba(96,165,250,0.2)] hover:shadow-[0_0_24px_rgba(96,165,250,0.06)] hover:-translate-y-1"
              >
                {/* Installed badge */}
                {plugin.installed && (
                  <div className="absolute right-4 top-4">
                    <span className="inline-flex items-center gap-1 rounded-full bg-[rgba(52,211,153,0.15)] px-2 py-0.5 text-[9px] font-semibold uppercase text-[#34d399]">
                      <Check className="h-2.5 w-2.5" />
                      Installed
                    </span>
                  </div>
                )}

                {/* Icon + Name + Author */}
                <div className="flex items-start gap-3 mb-3">
                  <div
                    className={`flex h-11 w-11 flex-shrink-0 items-center justify-center rounded-xl bg-gradient-to-br ${gradient} text-sm font-bold text-white shadow-lg`}
                  >
                    {plugin.icon}
                  </div>
                  <div className="min-w-0 flex-1">
                    <h4 className="text-sm font-semibold text-[#e2e8f0] truncate">
                      {plugin.name}
                    </h4>
                    <p className="flex items-center gap-1 text-[10px] text-[#64748b] mt-0.5">
                      <User className="h-2.5 w-2.5" />
                      {plugin.author}
                    </p>
                  </div>
                </div>

                {/* Description */}
                <p className="mb-4 text-xs text-[#94a3b8] leading-relaxed line-clamp-2 flex-1">
                  {plugin.description}
                </p>

                {/* Tags */}
                {plugin.tags && (
                  <div className="mb-4 flex flex-wrap gap-1">
                    {plugin.tags.map((tag) => (
                      <span
                        key={tag}
                        className="rounded-md bg-[rgba(255,255,255,0.03)] px-1.5 py-0.5 text-[9px] text-[#64748b] border border-[rgba(255,255,255,0.04)]"
                      >
                        {tag}
                      </span>
                    ))}
                  </div>
                )}

                {/* Stats row */}
                <div className="flex items-center gap-4 mb-4 text-[10px] text-[#64748b]">
                  <span className="inline-flex items-center gap-1">
                    <Download className="h-3 w-3" />
                    {formatInstallCount(plugin.installCount)}
                  </span>
                  <span className="inline-flex items-center gap-1">
                    <Star className="h-3 w-3 text-[#fbbf24]" />
                    {plugin.rating}
                  </span>
                  <span className="ml-auto font-mono">v{plugin.version}</span>
                </div>

                {/* Actions */}
                <div className="flex items-center gap-2">
                  <button
                    onClick={() => setSelectedPlugin(plugin)}
                    className="flex-1 rounded-lg border border-[rgba(255,255,255,0.1)] py-2 text-xs font-medium text-[#94a3b8] transition-colors hover:bg-[rgba(255,255,255,0.04)] hover:text-[#e2e8f0]"
                  >
                    Details
                  </button>
                  <button
                    onClick={() => handleToggleInstall(plugin.id)}
                    disabled={isInstalling}
                    className={`flex-1 rounded-lg py-2 text-xs font-semibold transition-all duration-200 disabled:opacity-60 ${
                      plugin.installed
                        ? "border border-[rgba(248,113,113,0.2)] text-[#f87171] hover:bg-[rgba(248,113,113,0.08)]"
                        : "bg-[#60a5fa] text-[#0a0e1a] hover:bg-[#3b82f6]"
                    }`}
                  >
                    {isInstalling ? (
                      <span className="inline-flex items-center gap-1">
                        <Loader2 className="h-3 w-3 animate-spin" />
                        {plugin.installed ? "Removing..." : "Installing..."}
                      </span>
                    ) : plugin.installed ? (
                      <span className="inline-flex items-center gap-1 justify-center">
                        <Trash2 className="h-3 w-3" />
                        Uninstall
                      </span>
                    ) : (
                      <span className="inline-flex items-center gap-1 justify-center">
                        <Download className="h-3 w-3" />
                        Install
                      </span>
                    )}
                  </button>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* ── Plugin Detail Modal ────────────────────────────── */}
      {selectedPlugin && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm"
          onClick={(e) => {
            if (e.target === e.currentTarget) setSelectedPlugin(null);
          }}
          style={{ animation: "modal-fade 0.2s ease-out" }}
        >
          <div
            className="relative w-full max-w-lg rounded-2xl border border-[rgba(255,255,255,0.1)] bg-[#141928] shadow-2xl"
            style={{ animation: "modal-scale 0.25s ease-out" }}
          >
            {/* Close button */}
            <button
              onClick={() => setSelectedPlugin(null)}
              className="absolute right-4 top-4 flex h-8 w-8 items-center justify-center rounded-full text-[#64748b] transition-colors hover:bg-[rgba(255,255,255,0.04)] hover:text-[#e2e8f0]"
            >
              <X className="h-4 w-4" />
            </button>

            <div className="p-6">
              {/* Header */}
              <div className="flex items-start gap-4 mb-5">
                <div
                  className={`flex h-14 w-14 flex-shrink-0 items-center justify-center rounded-xl bg-gradient-to-br ${
                    ICON_GRADIENTS[selectedPlugin.category] ??
                    ICON_GRADIENTS.Utilities
                  } text-lg font-bold text-white shadow-lg`}
                >
                  {selectedPlugin.icon}
                </div>
                <div>
                  <h3 className="text-lg font-bold text-[#e2e8f0]">
                    {selectedPlugin.name}
                  </h3>
                  <p className="flex items-center gap-1 text-xs text-[#64748b] mt-0.5">
                    <User className="h-3 w-3" />
                    {selectedPlugin.author}
                  </p>
                  <div className="mt-2 flex items-center gap-3 text-xs text-[#94a3b8]">
                    <span className="inline-flex items-center gap-1">
                      <Download className="h-3 w-3" />
                      {formatInstallCount(selectedPlugin.installCount)} installs
                    </span>
                    <span className="inline-flex items-center gap-1">
                      <Star className="h-3 w-3 text-[#fbbf24]" />
                      {selectedPlugin.rating}
                    </span>
                    <span className="font-mono text-[#64748b]">
                      v{selectedPlugin.version}
                    </span>
                  </div>
                </div>
              </div>

              {/* Category + Status */}
              <div className="flex gap-2 mb-5">
                <span className="rounded-full bg-[rgba(96,165,250,0.1)] px-2.5 py-0.5 text-[10px] font-semibold text-[#60a5fa]">
                  {selectedPlugin.category}
                </span>
                {selectedPlugin.installed && (
                  <span className="inline-flex items-center gap-1 rounded-full bg-[rgba(52,211,153,0.15)] px-2.5 py-0.5 text-[10px] font-semibold text-[#34d399]">
                    <Check className="h-2.5 w-2.5" />
                    Installed
                  </span>
                )}
              </div>

              {/* Long description */}
              <div className="mb-6">
                <p className="text-[10px] uppercase tracking-wider text-[#64748b] mb-2">
                  About
                </p>
                <p className="text-sm text-[#94a3b8] leading-relaxed">
                  {selectedPlugin.longDescription ?? selectedPlugin.description}
                </p>
              </div>

              {/* Tags */}
              {selectedPlugin.tags && selectedPlugin.tags.length > 0 && (
                <div className="mb-6">
                  <p className="text-[10px] uppercase tracking-wider text-[#64748b] mb-2">
                    Tags
                  </p>
                  <div className="flex flex-wrap gap-1.5">
                    {selectedPlugin.tags.map((tag) => (
                      <span
                        key={tag}
                        className="rounded-md bg-[rgba(255,255,255,0.04)] px-2 py-1 text-[10px] text-[#94a3b8] border border-[rgba(255,255,255,0.06)]"
                      >
                        {tag}
                      </span>
                    ))}
                  </div>
                </div>
              )}

              {/* Action buttons */}
              <div className="flex items-center gap-3 border-t border-[rgba(255,255,255,0.06)] pt-5">
                <button
                  onClick={() => handleToggleInstall(selectedPlugin.id)}
                  disabled={installingId === selectedPlugin.id}
                  className={`flex-1 rounded-xl py-3 text-sm font-semibold transition-all duration-200 disabled:opacity-60 ${
                    selectedPlugin.installed
                      ? "border border-[rgba(248,113,113,0.2)] text-[#f87171] hover:bg-[rgba(248,113,113,0.08)]"
                      : "bg-[#60a5fa] text-[#0a0e1a] hover:bg-[#3b82f6]"
                  }`}
                >
                  {installingId === selectedPlugin.id ? (
                    <span className="inline-flex items-center justify-center gap-1.5">
                      <Loader2 className="h-4 w-4 animate-spin" />
                      {selectedPlugin.installed
                        ? "Removing..."
                        : "Installing..."}
                    </span>
                  ) : selectedPlugin.installed ? (
                    <span className="inline-flex items-center justify-center gap-1.5">
                      <Trash2 className="h-4 w-4" />
                      Uninstall Plugin
                    </span>
                  ) : (
                    <span className="inline-flex items-center justify-center gap-1.5">
                      <Download className="h-4 w-4" />
                      Install Plugin
                    </span>
                  )}
                </button>
                <button
                  onClick={() => setSelectedPlugin(null)}
                  className="rounded-xl border border-[rgba(255,255,255,0.1)] px-6 py-3 text-sm font-medium text-[#94a3b8] transition-colors hover:bg-[rgba(255,255,255,0.04)] hover:text-[#e2e8f0]"
                >
                  Close
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Modal animations */}
      <style>{`
        @keyframes modal-fade {
          from { opacity: 0; }
          to { opacity: 1; }
        }
        @keyframes modal-scale {
          from { opacity: 0; transform: scale(0.95) translateY(8px); }
          to { opacity: 1; transform: scale(1) translateY(0); }
        }
      `}</style>
    </div>
  );
}
