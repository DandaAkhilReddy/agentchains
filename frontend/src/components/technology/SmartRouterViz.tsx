import { useState } from "react";
import {
  DollarSign,
  Zap,
  TrendingUp,
  Star,
  RefreshCw,
  Shuffle,
  MapPin,
  Route,
} from "lucide-react";

/* ------------------------------------------------------------------ */
/*  Strategy definitions — all 7 routing strategies                    */
/* ------------------------------------------------------------------ */
const STRATEGIES = [
  {
    id: "cheapest",
    label: "Cheapest",
    description: "Routes to the lowest-cost provider available in the marketplace.",
    optimizes: "Price",
    icon: DollarSign,
    color: "#34d399",
    colorFaded: "rgba(52,211,153,0.12)",
    formula: "sort by price ASC",
    weights: { price: 1, speed: 0, quality: 0, reputation: 0, freshness: 0 },
    meter: 0.92,
  },
  {
    id: "fastest",
    label: "Fastest",
    description: "Picks the provider with lowest latency and highest cache-hit rate.",
    optimizes: "Speed",
    icon: Zap,
    color: "#fbbf24",
    colorFaded: "rgba(251,191,36,0.12)",
    formula: "cache_hit + low latency",
    weights: { price: 0, speed: 1, quality: 0, reputation: 0, freshness: 0 },
    meter: 0.88,
  },
  {
    id: "best_value",
    label: "Best Value",
    description: "Balances quality against price for optimal cost-effectiveness.",
    optimizes: "Value Ratio",
    icon: TrendingUp,
    color: "#60a5fa",
    colorFaded: "rgba(96,165,250,0.12)",
    formula: "0.4 x (quality/price) + 0.25 x rep + 0.2 x fresh + 0.15 x (1-price)",
    weights: { price: 0.15, speed: 0, quality: 0.4, reputation: 0.25, freshness: 0.2 },
    meter: 0.85,
  },
  {
    id: "highest_quality",
    label: "Highest Quality",
    description: "Selects the top-rated provider regardless of cost or speed.",
    optimizes: "Quality",
    icon: Star,
    color: "#a78bfa",
    colorFaded: "rgba(167,139,250,0.12)",
    formula: "0.5 x quality + 0.3 x reputation + 0.2 x freshness",
    weights: { price: 0, speed: 0, quality: 0.5, reputation: 0.3, freshness: 0.2 },
    meter: 0.95,
  },
  {
    id: "round_robin",
    label: "Round Robin",
    description: "Evenly distributes requests across all providers for fairness.",
    optimizes: "Fairness",
    icon: RefreshCw,
    color: "#22d3ee",
    colorFaded: "rgba(34,211,238,0.12)",
    formula: "fair rotation among sellers",
    weights: { price: 0.2, speed: 0.2, quality: 0.2, reputation: 0.2, freshness: 0.2 },
    meter: 0.6,
  },
  {
    id: "weighted_random",
    label: "Weighted Random",
    description: "Probabilistic selection weighted by provider reputation score.",
    optimizes: "Diversity",
    icon: Shuffle,
    color: "#f472b6",
    colorFaded: "rgba(244,114,182,0.12)",
    formula: "probabilistic by reputation",
    weights: { price: 0.33, speed: 0, quality: 0.33, reputation: 0.34, freshness: 0 },
    meter: 0.72,
  },
  {
    id: "locality",
    label: "Locality",
    description: "Prefers geographically close providers to reduce network hops.",
    optimizes: "Proximity",
    icon: MapPin,
    color: "#00ff88",
    colorFaded: "rgba(0,255,136,0.12)",
    formula: "0.5 x proximity + 0.2 x quality + 0.3 x price",
    weights: { price: 0.3, speed: 0, quality: 0.2, reputation: 0, freshness: 0 },
    meter: 0.78,
  },
];

/* ------------------------------------------------------------------ */
/*  CSS-in-JS style blocks (injected via <style> tag)                  */
/* ------------------------------------------------------------------ */
const injectId = "smart-router-viz-styles";

