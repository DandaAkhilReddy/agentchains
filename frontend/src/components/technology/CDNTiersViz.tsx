import { Database, Zap, HardDrive, ArrowDown, ArrowUp } from "lucide-react";
import { useCDNStats } from "../../hooks/useSystemMetrics";
import StatCard from "../StatCard";

export default function CDNTiersViz() {
  const { data: stats } = useCDNStats();

  const tiers = [
    {
      label: "Hot Tier",
      icon: Zap,
      desc: "In-memory LFU cache",
      latency: "<0.1ms",
      color: "text-danger",
      bg: "bg-danger/5 border-danger/20",
      hitRate: stats?.hot_cache?.hit_rate ?? 0,
    },
    {
      label: "Warm Tier",
      icon: Database,
      desc: "TTL-based content cache",
      latency: "~0.5ms",
      color: "text-warning",
      bg: "bg-warning/5 border-warning/20",
      hitRate: stats?.warm_cache?.hit_rate ?? 0,
    },
    {
      label: "Cold Tier",
      icon: HardDrive,
      desc: "HashFS disk storage",
      latency: "1-5ms",
      color: "text-primary",
      bg: "bg-primary/5 border-primary/20",
      hitRate: 1,
    },
  ];

  return (
    <div className="space-y-6">
      {/* Tier Diagram */}
      <div className="space-y-3">
        {tiers.map((tier, i) => {
          const Icon = tier.icon;
          return (
            <div key={tier.label}>
              <div className={`glass-card border ${tier.bg} p-4 rounded-xl`}>
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <Icon className={`h-5 w-5 ${tier.color}`} />
                    <div>
                      <h3 className="text-sm font-semibold text-text-primary">
                        {tier.label}
                      </h3>
                      <p className="text-xs text-text-muted">{tier.desc}</p>
                    </div>
                  </div>
                  <div className="text-right">
                    <p className={`text-lg font-bold font-mono ${tier.color}`}>
                      {tier.latency}
                    </p>
                    <p className="text-xs text-text-muted">
                      Hit rate: {(tier.hitRate * 100).toFixed(0)}%
                    </p>
                  </div>
                </div>
              </div>
              {i < tiers.length - 1 && (
                <div className="flex items-center justify-center gap-6 py-1 text-text-muted">
                  <span className="flex items-center gap-1 text-[10px]">
                    <ArrowDown className="h-3 w-3" /> miss
                  </span>
                  <span className="flex items-center gap-1 text-[10px]">
                    <ArrowUp className="h-3 w-3 text-success" /> promote
                  </span>
                </div>
              )}
            </div>
          );
        })}
      </div>

      {/* Stats */}
      <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
        <StatCard
          label="Hot Hit Rate"
          value={`${((stats?.hot_cache?.hit_rate ?? 0) * 100).toFixed(0)}%`}
          icon={Zap}
        />
        <StatCard
          label="Warm Hit Rate"
          value={`${((stats?.warm_cache?.hit_rate ?? 0) * 100).toFixed(0)}%`}
          icon={Database}
        />
        <StatCard
          label="Total Requests"
          value={(stats?.overview?.total_requests ?? 0).toLocaleString()}
          icon={HardDrive}
        />
        <StatCard
          label="Hot Utilization"
          value={`${((stats?.hot_cache?.utilization_pct ?? 0) * 100).toFixed(0)}%`}
          icon={Zap}
        />
      </div>
    </div>
  );
}
