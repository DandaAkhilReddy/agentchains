import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useAuth } from "../hooks/useAuth";
import { useToast } from "../components/Toast";
import PageHeader from "../components/PageHeader";
import {
  Plug,
  Webhook,
  Copy,
  Check,
  Trash2,
  Zap,
  ExternalLink,
  Radio,
  ShieldCheck,
  Terminal,
  Lock,
} from "lucide-react";
import {
  registerOpenClawWebhook,
  fetchOpenClawWebhooks,
  deleteOpenClawWebhook,
  testOpenClawWebhook,
  fetchOpenClawStatus,
} from "../lib/api";
import { relativeTime } from "../lib/format";

const EVENT_TYPES = [
  { id: "opportunity", label: "Opportunity", description: "New revenue opportunities detected" },
  { id: "demand_spike", label: "Demand Spike", description: "Surge in search queries" },
  { id: "transaction", label: "Transaction", description: "Purchases of your listings" },
  { id: "listing_created", label: "Listing Created", description: "New listings in your categories" },
];

const API_DOCS_URL = "https://agentchains-marketplace.orangemeadow-3bb536df.eastus.azurecontainerapps.io/docs";

export default function IntegrationsPage() {
  const { token, login } = useAuth();
  const { toast } = useToast();
  const queryClient = useQueryClient();

  const [inputToken, setInputToken] = useState("");
  const [gatewayUrl, setGatewayUrl] = useState("");
  const [bearerToken, setBearerToken] = useState("");
  const [selectedEvents, setSelectedEvents] = useState<string[]>([]);
  const [copiedId, setCopiedId] = useState<string | null>(null);

  // ── Queries ──

  const { data: status } = useQuery({
    queryKey: ["openclaw-status"],
    queryFn: () => fetchOpenClawStatus(token!),
    enabled: !!token,
    refetchInterval: 30_000,
  });

  const { data: webhooksData, isLoading: webhooksLoading } = useQuery({
    queryKey: ["openclaw-webhooks"],
    queryFn: () => fetchOpenClawWebhooks(token!),
    enabled: !!token,
  });

  // ── Mutations ──

  const registerMutation = useMutation({
    mutationFn: () =>
      registerOpenClawWebhook(token!, {
        gateway_url: gatewayUrl,
        bearer_token: bearerToken,
        event_types: selectedEvents,
        filters: {},
      }),
    onSuccess: () => {
      toast("Webhook registered successfully!", "success");
      setGatewayUrl("");
      setBearerToken("");
      setSelectedEvents([]);
      queryClient.invalidateQueries({ queryKey: ["openclaw-webhooks"] });
      queryClient.invalidateQueries({ queryKey: ["openclaw-status"] });
    },
    onError: (err) => toast((err as Error).message, "error"),
  });

  const deleteMutation = useMutation({
    mutationFn: (webhookId: string) => deleteOpenClawWebhook(token!, webhookId),
    onSuccess: () => {
      toast("Webhook deleted", "success");
      queryClient.invalidateQueries({ queryKey: ["openclaw-webhooks"] });
      queryClient.invalidateQueries({ queryKey: ["openclaw-status"] });
    },
    onError: (err) => toast((err as Error).message, "error"),
  });

  const testMutation = useMutation({
    mutationFn: (webhookId: string) => testOpenClawWebhook(token!, webhookId),
    onSuccess: (data) => {
      toast(data.success ? "Test webhook delivered!" : `Test failed: ${data.message}`, data.success ? "success" : "error");
    },
    onError: (err) => toast((err as Error).message, "error"),
  });

  // ── Helpers ──

  const toggleEvent = (eventId: string) => {
    setSelectedEvents((prev) =>
      prev.includes(eventId) ? prev.filter((e) => e !== eventId) : [...prev, eventId],
    );
  };

  const copyToClipboard = (text: string, id: string) => {
    navigator.clipboard.writeText(text);
    setCopiedId(id);
    toast("Copied to clipboard", "info");
    setTimeout(() => setCopiedId(null), 2000);
  };

  const handleConnect = () => {
    const t = inputToken.trim();
    if (t) login(t);
  };

  // ── Auth gate ──

  if (!token) {
    return (
      <div className="min-h-[70vh] flex items-center justify-center animate-fade-in">
        <div
          className="relative w-full max-w-md rounded-2xl p-8 space-y-6"
          style={{
            background: "#141928",
            border: "1px solid rgba(255,255,255,0.06)",
            boxShadow: "0 0 40px rgba(96,165,250,0.06), 0 8px 32px rgba(0,0,0,0.4)",
          }}
        >
          {/* Decorative glow */}
          <div
            className="absolute -top-px left-1/2 -translate-x-1/2 h-px w-2/3"
            style={{ background: "linear-gradient(90deg, transparent, #60a5fa, transparent)" }}
          />

          <div className="text-center space-y-2">
            <div
              className="mx-auto flex h-12 w-12 items-center justify-center rounded-xl"
              style={{
                background: "rgba(96,165,250,0.1)",
                boxShadow: "0 0 20px rgba(96,165,250,0.15)",
              }}
            >
              <Lock className="h-6 w-6 text-[#60a5fa]" />
            </div>
            <h3
              className="text-lg font-bold"
              style={{
                background: "linear-gradient(135deg, #60a5fa, #a78bfa)",
                WebkitBackgroundClip: "text",
                WebkitTextFillColor: "transparent",
              }}
            >
              Connect Your Agent
            </h3>
            <p className="text-sm text-[#94a3b8]">
              Paste your agent JWT to manage integrations
            </p>
          </div>

          <input
            type="text"
            value={inputToken}
            onChange={(e) => setInputToken(e.target.value)}
            placeholder="eyJhbGciOi..."
            className="w-full rounded-xl px-4 py-3 text-sm text-[#e2e8f0] placeholder-[#64748b] outline-none transition-all focus:ring-2 focus:ring-[#60a5fa]/40"
            style={{
              background: "#1a2035",
              border: "1px solid rgba(255,255,255,0.06)",
              fontFamily: "var(--font-mono)",
            }}
          />

          <button
            onClick={handleConnect}
            disabled={!inputToken.trim()}
            className="w-full rounded-xl px-4 py-3 text-sm font-semibold text-white transition-all hover:shadow-[0_0_20px_rgba(96,165,250,0.3)] disabled:opacity-40 disabled:cursor-not-allowed"
            style={{
              background: "linear-gradient(135deg, #3b82f6, #6366f1)",
            }}
          >
            Connect
          </button>
        </div>
      </div>
    );
  }

  const webhooks = webhooksData?.webhooks ?? [];
  const isConnected = status?.connected ?? false;

  return (
    <div className="space-y-8 animate-fade-in">
      {/* Header */}
      <div className="flex items-center justify-between">
        <PageHeader title="Integrations" subtitle="Connect OpenClaw agents and webhooks" icon={Plug} />
        <div className="flex items-center gap-2.5">
          <span
            className="inline-flex h-2.5 w-2.5 rounded-full"
            style={{
              backgroundColor: isConnected ? "#34d399" : "#f87171",
              boxShadow: isConnected
                ? "0 0 8px rgba(52,211,153,0.5), 0 0 16px rgba(52,211,153,0.2)"
                : "0 0 8px rgba(248,113,113,0.5)",
            }}
          />
          <span className="text-xs font-medium text-[#94a3b8]">
            {isConnected ? "Connected" : "Disconnected"}
          </span>
          {status && (
            <span className="text-xs text-[#64748b] ml-2 font-mono">
              {status.active_count}/{status.webhooks_count} active
            </span>
          )}
        </div>
      </div>

      {/* 2-Column Layout */}
      <div className="grid gap-6 lg:grid-cols-2">
        {/* OpenClaw Connection Card */}
        <div
          className="rounded-2xl p-6 transition-all"
          style={{
            background: "#141928",
            border: "1px solid rgba(255,255,255,0.06)",
            boxShadow: "0 4px 24px rgba(0,0,0,0.3)",
          }}
        >
          <h3 className="mb-5 flex items-center gap-2.5">
            <div
              className="flex h-8 w-8 items-center justify-center rounded-lg"
              style={{ background: "rgba(96,165,250,0.1)" }}
            >
              <Webhook className="h-4 w-4 text-[#60a5fa]" />
            </div>
            <span
              className="text-sm font-bold"
              style={{
                background: "linear-gradient(135deg, #60a5fa, #a78bfa)",
                WebkitBackgroundClip: "text",
                WebkitTextFillColor: "transparent",
              }}
            >
              Connect OpenClaw
            </span>
          </h3>

          <div className="space-y-4">
            {/* Gateway URL */}
            <div>
              <label className="mb-1.5 block text-xs font-medium text-[#94a3b8]">Gateway URL</label>
              <input
                type="text"
                value={gatewayUrl}
                onChange={(e) => setGatewayUrl(e.target.value)}
                placeholder="https://your-openclaw-gateway.example.com/webhook"
                className="w-full rounded-xl px-3.5 py-2.5 text-sm text-[#e2e8f0] placeholder-[#64748b] outline-none transition-all focus:ring-2 focus:ring-[#60a5fa]/30"
                style={{
                  background: "#1a2035",
                  border: "1px solid rgba(255,255,255,0.06)",
                }}
              />
            </div>

            {/* Bearer Token */}
            <div>
              <label className="mb-1.5 block text-xs font-medium text-[#94a3b8]">Bearer Token</label>
              <input
                type="password"
                value={bearerToken}
                onChange={(e) => setBearerToken(e.target.value)}
                placeholder="your-webhook-secret-token"
                className="w-full rounded-xl px-3.5 py-2.5 text-sm text-[#e2e8f0] placeholder-[#64748b] outline-none transition-all focus:ring-2 focus:ring-[#60a5fa]/30"
                style={{
                  background: "#1a2035",
                  border: "1px solid rgba(255,255,255,0.06)",
                }}
              />
            </div>

            {/* Event Types */}
            <div>
              <label className="mb-2 block text-xs font-medium text-[#94a3b8]">Event Types</label>
              <div className="grid grid-cols-2 gap-2.5">
                {EVENT_TYPES.map((evt) => {
                  const isSelected = selectedEvents.includes(evt.id);
                  return (
                    <button
                      key={evt.id}
                      onClick={() => toggleEvent(evt.id)}
                      className="flex items-start gap-2.5 rounded-xl p-3 text-left transition-all"
                      style={{
                        background: isSelected ? "rgba(96,165,250,0.08)" : "#1a2035",
                        border: isSelected
                          ? "1px solid rgba(96,165,250,0.3)"
                          : "1px solid rgba(255,255,255,0.06)",
                        boxShadow: isSelected ? "0 0 12px rgba(96,165,250,0.1)" : "none",
                      }}
                    >
                      {/* Checkbox */}
                      <div
                        className="mt-0.5 flex h-4 w-4 shrink-0 items-center justify-center rounded"
                        style={{
                          background: isSelected ? "#60a5fa" : "transparent",
                          border: isSelected ? "none" : "1.5px solid #64748b",
                        }}
                      >
                        {isSelected && <Check className="h-3 w-3 text-white" />}
                      </div>
                      <div className="min-w-0">
                        <span className={`block text-xs font-semibold ${isSelected ? "text-[#60a5fa]" : "text-[#e2e8f0]"}`}>
                          {evt.label}
                        </span>
                        <span className="mt-0.5 block text-[10px] text-[#64748b] leading-tight">
                          {evt.description}
                        </span>
                      </div>
                    </button>
                  );
                })}
              </div>
            </div>

            {/* Connect Button */}
            <button
              onClick={() => registerMutation.mutate()}
              disabled={!gatewayUrl.trim() || selectedEvents.length === 0 || registerMutation.isPending}
              className="w-full rounded-xl px-4 py-3 text-sm font-semibold text-white transition-all hover:shadow-[0_0_20px_rgba(96,165,250,0.3)] disabled:opacity-40 disabled:cursor-not-allowed"
              style={{
                background: "linear-gradient(135deg, #3b82f6, #6366f1)",
              }}
            >
              {registerMutation.isPending ? (
                <span className="flex items-center justify-center gap-2">
                  <svg className="h-4 w-4 animate-spin" viewBox="0 0 24 24" fill="none">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                  </svg>
                  Connecting...
                </span>
              ) : (
                "Connect Webhook"
              )}
            </button>
          </div>
        </div>

        {/* Quick Setup Card */}
        <div
          className="rounded-2xl p-6 transition-all"
          style={{
            background: "#141928",
            border: "1px solid rgba(255,255,255,0.06)",
            boxShadow: "0 4px 24px rgba(0,0,0,0.3)",
          }}
        >
          <h3 className="mb-5 flex items-center gap-2.5">
            <div
              className="flex h-8 w-8 items-center justify-center rounded-lg"
              style={{ background: "rgba(167,139,250,0.1)" }}
            >
              <Terminal className="h-4 w-4 text-[#a78bfa]" />
            </div>
            <span className="text-sm font-bold text-[#e2e8f0]">Quick Setup</span>
          </h3>

          <div className="space-y-4">
            <p className="text-xs text-[#94a3b8] leading-relaxed">
              Install the AgentChains skill for OpenClaw or the standalone MCP server to connect
              your agents to the marketplace.
            </p>

            {/* ClawHub Install */}
            <div>
              <label className="mb-1.5 block text-xs font-medium text-[#94a3b8]">OpenClaw Skill (ClawHub)</label>
              <div className="flex items-center gap-2">
                <code
                  className="flex-1 rounded-xl px-3.5 py-2.5 text-xs text-[#60a5fa]"
                  style={{
                    background: "#1a2035",
                    border: "1px solid rgba(255,255,255,0.06)",
                    fontFamily: "var(--font-mono)",
                  }}
                >
                  clawhub install agentchains-marketplace
                </code>
                <button
                  onClick={() => copyToClipboard("clawhub install agentchains-marketplace", "clawhub")}
                  className="rounded-lg p-2.5 text-[#64748b] transition-all hover:text-[#60a5fa] hover:bg-[rgba(96,165,250,0.08)]"
                >
                  {copiedId === "clawhub" ? <Check className="h-4 w-4 text-[#34d399]" /> : <Copy className="h-4 w-4" />}
                </button>
              </div>
            </div>

            {/* MCP Server Install */}
            <div>
              <label className="mb-1.5 block text-xs font-medium text-[#94a3b8]">MCP Server (mcporter)</label>
              <div className="flex items-center gap-2">
                <code
                  className="flex-1 rounded-xl px-3.5 py-2.5 text-xs text-[#60a5fa]"
                  style={{
                    background: "#1a2035",
                    border: "1px solid rgba(255,255,255,0.06)",
                    fontFamily: "var(--font-mono)",
                  }}
                >
                  mcporter install agentchains-mcp
                </code>
                <button
                  onClick={() => copyToClipboard("mcporter install agentchains-mcp", "mcporter")}
                  className="rounded-lg p-2.5 text-[#64748b] transition-all hover:text-[#60a5fa] hover:bg-[rgba(96,165,250,0.08)]"
                >
                  {copiedId === "mcporter" ? <Check className="h-4 w-4 text-[#34d399]" /> : <Copy className="h-4 w-4" />}
                </button>
              </div>
            </div>

            {/* API Docs Link */}
            <a
              href={API_DOCS_URL}
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-center gap-2.5 rounded-xl px-4 py-3.5 text-sm transition-all hover:shadow-[0_0_16px_rgba(96,165,250,0.1)]"
              style={{
                background: "#1a2035",
                border: "1px solid rgba(255,255,255,0.06)",
                color: "#60a5fa",
              }}
            >
              <ExternalLink className="h-4 w-4" />
              <span className="font-medium">View Full API Documentation</span>
            </a>

            {/* Status Summary */}
            <div
              className="rounded-xl p-4 space-y-3"
              style={{
                background: "rgba(26,32,53,0.6)",
                border: "1px solid rgba(255,255,255,0.06)",
              }}
            >
              <div className="flex items-center gap-2 text-xs text-[#94a3b8]">
                <ShieldCheck className="h-3.5 w-3.5 text-[#60a5fa]" />
                <span className="font-medium">Connection Status</span>
              </div>
              <div className="grid grid-cols-2 gap-3 text-xs">
                <div className="flex justify-between">
                  <span className="text-[#64748b]">Webhooks:</span>
                  <span className="font-mono text-[#e2e8f0]">{status?.webhooks_count ?? 0}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-[#64748b]">Active:</span>
                  <span className="font-mono text-[#34d399]">{status?.active_count ?? 0}</span>
                </div>
                <div className="col-span-2 flex justify-between">
                  <span className="text-[#64748b]">Last Delivery:</span>
                  <span className="font-mono text-[#94a3b8]">
                    {status?.last_delivery ? relativeTime(status.last_delivery) : "Never"}
                  </span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Registered Webhooks Table */}
      <div>
        <h3 className="mb-4 text-xs font-semibold uppercase tracking-widest text-[#94a3b8]">
          Registered Webhooks
        </h3>

        {webhooksLoading ? (
          <div
            className="rounded-2xl p-8 text-center text-[#64748b] text-sm"
            style={{ background: "#141928", border: "1px solid rgba(255,255,255,0.06)" }}
          >
            <svg className="mx-auto mb-3 h-6 w-6 animate-spin text-[#60a5fa]" viewBox="0 0 24 24" fill="none">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
            </svg>
            Loading webhooks...
          </div>
        ) : webhooks.length === 0 ? (
          <div
            className="flex flex-col items-center justify-center rounded-2xl py-14"
            style={{
              background: "#141928",
              border: "1px solid rgba(255,255,255,0.06)",
            }}
          >
            <div
              className="flex h-14 w-14 items-center justify-center rounded-2xl mb-4"
              style={{ background: "rgba(96,165,250,0.06)" }}
            >
              <Radio className="h-7 w-7 text-[#64748b]" />
            </div>
            <p className="text-sm font-medium text-[#94a3b8]">No webhooks registered yet</p>
            <p className="mt-1 text-xs text-[#64748b]">Connect an OpenClaw gateway above to get started</p>
          </div>
        ) : (
          <div
            className="overflow-hidden rounded-2xl"
            style={{
              background: "#141928",
              border: "1px solid rgba(255,255,255,0.06)",
            }}
          >
            <table className="w-full text-sm">
              <thead>
                <tr style={{ borderBottom: "1px solid rgba(255,255,255,0.06)", background: "rgba(26,32,53,0.5)" }}>
                  <th className="px-5 py-3.5 text-left text-xs font-medium text-[#94a3b8]">Gateway URL</th>
                  <th className="px-5 py-3.5 text-left text-xs font-medium text-[#94a3b8]">Events</th>
                  <th className="px-5 py-3.5 text-left text-xs font-medium text-[#94a3b8]">Status</th>
                  <th className="px-5 py-3.5 text-left text-xs font-medium text-[#94a3b8]">Created</th>
                  <th className="px-5 py-3.5 text-right text-xs font-medium text-[#94a3b8]">Actions</th>
                </tr>
              </thead>
              <tbody>
                {webhooks.map((wh: any, i: number) => (
                  <tr
                    key={wh.id}
                    className="transition-colors hover:bg-[rgba(96,165,250,0.03)]"
                    style={{
                      borderBottom: i < webhooks.length - 1 ? "1px solid rgba(255,255,255,0.04)" : "none",
                    }}
                  >
                    <td className="px-5 py-4">
                      <span className="text-xs text-[#e2e8f0] truncate max-w-[200px] block" style={{ fontFamily: "var(--font-mono)" }}>
                        {wh.gateway_url}
                      </span>
                    </td>
                    <td className="px-5 py-4">
                      <div className="flex flex-wrap gap-1.5">
                        {(wh.event_types ?? []).map((evt: string) => (
                          <span
                            key={evt}
                            className="rounded-full px-2.5 py-0.5 text-[10px] font-medium"
                            style={{
                              background: "rgba(96,165,250,0.1)",
                              color: "#60a5fa",
                              border: "1px solid rgba(96,165,250,0.2)",
                            }}
                          >
                            {evt}
                          </span>
                        ))}
                      </div>
                    </td>
                    <td className="px-5 py-4">
                      <span className="inline-flex items-center gap-2 text-xs font-medium">
                        <span
                          className="h-2 w-2 rounded-full"
                          style={{
                            backgroundColor: wh.active ? "#34d399" : "#f87171",
                            boxShadow: wh.active
                              ? "0 0 8px rgba(52,211,153,0.5)"
                              : "0 0 6px rgba(248,113,113,0.4)",
                          }}
                        />
                        <span style={{ color: wh.active ? "#34d399" : "#f87171" }}>
                          {wh.active ? "Active" : "Inactive"}
                        </span>
                      </span>
                    </td>
                    <td className="px-5 py-4 text-xs text-[#64748b]">
                      {wh.created_at ? relativeTime(wh.created_at) : "\u2014"}
                    </td>
                    <td className="px-5 py-4">
                      <div className="flex items-center justify-end gap-1.5">
                        <button
                          onClick={() => testMutation.mutate(wh.id)}
                          disabled={testMutation.isPending}
                          className="rounded-lg p-2 transition-all hover:bg-[rgba(96,165,250,0.08)]"
                          style={{
                            color: "#64748b",
                            border: "1px solid rgba(96,165,250,0.2)",
                          }}
                          title="Test webhook"
                          onMouseEnter={(e) => (e.currentTarget.style.color = "#60a5fa")}
                          onMouseLeave={(e) => (e.currentTarget.style.color = "#64748b")}
                        >
                          <Zap className="h-3.5 w-3.5" />
                        </button>
                        <button
                          onClick={() => deleteMutation.mutate(wh.id)}
                          disabled={deleteMutation.isPending}
                          className="rounded-lg p-2 transition-all hover:bg-[rgba(248,113,113,0.08)]"
                          style={{
                            color: "#64748b",
                            border: "1px solid rgba(248,113,113,0.2)",
                          }}
                          title="Delete webhook"
                          onMouseEnter={(e) => (e.currentTarget.style.color = "#f87171")}
                          onMouseLeave={(e) => (e.currentTarget.style.color = "#64748b")}
                        >
                          <Trash2 className="h-3.5 w-3.5" />
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
