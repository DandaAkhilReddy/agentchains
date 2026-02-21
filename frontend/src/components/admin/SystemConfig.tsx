import { useState } from "react";
import {
  Settings,
  ToggleLeft,
  ToggleRight,
  Save,
  RefreshCw,
  CheckCircle2,
  XCircle,
  AlertTriangle,
  Server,
  Database,
  Wifi,
  Shield,
} from "lucide-react";

/**
 * System Configuration Panel.
 *
 * Displays and allows editing of platform settings, toggling feature flags,
 * and viewing the current status of backend services.
 */

/* ── Data Types ─────────────────────────────────────────────────── */

interface ConfigSetting {
  key: string;
  label: string;
  value: string;
  description: string;
  editable: boolean;
}

interface FeatureFlag {
  key: string;
  label: string;
  enabled: boolean;
  description: string;
}

interface ServiceStatus {
  name: string;
  status: "healthy" | "degraded" | "down";
  latencyMs: number;
  icon: typeof Server;
}

/* ── Demo Data ──────────────────────────────────────────────────── */

const INITIAL_SETTINGS: ConfigSetting[] = [
  {
    key: "max_agents",
    label: "Max Agents",
    value: "10000",
    description: "Maximum number of agents allowed on the platform",
    editable: true,
  },
  {
    key: "session_timeout_min",
    label: "Session Timeout (min)",
    value: "30",
    description: "Default session timeout in minutes for agent connections",
    editable: true,
  },
  {
    key: "rate_limit_rpm",
    label: "Rate Limit (req/min)",
    value: "120",
    description: "Default API rate limit per agent per minute",
    editable: true,
  },
  {
    key: "max_payload_mb",
    label: "Max Payload (MB)",
    value: "10",
    description: "Maximum request payload size in megabytes",
    editable: true,
  },
  {
    key: "platform_version",
    label: "Platform Version",
    value: "1.0.0",
    description: "Current deployed platform version",
    editable: false,
  },
  {
    key: "environment",
    label: "Environment",
    value: "production",
    description: "Current deployment environment",
    editable: false,
  },
];

const INITIAL_FLAGS: FeatureFlag[] = [
  {
    key: "enable_a2ui",
    label: "A2UI Protocol",
    enabled: true,
    description: "Enable Agent-to-UI real-time communication",
  },
  {
    key: "enable_plugins",
    label: "Plugin System",
    enabled: true,
    description: "Enable the plugin marketplace and loader",
  },
  {
    key: "enable_mcp",
    label: "MCP Federation",
    enabled: true,
    description: "Enable Model Context Protocol federation",
  },
  {
    key: "enable_analytics",
    label: "Advanced Analytics",
    enabled: false,
    description: "Enable ML-powered analytics and anomaly detection",
  },
  {
    key: "enable_beta_features",
    label: "Beta Features",
    enabled: false,
    description: "Enable experimental features for early testing",
  },
  {
    key: "maintenance_mode",
    label: "Maintenance Mode",
    enabled: false,
    description: "Put the platform into read-only maintenance mode",
  },
];

const SERVICE_STATUSES: ServiceStatus[] = [
  { name: "API Server", status: "healthy", latencyMs: 12, icon: Server },
  { name: "Database", status: "healthy", latencyMs: 3, icon: Database },
  { name: "WebSocket", status: "healthy", latencyMs: 8, icon: Wifi },
  { name: "Auth Service", status: "healthy", latencyMs: 15, icon: Shield },
  { name: "Redis Cache", status: "degraded", latencyMs: 45, icon: Database },
  { name: "ML Pipeline", status: "down", latencyMs: 0, icon: Server },
];

const STATUS_STYLES: Record<string, { color: string; bg: string; label: string }> = {
  healthy: { color: "#34d399", bg: "rgba(52,211,153,0.1)", label: "Healthy" },
  degraded: { color: "#fbbf24", bg: "rgba(251,191,36,0.1)", label: "Degraded" },
  down: { color: "#f87171", bg: "rgba(248,113,113,0.1)", label: "Down" },
};

/* ── Component ──────────────────────────────────────────────────── */

