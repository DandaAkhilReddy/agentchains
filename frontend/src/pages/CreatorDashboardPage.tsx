import { useEffect, useState } from "react";
import { Wallet, Bot, TrendingUp, ArrowRight, RefreshCw, Link2, LogOut, User } from "lucide-react";
import { fetchCreatorDashboard, claimAgent } from "../lib/api";
import PageHeader from "../components/PageHeader";
import Badge from "../components/Badge";
import AnimatedCounter from "../components/AnimatedCounter";
import { formatUSD } from "../lib/format";
import type { CreatorDashboard } from "../types/api";

interface Props {
  token: string;
  creatorName: string;
  onNavigate: (tab: string) => void;
  onLogout: () => void;
}

export default function CreatorDashboardPage({ token, creatorName, onNavigate, onLogout }: Props) {
  const [dashboard, setDashboard] = useState<CreatorDashboard | null>(null);
  const [loading, setLoading] = useState(true);
  const [claimId, setClaimId] = useState("");
  const [claimMsg, setClaimMsg] = useState("");

  const load = async () => {
    setLoading(true);
    try {
      const data = await fetchCreatorDashboard(token);
      setDashboard(data);
    } catch (e) {
      console.error("Dashboard load failed:", e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, [token]);

  const handleClaim = async () => {
    if (!claimId.trim()) return;
    try {
      await claimAgent(token, claimId.trim());
      setClaimMsg("Agent linked successfully!");
      setClaimId("");
      load();
    } catch (e: any) {
      setClaimMsg(e.message || "Failed to claim agent");
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <RefreshCw className="h-6 w-6 animate-spin text-primary" />
      </div>
    );
  }

  const d = dashboard;

  return (
    <div className="space-y-6">
      <PageHeader
        title="Creator Studio"
        subtitle={`Welcome back, ${creatorName}`}
        icon={User}
        actions={
          <div className="flex gap-2">
            <button
              onClick={() => onNavigate("redeem")}
              className="btn-primary flex items-center gap-1.5 px-4 py-2 text-sm"
            >
              Withdraw <ArrowRight className="h-4 w-4" />
            </button>
            <button
              onClick={onLogout}
              className="btn-ghost flex items-center gap-1.5 px-3 py-2 text-sm"
            >
              <LogOut className="h-4 w-4" />
            </button>
          </div>
        }
      />

      {/* Stats Grid */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <div className="glass-card gradient-border-card glow-hover p-5">
          <div className="flex items-center gap-3">
            <div className="rounded-xl bg-primary-glow p-2.5">
              <Wallet className="h-5 w-5 text-primary" />
            </div>
            <div>
              <p className="text-xs text-text-muted">USD Balance</p>
              <p className="text-xl font-bold text-text-primary" style={{ fontFamily: "var(--font-mono)" }}>
                {formatUSD(d?.creator_balance || 0)}
              </p>
            </div>
          </div>
        </div>
        <div className="glass-card gradient-border-card glow-hover p-5">
          <div className="flex items-center gap-3">
            <div className="rounded-xl bg-success-glow p-2.5">
              <TrendingUp className="h-5 w-5 text-success" />
            </div>
            <div>
              <p className="text-xs text-text-muted">Total Earned</p>
              <p className="text-xl font-bold text-text-primary" style={{ fontFamily: "var(--font-mono)" }}>
                {formatUSD(d?.creator_total_earned || 0)}
              </p>
            </div>
          </div>
        </div>
        <div className="glass-card gradient-border-card glow-hover p-5">
          <div className="flex items-center gap-3">
            <div className="rounded-xl bg-secondary-glow p-2.5">
              <Bot className="h-5 w-5 text-secondary" />
            </div>
            <div>
              <p className="text-xs text-text-muted">Active Agents</p>
              <p className="text-xl font-bold text-text-primary" style={{ fontFamily: "var(--font-mono)" }}>
                <AnimatedCounter value={d?.agents_count || 0} />
              </p>
            </div>
          </div>
        </div>
        <div className="glass-card gradient-border-card glow-hover p-5">
          <div className="flex items-center gap-3">
            <div className="rounded-xl bg-warning-glow p-2.5">
              <TrendingUp className="h-5 w-5 text-warning" />
            </div>
            <div>
              <p className="text-xs text-text-muted">Agent Earnings</p>
              <p className="text-xl font-bold text-text-primary" style={{ fontFamily: "var(--font-mono)" }}>
                {formatUSD(d?.total_agent_earnings || 0)}
              </p>
            </div>
          </div>
        </div>
      </div>

      {/* Agent List */}
      <div className="glass-card gradient-border-card p-5">
        <h2 className="mb-4 text-xs font-semibold uppercase tracking-widest text-text-secondary">Your Agents</h2>
        {d?.agents && d.agents.length > 0 ? (
          <div className="space-y-3">
            {d.agents.map((agent) => (
              <div
                key={agent.agent_id}
                className="flex items-center justify-between rounded-xl border border-border-subtle bg-surface-raised/50 p-4 transition-colors hover:border-primary/30"
              >
                <div className="flex items-center gap-3">
                  <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-primary-glow text-xs font-bold text-primary">
                    {agent.agent_name.slice(0, 2).toUpperCase()}
                  </div>
                  <div>
                    <p className="font-medium text-text-primary">{agent.agent_name}</p>
                    <div className="flex items-center gap-2 mt-0.5">
                      <Badge label={agent.agent_type} variant="blue" />
                      <Badge
                        label={agent.status}
                        variant={agent.status === "active" ? "green" : "gray"}
                      />
                    </div>
                  </div>
                </div>
                <div className="text-right">
                  <p className="font-semibold text-primary" style={{ fontFamily: "var(--font-mono)" }}>
                    {formatUSD(agent.total_earned)}
                  </p>
                  <p className="text-xs text-text-muted">
                    Balance: {formatUSD(agent.balance)}
                  </p>
                </div>
              </div>
            ))}
          </div>
        ) : (
          <div className="flex flex-col items-center justify-center py-8 text-text-muted">
            <Bot className="mb-3 h-8 w-8 opacity-40" />
            <p className="text-sm">No agents linked yet. Claim your first agent below.</p>
          </div>
        )}
      </div>

      {/* Claim Agent */}
      <div className="glass-card gradient-border-card p-5">
        <h2 className="mb-1 text-xs font-semibold uppercase tracking-widest text-text-secondary">Link an Agent</h2>
        <p className="mb-4 text-sm text-text-muted">
          Enter your agent's ID to claim ownership. All future earnings will flow to your account.
        </p>
        <div className="flex gap-2">
          <input
            type="text"
            value={claimId}
            onChange={(e) => setClaimId(e.target.value)}
            placeholder="Agent ID (UUID)"
            className="futuristic-input flex-1 px-3 py-2 text-sm"
            style={{ fontFamily: "var(--font-mono)" }}
          />
          <button
            onClick={handleClaim}
            className="btn-primary flex items-center gap-1.5 px-4 py-2 text-sm"
          >
            <Link2 className="h-4 w-4" /> Claim
          </button>
        </div>
        {claimMsg && (
          <p className={`mt-2 text-sm ${claimMsg.includes("success") ? "text-success" : "text-danger"}`}>
            {claimMsg}
          </p>
        )}
      </div>
    </div>
  );
}
