import { useState, useMemo } from "react";
import { useTranslation } from "react-i18next";
import { formatCurrency, formatCurrencyCompact } from "../lib/format";
import { useCountryConfig } from "../hooks/useCountryConfig";
import { calculateEMI, calculateTotalInterest } from "../lib/emi-math";

export function EMICalculatorPage() {
  const { t } = useTranslation();
  const config = useCountryConfig();
  const { principal: pRange } = config.sliderRanges;

  const [principal, setPrincipal] = useState(config.code === "US" ? 250000 : 2000000);
  const [rate, setRate] = useState(8.5);
  const [tenureYears, setTenureYears] = useState(20);

  const result = useMemo(() => {
    const tenureMonths = tenureYears * 12;
    const emi = calculateEMI(principal, rate, tenureMonths);
    const totalInterest = calculateTotalInterest(principal, rate, tenureMonths);
    const totalPayment = principal + totalInterest;
    return { emi, totalInterest, totalPayment, tenureMonths };
  }, [principal, rate, tenureYears]);

  const interestPercent = result.totalPayment > 0 ? (result.totalInterest / result.totalPayment) * 100 : 0;
  const fmt = (n: number) => formatCurrency(n, config.code);
  const fmtC = (n: number) => formatCurrencyCompact(n, config.code);

  return (
    <div className="max-w-2xl mx-auto space-y-6">
      <h1 className="text-xl font-bold text-[var(--color-text-primary)]">{t("emi.title")}</h1>

      <div className="bg-[var(--color-bg-card)] rounded-xl p-6 shadow-sm border border-[var(--color-border-subtle)] space-y-6">
        {/* Principal Slider */}
        <div>
          <div className="flex justify-between mb-2">
            <label className="text-sm font-medium text-[var(--color-text-primary)]">{t("emi.principal")}</label>
            <span className="text-sm font-semibold text-[var(--color-accent)]">{fmt(principal)}</span>
          </div>
          <input
            type="range"
            min={pRange.min} max={pRange.max} step={pRange.step}
            value={principal}
            onChange={(e) => setPrincipal(Number(e.target.value))}
            className="w-full h-2 bg-gray-200 rounded-lg appearance-none cursor-pointer accent-blue-600"
          />
          <div className="flex justify-between text-xs text-[var(--color-text-tertiary)] mt-1">
            <span>{fmtC(pRange.min)}</span><span>{fmtC(pRange.max)}</span>
          </div>
        </div>

        {/* Rate Slider */}
        <div>
          <div className="flex justify-between mb-2">
            <label className="text-sm font-medium text-[var(--color-text-primary)]">{t("emi.rate")}</label>
            <span className="text-sm font-semibold text-[var(--color-accent)]">{rate}%</span>
          </div>
          <input
            type="range"
            min={1} max={25} step={0.1}
            value={rate}
            onChange={(e) => setRate(Number(e.target.value))}
            className="w-full h-2 bg-gray-200 rounded-lg appearance-none cursor-pointer accent-blue-600"
          />
          <div className="flex justify-between text-xs text-[var(--color-text-tertiary)] mt-1">
            <span>1%</span><span>25%</span>
          </div>
        </div>

        {/* Tenure Slider */}
        <div>
          <div className="flex justify-between mb-2">
            <label className="text-sm font-medium text-[var(--color-text-primary)]">{t("emi.tenure")}</label>
            <span className="text-sm font-semibold text-[var(--color-accent)]">{tenureYears} years</span>
          </div>
          <input
            type="range"
            min={1} max={30} step={1}
            value={tenureYears}
            onChange={(e) => setTenureYears(Number(e.target.value))}
            className="w-full h-2 bg-gray-200 rounded-lg appearance-none cursor-pointer accent-blue-600"
          />
          <div className="flex justify-between text-xs text-[var(--color-text-tertiary)] mt-1">
            <span>1yr</span><span>30yr</span>
          </div>
        </div>
      </div>

      {/* Results */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="bg-[var(--color-accent-subtle)] rounded-xl p-5 text-center">
          <p className="text-sm text-[var(--color-accent)] mb-1">{t("emi.monthlyEmi")}</p>
          <p className="text-2xl font-bold text-[var(--color-accent-text)]">{fmt(result.emi)}</p>
        </div>
        <div className="bg-red-50 rounded-xl p-5 text-center">
          <p className="text-sm text-red-600 mb-1">{t("emi.totalInterest")}</p>
          <p className="text-2xl font-bold text-red-700">{fmt(result.totalInterest)}</p>
        </div>
        <div className="bg-green-50 rounded-xl p-5 text-center">
          <p className="text-sm text-green-600 mb-1">{t("emi.totalPayment")}</p>
          <p className="text-2xl font-bold text-green-700">{fmt(result.totalPayment)}</p>
        </div>
      </div>

      {/* Visual Breakdown */}
      <div className="bg-[var(--color-bg-card)] rounded-xl p-6 shadow-sm border border-[var(--color-border-subtle)]">
        <h3 className="text-sm font-medium text-[var(--color-text-primary)] mb-3">{t("emi.paymentBreakdown")}</h3>
        <div className="h-6 bg-[var(--color-bg-inset)] rounded-full overflow-hidden flex">
          <div className="bg-blue-500 h-full" style={{ width: `${100 - interestPercent}%` }} />
          <div className="bg-red-400 h-full" style={{ width: `${interestPercent}%` }} />
        </div>
        <div className="flex justify-between mt-2 text-xs">
          <span className="flex items-center gap-1"><span className="w-2 h-2 bg-blue-500 rounded-full" /> {t("loanDetail.principal")} ({Math.round(100 - interestPercent)}%)</span>
          <span className="flex items-center gap-1"><span className="w-2 h-2 bg-red-400 rounded-full" /> {t("loanDetail.interest")} ({Math.round(interestPercent)}%)</span>
        </div>
      </div>
    </div>
  );
}
