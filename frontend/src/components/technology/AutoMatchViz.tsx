import { useState } from "react";
import {
  Search,
  CheckCircle,
  Cpu,
  ShoppingCart,
  Tag,
  ArrowRight,
} from "lucide-react";

/* ------------------------------------------------------------------ */
/*  Data                                                               */
/* ------------------------------------------------------------------ */
const MOCK_LISTINGS = [
  {
    title: "Python FastAPI tutorial",
    keyword: 0.45,
    quality: 0.24,
    freshness: 0.18,
    spec: 0.1,
    price: 0.012,
    freshCost: 0.028,
  },
  {
    title: "Django REST framework",
    keyword: 0.35,
    quality: 0.27,
    freshness: 0.16,
    spec: 0.1,
    price: 0.009,
    freshCost: 0.022,
  },
  {
    title: "Flask web development",
    keyword: 0.3,
    quality: 0.21,
    freshness: 0.14,
    spec: 0,
    price: 0.007,
    freshCost: 0.018,
  },
  {
    title: "Node.js Express guide",
    keyword: 0.1,
    quality: 0.28,
    freshness: 0.19,
    spec: 0,
    price: 0.011,
    freshCost: 0.025,
  },
];

const FRESH_COSTS = [
  { category: "web_search", fresh: 0.01, cached: 0.003 },
  { category: "code_analysis", fresh: 0.02, cached: 0.005 },
  { category: "document_summary", fresh: 0.015, cached: 0.004 },
  { category: "api_response", fresh: 0.005, cached: 0.002 },
  { category: "computation", fresh: 0.03, cached: 0.008 },
];

const SCORING_FACTORS = [
  { label: "Price Weight", value: 0.25, color: "#34d399" },
  { label: "Quality Weight", value: 0.3, color: "#a78bfa" },
  { label: "Freshness Weight", value: 0.25, color: "#22d3ee" },
  { label: "Reputation Weight", value: 0.2, color: "#fbbf24" },
];

/* ------------------------------------------------------------------ */
/*  Styles                                                             */
/* ------------------------------------------------------------------ */
const injectId = "auto-match-viz-styles";

const css = `
/* ---- keyframes ---- */
@keyframes am-pulse {
  0%   { transform: scale(1); opacity: 1; }
  50%  { transform: scale(1.08); opacity: 0.7; }
  100% { transform: scale(1); opacity: 1; }
}
@keyframes am-spin {
  from { transform: rotate(0deg); }
  to   { transform: rotate(360deg); }
}
@keyframes am-bar-grow {
  from { width: 0%; }
}
@keyframes am-flow-dots {
  0%   { opacity: 0.2; transform: translateX(-8px); }
  50%  { opacity: 1;   transform: translateX(0); }
  100% { opacity: 0.2; transform: translateX(8px); }
}
@keyframes am-check-pop {
  0%   { transform: scale(0); }
  60%  { transform: scale(1.2); }
  100% { transform: scale(1); }
}
@keyframes am-glow {
  0%   { box-shadow: 0 0 12px rgba(96,165,250,0.15); }
  50%  { box-shadow: 0 0 28px rgba(96,165,250,0.35); }
  100% { box-shadow: 0 0 12px rgba(96,165,250,0.15); }
}

/* ---- dark cards ---- */
.am-card {
  background: #141928;
  border-radius: 16px;
  border: 1px solid rgba(255,255,255,0.06);
  padding: 20px;
  transition: all 0.3s;
}
.am-card:hover {
  border-color: rgba(255,255,255,0.1);
}

/* ---- match engine hub ---- */
.am-engine {
  width: 80px; height: 80px;
  border-radius: 50%;
  background: linear-gradient(135deg, #1a2035, #141928);
  border: 2px solid rgba(96,165,250,0.35);
  display: flex; align-items: center; justify-content: center;
  animation: am-glow 3s ease-in-out infinite;
  flex-shrink: 0;
}
.am-engine svg {
  color: #60a5fa;
  animation: am-spin 6s linear infinite;
}

/* ---- flow arrows ---- */
.am-flow-dot {
  width: 6px; height: 6px;
  border-radius: 50%;
  background: #60a5fa;
  animation: am-flow-dots 1.2s ease-in-out infinite;
}
.am-flow-dot:nth-child(2) { animation-delay: 0.2s; }
.am-flow-dot:nth-child(3) { animation-delay: 0.4s; }

/* ---- listing result card ---- */
.am-listing {
  background: #141928;
  border-radius: 12px;
  border: 1px solid rgba(255,255,255,0.06);
  padding: 14px 16px;
  transition: all 0.3s;
  position: relative;
}
.am-listing:hover {
  border-color: rgba(255,255,255,0.12);
  background: #1a2035;
}
.am-listing.am-best {
  border-color: rgba(52,211,153,0.4);
  box-shadow: 0 0 16px rgba(52,211,153,0.08);
}

/* ---- scoring bar ---- */
.am-score-track {
  height: 8px;
  border-radius: 4px;
  background: rgba(255,255,255,0.06);
  overflow: hidden;
  flex: 1;
}
.am-score-fill {
  height: 100%;
  border-radius: 4px;
  animation: am-bar-grow 0.8s cubic-bezier(0.4,0,0.2,1) forwards;
}

/* ---- stacked bar ---- */
.am-stacked-track {
  height: 10px;
  border-radius: 5px;
  overflow: hidden;
  background: rgba(255,255,255,0.06);
  display: flex;
}

/* ---- table ---- */
.am-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 12px;
}
.am-table th {
  text-align: left;
  padding: 8px 0;
  color: #64748b;
  border-bottom: 1px solid rgba(255,255,255,0.06);
  font-weight: 500;
}
.am-table th:not(:first-child) {
  text-align: right;
}
.am-table td {
  padding: 10px 0;
  border-bottom: 1px solid rgba(255,255,255,0.03);
}
.am-table td:not(:first-child) {
  text-align: right;
}
.am-table tr:last-child td {
  border-bottom: none;
}
`;

