import { useState, useMemo } from "react";
import {
  FileText,
  Search,
  Filter,
  ChevronDown,
  ChevronUp,
  Clock,
  User,
  Shield,
  AlertTriangle,
  Info,
  Activity,
} from "lucide-react";

/**
 * Audit Log Viewer.
 *
 * Displays a filterable, sortable table of audit events with timestamp,
 * actor, action type, and expandable details.
 */

/* ── Data Types ─────────────────────────────────────────────────── */

interface AuditEvent {
  id: string;
  timestamp: string;
  actor: string;
  actorType: "agent" | "admin" | "system";
  action: string;
  category: string;
  severity: "info" | "warning" | "critical";
  resource: string;
  details: Record<string, string>;
  ipAddress?: string;
}

/* ── Demo Data ──────────────────────────────────────────────────── */

const DEMO_EVENTS: AuditEvent[] = [
  {
    id: "evt-001",
    timestamp: "2026-02-21T14:32:10Z",
    actor: "admin@agentchains.io",
    actorType: "admin",
    action: "agent.deactivated",
    category: "Agent Management",
    severity: "warning",
    resource: "agent-xyz-789",
    details: {
      reason: "Suspicious activity detected",
      previous_status: "active",
      new_status: "suspended",
    },
    ipAddress: "192.168.1.100",
  },
  {
    id: "evt-002",
    timestamp: "2026-02-21T14:28:05Z",
    actor: "system",
    actorType: "system",
    action: "rate_limit.triggered",
    category: "Security",
    severity: "warning",
    resource: "agent-abc-123",
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
    resource: "listing-def-456",
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
    resource: "system-config",
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
    resource: "auth-service",
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
    resource: "tx-ghi-890",
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
    resource: "payout-jkl-012",
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
    resource: "redis-cache",
    details: {
      service: "Redis Cache",
      latency_ms: "450",
      threshold_ms: "100",
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

const ACTOR_ICONS: Record<string, typeof User> = {
  agent: Activity,
  admin: Shield,
  system: Info,
};

/* ── Component ──────────────────────────────────────────────────── */

export default function AuditViewer() {
  const [searchQuery, setSearchQuery] = useState("");
  const [categoryFilter, setCategoryFilter] = useState("All");
  const [severityFilter, setSeverityFilter] = useState("All");
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [sortAsc, setSortAsc] = useState(false);

  const filteredEvents = useMemo(() => {
    let result = DEMO_EVENTS;

    if (categoryFilter !== "All") {
      result = result.filter((e) => e.category === categoryFilter);
    }

    if (severityFilter !== "All") {
      result = result.filter((e) => e.severity === severityFilter);
    }

    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase();
      result = result.filter(
        (e) =>
          e.actor.toLowerCase().includes(q) ||
          e.action.toLowerCase().includes(q) ||
          e.resource.toLowerCase().includes(q) ||
          e.category.toLowerCase().includes(q),
      );
    }

    result = [...result].sort((a, b) => {
      const cmp = new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime();
      return sortAsc ? cmp : -cmp;
    });

    return result;
  }, [searchQuery, categoryFilter, severityFilter, sortAsc]);

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
      <div className="flex items-center gap-3">
        <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-[rgba(251,191,36,0.1)]">
          <FileText className="h-4 w-4 text-[#fbbf24]" />
        </div>
        <div>
          <h3 className="text-sm font-semibold text-[#e2e8f0]">Audit Log</h3>
          <p className="text-xs text-[#64748b]">
            {filteredEvents.length} event{filteredEvents.length !== 1 ? "s" : ""}
          </p>
        </div>
      </div>

      {/* Filters */}
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
        {/* Search */}
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-[#64748b]" />
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Search by actor, action, or resource..."
            className="w-full rounded-lg border border-[rgba(255,255,255,0.1)] bg-[#0d1220] py-2 pl-9 pr-4 text-sm text-[#e2e8f0] placeholder-[#475569] outline-none transition-colors focus:border-[#60a5fa]"
          />
        </div>

        {/* Category filter */}
        <div className="flex items-center gap-1.5">
          <Filter className="h-3.5 w-3.5 text-[#64748b] flex-shrink-0" />
          <select
            value={categoryFilter}
            onChange={(e) => setCategoryFilter(e.target.value)}
            className="rounded-lg border border-[rgba(255,255,255,0.1)] bg-[#0d1220] px-3 py-2 text-xs text-[#e2e8f0] outline-none transition-colors focus:border-[#60a5fa]"
          >
            {ACTION_CATEGORIES.map((cat) => (
              <option key={cat} value={cat}>
                {cat}
              </option>
            ))}
          </select>
        </div>

        {/* Severity filter */}
        <div className="flex items-center gap-1">
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

      {/* Events Table */}
      {filteredEvents.length === 0 ? (
        <div className="rounded-2xl border border-[rgba(255,255,255,0.06)] bg-[#141928] p-12 text-center">
          <FileText className="mx-auto h-8 w-8 text-[#475569] mb-3" />
          <p className="text-sm text-[#94a3b8]">No audit events match your filters</p>
        </div>
      ) : (
        <div className="rounded-2xl border border-[rgba(255,255,255,0.06)] bg-[#141928] overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-[rgba(255,255,255,0.06)] bg-[#0d1220]">
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
                  <th className="px-4 py-3 text-center text-xs font-medium uppercase tracking-wider text-[#64748b]">
                    Severity
                  </th>
                  <th className="px-4 py-3 text-center text-xs font-medium uppercase tracking-wider text-[#64748b]">
                    Details
                  </th>
                </tr>
              </thead>
              <tbody>
                {filteredEvents.map((event, idx) => {
                  const isExpanded = expandedId === event.id;
                  const sevStyle = SEVERITY_STYLES[event.severity];
                  const ActorIcon = ACTOR_ICONS[event.actorType] ?? User;

                  return (
                    <>
                      <tr
                        key={event.id}
                        className={`border-b border-[rgba(255,255,255,0.04)] transition-colors hover:bg-[rgba(96,165,250,0.04)] ${
                          idx % 2 === 1 ? "bg-[rgba(255,255,255,0.01)]" : ""
                        }`}
                      >
                        <td className="px-4 py-3 whitespace-nowrap">
                          <span className="text-xs font-mono text-[#94a3b8]">
                            {formatTimestamp(event.timestamp)}
                          </span>
                        </td>

                        <td className="px-4 py-3">
                          <div className="flex items-center gap-2">
                            <ActorIcon className="h-3.5 w-3.5 text-[#64748b]" />
                            <div>
                              <p className="text-xs text-[#e2e8f0]">
                                {event.actor}
                              </p>
                              <p className="text-[9px] uppercase text-[#475569]">
                                {event.actorType}
                              </p>
                            </div>
                          </div>
                        </td>

                        <td className="px-4 py-3">
                          <div>
                            <p className="text-xs font-medium text-[#e2e8f0]">
                              {event.action}
                            </p>
                            <p className="text-[10px] text-[#64748b]">
                              {event.category} / {event.resource}
                            </p>
                          </div>
                        </td>

                        <td className="px-4 py-3 text-center">
                          <span
                            className="inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[9px] font-semibold uppercase"
                            style={{
                              backgroundColor: sevStyle.bg,
                              color: sevStyle.color,
                            }}
                          >
                            {event.severity === "critical" && (
                              <AlertTriangle className="h-2.5 w-2.5" />
                            )}
                            {event.severity}
                          </span>
                        </td>

                        <td className="px-4 py-3 text-center">
                          <button
                            onClick={() =>
                              setExpandedId(isExpanded ? null : event.id)
                            }
                            className="rounded p-1.5 text-[#64748b] transition-colors hover:bg-[rgba(255,255,255,0.04)] hover:text-[#e2e8f0]"
                          >
                            {isExpanded ? (
                              <ChevronUp className="h-3.5 w-3.5" />
                            ) : (
                              <ChevronDown className="h-3.5 w-3.5" />
                            )}
                          </button>
                        </td>
                      </tr>

                      {/* Expanded details */}
                      {isExpanded && (
                        <tr key={`${event.id}-details`}>
                          <td
                            colSpan={5}
                            className="border-b border-[rgba(255,255,255,0.04)] bg-[rgba(96,165,250,0.02)] px-6 py-4"
                          >
                            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
                              {Object.entries(event.details).map(
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
                              {event.ipAddress && (
                                <div>
                                  <p className="text-[10px] uppercase tracking-wider text-[#64748b]">
                                    IP Address
                                  </p>
                                  <p className="mt-0.5 text-xs font-mono text-[#e2e8f0]">
                                    {event.ipAddress}
                                  </p>
                                </div>
                              )}
                              <div>
                                <p className="text-[10px] uppercase tracking-wider text-[#64748b]">
                                  Event ID
                                </p>
                                <p className="mt-0.5 text-xs font-mono text-[#94a3b8]">
                                  {event.id}
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
        </div>
      )}
    </div>
  );
}
