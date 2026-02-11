import { useEffect, useState } from "react";
import { Wallet, Bot, TrendingUp, ArrowRight, RefreshCw, Link2, LogOut } from "lucide-react";
import { fetchCreatorDashboard, fetchCreatorWallet, claimAgent } from "../lib/api";

interface Props {
  token: string;
  creatorName: string;
  onNavigate: (tab: string) => void;
  onLogout: () => void;
}

interface Dashboard {
  creator_balance: number;
  creator_total_earned: number;
  creator_balance_usd: number;
  agents_count: number;
  agents: Array<{
    agent_id: string;
    agent_name: string;
    agent_type: string;
    status: string;
    total_earned: number;
    total_spent: number;
    balance: number;
  }>;
  total_agent_earnings: number;
  total_agent_spent: number;
  peg_rate_usd: number;
  token_name: string;
}

function StatCard({ icon: Icon, label, value, sub }: { icon: any; label: string; value: string; sub?: string }) {
  return (
    <div className="rounded-xl border border-[var(--border-default)] bg-[var(--bg-card)] p-5">
      <div className="flex items-center gap-3">
        <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-[var(--accent)]/10">
          <Icon className="h-5 w-5 text-[var(--accent)]" />
        </div>
        <div>
          <p className="text-xs text-[var(--text-muted)]">{label}</p>
          <p className="text-xl font-bold text-[var(--text-primary)]">{value}</p>
          {sub && <p className="text-xs text-[var(--text-secondary)]">{sub}</p>}
        </div>
      </div>
    </div>
  );
}

export default function CreatorDashboardPage({ token, creatorName, onNavigate, onLogout }: Props) {
  const [dashboard, setDashboard] = useState<Dashboard | null>(null);
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

  const fmtARD = (n: number) => {
    if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(2)}M`;
    if (n >= 1_000) return `${(n / 1_000).toFixed(1)}K`;
    return n.toFixed(0);
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <RefreshCw className="h-6 w-6 animate-spin text-[var(--accent)]" />
      </div>
    );
  }

  const d = dashboard;
  const tokenName = d?.token_name || "ARD";

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-[var(--text-primary)]">
            Welcome, {creatorName}
          </h1>
          <p className="text-sm text-[var(--text-muted)]">Creator Dashboard — manage your agents and earnings</p>
        </div>
        <div className="flex gap-2">
          <button
            onClick={() => onNavigate("redeem")}
            className="flex items-center gap-1.5 rounded-lg bg-[var(--accent)] px-4 py-2 text-sm font-semibold text-black hover:bg-[var(--accent-hover)] transition-colors"
          >
            Redeem <ArrowRight className="h-4 w-4" />
          </button>
          <button
            onClick={onLogout}
            className="flex items-center gap-1.5 rounded-lg border border-[var(--border-default)] px-3 py-2 text-sm text-[var(--text-secondary)] hover:text-[var(--text-primary)] transition-colors"
          >
            <LogOut className="h-4 w-4" />
          </button>
        </div>
      </div>

      {/* Stats Grid */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard
          icon={Wallet}
          label={`${tokenName} Balance`}
          value={`${fmtARD(d?.creator_balance || 0)} ${tokenName}`}
          sub={`$${(d?.creator_balance_usd || 0).toFixed(2)} USD`}
        />
        <StatCard
          icon={TrendingUp}
          label="Total Earned"
          value={`${fmtARD(d?.creator_total_earned || 0)} ${tokenName}`}
        />
        <StatCard
          icon={Bot}
          label="Active Agents"
          value={String(d?.agents_count || 0)}
        />
        <StatCard
          icon={TrendingUp}
          label="Agent Earnings"
          value={`${fmtARD(d?.total_agent_earnings || 0)} ${tokenName}`}
          sub={`$${((d?.total_agent_earnings || 0) * (d?.peg_rate_usd || 0.001)).toFixed(2)} USD`}
        />
      </div>

      {/* Agent List */}
      <div className="rounded-xl border border-[var(--border-default)] bg-[var(--bg-card)] p-5">
        <h2 className="mb-4 text-lg font-semibold text-[var(--text-primary)]">Your Agents</h2>
        {d?.agents && d.agents.length > 0 ? (
          <div className="space-y-3">
            {d.agents.map((agent) => (
              <div key={agent.agent_id} className="flex items-center justify-between rounded-lg border border-[var(--border-default)] p-4">
                <div>
                  <p className="font-medium text-[var(--text-primary)]">{agent.agent_name}</p>
                  <p className="text-xs text-[var(--text-muted)]">
                    {agent.agent_type} — {agent.status}
                  </p>
                </div>
                <div className="text-right">
                  <p className="font-semibold text-[var(--accent)]">
                    {fmtARD(agent.total_earned)} {tokenName} earned
                  </p>
                  <p className="text-xs text-[var(--text-muted)]">
                    Balance: {fmtARD(agent.balance)} {tokenName}
                  </p>
                </div>
              </div>
            ))}
          </div>
        ) : (
          <p className="text-sm text-[var(--text-muted)]">No agents linked yet. Claim your first agent below.</p>
        )}
      </div>

      {/* Claim Agent */}
      <div className="rounded-xl border border-[var(--border-default)] bg-[var(--bg-card)] p-5">
        <h2 className="mb-3 text-lg font-semibold text-[var(--text-primary)]">Link an Agent</h2>
        <p className="mb-3 text-sm text-[var(--text-muted)]">
          Enter your agent's ID to claim ownership. All future earnings will flow to your account.
        </p>
        <div className="flex gap-2">
          <input
            type="text"
            value={claimId}
            onChange={(e) => setClaimId(e.target.value)}
            placeholder="Agent ID (UUID)"
            className="flex-1 rounded-lg border border-[var(--border-default)] bg-[var(--bg-card)] px-3 py-2 text-sm text-[var(--text-primary)] outline-none focus:border-[var(--accent)] transition-colors"
          />
          <button
            onClick={handleClaim}
            className="flex items-center gap-1.5 rounded-lg bg-[var(--accent)] px-4 py-2 text-sm font-semibold text-black hover:bg-[var(--accent-hover)]"
          >
            <Link2 className="h-4 w-4" /> Claim
          </button>
        </div>
        {claimMsg && (
          <p className={`mt-2 text-sm ${claimMsg.includes("success") ? "text-[var(--accent)]" : "text-red-400"}`}>
            {claimMsg}
          </p>
        )}
      </div>
    </div>
  );
}
