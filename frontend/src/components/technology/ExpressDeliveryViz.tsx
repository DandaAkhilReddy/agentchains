import { useState, useEffect, useRef } from "react";
import {
  Zap,
  Clock,
  CheckCircle2,
  Send,
  ShieldCheck,
  GitBranch,
  Database,
  Truck,
  BadgeCheck,
} from "lucide-react";

/* ── keyframe styles ── */
const styleId = "express-delivery-viz-styles";
function ensureStyles() {
  if (typeof document === "undefined") return;
  if (document.getElementById(styleId)) return;
  const style = document.createElement("style");
  style.id = styleId;
  style.textContent = `
    @keyframes edv-card-enter {
      from { opacity: 0; transform: translateY(20px) scale(0.96); }
      to { opacity: 1; transform: translateY(0) scale(1); }
    }
    @keyframes edv-stage-light {
      0% { border-color: rgba(255,255,255,0.06); box-shadow: none; }
      100% { border-color: var(--edv-stage-color); box-shadow: 0 0 20px var(--edv-stage-glow); }
    }
    @keyframes edv-check-pop {
      0% { opacity: 0; transform: scale(0); }
      60% { transform: scale(1.2); }
      100% { opacity: 1; transform: scale(1); }
    }
    @keyframes edv-flow-dash {
      from { stroke-dashoffset: 16; }
      to { stroke-dashoffset: 0; }
    }
    @keyframes edv-flow-dot {
      0% { opacity: 0; }
      20% { opacity: 1; }
      80% { opacity: 1; }
      100% { opacity: 0; }
    }
    @keyframes edv-needle-sweep {
      from { transform: rotate(-135deg); }
    }
    @keyframes edv-glow-number {
      0%, 100% { text-shadow: 0 0 12px rgba(0,255,136,0.4); }
      50% { text-shadow: 0 0 24px rgba(0,255,136,0.7), 0 0 40px rgba(0,255,136,0.3); }
    }
    @keyframes edv-pulse-ring {
      0% { stroke-opacity: 0.3; }
      50% { stroke-opacity: 0.6; }
      100% { stroke-opacity: 0.3; }
    }
    @keyframes edv-bar-grow {
      from { width: 0%; }
    }
    @keyframes edv-metric-enter {
      from { opacity: 0; transform: translateY(12px); }
      to { opacity: 1; transform: translateY(0); }
    }
  `;
  document.head.appendChild(style);
}

/* ── pipeline stages config ── */
const STAGES = [
  { label: "Request", icon: Send, latency: "<1ms", color: "#60a5fa", colorRgb: "96,165,250" },
  { label: "Auth", icon: ShieldCheck, latency: "~2ms", color: "#a78bfa", colorRgb: "167,139,250" },
  { label: "Route", icon: GitBranch, latency: "~1ms", color: "#34d399", colorRgb: "52,211,153" },
  { label: "Cache", icon: Database, latency: "<1ms", color: "#fbbf24", colorRgb: "251,191,36" },
  { label: "Deliver", icon: Truck, latency: "~3ms", color: "#00ff88", colorRgb: "0,255,136" },
  { label: "Verify", icon: BadgeCheck, latency: "~1ms", color: "#60a5fa", colorRgb: "96,165,250" },
];

const TRADITIONAL = [
  { label: "Initiate", ms: 500 },
  { label: "Pay", ms: 2000 },
  { label: "Deliver", ms: 1000 },
  { label: "Verify", ms: 500 },
  { label: "Complete", ms: 200 },
];

const EXPRESS_MS = 85;

