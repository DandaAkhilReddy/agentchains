import { useState, useEffect } from "react";
import { Flame, Thermometer, HardDrive, ArrowDown, ArrowUp, Zap, Database, Activity } from "lucide-react";
import { useCDNStats } from "../../hooks/useSystemMetrics";
import StatCard from "../StatCard";

/* ── keyframe styles injected once ── */
const styleId = "cdn-tiers-viz-styles";
function ensureStyles() {
  if (typeof document === "undefined") return;
  if (document.getElementById(styleId)) return;
  const style = document.createElement("style");
  style.id = styleId;
  style.textContent = `
    @keyframes cdn-flame-flicker {
      0%, 100% { opacity: 0.85; transform: scaleY(1) translateY(0); }
      25% { opacity: 1; transform: scaleY(1.08) translateY(-1px); }
      50% { opacity: 0.9; transform: scaleY(0.95) translateY(1px); }
      75% { opacity: 1; transform: scaleY(1.04) translateY(-0.5px); }
    }
    @keyframes cdn-warm-pulse {
      0%, 100% { opacity: 0.6; }
      50% { opacity: 1; }
    }
    @keyframes cdn-cold-spin {
      0% { transform: rotate(0deg); }
      100% { transform: rotate(360deg); }
    }
    @keyframes cdn-dash-flow {
      from { stroke-dashoffset: 20; }
      to { stroke-dashoffset: 0; }
    }
    @keyframes cdn-dash-flow-up {
      from { stroke-dashoffset: 0; }
      to { stroke-dashoffset: 20; }
    }
    @keyframes cdn-dot-down {
      0% { offset-distance: 0%; opacity: 0; }
      10% { opacity: 1; }
      90% { opacity: 1; }
      100% { offset-distance: 100%; opacity: 0; }
    }
    @keyframes cdn-dot-up {
      0% { offset-distance: 100%; opacity: 0; }
      10% { opacity: 1; }
      90% { opacity: 1; }
      100% { offset-distance: 0%; opacity: 0; }
    }
    @keyframes cdn-card-enter {
      from { opacity: 0; transform: translateY(16px); }
      to { opacity: 1; transform: translateY(0); }
    }
    @keyframes cdn-glow-pulse {
      0%, 100% { box-shadow: var(--cdn-glow-base); }
      50% { box-shadow: var(--cdn-glow-peak); }
    }
    @keyframes cdn-bar-fill {
      from { width: 0%; }
    }
    @keyframes cdn-heat-wave {
      0%, 100% { background-position: 0% 50%; }
      50% { background-position: 100% 50%; }
    }
  `;
  document.head.appendChild(style);
}

/* ── tier config ── */
const TIER_CONFIG = [
  {
    key: "hot",
    label: "Hot Cache",
    subtitle: "Tier 1",
    desc: "In-Memory LFU",
    latency: "< 1ms",
    capacity: "256MB",
    icon: Flame,
    accent: "#f87171",
    accentRgb: "248,113,113",
    glowBase: "0 0 0 1px rgba(248,113,113,0.2), 0 0 20px rgba(248,113,113,0.08)",
    glowPeak: "0 0 0 1px rgba(248,113,113,0.4), 0 0 30px rgba(248,113,113,0.15), 0 0 60px rgba(248,113,113,0.05)",
    animClass: "cdn-flame-flicker",
  },
  {
    key: "warm",
    label: "Warm Cache",
    subtitle: "Tier 2",
    desc: "TTL Cache",
    latency: "~5ms",
    capacity: "1GB",
    icon: Thermometer,
    accent: "#fbbf24",
    accentRgb: "251,191,36",
    glowBase: "0 0 0 1px rgba(251,191,36,0.2), 0 0 20px rgba(251,191,36,0.08)",
    glowPeak: "0 0 0 1px rgba(251,191,36,0.4), 0 0 30px rgba(251,191,36,0.15), 0 0 60px rgba(251,191,36,0.05)",
    animClass: "cdn-warm-pulse",
  },
  {
    key: "cold",
    label: "Cold Store",
    subtitle: "Tier 3",
    desc: "HashFS Content-Addressed",
    latency: "10-50ms",
    capacity: "Unlimited",
    icon: HardDrive,
    accent: "#60a5fa",
    accentRgb: "96,165,250",
    glowBase: "0 0 0 1px rgba(96,165,250,0.2), 0 0 20px rgba(96,165,250,0.08)",
    glowPeak: "0 0 0 1px rgba(96,165,250,0.4), 0 0 30px rgba(96,165,250,0.15), 0 0 60px rgba(96,165,250,0.05)",
    animClass: "cdn-cold-spin",
  },
];

