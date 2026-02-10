import { useState } from "react";
import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { Plus, Zap, TrendingDown, Brain, ChevronDown, ChevronUp, AlertTriangle, Shield, Sparkles, Wallet, Calendar, Target } from "lucide-react";
import api from "../lib/api";
import { formatMonths, formatCurrency } from "../lib/format";
import { CurrencyDisplay } from "../components/shared/CurrencyDisplay";
import { EmptyState } from "../components/shared/EmptyState";
import { AnimatedNumber } from "../components/shared/AnimatedNumber";
import { DashboardSkeleton } from "../components/dashboard/DashboardSkeleton";
import { useCountryStore } from "../store/countryStore";
import type { Loan, DashboardSummary, LoanInsight } from "../types";

const LOAN_TYPE_COLORS: Record<string, string> = {
  home: "bg-blue-100 text-blue-700",
  personal: "bg-purple-100 text-purple-700",
  car: "bg-green-100 text-green-700",
  education: "bg-yellow-100 text-yellow-700",
  gold: "bg-amber-100 text-amber-700",
  credit_card: "bg-red-100 text-red-700",
  business: "bg-teal-100 text-teal-700",
};

export function DashboardPage() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const country = useCountryStore((s) => s.country);
  const [expandedInsight, setExpandedInsight] = useState<string | null>(null);

  const { data: loans, isLoading } = useQuery<Loan[]>({
    queryKey: ["loans"],
    queryFn: () => api.get("/api/loans").then((r) => r.data),
  });

  const activeLoans = loans?.filter((l) => l.status === "active") || [];

  const { data: summary } = useQuery<DashboardSummary>({
    queryKey: ["dashboard-summary"],
    queryFn: () => api.get("/api/optimizer/dashboard-summary").then((r) => r.data),
    enabled: activeLoans.length > 0,
  });

  const { data: insights } = useQuery<LoanInsight[]>({
    queryKey: ["loan-insights", activeLoans.map((l) => l.id).join(",")],
    queryFn: () =>
      api
        .post("/api/ai/explain-loans-batch", { loan_ids: activeLoans.map((l) => l.id) })
        .then((r) => r.data.insights),
    enabled: activeLoans.length > 0,
  });

  if (isLoading) return <DashboardSkeleton />;

  if (activeLoans.length === 0) {
    return (
      <EmptyState
        title={t("dashboard.noLoansYet")}
        description={t("dashboard.noLoansDesc")}
        action={{ label: t("dashboard.addLoan"), onClick: () => navigate("/scanner") }}
      />
    );
  }

  const totalDebt = activeLoans.reduce((sum, l) => sum + l.outstanding_principal, 0);
  const totalEMI = activeLoans.reduce((sum, l) => sum + l.emi_amount, 0);
  const maxTenure = Math.max(...activeLoans.map((l) => l.remaining_tenure_months));
  const avgRate = activeLoans.reduce((sum, l) => sum + l.interest_rate, 0) / activeLoans.length;
  const highestRateLoan = activeLoans.reduce((max, l) => (l.interest_rate > max.interest_rate ? l : max), activeLoans[0]);

  const currencyFormatter = (n: number) => formatCurrency(n, country);
  const insightMap = new Map(insights?.map((i) => [i.loan_id, i.text]) || []);

  // Health score: 0-100 based on avg rate, debt-to-EMI ratio, loan count
  const rateScore = Math.max(0, 100 - avgRate * 5);
  const ratioScore = totalEMI > 0 ? Math.min(100, (totalDebt / totalEMI / 300) * 100) : 50;
  const healthScore = Math.round((rateScore * 0.6 + (100 - ratioScore) * 0.4));
  const healthColor = healthScore > 70 ? "text-green-500" : healthScore > 40 ? "text-yellow-500" : "text-red-500";
  const healthBg = healthScore > 70 ? "#22c55e" : healthScore > 40 ? "#eab308" : "#ef4444";

  return (
    <div className="space-y-6 animate-fade-up">
      {/* AI Optimizer Summary Card */}
      {summary?.has_loans && summary.interest_saved > 0 && (
        <div className="bg-gradient-to-r from-emerald-500 to-teal-600 rounded-xl p-5 text-white shadow-float animate-fade-up">
          <div className="flex items-start gap-3">
            <div className="w-10 h-10 bg-white/20 rounded-full flex items-center justify-center flex-shrink-0">
              <Sparkles className="w-5 h-5" />
            </div>
            <div className="flex-1">
              <p className="text-sm font-medium text-emerald-100">{t("dashboard.aiRecommendation")}</p>
              <p className="text-lg font-bold mt-1">
                {t("dashboard.youCouldSave")}{" "}
                <CurrencyDisplay amount={summary.interest_saved} className="text-white" />{" "}
                {t("dashboard.inInterest")}
              </p>
              <p className="text-sm text-emerald-100 mt-1">
                {t("dashboard.byPaying")}{" "}
                <CurrencyDisplay amount={summary.suggested_extra} className="text-white" />{" "}
                {t("dashboard.extraPerMonth")} · {summary.months_saved} {t("dashboard.monthsFaster")}
              </p>
              <div className="flex gap-2 mt-3">
                <button
                  onClick={() => navigate("/optimizer")}
                  className="px-3 py-1.5 bg-white text-emerald-700 rounded-lg text-sm font-medium hover:bg-emerald-50 press-scale"
                >
                  {t("dashboard.viewStrategies")}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Summary Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 stagger-children">
        <div className="bg-[var(--color-bg-card)] rounded-xl p-5 shadow-card border border-[var(--color-border-subtle)] hover:shadow-card-hover transition-shadow">
          <div className="flex items-center gap-3 mb-2">
            <div className="w-10 h-10 bg-blue-100 dark:bg-blue-900/30 rounded-full flex items-center justify-center">
              <Wallet className="w-5 h-5 text-blue-600 dark:text-blue-400" />
            </div>
            <p className="text-sm text-[var(--color-text-secondary)]">{t("dashboard.totalDebt")}</p>
          </div>
          <AnimatedNumber value={totalDebt} formatter={currencyFormatter} className="text-2xl font-bold text-[var(--color-text-primary)]" />
          <p className="text-xs text-[var(--color-text-tertiary)] mt-1">{t("dashboard.activeLoans", { count: activeLoans.length })}</p>
        </div>
        <div className="bg-[var(--color-bg-card)] rounded-xl p-5 shadow-card border border-[var(--color-border-subtle)] hover:shadow-card-hover transition-shadow">
          <div className="flex items-center gap-3 mb-2">
            <div className="w-10 h-10 bg-purple-100 dark:bg-purple-900/30 rounded-full flex items-center justify-center">
              <Calendar className="w-5 h-5 text-purple-600 dark:text-purple-400" />
            </div>
            <p className="text-sm text-[var(--color-text-secondary)]">{t("dashboard.monthlyEmi")}</p>
          </div>
          <AnimatedNumber value={totalEMI} formatter={currencyFormatter} className="text-2xl font-bold text-[var(--color-text-primary)]" />
          <p className="text-xs text-[var(--color-text-tertiary)] mt-1">{t("dashboard.perMonth")}</p>
        </div>
        <div className="bg-[var(--color-bg-card)] rounded-xl p-5 shadow-card border border-[var(--color-border-subtle)] hover:shadow-card-hover transition-shadow">
          <div className="flex items-center gap-3 mb-2">
            <div className="w-10 h-10 bg-emerald-100 dark:bg-emerald-900/30 rounded-full flex items-center justify-center">
              <Target className="w-5 h-5 text-emerald-600 dark:text-emerald-400" />
            </div>
            <p className="text-sm text-[var(--color-text-secondary)]">{t("dashboard.debtFreeBy")}</p>
          </div>
          <p className="text-2xl font-bold text-[var(--color-text-primary)]">
            {summary?.debt_free_months ? formatMonths(summary.debt_free_months) : formatMonths(maxTenure)}
          </p>
          <p className="text-xs text-[var(--color-text-tertiary)] mt-1">
            {summary?.debt_free_months
              ? t("dashboard.withOptimization")
              : t("dashboard.longestRemaining")}
          </p>
        </div>
      </div>

      {/* Portfolio Health */}
      <div className="bg-[var(--color-bg-card)] rounded-xl p-5 shadow-card border border-[var(--color-border-subtle)]">
        <div className="flex items-center gap-2 mb-4">
          <Shield className="w-5 h-5 text-[var(--color-accent)]" />
          <h2 className="font-semibold text-[var(--color-text-primary)]">{t("dashboard.portfolioHealth")}</h2>
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-4 gap-4">
          {/* Health Score Ring */}
          <div className="flex items-center justify-center">
            <div className="relative w-20 h-20">
              <svg className="w-20 h-20 -rotate-90" viewBox="0 0 36 36">
                <path
                  d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831"
                  fill="none"
                  stroke="var(--color-bg-inset)"
                  strokeWidth="3"
                />
                <path
                  d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831"
                  fill="none"
                  stroke={healthBg}
                  strokeWidth="3"
                  strokeDasharray={`${healthScore}, 100`}
                  strokeLinecap="round"
                  className="transition-all duration-1000 ease-out"
                />
              </svg>
              <div className="absolute inset-0 flex items-center justify-center">
                <span className={`text-lg font-bold ${healthColor}`}>{healthScore}</span>
              </div>
            </div>
          </div>

          <div>
            <p className="text-xs text-[var(--color-text-secondary)]">{t("dashboard.avgRate")}</p>
            <p className={`text-lg font-bold ${avgRate > 15 ? "text-red-600" : avgRate > 10 ? "text-yellow-600" : "text-green-600"}`}>
              {avgRate.toFixed(1)}%
            </p>
          </div>
          <div>
            <p className="text-xs text-[var(--color-text-secondary)]">{t("dashboard.highestRisk")}</p>
            <div className="flex items-center gap-1">
              <AlertTriangle className={`w-4 h-4 ${highestRateLoan.interest_rate > 15 ? "text-red-500" : "text-yellow-500"}`} />
              <span className="text-sm font-medium text-[var(--color-text-primary)]">
                {highestRateLoan.bank_name} ({highestRateLoan.interest_rate}%)
              </span>
            </div>
          </div>
          <div>
            <p className="text-xs text-[var(--color-text-secondary)]">{t("dashboard.debtToEmi")}</p>
            <p className="text-lg font-bold text-[var(--color-text-primary)]">
              {totalEMI > 0 ? Math.round(totalDebt / totalEMI) : 0} {t("common.months")}
            </p>
          </div>
        </div>
      </div>

      {/* Quick Actions */}
      <div className="flex flex-wrap gap-3">
        <button
          onClick={() => navigate("/scanner")}
          className="btn btn-primary press-scale"
        >
          <Plus className="w-4 h-4" />
          {t("dashboard.addLoan")}
        </button>
        <button
          onClick={() => navigate("/optimizer")}
          className="flex items-center gap-2 px-4 py-2 bg-gradient-to-r from-indigo-500 to-purple-600 text-white rounded-lg text-sm font-medium hover:from-indigo-600 hover:to-purple-700 press-scale"
        >
          <Zap className="w-4 h-4" />
          {t("dashboard.viewStrategies")}
        </button>
      </div>

      {/* Strategy Preview */}
      {summary?.strategies_preview && summary.strategies_preview.length > 0 && (
        <div className="bg-[var(--color-bg-card)] rounded-xl p-5 shadow-card border border-[var(--color-border-subtle)]">
          <div className="flex items-center gap-2 mb-3">
            <TrendingDown className="w-5 h-5 text-indigo-500" />
            <h2 className="font-semibold text-[var(--color-text-primary)]">{t("dashboard.strategyPreview")}</h2>
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 stagger-children">
            {summary.strategies_preview.map((s) => (
              <div
                key={s.name}
                className={`p-3 rounded-lg border transition-shadow hover:shadow-card-hover press-scale cursor-pointer ${
                  s.name === summary.recommended_strategy
                    ? "border-emerald-300 bg-emerald-50 dark:bg-emerald-900/20 dark:border-emerald-700"
                    : "border-[var(--color-border-default)]"
                }`}
                onClick={() => navigate("/optimizer")}
              >
                <div className="flex items-center justify-between mb-1">
                  <span className="text-sm font-medium text-[var(--color-text-primary)] capitalize">{s.name.replace(/_/g, " ")}</span>
                  {s.name === summary.recommended_strategy && (
                    <span className="text-xs bg-emerald-100 text-emerald-700 dark:bg-emerald-900/40 dark:text-emerald-300 px-1.5 py-0.5 rounded-full">
                      {t("optimizer.strategy.recommended")}
                    </span>
                  )}
                </div>
                <p className="text-xs text-[var(--color-text-secondary)]">
                  {t("optimizer.interestSaved")}:{" "}
                  <CurrencyDisplay amount={s.interest_saved} compact className="font-medium text-[var(--color-text-primary)]" />
                </p>
                <p className="text-xs text-[var(--color-text-secondary)]">
                  {t("optimizer.monthsSaved")}: <span className="font-medium text-[var(--color-text-primary)]">{s.months_saved}</span>
                </p>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Loan Cards with AI Insights */}
      <div>
        <h2 className="text-lg font-semibold text-[var(--color-text-primary)] mb-3">{t("dashboard.yourLoans")}</h2>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 stagger-children">
          {activeLoans.map((loan) => {
            const insight = insightMap.get(loan.id);
            const isExpanded = expandedInsight === loan.id;
            return (
              <div
                key={loan.id}
                className="bg-[var(--color-bg-card)] rounded-xl shadow-card border border-[var(--color-border-subtle)] overflow-hidden hover:shadow-card-hover transition-shadow"
              >
                <div
                  onClick={() => navigate(`/loans/${loan.id}`)}
                  className="p-4 cursor-pointer hover:bg-[var(--color-bg-subtle)] transition-colors"
                >
                  <div className="flex items-center justify-between mb-3">
                    <span className="font-medium text-[var(--color-text-primary)]">{loan.bank_name}</span>
                    <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${LOAN_TYPE_COLORS[loan.loan_type] || "bg-[var(--color-bg-inset)] text-[var(--color-text-secondary)]"}`}>
                      {loan.loan_type}
                    </span>
                  </div>
                  <div className="space-y-2 text-sm">
                    <div className="flex justify-between">
                      <span className="text-[var(--color-text-secondary)]">{t("loans.outstanding")}</span>
                      <CurrencyDisplay amount={loan.outstanding_principal} className="font-medium text-[var(--color-text-primary)]" />
                    </div>
                    <div className="flex justify-between">
                      <span className="text-[var(--color-text-secondary)]">{t("loans.rate")}</span>
                      <span className="font-medium text-[var(--color-text-primary)]">{loan.interest_rate}%</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-[var(--color-text-secondary)]">{t("loans.emi")}</span>
                      <CurrencyDisplay amount={loan.emi_amount} className="font-medium text-[var(--color-text-primary)]" />
                    </div>
                    <div className="flex justify-between">
                      <span className="text-[var(--color-text-secondary)]">{t("loans.remaining")}</span>
                      <span className="font-medium text-[var(--color-text-primary)]">{formatMonths(loan.remaining_tenure_months)}</span>
                    </div>
                  </div>
                  {/* Progress bar */}
                  <div className="mt-3">
                    <div className="h-1.5 bg-[var(--color-bg-inset)] rounded-full overflow-hidden">
                      <div
                        className="h-full bg-[var(--color-accent)] rounded-full transition-all duration-700 ease-out"
                        style={{ width: `${Math.max(5, (1 - loan.outstanding_principal / loan.principal_amount) * 100)}%` }}
                      />
                    </div>
                    <p className="text-xs text-[var(--color-text-tertiary)] mt-1">
                      {Math.round((1 - loan.outstanding_principal / loan.principal_amount) * 100)}% {t("dashboard.paid")}
                    </p>
                  </div>
                </div>

                {/* AI Insight — shown inline */}
                {insight && (
                  <div
                    className="border-t border-[var(--color-border-subtle)] px-4 py-2.5 cursor-pointer hover:bg-indigo-50/50 dark:hover:bg-indigo-900/20 transition-colors"
                    onClick={(e) => {
                      e.stopPropagation();
                      setExpandedInsight(isExpanded ? null : loan.id);
                    }}
                  >
                    <div className="flex items-start gap-2">
                      <Brain className="w-3.5 h-3.5 text-indigo-500 mt-0.5 flex-shrink-0" />
                      <p className="text-xs text-[var(--color-text-secondary)] leading-relaxed flex-1">
                        {isExpanded ? insight : insight.length > 100 ? insight.slice(0, 100) + "..." : insight}
                      </p>
                      {insight.length > 100 && (
                        isExpanded ? <ChevronUp className="w-3.5 h-3.5 text-[var(--color-text-tertiary)] flex-shrink-0" /> : <ChevronDown className="w-3.5 h-3.5 text-[var(--color-text-tertiary)] flex-shrink-0" />
                      )}
                    </div>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
