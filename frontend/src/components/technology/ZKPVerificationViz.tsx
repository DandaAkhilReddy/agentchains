import { useState, useEffect } from "react";
import { Shield, GitBranch, FileCheck, Filter, ShieldCheck, Lock, Unlock, CheckCircle2 } from "lucide-react";

/* ------------------------------------------------------------------ */
/*  Bloom-filter helper (preserved from original)                      */
/* ------------------------------------------------------------------ */
function getBloomBits(word: string): number[] {
  const bits: number[] = [];
  for (let seed = 0; seed < 3; seed++) {
    let hash = seed * 31;
    for (let i = 0; i < word.length; i++) {
      hash = ((hash << 5) - hash + word.charCodeAt(i)) | 0;
    }
    bits.push(Math.abs(hash) % 256);
  }
  return [...new Set(bits)];
}

/* ------------------------------------------------------------------ */
/*  Proof type definitions                                             */
/* ------------------------------------------------------------------ */
const PROOF_TYPES = [
  {
    id: "merkle",
    icon: GitBranch,
    title: "Merkle Root",
    desc: "Proves data exists in a hash tree without revealing the full tree",
    accent: "#60a5fa",
    accentRgb: "96,165,250",
  },
  {
    id: "schema",
    icon: FileCheck,
    title: "Schema Proof",
    desc: "Verifies data matches expected structure without exposing content",
    accent: "#a78bfa",
    accentRgb: "167,139,250",
  },
  {
    id: "bloom",
    icon: Filter,
    title: "Bloom Filter",
    desc: 'Probabilistic membership check \u2014 "probably present" or "definitely absent"',
    accent: "#34d399",
    accentRgb: "52,211,153",
  },
  {
    id: "metadata",
    icon: Shield,
    title: "Metadata Validation",
    desc: "Validates listing metadata (size, type, timestamp) without content access",
    accent: "#fbbf24",
    accentRgb: "251,191,36",
  },
] as const;

/* ------------------------------------------------------------------ */
/*  Inline keyframes (injected once via <style>)                       */
/* ------------------------------------------------------------------ */
const zkpStyles = `
@keyframes zkp-pulse-ring {
  0%, 100% { transform: scale(1); opacity: 0.5; }
  50%      { transform: scale(1.15); opacity: 1; }
}
@keyframes zkp-dash-flow {
  to { stroke-dashoffset: -20; }
}
@keyframes zkp-node-glow {
  0%, 100% { filter: drop-shadow(0 0 2px var(--glow)); }
  50%      { filter: drop-shadow(0 0 8px var(--glow)); }
}
@keyframes zkp-check-pop {
  0%   { transform: scale(0); opacity: 0; }
  60%  { transform: scale(1.3); }
  100% { transform: scale(1); opacity: 1; }
}
@keyframes zkp-unlock {
  0%   { transform: translateY(0); opacity: 1; }
  40%  { transform: translateY(-3px); opacity: 0; }
  41%  { transform: translateY(3px); opacity: 0; }
  100% { transform: translateY(0); opacity: 1; }
}
@keyframes zkp-spin-hub {
  to { transform: rotate(360deg); }
}
@keyframes zkp-verify-line {
  0%   { stroke-dashoffset: 60; }
  100% { stroke-dashoffset: 0; }
}
`;

