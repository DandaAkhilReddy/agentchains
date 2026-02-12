import { useState } from "react";
import {
  Route,
  Zap,
  Star,
  Scale,
  RefreshCw,
  Shuffle,
  MapPin,
} from "lucide-react";
import {
  RadarChart,
  PolarGrid,
  PolarAngleAxis,
  Radar,
  ResponsiveContainer,
} from "recharts";

const STRATEGIES = [
  {
    id: "cheapest",
    label: "Cheapest",
    icon: Scale,
    formula: "sort by price ASC",
    weights: { price: 1, speed: 0, quality: 0, reputation: 0, freshness: 0 },
  },
  {
    id: "fastest",
    label: "Fastest",
    icon: Zap,
    formula: "cache_hit + low latency",
    weights: { price: 0, speed: 1, quality: 0, reputation: 0, freshness: 0 },
  },
  {
    id: "highest_quality",
    label: "Highest Quality",
    icon: Star,
    formula: "0.5 x quality + 0.3 x reputation + 0.2 x freshness",
    weights: { price: 0, speed: 0, quality: 0.5, reputation: 0.3, freshness: 0.2 },
  },
  {
    id: "best_value",
    label: "Best Value",
    icon: Route,
    formula: "0.4 x (quality/price) + 0.25 x reputation + 0.2 x freshness + 0.15 x (1-price)",
    weights: { price: 0.15, speed: 0, quality: 0.4, reputation: 0.25, freshness: 0.2 },
  },
  {
    id: "round_robin",
    label: "Round Robin",
    icon: RefreshCw,
    formula: "fair rotation among sellers",
    weights: { price: 0.2, speed: 0.2, quality: 0.2, reputation: 0.2, freshness: 0.2 },
  },
  {
    id: "weighted_random",
    label: "Weighted Random",
    icon: Shuffle,
    formula: "probabilistic by reputation",
    weights: { price: 0.33, speed: 0, quality: 0.33, reputation: 0.34, freshness: 0 },
  },
  {
    id: "locality",
    label: "Locality",
    icon: MapPin,
    formula: "0.5 x proximity + 0.2 x quality + 0.3 x price",
    weights: { price: 0.3, speed: 0, quality: 0.2, reputation: 0, freshness: 0 },
  },
];

export default function SmartRouterViz() {
  const [selected, setSelected] = useState("best_value");
  const strategy = STRATEGIES.find((s) => s.id === selected)!;
  const radarData = Object.entries(strategy.weights).map(([key, val]) => ({
    dimension: key,
    value: val * 100,
  }));

  return (
    <div className="space-y-6">
      {/* Strategy Grid */}
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4">
        {STRATEGIES.map((s) => {
          const Icon = s.icon;
          const isActive = s.id === selected;
          return (
            <button
              key={s.id}
              onClick={() => setSelected(s.id)}
              className={`glass-card-subtle p-3 rounded-xl text-left transition-all ${
                isActive
                  ? "border-primary/30 shadow-[0_0_12px_rgba(59,130,246,0.08)]"
                  : "hover:border-primary/15"
              }`}
            >
              <div className="flex items-center gap-2 mb-2">
                <Icon
                  className={`h-4 w-4 ${isActive ? "text-primary" : "text-text-muted"}`}
                />
                <span
                  className={`text-xs font-semibold ${
                    isActive ? "text-primary" : "text-text-primary"
                  }`}
                >
                  {s.label}
                </span>
              </div>
              <p className="text-[10px] font-mono text-text-muted leading-relaxed">
                {s.formula}
              </p>
            </button>
          );
        })}
      </div>

      {/* Radar Chart Detail */}
      <div className="glass-card p-6">
        <h3 className="text-sm font-semibold text-text-primary mb-1">
          {strategy.label} Strategy
        </h3>
        <p className="text-xs font-mono text-text-muted mb-4">
          {strategy.formula}
        </p>
        <div className="h-64">
          <ResponsiveContainer width="100%" height="100%">
            <RadarChart data={radarData}>
              <PolarGrid stroke="#e2e8f0" />
              <PolarAngleAxis
                dataKey="dimension"
                tick={{ fill: "#94a3b8", fontSize: 11 }}
              />
              <Radar
                dataKey="value"
                fill="#3b82f6"
                fillOpacity={0.15}
                stroke="#3b82f6"
                strokeWidth={2}
              />
            </RadarChart>
          </ResponsiveContainer>
        </div>
      </div>
    </div>
  );
}
