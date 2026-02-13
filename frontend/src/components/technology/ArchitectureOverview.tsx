import { useMemo, useCallback, useRef, useEffect, useState } from "react";
import {
  Cpu,
  Route,
  Search,
  Database,
  Zap,
  DollarSign,
  TrendingUp,
  Shield,
  Globe,
  Code2,
  Wifi,
  Terminal,
  Server,
  Brain,
  BarChart3,
  HardDrive,
  type LucideIcon,
} from "lucide-react";
import { useSystemMetrics } from "../../hooks/useSystemMetrics";
import StatCard from "../StatCard";

/* ------------------------------------------------------------------ */
/* Types                                                               */
/* ------------------------------------------------------------------ */

interface ArchNode {
  id: string;
  label: string;
  desc: string;
  icon: LucideIcon;
  layer: 0 | 1 | 2 | 3;
}

interface ArchConnection {
  from: string;
  to: string;
}

interface Props {
  onNavigate: (tab: string) => void;
}

/* ------------------------------------------------------------------ */
/* Layer colours                                                       */
/* ------------------------------------------------------------------ */

const LAYER_COLORS: Record<number, string> = {
  0: "#a78bfa", // purple  - clients
  1: "#60a5fa", // blue    - core
  2: "#fbbf24", // amber   - intelligence
  3: "#34d399", // green   - data
};

const LAYER_LABELS = ["Clients", "Core Platform", "Intelligence", "Data Layer"];

/* ------------------------------------------------------------------ */
/* TAB_MAP: which nodes map to which tab                               */
/* ------------------------------------------------------------------ */

const TAB_MAP: Record<string, string> = {
  "core-gateway": "router",
  "core-router": "router",
  "core-zkp": "zkp",
  "core-cdn": "cdn",
  "core-billing": "tokens",
  "intel-demand": "overview",
  "intel-price": "overview",
  "intel-rep": "overview",
  "client-openclaw": "overview",
  "client-mcp": "overview",
  "client-rest": "overview",
  "client-ws": "overview",
  "data-pg": "overview",
  "data-hashfs": "overview",
};

/* ------------------------------------------------------------------ */
/* Nodes                                                               */
/* ------------------------------------------------------------------ */

const NODES: ArchNode[] = [
  // Layer 0 - Clients
  { id: "client-openclaw", label: "OpenClaw", desc: "No Code", icon: Code2, layer: 0 },
  { id: "client-mcp", label: "MCP Protocol", desc: "Claude", icon: Brain, layer: 0 },
  { id: "client-rest", label: "REST API", desc: "HTTP/JSON", icon: Terminal, layer: 0 },
  { id: "client-ws", label: "WebSocket", desc: "Real-time", icon: Wifi, layer: 0 },

  // Layer 1 - Core
  { id: "core-gateway", label: "FastAPI Gateway", desc: "82 endpoints", icon: Server, layer: 1 },
  { id: "core-router", label: "Smart Router", desc: "7 strategies", icon: Route, layer: 1 },
  { id: "core-zkp", label: "ZKP Verifier", desc: "4 proofs", icon: Shield, layer: 1 },
  { id: "core-cdn", label: "3-Tier CDN", desc: "Cache layers", icon: Globe, layer: 1 },
  { id: "core-billing", label: "Billing Engine", desc: "USD", icon: DollarSign, layer: 1 },

  // Layer 2 - Intelligence
  { id: "intel-demand", label: "Demand Signals", desc: "Analytics", icon: TrendingUp, layer: 2 },
  { id: "intel-price", label: "Price Oracle", desc: "Dynamic", icon: BarChart3, layer: 2 },
  { id: "intel-rep", label: "Reputation Engine", desc: "Trust scores", icon: Search, layer: 2 },

  // Layer 3 - Data
  { id: "data-pg", label: "PostgreSQL", desc: "Primary store", icon: Database, layer: 3 },
  { id: "data-hashfs", label: "Content Store", desc: "HashFS", icon: HardDrive, layer: 3 },
];

/* ------------------------------------------------------------------ */
/* Connections (cross-layer flows)                                     */
/* ------------------------------------------------------------------ */