/* ------------------------------------------------------------------ */
/*  Merkle Tree SVG                                                    */
/* ------------------------------------------------------------------ */
function MerkleTreeSVG({ accent }: { accent: string }) {
  return (
    <svg viewBox="0 0 120 72" className="w-full h-auto" style={{ maxHeight: 72 }}>
      {/* edges */}
      <line x1="60" y1="10" x2="30" y2="32" stroke={accent} strokeWidth="1.5" strokeOpacity="0.5"
        strokeDasharray="4 3" style={{ animation: "zkp-dash-flow 1.5s linear infinite" }} />
      <line x1="60" y1="10" x2="90" y2="32" stroke={accent} strokeWidth="1.5" strokeOpacity="0.5"
        strokeDasharray="4 3" style={{ animation: "zkp-dash-flow 1.5s linear infinite" }} />
      <line x1="30" y1="32" x2="15" y2="56" stroke={accent} strokeWidth="1" strokeOpacity="0.3" />
      <line x1="30" y1="32" x2="45" y2="56" stroke={accent} strokeWidth="1.5" strokeOpacity="0.7"
        strokeDasharray="4 3" style={{ animation: "zkp-dash-flow 1.5s linear infinite" }} />
      <line x1="90" y1="32" x2="75" y2="56" stroke={accent} strokeWidth="1" strokeOpacity="0.3" />
      <line x1="90" y1="32" x2="105" y2="56" stroke={accent} strokeWidth="1" strokeOpacity="0.3" />

      {/* root */}
      <circle cx="60" cy="10" r="6" fill={accent} fillOpacity="0.25" stroke={accent} strokeWidth="1.5"
        style={{ "--glow": accent, animation: "zkp-node-glow 2s ease-in-out infinite" } as React.CSSProperties} />
      <circle cx="60" cy="10" r="2.5" fill={accent} />

      {/* level-1 */}
      <circle cx="30" cy="32" r="5" fill={accent} fillOpacity="0.18" stroke={accent} strokeWidth="1" />
      <circle cx="90" cy="32" r="5" fill={accent} fillOpacity="0.18" stroke={accent} strokeWidth="1" />

      {/* leaves — highlighted path node */}
      <circle cx="15" cy="56" r="4" fill="#1a2035" stroke="#64748b" strokeWidth="1" />
      <circle cx="45" cy="56" r="4" fill={accent} fillOpacity="0.3" stroke={accent} strokeWidth="1.5"
        style={{ "--glow": accent, animation: "zkp-node-glow 2s ease-in-out infinite 0.5s" } as React.CSSProperties} />
      <circle cx="75" cy="56" r="4" fill="#1a2035" stroke="#64748b" strokeWidth="1" />
      <circle cx="105" cy="56" r="4" fill="#1a2035" stroke="#64748b" strokeWidth="1" />
    </svg>
  );
}

/* ------------------------------------------------------------------ */
/*  Schema Structure SVG                                               */
/* ------------------------------------------------------------------ */
function SchemaSVG({ accent }: { accent: string }) {
  const rows = [
    { label: "name", w: 58 },
    { label: "type", w: 44 },
    { label: "size", w: 36 },
    { label: "hash", w: 50 },
  ];
  return (
    <svg viewBox="0 0 120 72" className="w-full h-auto" style={{ maxHeight: 72 }}>
      <rect x="8" y="2" width="104" height="68" rx="6" fill="#0a0e1a" stroke={accent} strokeWidth="1" strokeOpacity="0.35" />
      <text x="60" y="14" textAnchor="middle" fill={accent} fontSize="8" fontWeight="600" fontFamily="monospace">
        {"{ schema }"}
      </text>
      {rows.map((r, i) => {
        const y = 22 + i * 13;
        return (
          <g key={r.label}>
            <text x="16" y={y + 8} fill="#94a3b8" fontSize="7" fontFamily="monospace">{r.label}:</text>
            <rect x={54} y={y + 1} width={r.w} height="9" rx="2" fill={accent} fillOpacity="0.12"
              stroke={accent} strokeWidth="0.6" strokeOpacity="0.4" />
            <text x={54 + r.w / 2} y={y + 8} textAnchor="middle" fill={accent} fillOpacity="0.6"
              fontSize="6" fontFamily="monospace">***</text>
          </g>
        );
      })}
    </svg>
  );
}

/* ------------------------------------------------------------------ */
/*  Bloom Filter bit-array mini SVG                                    */
/* ------------------------------------------------------------------ */
function BloomMiniSVG({ accent }: { accent: string }) {
  const highlighted = [3, 7, 11, 18, 22, 29];
  const cols = 8;
  const rows = 4;
  return (
    <svg viewBox="0 0 120 72" className="w-full h-auto" style={{ maxHeight: 72 }}>
      {Array.from({ length: rows * cols }, (_, idx) => {
        const r = Math.floor(idx / cols);
        const c = idx % cols;
        const x = 8 + c * 14;
        const y = 4 + r * 17;
        const isHit = highlighted.includes(idx);
        return (
          <rect key={idx} x={x} y={y} width="10" height="14" rx="2"
            fill={isHit ? accent : "#1a2035"}
            fillOpacity={isHit ? 0.45 : 1}
            stroke={isHit ? accent : "#64748b"}
            strokeWidth={isHit ? 1.2 : 0.5}
            strokeOpacity={isHit ? 0.8 : 0.3}
            style={isHit ? { "--glow": accent, animation: `zkp-node-glow 2s ease-in-out infinite ${idx * 0.2}s` } as React.CSSProperties : undefined}
          />
        );
      })}
      <text x="60" y="70" textAnchor="middle" fill="#64748b" fontSize="6" fontFamily="monospace">
        256-bit array
      </text>
    </svg>
  );
}

