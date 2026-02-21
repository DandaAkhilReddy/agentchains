import { useState, useCallback } from "react";
import {
  Settings,
  ToggleLeft,
  ToggleRight,
  Shield,
  Key,
  Activity,
  Save,
  RefreshCw,
  Plus,
  Trash2,
  Copy,
  Check,
  Eye,
  EyeOff,
  AlertTriangle,
  Server,
  Gauge,
  CheckCircle2,
  XCircle,
} from "lucide-react";

/**
 * System Configuration Admin Panel.
 *
 * Provides:
 *   - Feature flags toggle list
 *   - Rate limit settings (with save)
 *   - API key management (create, revoke, copy)
 *   - Health status dashboard with green/red indicators
 */

/* ── Data Types ─────────────────────────────────────────────────── */

interface FeatureFlag {
  id: string;
  name: string;
  description: string;
  enabled: boolean;
  category: string;
}

interface RateLimitConfig {
  id: string;
  endpoint: string;
  requestsPerMinute: number;
  burstLimit: number;
}

interface ApiKey {
  id: string;
  name: string;
  key: string;
  createdAt: string;
  lastUsed?: string;
  active: boolean;
}

interface HealthService {
  name: string;
  status: "healthy" | "degraded" | "down";
  latencyMs: number;
  uptime: string;
}

/* ── Static Data ────────────────────────────────────────────────── */

const INITIAL_FLAGS: FeatureFlag[] = [
  {
    id: "ff-a2ui",
    name: "A2UI Protocol",
    description: "Enable Agent-to-UI real-time rendering protocol",
    enabled: true,
    category: "Core",
  },
  {
    id: "ff-marketplace",
    name: "Plugin Marketplace",
    description: "Enable the plugin marketplace for all users",
    enabled: true,
    category: "Features",
  },
  {
    id: "ff-billing",
    name: "Billing Module",
    description: "Enable billing and subscription management",
    enabled: true,
    category: "Features",
  },
  {
    id: "ff-audit-log",
    name: "Audit Logging",
    description: "Log all admin actions to the audit trail",
    enabled: true,
    category: "Security",
  },
  {
    id: "ff-agent-sandbox",
    name: "Agent Sandboxing",
    description: "Run agents in isolated sandbox environments",
    enabled: false,
    category: "Security",
  },
  {
    id: "ff-multi-region",
    name: "Multi-Region Routing",
    description: "Enable cross-region agent routing and failover",
    enabled: false,
    category: "Infrastructure",
  },
  {
    id: "ff-dark-mode",
    name: "Dark Mode (Beta)",
    description: "Enable experimental dark mode theme toggle",
    enabled: true,
    category: "UI",
  },
  {
    id: "ff-websocket-v2",
    name: "WebSocket v2",
    description: "Use the new WebSocket connection protocol",
    enabled: false,
    category: "Infrastructure",
  },
];

const INITIAL_RATE_LIMITS: RateLimitConfig[] = [
  {
    id: "rl-api",
    endpoint: "/api/v1/*",
    requestsPerMinute: 1000,
    burstLimit: 50,
  },
  {
    id: "rl-agents",
    endpoint: "/api/v1/agents",
    requestsPerMinute: 500,
    burstLimit: 30,
  },
  {
    id: "rl-transactions",
    endpoint: "/api/v1/transactions",
    requestsPerMinute: 200,
    burstLimit: 20,
  },
  {
    id: "rl-auth",
    endpoint: "/api/v1/auth/*",
    requestsPerMinute: 100,
    burstLimit: 10,
  },
];

const INITIAL_API_KEYS: ApiKey[] = [
  {
    id: "key-1",
    name: "Production API",
    key: "ak_prod_xK8mN2pR5vW9qT3j",
    createdAt: "2026-01-15T10:00:00Z",
    lastUsed: "2026-02-21T08:30:00Z",
    active: true,
  },
  {
    id: "key-2",
    name: "Staging API",
    key: "ak_stg_bL4fH7cY1dA6mJ0e",
    createdAt: "2026-02-01T14:00:00Z",
    lastUsed: "2026-02-20T16:45:00Z",
    active: true,
  },
  {
    id: "key-3",
    name: "CI/CD Pipeline",
    key: "ak_ci_nP2wF9kS8tR6vQ3x",
    createdAt: "2025-12-10T09:00:00Z",
    lastUsed: "2026-02-19T22:10:00Z",
    active: true,
  },
];

