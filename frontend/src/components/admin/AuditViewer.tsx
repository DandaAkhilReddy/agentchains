import { useState, useMemo, useCallback } from "react";
import {
  FileText,
  Search,
  Download,
  ChevronDown,
  ChevronUp,
  Calendar,
  User,
  Shield,
  Clock,
  Filter,
  X,
  AlertTriangle,
  Info,
  Activity,
} from "lucide-react";

/**
 * Audit Log Viewer.
 *
 * Provides:
 *   - Filterable table: timestamp, actor, action, resource, details
 *   - Date range picker
 *   - Export CSV button
 *   - Expandable row detail
 */

/* ── Data Types ─────────────────────────────────────────────────── */

interface AuditEntry {
  id: string;
  timestamp: string;
  actor: string;
  actorType: "admin" | "system" | "agent" | "user";
  action: string;
  category: string;
  severity: "info" | "warning" | "critical";
  resource: string;
  resourceId?: string;
  details: Record<string, string>;
  ipAddress?: string;
  userAgent?: string;
}

/* ── Static Data ────────────────────────────────────────────────── */

const AUDIT_ENTRIES: AuditEntry[] = [
  {
    id: "evt-001",
    timestamp: "2026-02-21T14:32:10Z",
    actor: "admin@agentchains.io",
    actorType: "admin",
    action: "agent.deactivated",
    category: "Agent Management",
    severity: "warning",
    resource: "Agent",
    resourceId: "agent-xyz-789",
    details: {
      reason: "Suspicious activity detected",
      previous_status: "active",
      new_status: "suspended",
    },
    ipAddress: "192.168.1.100",
    userAgent: "Mozilla/5.0 Chrome/120",
  },
  {
    id: "evt-002",
    timestamp: "2026-02-21T14:28:05Z",
    actor: "system",
    actorType: "system",
    action: "rate_limit.triggered",
    category: "Security",
    severity: "warning",
    resource: "RateLimit",
    resourceId: "agent-abc-123",
    details: {
      endpoint: "/api/v2/agents/execute",
      limit: "120 req/min",
      actual: "145 req/min",
    },
  },
  {
    id: "evt-003",
    timestamp: "2026-02-21T14:15:30Z",
    actor: "agent-abc-123",
    actorType: "agent",
    action: "listing.created",
    category: "Marketplace",
    severity: "info",
    resource: "Listing",
    resourceId: "listing-def-456",
    details: {
      listing_name: "Data Analysis Service",
      price_usd: "25.00",
      category: "Analytics",
    },
  },
  {
    id: "evt-004",
    timestamp: "2026-02-21T13:55:12Z",
    actor: "admin@agentchains.io",
    actorType: "admin",
    action: "config.updated",
    category: "Configuration",
    severity: "info",
    resource: "SystemConfig",
    resourceId: "rate_limit_rpm",
    details: {
      setting: "rate_limit_rpm",
      old_value: "100",
      new_value: "120",
    },
    ipAddress: "192.168.1.100",
  },
  {
    id: "evt-005",
    timestamp: "2026-02-21T13:40:00Z",
    actor: "system",
    actorType: "system",
    action: "auth.failed",
    category: "Security",
    severity: "critical",
    resource: "AuthService",
    details: {
      reason: "Invalid JWT signature",
      source_ip: "10.0.0.45",
      attempts: "5",
    },
  },
  {
    id: "evt-006",
    timestamp: "2026-02-21T13:22:44Z",
    actor: "agent-qrs-567",
    actorType: "agent",
    action: "transaction.completed",
    category: "Marketplace",
    severity: "info",
    resource: "Transaction",
    resourceId: "tx-ghi-890",
    details: {
      amount_usd: "42.50",
      buyer: "agent-abc-123",
      seller: "agent-qrs-567",
    },
  },
  {
    id: "evt-007",
    timestamp: "2026-02-21T12:58:19Z",
    actor: "admin@agentchains.io",
    actorType: "admin",
    action: "payout.approved",
    category: "Finance",
    severity: "info",
    resource: "Payout",
    resourceId: "payout-jkl-012",
    details: {
      agent_id: "agent-qrs-567",
      amount_usd: "150.00",
      method: "bank_transfer",
    },
    ipAddress: "192.168.1.100",
  },
  {
    id: "evt-008",
    timestamp: "2026-02-21T12:30:00Z",
    actor: "system",
    actorType: "system",
    action: "service.degraded",
    category: "Infrastructure",
    severity: "critical",
    resource: "System",
    resourceId: "redis-cache",
    details: {
      service: "Redis Cache",
      latency_ms: "450",
      threshold_ms: "100",
    },
  },
  {
    id: "evt-009",
    timestamp: "2026-02-20T18:15:45Z",
    actor: "admin@agentchains.io",
    actorType: "admin",
    action: "feature_flag.toggled",
    category: "Configuration",
    severity: "info",
    resource: "FeatureFlag",
    resourceId: "ff-marketplace",
    details: {
      flag: "enable_marketplace",
      old_value: "false",
      new_value: "true",
    },
    ipAddress: "192.168.1.100",
  },
  {
    id: "evt-010",
    timestamp: "2026-02-20T10:00:00Z",
    actor: "user-john-doe",
    actorType: "user",
    action: "plugin.installed",
    category: "Marketplace",
    severity: "info",
    resource: "Plugin",
    resourceId: "plugin-llm-router",
    details: {
      version: "2.1.0",
      previous_version: "none",
    },
  },
];