/* ------------------------------------------------------------------ */
/*  Component                                                          */
/* ------------------------------------------------------------------ */
export default function AutoMatchViz() {
  const [query, setQuery] = useState("python web framework");

  /* Inject styles once */
  if (typeof document !== "undefined" && !document.getElementById(injectId)) {
    const tag = document.createElement("style");
    tag.id = injectId;
    tag.textContent = css;
    document.head.appendChild(tag);
  }

  /* Compute totals & rank */
  const scored = MOCK_LISTINGS.map((l) => ({
    ...l,
    total: l.keyword + l.quality + l.freshness + l.spec,
    matchPct: Math.round((l.keyword + l.quality + l.freshness + l.spec) * 100),
    savings: Math.round((1 - l.price / l.freshCost) * 100),
  })).sort((a, b) => b.total - a.total);

  const bestTitle = scored[0]?.title;

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 28 }}>
      {/* ================================================================ */}
      {/*  SECTION 1 — Explanation header                                   */}
      {/* ================================================================ */}
      <div className="am-card">
        <h2
          style={{
            fontSize: 20,
            fontWeight: 700,
            color: "#e2e8f0",
            margin: 0,
            marginBottom: 6,
          }}
        >
          Auto-Match Engine
        </h2>
        <p style={{ fontSize: 13, color: "#94a3b8", margin: 0, lineHeight: 1.6 }}>
          Finds the best listing for your query using multiple scoring factors.
          The engine evaluates keyword relevance, quality ratings, data freshness,
          and seller specialization to surface the optimal cached result --
          saving you up to 70% compared to fresh computation.
        </p>
      </div>

      {/* ================================================================ */}
      {/*  SECTION 2 — Buyer -> Engine -> Matched Listings flow            */}
      {/* ================================================================ */}
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "1fr auto 1fr",
          gap: 20,
          alignItems: "start",
        }}
      >
        {/* ---- Left: Buyer Request ---- */}
        <div
          className="am-card"
          style={{ borderColor: "rgba(96,165,250,0.25)" }}
        >
          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: 8,
              marginBottom: 14,
            }}
          >
            <ShoppingCart size={16} style={{ color: "#60a5fa" }} />
            <span
              style={{ fontSize: 13, fontWeight: 600, color: "#60a5fa" }}
            >
              Buyer Request
            </span>
          </div>

          {/* Query input */}
          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: 8,
              background: "rgba(255,255,255,0.04)",
              borderRadius: 10,
              padding: "8px 12px",
              marginBottom: 14,
            }}
          >
            <Search size={14} style={{ color: "#64748b", flexShrink: 0 }} />
            <input
              type="text"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Enter search query..."
              style={{
                flex: 1,
                background: "transparent",
                border: "none",
                outline: "none",
                color: "#e2e8f0",
                fontSize: 13,
              }}
            />
          </div>

          <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
            <div style={{ display: "flex", justifyContent: "space-between" }}>
              <span style={{ fontSize: 11, color: "#64748b" }}>Budget</span>
              <span
                style={{
                  fontSize: 11,
                  color: "#34d399",
                  fontFamily: "monospace",
                }}
              >
                $0.015 / call
              </span>
            </div>
            <div style={{ display: "flex", justifyContent: "space-between" }}>
              <span style={{ fontSize: 11, color: "#64748b" }}>
                Quality Pref
              </span>
              <span
                style={{
                  fontSize: 11,
                  color: "#a78bfa",
                  fontFamily: "monospace",
                }}
              >
                High (&gt; 0.8)
              </span>
            </div>
            <div style={{ display: "flex", justifyContent: "space-between" }}>
              <span style={{ fontSize: 11, color: "#64748b" }}>
                Max Age
              </span>
              <span
                style={{
                  fontSize: 11,
                  color: "#22d3ee",
                  fontFamily: "monospace",
                }}
              >
                24 hours
              </span>
            </div>
          </div>
        </div>

        {/* ---- Center: Match Engine ---- */}
        <div
          style={{
            display: "flex",
            flexDirection: "column",
            alignItems: "center",
            gap: 12,
            paddingTop: 28,
          }}
        >
          {/* Flow dots left */}
          <div style={{ display: "flex", gap: 4, marginBottom: 8 }}>
            <div className="am-flow-dot" />
            <div className="am-flow-dot" />
            <div className="am-flow-dot" />
          </div>

          <div className="am-engine">
            <Cpu size={28} />
          </div>

          <span
            style={{
              fontSize: 11,
              fontWeight: 600,
              color: "#60a5fa",
              textAlign: "center",
              letterSpacing: 0.5,
            }}
          >
            Match Engine
          </span>

          {/* Flow dots right */}
          <div style={{ display: "flex", gap: 4, marginTop: 4 }}>
            <ArrowRight size={14} style={{ color: "#34d399", opacity: 0.6 }} />
          </div>
        </div>

        {/* ---- Right: Matched Listings ---- */}
        <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
          {scored.map((listing, idx) => {
            const isBest = listing.title === bestTitle;
            return (
              <div
                key={listing.title}
                className={`am-listing${isBest ? " am-best" : ""}`}
              >
                {/* Header row */}
                <div
                  style={{
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "space-between",
                    marginBottom: 8,
                  }}
                >
                  <div
                    style={{
                      display: "flex",
                      alignItems: "center",
                      gap: 8,
                    }}
                  >
                    {isBest && (
                      <CheckCircle
                        size={14}
                        style={{
                          color: "#34d399",
                          animation: "am-check-pop 0.4s ease-out forwards",
                        }}
                      />
                    )}
                    <span
                      style={{
                        fontSize: 13,
                        fontWeight: 600,
                        color: isBest ? "#34d399" : "#e2e8f0",
                      }}
                    >
                      {listing.title}
                    </span>
                  </div>
                  {isBest && (
                    <span
                      style={{
                        fontSize: 10,
                        fontWeight: 700,
                        color: "#0a0e1a",
                        background: "#34d399",
                        padding: "2px 8px",
                        borderRadius: 20,
                        letterSpacing: 0.3,
                      }}
                    >
                      BEST
                    </span>
                  )}
                </div>

                {/* Metrics row */}
                <div
                  style={{
                    display: "flex",
                    gap: 12,
                    flexWrap: "wrap",
                    marginBottom: 8,
                  }}
                >
                  <span style={{ fontSize: 11, color: "#64748b" }}>
                    Price:{" "}
                    <span
                      style={{ color: "#34d399", fontFamily: "monospace" }}
                    >
                      ${listing.price.toFixed(3)}
                    </span>
                  </span>
                  <span style={{ fontSize: 11, color: "#64748b" }}>
                    Quality:{" "}
                    <span
                      style={{ color: "#a78bfa", fontFamily: "monospace" }}
                    >
                      {(listing.quality * 3.3).toFixed(1)}
                    </span>
                  </span>
                  <span style={{ fontSize: 11, color: "#64748b" }}>
                    Match:{" "}
                    <span
                      style={{
                        color: "#60a5fa",
                        fontWeight: 700,
                        fontFamily: "monospace",
                      }}
                    >
                      {listing.matchPct}%
                    </span>
                  </span>
                </div>

                {/* Score bar (stacked) */}
                <div className="am-stacked-track">
                  <div
                    style={{
                      width: `${listing.keyword * 100}%`,
                      background: "#60a5fa",
                      transition: "width 0.5s",
                    }}
                  />
                  <div
                    style={{
                      width: `${listing.quality * 100}%`,
                      background: "#a78bfa",
                      transition: "width 0.5s",
                    }}
                  />
                  <div
                    style={{
                      width: `${listing.freshness * 100}%`,
                      background: "#22d3ee",
                      transition: "width 0.5s",
                    }}
                  />
                  {listing.spec > 0 && (
                    <div
                      style={{
                        width: `${listing.spec * 100}%`,
                        background: "#fbbf24",
                        transition: "width 0.5s",
                      }}
                    />
                  )}
                </div>

                {/* Savings indicator */}
                <div style={{ marginTop: 8, display: "flex", alignItems: "center", gap: 6 }}>
                  <Tag size={11} style={{ color: "#34d399" }} />
                  <span
                    style={{
                      fontSize: 11,
                      color: "#34d399",
                      fontWeight: 600,
                    }}
                  >
                    Save {listing.savings}% vs fresh computation
                  </span>
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* ================================================================ */}
      {/*  SECTION 3 — Scoring factors                                      */}
      {/* ================================================================ */}
      <div className="am-card">
        <h3
          style={{
            fontSize: 15,
            fontWeight: 700,
            color: "#e2e8f0",
            margin: 0,
            marginBottom: 4,
          }}
        >
          Scoring Formula
        </h3>
        <p
          style={{
            fontSize: 12,
            color: "#64748b",
            margin: 0,
            marginBottom: 16,
          }}
        >
          Each listing is scored by weighting four independent factors:
        </p>

        {/* Formula display */}
        <div
          style={{
            display: "flex",
            flexWrap: "wrap",
            alignItems: "center",
            gap: 6,
            fontSize: 12,
            fontFamily: "monospace",
            marginBottom: 20,
            padding: "10px 14px",
            background: "rgba(255,255,255,0.03)",
            borderRadius: 10,
          }}
        >
          <span style={{ color: "#94a3b8" }}>Score =</span>
          <span
            style={{
              background: "rgba(96,165,250,0.12)",
              color: "#60a5fa",
              fontWeight: 700,
              padding: "2px 8px",
              borderRadius: 4,
            }}
          >
            0.5
          </span>
          <span style={{ color: "#64748b" }}>x keyword</span>
          <span style={{ color: "#94a3b8" }}>+</span>
          <span
            style={{
              background: "rgba(167,139,250,0.12)",
              color: "#a78bfa",
              fontWeight: 700,
              padding: "2px 8px",
              borderRadius: 4,
            }}
          >
            0.3
          </span>
          <span style={{ color: "#64748b" }}>x quality</span>
          <span style={{ color: "#94a3b8" }}>+</span>
          <span
            style={{
              background: "rgba(34,211,238,0.12)",
              color: "#22d3ee",
              fontWeight: 700,
              padding: "2px 8px",
              borderRadius: 4,
            }}
          >
            0.2
          </span>
          <span style={{ color: "#64748b" }}>x freshness</span>
          <span style={{ color: "#94a3b8" }}>+</span>
          <span
            style={{
              background: "rgba(251,191,36,0.12)",
              color: "#fbbf24",
              fontWeight: 700,
              padding: "2px 8px",
              borderRadius: 4,
            }}
          >
            0.1
          </span>
          <span style={{ color: "#64748b" }}>x specialization</span>
        </div>

        {/* Factor bars */}
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 14 }}>
          {SCORING_FACTORS.map((f) => (
            <div
              key={f.label}
              style={{
                background: "rgba(255,255,255,0.03)",
                borderRadius: 10,
                padding: "12px 14px",
              }}
            >
              <div
                style={{
                  display: "flex",
                  justifyContent: "space-between",
                  marginBottom: 8,
                }}
              >
                <span style={{ fontSize: 12, color: "#94a3b8" }}>
                  {f.label}
                </span>
                <span
                  style={{
                    fontSize: 12,
                    fontFamily: "monospace",
                    fontWeight: 700,
                    color: f.color,
                  }}
                >
                  {(f.value * 100).toFixed(0)}%
                </span>
              </div>
              <div className="am-score-track">
                <div
                  className="am-score-fill"
                  style={{
                    width: `${f.value * 100}%`,
                    background: `linear-gradient(90deg, ${f.color}, ${f.color}88)`,
                  }}
                />
              </div>
            </div>
          ))}
        </div>

        {/* Legend */}
        <div
          style={{
            display: "flex",
            gap: 16,
            marginTop: 16,
            paddingTop: 12,
            borderTop: "1px solid rgba(255,255,255,0.06)",
            flexWrap: "wrap",
          }}
        >
          {[
            { label: "Keyword", color: "#60a5fa" },
            { label: "Quality", color: "#a78bfa" },
            { label: "Freshness", color: "#22d3ee" },
            { label: "Specialization", color: "#fbbf24" },
          ].map((l) => (
            <span
              key={l.label}
              style={{
                display: "flex",
                alignItems: "center",
                gap: 6,
                fontSize: 11,
                color: "#94a3b8",
              }}
            >
              <span
                style={{
                  width: 8,
                  height: 8,
                  borderRadius: "50%",
                  background: l.color,
                  display: "inline-block",
                }}
              />
              {l.label}
            </span>
          ))}
        </div>
      </div>

      {/* ================================================================ */}
      {/*  SECTION 4 — Cached vs Fresh Cost Table                           */}
      {/* ================================================================ */}
      <div className="am-card">
        <h3
          style={{
            fontSize: 15,
            fontWeight: 700,
            color: "#e2e8f0",
            margin: 0,
            marginBottom: 4,
          }}
        >
          Cached vs Fresh Cost
        </h3>
        <p
          style={{
            fontSize: 12,
            color: "#64748b",
            margin: 0,
            marginBottom: 16,
          }}
        >
          Auto-match surfaces cached results at a fraction of fresh computation cost.
        </p>

        <table className="am-table">
          <thead>
            <tr>
              <th>Category</th>
              <th>Fresh Cost</th>
              <th>Cached Price</th>
              <th>Savings</th>
            </tr>
          </thead>
          <tbody>
            {FRESH_COSTS.map((c) => {
              const savingsPct = ((1 - c.cached / c.fresh) * 100).toFixed(0);
              return (
                <tr key={c.category}>
                  <td
                    style={{
                      color: "#e2e8f0",
                      fontWeight: 500,
                      textTransform: "capitalize",
                    }}
                  >
                    {c.category.replace(/_/g, " ")}
                  </td>
                  <td style={{ color: "#94a3b8", fontFamily: "monospace" }}>
                    ${c.fresh.toFixed(3)}
                  </td>
                  <td
                    style={{
                      color: "#34d399",
                      fontFamily: "monospace",
                      fontWeight: 600,
                    }}
                  >
                    ${c.cached.toFixed(3)}
                  </td>
                  <td>
                    <span
                      style={{
                        background: "rgba(96,165,250,0.12)",
                        color: "#60a5fa",
                        fontWeight: 700,
                        fontFamily: "monospace",
                        padding: "2px 8px",
                        borderRadius: 20,
                        fontSize: 11,
                      }}
                    >
                      {savingsPct}%
                    </span>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
