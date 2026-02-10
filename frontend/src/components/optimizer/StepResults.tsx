import { useState, useEffect } from "react";
import { useTranslation } from "react-i18next";
import { useMutation } from "@tanstack/react-query";
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from "recharts";
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
        config: { monthly_extra: 0 },
        results: { interest_saved: selected?.interest_saved_vs_baseline, months_saved: selected?.months_saved_vs_baseline },
      }),
    onSuccess: () => setSaved(true),
  });

  const chartData = results.strategies.map((s) => ({
    name: s.strategy_name,
    interestSaved: Number(s.interest_saved_vs_baseline),
    monthsSaved: s.months_saved_vs_baseline,
    totalMonths: s.total_months,
  }));

  return (
    <div className="space-y-6">
      {/* Hero Banner */}
      {selected && (
        <div className="text-center py-6 bg-gradient-to-r from-green-50 to-emerald-50 rounded-xl border border-green-200">
          <p className="text-sm text-green-600 mb-1">{selected.strategy_description}</p>
          <p className="text-4xl font-bold text-green-700 mb-2">
            {t("optimizer.results.youSave")} {fmt(Number(selected.interest_saved_vs_baseline))}
          </p>
          <p className="text-gray-600">
            {t("optimizer.results.debtFree")} {selected.months_saved_vs_baseline} {t("optimizer.results.monthsEarlier")} ({formatMonths(selected.total_months)} → {formatMonths(results.baseline_total_months)})
          </p>
        </div>
      )}

      {/* Strategy Comparison Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
        {results.strategies.map((s) => (
          <div
            key={s.strategy_name}
            className={`p-4 rounded-xl border-2 ${
              s.strategy_name === results.recommended_strategy
                ? "border-purple-300 bg-purple-50"
                : "border-gray-200"
            }`}
          >
            <div className="flex items-center justify-between mb-2">
              <span className="font-semibold text-gray-900 capitalize">{s.strategy_name.replace("_", " ")}</span>
              {s.strategy_name === results.recommended_strategy && (
                <span className="text-xs bg-purple-100 text-purple-700 px-2 py-0.5 rounded-full">{t("optimizer.results.best")}</span>
              )}
            </div>
            <div className="grid grid-cols-2 gap-2 text-sm">
              <div>
                <p className="text-gray-400">{t("optimizer.interestSaved")}</p>
                <p className="font-semibold text-green-600">{fmtC(Number(s.interest_saved_vs_baseline))}</p>
              </div>
              <div>
                <p className="text-gray-400">{t("optimizer.monthsSaved")}</p>
                <p className="font-semibold text-blue-600">{s.months_saved_vs_baseline} {t("common.months")}</p>
              </div>
            </div>
            {/* Payoff order */}
            <div className="mt-2">
              <p className="text-xs text-gray-400">{t("optimizer.results.payoffOrder")}:</p>
              <p className="text-xs text-gray-600">{s.payoff_order.join(" → ")}</p>
            </div>
          </div>
        ))}
      </div>

      {/* Comparison Chart */}
      <div className="bg-white rounded-xl p-4 border border-gray-100">
        <h3 className="font-semibold text-gray-900 mb-4">{t("optimizer.results.comparison")}</h3>
        <ResponsiveContainer width="100%" height={250}>
          <LineChart data={chartData}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="name" tick={{ fontSize: 12 }} />
            <YAxis
              tickFormatter={(v) => fmtC(v)}
              tick={{ fontSize: 12 }}
            />
            <Tooltip formatter={(value) => fmt(Number(value))} />
            <Line type="monotone" dataKey="interestSaved" stroke="#22c55e" strokeWidth={2} name={t("optimizer.interestSaved")} />
          </LineChart>
        </ResponsiveContainer>
      </div>

      {/* Rate Sensitivity Analysis */}
      {sensitivity && sensitivity.points.length > 0 && (
        <div className="bg-white rounded-xl p-4 border border-gray-100">
          <h3 className="font-semibold text-gray-900 mb-4">{t("optimizer.results.sensitivityTitle")}</h3>
          <p className="text-xs text-gray-400 mb-3">{t("optimizer.results.sensitivityDesc")}</p>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b text-left text-gray-500">
                  <th className="py-2 pr-4">{t("optimizer.results.rateChange")}</th>
                  <th className="py-2 pr-4">{t("optimizer.results.totalInterest")}</th>
                  <th className="py-2 pr-4">{t("optimizer.results.totalMonths")}</th>
                  <th className="py-2">{t("optimizer.interestSaved")}</th>
                </tr>
              </thead>
              <tbody>
                {sensitivity.points.map((p) => (
                  <tr key={p.rate_delta_pct} className={`border-b last:border-0 ${p.rate_delta_pct === 0 ? "bg-blue-50 font-medium" : ""}`}>
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

      {/* Save Plan */}
      <button
        onClick={() => saveMutation.mutate()}
        disabled={saveMutation.isPending || saved}
        className="w-full py-3 bg-blue-600 text-white rounded-xl font-medium hover:bg-blue-700 disabled:opacity-50"
      >
        {saved ? t("optimizer.results.planSaved") : saveMutation.isPending ? t("common.saving") : t("optimizer.savePlan")}
      </button>
    </div>
  );
}
