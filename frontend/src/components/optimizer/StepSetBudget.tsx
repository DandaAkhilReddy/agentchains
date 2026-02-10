import { useState } from "react";
import { useTranslation } from "react-i18next";
import { formatCurrency } from "../../lib/format";
import { useCountryConfig } from "../../hooks/useCountryConfig";

interface Props {
  monthlyExtra: number;
  onMonthlyExtraChange: (value: number) => void;
  lumpSums: { month: number; amount: number }[];
  onLumpSumsChange: (sums: { month: number; amount: number }[]) => void;
  annualGrowthPct: number;
  onAnnualGrowthPctChange: (value: number) => void;
}

export function StepSetBudget({ monthlyExtra, onMonthlyExtraChange, lumpSums, onLumpSumsChange, annualGrowthPct, onAnnualGrowthPctChange }: Props) {
  const { t } = useTranslation();
  const config = useCountryConfig();
  const fmt = (n: number) => formatCurrency(n, config.code);

  const { dailySaving: dRange, monthlyExtra: mRange, lumpSumDefault } = config.sliderRanges;
  const [budgetMode, setBudgetMode] = useState(false);
  const [dailySaving, setDailySaving] = useState(dRange.min * 10); // sensible default

  const handleBudgetModeToggle = () => {
    if (!budgetMode) {
      onMonthlyExtraChange(dailySaving * 30);
    }
    setBudgetMode(!budgetMode);
  };

  const handleDailyChange = (value: number) => {
    setDailySaving(value);
    if (budgetMode) onMonthlyExtraChange(value * 30);
  };

  const addLumpSum = () => {
    onLumpSumsChange([...lumpSums, { month: 6, amount: lumpSumDefault }]);
  };

  return (
    <div className="space-y-6">
      <h2 className="font-semibold text-gray-900">{t("optimizer.budget.howMuchExtra")}</h2>

      {/* Budget Mode Toggle (Gullak / Piggy Bank) */}
      <div className="flex items-center justify-between p-4 bg-amber-50 rounded-xl border border-amber-200">
        <div>
          <p className="font-medium text-amber-800">{t(config.budgetModeKey)}</p>
          <p className="text-sm text-amber-600">{t("optimizer.budget.budgetModeDesc")}</p>
        </div>
        <button
          onClick={handleBudgetModeToggle}
          className={`relative w-12 h-6 rounded-full transition-colors ${budgetMode ? "bg-amber-500" : "bg-gray-300"}`}
        >
          <span className={`absolute top-0.5 w-5 h-5 bg-white rounded-full shadow transition-transform ${budgetMode ? "translate-x-6" : "translate-x-0.5"}`} />
        </button>
      </div>

      {budgetMode ? (
        <div>
          <div className="flex justify-between mb-2">
            <label className="text-sm font-medium text-gray-700">{t("optimizer.budget.dailySaving")}</label>
            <span className="text-sm font-semibold text-amber-600">{fmt(dailySaving)}/{t("common.day")} = {fmt(dailySaving * 30)}/{t("common.month")}</span>
          </div>
          <input
            type="range" min={dRange.min} max={dRange.max} step={dRange.step}
            value={dailySaving}
            onChange={(e) => handleDailyChange(Number(e.target.value))}
            className="w-full h-2 bg-gray-200 rounded-lg appearance-none cursor-pointer accent-amber-500"
          />
          <div className="flex justify-between text-xs text-gray-400 mt-1">
            <span>{fmt(dRange.min)}/{t("common.day")}</span><span>{fmt(dRange.max)}/{t("common.day")}</span>
          </div>
        </div>
      ) : (
        <div>
          <div className="flex justify-between mb-2">
            <label className="text-sm font-medium text-gray-700">{t("optimizer.budget.monthlyExtra")}</label>
            <span className="text-sm font-semibold text-blue-600">{fmt(monthlyExtra)}</span>
          </div>
          <input
            type="range" min={mRange.min} max={mRange.max} step={mRange.step}
            value={monthlyExtra}
            onChange={(e) => onMonthlyExtraChange(Number(e.target.value))}
            className="w-full h-2 bg-gray-200 rounded-lg appearance-none cursor-pointer accent-blue-600"
          />
          <div className="flex justify-between text-xs text-gray-400 mt-1">
            <span>{fmt(mRange.min)}</span><span>{fmt(mRange.max)}</span>
          </div>
        </div>
      )}

      {/* Salary Growth */}
      <div>
        <div className="flex justify-between mb-2">
          <label className="text-sm font-medium text-gray-700">{t("optimizer.budget.salaryGrowth")}</label>
          <span className="text-sm font-semibold text-emerald-600">{annualGrowthPct}% / {t("optimizer.budget.year")}</span>
        </div>
        <input
          type="range" min={0} max={30} step={1}
          value={annualGrowthPct}
          onChange={(e) => onAnnualGrowthPctChange(Number(e.target.value))}
          className="w-full h-2 bg-gray-200 rounded-lg appearance-none cursor-pointer accent-emerald-600"
        />
        <div className="flex justify-between text-xs text-gray-400 mt-1">
          <span>0%</span><span>30%</span>
        </div>
        <p className="text-xs text-gray-400 mt-1">{t("optimizer.budget.salaryGrowthDesc")}</p>
      </div>

      {/* Lump Sums */}
      <div>
        <div className="flex items-center justify-between mb-2">
          <label className="text-sm font-medium text-gray-700">{t("optimizer.budget.lumpSum")}</label>
          <button onClick={addLumpSum} className="text-sm text-blue-600 hover:text-blue-700">+ {t("optimizer.budget.add")}</button>
        </div>
        {lumpSums.map((ls, i) => (
          <div key={i} className="flex gap-3 mb-2">
            <div className="flex-1">
              <input
                type="number" placeholder={t("optimizer.budget.amount")}
                value={ls.amount}
                onChange={(e) => {
                  const updated = [...lumpSums];
                  updated[i].amount = Number(e.target.value);
                  onLumpSumsChange(updated);
                }}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm"
              />
            </div>
            <div className="w-24">
              <input
                type="number" placeholder={t("optimizer.budget.month")}
                value={ls.month}
                onChange={(e) => {
                  const updated = [...lumpSums];
                  updated[i].month = Number(e.target.value);
                  onLumpSumsChange(updated);
                }}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm"
              />
            </div>
            <button
              onClick={() => onLumpSumsChange(lumpSums.filter((_, j) => j !== i))}
              className="text-red-500 hover:text-red-600 text-sm"
            >
              {t("optimizer.budget.remove")}
            </button>
          </div>
        ))}
      </div>
    </div>
  );
}
