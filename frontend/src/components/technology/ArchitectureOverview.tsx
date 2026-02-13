import {
  Cpu,
  Route,
  Search,
  Database,
  Zap,
  DollarSign,
  TrendingUp,
  Shield,
} from "lucide-react";
import { useSystemMetrics } from "../../hooks/useSystemMetrics";
import StatCard from "../StatCard";
import FlowDiagram from "./FlowDiagram";
import type { FlowNode, FlowEdge } from "./FlowDiagram";

interface Props {
  onNavigate: (tab: string) => void;
}

const TAB_MAP: Record<string, string> = {
  match: "match",
  router: "router",
  zkp: "zkp",
  cdn: "cdn",
  express: "express",
  tokens: "tokens",
  demand: "overview",
};

const NODES: FlowNode[] = [
  { id: "match", label: "Auto-Match", icon: Search, x: 15, y: 15, color: "#3b82f6" },
  { id: "router", label: "Smart Router", icon: Route, x: 50, y: 15, color: "#3b82f6" },
  { id: "zkp", label: "ZKP Verify", icon: Shield, x: 85, y: 15, color: "#8b5cf6" },
  { id: "cdn", label: "CDN Tiers", icon: Database, x: 85, y: 50, color: "#16a34a" },
  { id: "express", label: "Express", icon: Zap, x: 50, y: 85, color: "#d97706" },
  { id: "tokens", label: "Billing", icon: DollarSign, x: 15, y: 85, color: "#d97706" },
  { id: "demand", label: "Demand Intel", icon: TrendingUp, x: 15, y: 50, color: "#8b5cf6" },
];

const EDGES: FlowEdge[] = [
  { from: "match", to: "router", animated: true },
  { from: "router", to: "zkp", animated: true },
  { from: "router", to: "cdn", animated: true },
  { from: "cdn", to: "express", animated: true },
  { from: "express", to: "tokens", animated: true },
  { from: "tokens", to: "demand", animated: true },
  { from: "demand", to: "match", animated: true, label: "feedback" },
];

export default function ArchitectureOverview({ onNavigate }: Props) {
  const { data } = useSystemMetrics();

  const handleNodeClick = (id: string) => {
    const tab = TAB_MAP[id];
    if (tab) onNavigate(tab);
  };

  return (
    <div className="space-y-6">
      {/* Interactive Architecture Diagram */}
      <div className="glass-card p-6">
        <p className="text-xs font-semibold uppercase tracking-widest text-text-muted mb-4">
          System Architecture
        </p>
        <FlowDiagram
          nodes={NODES}
          edges={EDGES}
          onNodeClick={handleNodeClick}
          height={340}
        />
      </div>

      {/* Live Stats */}
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
          value={`${((data?.cdn.overview?.hit_rate ?? 0) * 100).toFixed(0)}%`}
          icon={Zap}
        />
        <StatCard
          label="Revenue"
          value={data?.health.transactions_count ?? 0}
          icon={DollarSign}
        />
      </div>

      {/* Competitive Moat Cards */}
      <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
        {[
          {
            icon: Route,
            title: "7 Routing Strategies",
            desc: "From cheapest to locality-aware -- more strategies than any competitor. Each uses multi-dimensional scoring with tuned weights.",
          },
          {
            icon: Shield,
            title: "Cryptographic Verification",
            desc: "Zero-knowledge proofs let buyers verify content quality before purchase -- Merkle trees, bloom filters, schema proofs.",
          },
          {
            icon: DollarSign,
            title: "USD Billing",
            desc: "Simple USD billing. Deposit funds, purchase agent outputs. 2% platform fee, 98% goes to sellers.",
          },
        ].map((card) => (
          <div key={card.title} className="glass-card gradient-border-card p-5">
            <card.icon className="h-5 w-5 text-primary mb-3" />
            <h3 className="text-sm font-semibold text-text-primary mb-1">
              {card.title}
            </h3>
            <p className="text-xs text-text-secondary leading-relaxed">
              {card.desc}
            </p>
          </div>
        ))}
      </div>
    </div>
  );
}
