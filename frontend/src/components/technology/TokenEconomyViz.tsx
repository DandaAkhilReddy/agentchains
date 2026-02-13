import { useEffect, useState } from "react";
import {
  Gift,
  ShoppingCart,
  Percent,
  DollarSign,
  Code2,
  Landmark,
  ArrowRight,
} from "lucide-react";

/* ------------------------------------------------------------------ */
/*  Inline keyframes (injected once)                                   */
/* ------------------------------------------------------------------ */
const tokenStyles = `
@keyframes token-flow-right {
  0%   { transform: translateX(0); opacity: 0; }
  10%  { opacity: 1; }
  90%  { opacity: 1; }
  100% { transform: translateX(var(--flow-dist, 60px)); opacity: 0; }
}
@keyframes token-pulse {
  0%, 100% { transform: scale(1); opacity: 0.7; }
  50%      { transform: scale(1.25); opacity: 1; }
}
@keyframes token-number-tick {
  0%   { opacity: 0; transform: translateY(6px); }
  100% { opacity: 1; transform: translateY(0); }
}
@keyframes token-glow-border {
  0%, 100% { box-shadow: 0 0 0 rgba(0,0,0,0); }
  50%      { box-shadow: var(--glow-shadow); }
}
@keyframes token-dash-flow {
  to { stroke-dashoffset: -16; }
}
`;

/* ------------------------------------------------------------------ */
/*  Flow step definitions                                              */
/* ------------------------------------------------------------------ */
const FLOW_STEPS = [
  {
    id: "signup",
    icon: Gift,
    label: "Signup Bonus",
    sub: "Agent gets $0.10 credit",
    accent: "#34d399",
    accentRgb: "52,211,153",
  },
  {
    id: "purchase",
    icon: ShoppingCart,
    label: "Buyer Purchases",
    sub: "$X from buyer balance",
    accent: "#60a5fa",
    accentRgb: "96,165,250",
  },
  {
    id: "fee",
    icon: Percent,
    label: "Platform Fee",
    sub: "2% extracted",
    accent: "#fbbf24",
    accentRgb: "251,191,36",
  },
  {
    id: "seller",
    icon: DollarSign,
    label: "Seller Earnings",
    sub: "98% to seller",
    accent: "#00ff88",
    accentRgb: "0,255,136",
  },
  {
    id: "royalty",
    icon: Code2,
    label: "Creator Royalty",
    sub: "100% to creator",
    accent: "#a78bfa",
    accentRgb: "167,139,250",
  },
  {
    id: "redeem",
    icon: Landmark,
    label: "Redemption",
    sub: "UPI / Bank / Gift Card",
    accent: "#34d399",
    accentRgb: "52,211,153",
  },
] as const;

/* ------------------------------------------------------------------ */
/*  Metric card definitions                                            */
/* ------------------------------------------------------------------ */
const METRICS = [
  { label: "Platform Fee", value: "2%", accent: "#fbbf24", accentRgb: "251,191,36" },
  { label: "Signup Bonus", value: "$0.10", accent: "#34d399", accentRgb: "52,211,153" },
  { label: "Min Withdrawal", value: "$10.00", accent: "#60a5fa", accentRgb: "96,165,250" },
  { label: "Creator Royalty", value: "100%", accent: "#a78bfa", accentRgb: "167,139,250" },
] as const;

/* ------------------------------------------------------------------ */
/*  Animated number (simple tick-up on mount)                          */
/* ------------------------------------------------------------------ */
function AnimatedValue({ value, accent }: { value: string; accent: string }) {
  const [show, setShow] = useState(false);
  useEffect(() => {
    const t = setTimeout(() => setShow(true), 200);
    return () => clearTimeout(t);
  }, []);
  return (
    <span
      className="text-xl font-extrabold"
      style={{
        color: accent,
        fontFamily: "var(--font-mono, ui-monospace, monospace)",
        opacity: show ? 1 : 0,
        transform: show ? "translateY(0)" : "translateY(6px)",
        transition: "all 0.5s ease-out",
      }}
    >
      {value}
    </span>
  );
}

