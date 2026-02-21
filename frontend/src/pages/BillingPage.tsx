import { useState, useMemo } from "react";
import {
  CreditCard,
  Download,
  Check,
  Zap,
  Crown,
  Building2,
  TrendingUp,
  FileText,
  ChevronDown,
  ChevronUp,
  ExternalLink,
} from "lucide-react";
import PageHeader from "../components/PageHeader";

/**
 * Billing / Subscription Page.
 *
 * URL: /billing
 *
 * Shows current plan, usage meters, invoices, and plan comparison cards
 * (Free, Pro, Enterprise).
 */

/* ── Data Types ─────────────────────────────────────────────────── */

interface UsageMeter {
  label: string;
  current: number;
  limit: number;
  unit: string;
  color: string;
}

interface Invoice {
  id: string;
  date: string;
  amount: number;
  status: "paid" | "pending" | "overdue";
  downloadUrl: string;
}

interface PlanFeature {
  text: string;
  included: boolean;
}

interface Plan {
  name: string;
  price: string;
  period: string;
  description: string;
  icon: typeof Zap;
  color: string;
  bgColor: string;
  glowColor: string;
  popular?: boolean;
  features: PlanFeature[];
}

/* ── Static Data ────────────────────────────────────────────────── */

const CURRENT_PLAN = "Pro";

const USAGE_METERS: UsageMeter[] = [
  {
    label: "API Calls",
    current: 45_230,
    limit: 100_000,
    unit: "calls",
    color: "#60a5fa",
  },
  {
    label: "Agent Sessions",
    current: 127,
    limit: 500,
    unit: "sessions",
    color: "#a78bfa",
  },
  {
    label: "Data Transfer",
    current: 3.2,
    limit: 10,
    unit: "GB",
    color: "#34d399",
  },
  {
    label: "Storage",
    current: 1.8,
    limit: 5,
    unit: "GB",
    color: "#fbbf24",
  },
];

const INVOICES: Invoice[] = [
  {
    id: "INV-2026-001",
    date: "2026-02-01",
    amount: 49.0,
    status: "paid",
    downloadUrl: "#",
  },
  {
    id: "INV-2026-002",
    date: "2026-01-01",
    amount: 49.0,
    status: "paid",
    downloadUrl: "#",
  },
  {
    id: "INV-2025-012",
    date: "2025-12-01",
    amount: 49.0,
    status: "paid",
    downloadUrl: "#",
  },
  {
    id: "INV-2025-011",
    date: "2025-11-01",
    amount: 29.0,
    status: "paid",
    downloadUrl: "#",
  },
  {
    id: "INV-2025-010",
    date: "2025-10-01",
    amount: 29.0,
    status: "paid",
    downloadUrl: "#",
  },
];

const PLANS: Plan[] = [
  {
    name: "Free",
    price: "$0",
    period: "forever",
    description: "Perfect for getting started and small experiments",
    icon: Zap,
    color: "#64748b",
    bgColor: "rgba(100,116,139,0.08)",
    glowColor: "rgba(100,116,139,0.2)",
    features: [
      { text: "1,000 API calls/month", included: true },
      { text: "5 agent sessions", included: true },
      { text: "500 MB storage", included: true },
      { text: "Community support", included: true },
      { text: "Custom agents", included: false },
      { text: "Priority routing", included: false },
      { text: "Analytics dashboard", included: false },
      { text: "SLA guarantee", included: false },
    ],
  },
  {
    name: "Pro",
    price: "$49",
    period: "/month",
    description: "For professional developers and growing teams",
    icon: Crown,
    color: "#60a5fa",
    bgColor: "rgba(96,165,250,0.08)",
    glowColor: "rgba(96,165,250,0.3)",
    popular: true,
    features: [
      { text: "100,000 API calls/month", included: true },
      { text: "500 agent sessions", included: true },
      { text: "10 GB storage", included: true },
      { text: "Priority support", included: true },
      { text: "Custom agents", included: true },
      { text: "Priority routing", included: true },
      { text: "Analytics dashboard", included: true },
      { text: "SLA guarantee", included: false },
    ],
  },
  {
    name: "Enterprise",
    price: "Custom",
    period: "",
    description: "Tailored solutions for large organizations",
    icon: Building2,
    color: "#a78bfa",
    bgColor: "rgba(167,139,250,0.08)",
    glowColor: "rgba(167,139,250,0.3)",
    features: [
      { text: "Unlimited API calls", included: true },
      { text: "Unlimited agent sessions", included: true },
      { text: "Unlimited storage", included: true },
      { text: "Dedicated support", included: true },
      { text: "Custom agents", included: true },
      { text: "Priority routing", included: true },
      { text: "Advanced analytics", included: true },
      { text: "99.99% SLA guarantee", included: true },
    ],
  },
];

