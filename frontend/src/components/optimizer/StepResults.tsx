import { useState, useEffect, useMemo } from "react";
import { useTranslation } from "react-i18next";
import { useMutation } from "@tanstack/react-query";
import { Target, Lightbulb, ArrowRight } from "lucide-react";
import api from "../../lib/api";
import { formatCurrency, formatCurrencyCompact, formatMonths } from "../../lib/format";
import { useCountryConfig } from "../../hooks/useCountryConfig";
import type { OptimizationResult, SensitivityResult } from "../../types";

interface Props {
  results: OptimizationResult;
  selectedStrategy: string;
  loanIds: string[];
  monthlyExtra: number;
  lumpSums: { month: number; amount: number }[];
  annualGrowthPct: number;
}

const LOAN_TYPE_COLORS: Record<string, string> = {
  home: "bg-blue-500",
  personal: "bg-purple-500",
  car: "bg-green-500",
  education: "bg-amber-500",
  gold: "bg-yellow-500",
  credit_card: "bg-red-500",
  business: "bg-indigo-500",
};

export function StepResults({ results, selectedStrategy, loanIds, monthlyExtra, lumpSums, annualGrowthPct }: Props) {
  const { t } = useTranslation();
  const config = useCountryConfig();
  const [saved, setSaved] = useState(false);
  const [sensitivity, setSensitivity] = useState<SensitivityResult | null>(null);

  useEffect(() => {
    api.post("/api/optimizer/sensitivity", {
      loan_ids: loanIds,
      monthly_extra: monthlyExtra,
      lump_sums: lumpSums,
      strategy: results.recommended_strategy,
      annual_growth_pct: annualGrowthPct,
    }).then((r) => setSensitivity(r.data)).catch(() => {});
  }, [loanIds, monthlyExtra, lumpSums, annualGrowthPct, results.recommended_strategy]);

  const fmt = (n: number) => formatCurrency(n, config.code);
  const fmtC = (n: number) => formatCurrencyCompact(n, config.code);

  const best = results.strategies.find((s) => s.strategy_name === results.recommended_strategy);
  const selected = results.strategies.find((s) => s.strategy_name === selectedStrategy) || best;

  const saveMutation = useMutation({
    mutationFn: () =>
      api.post("/api/optimizer/save-plan", {
        name: `${selected?.strategy_name} plan`,
        strategy: selected?.strategy_name,
        config: { monthly_extra: monthlyExtra },
        results: { interest_saved: selected?.interest_saved_vs_baseline, months_saved: selected?.months_saved_vs_baseline },
      }),
    onSuccess: () => setSaved(true),
  });

  // Build actionable advice items
  const advice = useMemo(() => {
    if (!selected) return [];
    const items: string[] = [];
    const lr = selected.loan_results;
    if (lr.length > 0) {
      const first = lr.sort((a, b) => a.payoff_month - b.payoff_month)[0];
      items.push(t("optimizer.results.actionFocus", { bank: first.bank_name, type: first.loan_type }));
      items.push(t("optimizer.results.actionPaidOff", { bank: first.bank_name, month: first.payoff_month, saved: first.months_saved }));
      if (lr.length > 1) {
        items.push(t("optimizer.results.actionFreedEmi", { bank: first.bank_name, emi: fmtC(first.original_balance / Math.max(first.payoff_month, 1)) }));
      }
    }
    if (lumpSums.length > 0) {
      const ls = lumpSums[0];
      items.push(t("optimizer.results.actionLumpSum", { amount: fmtC(ls.amount), month: ls.month }));
    }
    if (sensitivity && sensitivity.points.length > 0) {
      const oneUp = sensitivity.points.find((p) => p.rate_delta_pct === 1);
      const baseline = sensitivity.points.find((p) => p.rate_delta_pct === 0);
      if (oneUp && baseline) {
        const diff = Number(oneUp.total_interest_paid) - Number(baseline.total_interest_paid);
        if (diff > 0) {
          items.push(t("optimizer.results.actionRateLock", { cost: fmtC(diff) }));
        }
      }
    }
    return items;
  }, [selected, sensitivity, lumpSums, t, fmtC]);

  // Max payoff month for timeline scaling
  const maxPayoff = selected ? Math.max(...selected.loan_results.map((l) => l.payoff_month), 1) : 1;

  return (
    <div className="space-y-6">
      {/* ─── Hero Banner with Before/After ─── */}
      {selected && (
        <div className="py-6 bg-gradient-to-r from-green-50 to-emerald-50 rounded-xl border border-green-200">
          <div className="text-center mb-4">
            <p className="text-sm text-green-600 mb-1">{selected.strategy_description}</p>
            <p className="text-4xl font-bold text-green-700">
              {t("optimizer.results.youSave")} {fmt(Number(selected.interest_saved_vs_baseline))}
            </p>
            <p className="text-[var(--color-text-secondary)] mt-1">
              {t("optimizer.results.debtFree")} {selected.months_saved_vs_baseline} {t("optimizer.results.monthsEarlier")}
            </p>
          </div>
          {/* Before / After comparison */}
          <div className="grid grid-cols-2 gap-3 px-6">
            <div className="bg-[var(--color-bg-card)]/70 rounded-lg p-3 text-center border border-[var(--color-border-default)]">
              <p className="text-xs text-[var(--color-text-secondary)] mb-1">{t("optimizer.results.withoutPlan")}</p>
              <p className="text-lg font-bold text-[var(--color-text-primary)]">{fmtC(Number(results.baseline_total_interest))}</p>
              <p className="text-xs text-[var(--color-text-tertiary)]">{formatMonths(results.baseline_total_months)}</p>
            </div>
            <div className="bg-[var(--color-bg-card)]/70 rounded-lg p-3 text-center border border-green-200">
              <p className="text-xs text-green-600 mb-1">{t("optimizer.results.withPlan")}</p>
              <p className="text-lg font-bold text-green-700">{fmtC(Number(selected.total_interest_paid))}</p>
              <p className="text-xs text-green-500">{formatMonths(selected.total_months)}</p>
            </div>
          </div>
        </div>
      )}

      {/* ─── Payoff Timeline ─── */}
      {selected && selected.loan_results.length > 0 && (
        <div className="bg-[var(--color-bg-card)] rounded-xl p-4 border border-[var(--color-border-subtle)]">
          <h3 className="font-semibold text-[var(--color-text-primary)] mb-4 flex items-center gap-2">
            <Target className="w-4 h-4 text-blue-500" />
            {t("optimizer.results.payoffTimeline")}
          </h3>
          <div className="space-y-3">
            {[...selected.loan_results]
              .sort((a, b) => a.payoff_month - b.payoff_month)
              .map((loan) => {
                const pct = Math.max((loan.payoff_month / maxPayoff) * 100, 8);
                const color = LOAN_TYPE_COLORS[loan.loan_type] || "bg-gray-500";
                return (
                  <div key={loan.loan_id}>
                    <div className="flex items-center justify-between text-sm mb-1">
                      <span className="font-medium text-[var(--color-text-primary)]">{loan.bank_name}</span>
                      <span className="text-xs text-[var(--color-text-tertiary)]">
                        {t("optimizer.results.paidOffMonth", { month: loan.payoff_month })}
                        {loan.months_saved > 0 && (
                          <span className="text-green-600 ml-1">
                            ({t("optimizer.results.savedMonths", { months: loan.months_saved })})
                          </span>
                        )}
                      </span>
                    </div>
                    <div className="w-full bg-[var(--color-bg-inset)] rounded-full h-3 overflow-hidden">
                      <div
                        className={`h-full rounded-full ${color} transition-all duration-500`}
                        style={{ width: `${pct}%` }}
                      />
                    </div>
                  </div>
                );
              })}
          </div>
          <div className="flex justify-between text-xs text-[var(--color-text-tertiary)] mt-2">
            <span>0</span>
            <span>{maxPayoff} {t("common.months")}</span>
          </div>
        </div>
      )}

      {/* ─── Actionable Advice ─── */}
      {advice.length > 0 && (
        <div className="bg-amber-50 rounded-xl p-4 border border-amber-200">
          <h3 className="font-semibold text-[var(--color-text-primary)] mb-3 flex items-center gap-2">
            <Lightbulb className="w-4 h-4 text-amber-500" />
            {t("optimizer.results.actionPlan")}
          </h3>
          <ol className="space-y-2">
            {advice.map((item, i) => (
              <li key={i} className="flex items-start gap-2 text-sm text-[var(--color-text-primary)]">
                <span className="flex-shrink-0 w-5 h-5 rounded-full bg-amber-200 text-amber-800 text-xs flex items-center justify-center font-semibold mt-0.5">
                  {i + 1}
                </span>
                <span>{item}</span>
              </li>
            ))}
          </ol>
        </div>
      )}

      {/* ─── Strategy Comparison Cards ─── */}
      <div>
        <h3 className="font-semibold text-[var(--color-text-primary)] mb-3">{t("optimizer.results.comparison")}</h3>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          {results.strategies.map((s) => (
            <div
              key={s.strategy_name}
              className={`p-4 rounded-xl border-2 ${
                s.strategy_name === results.recommended_strategy
                  ? "border-purple-300 bg-purple-50 dark:bg-purple-900/20 dark:border-purple-700"
                  : "border-[var(--color-border-default)]"
              }`}
            >
              <div className="flex items-center justify-between mb-2">
                <span className="font-semibold text-[var(--color-text-primary)] capitalize">{s.strategy_name.replace("_", " ")}</span>
                {s.strategy_name === results.recommended_strategy && (
                  <span className="text-xs bg-purple-100 text-purple-700 px-2 py-0.5 rounded-full">{t("optimizer.results.best")}</span>
                )}
              </div>
              <div className="grid grid-cols-2 gap-2 text-sm">
                <div>
                  <p className="text-[var(--color-text-tertiary)]">{t("optimizer.interestSaved")}</p>
                  <p className="font-semibold text-green-600">{fmtC(Number(s.interest_saved_vs_baseline))}</p>
                </div>
                <div>
                  <p className="text-[var(--color-text-tertiary)]">{t("optimizer.monthsSaved")}</p>
                  <p className="font-semibold text-blue-600">{s.months_saved_vs_baseline} {t("common.months")}</p>
                </div>
              </div>
              {/* Per-loan breakdown */}
              {s.loan_results.length > 0 && (
                <div className="mt-3 pt-2 border-t border-[var(--color-border-default)]">
                  <p className="text-xs text-[var(--color-text-tertiary)] mb-1">{t("optimizer.results.perLoanBreakdown")}</p>
                  {s.loan_results.map((lr) => (
                    <div key={lr.loan_id} className="flex items-center justify-between text-xs text-[var(--color-text-secondary)] py-0.5">
                      <span>{lr.bank_name} <span className="text-[var(--color-text-tertiary)]">({lr.loan_type})</span></span>
                      <span className="flex items-center gap-1">
                        <ArrowRight className="w-3 h-3 text-[var(--color-text-tertiary)]" />
                        <span>{t("optimizer.results.paidOffMonth", { month: lr.payoff_month })}</span>
                        {lr.months_saved > 0 && (
                          <span className="text-green-600">-{lr.months_saved}mo</span>
                        )}
                      </span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          ))}
        </div>
      </div>

      {/* ─── Rate Sensitivity Analysis ─── */}
      {sensitivity && sensitivity.points.length > 0 && (
        <div className="bg-[var(--color-bg-card)] rounded-xl p-4 border border-[var(--color-border-subtle)]">
          <h3 className="font-semibold text-[var(--color-text-primary)] mb-4">{t("optimizer.results.sensitivityTitle")}</h3>
          <p className="text-xs text-[var(--color-text-tertiary)] mb-3">{t("optimizer.results.sensitivityDesc")}</p>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-[var(--color-border-default)] text-left text-[var(--color-text-secondary)]">
                  <th className="py-2 pr-4">{t("optimizer.results.rateChange")}</th>
                  <th className="py-2 pr-4">{t("optimizer.results.totalInterest")}</th>
                  <th className="py-2 pr-4">{t("optimizer.results.totalMonths")}</th>
                  <th className="py-2">{t("optimizer.interestSaved")}</th>
                </tr>
              </thead>
              <tbody>
                {sensitivity.points.map((p) => (
                  <tr key={p.rate_delta_pct} className={`border-b border-[var(--color-border-subtle)] last:border-0 ${p.rate_delta_pct === 0 ? "bg-[var(--color-accent-subtle)] font-medium" : ""}`}>
                    <td className="py-2 pr-4">{p.rate_delta_pct > 0 ? "+" : ""}{p.rate_delta_pct}%</td>
                    <td className="py-2 pr-4">{fmtC(Number(p.total_interest_paid))}</td>
                    <td className="py-2 pr-4">{formatMonths(p.total_months)}</td>
                    <td className="py-2 text-green-600">{fmtC(Number(p.interest_saved_vs_baseline))}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* ─── Save Plan ─── */}
      <button
        onClick={() => saveMutation.mutate()}
        disabled={saveMutation.isPending || saved}
        className="w-full py-3 bg-[var(--color-accent)] text-white rounded-xl font-medium hover:bg-[var(--color-accent-hover)] disabled:opacity-50 press-scale"
      >
        {saved ? t("optimizer.results.planSaved") : saveMutation.isPending ? t("common.saving") : t("optimizer.savePlan")}
      </button>
    </div>
  );
}