/* ------------------------------------------------------------------ */
/*  Flow arrow with animated token dots                                */
/* ------------------------------------------------------------------ */
function FlowArrow({ color }: { color: string }) {
  return (
    <div className="relative flex items-center" style={{ width: 48, height: 24 }}>
      {/* base line */}
      <svg width="48" height="24" viewBox="0 0 48 24" className="absolute inset-0">
        <line x1="0" y1="12" x2="38" y2="12" stroke={color} strokeWidth="2"
          strokeOpacity="0.25" strokeDasharray="4 4"
          style={{ animation: "token-dash-flow 1.2s linear infinite" }} />
        <polygon points="36,7 48,12 36,17" fill={color} fillOpacity="0.5" />
      </svg>
      {/* animated dot */}
      <div
        className="absolute rounded-full"
        style={{
          width: 6,
          height: 6,
          background: color,
          top: 9,
          left: 0,
          boxShadow: `0 0 8px ${color}`,
          "--flow-dist": "38px",
          animation: "token-flow-right 1.8s ease-in-out infinite",
        } as React.CSSProperties}
      />
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  Flow Step Card                                                     */
/* ------------------------------------------------------------------ */
function FlowStepCard({ step }: { step: typeof FLOW_STEPS[number] }) {
  const Icon = step.icon;
  const [hovered, setHovered] = useState(false);
  return (
    <div
      className="flex flex-col items-center text-center shrink-0"
      style={{ minWidth: 100 }}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
    >
      <div
        className="flex h-12 w-12 items-center justify-center rounded-2xl transition-all duration-300 mb-2"
        style={{
          background: `rgba(${step.accentRgb}, ${hovered ? 0.2 : 0.12})`,
          border: `1px solid rgba(${step.accentRgb}, ${hovered ? 0.5 : 0.2})`,
          boxShadow: hovered
            ? `0 0 20px rgba(${step.accentRgb}, 0.25)`
            : `0 0 8px rgba(${step.accentRgb}, 0.1)`,
        }}
      >
        <Icon style={{ color: step.accent, width: 22, height: 22 }} />
      </div>
      <p className="text-xs font-bold" style={{ color: "#e2e8f0" }}>
        {step.label}
      </p>
      <p className="text-[10px] mt-0.5" style={{ color: "#64748b" }}>
        {step.sub}
      </p>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  Full Flow SVG (for larger screens — replaces cards)                */
/* ------------------------------------------------------------------ */
function FlowDiagramSVG() {
  const nodeX = [30, 130, 230, 330, 430, 530];
  const nodeY = 50;

  return (
    <svg viewBox="0 0 580 110" className="w-full h-auto hidden sm:block" style={{ maxHeight: 130 }}>
      <defs>
        <filter id="tokenGlow">
          <feGaussianBlur stdDeviation="3" result="blur" />
          <feMerge>
            <feMergeNode in="blur" />
            <feMergeNode in="SourceGraphic" />
          </feMerge>
        </filter>
      </defs>

      {/* Connection lines */}
      {FLOW_STEPS.slice(0, -1).map((step, i) => (
        <g key={`line-${i}`}>
          <line x1={nodeX[i] + 20} y1={nodeY} x2={nodeX[i + 1] - 20} y2={nodeY}
            stroke={step.accent} strokeWidth="2" strokeOpacity="0.2"
            strokeDasharray="5 4"
            style={{ animation: `token-dash-flow 1.5s linear infinite ${i * 0.3}s` }} />
          {/* arrowhead */}
          <polygon
            points={`${nodeX[i + 1] - 22},${nodeY - 4} ${nodeX[i + 1] - 14},${nodeY} ${nodeX[i + 1] - 22},${nodeY + 4}`}
            fill={step.accent} fillOpacity="0.4" />
          {/* animated token circle on each line */}
          <circle r="3" fill={step.accent} filter="url(#tokenGlow)">
            <animateMotion
              dur={`${1.8 + i * 0.2}s`}
              repeatCount="indefinite"
              path={`M${nodeX[i] + 20},${nodeY} L${nodeX[i + 1] - 20},${nodeY}`}
            />
          </circle>
        </g>
      ))}

      {/* Nodes */}
      {FLOW_STEPS.map((step, i) => {
        const Icon = step.icon;
        return (
          <g key={step.id}>
            <circle cx={nodeX[i]} cy={nodeY} r="18" fill={step.accent} fillOpacity="0.1"
              stroke={step.accent} strokeWidth="1.5" strokeOpacity="0.35" />
            <circle cx={nodeX[i]} cy={nodeY} r="12" fill={step.accent} fillOpacity="0.06" />
            {/* lucide icon as foreignObject */}
            <foreignObject x={nodeX[i] - 9} y={nodeY - 9} width="18" height="18">
              <div style={{ display: "flex", alignItems: "center", justifyContent: "center", width: "100%", height: "100%" }}>
                <Icon style={{ color: step.accent, width: 14, height: 14 }} />
              </div>
            </foreignObject>
            <text x={nodeX[i]} y={nodeY + 32} textAnchor="middle" fill="#e2e8f0"
              fontSize="8" fontWeight="600" fontFamily="system-ui, sans-serif">
              {step.label}
            </text>
            <text x={nodeX[i]} y={nodeY + 44} textAnchor="middle" fill="#64748b"
              fontSize="6.5" fontFamily="system-ui, sans-serif">
              {step.sub}
            </text>
          </g>
        );
      })}
    </svg>
  );
}

/* ------------------------------------------------------------------ */
/*  Main Component                                                     */
/* ------------------------------------------------------------------ */
export default function TokenEconomyViz() {
  const [stylesInjected, setStylesInjected] = useState(false);

  useEffect(() => {
    if (stylesInjected) return;
    const id = "token-economy-styles";
    if (!document.getElementById(id)) {
      const tag = document.createElement("style");
      tag.id = id;
      tag.textContent = tokenStyles;
      document.head.appendChild(tag);
    }
    setStylesInjected(true);
  }, [stylesInjected]);

  return (
    <div className="space-y-6">
      {/* ---- USD Flow Diagram ---- */}
      <div
        className="rounded-2xl border p-5 overflow-hidden"
        style={{ background: "#141928", borderColor: "rgba(255,255,255,0.06)" }}
      >
        <h3 className="text-sm font-bold mb-1" style={{ color: "#e2e8f0" }}>
          USD Flow
        </h3>
        <p className="text-xs mb-4" style={{ color: "#64748b" }}>
          How money moves through the marketplace
        </p>

        {/* Large-screen SVG flow */}
        <FlowDiagramSVG />

        {/* Small-screen card flow (visible only on mobile) */}
        <div className="flex items-center gap-1 overflow-x-auto pb-2 sm:hidden">
          {FLOW_STEPS.map((step, i) => (
            <div key={step.id} className="flex items-center gap-1 shrink-0">
              <FlowStepCard step={step} />
              {i < FLOW_STEPS.length - 1 && (
                <FlowArrow color={step.accent} />
              )}
            </div>
          ))}
        </div>
      </div>

      {/* ---- Key Metrics ---- */}
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        {METRICS.map((m) => (
          <div
            key={m.label}
            className="rounded-2xl border p-4 text-center transition-all duration-300"
            style={{
              background: "#141928",
              borderColor: "rgba(255,255,255,0.06)",
              "--glow-shadow": `0 0 16px rgba(${m.accentRgb}, 0.15)`,
            } as React.CSSProperties}
            onMouseEnter={(e) => {
              e.currentTarget.style.borderColor = `rgba(${m.accentRgb}, 0.4)`;
              e.currentTarget.style.boxShadow = `0 0 20px rgba(${m.accentRgb}, 0.12)`;
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.borderColor = "rgba(255,255,255,0.06)";
              e.currentTarget.style.boxShadow = "none";
            }}
          >
            <p
              className="text-[10px] font-semibold uppercase tracking-widest mb-2"
              style={{ color: "#94a3b8" }}
            >
              {m.label}
            </p>
            <AnimatedValue value={m.value} accent={m.accent} />
          </div>
        ))}
      </div>

      {/* ---- Pricing Detail Table ---- */}
      <div
        className="rounded-2xl border p-5"
        style={{ background: "#141928", borderColor: "rgba(255,255,255,0.06)" }}
      >
        <h3 className="text-sm font-bold mb-4" style={{ color: "#e2e8f0" }}>
          Pricing
        </h3>
        <div className="space-y-2">
          {[
            { label: "Platform Fee", value: "2%", desc: "Flat fee on every transaction", accent: "#fbbf24" },
            { label: "Creator Royalty", value: "100%", desc: "Agent earnings go to creator", accent: "#a78bfa" },
            { label: "Min Deposit", value: "$1.00", desc: "Minimum balance top-up", accent: "#60a5fa" },
            { label: "Welcome Credit", value: "$0.10", desc: "Free credit on signup", accent: "#34d399" },
            { label: "Min Withdrawal", value: "$10.00", desc: "Minimum payout via UPI/Bank", accent: "#34d399" },
          ].map((item) => (
            <div
              key={item.label}
              className="flex items-center justify-between rounded-xl px-4 py-2.5 transition-colors duration-200"
              style={{ background: "rgba(10,14,26,0.6)" }}
            >
              <div className="flex items-center gap-3">
                <div
                  className="h-1.5 w-1.5 rounded-full"
                  style={{ background: item.accent, boxShadow: `0 0 6px ${item.accent}` }}
                />
                <div>
                  <p className="text-xs font-medium" style={{ color: "#e2e8f0" }}>
                    {item.label}
                  </p>
                  <p className="text-[10px]" style={{ color: "#64748b" }}>
                    {item.desc}
                  </p>
                </div>
              </div>
              <span
                className="text-sm font-bold"
                style={{
                  color: item.accent,
                  fontFamily: "var(--font-mono, ui-monospace, monospace)",
                }}
              >
                {item.value}
              </span>
            </div>
          ))}
        </div>
      </div>

      {/* ---- How Billing Works (preserved from original, restyled) ---- */}
      <div
        className="rounded-2xl border p-5"
        style={{ background: "#141928", borderColor: "rgba(255,255,255,0.06)" }}
      >
        <h3 className="text-sm font-bold mb-4" style={{ color: "#e2e8f0" }}>
          How Billing Works
        </h3>
        <div className="flex flex-col items-center gap-3 sm:flex-row sm:justify-center sm:gap-6">
          {[
            { icon: ShoppingCart, label: "Deposit", sub: "Add USD to balance", accent: "#60a5fa", accentRgb: "96,165,250" },
            { icon: ArrowRight, label: "Purchase", sub: "Buy agent data", accent: "#a78bfa", accentRgb: "167,139,250" },
            { icon: DollarSign, label: "Seller +98%", sub: "Seller gets 98%", accent: "#00ff88", accentRgb: "0,255,136" },
            { icon: Percent, label: "Fee 2%", sub: "Platform fee", accent: "#fbbf24", accentRgb: "251,191,36" },
          ].map((step, i, arr) => {
            const Icon = step.icon;
            return (
              <div key={step.label} className="flex items-center gap-4">
                <div className="text-center">
                  <div
                    className="mx-auto flex h-11 w-11 items-center justify-center rounded-xl mb-1.5 transition-all duration-200"
                    style={{
                      background: `rgba(${step.accentRgb}, 0.12)`,
                      border: `1px solid rgba(${step.accentRgb}, 0.25)`,
                      boxShadow: `0 0 10px rgba(${step.accentRgb}, 0.1)`,
                    }}
                  >
                    <Icon style={{ color: step.accent, width: 20, height: 20 }} />
                  </div>
                  <p className="text-xs font-semibold" style={{ color: "#e2e8f0" }}>
                    {step.label}
                  </p>
                  <p className="text-[10px]" style={{ color: "#64748b" }}>
                    {step.sub}
                  </p>
                </div>
                {i < arr.length - 1 && (
                  <div className="hidden sm:block">
                    <svg width="32" height="12" viewBox="0 0 32 12">
                      <line x1="0" y1="6" x2="24" y2="6" stroke={step.accent}
                        strokeWidth="1.5" strokeOpacity="0.3" strokeDasharray="3 3"
                        style={{ animation: "token-dash-flow 1.5s linear infinite" }} />
                      <polygon points="22,3 32,6 22,9" fill={step.accent} fillOpacity="0.45" />
                    </svg>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
