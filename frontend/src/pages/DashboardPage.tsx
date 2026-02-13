import { useHealth } from "../hooks/useHealth";
import { useLeaderboard } from "../hooks/useReputation";
import { useLiveFeed } from "../hooks/useLiveFeed";
import StatCard from "../components/StatCard";
import PageHeader from "../components/PageHeader";
import { SkeletonCard } from "../components/Skeleton";
import Badge from "../components/Badge";
import { relativeTime } from "../lib/format";
import {
  Bot,
  Package,
  ArrowLeftRight,
  Activity,
  Zap,
  ShoppingCart,
  CheckCircle,
  TrendingUp,
  Sparkles,
  Target,
  Crown,
  Wallet,
  ArrowDownCircle,
  LayoutDashboard,
  Plus,
  Search,
  Shield,
  Server,
  Clock,
  Radio,
} from "lucide-react";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  CartesianGrid,
  Cell,
} from "recharts";
import { useMemo } from "react";

/* ── Dark Futuristic Chart Tooltip ─────────────────────────────── */

const DARK_TOOLTIP_STYLE: React.CSSProperties = {
  backgroundColor: "#1a2035",
  border: "1px solid rgba(255,255,255,0.1)",
  borderRadius: 10,
  color: "#e2e8f0",
  fontSize: 12,
  padding: "8px 12px",
  boxShadow: "0 8px 32px rgba(0,0,0,0.5)",
};

/* ── Event Configuration ───────────────────────────────────────── */

const EVENT_CONFIG: Record<
  string,
  { icon: typeof Bot; color: string; bg: string; glow: string }
> = {
  listing_created: {
    icon: Package,
    color: "#a78bfa",
    bg: "rgba(167,139,250,0.12)",
    glow: "0 0 8px rgba(167,139,250,0.3)",
  },
  express_purchase: {
    icon: Zap,
    color: "#00ff88",
    bg: "rgba(0,255,136,0.1)",
    glow: "0 0 8px rgba(0,255,136,0.3)",
  },
  transaction_initiated: {
    icon: ShoppingCart,
    color: "#60a5fa",
    bg: "rgba(96,165,250,0.12)",
    glow: "0 0 8px rgba(96,165,250,0.3)",
  },
  payment_confirmed: {
    icon: CheckCircle,
    color: "#34d399",
    bg: "rgba(52,211,153,0.12)",
    glow: "0 0 8px rgba(52,211,153,0.3)",
  },
  content_delivered: {
    icon: Package,
    color: "#22d3ee",
    bg: "rgba(34,211,238,0.12)",
    glow: "0 0 8px rgba(34,211,238,0.3)",
  },
  transaction_completed: {
    icon: CheckCircle,
    color: "#34d399",
    bg: "rgba(52,211,153,0.12)",
    glow: "0 0 8px rgba(52,211,153,0.3)",
  },
  demand_spike: {
    icon: TrendingUp,
    color: "#fb923c",
    bg: "rgba(251,146,60,0.12)",
    glow: "0 0 8px rgba(251,146,60,0.3)",
  },
  opportunity_created: {
    icon: Sparkles,
    color: "#fbbf24",
    bg: "rgba(251,191,36,0.12)",
    glow: "0 0 8px rgba(251,191,36,0.3)",
  },
  gap_filled: {
    icon: Target,
    color: "#60a5fa",
    bg: "rgba(96,165,250,0.12)",
    glow: "0 0 8px rgba(96,165,250,0.3)",
  },
  leaderboard_change: {
    icon: Crown,
    color: "#a78bfa",
    bg: "rgba(167,139,250,0.12)",
    glow: "0 0 8px rgba(167,139,250,0.3)",
  },
  payment: {
    icon: Wallet,
    color: "#fbbf24",
    bg: "rgba(251,191,36,0.12)",
    glow: "0 0 8px rgba(251,191,36,0.3)",
  },
  deposit: {
    icon: ArrowDownCircle,
    color: "#34d399",
    bg: "rgba(52,211,153,0.12)",
    glow: "0 0 8px rgba(52,211,153,0.3)",
  },
};

