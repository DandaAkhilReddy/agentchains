import { useState, useMemo } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
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
  Lightbulb,
  ArrowRight,
  AlertTriangle,
  Loader2,
} from "lucide-react";
import PageHeader from "../components/PageHeader";
import { useAuth } from "../hooks/useAuth";
import { formatUSD } from "../lib/format";
import {
  fetchPlans,
  fetchMySubscription,
  fetchUsage,
  fetchInvoices,
  fetchPlanRecommendation,
  createSubscription,
  cancelSubscription,
  changePlan,
  fetchInvoicePdf,
} from "../api/billing";
import type {
  PlanResponse,
  UsageMeterResponse,
  InvoiceResponse,
  SubscriptionResponse,
  RecommendationResponse,
} from "../types/billing";

/**
 * Billing / Subscription Page.
 *
 * URL: /billing
 *
 * Shows current plan, usage meters, invoices, plan comparison cards,
 * and AI-powered plan recommendation — all wired to live API data.
 */

/* -- Icon/color map per tier -- */

const TIER_CONFIG: Record<
  string,
  {
    icon: typeof Zap;
    color: string;
    bgColor: string;
    glowColor: string;
    popular?: boolean;
  }
> = {
  free: {
    icon: Zap,
    color: "#64748b",
    bgColor: "rgba(100,116,139,0.08)",
    glowColor: "rgba(100,116,139,0.2)",
  },
  starter: {
    icon: Zap,
    color: "#34d399",
    bgColor: "rgba(52,211,153,0.08)",
    glowColor: "rgba(52,211,153,0.2)",
  },
  pro: {
    icon: Crown,
    color: "#60a5fa",
    bgColor: "rgba(96,165,250,0.08)",
    glowColor: "rgba(96,165,250,0.3)",
    popular: true,
  },
  enterprise: {
    icon: Building2,
    color: "#a78bfa",
    bgColor: "rgba(167,139,250,0.08)",
    glowColor: "rgba(167,139,250,0.3)",
  },
};

const METRIC_CONFIG: Record<string, { label: string; unit: string; color: string }> = {
  api_calls: { label: "API Calls", unit: "calls", color: "#60a5fa" },
  storage: { label: "Storage", unit: "GB", color: "#fbbf24" },
  bandwidth: { label: "Data Transfer", unit: "GB", color: "#34d399" },
};

const INVOICE_STATUS_COLORS: Record<string, { bg: string; text: string }> = {
  paid: { bg: "rgba(52,211,153,0.15)", text: "#34d399" },
  open: { bg: "rgba(251,191,36,0.15)", text: "#fbbf24" },
  draft: { bg: "rgba(100,116,139,0.15)", text: "#94a3b8" },
  void: { bg: "rgba(100,116,139,0.15)", text: "#64748b" },
  uncollectible: { bg: "rgba(248,113,113,0.15)", text: "#f87171" },
};

/* -- Component -- */