const CONNECTIONS: ArchConnection[] = [
  // Clients -> Core
  { from: "client-openclaw", to: "core-gateway" },
  { from: "client-mcp", to: "core-gateway" },
  { from: "client-rest", to: "core-gateway" },
  { from: "client-ws", to: "core-gateway" },
  // Core internal
  { from: "core-gateway", to: "core-router" },
  { from: "core-router", to: "core-zkp" },
  { from: "core-router", to: "core-cdn" },
  { from: "core-router", to: "core-billing" },
  // Core -> Intelligence
  { from: "core-router", to: "intel-demand" },
  { from: "core-billing", to: "intel-price" },
  { from: "core-zkp", to: "intel-rep" },
  // Intelligence -> Data
  { from: "intel-demand", to: "data-pg" },
  { from: "intel-price", to: "data-pg" },
  { from: "intel-rep", to: "data-pg" },
  // Core -> Data
  { from: "core-cdn", to: "data-hashfs" },
];

/* ------------------------------------------------------------------ */
/* Keyframe CSS (injected once)                                        */
/* ------------------------------------------------------------------ */

const STYLE_ID = "arch-overview-keyframes";

function ensureKeyframes() {
  if (typeof document === "undefined") return;
  if (document.getElementById(STYLE_ID)) return;
  const style = document.createElement("style");
  style.id = STYLE_ID;
  style.textContent = `
    @keyframes archFlowDash {
      to { stroke-dashoffset: -24; }
    }
    @keyframes archFlowDot {
      0% { offset-distance: 0%; opacity: 0; }
      10% { opacity: 1; }
      90% { opacity: 1; }
      100% { offset-distance: 100%; opacity: 0; }
    }
    @keyframes archNodeEnter {
      from { opacity: 0; transform: translateY(12px) scale(0.95); }
      to { opacity: 1; transform: translateY(0) scale(1); }
    }
    @keyframes archPulseGlow {
      0%, 100% { opacity: 0.5; }
      50% { opacity: 1; }
    }
  `;
  document.head.appendChild(style);
}

/* ------------------------------------------------------------------ */
/* Helper: group nodes by layer                                        */
/* ------------------------------------------------------------------ */

function groupByLayer(nodes: ArchNode[]): ArchNode[][] {
  const layers: ArchNode[][] = [[], [], [], []];
  for (const n of nodes) layers[n.layer].push(n);
  return layers;
}

/* ------------------------------------------------------------------ */
/* Node card component                                                 */
/* ------------------------------------------------------------------ */

function NodeCard({
  node,
  onClick,
  delay,
}: {
  node: ArchNode;
  onClick: () => void;
  delay: number;
}) {
  const color = LAYER_COLORS[node.layer];
  const Icon = node.icon;

  return (
    <button
      type="button"
      onClick={onClick}
      className="group relative flex items-center gap-3 rounded-xl border px-4 py-3 text-left transition-all duration-300 hover:scale-[1.03] active:scale-[0.98] cursor-pointer"
      style={{
        background: "#141928",
        borderColor: "rgba(255,255,255,0.06)",
        animation: `archNodeEnter 0.5s ease-out ${delay}ms both`,
      }}
      onMouseEnter={(e) => {
        const el = e.currentTarget as HTMLElement;
        el.style.borderColor = `${color}50`;
        el.style.boxShadow = `0 0 24px ${color}20, inset 0 1px 0 ${color}15`;
      }}
      onMouseLeave={(e) => {
        const el = e.currentTarget as HTMLElement;
        el.style.borderColor = "rgba(255,255,255,0.06)";
        el.style.boxShadow = "none";
      }}
    >
      {/* Icon circle */}
      <div
        className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full transition-shadow duration-300"
        style={{
          backgroundColor: `${color}20`,
          boxShadow: `0 0 10px ${color}15`,
        }}
      >
        <Icon className="h-4 w-4" style={{ color }} />
      </div>
      {/* Text */}
      <div className="min-w-0">
        <p className="text-sm font-semibold text-[#e2e8f0] truncate">{node.label}</p>
        <p className="text-xs text-[#64748b] truncate">{node.desc}</p>
      </div>
    </button>
  );
}

/* ------------------------------------------------------------------ */
/* SVG connections with animated dashes + flowing dots                  */
/* ------------------------------------------------------------------ */