const HEALTH_SERVICES: HealthService[] = [
  { name: "API Gateway", status: "healthy", latencyMs: 12, uptime: "99.99%" },
  { name: "PostgreSQL", status: "healthy", latencyMs: 3, uptime: "99.98%" },
  { name: "Redis Cache", status: "healthy", latencyMs: 1, uptime: "99.99%" },
  { name: "WebSocket Hub", status: "healthy", latencyMs: 8, uptime: "99.97%" },
  { name: "Task Queue", status: "degraded", latencyMs: 45, uptime: "99.85%" },
  { name: "Object Storage", status: "healthy", latencyMs: 18, uptime: "99.99%" },
];

/* ── Status colors ──────────────────────────────────────────────── */

const HEALTH_COLORS: Record<string, { bg: string; text: string; glow: string }> = {
  healthy: {
    bg: "rgba(52,211,153,0.1)",
    text: "#34d399",
    glow: "0 0 8px rgba(52,211,153,0.4)",
  },
  degraded: {
    bg: "rgba(251,191,36,0.1)",
    text: "#fbbf24",
    glow: "0 0 8px rgba(251,191,36,0.4)",
  },
  down: {
    bg: "rgba(248,113,113,0.1)",
    text: "#f87171",
    glow: "0 0 8px rgba(248,113,113,0.4)",
  },
};

/* ── Component ──────────────────────────────────────────────────── */