/* ── speed gauge component ── */
function SpeedGauge({ totalMs, visible }: { totalMs: number; visible: boolean }) {
  // Map 0-200ms to 0-270 degrees. <10 green, 10-50 amber, >50 red
  const maxMs = 200;
  const clampedMs = Math.min(totalMs, maxMs);
  const sweepAngle = (clampedMs / maxMs) * 270;
  const needleAngle = -135 + sweepAngle;

  const cx = 100;
  const cy = 100;
  const r = 75;

  // Build arc segments for color zones
  function arcPath(startDeg: number, endDeg: number) {
    const startRad = ((startDeg - 90) * Math.PI) / 180;
    const endRad = ((endDeg - 90) * Math.PI) / 180;
    const x1 = cx + r * Math.cos(startRad);
    const y1 = cy + r * Math.sin(startRad);
    const x2 = cx + r * Math.cos(endRad);
    const y2 = cy + r * Math.sin(endRad);
    const largeArc = endDeg - startDeg > 180 ? 1 : 0;
    return `M ${x1} ${y1} A ${r} ${r} 0 ${largeArc} 1 ${x2} ${y2}`;
  }

  // -135deg to +135deg = 270 total. split into 3 zones
  // Green: 0-10ms => 0 to (10/200)*270 = 13.5deg
  // Amber: 10-50ms => 13.5deg to 67.5deg
  // Red:   50-200ms => 67.5deg to 270deg
  const greenEnd = (10 / maxMs) * 270;
  const amberEnd = (50 / maxMs) * 270;

  return (
    <div
      style={{
        position: "relative",
        width: 200,
        height: 200,
        animation: visible ? "edv-card-enter 0.6s ease-out 0.3s both" : "none",
      }}
    >
      <svg width="200" height="200" viewBox="0 0 200 200">
        {/* Background track */}
        <path
          d={arcPath(-135, 135)}
          fill="none"
          stroke="rgba(255,255,255,0.06)"
          strokeWidth="12"
          strokeLinecap="round"
        />

        {/* Green zone */}
        <path
          d={arcPath(-135, -135 + greenEnd)}
          fill="none"
          stroke="#34d399"
          strokeWidth="12"
          strokeLinecap="round"
          opacity={0.25}
        />

        {/* Amber zone */}
        <path
          d={arcPath(-135 + greenEnd, -135 + amberEnd)}
          fill="none"
          stroke="#fbbf24"
          strokeWidth="12"
          strokeLinecap="round"
          opacity={0.25}
        />

        {/* Red zone */}
        <path
          d={arcPath(-135 + amberEnd, 135)}
          fill="none"
          stroke="#f87171"
          strokeWidth="12"
          strokeLinecap="round"
          opacity={0.25}
        />

        {/* Active arc up to value */}
        {visible && (
          <path
            d={arcPath(-135, -135 + sweepAngle)}
            fill="none"
            stroke={totalMs < 10 ? "#34d399" : totalMs < 50 ? "#fbbf24" : "#f87171"}
            strokeWidth="12"
            strokeLinecap="round"
            style={{
              filter: `drop-shadow(0 0 6px ${totalMs < 10 ? "rgba(52,211,153,0.5)" : totalMs < 50 ? "rgba(251,191,36,0.5)" : "rgba(248,113,113,0.5)"})`,
            }}
          >
            <animate
              attributeName="stroke-dasharray"
              from="0 1000"
              to="1000 0"
              dur="1.5s"
              fill="freeze"
            />
          </path>
        )}

        {/* Pulsing ring */}
        <circle
          cx={cx}
          cy={cy}
          r="50"
          fill="none"
          stroke="#00ff88"
          strokeWidth="0.5"
          style={{ animation: "edv-pulse-ring 2s ease-in-out infinite" }}
        />

        {/* Needle */}
        {visible && (
          <line
            x1={cx}
            y1={cy}
            x2={cx}
            y2={cy - 60}
            stroke="#e2e8f0"
            strokeWidth="2"
            strokeLinecap="round"
            style={{
              transformOrigin: `${cx}px ${cy}px`,
              transform: `rotate(${needleAngle}deg)`,
              animation: "edv-needle-sweep 1.5s ease-out forwards",
              filter: "drop-shadow(0 0 3px rgba(226,232,240,0.4))",
            }}
          />
        )}

        {/* Center dot */}
        <circle cx={cx} cy={cy} r="4" fill="#e2e8f0" />
        <circle cx={cx} cy={cy} r="2" fill="#0a0e1a" />

        {/* Scale labels */}
        <text x="30" y="170" fill="#64748b" fontSize="9" fontFamily="var(--font-mono, ui-monospace, monospace)">0</text>
        <text x="155" y="170" fill="#64748b" fontSize="9" fontFamily="var(--font-mono, ui-monospace, monospace)">200ms</text>
      </svg>

      {/* Center text */}
      <div
        style={{
          position: "absolute",
          top: "50%",
          left: "50%",
          transform: "translate(-50%, -30%)",
          textAlign: "center",
        }}
      >
        <div
          style={{
            fontSize: 28,
            fontWeight: 800,
            fontFamily: "var(--font-mono, ui-monospace, monospace)",
            color: "#00ff88",
            animation: visible ? "edv-glow-number 2s ease-in-out infinite" : "none",
            lineHeight: 1,
          }}
        >
          {"< 100ms"}
        </div>
        <div style={{ fontSize: 9, color: "#64748b", marginTop: 2, letterSpacing: "0.08em", textTransform: "uppercase" as const }}>
          Total Delivery
        </div>
      </div>
    </div>
  );
}