const css = `
/* ---- keyframes ---- */
@keyframes sr-pulse-ring {
  0%   { transform: scale(0.85); opacity: 0.7; }
  50%  { transform: scale(1.15); opacity: 0.3; }
  100% { transform: scale(0.85); opacity: 0.7; }
}
@keyframes sr-bar-fill {
  from { width: 0%; }
}
@keyframes sr-dash-flow {
  to { stroke-dashoffset: -20; }
}
@keyframes sr-center-glow {
  0%   { box-shadow: 0 0 20px rgba(96,165,250,0.15); }
  50%  { box-shadow: 0 0 36px rgba(96,165,250,0.35); }
  100% { box-shadow: 0 0 20px rgba(96,165,250,0.15); }
}
@keyframes sr-icon-spin {
  from { transform: rotate(0deg); }
  to   { transform: rotate(360deg); }
}

/* ---- reusable classes ---- */
.sr-card {
  background: #141928;
  border-radius: 16px;
  border: 1px solid rgba(255,255,255,0.06);
  padding: 20px;
  cursor: pointer;
  transition: all 0.3s cubic-bezier(0.4,0,0.2,1);
  position: relative;
  overflow: hidden;
}
.sr-card::before {
  content: '';
  position: absolute;
  inset: 0;
  border-radius: 16px;
  padding: 1px;
  background: linear-gradient(135deg, transparent 40%, var(--card-accent) 100%);
  -webkit-mask: linear-gradient(#fff 0 0) content-box, linear-gradient(#fff 0 0);
  -webkit-mask-composite: xor;
  mask-composite: exclude;
  opacity: 0;
  transition: opacity 0.3s;
  pointer-events: none;
}
.sr-card:hover::before,
.sr-card.sr-active::before {
  opacity: 1;
}
.sr-card:hover,
.sr-card.sr-active {
  border-color: var(--card-accent);
  box-shadow: 0 0 24px color-mix(in srgb, var(--card-accent) 18%, transparent);
}
.sr-card.sr-active {
  background: #1a2035;
}

.sr-icon-ring {
  width: 40px; height: 40px;
  border-radius: 50%;
  display: flex; align-items: center; justify-content: center;
  position: relative;
  flex-shrink: 0;
}
.sr-icon-ring::after {
  content: '';
  position: absolute; inset: -4px;
  border-radius: 50%;
  border: 2px solid var(--card-accent);
  opacity: 0;
  transition: opacity 0.3s;
}
.sr-card.sr-active .sr-icon-ring::after {
  opacity: 0.35;
  animation: sr-pulse-ring 2.4s ease-in-out infinite;
}

.sr-meter-track {
  width: 100%; height: 6px;
  border-radius: 3px;
  background: rgba(255,255,255,0.06);
  overflow: hidden;
  margin-top: 12px;
}
.sr-meter-fill {
  height: 100%;
  border-radius: 3px;
  animation: sr-bar-fill 0.8s cubic-bezier(0.4,0,0.2,1) forwards;
}

/* ---- center router hub ---- */
.sr-router-hub {
  width: 72px; height: 72px;
  border-radius: 50%;
  background: linear-gradient(135deg, #1a2035, #141928);
  border: 2px solid rgba(96,165,250,0.35);
  display: flex; align-items: center; justify-content: center;
  animation: sr-center-glow 3s ease-in-out infinite;
  position: relative;
  z-index: 2;
}
.sr-router-hub svg {
  color: #60a5fa;
}

/* ---- detail pane ---- */
.sr-detail {
  background: #141928;
  border-radius: 16px;
  border: 1px solid rgba(255,255,255,0.06);
  padding: 24px;
}
.sr-weight-row {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 10px;
}
.sr-weight-label {
  width: 80px;
  font-size: 12px;
  color: #94a3b8;
  text-transform: capitalize;
}
.sr-weight-track {
  flex: 1;
  height: 8px;
  border-radius: 4px;
  background: rgba(255,255,255,0.06);
  overflow: hidden;
}
.sr-weight-fill {
  height: 100%;
  border-radius: 4px;
  transition: width 0.5s cubic-bezier(0.4,0,0.2,1);
}
.sr-weight-val {
  width: 36px;
  text-align: right;
  font-size: 12px;
  font-family: monospace;
  color: #e2e8f0;
}

/* SVG animated paths */
.sr-path-line {
  stroke-dasharray: 6 4;
  animation: sr-dash-flow 1.2s linear infinite;
}
`;

