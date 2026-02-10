import { useState } from "react";
import { useTranslation } from "react-i18next";
import { X } from "lucide-react";
import { useCountryConfig } from "../../hooks/useCountryConfig";

interface Props {
  onSubmit: (data: any) => void;
  onClose: () => void;
  isLoading?: boolean;
  initialData?: any;
}

export function LoanForm({ onSubmit, onClose, isLoading, initialData }: Props) {
  const { t } = useTranslation();
  const config = useCountryConfig();

  const [form, setForm] = useState({
    bank_name: initialData?.bank_name || "",
    loan_type: initialData?.loan_type || "home",
    loan_amount: initialData?.outstanding_principal || initialData?.principal_amount || "",
    interest_rate: initialData?.interest_rate || "",
    emi_amount: initialData?.emi_amount || "",
  });

  const handleChange = (field: string, value: string) => {
    setForm((prev) => ({ ...prev, [field]: value }));
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const amount = Number(form.loan_amount);
    const rate = Number(form.interest_rate);
    const emi = Number(form.emi_amount);

    // Auto-calculate tenure: n = -log(1 - P*r/EMI) / log(1+r)
    let tenure = 240;
    const r = rate / 12 / 100;
    if (r > 0 && emi > 0 && amount > 0) {
      const ratio = 1 - (amount * r) / emi;
      if (ratio > 0) {
        tenure = Math.ceil(-Math.log(ratio) / Math.log(1 + r));
      }
    }

    // Auto-infer tax deductions from loan type
    const isHome = form.loan_type === "home";
    const isEducation = form.loan_type === "education";

    onSubmit({
      bank_name: form.bank_name,
      loan_type: form.loan_type,
      principal_amount: amount,
      outstanding_principal: amount,
      interest_rate: rate,
      interest_rate_type: "floating",
      tenure_months: Math.min(Math.max(tenure, 1), 600),
      remaining_tenure_months: Math.min(Math.max(tenure, 1), 600),
      emi_amount: emi,
      prepayment_penalty_pct: 0,
      foreclosure_charges_pct: 0,
      eligible_80c: isHome,
      eligible_24b: isHome,
      eligible_80e: isEducation,
      eligible_80eea: false,
    });
  };

  const sym = config.currencySymbol;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
      <div className="bg-[var(--color-bg-card)] rounded-2xl w-full max-w-lg max-h-[90vh] overflow-y-auto animate-scale-in">
        <div className="flex items-center justify-between p-4 border-b border-[var(--color-border-subtle)]">
          <h2 className="text-lg font-semibold text-[var(--color-text-primary)]">{t("loanForm.quickAdd")}</h2>
          <button onClick={onClose} className="p-1 hover:bg-[var(--color-bg-inset)] rounded-lg">
            <X className="w-5 h-5" />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="p-4 space-y-4">
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-[var(--color-text-primary)] mb-1">{t("loans.bank")}</label>
              <select
                value={form.bank_name}
                onChange={(e) => handleChange("bank_name", e.target.value)}
                className="w-full px-3 py-2 border border-[var(--color-border-strong)] rounded-lg text-sm bg-[var(--color-bg-app)] text-[var(--color-text-primary)]"
                required
              >
                <option value="">{t("loanForm.selectBank")}</option>
                {config.banks.map((b) => <option key={b} value={b}>{b}</option>)}
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium text-[var(--color-text-primary)] mb-1">{t("loans.type")}</label>
              <select
                value={form.loan_type}
                onChange={(e) => handleChange("loan_type", e.target.value)}
                className="w-full px-3 py-2 border border-[var(--color-border-strong)] rounded-lg text-sm bg-[var(--color-bg-app)] text-[var(--color-text-primary)] capitalize"
              >
                {config.loanTypes.map((lt) => <option key={lt} value={lt}>{lt.replace("_", " ")}</option>)}
              </select>
            </div>
          </div>

          <div>
            <label className="block text-sm font-medium text-[var(--color-text-primary)] mb-1">{t("loanForm.loanAmount")} ({sym})</label>
            <input
              type="number"
              value={form.loan_amount}
              onChange={(e) => handleChange("loan_amount", e.target.value)}
              className="w-full px-3 py-2 border border-[var(--color-border-strong)] rounded-lg text-sm bg-[var(--color-bg-app)] text-[var(--color-text-primary)]"
              required
              min="1"
              placeholder="e.g. 2500000"
            />
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-[var(--color-text-primary)] mb-1">{t("loanForm.interestRate")}</label>
              <input
                type="number"
                step="0.01"
                value={form.interest_rate}
                onChange={(e) => handleChange("interest_rate", e.target.value)}
                className="w-full px-3 py-2 border border-[var(--color-border-strong)] rounded-lg text-sm bg-[var(--color-bg-app)] text-[var(--color-text-primary)]"
                required
                min="0"
                max="50"
                placeholder="e.g. 8.5"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-[var(--color-text-primary)] mb-1">{t("loanForm.emiAmount")} ({sym})</label>
              <input
                type="number"
                value={form.emi_amount}
                onChange={(e) => handleChange("emi_amount", e.target.value)}
                className="w-full px-3 py-2 border border-[var(--color-border-strong)] rounded-lg text-sm bg-[var(--color-bg-app)] text-[var(--color-text-primary)]"
                required
                min="1"
                placeholder="e.g. 22000"
              />
            </div>
          </div>

          <button
            type="submit"
            disabled={isLoading}
            className="w-full py-2.5 bg-[var(--color-accent)] text-white rounded-lg font-medium hover:bg-[var(--color-accent-hover)] disabled:opacity-50"
          >
            {isLoading ? t("loanForm.saving") : t("loanForm.saveLoan")}
          </button>
        </form>
      </div>
    </div>
  );
}
