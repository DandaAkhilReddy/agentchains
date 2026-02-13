import {
  CreditCard,
  ArrowDown,
  Users,
  DollarSign,
} from "lucide-react";
import StatCard from "../StatCard";

const FLOW_STEPS = [
  { icon: CreditCard, label: "Deposit", sub: "Add USD to balance" },
  { icon: ArrowDown, label: "Purchase", sub: "Buy agent data" },
  { icon: Users, label: "Seller +98%", sub: "Seller gets 98%" },
  { icon: DollarSign, label: "Fee 2%", sub: "Platform fee" },
];

export default function TokenEconomyViz() {
  return (
    <div className="space-y-6">
      {/* Payment Flow */}
      <div className="glass-card p-5">
        <h3 className="text-sm font-semibold text-text-primary mb-4">
          How Billing Works
        </h3>
        <div className="flex flex-col items-center gap-3 sm:flex-row sm:justify-center sm:gap-4">
          {FLOW_STEPS.map((step, i) => (
            <div key={step.label} className="flex items-center gap-3">
              <div className="text-center">
                <div className="mx-auto flex h-10 w-10 items-center justify-center rounded-xl bg-primary-glow mb-1">
                  <step.icon className="h-5 w-5 text-primary" />
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

      {/* Pricing Overview */}
      <div className="glass-card p-5">
        <h3 className="text-sm font-semibold text-text-primary mb-4">
          Pricing
        </h3>
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          {[
            { label: "Platform Fee", value: "2%" },
            { label: "Creator Royalty", value: "Auto-paid" },
            { label: "Min Deposit", value: "$1.00" },
            { label: "Welcome Credit", value: "$0.10" },
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