/* ── flow arrow SVG between tiers ── */
function FlowArrow({
  direction,
  color,
  label,
  delay = 0,
}: {
  direction: "down" | "up";
  color: string;
  label: string;
  delay?: number;
}) {
  const isDown = direction === "down";
  return (
    <div className="flex flex-col items-center gap-0.5" style={{ minWidth: 90 }}>
      <span
        style={{
          fontSize: 9,
          fontWeight: 600,
          letterSpacing: "0.04em",
          color: "#64748b",
          textTransform: "uppercase",
          display: "flex",
          alignItems: "center",
          gap: 3,
        }}
      >
        {isDown ? (
          <ArrowDown style={{ width: 10, height: 10, color: "#64748b" }} />
        ) : (
          <ArrowUp style={{ width: 10, height: 10, color: "#34d399" }} />
        )}
        {label}
      </span>
      <svg width="40" height="32" viewBox="0 0 40 32" fill="none">
        {/* path */}
        <line
          x1="20"
          y1={isDown ? 2 : 30}
          x2="20"
          y2={isDown ? 30 : 2}
          stroke={color}
          strokeWidth="1.5"
          strokeDasharray="4 4"
          style={{
            animation: `${isDown ? "cdn-dash-flow" : "cdn-dash-flow-up"} 1s linear infinite`,
            animationDelay: `${delay}ms`,
          }}
          strokeLinecap="round"
        />
        {/* arrowhead */}
        <polygon
          points={isDown ? "15,26 20,32 25,26" : "15,6 20,0 25,6"}
          fill={color}
          opacity={0.8}
        />
        {/* animated dot */}
        <circle r="2.5" fill={color} opacity={0.9}>
          <animateMotion
            dur="1.5s"
            repeatCount="indefinite"
            begin={`${delay / 1000}s`}
            path={isDown ? "M20,2 L20,30" : "M20,30 L20,2"}
          />
        </circle>
      </svg>
    </div>
  );
}

/* ── capacity bar ── */
function CapacityBar({ percent, color }: { percent: number; color: string }) {
  return (
    <div
      style={{
        height: 4,
        borderRadius: 2,
        background: "rgba(255,255,255,0.06)",
        overflow: "hidden",
        width: "100%",
        marginTop: 6,
      }}
    >
      <div
        style={{
          height: "100%",
          borderRadius: 2,
          background: `linear-gradient(90deg, ${color}, ${color}88)`,
          width: `${Math.min(percent, 100)}%`,
          animation: "cdn-bar-fill 1s ease-out forwards",
        }}
      />
    </div>
  );
}