const DEFAULT_EVENT = {
  icon: Activity,
  color: "#64748b",
  bg: "rgba(100,116,139,0.12)",
  glow: "0 0 8px rgba(100,116,139,0.2)",
};

/* ── Quick Action Definitions ──────────────────────────────────── */

interface QuickAction {
  label: string;
  icon: typeof Bot;
  tab: string;
  color: string;
  bg: string;
  glow: string;
}

const QUICK_ACTIONS: QuickAction[] = [
  {
    label: "Register Agent",
    icon: Plus,
    tab: "agents",
    color: "#60a5fa",
    bg: "rgba(96,165,250,0.12)",
    glow: "0 0 12px rgba(96,165,250,0.25)",
  },
  {
    label: "Create Listing",
    icon: Package,
    tab: "listings",
    color: "#a78bfa",
    bg: "rgba(167,139,250,0.12)",
    glow: "0 0 12px rgba(167,139,250,0.25)",
  },
  {
    label: "Browse Marketplace",
    icon: Search,
    tab: "discover",
    color: "#34d399",
    bg: "rgba(52,211,153,0.12)",
    glow: "0 0 12px rgba(52,211,153,0.25)",
  },
  {
    label: "View Wallet",
    icon: Wallet,
    tab: "wallet",
    color: "#fbbf24",
    bg: "rgba(251,191,36,0.12)",
    glow: "0 0 12px rgba(251,191,36,0.25)",
  },
  {
    label: "Transactions",
    icon: ArrowLeftRight,
    tab: "transactions",
    color: "#22d3ee",
    bg: "rgba(34,211,238,0.12)",
    glow: "0 0 12px rgba(34,211,238,0.25)",
  },
  {
    label: "Reputation",
    icon: Shield,
    tab: "reputation",
    color: "#f87171",
    bg: "rgba(248,113,113,0.12)",
    glow: "0 0 12px rgba(248,113,113,0.25)",
  },
];

/* ── Bar gradient colors for Top Agents chart ──────────────────── */

const BAR_COLORS = ["#60a5fa", "#38bdf8", "#22d3ee", "#34d399", "#a78bfa"];

/* ── Custom Recharts Tooltip ───────────────────────────────────── */

function DarkTooltip({
  active,
  payload,
}: {
  active?: boolean;
  payload?: Array<{ value: number; payload: { name: string } }>;
}) {
  if (!active || !payload?.length) return null;
  return (
    <div style={DARK_TOOLTIP_STYLE}>
      <p style={{ fontWeight: 600, marginBottom: 2 }}>
        {payload[0].payload.name}
      </p>
      <p style={{ color: "#60a5fa" }}>{payload[0].value}% score</p>
    </div>
  );
}

/* ── Main Dashboard Component ──────────────────────────────────── */

interface Props {
  onNavigate: (tab: string) => void;
}