export default function SystemConfig() {
  const [settings, setSettings] = useState(INITIAL_SETTINGS);
  const [flags, setFlags] = useState(INITIAL_FLAGS);
  const [editValues, setEditValues] = useState<Record<string, string>>({});
  const [saved, setSaved] = useState(false);

  const handleSettingChange = (key: string, value: string) => {
    setEditValues((prev) => ({ ...prev, [key]: value }));
  };

  const handleSave = () => {
    setSettings((prev) =>
      prev.map((s) =>
        editValues[s.key] !== undefined
          ? { ...s, value: editValues[s.key] }
          : s,
      ),
    );
    setEditValues({});
    setSaved(true);
    setTimeout(() => setSaved(false), 2000);
  };

  const handleToggleFlag = (key: string) => {
    setFlags((prev) =>
      prev.map((f) => (f.key === key ? { ...f, enabled: !f.enabled } : f)),
    );
  };

  const hasChanges = Object.keys(editValues).length > 0;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-[rgba(96,165,250,0.1)]">
            <Settings className="h-4 w-4 text-[#60a5fa]" />
          </div>
          <div>
            <h3 className="text-sm font-semibold text-[#e2e8f0]">
              System Configuration
            </h3>
            <p className="text-xs text-[#64748b]">
              Manage platform settings, features, and services
            </p>
          </div>
        </div>

        {hasChanges && (
          <button
            onClick={handleSave}
            className="inline-flex items-center gap-1.5 rounded-lg bg-[#60a5fa] px-4 py-2 text-xs font-medium text-[#0a0e1a] transition-colors hover:bg-[#3b82f6]"
          >
            <Save className="h-3.5 w-3.5" />
            Save Changes
          </button>
        )}

        {saved && (
          <span className="inline-flex items-center gap-1 text-xs text-[#34d399]">
            <CheckCircle2 className="h-3.5 w-3.5" />
            Saved
          </span>
        )}
      </div>

      {/* Settings Table */}
      <div className="rounded-2xl border border-[rgba(255,255,255,0.06)] bg-[#141928] overflow-hidden">
        <div className="border-b border-[rgba(255,255,255,0.06)] px-5 py-3">
          <h4 className="text-xs font-semibold uppercase tracking-wider text-[#94a3b8]">
            Platform Settings
          </h4>
        </div>

        <div className="divide-y divide-[rgba(255,255,255,0.04)]">
          {settings.map((setting) => {
            const editVal = editValues[setting.key];
            const displayVal = editVal !== undefined ? editVal : setting.value;
            const isModified = editVal !== undefined && editVal !== setting.value;

            return (
              <div
                key={setting.key}
                className="flex items-center justify-between px-5 py-3.5"
              >
                <div className="flex-1 mr-4">
                  <p className="text-sm font-medium text-[#e2e8f0]">
                    {setting.label}
                    {isModified && (
                      <span className="ml-2 text-[10px] text-[#fbbf24]">
                        (modified)
                      </span>
                    )}
                  </p>
                  <p className="text-[10px] text-[#64748b] mt-0.5">
                    {setting.description}
                  </p>
                </div>

                {setting.editable ? (
                  <input
                    type="text"
                    value={displayVal}
                    onChange={(e) =>
                      handleSettingChange(setting.key, e.target.value)
                    }
                    className="w-32 rounded-lg border border-[rgba(255,255,255,0.1)] bg-[#0d1220] px-3 py-1.5 text-right text-xs font-mono text-[#e2e8f0] outline-none transition-colors focus:border-[#60a5fa]"
                  />
                ) : (
                  <span className="text-xs font-mono text-[#94a3b8]">
                    {setting.value}
                  </span>
                )}
              </div>
            );
          })}
        </div>
      </div>

      {/* Feature Flags */}
      <div className="rounded-2xl border border-[rgba(255,255,255,0.06)] bg-[#141928] overflow-hidden">
        <div className="border-b border-[rgba(255,255,255,0.06)] px-5 py-3">
          <h4 className="text-xs font-semibold uppercase tracking-wider text-[#94a3b8]">
            Feature Flags
          </h4>
        </div>

        <div className="divide-y divide-[rgba(255,255,255,0.04)]">
          {flags.map((flag) => (
            <div
              key={flag.key}
              className="flex items-center justify-between px-5 py-3.5"
            >
              <div className="flex-1 mr-4">
                <p className="text-sm font-medium text-[#e2e8f0]">
                  {flag.label}
                </p>
                <p className="text-[10px] text-[#64748b] mt-0.5">
                  {flag.description}
                </p>
              </div>

              <button
                onClick={() => handleToggleFlag(flag.key)}
                className="flex-shrink-0 transition-colors"
                title={flag.enabled ? "Disable" : "Enable"}
              >
                {flag.enabled ? (
                  <ToggleRight className="h-6 w-6 text-[#34d399]" />
                ) : (
                  <ToggleLeft className="h-6 w-6 text-[#475569]" />
                )}
              </button>
            </div>
          ))}
        </div>
      </div>

      {/* Service Status */}
      <div className="rounded-2xl border border-[rgba(255,255,255,0.06)] bg-[#141928] overflow-hidden">
        <div className="flex items-center justify-between border-b border-[rgba(255,255,255,0.06)] px-5 py-3">
          <h4 className="text-xs font-semibold uppercase tracking-wider text-[#94a3b8]">
            Service Status
          </h4>
          <button className="inline-flex items-center gap-1 text-[10px] text-[#60a5fa] transition-colors hover:text-[#3b82f6]">
            <RefreshCw className="h-3 w-3" />
            Refresh
          </button>
        </div>

        <div className="grid gap-3 p-5 sm:grid-cols-2 lg:grid-cols-3">
          {SERVICE_STATUSES.map((svc) => {
            const style = STATUS_STYLES[svc.status];
            const Icon = svc.icon;
            const StatusIcon =
              svc.status === "healthy"
                ? CheckCircle2
                : svc.status === "degraded"
                  ? AlertTriangle
                  : XCircle;

            return (
              <div
                key={svc.name}
                className="flex items-center gap-3 rounded-xl border border-[rgba(255,255,255,0.06)] bg-[#0d1220] p-3.5"
              >
                <div
                  className="flex h-9 w-9 items-center justify-center rounded-lg"
                  style={{ backgroundColor: style.bg }}
                >
                  <Icon className="h-4 w-4" style={{ color: style.color }} />
                </div>
                <div className="flex-1">
                  <p className="text-xs font-medium text-[#e2e8f0]">
                    {svc.name}
                  </p>
                  <div className="flex items-center gap-2 mt-0.5">
                    <StatusIcon
                      className="h-3 w-3"
                      style={{ color: style.color }}
                    />
                    <span
                      className="text-[10px] font-semibold"
                      style={{ color: style.color }}
                    >
                      {style.label}
                    </span>
                    {svc.latencyMs > 0 && (
                      <span className="text-[10px] text-[#64748b]">
                        {svc.latencyMs}ms
                      </span>
                    )}
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
