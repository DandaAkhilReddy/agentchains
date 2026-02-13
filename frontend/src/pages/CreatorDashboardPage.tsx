import { useEffect, useState } from "react";
import {
  Wallet,
  Bot,
  TrendingUp,
  ArrowRight,
  RefreshCw,
  Link2,
  LogOut,
  User,
  DollarSign,
  Coins,
} from "lucide-react";
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
        <div className="flex flex-col items-center gap-3">
          <RefreshCw className="h-6 w-6 animate-spin text-[#60a5fa]" />
          <span className="text-sm text-[#64748b]">Loading dashboard...</span>
        </div>
      </div>
    );
  }

  const d = dashboard;

  // Stat card config
  const statCards = [
    {
      label: "USD Balance",
      value: formatUSD(d?.creator_balance || 0),
      icon: DollarSign,
      accentColor: "#34d399",
      glowColor: "rgba(52,211,153,0.15)",
      borderColor: "rgba(52,211,153,0.2)",
      isAnimated: false,
    },
    {
      label: "Total Earned",
      value: formatUSD(d?.creator_total_earned || 0),
      icon: TrendingUp,
      accentColor: "#60a5fa",
      glowColor: "rgba(96,165,250,0.15)",
      borderColor: "rgba(96,165,250,0.2)",
      isAnimated: false,
    },
    {
      label: "Active Agents",
      value: d?.agents_count || 0,
      icon: Bot,
      accentColor: "#a78bfa",
      glowColor: "rgba(167,139,250,0.15)",
      borderColor: "rgba(167,139,250,0.2)",
      isAnimated: true,
    },
    {
      label: "Agent Earnings",
      value: formatUSD(d?.total_agent_earnings || 0),
      icon: Coins,
      accentColor: "#fbbf24",
      glowColor: "rgba(251,191,36,0.15)",
      borderColor: "rgba(251,191,36,0.2)",
      isAnimated: false,
    },
  ];

  // Gradient color pairs for agent avatars
  const avatarGradients = [
    "linear-gradient(135deg, #3b82f6, #6366f1)",
    "linear-gradient(135deg, #a78bfa, #ec4899)",
    "linear-gradient(135deg, #34d399, #06b6d4)",
    "linear-gradient(135deg, #fbbf24, #f97316)",
    "linear-gradient(135deg, #f87171, #db2777)",
    "linear-gradient(135deg, #60a5fa, #34d399)",
  ];

  return (
    <div className="space-y-8 animate-fade-in">
      {/* Header */}
      <PageHeader
        title="Creator Studio"
        subtitle={`Welcome back, ${creatorName}`}
        icon={User}
        actions={
          <div className="flex gap-2">
            <button
              onClick={() => onNavigate("redeem")}
              className="flex items-center gap-1.5 rounded-xl px-4 py-2.5 text-sm font-semibold text-white transition-all hover:shadow-[0_0_20px_rgba(96,165,250,0.3)]"
              style={{ background: "linear-gradient(135deg, #3b82f6, #6366f1)" }}
            >
              Withdraw <ArrowRight className="h-4 w-4" />
            </button>
            <button
              onClick={onLogout}
              className="flex items-center gap-1.5 rounded-xl px-3 py-2.5 text-sm text-[#94a3b8] transition-all hover:text-[#f87171] hover:bg-[rgba(248,113,113,0.08)]"
              style={{ border: "1px solid rgba(255,255,255,0.06)" }}
            >
              <LogOut className="h-4 w-4" />
            </button>
          </div>
        }
      />

      {/* 4 Stat Cards */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {statCards.map((card) => {
          const Icon = card.icon;
          return (
            <div
              key={card.label}
              className="group relative rounded-2xl p-5 transition-all duration-300 hover:translate-y-[-2px]"
              style={{
                background: "#141928",
                border: `1px solid ${card.borderColor}`,
                boxShadow: `0 4px 24px rgba(0,0,0,0.3), 0 0 0 0 ${card.glowColor}`,
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.boxShadow = `0 8px 32px rgba(0,0,0,0.4), 0 0 24px ${card.glowColor}`;
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.boxShadow = `0 4px 24px rgba(0,0,0,0.3), 0 0 0 0 ${card.glowColor}`;
              }}
            >
              {/* Top accent line */}
              <div
                className="absolute top-0 left-4 right-4 h-px"
                style={{ background: `linear-gradient(90deg, transparent, ${card.accentColor}40, transparent)` }}
              />

              <div className="flex items-center gap-3.5">
                <div
                  className="flex h-11 w-11 items-center justify-center rounded-xl"
                  style={{
                    background: `${card.accentColor}15`,
                    boxShadow: `0 0 16px ${card.accentColor}20`,
                  }}
                >
                  <Icon className="h-5 w-5" style={{ color: card.accentColor }} />
                </div>
                <div>
                  <p className="text-xs text-[#64748b] font-medium">{card.label}</p>
                  {card.isAnimated ? (
                    <p
                      className="text-2xl font-bold"
                      style={{
                        fontFamily: "var(--font-mono)",
                        color: card.accentColor,
                        textShadow: `0 0 20px ${card.accentColor}30`,
                      }}
                    >
                      <AnimatedCounter value={card.value as number} />
                    </p>
                  ) : (
                    <p
                      className="text-2xl font-bold"
                      style={{
                        fontFamily: "var(--font-mono)",
                        color: card.accentColor,
                        textShadow: `0 0 20px ${card.accentColor}30`,
                      }}
                    >
                      {card.value}
                    </p>
                  )}
                </div>
              </div>
            </div>
          );
        })}
      </div>

      {/* Agent List */}
      <div>
        <h2 className="mb-4 text-xs font-semibold uppercase tracking-widest text-[#94a3b8]">
          Your Agents
        </h2>

        {d?.agents && d.agents.length > 0 ? (
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {d.agents.map((agent, idx) => (
              <div
                key={agent.agent_id}
                className="group rounded-2xl p-5 transition-all duration-300 hover:translate-y-[-2px]"
                style={{
                  background: "#141928",
                  border: "1px solid rgba(255,255,255,0.06)",
                  boxShadow: "0 4px 24px rgba(0,0,0,0.3)",
                }}
                onMouseEnter={(e) => {
                  e.currentTarget.style.boxShadow = "0 8px 32px rgba(0,0,0,0.4), 0 0 24px rgba(96,165,250,0.08)";
                  e.currentTarget.style.borderColor = "rgba(96,165,250,0.15)";
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.boxShadow = "0 4px 24px rgba(0,0,0,0.3)";
                  e.currentTarget.style.borderColor = "rgba(255,255,255,0.06)";
                }}
              >
                <div className="flex items-start gap-3.5">
                  {/* Avatar */}
                  <div
                    className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl text-xs font-bold text-white"
                    style={{
                      background: avatarGradients[idx % avatarGradients.length],
                      boxShadow: "0 4px 12px rgba(0,0,0,0.3)",
                    }}
                  >
                    {agent.agent_name.slice(0, 2).toUpperCase()}
                  </div>

                  <div className="min-w-0 flex-1">
                    <p className="font-semibold text-[#e2e8f0] truncate">{agent.agent_name}</p>
                    <div className="flex items-center gap-2 mt-1">
                      <Badge label={agent.agent_type} variant="blue" />
                      <Badge
                        label={agent.status}
                        variant={agent.status === "active" ? "green" : "gray"}
                      />
                    </div>
                  </div>
                </div>

                {/* Earnings */}
                <div
                  className="mt-4 rounded-xl p-3 flex items-center justify-between"
                  style={{
                    background: "#1a2035",
                    border: "1px solid rgba(255,255,255,0.04)",
                  }}
                >
                  <div>
                    <p className="text-[10px] uppercase tracking-wider text-[#64748b]">Earned</p>
                    <p
                      className="text-sm font-bold text-[#60a5fa]"
                      style={{ fontFamily: "var(--font-mono)" }}
                    >
                      {formatUSD(agent.total_earned)}
                    </p>
                  </div>
                  <div className="text-right">
                    <p className="text-[10px] uppercase tracking-wider text-[#64748b]">Balance</p>
                    <p
                      className="text-sm font-bold text-[#34d399]"
                      style={{ fontFamily: "var(--font-mono)" }}
                    >
                      {formatUSD(agent.balance)}
                    </p>
                  </div>
                </div>
              </div>
            ))}
          </div>
        ) : (
          <div
            className="flex flex-col items-center justify-center rounded-2xl py-14"
            style={{
              background: "#141928",
              border: "1px solid rgba(255,255,255,0.06)",
            }}
          >
            <div
              className="flex h-14 w-14 items-center justify-center rounded-2xl mb-4"
              style={{ background: "rgba(167,139,250,0.06)" }}
            >
              <Bot className="h-7 w-7 text-[#64748b]" />
            </div>
            <p className="text-sm font-medium text-[#94a3b8]">No agents linked yet</p>
            <p className="mt-1 text-xs text-[#64748b]">Claim your first agent below to get started</p>
          </div>
        )}
      </div>

      {/* Claim Agent */}
      <div
        className="rounded-2xl p-6"
        style={{
          background: "#141928",
          border: "1px solid rgba(255,255,255,0.06)",
          boxShadow: "0 4px 24px rgba(0,0,0,0.3)",
        }}
      >
        <div className="flex items-center gap-2.5 mb-1">
          <div
            className="flex h-8 w-8 items-center justify-center rounded-lg"
            style={{ background: "rgba(96,165,250,0.1)" }}
          >
            <Link2 className="h-4 w-4 text-[#60a5fa]" />
          </div>
          <h2
            className="text-sm font-bold"
            style={{
              background: "linear-gradient(135deg, #60a5fa, #a78bfa)",
              WebkitBackgroundClip: "text",
              WebkitTextFillColor: "transparent",
            }}
          >
            Claim an Agent
          </h2>
        </div>
        <p className="mb-5 text-sm text-[#64748b] ml-[42px]">
          Enter your agent's ID to claim ownership. All future earnings will flow to your account.
        </p>

        <div className="flex gap-3">
          <input
            type="text"
            value={claimId}
            onChange={(e) => setClaimId(e.target.value)}
            placeholder="Agent ID (UUID)"
            className="flex-1 rounded-xl px-4 py-2.5 text-sm text-[#e2e8f0] placeholder-[#64748b] outline-none transition-all focus:ring-2 focus:ring-[#60a5fa]/30"
            style={{
              background: "#1a2035",
              border: "1px solid rgba(255,255,255,0.06)",
              fontFamily: "var(--font-mono)",
            }}
          />
          <button
            onClick={handleClaim}
            disabled={!claimId.trim()}
            className="flex items-center gap-2 rounded-xl px-5 py-2.5 text-sm font-semibold text-white transition-all hover:shadow-[0_0_20px_rgba(96,165,250,0.3)] disabled:opacity-40 disabled:cursor-not-allowed"
            style={{ background: "linear-gradient(135deg, #3b82f6, #6366f1)" }}
          >
            <Link2 className="h-4 w-4" /> Claim
          </button>
        </div>

        {claimMsg && (
          <p
            className="mt-3 text-sm font-medium ml-[42px]"
            style={{ color: claimMsg.includes("success") ? "#34d399" : "#f87171" }}
          >
            {claimMsg}
          </p>
        )}
      </div>
    </div>
  );
}
