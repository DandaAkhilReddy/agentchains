import {
  Coins,
  ArrowDown,
  Users,
  CreditCard,
  TrendingUp,
} from "lucide-react";
import { useSystemMetrics } from "../../hooks/useSystemMetrics";
import StatCard from "../StatCard";

const TIERS = [
  { name: "Bronze", min: 0, color: "#92400e" },
  { name: "Silver", min: 10000, color: "#64748b" },
  { name: "Gold", min: 100000, color: "#d97706" },
  { name: "Platinum", min: 1000000, color: "#7c3aed" },
];

const FLOW_STEPS = [
  { icon: CreditCard, label: "Deposit", sub: "Buy ARD with USD" },
  { icon: ArrowDown, label: "Purchase", sub: "100 ARD" },
  { icon: Users, label: "Seller +98", sub: "98% to seller" },
  { icon: Coins, label: "Fee 2 ARD", sub: "2% platform fee" },
];

export default function TokenEconomyViz() {
  const { data } = useSystemMetrics();
  const supply = data?.tokenSupply;

  return (
    <div className="space-y-6">
      {/* Token Flow */}
      <div className="glass-card p-5">
        <h3 className="text-sm font-semibold text-text-primary mb-4">
          Token Flow
        </h3>
        <div className="flex flex-col items-center gap-3 sm:flex-row sm:justify-center sm:gap-4">
          {FLOW_STEPS.map((step, i) => (
            <div key={step.label} className="flex items-center gap-3">
              <div className="text-center">
                <div className="mx-auto flex h-10 w-10 items-center justify-center rounded-xl bg-primary-glow mb-1">
                  <step.icon
                    className="h-5 w-5 text-primary"
                  />
                </div>
                <p className="text-xs font-medium text-text-primary">
                  {step.label}
                </p>
                <p className="text-[10px] text-text-muted">{step.sub}</p>
              </div>
              {i < FLOW_STEPS.length - 1 && (
                <div className="hidden sm:block h-0.5 w-6 bg-border-subtle rounded" />
              )}
            </div>
          ))}
        </div>
      </div>

      {/* Supply Stats */}
      <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
        <StatCard
          label="Total Issued"
          value={(supply?.total_minted ?? 0).toLocaleString()}
          subtitle="ARD"
          icon={Coins}
        />
        <StatCard
          label="Fees Collected"
          value={(supply?.platform_balance ?? 0).toLocaleString()}
          subtitle="ARD"
          icon={Coins}
        />
        <StatCard
          label="Circulating"
          value={(supply?.circulating ?? 0).toLocaleString()}
          subtitle="ARD"
          icon={TrendingUp}
        />
        <StatCard
          label="Platform"
          value={(supply?.platform_balance ?? 0).toLocaleString()}
          subtitle="ARD"
          icon={CreditCard}
        />
      </div>

      {/* Tier Progression */}
      <div className="glass-card p-5">
        <h3 className="text-sm font-semibold text-text-primary mb-4">
          Volume Tiers
        </h3>
        <div className="relative">
          <div className="h-2 rounded-full bg-surface-overlay">
            <div
              className="h-full rounded-full bg-gradient-to-r from-primary via-secondary to-warning"
              style={{ width: "100%" }}
            />
          </div>
          <div className="flex justify-between mt-2">
            {TIERS.map((tier) => (
              <div key={tier.name} className="text-center">
                <div className="h-3 w-0.5 bg-border-subtle mx-auto mb-1" />
                <p className="text-xs font-bold" style={{ color: tier.color }}>
                  {tier.name}
                </p>
                <p className="text-[10px] text-text-muted">
                  {tier.min > 0 ? `${(tier.min / 1000).toFixed(0)}K` : "0"}
                </p>
              </div>
            ))}
          </div>
        </div>
        <div className="mt-4 grid grid-cols-2 gap-3 sm:grid-cols-4">
          {[
            { label: "Platform Fee", value: "2%" },
            { label: "Creator Royalty", value: "Auto-paid" },
            { label: "Peg Rate", value: "1 ARD = $0.001" },
            { label: "Signup Bonus", value: "100 ARD" },
          ].map((item) => (
            <div
              key={item.label}
              className="rounded-lg bg-surface-overlay/50 p-2 text-center"
            >
              <p className="text-[10px] text-text-muted">{item.label}</p>
              <p className="text-xs font-bold text-text-primary">
                {item.value}
              </p>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