/* ── main component ── */
export default function CDNTiersViz() {
  ensureStyles();

  const { data: stats } = useCDNStats();
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    const t = setTimeout(() => setVisible(true), 50);
    return () => clearTimeout(t);
  }, []);

  const hitRates: Record<string, number> = {
    hot: stats?.hot_cache?.hit_rate ?? 0,
    warm: stats?.warm_cache?.hit_rate ?? 0,
    cold: 1,
  };

  const utilization: Record<string, number> = {
    hot: (stats?.hot_cache?.utilization_pct ?? 0) * 100,
    warm: 65,
    cold: 30,
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 28 }}>
      {/* ── Tier Cards (horizontal on md+, vertical on mobile) ── */}
      <div
        style={{
          display: "flex",
          flexDirection: "row",
          alignItems: "flex-start",
          gap: 0,
          flexWrap: "wrap",
          justifyContent: "center",
        }}
      >
        {TIER_CONFIG.map((tier, i) => {
          const Icon = tier.icon;
          const hitRate = hitRates[tier.key];
          const util = utilization[tier.key];

          return (
            <div
              key={tier.key}
              style={{
                display: "flex",
                alignItems: "center",
                flexDirection: "row",
              }}
            >
              {/* Tier Card */}
              <div
                style={{
                  ["--cdn-glow-base" as string]: tier.glowBase,
                  ["--cdn-glow-peak" as string]: tier.glowPeak,
                  background: "#141928",
                  borderRadius: 16,
                  padding: "20px 22px",
                  minWidth: 220,
                  maxWidth: 260,
                  position: "relative",
                  overflow: "hidden",
                  border: `1px solid rgba(${tier.accentRgb}, 0.2)`,
                  animation: visible
                    ? `cdn-card-enter 0.5s ease-out ${i * 150}ms both, cdn-glow-pulse 3s ease-in-out ${i * 500}ms infinite`
                    : "none",
                  opacity: visible ? undefined : 0,
                }}
              >
                {/* Subtle heat gradient overlay for hot tier */}
                {tier.key === "hot" && (
                  <div
                    style={{
                      position: "absolute",
                      inset: 0,
                      borderRadius: 16,
                      background:
                        "linear-gradient(135deg, rgba(248,113,113,0.06) 0%, transparent 40%, rgba(251,146,60,0.04) 100%)",
                      backgroundSize: "200% 200%",
                      animation: "cdn-heat-wave 6s ease infinite",
                      pointerEvents: "none",
                    }}
                  />
                )}

                {/* Header */}
                <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 14 }}>
                  <div
                    style={{
                      width: 36,
                      height: 36,
                      borderRadius: 10,
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "center",
                      background: `rgba(${tier.accentRgb}, 0.12)`,
                      boxShadow: `0 0 16px rgba(${tier.accentRgb}, 0.15)`,
                    }}
                  >
                    <Icon
                      style={{
                        width: 18,
                        height: 18,
                        color: tier.accent,
                        animation:
                          tier.key === "hot"
                            ? "cdn-flame-flicker 1.5s ease-in-out infinite"
                            : tier.key === "warm"
                              ? "cdn-warm-pulse 2s ease-in-out infinite"
                              : undefined,
                      }}
                    />
                  </div>
                  <div>
                    <div style={{ fontSize: 14, fontWeight: 700, color: "#e2e8f0", lineHeight: 1.2 }}>
                      {tier.label}
                    </div>
                    <div style={{ fontSize: 10, fontWeight: 600, color: tier.accent, letterSpacing: "0.06em", textTransform: "uppercase" as const }}>
                      {tier.subtitle}
                    </div>
                  </div>
                </div>

                {/* Description */}
                <div style={{ fontSize: 11, color: "#94a3b8", marginBottom: 12 }}>{tier.desc}</div>

                {/* Latency + Capacity */}
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", marginBottom: 8 }}>
                  <div>
                    <div style={{ fontSize: 10, color: "#64748b", textTransform: "uppercase" as const, letterSpacing: "0.05em" }}>
                      Latency
                    </div>
                    <div
                      style={{
                        fontSize: 20,
                        fontWeight: 800,
                        fontFamily: "var(--font-mono, ui-monospace, monospace)",
                        color: tier.accent,
                        textShadow: `0 0 12px rgba(${tier.accentRgb}, 0.4)`,
                      }}
                    >
                      {tier.latency}
                    </div>
                  </div>
                  <div style={{ textAlign: "right" }}>
                    <div style={{ fontSize: 10, color: "#64748b", textTransform: "uppercase" as const, letterSpacing: "0.05em" }}>
                      Capacity
                    </div>
                    <div style={{ fontSize: 13, fontWeight: 600, fontFamily: "var(--font-mono, ui-monospace, monospace)", color: "#e2e8f0" }}>
                      {tier.capacity}
                    </div>
                  </div>
                </div>

                {/* Hit Rate */}
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 4 }}>
                  <span style={{ fontSize: 10, color: "#64748b" }}>Hit Rate</span>
                  <span
                    style={{
                      fontSize: 11,
                      fontWeight: 700,
                      fontFamily: "var(--font-mono, ui-monospace, monospace)",
                      color: tier.accent,
                    }}
                  >
                    {(hitRate * 100).toFixed(0)}%
                  </span>
                </div>
                <CapacityBar percent={hitRate * 100} color={tier.accent} />

                {/* Utilization */}
                <div
                  style={{
                    display: "flex",
                    justifyContent: "space-between",
                    alignItems: "center",
                    marginTop: 10,
                    marginBottom: 4,
                  }}
                >
                  <span style={{ fontSize: 10, color: "#64748b" }}>Utilization</span>
                  <span
                    style={{
                      fontSize: 11,
                      fontWeight: 700,
                      fontFamily: "var(--font-mono, ui-monospace, monospace)",
                      color: "#94a3b8",
                    }}
                  >
                    {util.toFixed(0)}%
                  </span>
                </div>
                <CapacityBar percent={util} color={`rgba(${tier.accentRgb}, 0.5)`} />
              </div>

              {/* Flow Arrows between tiers */}
              {i < TIER_CONFIG.length - 1 && (
                <div
                  style={{
                    display: "flex",
                    flexDirection: "column",
                    alignItems: "center",
                    gap: 2,
                    padding: "0 6px",
                  }}
                >
                  <FlowArrow
                    direction="up"
                    color="#34d399"
                    label="Promote on hit"
                    delay={i * 400}
                  />
                  <FlowArrow
                    direction="down"
                    color="#64748b"
                    label="Evict on capacity"
                    delay={i * 400 + 200}
                  />
                </div>
              )}
            </div>
          );
        })}
      </div>

      {/* Responsive: on small screens stack vertically */}
      <style>{`
        @media (max-width: 768px) {
          .cdn-tiers-viz-styles + div > div:first-child {
            flex-direction: column !important;
            align-items: center !important;
          }
        }
      `}</style>

      {/* ── Stats at bottom ── */}
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fit, minmax(160px, 1fr))",
          gap: 16,
        }}
      >
        <StatCard
          label="Hot Hit Rate"
          value={`${((stats?.hot_cache?.hit_rate ?? 0) * 100).toFixed(0)}%`}
          icon={Zap}
          sparkColor="#f87171"
          subtitle="In-memory LFU"
        />
        <StatCard
          label="Warm Hit Rate"
          value={`${((stats?.warm_cache?.hit_rate ?? 0) * 100).toFixed(0)}%`}
          icon={Database}
          sparkColor="#fbbf24"
          subtitle="TTL cache layer"
        />
        <StatCard
          label="Total Requests"
          value={(stats?.overview?.total_requests ?? 0).toLocaleString()}
          icon={Activity}
          sparkColor="#60a5fa"
          subtitle="All tiers combined"
        />
        <StatCard
          label="Hot Utilization"
          value={`${((stats?.hot_cache?.utilization_pct ?? 0) * 100).toFixed(0)}%`}
          icon={Flame}
          sparkColor="#f87171"
          subtitle="256MB capacity"
        />
      </div>
    </div>
  );
}