const ACTION_CATEGORIES = [
  "All",
  "Agent Management",
  "Security",
  "Marketplace",
  "Configuration",
  "Finance",
  "Infrastructure",
];

const SEVERITY_FILTERS = ["All", "info", "warning", "critical"];

const SEVERITY_STYLES: Record<string, { color: string; bg: string }> = {
  info: { color: "#60a5fa", bg: "rgba(96,165,250,0.1)" },
  warning: { color: "#fbbf24", bg: "rgba(251,191,36,0.1)" },
  critical: { color: "#f87171", bg: "rgba(248,113,113,0.1)" },
};

const ACTOR_COLORS: Record<string, { bg: string; text: string; icon: typeof User }> = {
  admin: { bg: "rgba(167,139,250,0.15)", text: "#a78bfa", icon: Shield },
  system: { bg: "rgba(96,165,250,0.15)", text: "#60a5fa", icon: Info },
  agent: { bg: "rgba(52,211,153,0.15)", text: "#34d399", icon: Activity },
  user: { bg: "rgba(251,191,36,0.15)", text: "#fbbf24", icon: User },
};

/* ── Component ──────────────────────────────────────────────────── */

export default function AuditViewer() {
  const [searchQuery, setSearchQuery] = useState("");
  const [categoryFilter, setCategoryFilter] = useState("All");
  const [severityFilter, setSeverityFilter] = useState("All");
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [sortAsc, setSortAsc] = useState(false);

  /* ── Filtering ────────────────────────────────────────────── */

  const filteredEntries = useMemo(() => {
    let result = [...AUDIT_ENTRIES];

    // Category filter
    if (categoryFilter !== "All") {
      result = result.filter((e) => e.category === categoryFilter);
    }

    // Severity filter
    if (severityFilter !== "All") {
      result = result.filter((e) => e.severity === severityFilter);
    }

    // Search filter
    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase();
      result = result.filter(
        (e) =>
          e.actor.toLowerCase().includes(q) ||
          e.action.toLowerCase().includes(q) ||
          e.resource.toLowerCase().includes(q) ||
          (e.resourceId?.toLowerCase().includes(q) ?? false) ||
          e.category.toLowerCase().includes(q) ||
          JSON.stringify(e.details).toLowerCase().includes(q),
      );
    }

    // Date range filter
    if (dateFrom) {
      const fromDate = new Date(dateFrom);
      result = result.filter((e) => new Date(e.timestamp) >= fromDate);
    }
    if (dateTo) {
      const toDate = new Date(dateTo);
      toDate.setHours(23, 59, 59, 999);
      result = result.filter((e) => new Date(e.timestamp) <= toDate);
    }

    // Sort by timestamp
    result.sort((a, b) => {
      const cmp =
        new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime();
      return sortAsc ? cmp : -cmp;
    });

    return result;
  }, [searchQuery, categoryFilter, severityFilter, dateFrom, dateTo, sortAsc]);

  /* ── CSV Export ────────────────────────────────────────────── */

  const handleExportCSV = useCallback(() => {
    const headers = [
      "Timestamp",
      "Actor",
      "Actor Type",
      "Action",
      "Category",
      "Severity",
      "Resource",
      "Resource ID",
      "Details",
      "IP Address",
    ];
    const rows = filteredEntries.map((e) => [
      e.timestamp,
      e.actor,
      e.actorType,
      e.action,
      e.category,
      e.severity,
      e.resource,
      e.resourceId ?? "",
      JSON.stringify(e.details),
      e.ipAddress ?? "",
    ]);

    const csv = [
      headers.join(","),
      ...rows.map((row) =>
        row.map((cell) => `"${String(cell).replace(/"/g, '""')}"`).join(","),
      ),
    ].join("\n");

    const blob = new Blob([csv], { type: "text/csv;charset=utf-8;" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `audit-log-${new Date().toISOString().slice(0, 10)}.csv`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
  }, [filteredEntries]);

  /* ── Clear filters ────────────────────────────────────────── */

  const hasFilters =
    searchQuery ||
    categoryFilter !== "All" ||
    severityFilter !== "All" ||
    dateFrom ||
    dateTo;

  const clearFilters = useCallback(() => {
    setSearchQuery("");
    setCategoryFilter("All");
    setSeverityFilter("All");
    setDateFrom("");
    setDateTo("");
  }, []);

  /* ── Format helpers ───────────────────────────────────────── */

  const formatTimestamp = (iso: string) => {
    const d = new Date(iso);
    return d.toLocaleString("en-US", {
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
    });
  };

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-[rgba(251,191,36,0.1)]">
            <FileText className="h-4 w-4 text-[#fbbf24]" />
          </div>
          <div>
            <h3 className="text-sm font-semibold text-[#e2e8f0]">
              Audit Log
            </h3>
            <p className="text-xs text-[#64748b]">
              {filteredEntries.length} of {AUDIT_ENTRIES.length} entries
            </p>
          </div>
        </div>

        <button
          onClick={handleExportCSV}
          className="inline-flex items-center gap-1.5 rounded-lg border border-[rgba(255,255,255,0.1)] px-4 py-2 text-xs font-medium text-[#94a3b8] transition-colors hover:bg-[rgba(255,255,255,0.04)] hover:text-[#e2e8f0]"
        >
          <Download className="h-3.5 w-3.5" />
          Export CSV
        </button>
      </div>

      {/* Filter bar */}
      <div className="rounded-2xl border border-[rgba(255,255,255,0.06)] bg-[#141928] p-4">
        <div className="flex flex-wrap items-end gap-3">
          {/* Search */}
          <div className="flex-1 min-w-[200px]">
            <label className="mb-1 block text-[10px] font-medium uppercase tracking-wider text-[#64748b]">
              Search
            </label>
            <div className="relative">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-[#64748b]" />
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="Search by actor, action, or resource..."
                className="w-full rounded-lg border border-[rgba(255,255,255,0.06)] bg-[#0d1220] py-2 pl-9 pr-3 text-sm text-[#e2e8f0] placeholder-[#475569] outline-none transition-colors focus:border-[#60a5fa]"
              />
            </div>
          </div>

          {/* Category filter */}
          <div className="min-w-[160px]">
            <label className="mb-1 block text-[10px] font-medium uppercase tracking-wider text-[#64748b]">
              Category
            </label>
            <div className="relative">
              <Filter className="absolute left-3 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-[#64748b]" />
              <select
                value={categoryFilter}
                onChange={(e) => setCategoryFilter(e.target.value)}
                className="w-full appearance-none rounded-lg border border-[rgba(255,255,255,0.06)] bg-[#0d1220] py-2 pl-9 pr-8 text-sm text-[#e2e8f0] outline-none transition-colors focus:border-[#60a5fa] cursor-pointer"
              >
                {ACTION_CATEGORIES.map((cat) => (
                  <option key={cat} value={cat}>
                    {cat}
                  </option>
                ))}
              </select>
              <ChevronDown className="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 h-3 w-3 text-[#64748b]" />
            </div>
          </div>

          {/* Date from */}
          <div className="min-w-[150px]">
            <label className="mb-1 block text-[10px] font-medium uppercase tracking-wider text-[#64748b]">
              From
            </label>
            <div className="relative">
              <Calendar className="absolute left-3 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-[#64748b]" />
              <input
                type="date"
                value={dateFrom}
                onChange={(e) => setDateFrom(e.target.value)}
                className="w-full rounded-lg border border-[rgba(255,255,255,0.06)] bg-[#0d1220] py-2 pl-9 pr-3 text-sm text-[#e2e8f0] outline-none transition-colors focus:border-[#60a5fa] [color-scheme:dark]"
              />
            </div>
          </div>

          {/* Date to */}
          <div className="min-w-[150px]">
            <label className="mb-1 block text-[10px] font-medium uppercase tracking-wider text-[#64748b]">
              To
            </label>
            <div className="relative">
              <Calendar className="absolute left-3 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-[#64748b]" />
              <input
                type="date"
                value={dateTo}
                onChange={(e) => setDateTo(e.target.value)}
                className="w-full rounded-lg border border-[rgba(255,255,255,0.06)] bg-[#0d1220] py-2 pl-9 pr-3 text-sm text-[#e2e8f0] outline-none transition-colors focus:border-[#60a5fa] [color-scheme:dark]"
              />
            </div>
          </div>

          {/* Clear filters */}
          {hasFilters && (
            <button
              onClick={clearFilters}
              className="inline-flex items-center gap-1 rounded-lg border border-[rgba(248,113,113,0.2)] px-3 py-2 text-xs text-[#f87171] transition-colors hover:bg-[rgba(248,113,113,0.06)]"
            >
              <X className="h-3 w-3" />
              Clear
            </button>
          )}
        </div>

        {/* Severity filter pills */}
        <div className="mt-3 flex items-center gap-1">
          <span className="text-[10px] font-medium uppercase tracking-wider text-[#64748b] mr-2">
            Severity:
          </span>
          {SEVERITY_FILTERS.map((sev) => (
            <button
              key={sev}
              onClick={() => setSeverityFilter(sev)}
              className="rounded-lg px-2.5 py-1.5 text-[10px] font-medium uppercase transition-colors"
              style={{
                backgroundColor:
                  severityFilter === sev
                    ? sev === "All"
                      ? "rgba(96,165,250,0.15)"
                      : SEVERITY_STYLES[sev]?.bg ?? "rgba(96,165,250,0.15)"
                    : "transparent",
                color:
                  severityFilter === sev
                    ? sev === "All"
                      ? "#60a5fa"
                      : SEVERITY_STYLES[sev]?.color ?? "#60a5fa"
                    : "#64748b",
                border: `1px solid ${
                  severityFilter === sev
                    ? "rgba(96,165,250,0.3)"
                    : "rgba(255,255,255,0.06)"
                }`,
              }}
            >
              {sev}
            </button>
          ))}
        </div>
      </div>

      {/* Audit table */}
      {filteredEntries.length === 0 ? (
        <div className="flex flex-col items-center rounded-2xl border border-[rgba(255,255,255,0.06)] bg-[#141928] py-16">
          <FileText className="h-8 w-8 text-[#475569] mb-3" />
          <p className="text-sm text-[#94a3b8]">No audit entries found</p>
          <p className="text-xs text-[#64748b] mt-1">
            Try adjusting your filters
          </p>
        </div>
      ) : (
        <div className="rounded-2xl border border-[rgba(255,255,255,0.06)] bg-[#141928] overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-[rgba(255,255,255,0.06)] bg-[#0d1220]">
                  <th className="w-8 px-4 py-3" />
                  <th
                    className="cursor-pointer px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-[#64748b] hover:text-[#e2e8f0] transition-colors"
                    onClick={() => setSortAsc((v) => !v)}
                  >
                    <span className="inline-flex items-center gap-1">
                      <Clock className="h-3 w-3" />
                      Timestamp
                      {sortAsc ? (
                        <ChevronUp className="h-3 w-3" />
                      ) : (
                        <ChevronDown className="h-3 w-3" />
                      )}
                    </span>
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-[#64748b]">
                    Actor
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-[#64748b]">
                    Action
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-[#64748b]">
                    Resource
                  </th>
                  <th className="px-4 py-3 text-center text-xs font-medium uppercase tracking-wider text-[#64748b]">
                    Severity
                  </th>
                </tr>
              </thead>
              <tbody>
                {filteredEntries.map((entry, idx) => {
                  const isExpanded = expandedId === entry.id;
                  const sevStyle = SEVERITY_STYLES[entry.severity];
                  const actorConfig =
                    ACTOR_COLORS[entry.actorType] ?? ACTOR_COLORS.user;
                  const ActorIcon = actorConfig.icon;

                  return (
                    <>
                      <tr
                        key={entry.id}
                        className={`border-b border-[rgba(255,255,255,0.04)] transition-colors hover:bg-[rgba(96,165,250,0.04)] cursor-pointer ${
                          idx % 2 === 1
                            ? "bg-[rgba(255,255,255,0.01)]"
                            : ""
                        }`}
                        onClick={() =>
                          setExpandedId(isExpanded ? null : entry.id)
                        }
                      >
                        {/* Expand toggle */}
                        <td className="px-4 py-3 text-[#64748b]">
                          {isExpanded ? (
                            <ChevronUp className="h-3.5 w-3.5" />
                          ) : (
                            <ChevronDown className="h-3.5 w-3.5" />
                          )}
                        </td>

                        {/* Timestamp */}
                        <td className="px-4 py-3 whitespace-nowrap">
                          <span className="text-xs font-mono text-[#94a3b8]">
                            {formatTimestamp(entry.timestamp)}
                          </span>
                        </td>

                        {/* Actor */}
                        <td className="px-4 py-3">
                          <div className="flex items-center gap-2">
                            <div
                              className="flex h-6 w-6 items-center justify-center rounded-full"
                              style={{ backgroundColor: actorConfig.bg }}
                            >
                              <ActorIcon
                                className="h-3 w-3"
                                style={{ color: actorConfig.text }}
                              />
                            </div>
                            <div>
                              <p className="text-xs text-[#e2e8f0] truncate max-w-[160px]">
                                {entry.actor}
                              </p>
                              <span
                                className="text-[9px] font-semibold uppercase"
                                style={{ color: actorConfig.text }}
                              >
                                {entry.actorType}
                              </span>
                            </div>
                          </div>
                        </td>

                        {/* Action */}
                        <td className="px-4 py-3">
                          <div>
                            <span className="rounded-md bg-[rgba(96,165,250,0.08)] px-2 py-0.5 text-[10px] font-medium text-[#60a5fa]">
                              {entry.action}
                            </span>
                            <p className="mt-0.5 text-[10px] text-[#475569]">
                              {entry.category}
                            </p>
                          </div>
                        </td>

                        {/* Resource */}
                        <td className="px-4 py-3">
                          <div>
                            <p className="text-xs text-[#e2e8f0]">
                              {entry.resource}
                            </p>
                            {entry.resourceId && (
                              <p className="text-[10px] font-mono text-[#475569]">
                                {entry.resourceId}
                              </p>
                            )}
                          </div>
                        </td>

                        {/* Severity */}
                        <td className="px-4 py-3 text-center">
                          <span
                            className="inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[9px] font-semibold uppercase"
                            style={{
                              backgroundColor: sevStyle.bg,
                              color: sevStyle.color,
                            }}
                          >
                            {entry.severity === "critical" && (
                              <AlertTriangle className="h-2.5 w-2.5" />
                            )}
                            {entry.severity}
                          </span>
                        </td>
                      </tr>

                      {/* Expanded detail row */}
                      {isExpanded && (
                        <tr key={`${entry.id}-detail`}>
                          <td
                            colSpan={6}
                            className="border-b border-[rgba(255,255,255,0.04)] bg-[rgba(96,165,250,0.02)] px-6 py-4"
                          >
                            <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
                              {/* Details key-value pairs */}
                              {Object.entries(entry.details).map(
                                ([key, value]) => (
                                  <div key={key}>
                                    <p className="text-[10px] uppercase tracking-wider text-[#64748b]">
                                      {key.replace(/_/g, " ")}
                                    </p>
                                    <p className="mt-0.5 text-xs font-mono text-[#e2e8f0]">
                                      {value}
                                    </p>
                                  </div>
                                ),
                              )}

                              {/* Metadata */}
                              {entry.ipAddress && (
                                <div>
                                  <p className="text-[10px] uppercase tracking-wider text-[#64748b]">
                                    IP Address
                                  </p>
                                  <p className="mt-0.5 text-xs font-mono text-[#e2e8f0]">
                                    {entry.ipAddress}
                                  </p>
                                </div>
                              )}
                              {entry.userAgent && (
                                <div>
                                  <p className="text-[10px] uppercase tracking-wider text-[#64748b]">
                                    User Agent
                                  </p>
                                  <p className="mt-0.5 text-xs text-[#94a3b8] break-all">
                                    {entry.userAgent}
                                  </p>
                                </div>
                              )}
                              <div>
                                <p className="text-[10px] uppercase tracking-wider text-[#64748b]">
                                  Full Timestamp
                                </p>
                                <p className="mt-0.5 text-xs font-mono text-[#94a3b8]">
                                  {entry.timestamp}
                                </p>
                              </div>
                              <div>
                                <p className="text-[10px] uppercase tracking-wider text-[#64748b]">
                                  Event ID
                                </p>
                                <p className="mt-0.5 text-xs font-mono text-[#94a3b8]">
                                  {entry.id}
                                </p>
                              </div>
                            </div>
                          </td>
                        </tr>
                      )}
                    </>
                  );
                })}
              </tbody>
            </table>
          </div>

          {/* Footer */}
          <div className="flex items-center justify-between border-t border-[rgba(255,255,255,0.06)] px-4 py-3">
            <p className="text-xs text-[#64748b]">
              Showing {filteredEntries.length} of {AUDIT_ENTRIES.length} entries
            </p>
            <button
              onClick={handleExportCSV}
              className="inline-flex items-center gap-1 text-[10px] font-medium text-[#60a5fa] transition-colors hover:text-[#3b82f6]"
            >
              <Download className="h-3 w-3" />
              Export filtered results
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