/* ── Status badge colors ────────────────────────────────────────── */

const INVOICE_STATUS_COLORS: Record<string, { bg: string; text: string }> = {
  paid: { bg: "rgba(52,211,153,0.15)", text: "#34d399" },
  pending: { bg: "rgba(251,191,36,0.15)", text: "#fbbf24" },
  overdue: { bg: "rgba(248,113,113,0.15)", text: "#f87171" },
};

/* ── Component ──────────────────────────────────────────────────── */

export default function BillingPage() {
  const [showAllInvoices, setShowAllInvoices] = useState(false);

  const visibleInvoices = useMemo(
    () => (showAllInvoices ? INVOICES : INVOICES.slice(0, 3)),
    [showAllInvoices],
  );

  return (
    <div className="space-y-6">
      {/* Page header */}
      <PageHeader
        title="Billing & Subscription"
        subtitle="Manage your plan, monitor usage, and view invoices"
        icon={CreditCard}
      />

      {/* ── Current Plan Banner ──────────────────────────────── */}
      <div
        className="rounded-2xl border p-6"
        style={{
          borderColor: "rgba(96,165,250,0.2)",
          background:
            "linear-gradient(135deg, rgba(96,165,250,0.06) 0%, rgba(167,139,250,0.04) 100%)",
        }}
      >
        <div className="flex items-center justify-between flex-wrap gap-4">
          <div className="flex items-center gap-4">
            <div
              className="flex h-12 w-12 items-center justify-center rounded-xl"
              style={{
                backgroundColor: "rgba(96,165,250,0.15)",
                boxShadow: "0 0 16px rgba(96,165,250,0.2)",
              }}
            >
              <Crown className="h-6 w-6 text-[#60a5fa]" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h3 className="text-lg font-bold text-[#e2e8f0]">
                  {CURRENT_PLAN} Plan
                </h3>
                <span className="rounded-full bg-[rgba(96,165,250,0.15)] px-2.5 py-0.5 text-[10px] font-semibold uppercase text-[#60a5fa]">
                  Active
                </span>
              </div>
              <p className="text-xs text-[#64748b] mt-0.5">
                Your next billing date is March 1, 2026
              </p>
            </div>
          </div>
          <div className="flex items-center gap-3">
            <button className="rounded-xl border border-[rgba(255,255,255,0.1)] bg-transparent px-4 py-2.5 text-sm font-medium text-[#94a3b8] transition-colors hover:bg-[rgba(255,255,255,0.04)] hover:text-[#e2e8f0]">
              Cancel Plan
            </button>
            <button className="rounded-xl bg-[#60a5fa] px-4 py-2.5 text-sm font-medium text-[#0a0e1a] transition-colors hover:bg-[#3b82f6]">
              Upgrade
            </button>
          </div>
        </div>
      </div>

      {/* ── Usage Meters ─────────────────────────────────────── */}
      <div className="rounded-2xl border border-[rgba(255,255,255,0.06)] bg-[#141928] p-6">
        <div className="flex items-center gap-2 mb-5">
          <TrendingUp className="h-4 w-4 text-[#60a5fa]" />
          <h3 className="text-sm font-semibold text-[#e2e8f0]">
            Usage This Period
          </h3>
        </div>

        <div className="grid gap-5 sm:grid-cols-2">
          {USAGE_METERS.map((meter) => {
            const percent = Math.min(
              100,
              Math.round((meter.current / meter.limit) * 100),
            );
            const isHigh = percent >= 80;
            const displayColor = isHigh ? "#f87171" : meter.color;

            return (
              <div key={meter.label} className="space-y-2">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-medium text-[#e2e8f0]">
                    {meter.label}
                  </span>
                  <span className="text-xs font-mono text-[#94a3b8]">
                    {typeof meter.current === "number" && meter.current >= 1000
                      ? meter.current.toLocaleString()
                      : meter.current}{" "}
                    / {typeof meter.limit === "number" && meter.limit >= 1000
                      ? meter.limit.toLocaleString()
                      : meter.limit}{" "}
                    {meter.unit}
                  </span>
                </div>

                {/* Progress bar */}
                <div className="h-2.5 w-full overflow-hidden rounded-full bg-[#0d1220]">
                  <div
                    className="h-full rounded-full transition-all duration-500 ease-out"
                    style={{
                      width: `${percent}%`,
                      backgroundColor: displayColor,
                      boxShadow: `0 0 8px ${displayColor}40`,
                    }}
                  />
                </div>

                <div className="flex items-center justify-between">
                  <span
                    className="text-[10px] font-semibold"
                    style={{ color: displayColor }}
                  >
                    {percent}% used
                  </span>
                  {isHigh && (
                    <span className="text-[10px] text-[#f87171]">
                      Approaching limit
                    </span>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* ── Plan Comparison Cards ─────────────────────────────── */}
      <div>
        <h3 className="mb-4 text-sm font-semibold text-[#e2e8f0]">
          Compare Plans
        </h3>
        <div className="grid gap-5 lg:grid-cols-3">
          {PLANS.map((plan) => {
            const Icon = plan.icon;
            const isCurrent = plan.name === CURRENT_PLAN;

            return (
              <div
                key={plan.name}
                className="relative flex flex-col rounded-2xl border overflow-hidden transition-all duration-300 hover:-translate-y-1 hover:shadow-lg"
                style={{
                  borderColor: isCurrent
                    ? `${plan.color}40`
                    : "rgba(255,255,255,0.06)",
                  background: isCurrent
                    ? `linear-gradient(135deg, ${plan.bgColor}, #141928)`
                    : "#141928",
                  boxShadow: isCurrent
                    ? `0 0 24px ${plan.glowColor}`
                    : undefined,
                }}
              >
                {/* Popular badge */}
                {plan.popular && (
                  <div
                    className="absolute right-4 top-4 rounded-full px-2.5 py-0.5 text-[9px] font-bold uppercase tracking-wider"
                    style={{
                      backgroundColor: `${plan.color}20`,
                      color: plan.color,
                    }}
                  >
                    Most Popular
                  </div>
                )}

                <div className="flex flex-1 flex-col p-6">
                  {/* Plan header */}
                  <div className="flex items-center gap-3 mb-4">
                    <div
                      className="flex h-10 w-10 items-center justify-center rounded-xl"
                      style={{
                        backgroundColor: plan.bgColor,
                        boxShadow: `0 0 12px ${plan.glowColor}`,
                      }}
                    >
                      <Icon
                        className="h-5 w-5"
                        style={{ color: plan.color }}
                      />
                    </div>
                    <div>
                      <h4 className="text-base font-bold text-[#e2e8f0]">
                        {plan.name}
                      </h4>
                    </div>
                  </div>

                  {/* Price */}
                  <div className="mb-3">
                    <span className="text-3xl font-bold text-[#e2e8f0]">
                      {plan.price}
                    </span>
                    {plan.period && (
                      <span className="text-sm text-[#64748b]">
                        {plan.period}
                      </span>
                    )}
                  </div>

                  <p className="mb-5 text-xs text-[#64748b] leading-relaxed">
                    {plan.description}
                  </p>

                  {/* Features */}
                  <div className="flex-1 space-y-2.5 mb-6">
                    {plan.features.map((feature, idx) => (
                      <div key={idx} className="flex items-center gap-2.5">
                        <div
                          className="flex h-4 w-4 flex-shrink-0 items-center justify-center rounded-full"
                          style={{
                            backgroundColor: feature.included
                              ? `${plan.color}20`
                              : "rgba(100,116,139,0.1)",
                          }}
                        >
                          {feature.included ? (
                            <Check
                              className="h-2.5 w-2.5"
                              style={{ color: plan.color }}
                            />
                          ) : (
                            <span className="text-[8px] text-[#475569]">
                              --
                            </span>
                          )}
                        </div>
                        <span
                          className="text-xs"
                          style={{
                            color: feature.included ? "#94a3b8" : "#475569",
                          }}
                        >
                          {feature.text}
                        </span>
                      </div>
                    ))}
                  </div>

                  {/* CTA button */}
                  <button
                    className="w-full rounded-xl py-3 text-sm font-semibold transition-all duration-200"
                    style={{
                      backgroundColor: isCurrent
                        ? "transparent"
                        : plan.bgColor,
                      color: isCurrent ? "#64748b" : plan.color,
                      border: `1px solid ${
                        isCurrent
                          ? "rgba(100,116,139,0.2)"
                          : `${plan.color}30`
                      }`,
                      cursor: isCurrent ? "default" : "pointer",
                    }}
                    disabled={isCurrent}
                  >
                    {isCurrent
                      ? "Current Plan"
                      : plan.name === "Enterprise"
                        ? "Contact Sales"
                        : `Upgrade to ${plan.name}`}
                  </button>
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* ── Invoices Table ────────────────────────────────────── */}
      <div className="rounded-2xl border border-[rgba(255,255,255,0.06)] bg-[#141928] overflow-hidden">
        <div className="flex items-center justify-between border-b border-[rgba(255,255,255,0.06)] px-6 py-4">
          <div className="flex items-center gap-2">
            <FileText className="h-4 w-4 text-[#fbbf24]" />
            <h3 className="text-sm font-semibold text-[#e2e8f0]">Invoices</h3>
          </div>
          <span className="text-[10px] text-[#64748b]">
            {INVOICES.length} total
          </span>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-[rgba(255,255,255,0.06)] bg-[#0d1220]">
                <th className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider text-[#64748b]">
                  Invoice
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider text-[#64748b]">
                  Date
                </th>
                <th className="px-6 py-3 text-right text-xs font-medium uppercase tracking-wider text-[#64748b]">
                  Amount
                </th>
                <th className="px-6 py-3 text-center text-xs font-medium uppercase tracking-wider text-[#64748b]">
                  Status
                </th>
                <th className="px-6 py-3 text-center text-xs font-medium uppercase tracking-wider text-[#64748b]">
                  Download
                </th>
              </tr>
            </thead>
            <tbody>
              {visibleInvoices.map((invoice, idx) => {
                const statusStyle =
                  INVOICE_STATUS_COLORS[invoice.status] ??
                  INVOICE_STATUS_COLORS.pending;
                return (
                  <tr
                    key={invoice.id}
                    className={`border-b border-[rgba(255,255,255,0.04)] transition-colors hover:bg-[rgba(96,165,250,0.04)] ${
                      idx % 2 === 1 ? "bg-[rgba(255,255,255,0.01)]" : ""
                    }`}
                  >
                    <td className="px-6 py-3">
                      <span className="font-mono text-xs text-[#e2e8f0]">
                        {invoice.id}
                      </span>
                    </td>
                    <td className="px-6 py-3 text-xs text-[#94a3b8]">
                      {new Date(invoice.date).toLocaleDateString("en-US", {
                        year: "numeric",
                        month: "long",
                        day: "numeric",
                      })}
                    </td>
                    <td className="px-6 py-3 text-right text-xs font-semibold text-[#e2e8f0]">
                      ${invoice.amount.toFixed(2)}
                    </td>
                    <td className="px-6 py-3 text-center">
                      <span
                        className="inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-[10px] font-semibold uppercase"
                        style={{
                          backgroundColor: statusStyle.bg,
                          color: statusStyle.text,
                        }}
                      >
                        <span
                          className="h-1.5 w-1.5 rounded-full"
                          style={{ backgroundColor: statusStyle.text }}
                        />
                        {invoice.status}
                      </span>
                    </td>
                    <td className="px-6 py-3 text-center">
                      <a
                        href={invoice.downloadUrl}
                        className="inline-flex items-center gap-1 rounded-lg p-1.5 text-[#64748b] transition-colors hover:bg-[rgba(255,255,255,0.04)] hover:text-[#60a5fa]"
                        title="Download invoice"
                      >
                        <Download className="h-3.5 w-3.5" />
                      </a>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>

        {/* Show more / less */}
        {INVOICES.length > 3 && (
          <div className="border-t border-[rgba(255,255,255,0.06)] px-6 py-3">
            <button
              onClick={() => setShowAllInvoices((v) => !v)}
              className="inline-flex items-center gap-1 text-xs font-medium text-[#60a5fa] transition-colors hover:text-[#3b82f6]"
            >
              {showAllInvoices ? (
                <>
                  Show less <ChevronUp className="h-3 w-3" />
                </>
              ) : (
                <>
                  View all {INVOICES.length} invoices{" "}
                  <ChevronDown className="h-3 w-3" />
                </>
              )}
            </button>
          </div>
        )}
      </div>

      {/* ── Payment Method ────────────────────────────────────── */}
      <div className="rounded-2xl border border-[rgba(255,255,255,0.06)] bg-[#141928] p-6">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-[rgba(96,165,250,0.1)]">
              <CreditCard className="h-5 w-5 text-[#60a5fa]" />
            </div>
            <div>
              <p className="text-sm font-semibold text-[#e2e8f0]">
                Payment Method
              </p>
              <p className="text-xs text-[#64748b]">
                Visa ending in 4242
              </p>
            </div>
          </div>
          <button className="inline-flex items-center gap-1.5 rounded-xl border border-[rgba(255,255,255,0.1)] px-4 py-2 text-xs font-medium text-[#94a3b8] transition-colors hover:bg-[rgba(255,255,255,0.04)] hover:text-[#e2e8f0]">
            <ExternalLink className="h-3 w-3" />
            Update
          </button>
        </div>
      </div>
    </div>
  );
}