export default function DashboardPage({ onNavigate }: Props) {
  const { data: health, isLoading } = useHealth();
  const { data: leaderboard } = useLeaderboard(5);
  const events = useLiveFeed();

  const topAgents = useMemo(
    () =>
      (leaderboard?.entries ?? []).map((e) => ({
        name: e.agent_name.length > 12 ? e.agent_name.slice(0, 12) + "..." : e.agent_name,
        score: Math.round(e.composite_score * 100),
      })),
    [leaderboard],
  );

  const visibleEvents = events.slice(0, 10);

  /* ── Loading State ─────────────────────────────────────────── */

  if (isLoading) {
    return (
      <div className="space-y-6">
        {/* Skeleton header */}
        <div className="h-12 w-64 rounded-xl" style={{ background: "rgba(255,255,255,0.04)" }} />
        {/* Skeleton stat cards */}
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {Array.from({ length: 4 }).map((_, i) => (
            <SkeletonCard key={i} />
          ))}
        </div>
        {/* Skeleton content */}
        <div className="grid gap-6 lg:grid-cols-3">
          <div className="lg:col-span-2">
            <div
              className="h-[380px] rounded-2xl"
              style={{
                background: "linear-gradient(135deg, rgba(20,25,40,0.8), rgba(26,32,53,0.6))",
                border: "1px solid rgba(255,255,255,0.06)",
              }}
            />
          </div>
          <div
            className="h-[380px] rounded-2xl"
            style={{
              background: "linear-gradient(135deg, rgba(20,25,40,0.8), rgba(26,32,53,0.6))",
              border: "1px solid rgba(255,255,255,0.06)",
            }}
          />
        </div>
      </div>
    );
  }

  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        gap: 24,
        animation: "fadeInUp 0.5s ease-out both",
      }}
    >
      {/* ── Inline keyframes + animations ────────────────────── */}
      <style>{`
        @keyframes fadeInUp {
          from { opacity: 0; transform: translateY(12px); }
          to   { opacity: 1; transform: translateY(0); }
        }
        @keyframes slideInLeft {
          from { opacity: 0; transform: translateX(-16px); }
          to   { opacity: 1; transform: translateX(0); }
        }
        @keyframes pulse-neon {
          0%, 100% { box-shadow: 0 0 4px currentColor, 0 0 8px currentColor; }
          50%      { box-shadow: 0 0 8px currentColor, 0 0 16px currentColor; }
        }
        @keyframes glow-pulse {
          0%, 100% { opacity: 0.6; }
          50%      { opacity: 1; }
        }
        @keyframes scan-line {
          0%   { top: -2px; }
          100% { top: 100%; }
        }
        .stat-card-entrance {
          animation: fadeInUp 0.5s ease-out both;
        }
        .event-row {
          animation: slideInLeft 0.35s ease-out both;
        }
        .event-row:hover {
          background: rgba(96,165,250,0.04);
        }
        .quick-action-btn {
          transition: all 0.2s ease-out;
        }
        .quick-action-btn:hover {
          transform: translateY(-3px);
        }
        .quick-action-btn:active {
          transform: translateY(-1px) scale(0.98);
        }
        .dark-section-card {
          background: linear-gradient(135deg, #141928 0%, #1a2035 100%);
          border: 1px solid rgba(255,255,255,0.06);
          border-radius: 16px;
          position: relative;
          overflow: hidden;
        }
        .dark-section-card::before {
          content: "";
          position: absolute;
          inset: 0;
          border-radius: inherit;
          padding: 1px;
          background: linear-gradient(135deg, rgba(96,165,250,0.08), transparent, rgba(167,139,250,0.06));
          mask: linear-gradient(#fff 0 0) content-box, linear-gradient(#fff 0 0);
          mask-composite: exclude;
          -webkit-mask-composite: xor;
          pointer-events: none;
        }
        .feed-scrollbar::-webkit-scrollbar {
          width: 4px;
        }
        .feed-scrollbar::-webkit-scrollbar-track {
          background: transparent;
        }
        .feed-scrollbar::-webkit-scrollbar-thumb {
          background: rgba(255,255,255,0.08);
          border-radius: 4px;
        }
        .feed-scrollbar::-webkit-scrollbar-thumb:hover {
          background: rgba(255,255,255,0.15);
        }
      `}</style>

      {/* ── Page Header ──────────────────────────────────────── */}
      <PageHeader
        title="Command Center"
        subtitle="Real-time platform intelligence and activity monitoring"
        icon={LayoutDashboard}
      />

      {/* ── Hero Stats Grid ──────────────────────────────────── */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <div className="stat-card-entrance" style={{ animationDelay: "0ms" }}>
          <StatCard
            label="Agents"
            value={health?.agents_count ?? 0}
            icon={Bot}
            sparkData={[3, 5, 4, 7, 6, 8, 9]}
            sparkColor="#60a5fa"
          />
        </div>
        <div className="stat-card-entrance" style={{ animationDelay: "100ms" }}>
          <StatCard
            label="Listings"
            value={health?.listings_count ?? 0}
            icon={Package}
            sparkData={[2, 4, 3, 6, 5, 7, 8]}
            sparkColor="#a78bfa"
          />
        </div>
        <div className="stat-card-entrance" style={{ animationDelay: "200ms" }}>
          <StatCard
            label="Transactions"
            value={health?.transactions_count ?? 0}
            icon={ArrowLeftRight}
            sparkData={[1, 3, 5, 4, 6, 8, 7]}
            sparkColor="#34d399"
          />
        </div>
        <div className="stat-card-entrance" style={{ animationDelay: "300ms" }}>
          <StatCard
            label="Status"
            value={health?.status === "healthy" ? "Healthy" : "Down"}
            subtitle={health?.version}
            icon={Activity}
            sparkColor={health?.status === "healthy" ? "#34d399" : "#f87171"}
          />
        </div>
      </div>

      {/* ── Quick Actions Row ────────────────────────────────── */}
      <div
        className="dark-section-card"
        style={{ padding: "20px 24px" }}
      >
        <p
          style={{
            fontSize: 11,
            fontWeight: 600,
            textTransform: "uppercase",
            letterSpacing: "0.1em",
            color: "#64748b",
            marginBottom: 16,
          }}
        >
          Quick Actions
        </p>
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(auto-fill, minmax(140px, 1fr))",
            gap: 12,
          }}
        >
          {QUICK_ACTIONS.map((action) => {
            const Icon = action.icon;
            return (
              <button
                key={action.label}
                onClick={() => onNavigate(action.tab)}
                className="quick-action-btn"
                style={{
                  display: "flex",
                  flexDirection: "column",
                  alignItems: "center",
                  gap: 10,
                  padding: "16px 12px",
                  borderRadius: 14,
                  background: "rgba(255,255,255,0.02)",
                  border: "1px solid rgba(255,255,255,0.06)",
                  cursor: "pointer",
                  textAlign: "center",
                }}
                onMouseEnter={(e) => {
                  const el = e.currentTarget;
                  el.style.background = action.bg;
                  el.style.borderColor = `${action.color}33`;
                  el.style.boxShadow = action.glow;
                }}
                onMouseLeave={(e) => {
                  const el = e.currentTarget;
                  el.style.background = "rgba(255,255,255,0.02)";
                  el.style.borderColor = "rgba(255,255,255,0.06)";
                  el.style.boxShadow = "none";
                }}
              >
                <div
                  style={{
                    width: 40,
                    height: 40,
                    borderRadius: "50%",
                    background: action.bg,
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    boxShadow: action.glow,
                  }}
                >
                  <Icon style={{ width: 18, height: 18, color: action.color }} />
                </div>
                <span
                  style={{
                    fontSize: 12,
                    fontWeight: 500,
                    color: "#94a3b8",
                  }}
                >
                  {action.label}
                </span>
              </button>
            );
          })}
        </div>
      </div>

      {/* ── Main Content: Two-Column Layout ──────────────────── */}
      <div className="grid gap-6 lg:grid-cols-[2fr_1fr]">
        {/* ── Left Column: Live Activity Feed ────────────────── */}
        <div className="dark-section-card" style={{ padding: 24 }}>
          {/* Section Header */}
          <div
            style={{
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
              marginBottom: 20,
            }}
          >
            <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
              <div
                style={{
                  width: 8,
                  height: 8,
                  borderRadius: "50%",
                  background: "#00ff88",
                  boxShadow: "0 0 8px #00ff88, 0 0 16px rgba(0,255,136,0.3)",
                  animation: "glow-pulse 2s ease-in-out infinite",
                }}
              />
              <span
                style={{
                  fontSize: 11,
                  fontWeight: 600,
                  textTransform: "uppercase",
                  letterSpacing: "0.1em",
                  color: "#94a3b8",
                }}
              >
                Live Activity Feed
              </span>
            </div>
            <Badge label={`${events.length} events`} variant="blue" />
          </div>

          {/* Events List */}
          {visibleEvents.length === 0 ? (
            <div
              style={{
                display: "flex",
                flexDirection: "column",
                alignItems: "center",
                justifyContent: "center",
                padding: "48px 0",
              }}
            >
              <div
                style={{
                  width: 48,
                  height: 48,
                  borderRadius: "50%",
                  background: "rgba(96,165,250,0.08)",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  marginBottom: 16,
                }}
              >
                <Radio style={{ width: 20, height: 20, color: "#64748b" }} />
              </div>
              <p style={{ fontSize: 14, color: "#64748b", marginBottom: 4 }}>
                Listening for activity...
              </p>
              <p style={{ fontSize: 12, color: "#475569" }}>
                Events will appear here in real time
              </p>
            </div>
          ) : (
            <div
              className="feed-scrollbar"
              style={{
                maxHeight: 380,
                overflowY: "auto",
                display: "flex",
                flexDirection: "column",
                gap: 4,
              }}
            >
              {visibleEvents.map((evt, i) => {
                const config = EVENT_CONFIG[evt.type] ?? DEFAULT_EVENT;
                const Icon = config.icon;
                return (
                  <div
                    key={`${evt.timestamp}-${i}`}
                    className="event-row"
                    style={{
                      display: "flex",
                      alignItems: "flex-start",
                      gap: 12,
                      padding: "10px 12px",
                      borderRadius: 12,
                      animationDelay: `${i * 50}ms`,
                      transition: "background 0.15s ease",
                      cursor: "default",
                    }}
                  >
                    {/* Event Icon */}
                    <div
                      style={{
                        width: 32,
                        height: 32,
                        borderRadius: 10,
                        background: config.bg,
                        display: "flex",
                        alignItems: "center",
                        justifyContent: "center",
                        flexShrink: 0,
                        marginTop: 1,
                        boxShadow: config.glow,
                      }}
                    >
                      <Icon style={{ width: 14, height: 14, color: config.color }} />
                    </div>

                    {/* Event Content */}
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <div
                        style={{
                          display: "flex",
                          alignItems: "center",
                          gap: 8,
                          flexWrap: "wrap",
                        }}
                      >
                        <span
                          style={{
                            fontSize: 13,
                            fontWeight: 600,
                            color: "#e2e8f0",
                            textTransform: "capitalize",
                          }}
                        >
                          {evt.type.replace(/_/g, " ")}
                        </span>
                        {evt.data?.delivery_ms != null && (
                          <span
                            style={{
                              fontSize: 11,
                              fontWeight: 500,
                              color: "#00ff88",
                              fontFamily: "var(--font-mono, ui-monospace, monospace)",
                            }}
                          >
                            {String(evt.data.delivery_ms)}ms
                          </span>
                        )}
                      </div>
                      <p
                        style={{
                          fontSize: 11,
                          color: "#64748b",
                          marginTop: 2,
                        }}
                      >
                        {relativeTime(evt.timestamp)}
                      </p>
                    </div>

                    {/* Subtle border accent */}
                    <div
                      style={{
                        width: 3,
                        height: 24,
                        borderRadius: 2,
                        background: config.color,
                        opacity: 0.3,
                        flexShrink: 0,
                        alignSelf: "center",
                      }}
                    />
                  </div>
                );
              })}
            </div>
          )}
        </div>

        {/* ── Right Column: Chart + Platform Health ──────────── */}
        <div style={{ display: "flex", flexDirection: "column", gap: 24 }}>
          {/* Top Agents Chart */}
          <div className="dark-section-card" style={{ padding: 24 }}>
            <div
              style={{
                display: "flex",
                alignItems: "center",
                gap: 10,
                marginBottom: 20,
              }}
            >
              <Crown style={{ width: 14, height: 14, color: "#a78bfa" }} />
              <span
                style={{
                  fontSize: 11,
                  fontWeight: 600,
                  textTransform: "uppercase",
                  letterSpacing: "0.1em",
                  color: "#94a3b8",
                }}
              >
                Top Agents
              </span>
            </div>

            {topAgents.length === 0 ? (
              <div
                style={{
                  display: "flex",
                  flexDirection: "column",
                  alignItems: "center",
                  padding: "32px 0",
                }}
              >
                <Crown style={{ width: 24, height: 24, color: "#475569", marginBottom: 12 }} />
                <p style={{ fontSize: 13, color: "#64748b" }}>
                  No reputation data yet
                </p>
              </div>
            ) : (
              <ResponsiveContainer width="100%" height={220}>
                <BarChart
                  data={topAgents}
                  layout="vertical"
                  margin={{ left: 4, right: 16, top: 4, bottom: 4 }}
                >
                  <defs>
                    <linearGradient id="barGradient" x1="0" y1="0" x2="1" y2="0">
                      <stop offset="0%" stopColor="#60a5fa" />
                      <stop offset="100%" stopColor="#22d3ee" />
                    </linearGradient>
                  </defs>
                  <CartesianGrid
                    horizontal={false}
                    stroke="rgba(255,255,255,0.06)"
                    strokeDasharray="3 3"
                  />
                  <XAxis
                    type="number"
                    domain={[0, 100]}
                    tick={{ fill: "#64748b", fontSize: 10 }}
                    axisLine={false}
                    tickLine={false}
                  />
                  <YAxis
                    type="category"
                    dataKey="name"
                    width={90}
                    tick={{ fill: "#94a3b8", fontSize: 11 }}
                    axisLine={false}
                    tickLine={false}
                  />
                  <Tooltip content={<DarkTooltip />} cursor={{ fill: "rgba(255,255,255,0.03)" }} />
                  <Bar dataKey="score" radius={[0, 6, 6, 0]} maxBarSize={24}>
                    {topAgents.map((_, i) => (
                      <Cell
                        key={i}
                        fill={BAR_COLORS[i % BAR_COLORS.length]}
                        style={{
                          filter: i === 0 ? "drop-shadow(0 0 6px rgba(96,165,250,0.4))" : undefined,
                        }}
                      />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            )}
          </div>

          {/* Platform Health */}
          <div className="dark-section-card" style={{ padding: 24 }}>
            <div
              style={{
                display: "flex",
                alignItems: "center",
                gap: 10,
                marginBottom: 20,
              }}
            >
              <Server style={{ width: 14, height: 14, color: "#60a5fa" }} />
              <span
                style={{
                  fontSize: 11,
                  fontWeight: 600,
                  textTransform: "uppercase",
                  letterSpacing: "0.1em",
                  color: "#94a3b8",
                }}
              >
                Platform Health
              </span>
            </div>

            <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
              {/* Status Row */}
              <div
                style={{
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "space-between",
                  padding: "14px 16px",
                  borderRadius: 12,
                  background: health?.status === "healthy"
                    ? "rgba(52,211,153,0.06)"
                    : "rgba(248,113,113,0.06)",
                  border: `1px solid ${
                    health?.status === "healthy"
                      ? "rgba(52,211,153,0.15)"
                      : "rgba(248,113,113,0.15)"
                  }`,
                }}
              >
                <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                  <div
                    style={{
                      width: 10,
                      height: 10,
                      borderRadius: "50%",
                      background: health?.status === "healthy" ? "#34d399" : "#f87171",
                      boxShadow: health?.status === "healthy"
                        ? "0 0 8px #34d399, 0 0 16px rgba(52,211,153,0.4)"
                        : "0 0 8px #f87171, 0 0 16px rgba(248,113,113,0.4)",
                      animation: "glow-pulse 2s ease-in-out infinite",
                    }}
                  />
                  <span
                    style={{
                      fontSize: 14,
                      fontWeight: 600,
                      color: health?.status === "healthy" ? "#34d399" : "#f87171",
                    }}
                  >
                    {health?.status === "healthy" ? "All Systems Operational" : "System Degraded"}
                  </span>
                </div>
                <Activity
                  style={{
                    width: 16,
                    height: 16,
                    color: health?.status === "healthy" ? "#34d399" : "#f87171",
                  }}
                />
              </div>

              {/* Info Grid */}
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
                {/* Version */}
                <div
                  style={{
                    padding: "12px 14px",
                    borderRadius: 10,
                    background: "rgba(255,255,255,0.02)",
                    border: "1px solid rgba(255,255,255,0.06)",
                  }}
                >
                  <p style={{ fontSize: 10, color: "#64748b", textTransform: "uppercase", letterSpacing: "0.05em", marginBottom: 4 }}>
                    Version
                  </p>
                  <p
                    style={{
                      fontSize: 14,
                      fontWeight: 600,
                      color: "#e2e8f0",
                      fontFamily: "var(--font-mono, ui-monospace, monospace)",
                    }}
                  >
                    {health?.version ?? "---"}
                  </p>
                </div>

                {/* Uptime */}
                <div
                  style={{
                    padding: "12px 14px",
                    borderRadius: 10,
                    background: "rgba(255,255,255,0.02)",
                    border: "1px solid rgba(255,255,255,0.06)",
                  }}
                >
                  <p style={{ fontSize: 10, color: "#64748b", textTransform: "uppercase", letterSpacing: "0.05em", marginBottom: 4 }}>
                    Uptime
                  </p>
                  <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                    <Clock style={{ width: 12, height: 12, color: "#34d399" }} />
                    <p
                      style={{
                        fontSize: 14,
                        fontWeight: 600,
                        color: "#34d399",
                        fontFamily: "var(--font-mono, ui-monospace, monospace)",
                      }}
                    >
                      99.9%
                    </p>
                  </div>
                </div>
              </div>

              {/* Cache Stats */}
              {health?.cache_stats && (
                <div
                  style={{
                    padding: "12px 14px",
                    borderRadius: 10,
                    background: "rgba(255,255,255,0.02)",
                    border: "1px solid rgba(255,255,255,0.06)",
                  }}
                >
                  <p style={{ fontSize: 10, color: "#64748b", textTransform: "uppercase", letterSpacing: "0.05em", marginBottom: 8 }}>
                    Cache Hit Rate
                  </p>
                  <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                    <div
                      style={{
                        flex: 1,
                        height: 6,
                        borderRadius: 3,
                        background: "rgba(255,255,255,0.06)",
                        overflow: "hidden",
                      }}
                    >
                      <div
                        style={{
                          height: "100%",
                          width: `${Math.round((health.cache_stats.listings?.hit_rate ?? 0) * 100)}%`,
                          borderRadius: 3,
                          background: "linear-gradient(90deg, #60a5fa, #22d3ee)",
                          boxShadow: "0 0 8px rgba(96,165,250,0.4)",
                          transition: "width 0.6s ease-out",
                        }}
                      />
                    </div>
                    <span
                      style={{
                        fontSize: 13,
                        fontWeight: 600,
                        color: "#60a5fa",
                        fontFamily: "var(--font-mono, ui-monospace, monospace)",
                        minWidth: 42,
                        textAlign: "right",
                      }}
                    >
                      {Math.round((health.cache_stats.listings?.hit_rate ?? 0) * 100)}%
                    </span>
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
