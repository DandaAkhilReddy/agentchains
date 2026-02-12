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
      <div className="space-y-6 animate-fade-in">
        <div className="flex items-center gap-3">
          <div className="rounded-lg bg-primary-glow p-2">
            <Plug className="h-5 w-5 text-primary" />
          </div>
          <div>
            <h2 className="text-xl font-bold gradient-text">Integrations</h2>
            <p className="text-sm text-text-secondary">Connect external agents and tools</p>
          </div>
        </div>

        <div className="flex flex-col items-center py-16">
          <div className="glass-card gradient-border-card p-8 w-full max-w-md space-y-4">
            <div className="text-center">
              <h3 className="text-lg font-bold gradient-text">Connect Your Agent</h3>
              <p className="mt-1 text-sm text-text-secondary">
                Paste your agent JWT to manage integrations
              </p>
            </div>
            <input
              type="text"
              value={inputToken}
              onChange={(e) => setInputToken(e.target.value)}
              placeholder="eyJhbGciOi..."
              className="futuristic-input w-full px-4 py-3 text-sm"
              style={{ fontFamily: "var(--font-mono)" }}
            />
            <button onClick={handleConnect} disabled={!inputToken.trim()} className="btn-primary w-full px-4 py-2.5 text-sm">
              Connect
            </button>
          </div>
        </div>
      </div>
    );
  }

  const webhooks = webhooksData?.webhooks ?? [];
  const isConnected = status?.connected ?? false;

  return (
    <div className="space-y-6 animate-fade-in">
      {/* Header */}
      <div className="flex items-center justify-between">
        <PageHeader title="Integrations" subtitle="Connect OpenClaw agents and webhooks" icon={Plug} />
        <div className="flex items-center gap-2">
          <span
            className={`inline-flex h-2.5 w-2.5 rounded-full ${
              isConnected ? "bg-success shadow-[0_0_8px_rgba(0,255,136,0.5)]" : "bg-danger shadow-[0_0_8px_rgba(255,68,68,0.5)]"
            }`}
          />
          <span className="text-xs font-medium text-text-secondary">
            {isConnected ? "Connected" : "Disconnected"}
          </span>
          {status && (
            <span className="text-xs text-text-muted ml-2">
              {status.active_count}/{status.webhooks_count} active
            </span>
          )}
        </div>
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        {/* OpenClaw Connection Card */}
        <div className="glass-card gradient-border-card glow-hover p-5">
          <h3 className="mb-4 flex items-center gap-2 text-sm font-semibold text-text-primary">
            <Webhook className="h-4 w-4 text-primary" />
            OpenClaw Connection
          </h3>
          <div className="space-y-4">
            {/* Gateway URL */}
            <div>
              <label className="mb-1 block text-xs font-medium text-text-muted">Gateway URL</label>
              <input
                type="text"
                value={gatewayUrl}
                onChange={(e) => setGatewayUrl(e.target.value)}
                placeholder="https://your-openclaw-gateway.example.com/webhook"
                className="futuristic-input w-full px-3 py-2 text-sm"
              />
            </div>

            {/* Bearer Token */}
            <div>
              <label className="mb-1 block text-xs font-medium text-text-muted">Bearer Token</label>
              <input
                type="password"
                value={bearerToken}
                onChange={(e) => setBearerToken(e.target.value)}
                placeholder="your-webhook-secret-token"
                className="futuristic-input w-full px-3 py-2 text-sm"
              />
            </div>

            {/* Event Types */}
            <div>
              <label className="mb-2 block text-xs font-medium text-text-muted">Event Types</label>
              <div className="grid grid-cols-2 gap-2">
                {EVENT_TYPES.map((evt) => (
                  <button
                    key={evt.id}
                    onClick={() => toggleEvent(evt.id)}
                    className={`flex flex-col items-start rounded-lg border p-2.5 text-left transition-all ${
                      selectedEvents.includes(evt.id)
                        ? "border-primary bg-primary/10 shadow-[0_0_8px_rgba(0,212,255,0.15)]"
                        : "border-border-subtle bg-surface-overlay/30 hover:border-border-glow"
                    }`}
                  >
                    <span className={`text-xs font-semibold ${selectedEvents.includes(evt.id) ? "text-primary" : "text-text-primary"}`}>
                      {evt.label}
                    </span>
                    <span className="mt-0.5 text-[10px] text-text-muted leading-tight">
                      {evt.description}
                    </span>
                  </button>
                ))}
              </div>
            </div>

            {/* Connect Button */}
            <button
              onClick={() => registerMutation.mutate()}
              disabled={!gatewayUrl.trim() || selectedEvents.length === 0 || registerMutation.isPending}
              className="btn-primary w-full px-4 py-2.5 text-sm"
            >
              {registerMutation.isPending ? "Connecting..." : "Connect Webhook"}
            </button>
          </div>
        </div>

        {/* Quick Setup Card */}
        <div className="glass-card gradient-border-card glow-hover p-5">
          <h3 className="mb-4 flex items-center gap-2 text-sm font-semibold text-text-primary">
            <Terminal className="h-4 w-4 text-secondary" />
            Quick Setup
          </h3>
          <div className="space-y-4">
            <p className="text-xs text-text-secondary leading-relaxed">
              Install the AgentChains skill for OpenClaw or the standalone MCP server to connect
              your agents to the marketplace.
            </p>

            {/* ClawHub Install */}
            <div>
              <label className="mb-1 block text-xs font-medium text-text-muted">OpenClaw Skill (ClawHub)</label>
              <div className="flex items-center gap-2">
                <code className="flex-1 rounded-lg border border-border-subtle bg-surface-overlay/50 px-3 py-2 text-xs text-primary" style={{ fontFamily: "var(--font-mono)" }}>
                  clawhub install agentchains-marketplace
                </code>
                <button
                  onClick={() => copyToClipboard("clawhub install agentchains-marketplace", "clawhub")}
                  className="btn-ghost rounded-lg p-2 text-text-muted hover:text-primary"
                >
                  {copiedId === "clawhub" ? <Check className="h-4 w-4 text-success" /> : <Copy className="h-4 w-4" />}
                </button>
              </div>
            </div>

            {/* MCP Server Install */}
            <div>
              <label className="mb-1 block text-xs font-medium text-text-muted">MCP Server (mcporter)</label>
              <div className="flex items-center gap-2">
                <code className="flex-1 rounded-lg border border-border-subtle bg-surface-overlay/50 px-3 py-2 text-xs text-primary" style={{ fontFamily: "var(--font-mono)" }}>
                  mcporter install agentchains-mcp
                </code>
                <button
                  onClick={() => copyToClipboard("mcporter install agentchains-mcp", "mcporter")}
                  className="btn-ghost rounded-lg p-2 text-text-muted hover:text-primary"
                >
                  {copiedId === "mcporter" ? <Check className="h-4 w-4 text-success" /> : <Copy className="h-4 w-4" />}
                </button>
              </div>
            </div>

            {/* API Docs Link */}
            <a
              href={API_DOCS_URL}
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-center gap-2 rounded-lg border border-border-subtle bg-surface-overlay/30 px-4 py-3 text-sm text-text-secondary transition-all hover:border-primary hover:text-primary"
            >
              <ExternalLink className="h-4 w-4" />
              <span>View Full API Documentation</span>
            </a>

            {/* Status Summary */}
            <div className="rounded-lg border border-border-subtle bg-surface-overlay/20 p-3 space-y-2">
              <div className="flex items-center gap-2 text-xs text-text-muted">
                <ShieldCheck className="h-3.5 w-3.5 text-primary" />
                <span>Connection Status</span>
              </div>
              <div className="grid grid-cols-2 gap-2 text-xs">
                <div className="flex justify-between">
                  <span className="text-text-muted">Webhooks:</span>
                  <span className="font-mono text-text-primary">{status?.webhooks_count ?? 0}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-text-muted">Active:</span>
                  <span className="font-mono text-success">{status?.active_count ?? 0}</span>
                </div>
                <div className="col-span-2 flex justify-between">
                  <span className="text-text-muted">Last Delivery:</span>
                  <span className="font-mono text-text-secondary">
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
        <h3 className="mb-3 text-xs font-semibold uppercase tracking-widest text-text-secondary">
          Registered Webhooks
        </h3>

        {webhooksLoading ? (
          <div className="glass-card p-8 text-center text-text-muted text-sm">Loading webhooks...</div>
        ) : webhooks.length === 0 ? (
          <div className="glass-card flex flex-col items-center justify-center py-12 text-text-muted">
            <Radio className="mb-3 h-10 w-10 opacity-40" />
            <p className="text-sm">No webhooks registered yet</p>
            <p className="mt-1 text-xs text-text-muted">Connect an OpenClaw gateway above to get started</p>
          </div>
        ) : (
          <div className="glass-card overflow-hidden">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border-subtle bg-surface-overlay/30">
                  <th className="px-4 py-3 text-left text-text-secondary font-medium">Gateway URL</th>
                  <th className="px-4 py-3 text-left text-text-secondary font-medium">Events</th>
                  <th className="px-4 py-3 text-left text-text-secondary font-medium">Status</th>
                  <th className="px-4 py-3 text-left text-text-secondary font-medium">Created</th>
                  <th className="px-4 py-3 text-right text-text-secondary font-medium">Actions</th>
                </tr>
              </thead>
              <tbody>
                {webhooks.map((wh: any) => (
                  <tr
                    key={wh.id}
                    className="border-b border-border-subtle/50 transition-colors hover:bg-[rgba(0,212,255,0.06)]"
                  >
                    <td className="px-4 py-3">
                      <span className="text-xs font-mono text-text-primary truncate max-w-[200px] block">
                        {wh.gateway_url}
                      </span>
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex flex-wrap gap-1">
                        {(wh.event_types ?? []).map((evt: string) => (
                          <span
                            key={evt}
                            className="rounded-full bg-primary/10 px-2 py-0.5 text-[10px] font-medium text-primary"
                          >
                            {evt}
                          </span>
                        ))}
                      </div>
                    </td>
                    <td className="px-4 py-3">
                      <span className={`inline-flex items-center gap-1.5 text-xs font-medium ${wh.active ? "text-success" : "text-danger"}`}>
                        <span className={`h-1.5 w-1.5 rounded-full ${wh.active ? "bg-success" : "bg-danger"}`} />
                        {wh.active ? "Active" : "Inactive"}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-xs text-text-muted">
                      {wh.created_at ? relativeTime(wh.created_at) : "—"}
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex items-center justify-end gap-1">
                        <button
                          onClick={() => testMutation.mutate(wh.id)}
                          disabled={testMutation.isPending}
                          className="btn-ghost rounded-lg p-1.5 text-text-muted hover:text-primary"
                          title="Test webhook"
                        >
                          <Zap className="h-3.5 w-3.5" />
                        </button>
                        <button
                          onClick={() => deleteMutation.mutate(wh.id)}
                          disabled={deleteMutation.isPending}
                          className="btn-ghost rounded-lg p-1.5 text-text-muted hover:text-danger"
                          title="Delete webhook"
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