/* ------------------------------------------------------------------ */
/*  Metadata Validation SVG                                            */
/* ------------------------------------------------------------------ */
function MetadataSVG({ accent }: { accent: string }) {
  const items = ["File Size", "MIME Type", "Timestamp", "Checksum"];
  return (
    <svg viewBox="0 0 120 72" className="w-full h-auto" style={{ maxHeight: 72 }}>
      {items.map((item, i) => {
        const y = 6 + i * 16;
        return (
          <g key={item}>
            <circle cx="16" cy={y + 7} r="5" fill={accent} fillOpacity="0.15" stroke={accent}
              strokeWidth="1" strokeOpacity="0.4" />
            <polyline points={`13,${y + 7} 15,${y + 9.5} 19.5,${y + 4.5}`}
              fill="none" stroke={accent} strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round"
              strokeDasharray="10" strokeDashoffset="10"
              style={{ animation: `zkp-verify-line 0.6s ease-out ${0.3 + i * 0.2}s forwards` }} />
            <text x="28" y={y + 10} fill="#94a3b8" fontSize="7.5" fontFamily="monospace">{item}</text>
            <rect x="78" y={y + 1.5} width="34" height="10" rx="3" fill={accent} fillOpacity="0.08"
              stroke={accent} strokeWidth="0.5" strokeOpacity="0.3" />
            <text x="95" y={y + 9} textAnchor="middle" fill={accent} fillOpacity="0.55"
              fontSize="6" fontFamily="monospace">valid</text>
          </g>
        );
      })}
    </svg>
  );
}