interface NodeRect {
  id: string;
  x: number;
  y: number;
  w: number;
  h: number;
  layer: number;
}

function ConnectionsSVG({
  nodeRects,
  connections,
  containerRect,
}: {
  nodeRects: NodeRect[];
  connections: ArchConnection[];
  containerRect: DOMRect | null;
}) {
  if (!containerRect || nodeRects.length === 0) return null;

  const rectMap = new Map<string, NodeRect>();
  for (const r of nodeRects) rectMap.set(r.id, r);

  // Compute relative coordinates inside the SVG
  const toSVG = (rect: NodeRect, side: "right" | "left") => {
    const cx = side === "right" ? rect.x + rect.w : rect.x;
    const cy = rect.y + rect.h / 2;
    return { x: cx - containerRect.left, y: cy - containerRect.top };
  };

  const paths: { d: string; key: string; color: string }[] = [];
  for (const conn of connections) {
    const fromR = rectMap.get(conn.from);
    const toR = rectMap.get(conn.to);
    if (!fromR || !toR) continue;

    // Determine exit/entry side based on layer order
    const fromSide = fromR.layer <= toR.layer ? "right" : "left";
    const toSide = fromR.layer <= toR.layer ? "left" : "right";
    const p1 = toSVG(fromR, fromSide);
    const p2 = toSVG(toR, toSide);

    // Cubic bezier with horizontal control points for smooth curves
    const dx = Math.abs(p2.x - p1.x);
    const cpOff = Math.max(dx * 0.4, 30);
    const cp1x = p1.x + (fromSide === "right" ? cpOff : -cpOff);
    const cp2x = p2.x + (toSide === "left" ? -cpOff : cpOff);

    const d = `M ${p1.x} ${p1.y} C ${cp1x} ${p1.y} ${cp2x} ${p2.y} ${p2.x} ${p2.y}`;
    const color = LAYER_COLORS[fromR.layer] || "#60a5fa";
    paths.push({ d, key: `${conn.from}-${conn.to}`, color });
  }

  return (
    <svg
      className="pointer-events-none absolute inset-0"
      width={containerRect.width}
      height={containerRect.height}
      style={{ overflow: "visible" }}
    >
      <defs>
        {/* Animated dash pattern */}
        {paths.map((p) => (
          <linearGradient key={`grad-${p.key}`} id={`grad-${p.key}`} x1="0%" y1="0%" x2="100%" y2="0%">
            <stop offset="0%" stopColor={p.color} stopOpacity={0.6} />
            <stop offset="100%" stopColor={p.color} stopOpacity={0.15} />
          </linearGradient>
        ))}
      </defs>
      {paths.map((p, i) => (
        <g key={p.key}>
          {/* Background glow line */}
          <path
            d={p.d}
            stroke={p.color}
            strokeWidth={3}
            fill="none"
            opacity={0.06}
            strokeLinecap="round"
          />
          {/* Animated dashed line */}
          <path
            d={p.d}
            stroke={`url(#grad-${p.key})`}
            strokeWidth={1.5}
            fill="none"
            strokeLinecap="round"
            strokeDasharray="6 6"
            style={{
              animation: `archFlowDash ${2 + (i % 3) * 0.5}s linear infinite`,
            }}
          />
          {/* Flowing dot */}
          <circle
            r={3}
            fill={p.color}
            opacity={0.9}
            style={{
              offsetPath: `path('${p.d}')`,
              animation: `archFlowDot ${3 + (i % 4) * 0.7}s ease-in-out ${i * 0.3}s infinite`,
              filter: `drop-shadow(0 0 4px ${p.color})`,
            } as React.CSSProperties}
          />
        </g>
      ))}
    </svg>
  );
}

/* ------------------------------------------------------------------ */
/* Main component                                                      */
/* ------------------------------------------------------------------ */