/* ── pipeline connector SVG ── */
function PipelineConnector({ color, delay }: { color: string; delay: number }) {
  return (
    <svg
      width="32"
      height="8"
      viewBox="0 0 32 8"
      fill="none"
      style={{ flexShrink: 0, marginTop: 20 }}
    >
      <line
        x1="0"
        y1="4"
        x2="26"
        y2="4"
        stroke={color}
        strokeWidth="1.5"
        strokeDasharray="4 4"
        strokeLinecap="round"
        style={{
          animation: `edv-flow-dash 0.8s linear infinite`,
          animationDelay: `${delay}ms`,
        }}
      />
      <polygon points="24,1 30,4 24,7" fill={color} opacity={0.7} />
      {/* Flowing dot */}
      <circle r="2" fill={color}>
        <animateMotion
          dur="1s"
          repeatCount="indefinite"
          begin={`${delay / 1000}s`}
          path="M0,4 L26,4"
        />
        <animate
          attributeName="opacity"
          values="0;1;1;0"
          dur="1s"
          repeatCount="indefinite"
          begin={`${delay / 1000}s`}
        />
      </circle>
    </svg>
  );
}

/* ── main component ── */
export default function ExpressDeliveryViz() {
  ensureStyles();

  const [visible, setVisible] = useState(false);
  const [activeStage, setActiveStage] = useState(-1);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const tradTotal = TRADITIONAL.reduce((s, t) => s + t.ms, 0);

  useEffect(() => {
    const t = setTimeout(() => setVisible(true), 50);
    return () => clearTimeout(t);
  }, []);

  // Sequential stage animation
  useEffect(() => {
    if (!visible) return;
    let stage = 0;
    setActiveStage(0);
    intervalRef.current = setInterval(() => {
      stage += 1;
      if (stage >= STAGES.length) {
        if (intervalRef.current) clearInterval(intervalRef.current);
        setActiveStage(STAGES.length); // all complete
        return;
      }
      setActiveStage(stage);
    }, 500);
    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current);
    };
  }, [visible]);

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 28 }}>
      {/* ── Pipeline Stages ── */}
      <div
        style={{
          background: "#0a0e1a",
          borderRadius: 16,
          border: "1px solid rgba(255,255,255,0.06)",
          padding: "24px 20px",
          animation: visible ? "edv-card-enter 0.5s ease-out both" : "none",
          opacity: visible ? undefined : 0,
        }}
      >
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: 6,
            marginBottom: 20,
          }}
        >
          <Zap style={{ width: 16, height: 16, color: "#00ff88" }} />
          <span style={{ fontSize: 13, fontWeight: 700, color: "#e2e8f0", letterSpacing: "0.02em" }}>
            Express Pipeline
          </span>
          <span
            style={{
              marginLeft: "auto",
              fontSize: 11,
              fontFamily: "var(--font-mono, ui-monospace, monospace)",
              fontWeight: 700,
              color: "#34d399",
            }}
          >
            6 stages {"<"} 100ms
          </span>
        </div>

        {/* Stage cards - horizontal scrollable */}
        <div
          style={{
            display: "flex",
            alignItems: "flex-start",
            overflowX: "auto",
            gap: 0,
            paddingBottom: 4,
          }}
        >
          {STAGES.map((stage, i) => {
            const Icon = stage.icon;
            const isActive = i <= activeStage;
            const isCurrentlyAnimating = i === activeStage && activeStage < STAGES.length;

            return (
              <div key={stage.label} style={{ display: "flex", alignItems: "flex-start" }}>
                <div
                  style={{
                    ["--edv-stage-color" as string]: `rgba(${stage.colorRgb}, 0.4)`,
                    ["--edv-stage-glow" as string]: `rgba(${stage.colorRgb}, 0.15)`,
                    background: isActive ? "#141928" : "#0f1320",
                    borderRadius: 12,
                    border: `1px solid ${isActive ? `rgba(${stage.colorRgb}, 0.35)` : "rgba(255,255,255,0.06)"}`,
                    padding: "14px 16px",
                    minWidth: 100,
                    textAlign: "center" as const,
                    position: "relative" as const,
                    transition: "all 0.3s ease",
                    boxShadow: isActive
                      ? `0 0 20px rgba(${stage.colorRgb}, 0.1), inset 0 1px 0 rgba(${stage.colorRgb}, 0.1)`
                      : "none",
                    animation: isCurrentlyAnimating
                      ? `edv-stage-light 0.4s ease-out forwards`
                      : undefined,
                  }}
                >
                  {/* Step number */}
                  <div
                    style={{
                      width: 22,
                      height: 22,
                      borderRadius: "50%",
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "center",
                      margin: "0 auto 8px",
                      fontSize: 10,
                      fontWeight: 800,
                      background: isActive ? `rgba(${stage.colorRgb}, 0.15)` : "rgba(255,255,255,0.04)",
                      color: isActive ? stage.color : "#64748b",
                      border: `1px solid ${isActive ? `rgba(${stage.colorRgb}, 0.3)` : "rgba(255,255,255,0.06)"}`,
                      transition: "all 0.3s ease",
                    }}
                  >
                    {i + 1}
                  </div>

                  {/* Icon */}
                  <Icon
                    style={{
                      width: 20,
                      height: 20,
                      margin: "0 auto 6px",
                      display: "block",
                      color: isActive ? stage.color : "#475569",
                      transition: "color 0.3s ease",
                      filter: isActive ? `drop-shadow(0 0 6px rgba(${stage.colorRgb}, 0.4))` : "none",
                    }}
                  />

                  {/* Label */}
                  <div
                    style={{
                      fontSize: 11,
                      fontWeight: 600,
                      color: isActive ? "#e2e8f0" : "#64748b",
                      marginBottom: 4,
                      transition: "color 0.3s ease",
                    }}
                  >
                    {stage.label}
                  </div>

                  {/* Latency */}
                  <div
                    style={{
                      fontSize: 10,
                      fontFamily: "var(--font-mono, ui-monospace, monospace)",
                      fontWeight: 700,
                      color: isActive ? stage.color : "#475569",
                      transition: "color 0.3s ease",
                    }}
                  >
                    {stage.latency}
                  </div>

                  {/* Check mark */}
                  {isActive && activeStage > i && (
                    <div
                      style={{
                        position: "absolute",
                        top: 6,
                        right: 6,
                        animation: "edv-check-pop 0.3s ease-out both",
                      }}
                    >
                      <CheckCircle2 style={{ width: 12, height: 12, color: "#34d399" }} />
                    </div>
                  )}
                </div>

                {/* Connector between stages */}
                {i < STAGES.length - 1 && (
                  <PipelineConnector
                    color={isActive ? stage.color : "rgba(255,255,255,0.08)"}
                    delay={i * 200}
                  />
                )}
              </div>
            );
          })}
        </div>
      </div>

      {/* ── Speed Gauge + Comparison ── */}
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "1fr 1fr",
          gap: 20,
        }}
      >
        {/* Speed Gauge */}
        <div
          style={{
            background: "#0a0e1a",
            borderRadius: 16,
            border: "1px solid rgba(0,255,136,0.12)",
            padding: 24,
            display: "flex",
            flexDirection: "column",
            alignItems: "center",
            justifyContent: "center",
            animation: visible ? "edv-card-enter 0.5s ease-out 0.2s both" : "none",
            opacity: visible ? undefined : 0,
          }}
        >
          <SpeedGauge totalMs={EXPRESS_MS} visible={visible} />
        </div>

        {/* Traditional vs Express comparison */}
        <div
          style={{
            background: "#0a0e1a",
            borderRadius: 16,
            border: "1px solid rgba(255,255,255,0.06)",
            padding: 24,
            animation: visible ? "edv-card-enter 0.5s ease-out 0.4s both" : "none",
            opacity: visible ? undefined : 0,
          }}
        >
          <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 16 }}>
            <Clock style={{ width: 14, height: 14, color: "#64748b" }} />
            <span style={{ fontSize: 12, fontWeight: 700, color: "#e2e8f0" }}>Traditional Flow</span>
            <span
              style={{
                marginLeft: "auto",
                fontSize: 11,
                fontFamily: "var(--font-mono, ui-monospace, monospace)",
                fontWeight: 700,
                color: "#f87171",
              }}
            >
              {tradTotal}ms
            </span>
          </div>

          <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
            {TRADITIONAL.map((step, i) => (
              <div key={step.label} style={{ display: "flex", alignItems: "center", gap: 10 }}>
                <div
                  style={{
                    width: 22,
                    height: 22,
                    borderRadius: "50%",
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    fontSize: 9,
                    fontWeight: 700,
                    background: "rgba(255,255,255,0.04)",
                    color: "#64748b",
                    border: "1px solid rgba(255,255,255,0.06)",
                    flexShrink: 0,
                  }}
                >
                  {i + 1}
                </div>
                <div style={{ flex: 1 }}>
                  <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 3 }}>
                    <span style={{ fontSize: 11, fontWeight: 500, color: "#94a3b8" }}>
                      {step.label}
                    </span>
                    <span
                      style={{
                        fontSize: 10,
                        fontFamily: "var(--font-mono, ui-monospace, monospace)",
                        fontWeight: 600,
                        color: "#64748b",
                      }}
                    >
                      {step.ms}ms
                    </span>
                  </div>
                  <div
                    style={{
                      height: 4,
                      borderRadius: 2,
                      background: "rgba(255,255,255,0.06)",
                      overflow: "hidden",
                    }}
                  >
                    <div
                      style={{
                        height: "100%",
                        borderRadius: 2,
                        background: "linear-gradient(90deg, rgba(248,113,113,0.4), rgba(248,113,113,0.2))",
                        width: `${(step.ms / tradTotal) * 100}%`,
                        animation: visible ? "edv-bar-grow 0.8s ease-out forwards" : "none",
                        animationDelay: `${0.6 + i * 0.1}s`,
                      }}
                    />
                  </div>
                </div>
              </div>
            ))}
          </div>

          {/* Express comparison bar */}
          <div
            style={{
              marginTop: 16,
              padding: "10px 12px",
              background: "rgba(0,255,136,0.04)",
              borderRadius: 10,
              border: "1px solid rgba(0,255,136,0.12)",
            }}
          >
            <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 6 }}>
              <Zap style={{ width: 12, height: 12, color: "#00ff88" }} />
              <span style={{ fontSize: 11, fontWeight: 700, color: "#00ff88" }}>Express Delivery</span>
              <span
                style={{
                  marginLeft: "auto",
                  fontSize: 11,
                  fontFamily: "var(--font-mono, ui-monospace, monospace)",
                  fontWeight: 800,
                  color: "#00ff88",
                }}
              >
                {EXPRESS_MS}ms
              </span>
            </div>
            <div
              style={{
                height: 4,
                borderRadius: 2,
                background: "rgba(255,255,255,0.06)",
                overflow: "hidden",
              }}
            >
              <div
                style={{
                  height: "100%",
                  borderRadius: 2,
                  background: "linear-gradient(90deg, #00ff88, #34d399)",
                  width: `${(EXPRESS_MS / tradTotal) * 100}%`,
                  animation: visible ? "edv-bar-grow 0.8s ease-out 1s forwards" : "none",
                  boxShadow: "0 0 8px rgba(0,255,136,0.4)",
                }}
              />
            </div>
          </div>
        </div>
      </div>

      {/* ── Speedup + Key Metrics ── */}
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fit, minmax(150px, 1fr))",
          gap: 14,
        }}
      >
        {/* Speedup card */}
        <div
          style={{
            background: "linear-gradient(135deg, #141928, #0a0e1a)",
            borderRadius: 16,
            border: "1px solid rgba(0,255,136,0.15)",
            padding: "20px 16px",
            textAlign: "center",
            animation: visible ? "edv-metric-enter 0.4s ease-out 0.8s both" : "none",
          }}
        >
          <div style={{ fontSize: 9, color: "#64748b", textTransform: "uppercase" as const, letterSpacing: "0.1em", marginBottom: 6 }}>
            Speed Boost
          </div>
          <div
            style={{
              fontSize: 36,
              fontWeight: 900,
              fontFamily: "var(--font-mono, ui-monospace, monospace)",
              background: "linear-gradient(135deg, #00ff88, #34d399)",
              WebkitBackgroundClip: "text",
              WebkitTextFillColor: "transparent",
              lineHeight: 1,
            }}
          >
            {Math.round(tradTotal / EXPRESS_MS)}x
          </div>
          <div style={{ fontSize: 10, color: "#94a3b8", marginTop: 4 }}>
            faster than traditional
          </div>
        </div>

        {/* Total latency */}
        <div
          style={{
            background: "#141928",
            borderRadius: 16,
            border: "1px solid rgba(96,165,250,0.15)",
            padding: "20px 16px",
            textAlign: "center",
            animation: visible ? "edv-metric-enter 0.4s ease-out 0.9s both" : "none",
          }}
        >
          <div style={{ fontSize: 9, color: "#64748b", textTransform: "uppercase" as const, letterSpacing: "0.1em", marginBottom: 6 }}>
            Total Latency
          </div>
          <div
            style={{
              fontSize: 24,
              fontWeight: 800,
              fontFamily: "var(--font-mono, ui-monospace, monospace)",
              color: "#60a5fa",
              textShadow: "0 0 12px rgba(96,165,250,0.4)",
            }}
          >
            {EXPRESS_MS}ms
          </div>
          <div style={{ fontSize: 10, color: "#94a3b8", marginTop: 4 }}>
            end-to-end delivery
          </div>
        </div>

        {/* Cache hit rate */}
        <div
          style={{
            background: "#141928",
            borderRadius: 16,
            border: "1px solid rgba(251,191,36,0.15)",
            padding: "20px 16px",
            textAlign: "center",
            animation: visible ? "edv-metric-enter 0.4s ease-out 1.0s both" : "none",
          }}
        >
          <div style={{ fontSize: 9, color: "#64748b", textTransform: "uppercase" as const, letterSpacing: "0.1em", marginBottom: 6 }}>
            Cache Hit Rate
          </div>
          <div
            style={{
              fontSize: 24,
              fontWeight: 800,
              fontFamily: "var(--font-mono, ui-monospace, monospace)",
              color: "#fbbf24",
              textShadow: "0 0 12px rgba(251,191,36,0.4)",
            }}
          >
            97.2%
          </div>
          <div style={{ fontSize: 10, color: "#94a3b8", marginTop: 4 }}>
            hot + warm tiers
          </div>
        </div>

        {/* Success rate */}
        <div
          style={{
            background: "#141928",
            borderRadius: 16,
            border: "1px solid rgba(52,211,153,0.15)",
            padding: "20px 16px",
            textAlign: "center",
            animation: visible ? "edv-metric-enter 0.4s ease-out 1.1s both" : "none",
          }}
        >
          <div style={{ fontSize: 9, color: "#64748b", textTransform: "uppercase" as const, letterSpacing: "0.1em", marginBottom: 6 }}>
            Success Rate
          </div>
          <div
            style={{
              fontSize: 24,
              fontWeight: 800,
              fontFamily: "var(--font-mono, ui-monospace, monospace)",
              color: "#34d399",
              textShadow: "0 0 12px rgba(52,211,153,0.4)",
            }}
          >
            99.98%
          </div>
          <div style={{ fontSize: 10, color: "#94a3b8", marginTop: 4 }}>
            delivery verification
          </div>
        </div>
      </div>

      {/* Responsive grid fix for small screens */}
      <style>{`
        @media (max-width: 768px) {
          [style*="grid-template-columns: 1fr 1fr"] {
            grid-template-columns: 1fr !important;
          }
        }
      `}</style>
    </div>
  );
}