/* ------------------------------------------------------------------ */
/*  Proof Card                                                         */
/* ------------------------------------------------------------------ */
function ProofCard({ proof, isHovered, onHover, onLeave }: {
  proof: typeof PROOF_TYPES[number];
  isHovered: boolean;
  onHover: () => void;
  onLeave: () => void;
}) {
  const Icon = proof.icon;
  const svgMap: Record<string, JSX.Element> = {
    merkle: <MerkleTreeSVG accent={proof.accent} />,
    schema: <SchemaSVG accent={proof.accent} />,
    bloom: <BloomMiniSVG accent={proof.accent} />,
    metadata: <MetadataSVG accent={proof.accent} />,
  };

  return (
    <div
      onMouseEnter={onHover}
      onMouseLeave={onLeave}
      className="relative rounded-2xl border p-5 transition-all duration-300 cursor-default"
      style={{
        background: "#141928",
        borderColor: isHovered
          ? `rgba(${proof.accentRgb}, 0.45)`
          : "rgba(255,255,255,0.06)",
        boxShadow: isHovered
          ? `0 0 24px rgba(${proof.accentRgb}, 0.15), inset 0 1px 0 rgba(${proof.accentRgb}, 0.1)`
          : "none",
      }}
    >
      {/* header */}
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2.5">
          <div
            className="flex h-9 w-9 items-center justify-center rounded-full"
            style={{
              background: `rgba(${proof.accentRgb}, 0.15)`,
              boxShadow: `0 0 12px rgba(${proof.accentRgb}, 0.2)`,
            }}
          >
            <Icon className="h-4.5 w-4.5" style={{ color: proof.accent, width: 18, height: 18 }} />
          </div>
          <h3 className="text-sm font-bold" style={{ color: "#e2e8f0" }}>
            {proof.title}
          </h3>
        </div>

        {/* lock / unlock icon */}
        <div className="relative h-5 w-5" style={{ color: proof.accent }}>
          {isHovered ? (
            <Unlock className="h-5 w-5" style={{ animation: "zkp-unlock 0.4s ease-out" }} />
          ) : (
            <Lock className="h-5 w-5 opacity-50" />
          )}
        </div>
      </div>

      {/* description */}
      <p className="text-xs leading-relaxed mb-3" style={{ color: "#94a3b8" }}>
        {proof.desc}
      </p>

      {/* visual */}
      <div className="rounded-xl p-2 mb-3" style={{ background: "#0a0e1a" }}>
        {svgMap[proof.id]}
      </div>

      {/* verification status */}
      <div className="flex items-center gap-1.5">
        <CheckCircle2
          className="h-3.5 w-3.5"
          style={{
            color: proof.accent,
            animation: isHovered ? "zkp-check-pop 0.4s ease-out" : "none",
          }}
        />
        <span className="text-[11px] font-medium" style={{ color: proof.accent }}>
          Verified
        </span>
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  Center Hub SVG                                                     */
/* ------------------------------------------------------------------ */
function CenterHub() {
  return (
    <div className="flex items-center justify-center py-3">
      <div className="relative">
        <svg viewBox="0 0 200 200" width="180" height="180">
          {/* rotating outer ring */}
          <circle cx="100" cy="100" r="72" fill="none" stroke="#60a5fa" strokeWidth="1"
            strokeOpacity="0.2" strokeDasharray="6 8"
            style={{ transformOrigin: "100px 100px", animation: "zkp-spin-hub 20s linear infinite" }} />

          {/* connecting lines to 4 corners with animated dashes */}
          {[
            { x2: 20, y2: 20 },   // top-left = merkle (blue)
            { x2: 180, y2: 20 },  // top-right = schema (purple)
            { x2: 20, y2: 180 },  // bottom-left = bloom (green)
            { x2: 180, y2: 180 }, // bottom-right = metadata (amber)
          ].map((pt, i) => {
            const colors = ["#60a5fa", "#a78bfa", "#34d399", "#fbbf24"];
            return (
              <line key={i} x1="100" y1="100" x2={pt.x2} y2={pt.y2}
                stroke={colors[i]} strokeWidth="1.5" strokeOpacity="0.35"
                strokeDasharray="4 6"
                style={{ animation: `zkp-dash-flow 2s linear infinite ${i * 0.5}s` }} />
            );
          })}

          {/* inner glow circle */}
          <circle cx="100" cy="100" r="36" fill="url(#hubGrad)" stroke="#60a5fa"
            strokeWidth="1.5" strokeOpacity="0.35" />

          {/* pulse ring */}
          <circle cx="100" cy="100" r="44" fill="none" stroke="#60a5fa"
            strokeWidth="1" strokeOpacity="0.2"
            style={{ transformOrigin: "100px 100px", animation: "zkp-pulse-ring 3s ease-in-out infinite" }} />

          {/* shield icon in center */}
          <ShieldCheck x="86" y="86" width="28" height="28" style={{ color: "#60a5fa" }} />
          <text x="100" y="130" textAnchor="middle" fill="#e2e8f0" fontSize="9" fontWeight="700"
            fontFamily="system-ui, sans-serif">
            Verification
          </text>
          <text x="100" y="142" textAnchor="middle" fill="#94a3b8" fontSize="8"
            fontFamily="system-ui, sans-serif">
            Engine
          </text>

          {/* gradient def */}
          <defs>
            <radialGradient id="hubGrad" cx="50%" cy="50%" r="50%">
              <stop offset="0%" stopColor="#60a5fa" stopOpacity="0.12" />
              <stop offset="100%" stopColor="#0a0e1a" stopOpacity="0" />
            </radialGradient>
          </defs>
        </svg>
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  Main Component                                                     */
/* ------------------------------------------------------------------ */
export default function ZKPVerificationViz() {
  const [word, setWord] = useState("");
  const [hoveredProof, setHoveredProof] = useState<string | null>(null);
  const [stylesInjected, setStylesInjected] = useState(false);
  const bits = word ? getBloomBits(word) : [];

  // inject keyframes once
  useEffect(() => {
    if (stylesInjected) return;
    const id = "zkp-viz-styles";
    if (!document.getElementById(id)) {
      const tag = document.createElement("style");
      tag.id = id;
      tag.textContent = zkpStyles;
      document.head.appendChild(tag);
    }
    setStylesInjected(true);
  }, [stylesInjected]);

  return (
    <div className="space-y-6">
      {/* Verification Engine Hub */}
      <div
        className="rounded-2xl border"
        style={{
          background: "linear-gradient(135deg, #0a0e1a 0%, #141928 100%)",
          borderColor: "rgba(255,255,255,0.06)",
        }}
      >
        <CenterHub />
      </div>

      {/* Proof Types Grid */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        {PROOF_TYPES.map((p) => (
          <ProofCard
            key={p.id}
            proof={p}
            isHovered={hoveredProof === p.id}
            onHover={() => setHoveredProof(p.id)}
            onLeave={() => setHoveredProof(null)}
          />
        ))}
      </div>

      {/* Interactive Bloom Filter Demo */}
      <div
        className="rounded-2xl border p-5"
        style={{ background: "#141928", borderColor: "rgba(255,255,255,0.06)" }}
      >
        <h3 className="text-sm font-bold mb-1" style={{ color: "#e2e8f0" }}>
          Interactive Bloom Filter Demo
        </h3>
        <p className="text-xs mb-3" style={{ color: "#64748b" }}>
          Type a word to see which bits would be set in a 256-bit bloom filter with 3 hash functions.
        </p>
        <input
          type="text"
          value={word}
          onChange={(e) => setWord(e.target.value)}
          placeholder="Type a keyword..."
          className="w-full max-w-xs rounded-lg px-3 py-1.5 text-sm mb-4 focus:outline-none transition-colors"
          style={{
            background: "rgba(10,14,26,0.8)",
            border: "1px solid rgba(255,255,255,0.08)",
            color: "#e2e8f0",
          }}
          onFocus={(e) => {
            e.currentTarget.style.borderColor = "rgba(52,211,153,0.4)";
          }}
          onBlur={(e) => {
            e.currentTarget.style.borderColor = "rgba(255,255,255,0.08)";
          }}
        />
        <div className="flex flex-wrap gap-[2px]">
          {Array.from({ length: 256 }, (_, i) => (
            <div
              key={i}
              className="rounded-sm transition-all duration-300"
              style={{
                width: 10,
                height: 10,
                background: bits.includes(i) ? "#34d399" : "#1a2035",
                boxShadow: bits.includes(i) ? "0 0 6px rgba(52,211,153,0.5)" : "none",
              }}
            />
          ))}
        </div>
        {word && (
          <p className="text-xs mt-3" style={{ color: "#64748b" }}>
            Bits set: <span style={{ color: "#34d399" }}>{bits.join(", ")}</span> &mdash;{" "}
            {bits.length} of 256 bits active
          </p>
        )}
      </div>

      {/* Verification Pipeline */}
      <div
        className="rounded-2xl border p-5"
        style={{ background: "#141928", borderColor: "rgba(255,255,255,0.06)" }}
      >
        <h3 className="text-sm font-bold mb-4" style={{ color: "#e2e8f0" }}>
          Verification Pipeline
        </h3>
        <div className="flex items-center gap-2 overflow-x-auto pb-2">
          {[
            { step: "Query", color: "#60a5fa" },
            { step: "Bloom Check", color: "#34d399" },
            { step: "Schema Check", color: "#a78bfa" },
            { step: "Size Check", color: "#fbbf24" },
            { step: "Quality Check", color: "#fbbf24" },
            { step: "Verified", color: "#00ff88" },
          ].map((s, i, arr) => (
            <div key={s.step} className="flex items-center gap-2 shrink-0">
              <div
                className="rounded-lg px-3 py-1.5 text-xs font-medium transition-all duration-200"
                style={{
                  background:
                    i === arr.length - 1
                      ? "rgba(0,255,136,0.1)"
                      : "rgba(255,255,255,0.03)",
                  color: i === arr.length - 1 ? "#00ff88" : "#e2e8f0",
                  border:
                    i === arr.length - 1
                      ? "1px solid rgba(0,255,136,0.3)"
                      : "1px solid rgba(255,255,255,0.06)",
                  boxShadow:
                    i === arr.length - 1
                      ? "0 0 12px rgba(0,255,136,0.15)"
                      : "none",
                }}
              >
                {s.step}
              </div>
              {i < arr.length - 1 && (
                <svg width="20" height="12" viewBox="0 0 20 12">
                  <line x1="0" y1="6" x2="14" y2="6" stroke={s.color} strokeWidth="1.5"
                    strokeOpacity="0.4" strokeDasharray="3 2"
                    style={{ animation: "zkp-dash-flow 1.5s linear infinite" }} />
                  <polygon points="14,3 20,6 14,9" fill={s.color} fillOpacity="0.5" />
                </svg>
              )}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