export default function ArchitectureOverview({ onNavigate }: Props) {
  const { data } = useSystemMetrics();
  const containerRef = useRef<HTMLDivElement>(null);
  const nodeRefsMap = useRef<Map<string, HTMLElement>>(new Map());
  const [nodeRects, setNodeRects] = useState<NodeRect[]>([]);
  const [containerRect, setContainerRect] = useState<DOMRect | null>(null);

  const layers = useMemo(() => groupByLayer(NODES), []);

  // Inject keyframes on mount
  useEffect(() => { ensureKeyframes(); }, []);

  // Measure node positions for SVG connections
  const measureNodes = useCallback(() => {
    if (!containerRef.current) return;
    const cRect = containerRef.current.getBoundingClientRect();
    setContainerRect(cRect);

    const rects: NodeRect[] = [];
    nodeRefsMap.current.forEach((el, id) => {
      const r = el.getBoundingClientRect();
      const node = NODES.find((n) => n.id === id);
      rects.push({ id, x: r.left, y: r.top, w: r.width, h: r.height, layer: node?.layer ?? 0 });
    });
    setNodeRects(rects);
  }, []);

  useEffect(() => {
    // Measure after initial render + stagger animations
    const timer = setTimeout(measureNodes, 600);
    window.addEventListener("resize", measureNodes);
    return () => {
      clearTimeout(timer);
      window.removeEventListener("resize", measureNodes);
    };
  }, [measureNodes]);

  const registerNodeRef = useCallback((id: string, el: HTMLElement | null) => {
    if (el) nodeRefsMap.current.set(id, el);
    else nodeRefsMap.current.delete(id);
  }, []);

  const handleNodeClick = useCallback(
    (id: string) => {
      const tab = TAB_MAP[id];
      if (tab) onNavigate(tab);
    },
    [onNavigate],
  );

  return (
    <div className="space-y-6">
      {/* ---- Architecture Diagram ---- */}
      <div
        className="relative rounded-2xl border p-6 overflow-hidden"
        style={{
          background: "linear-gradient(135deg, #0a0e1a 0%, #141928 50%, #0a0e1a 100%)",
          borderColor: "rgba(255,255,255,0.06)",
        }}
      >
        {/* Section title */}
        <div className="mb-6 flex items-center gap-3">
          <div
            className="flex h-8 w-8 items-center justify-center rounded-lg"
            style={{ backgroundColor: "rgba(96,165,250,0.12)" }}
          >
            <Cpu className="h-4 w-4 text-[#60a5fa]" />
          </div>
          <div>
            <h2 className="text-sm font-bold tracking-tight text-[#e2e8f0]">
              System Architecture
            </h2>
            <p className="text-xs text-[#64748b]">Click any node to explore its subsystem</p>
          </div>
        </div>

        {/* Background grid pattern */}
        <div
          className="pointer-events-none absolute inset-0 opacity-[0.03]"
          style={{
            backgroundImage:
              "linear-gradient(rgba(255,255,255,0.1) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,0.1) 1px, transparent 1px)",
            backgroundSize: "40px 40px",
          }}
        />

        {/* 4-layer diagram */}
        <div ref={containerRef} className="relative">
          {/* SVG connection lines */}
          <ConnectionsSVG
            nodeRects={nodeRects}
            connections={CONNECTIONS}
            containerRect={containerRect}
          />

          {/* Horizontal layout: 4 columns on desktop, stacked on mobile */}
          <div className="grid grid-cols-1 gap-4 md:grid-cols-4 relative z-10">
            {layers.map((layerNodes, layerIdx) => (
              <div key={layerIdx} className="flex flex-col gap-2">
                {/* Layer header */}
                <div className="flex items-center gap-2 mb-2 px-1">
                  <div
                    className="h-2 w-2 rounded-full"
                    style={{
                      backgroundColor: LAYER_COLORS[layerIdx],
                      boxShadow: `0 0 8px ${LAYER_COLORS[layerIdx]}60`,
                      animation: "archPulseGlow 3s ease-in-out infinite",
                    }}
                  />
                  <span
                    className="text-[10px] font-bold uppercase tracking-[0.15em]"
                    style={{ color: LAYER_COLORS[layerIdx] }}
                  >
                    {LAYER_LABELS[layerIdx]}
                  </span>
                </div>

                {/* Node cards in this layer */}
                <div className="flex flex-col gap-2">
                  {layerNodes.map((node, nodeIdx) => (
                    <div
                      key={node.id}
                      ref={(el) => registerNodeRef(node.id, el)}
                    >
                      <NodeCard
                        node={node}
                        onClick={() => handleNodeClick(node.id)}
                        delay={layerIdx * 120 + nodeIdx * 60}
                      />
                    </div>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Bottom legend */}
        <div className="mt-6 flex flex-wrap items-center justify-center gap-4 border-t border-[rgba(255,255,255,0.04)] pt-4">
          {LAYER_LABELS.map((label, i) => (
            <div key={label} className="flex items-center gap-1.5">
              <div
                className="h-1.5 w-6 rounded-full"
                style={{
                  background: `linear-gradient(90deg, ${LAYER_COLORS[i]}80, ${LAYER_COLORS[i]}20)`,
                }}
              />
              <span className="text-[10px] font-medium text-[#64748b]">{label}</span>
            </div>
          ))}
          <div className="flex items-center gap-1.5">
            <svg width="20" height="8" className="shrink-0">
              <line
                x1="0" y1="4" x2="20" y2="4"
                stroke="#60a5fa"
                strokeWidth="1.5"
                strokeDasharray="3 3"
                opacity={0.5}
              />
            </svg>
            <span className="text-[10px] font-medium text-[#64748b]">Data flow</span>
          </div>
        </div>
      </div>

      {/* ---- Live Stats ---- */}
      <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
        <StatCard
          label="Agents"
          value={data?.health.agents_count ?? 0}
          icon={Cpu}
        />
        <StatCard
          label="Listings"
          value={data?.health.listings_count ?? 0}
          icon={Database}
        />
        <StatCard
          label="CDN Hit Rate"
          value={`${((() => { const o = data?.cdn.overview; if (!o || !o.total_requests) return 0; return ((o.tier1_hits + o.tier2_hits + o.tier3_hits) / o.total_requests) * 100; })()).toFixed(0)}%`}
          icon={Zap}
        />
        <StatCard
          label="Revenue"
          value={data?.health.transactions_count ?? 0}
          icon={DollarSign}
        />
      </div>

      {/* ---- Competitive Moat Cards ---- */}
      <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
        {[
          {
            icon: Route,
            title: "7 Routing Strategies",
            desc: "From cheapest to locality-aware -- more strategies than any competitor. Each uses multi-dimensional scoring with tuned weights.",
            accent: "#60a5fa",
          },
          {
            icon: Shield,
            title: "Cryptographic Verification",
            desc: "Zero-knowledge proofs let buyers verify content quality before purchase -- Merkle trees, bloom filters, schema proofs.",
            accent: "#a78bfa",
          },
          {
            icon: DollarSign,
            title: "USD Billing",
            desc: "Simple USD billing. Deposit funds, purchase agent outputs. 2% platform fee, 98% goes to sellers.",
            accent: "#34d399",
          },
        ].map((card) => (
          <div
            key={card.title}
            className="group relative rounded-2xl border p-5 transition-all duration-300 hover:scale-[1.02]"
            style={{
              background: "#141928",
              borderColor: "rgba(255,255,255,0.06)",
            }}
            onMouseEnter={(e) => {
              const el = e.currentTarget as HTMLElement;
              el.style.borderColor = `${card.accent}40`;
              el.style.boxShadow = `0 0 20px ${card.accent}15`;
            }}
            onMouseLeave={(e) => {
              const el = e.currentTarget as HTMLElement;
              el.style.borderColor = "rgba(255,255,255,0.06)";
              el.style.boxShadow = "none";
            }}
          >
            {/* Accent bar at top */}
            <div
              className="absolute top-0 left-6 right-6 h-[2px] rounded-full opacity-40"
              style={{
                background: `linear-gradient(90deg, transparent, ${card.accent}, transparent)`,
              }}
            />
            <div
              className="mb-3 flex h-9 w-9 items-center justify-center rounded-lg"
              style={{ backgroundColor: `${card.accent}18` }}
            >
              <card.icon className="h-4.5 w-4.5" style={{ color: card.accent }} />
            </div>
            <h3 className="text-sm font-semibold text-[#e2e8f0] mb-1.5">
              {card.title}
            </h3>
            <p className="text-xs text-[#94a3b8] leading-relaxed">
              {card.desc}
            </p>
          </div>
        ))}
      </div>
    </div>
  );
}