/* ------------------------------------------------------------------ */
/*  Component                                                          */
/* ------------------------------------------------------------------ */
export default function SmartRouterViz() {
  const [selected, setSelected] = useState("best_value");
  const strategy = STRATEGIES.find((s) => s.id === selected)!;

  /* Inject styles once */
  if (typeof document !== "undefined" && !document.getElementById(injectId)) {
    const tag = document.createElement("style");
    tag.id = injectId;
    tag.textContent = css;
    document.head.appendChild(tag);
  }

  /* Weight bar color per dimension */
  const dimensionColor: Record<string, string> = {
    price: "#34d399",
    speed: "#fbbf24",
    quality: "#a78bfa",
    reputation: "#60a5fa",
    freshness: "#22d3ee",
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 28 }}>
      {/* ---- Section header ---- */}
      <div>
        <h2
          style={{
            fontSize: 20,
            fontWeight: 700,
            color: "#e2e8f0",
            margin: 0,
            marginBottom: 4,
          }}
        >
          Smart Router Strategies
        </h2>
        <p style={{ fontSize: 13, color: "#64748b", margin: 0 }}>
          Choose how the marketplace routes buyer requests to the optimal seller
          listing. Each strategy prioritizes different optimization axes.
        </p>
      </div>

      {/* ---- Center routing visualisation (SVG hub + spokes) ---- */}
      <div
        style={{
          position: "relative",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          padding: "32px 0",
        }}
      >
        {/* SVG behind hub for animated paths */}
        <svg
          width="100%"
          height="160"
          viewBox="0 0 800 160"
          style={{ position: "absolute", inset: 0 }}
          preserveAspectRatio="xMidYMid meet"
        >
          {STRATEGIES.map((s, i) => {
            const startX = 400;
            const startY = 80;
            const angle = ((i - 3) / 6) * Math.PI;
            const endX = 400 + Math.cos(angle) * 340;
            const endY = 80 + Math.sin(angle) * 60;
            const isActive = s.id === selected;
            return (
              <line
                key={s.id}
                x1={startX}
                y1={startY}
                x2={endX}
                y2={endY}
                stroke={isActive ? s.color : "rgba(255,255,255,0.06)"}
                strokeWidth={isActive ? 2 : 1}
                className="sr-path-line"
                style={{
                  opacity: isActive ? 0.7 : 0.25,
                  transition: "stroke 0.3s, opacity 0.3s",
                }}
              />
            );
          })}
        </svg>

        {/* Center hub */}
        <div className="sr-router-hub">
          <Route size={28} />
        </div>
      </div>

      {/* ---- Strategy cards grid ---- */}
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fill, minmax(260px, 1fr))",
          gap: 16,
        }}
      >
        {STRATEGIES.map((s) => {
          const Icon = s.icon;
          const isActive = s.id === selected;
          return (
            <div
              key={s.id}
              className={`sr-card${isActive ? " sr-active" : ""}`}
              style={{ "--card-accent": s.color } as React.CSSProperties}
              onClick={() => setSelected(s.id)}
              role="button"
              tabIndex={0}
              onKeyDown={(e) => {
                if (e.key === "Enter" || e.key === " ") setSelected(s.id);
              }}
            >
              {/* Top row: icon + title */}
              <div
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: 12,
                  marginBottom: 10,
                }}
              >
                <div
                  className="sr-icon-ring"
                  style={{
                    background: s.colorFaded,
                    "--card-accent": s.color,
                  } as React.CSSProperties}
                >
                  <Icon
                    size={18}
                    style={{
                      color: s.color,
                      ...(isActive && s.id === "round_robin"
                        ? { animation: "sr-icon-spin 3s linear infinite" }
                        : {}),
                    }}
                  />
                </div>
                <div>
                  <div
                    style={{
                      fontSize: 14,
                      fontWeight: 600,
                      color: isActive ? s.color : "#e2e8f0",
                      transition: "color 0.3s",
                    }}
                  >
                    {s.label}
                  </div>
                  <div
                    style={{
                      fontSize: 11,
                      color: "#64748b",
                      marginTop: 1,
                    }}
                  >
                    Optimizes for:{" "}
                    <span style={{ color: s.color, fontWeight: 600 }}>
                      {s.optimizes}
                    </span>
                  </div>
                </div>
              </div>

              {/* Description */}
              <p
                style={{
                  fontSize: 12,
                  color: "#94a3b8",
                  margin: 0,
                  lineHeight: 1.5,
                }}
              >
                {s.description}
              </p>

              {/* Formula (mono) */}
              <div
                style={{
                  fontSize: 10,
                  fontFamily: "monospace",
                  color: "#64748b",
                  marginTop: 8,
                  background: "rgba(255,255,255,0.03)",
                  padding: "4px 8px",
                  borderRadius: 6,
                }}
              >
                {s.formula}
              </div>

              {/* Animated meter */}
              <div className="sr-meter-track">
                <div
                  className="sr-meter-fill"
                  style={{
                    width: `${s.meter * 100}%`,
                    background: `linear-gradient(90deg, ${s.color}, ${s.color}88)`,
                  }}
                />
              </div>
            </div>
          );
        })}
      </div>

      {/* ---- Detail pane: weight breakdown for selected strategy ---- */}
      <div className="sr-detail">
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: 12,
            marginBottom: 16,
          }}
        >
          <div
            className="sr-icon-ring"
            style={{
              background: strategy.colorFaded,
              "--card-accent": strategy.color,
            } as React.CSSProperties}
          >
            <strategy.icon size={18} style={{ color: strategy.color }} />
          </div>
          <div>
            <h3
              style={{
                fontSize: 16,
                fontWeight: 700,
                color: "#e2e8f0",
                margin: 0,
              }}
            >
              {strategy.label} — Weight Breakdown
            </h3>
            <p
              style={{
                fontSize: 12,
                fontFamily: "monospace",
                color: "#64748b",
                margin: 0,
                marginTop: 2,
              }}
            >
              {strategy.formula}
            </p>
          </div>
        </div>

        {/* Weight bars */}
        {Object.entries(strategy.weights).map(([dim, val]) => (
          <div className="sr-weight-row" key={dim}>
            <span className="sr-weight-label">{dim}</span>
            <div className="sr-weight-track">
              <div
                className="sr-weight-fill"
                style={{
                  width: `${val * 100}%`,
                  background: dimensionColor[dim] ?? "#60a5fa",
                }}
              />
            </div>
            <span className="sr-weight-val">{(val * 100).toFixed(0)}%</span>
          </div>
        ))}

        {/* Legend dots */}
        <div
          style={{
            display: "flex",
            flexWrap: "wrap",
            gap: 16,
            marginTop: 16,
            paddingTop: 12,
            borderTop: "1px solid rgba(255,255,255,0.06)",
          }}
        >
          {Object.entries(dimensionColor).map(([dim, col]) => (
            <span
              key={dim}
              style={{
                display: "flex",
                alignItems: "center",
                gap: 6,
                fontSize: 11,
                color: "#94a3b8",
                textTransform: "capitalize",
              }}
            >
              <span
                style={{
                  width: 8,
                  height: 8,
                  borderRadius: "50%",
                  background: col,
                  display: "inline-block",
                }}
              />
              {dim}
            </span>
          ))}
        </div>
      </div>
    </div>
  );
}
