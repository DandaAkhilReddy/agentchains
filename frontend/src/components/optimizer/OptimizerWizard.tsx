import { useState } from "react";
import { useTranslation } from "react-i18next";
import { useMutation } from "@tanstack/react-query";
import api from "../../lib/api";
import { useCountryConfig } from "../../hooks/useCountryConfig";
import type { Loan, OptimizationResult } from "../../types";
import { StepSelectLoans } from "./StepSelectLoans";
import { StepSetBudget } from "./StepSetBudget";
import { StepChooseStrategy } from "./StepChooseStrategy";
import { StepResults } from "./StepResults";

interface Props {
  loans: Loan[];
}

export function OptimizerWizard({ loans }: Props) {
  const { t } = useTranslation();
  const config = useCountryConfig();
  const [step, setStep] = useState(0);
  const [selectedLoanIds, setSelectedLoanIds] = useState<string[]>(loans.map((l) => l.id));
  const [monthlyExtra, setMonthlyExtra] = useState(config.sliderRanges.monthlyExtra.max / 10);
  const [lumpSums, setLumpSums] = useState<{ month: number; amount: number }[]>([]);
  const [strategy, setStrategy] = useState("smart_hybrid");
  const [annualGrowthPct, setAnnualGrowthPct] = useState(0);
  const [results, setResults] = useState<OptimizationResult | null>(null);

  const steps = [
    t("optimizer.wizard.stepSelectLoans"),
    t("optimizer.wizard.stepSetBudget"),
    t("optimizer.wizard.stepChooseStrategy"),
    t("optimizer.wizard.stepResults"),
  ];

  const analyzeMutation = useMutation({
    mutationFn: () =>
      api.post("/api/optimizer/analyze", {
        loan_ids: selectedLoanIds,
        monthly_extra: monthlyExtra,
        lump_sums: lumpSums,
        strategies: ["avalanche", "snowball", "smart_hybrid", "proportional"],
        annual_growth_pct: annualGrowthPct,
      }).then((r) => r.data),
    onSuccess: (data) => {
      setResults(data);
      setStep(3);
    },
  });

  const handleNext = () => {
    if (step === 2) {
      analyzeMutation.mutate();
    } else {
      setStep((s) => Math.min(s + 1, 3));
    }
  };

  const handleBack = () => setStep((s) => Math.max(s - 1, 0));

  return (
    <div className="max-w-3xl mx-auto space-y-6">
      <h1 className="text-xl font-bold text-[var(--color-text-primary)]">{t("optimizer.title")}</h1>

      {/* Progress Steps */}
      <div className="flex items-center gap-2">
        {steps.map((label, i) => (
          <div key={i} className="flex items-center gap-2 flex-1">
            <div className={`w-8 h-8 rounded-full flex items-center justify-center text-sm font-medium ${
              i <= step ? "bg-[var(--color-accent)] text-white" : "bg-gray-200 text-[var(--color-text-secondary)]"
            }`}>
              {i + 1}
            </div>
            <span className={`text-sm hidden md:block ${i <= step ? "text-[var(--color-accent)] font-medium" : "text-[var(--color-text-tertiary)]"}`}>
              {label}
            </span>
            {i < steps.length - 1 && <div className={`flex-1 h-0.5 ${i < step ? "bg-[var(--color-accent)]" : "bg-gray-200"}`} />}
          </div>
        ))}
      </div>

      {/* Step Content */}
      <div className="bg-[var(--color-bg-card)] rounded-xl p-6 shadow-sm border border-[var(--color-border-subtle)] min-h-[300px]">
        {step === 0 && (
          <StepSelectLoans
            loans={loans}
            selected={selectedLoanIds}
            onChange={setSelectedLoanIds}
          />
        )}
        {step === 1 && (
          <StepSetBudget
            monthlyExtra={monthlyExtra}
            onMonthlyExtraChange={setMonthlyExtra}
            lumpSums={lumpSums}
            onLumpSumsChange={setLumpSums}
            annualGrowthPct={annualGrowthPct}
            onAnnualGrowthPctChange={setAnnualGrowthPct}
          />
        )}
        {step === 2 && (
          <StepChooseStrategy selected={strategy} onChange={setStrategy} />
        )}
        {step === 3 && results && (
          <StepResults
            results={results}
            selectedStrategy={strategy}
            loanIds={selectedLoanIds}
            monthlyExtra={monthlyExtra}
            lumpSums={lumpSums}
            annualGrowthPct={annualGrowthPct}
          />
        )}
      </div>

      {/* Navigation */}
      <div className="flex justify-between">
        <button
          onClick={handleBack}
          disabled={step === 0}
          className="press-scale px-6 py-2.5 border border-[var(--color-border-strong)] rounded-lg text-sm font-medium text-[var(--color-text-primary)] hover:bg-[var(--color-bg-subtle)] disabled:opacity-30"
        >
          {t("common.back")}
        </button>
        {step < 3 && (
          <button
            onClick={handleNext}
            disabled={selectedLoanIds.length === 0 || analyzeMutation.isPending}
            className="press-scale px-6 py-2.5 bg-[var(--color-accent)] text-white rounded-lg text-sm font-medium hover:bg-[var(--color-accent-hover)] disabled:opacity-50"
          >
            {analyzeMutation.isPending ? t("optimizer.wizard.analyzing") : step === 2 ? t("optimizer.wizard.runOptimizer") : t("common.next")}
          </button>
        )}
      </div>
    </div>
  );
}