export default function BillingPage() {
  const { token } = useAuth();
  const queryClient = useQueryClient();
  const [showAllInvoices, setShowAllInvoices] = useState(false);
  const [cancelDialogOpen, setCancelDialogOpen] = useState(false);

  // ── Queries ──

  const plansQuery = useQuery({
    queryKey: ["plans"],
    queryFn: () => fetchPlans(),
  });

  const subscriptionQuery = useQuery({
    queryKey: ["subscription"],
    queryFn: () => fetchMySubscription(token),
    enabled: !!token,
  });

  const usageQuery = useQuery({
    queryKey: ["usage"],
    queryFn: () => fetchUsage(token),
    enabled: !!token,
  });

  const invoicesQuery = useQuery({
    queryKey: ["invoices"],
    queryFn: () => fetchInvoices(token, 1, 50),
    enabled: !!token,
  });

  const recommendQuery = useQuery({
    queryKey: ["plan-recommendation"],
    queryFn: () => fetchPlanRecommendation(token),
    enabled: !!token,
  });

  // ── Mutations ──

  const subscribeMutation = useMutation({
    mutationFn: ({ planId, cycle }: { planId: string; cycle: "monthly" | "yearly" }) =>
      createSubscription(token, planId, cycle),
    onSuccess: (data) => {
      if (data.checkout_url) {
        window.location.href = data.checkout_url;
      } else {
        queryClient.invalidateQueries({ queryKey: ["subscription"] });
        queryClient.invalidateQueries({ queryKey: ["plans"] });
      }
    },
  });

  const cancelMutation = useMutation({
    mutationFn: (immediate: boolean) => cancelSubscription(token, immediate),
    onSuccess: () => {
      setCancelDialogOpen(false);
      queryClient.invalidateQueries({ queryKey: ["subscription"] });
    },
  });

  const changePlanMutation = useMutation({
    mutationFn: (newPlanId: string) => changePlan(token, newPlanId),
    onSuccess: (data) => {
      if (data.checkout_url) {
        window.location.href = data.checkout_url;
      } else {
        queryClient.invalidateQueries({ queryKey: ["subscription"] });
      }
    },
  });

  // ── Derived data ──

  const plans = plansQuery.data ?? [];
  const subscription = subscriptionQuery.data;
  const usageMeters = usageQuery.data ?? [];
  const invoices = invoicesQuery.data?.items ?? [];
  const recommendation = recommendQuery.data;

  const currentPlanName = subscription?.plan?.name ?? null;

  const visibleInvoices = useMemo(
    () => (showAllInvoices ? invoices : invoices.slice(0, 3)),
    [showAllInvoices, invoices],
  );

  // ── Handlers ──

  const handleSubscribe = (planId: string) => {
    subscribeMutation.mutate({ planId, cycle: "monthly" });
  };

  const handleChangePlan = (planId: string) => {
    changePlanMutation.mutate(planId);
  };

  const handleDownloadInvoice = async (invoiceId: string) => {
    try {
      const result = await fetchInvoicePdf(token, invoiceId);
      if (result.pdf_url) {
        window.open(result.pdf_url, "_blank");
      }
    } catch {
      // Silently handled — PDF may not be available
    }
  };

  return (
    <div className="space-y-6">
      {/* Page header */}
      <PageHeader
        title="Billing & Subscription"
        subtitle="Manage your plan, monitor usage, and view invoices"
        icon={CreditCard}
      />

      {/* ── Current Plan Banner ──────────────────────────────── */}
      {subscription ? (
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
                    {subscription.plan.name} Plan
                  </h3>
                  <span className="rounded-full bg-[rgba(96,165,250,0.15)] px-2.5 py-0.5 text-[10px] font-semibold uppercase text-[#60a5fa]">
                    {subscription.status}
                  </span>
                </div>
                <p className="text-xs text-[#64748b] mt-0.5">
                  {subscription.current_period_end
                    ? `Next billing: ${new Date(subscription.current_period_end).toLocaleDateString()}`
                    : "No active billing period"}
                </p>
                {subscription.cancel_at_period_end && (
                  <p className="text-xs text-[#f87171] mt-0.5">
                    Cancels at end of current period
                  </p>
                )}
              </div>
            </div>
            <div className="flex items-center gap-3">
              <button
                onClick={() => setCancelDialogOpen(true)}
                disabled={cancelMutation.isPending || subscription.cancel_at_period_end}
                className="rounded-xl border border-[rgba(255,255,255,0.1)] bg-transparent px-4 py-2.5 text-sm font-medium text-[#94a3b8] transition-colors hover:bg-[rgba(255,255,255,0.04)] hover:text-[#e2e8f0] disabled:opacity-50"
              >
                Cancel Plan
              </button>
            </div>
          </div>
        </div>
      ) : (
        <div className="rounded-2xl border border-[rgba(255,255,255,0.06)] bg-[#141928] p-6 text-center">
          <p className="text-sm text-[#94a3b8]">
            {subscriptionQuery.isLoading
              ? "Loading subscription..."
              : "No active subscription. Choose a plan below to get started."}
          </p>
        </div>
      )}

      {/* ── Cancel confirmation dialog ── */}
      {cancelDialogOpen && (
        <div className="rounded-2xl border border-[rgba(248,113,113,0.2)] bg-[#141928] p-6">
          <div className="flex items-center gap-2 mb-3">
            <AlertTriangle className="h-4 w-4 text-[#f87171]" />
            <h4 className="text-sm font-semibold text-[#e2e8f0]">Cancel Subscription?</h4>
          </div>
          <p className="text-xs text-[#94a3b8] mb-4">
            Choose to cancel at the end of your current billing period (recommended) or immediately.
          </p>
          <div className="flex gap-3">
            <button
              onClick={() => cancelMutation.mutate(false)}
              disabled={cancelMutation.isPending}
              className="rounded-xl bg-[rgba(248,113,113,0.1)] px-4 py-2 text-sm font-medium text-[#f87171] hover:bg-[rgba(248,113,113,0.2)]"
            >
              {cancelMutation.isPending ? "Cancelling..." : "Cancel at Period End"}
            </button>
            <button
              onClick={() => cancelMutation.mutate(true)}
              disabled={cancelMutation.isPending}
              className="rounded-xl bg-[#f87171] px-4 py-2 text-sm font-medium text-[#0a0e1a] hover:bg-[#ef4444]"
            >
              Cancel Immediately
            </button>
            <button
              onClick={() => setCancelDialogOpen(false)}
              className="rounded-xl border border-[rgba(255,255,255,0.1)] px-4 py-2 text-sm font-medium text-[#94a3b8] hover:bg-[rgba(255,255,255,0.04)]"
            >
              Keep Plan
            </button>
          </div>
        </div>
      )}

      {/* ── Usage Meters ─────────────────────────────────────── */}
      <div className="rounded-2xl border border-[rgba(255,255,255,0.06)] bg-[#141928] p-6">
        <div className="flex items-center gap-2 mb-5">
          <TrendingUp className="h-4 w-4 text-[#60a5fa]" />
          <h3 className="text-sm font-semibold text-[#e2e8f0]">
            Usage This Period
          </h3>
        </div>

        {usageQuery.isLoading ? (
          <p className="text-xs text-[#64748b]">Loading usage...</p>
        ) : usageMeters.length === 0 ? (
          <p className="text-xs text-[#64748b]">No usage data available.</p>
        ) : (
          <div className="grid gap-5 sm:grid-cols-2">
            {usageMeters.map((meter) => {
              const cfg = METRIC_CONFIG[meter.metric_name] ?? {
                label: meter.metric_name,
                unit: "",
                color: "#60a5fa",
              };
              const percent = Math.min(100, Math.round(meter.percent_used));
              const isHigh = percent >= 80;
              const displayColor = isHigh ? "#f87171" : cfg.color;

              return (
                <div key={meter.metric_name} className="space-y-2">
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-medium text-[#e2e8f0]">
                      {cfg.label}
                    </span>
                    <span className="text-xs font-mono text-[#94a3b8]">
                      {meter.current >= 1000
                        ? meter.current.toLocaleString()
                        : meter.current}{" "}
                      / {meter.limit >= 1000
                        ? meter.limit.toLocaleString()
                        : meter.limit}{" "}
                      {cfg.unit}
                    </span>
                  </div>

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
        )}
      </div>

      {/* ── Plan Advisor ─────────────────────────────────────── */}
      {recommendation && recommendation.recommended_plan.name !== currentPlanName && (
        <div
          className="rounded-2xl border p-6"
          style={{
            borderColor: "rgba(52,211,153,0.2)",
            background:
              "linear-gradient(135deg, rgba(52,211,153,0.06) 0%, rgba(96,165,250,0.04) 100%)",
          }}
        >
          <div className="flex items-center gap-2 mb-3">
            <Lightbulb className="h-4 w-4 text-[#34d399]" />
            <h3 className="text-sm font-semibold text-[#e2e8f0]">
              Plan Recommendation
            </h3>
          </div>
          <p className="text-xs text-[#94a3b8] leading-relaxed mb-4">
            {recommendation.reasoning}
          </p>
          <div className="flex items-center gap-4">
            <button
              onClick={() => handleChangePlan(recommendation.recommended_plan.id)}
              disabled={changePlanMutation.isPending}
              className="inline-flex items-center gap-2 rounded-xl bg-[#34d399] px-4 py-2.5 text-sm font-semibold text-[#0a0e1a] transition-colors hover:bg-[#2dd4bf]"
            >
              {changePlanMutation.isPending ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <ArrowRight className="h-4 w-4" />
              )}
              Switch to {recommendation.recommended_plan.name}
            </button>
            {recommendation.savings_estimate_monthly > 0 && (
              <span className="text-xs font-semibold text-[#34d399]">
                Save {formatUSD(recommendation.savings_estimate_monthly)}/mo
              </span>
            )}
          </div>
        </div>
      )}

      {/* ── Plan Comparison Cards ─────────────────────────────── */}
      <div>
        <h3 className="mb-4 text-sm font-semibold text-[#e2e8f0]">
          Compare Plans
        </h3>

        {plansQuery.isLoading ? (
          <p className="text-xs text-[#64748b]">Loading plans...</p>
        ) : (
          <div className="grid gap-5 lg:grid-cols-3 xl:grid-cols-4">
            {plans.map((plan) => {
              const tier = TIER_CONFIG[plan.tier] ?? TIER_CONFIG.free;
              const Icon = tier.icon;
              const isCurrent = plan.name === currentPlanName;

              return (
                <div
                  key={plan.id}
                  className="relative flex flex-col rounded-2xl border overflow-hidden transition-all duration-300 hover:-translate-y-1 hover:shadow-lg"
                  style={{
                    borderColor: isCurrent
                      ? `${tier.color}40`
                      : "rgba(255,255,255,0.06)",
                    background: isCurrent
                      ? `linear-gradient(135deg, ${tier.bgColor}, #141928)`
                      : "#141928",
                    boxShadow: isCurrent
                      ? `0 0 24px ${tier.glowColor}`
                      : undefined,
                  }}
                >
                  {tier.popular && (
                    <div
                      className="absolute right-4 top-4 rounded-full px-2.5 py-0.5 text-[9px] font-bold uppercase tracking-wider"
                      style={{
                        backgroundColor: `${tier.color}20`,
                        color: tier.color,
                      }}
                    >
                      Most Popular
                    </div>
                  )}

                  <div className="flex flex-1 flex-col p-6">
                    <div className="flex items-center gap-3 mb-4">
                      <div
                        className="flex h-10 w-10 items-center justify-center rounded-xl"
                        style={{
                          backgroundColor: tier.bgColor,
                          boxShadow: `0 0 12px ${tier.glowColor}`,
                        }}
                      >
                        <Icon
                          className="h-5 w-5"
                          style={{ color: tier.color }}
                        />
                      </div>
                      <h4 className="text-base font-bold text-[#e2e8f0]">
                        {plan.name}
                      </h4>
                    </div>

                    <div className="mb-3">
                      <span className="text-3xl font-bold text-[#e2e8f0]">
                        {plan.price_monthly === 0
                          ? "$0"
                          : `$${plan.price_monthly}`}
                      </span>
                      <span className="text-sm text-[#64748b]">
                        {plan.price_monthly > 0 ? "/month" : " forever"}
                      </span>
                    </div>

                    <p className="mb-5 text-xs text-[#64748b] leading-relaxed">
                      {plan.description}
                    </p>

                    <div className="flex-1 space-y-2.5 mb-6">
                      {plan.features.map((feature, idx) => (
                        <div key={idx} className="flex items-center gap-2.5">
                          <div
                            className="flex h-4 w-4 flex-shrink-0 items-center justify-center rounded-full"
                            style={{ backgroundColor: `${tier.color}20` }}
                          >
                            <Check
                              className="h-2.5 w-2.5"
                              style={{ color: tier.color }}
                            />
                          </div>
                          <span className="text-xs text-[#94a3b8]">
                            {feature}
                          </span>
                        </div>
                      ))}
                    </div>

                    <button
                      onClick={() =>
                        isCurrent
                          ? undefined
                          : currentPlanName
                            ? handleChangePlan(plan.id)
                            : handleSubscribe(plan.id)
                      }
                      className="w-full rounded-xl py-3 text-sm font-semibold transition-all duration-200"
                      style={{
                        backgroundColor: isCurrent
                          ? "transparent"
                          : tier.bgColor,
                        color: isCurrent ? "#64748b" : tier.color,
                        border: `1px solid ${
                          isCurrent
                            ? "rgba(100,116,139,0.2)"
                            : `${tier.color}30`
                        }`,
                        cursor: isCurrent ? "default" : "pointer",
                      }}
                      disabled={isCurrent || subscribeMutation.isPending || changePlanMutation.isPending}
                    >
                      {isCurrent
                        ? "Current Plan"
                        : currentPlanName
                          ? `Switch to ${plan.name}`
                          : plan.tier === "enterprise"
                            ? "Contact Sales"
                            : `Get ${plan.name}`}
                    </button>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* ── Invoices Table ────────────────────────────────────── */}
      <div className="rounded-2xl border border-[rgba(255,255,255,0.06)] bg-[#141928] overflow-hidden">
        <div className="flex items-center justify-between border-b border-[rgba(255,255,255,0.06)] px-6 py-4">
          <div className="flex items-center gap-2">
            <FileText className="h-4 w-4 text-[#fbbf24]" />
            <h3 className="text-sm font-semibold text-[#e2e8f0]">Invoices</h3>
          </div>
          <span className="text-[10px] text-[#64748b]">
            {invoices.length} total
          </span>
        </div>

        {invoicesQuery.isLoading ? (
          <div className="p-6">
            <p className="text-xs text-[#64748b]">Loading invoices...</p>
          </div>
        ) : invoices.length === 0 ? (
          <div className="p-6">
            <p className="text-xs text-[#64748b]">No invoices yet.</p>
          </div>
        ) : (
          <>
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
                      INVOICE_STATUS_COLORS.open;
                    return (
                      <tr
                        key={invoice.id}
                        className={`border-b border-[rgba(255,255,255,0.04)] transition-colors hover:bg-[rgba(96,165,250,0.04)] ${
                          idx % 2 === 1 ? "bg-[rgba(255,255,255,0.01)]" : ""
                        }`}
                      >
                        <td className="px-6 py-3">
                          <span className="font-mono text-xs text-[#e2e8f0]">
                            {invoice.id.slice(0, 13)}...
                          </span>
                        </td>
                        <td className="px-6 py-3 text-xs text-[#94a3b8]">
                          {invoice.issued_at
                            ? new Date(invoice.issued_at).toLocaleDateString(
                                "en-US",
                                { year: "numeric", month: "long", day: "numeric" },
                              )
                            : "N/A"}
                        </td>
                        <td className="px-6 py-3 text-right text-xs font-semibold text-[#e2e8f0]">
                          {formatUSD(invoice.total_usd)}
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
                          <button
                            onClick={() => handleDownloadInvoice(invoice.id)}
                            className="inline-flex items-center gap-1 rounded-lg p-1.5 text-[#64748b] transition-colors hover:bg-[rgba(255,255,255,0.04)] hover:text-[#60a5fa]"
                            title="Download invoice"
                          >
                            <Download className="h-3.5 w-3.5" />
                          </button>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>

            {invoices.length > 3 && (
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
                      View all {invoices.length} invoices{" "}
                      <ChevronDown className="h-3 w-3" />
                    </>
                  )}
                </button>
              </div>
            )}
          </>
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
                Managed via Stripe
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
