import { useState } from "react";
import { useTranslation } from "react-i18next";
import { useMutation } from "@tanstack/react-query";
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from "recharts";
import api from "../../lib/api";
import { formatINR, formatINRCompact, formatMonths } from "../../lib/format";
import type { OptimizationResult } from "../../types";

interface Props {
  results: OptimizationResult;
  selectedStrategy: string;
}

export function StepResults({ results, selectedStrategy }: Props) {
  const { t } = useTranslation();
  const [saved, setSaved] = useState(false);

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

  // Build chart data from monthly snapshots (sample every N months for performance)
  // Since we don't have snapshots in the response type, we'll show strategy comparison
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
          <p className="text-sm text-green-600 mb-1">With {selected.strategy_description}</p>
          <p className="text-4xl font-bold text-green-700 mb-2">
            You save {formatINR(Number(selected.interest_saved_vs_baseline))}!
          </p>
          <p className="text-gray-600">
            Debt-free {selected.months_saved_vs_baseline} months earlier ({formatMonths(selected.total_months)} instead of {formatMonths(results.baseline_total_months)})
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
                <span className="text-xs bg-purple-100 text-purple-700 px-2 py-0.5 rounded-full">Best</span>
              )}
            </div>
            <div className="grid grid-cols-2 gap-2 text-sm">
              <div>
                <p className="text-gray-400">{t("optimizer.interestSaved")}</p>
                <p className="font-semibold text-green-600">{formatINRCompact(Number(s.interest_saved_vs_baseline))}</p>
              </div>
              <div>
                <p className="text-gray-400">{t("optimizer.monthsSaved")}</p>
                <p className="font-semibold text-blue-600">{s.months_saved_vs_baseline} months</p>
              </div>
            </div>
            {/* Payoff order */}
            <div className="mt-2">
              <p className="text-xs text-gray-400">Payoff order:</p>
              <p className="text-xs text-gray-600">{s.payoff_order.join(" → ")}</p>
            </div>
          </div>
        ))}
      </div>

      {/* Comparison Chart */}
      <div className="bg-white rounded-xl p-4 border border-gray-100">
        <h3 className="font-semibold text-gray-900 mb-4">Strategy Comparison</h3>
        <ResponsiveContainer width="100%" height={250}>
          <LineChart data={chartData}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="name" tick={{ fontSize: 12 }} />
            <YAxis
              tickFormatter={(v) => formatINRCompact(v)}
              tick={{ fontSize: 12 }}
            />
            <Tooltip formatter={(value) => formatINR(Number(value))} />
            <Line type="monotone" dataKey="interestSaved" stroke="#22c55e" strokeWidth={2} name="Interest Saved" />
          </LineChart>
        </ResponsiveContainer>
      </div>

      {/* Save Plan */}
      <button
        onClick={() => saveMutation.mutate()}
        disabled={saveMutation.isPending || saved}
        className="w-full py-3 bg-blue-600 text-white rounded-xl font-medium hover:bg-blue-700 disabled:opacity-50"
      >
        {saved ? "Plan Saved!" : saveMutation.isPending ? "Saving..." : t("optimizer.savePlan")}
      </button>
    </div>
  );
}