export default function SystemConfig() {
  const [flags, setFlags] = useState(INITIAL_FLAGS);
  const [rateLimits, setRateLimits] = useState(INITIAL_RATE_LIMITS);
  const [apiKeys, setApiKeys] = useState(INITIAL_API_KEYS);
  const [isSaving, setIsSaving] = useState(false);
  const [copiedKeyId, setCopiedKeyId] = useState<string | null>(null);
  const [visibleKeyId, setVisibleKeyId] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<
    "flags" | "ratelimits" | "apikeys" | "health"
  >("flags");

  /* ── Flag toggle ──────────────────────────────────────────── */

  const toggleFlag = useCallback((flagId: string) => {
    setFlags((prev) =>
      prev.map((f) =>
        f.id === flagId ? { ...f, enabled: !f.enabled } : f,
      ),
    );
  }, []);

  /* ── Rate limit save ──────────────────────────────────────── */

  const updateRateLimit = useCallback(
    (id: string, field: "requestsPerMinute" | "burstLimit", value: number) => {
      setRateLimits((prev) =>
        prev.map((rl) =>
          rl.id === id ? { ...rl, [field]: value } : rl,
        ),
      );
    },
    [],
  );

  const handleSaveRateLimits = useCallback(async () => {
    setIsSaving(true);
    // Simulate saving
    await new Promise((resolve) => setTimeout(resolve, 800));
    setIsSaving(false);
  }, []);

  /* ── API Key actions ──────────────────────────────────────── */

  const handleCopyKey = useCallback(async (keyId: string, keyValue: string) => {
    await navigator.clipboard.writeText(keyValue);
    setCopiedKeyId(keyId);
    setTimeout(() => setCopiedKeyId(null), 2000);
  }, []);

  const handleRevokeKey = useCallback((keyId: string) => {
    setApiKeys((prev) =>
      prev.map((k) =>
        k.id === keyId ? { ...k, active: false } : k,
      ),
    );
  }, []);

  const handleCreateKey = useCallback(() => {
    const newKey: ApiKey = {
      id: `key-${Date.now()}`,
      name: `New Key ${apiKeys.length + 1}`,
      key: `ak_new_${Math.random().toString(36).slice(2, 18)}`,
      createdAt: new Date().toISOString(),
      active: true,
    };
    setApiKeys((prev) => [newKey, ...prev]);
  }, [apiKeys.length]);

  /* ── Tab config ───────────────────────────────────────────── */

  const tabs = [
    { id: "flags" as const, label: "Feature Flags", icon: ToggleRight, count: flags.length },
    { id: "ratelimits" as const, label: "Rate Limits", icon: Gauge, count: rateLimits.length },
    { id: "apikeys" as const, label: "API Keys", icon: Key, count: apiKeys.filter((k) => k.active).length },
    { id: "health" as const, label: "Health Status", icon: Activity, count: HEALTH_SERVICES.length },
  ];

  // Group feature flags by category
  const flagCategories = flags.reduce<Record<string, FeatureFlag[]>>(
    (acc, flag) => {
      if (!acc[flag.category]) acc[flag.category] = [];
      acc[flag.category].push(flag);
      return acc;
    },
    {},
  );

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center gap-3">
        <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-[rgba(96,165,250,0.1)]">
          <Settings className="h-4 w-4 text-[#60a5fa]" />
        </div>
        <div>
          <h3 className="text-sm font-semibold text-[#e2e8f0]">
            System Configuration
          </h3>
          <p className="text-xs text-[#64748b]">
            Manage platform settings, keys, and monitoring
          </p>
        </div>
      </div>

      {/* Tab navigation */}
      <div className="flex gap-1 rounded-xl border border-[rgba(255,255,255,0.06)] bg-[#0d1220] p-1">
        {tabs.map((tab) => {
          const Icon = tab.icon;
          const isActive = activeTab === tab.id;
          return (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`flex items-center gap-2 rounded-lg px-4 py-2 text-xs font-medium transition-all duration-200 ${
                isActive
                  ? "bg-[#141928] text-[#e2e8f0] shadow-sm"
                  : "text-[#64748b] hover:text-[#94a3b8]"
              }`}
            >
              <Icon className="h-3.5 w-3.5" />
              {tab.label}
              <span
                className="rounded-full px-1.5 py-0.5 text-[9px] font-semibold"
                style={{
                  backgroundColor: isActive
                    ? "rgba(96,165,250,0.15)"
                    : "rgba(255,255,255,0.04)",
                  color: isActive ? "#60a5fa" : "#475569",
                }}
              >
                {tab.count}
              </span>
            </button>
          );
        })}
      </div>

      {/* ── Feature Flags Tab ───────────────────────────────── */}
      {activeTab === "flags" && (
        <div className="rounded-2xl border border-[rgba(255,255,255,0.06)] bg-[#141928] overflow-hidden">
          <div className="border-b border-[rgba(255,255,255,0.06)] px-6 py-4">
            <div className="flex items-center gap-2">
              <Shield className="h-4 w-4 text-[#a78bfa]" />
              <h4 className="text-sm font-semibold text-[#e2e8f0]">
                Feature Flags
              </h4>
            </div>
            <p className="mt-1 text-xs text-[#64748b]">
              Toggle features on or off across the platform
            </p>
          </div>

          <div className="divide-y divide-[rgba(255,255,255,0.04)]">
            {Object.entries(flagCategories).map(([category, categoryFlags]) => (
              <div key={category}>
                <div className="bg-[#0d1220] px-6 py-2">
                  <span className="text-[10px] font-semibold uppercase tracking-wider text-[#64748b]">
                    {category}
                  </span>
                </div>
                {categoryFlags.map((flag) => (
                  <div
                    key={flag.id}
                    className="flex items-center justify-between px-6 py-4 transition-colors hover:bg-[rgba(255,255,255,0.02)]"
                  >
                    <div className="flex-1">
                      <p className="text-sm font-medium text-[#e2e8f0]">
                        {flag.name}
                      </p>
                      <p className="mt-0.5 text-xs text-[#64748b]">
                        {flag.description}
                      </p>
                    </div>
                    <button
                      onClick={() => toggleFlag(flag.id)}
                      className="flex-shrink-0 ml-4 transition-colors"
                      title={flag.enabled ? "Disable" : "Enable"}
                    >
                      {flag.enabled ? (
                        <ToggleRight className="h-7 w-7 text-[#34d399]" />
                      ) : (
                        <ToggleLeft className="h-7 w-7 text-[#475569]" />
                      )}
                    </button>
                  </div>
                ))}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* ── Rate Limits Tab ─────────────────────────────────── */}
      {activeTab === "ratelimits" && (
        <div className="rounded-2xl border border-[rgba(255,255,255,0.06)] bg-[#141928] overflow-hidden">
          <div className="flex items-center justify-between border-b border-[rgba(255,255,255,0.06)] px-6 py-4">
            <div>
              <div className="flex items-center gap-2">
                <Gauge className="h-4 w-4 text-[#fbbf24]" />
                <h4 className="text-sm font-semibold text-[#e2e8f0]">
                  Rate Limits
                </h4>
              </div>
              <p className="mt-1 text-xs text-[#64748b]">
                Configure request rate limits per endpoint
              </p>
            </div>
            <button
              onClick={handleSaveRateLimits}
              disabled={isSaving}
              className="inline-flex items-center gap-1.5 rounded-lg bg-[#60a5fa] px-4 py-2 text-xs font-semibold text-[#0a0e1a] transition-colors hover:bg-[#3b82f6] disabled:opacity-60"
            >
              {isSaving ? (
                <RefreshCw className="h-3 w-3 animate-spin" />
              ) : (
                <Save className="h-3 w-3" />
              )}
              {isSaving ? "Saving..." : "Save Changes"}
            </button>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-[rgba(255,255,255,0.06)] bg-[#0d1220]">
                  <th className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider text-[#64748b]">
                    Endpoint
                  </th>
                  <th className="px-6 py-3 text-center text-xs font-medium uppercase tracking-wider text-[#64748b]">
                    Requests / min
                  </th>
                  <th className="px-6 py-3 text-center text-xs font-medium uppercase tracking-wider text-[#64748b]">
                    Burst Limit
                  </th>
                </tr>
              </thead>
              <tbody>
                {rateLimits.map((rl, idx) => (
                  <tr
                    key={rl.id}
                    className={`border-b border-[rgba(255,255,255,0.04)] ${
                      idx % 2 === 1 ? "bg-[rgba(255,255,255,0.01)]" : ""
                    }`}
                  >
                    <td className="px-6 py-3">
                      <code className="text-xs font-mono text-[#e2e8f0]">
                        {rl.endpoint}
                      </code>
                    </td>
                    <td className="px-6 py-3 text-center">
                      <input
                        type="number"
                        value={rl.requestsPerMinute}
                        onChange={(e) =>
                          updateRateLimit(
                            rl.id,
                            "requestsPerMinute",
                            Number(e.target.value),
                          )
                        }
                        className="w-24 rounded-lg border border-[rgba(255,255,255,0.1)] bg-[#0d1220] px-3 py-1.5 text-center text-xs font-mono text-[#e2e8f0] outline-none transition-colors focus:border-[#60a5fa]"
                      />
                    </td>
                    <td className="px-6 py-3 text-center">
                      <input
                        type="number"
                        value={rl.burstLimit}
                        onChange={(e) =>
                          updateRateLimit(
                            rl.id,
                            "burstLimit",
                            Number(e.target.value),
                          )
                        }
                        className="w-24 rounded-lg border border-[rgba(255,255,255,0.1)] bg-[#0d1220] px-3 py-1.5 text-center text-xs font-mono text-[#e2e8f0] outline-none transition-colors focus:border-[#60a5fa]"
                      />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* ── API Keys Tab ────────────────────────────────────── */}
      {activeTab === "apikeys" && (
        <div className="rounded-2xl border border-[rgba(255,255,255,0.06)] bg-[#141928] overflow-hidden">
          <div className="flex items-center justify-between border-b border-[rgba(255,255,255,0.06)] px-6 py-4">
            <div>
              <div className="flex items-center gap-2">
                <Key className="h-4 w-4 text-[#34d399]" />
                <h4 className="text-sm font-semibold text-[#e2e8f0]">
                  API Keys
                </h4>
              </div>
              <p className="mt-1 text-xs text-[#64748b]">
                Manage API keys for programmatic access
              </p>
            </div>
            <button
              onClick={handleCreateKey}
              className="inline-flex items-center gap-1.5 rounded-lg bg-[#60a5fa] px-4 py-2 text-xs font-semibold text-[#0a0e1a] transition-colors hover:bg-[#3b82f6]"
            >
              <Plus className="h-3 w-3" />
              Create Key
            </button>
          </div>

          <div className="divide-y divide-[rgba(255,255,255,0.04)]">
            {apiKeys.map((key) => (
              <div
                key={key.id}
                className={`flex items-center gap-4 px-6 py-4 transition-colors hover:bg-[rgba(255,255,255,0.02)] ${
                  !key.active ? "opacity-50" : ""
                }`}
              >
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <p className="text-sm font-medium text-[#e2e8f0]">
                      {key.name}
                    </p>
                    {!key.active && (
                      <span className="rounded-full bg-[rgba(248,113,113,0.15)] px-2 py-0.5 text-[9px] font-semibold uppercase text-[#f87171]">
                        Revoked
                      </span>
                    )}
                  </div>
                  <div className="mt-1 flex items-center gap-2">
                    <code className="text-[11px] font-mono text-[#64748b]">
                      {visibleKeyId === key.id
                        ? key.key
                        : key.key.slice(0, 8) + "..." + key.key.slice(-4)}
                    </code>
                    <button
                      onClick={() =>
                        setVisibleKeyId((prev) =>
                          prev === key.id ? null : key.id,
                        )
                      }
                      className="text-[#475569] hover:text-[#94a3b8] transition-colors"
                      title={visibleKeyId === key.id ? "Hide" : "Reveal"}
                    >
                      {visibleKeyId === key.id ? (
                        <EyeOff className="h-3 w-3" />
                      ) : (
                        <Eye className="h-3 w-3" />
                      )}
                    </button>
                  </div>
                  <div className="mt-1 flex gap-4 text-[10px] text-[#475569]">
                    <span>
                      Created:{" "}
                      {new Date(key.createdAt).toLocaleDateString()}
                    </span>
                    {key.lastUsed && (
                      <span>
                        Last used:{" "}
                        {new Date(key.lastUsed).toLocaleDateString()}
                      </span>
                    )}
                  </div>
                </div>

                <div className="flex items-center gap-1.5">
                  {key.active && (
                    <>
                      <button
                        onClick={() => handleCopyKey(key.id, key.key)}
                        className="rounded-lg p-2 text-[#64748b] transition-colors hover:bg-[rgba(255,255,255,0.04)] hover:text-[#e2e8f0]"
                        title="Copy key"
                      >
                        {copiedKeyId === key.id ? (
                          <Check className="h-3.5 w-3.5 text-[#34d399]" />
                        ) : (
                          <Copy className="h-3.5 w-3.5" />
                        )}
                      </button>
                      <button
                        onClick={() => handleRevokeKey(key.id)}
                        className="rounded-lg p-2 text-[#64748b] transition-colors hover:bg-[rgba(248,113,113,0.1)] hover:text-[#f87171]"
                        title="Revoke key"
                      >
                        <Trash2 className="h-3.5 w-3.5" />
                      </button>
                    </>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* ── Health Status Tab ───────────────────────────────── */}
      {activeTab === "health" && (
        <div className="space-y-4">
          {/* Overall status banner */}
          {(() => {
            const hasDown = HEALTH_SERVICES.some((s) => s.status === "down");
            const hasDegraded = HEALTH_SERVICES.some(
              (s) => s.status === "degraded",
            );
            const overallStatus = hasDown
              ? "down"
              : hasDegraded
                ? "degraded"
                : "healthy";
            const colors = HEALTH_COLORS[overallStatus];

            return (
              <div
                className="rounded-2xl border p-5"
                style={{
                  borderColor: `${colors.text}30`,
                  backgroundColor: colors.bg,
                }}
              >
                <div className="flex items-center gap-3">
                  <div
                    className="h-3.5 w-3.5 rounded-full"
                    style={{
                      backgroundColor: colors.text,
                      boxShadow: colors.glow,
                    }}
                  />
                  <span
                    className="text-sm font-semibold"
                    style={{ color: colors.text }}
                  >
                    {overallStatus === "healthy"
                      ? "All Systems Operational"
                      : overallStatus === "degraded"
                        ? "Partial Service Degradation"
                        : "Service Outage Detected"}
                  </span>
                  {overallStatus !== "healthy" && (
                    <AlertTriangle
                      className="h-4 w-4"
                      style={{ color: colors.text }}
                    />
                  )}
                </div>
              </div>
            );
          })()}

          {/* Service grid */}
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {HEALTH_SERVICES.map((service) => {
              const colors = HEALTH_COLORS[service.status];
              const StatusIcon =
                service.status === "healthy"
                  ? CheckCircle2
                  : service.status === "degraded"
                    ? AlertTriangle
                    : XCircle;
              return (
                <div
                  key={service.name}
                  className="rounded-2xl border border-[rgba(255,255,255,0.06)] bg-[#141928] p-5 transition-shadow hover:shadow-lg"
                >
                  <div className="flex items-center justify-between mb-3">
                    <div className="flex items-center gap-2">
                      <Server className="h-3.5 w-3.5 text-[#94a3b8]" />
                      <p className="text-sm font-medium text-[#e2e8f0]">
                        {service.name}
                      </p>
                    </div>
                    <div
                      className="h-2.5 w-2.5 rounded-full"
                      style={{
                        backgroundColor: colors.text,
                        boxShadow: colors.glow,
                      }}
                    />
                  </div>

                  <div className="space-y-2">
                    <div className="flex items-center justify-between">
                      <span className="text-[10px] uppercase tracking-wider text-[#64748b]">
                        Status
                      </span>
                      <span
                        className="inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[9px] font-semibold uppercase"
                        style={{
                          backgroundColor: colors.bg,
                          color: colors.text,
                        }}
                      >
                        <StatusIcon className="h-2.5 w-2.5" />
                        {service.status}
                      </span>
                    </div>
                    <div className="flex items-center justify-between">
                      <span className="text-[10px] uppercase tracking-wider text-[#64748b]">
                        Latency
                      </span>
                      <span className="text-xs font-mono text-[#e2e8f0]">
                        {service.latencyMs}ms
                      </span>
                    </div>
                    <div className="flex items-center justify-between">
                      <span className="text-[10px] uppercase tracking-wider text-[#64748b]">
                        Uptime
                      </span>
                      <span className="text-xs font-mono text-[#34d399]">
                        {service.uptime}
                      </span>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}
