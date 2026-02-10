import { useState, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { useDropzone } from "react-dropzone";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { FileText, Sparkles, AlertCircle, RotateCcw, PenLine } from "lucide-react";
import api from "../lib/api";
import { useToastStore } from "../store/toastStore";
import { useCountryStore } from "../store/countryStore";
import { useCountryConfig } from "../hooks/useCountryConfig";

export function ScanDocumentPage() {
  const navigate = useNavigate();
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const { addToast } = useToastStore();
  const { country, setCountry } = useCountryStore();
  const config = useCountryConfig();
  const [showManualForm, setShowManualForm] = useState(false);
  const [scanFailed, setScanFailed] = useState(false);
  const [scanError, setScanError] = useState<string | null>(null);

  // Manual form state — 5 fields only
  const [form, setForm] = useState({
    bank_name: "",
    loan_type: "home",
    loan_amount: "",
    interest_rate: "",
    emi_amount: "",
  });

  const uploadMutation = useMutation({
    mutationFn: async (file: File) => {
      const formData = new FormData();
      formData.append("file", file);
      const res = await api.post("/api/scanner/upload", formData, {
        headers: { "Content-Type": "multipart/form-data" },
      });
      return res.data;
    },
    onSuccess: (data) => {
      // Auto-switch country if document was from a different currency
      if (data.detected_country && data.detected_country !== country) {
        setCountry(data.detected_country as "IN" | "US");
        const countryName = data.detected_country === "US" ? "United States" : "India";
        addToast({ type: "info", message: t("scanner.countryAutoSwitched", { country: countryName }) });
      }

      if (data.loan_id) {
        addToast({ type: "success", message: t("scanner.loanCreated") });
        queryClient.invalidateQueries({ queryKey: ["loans"] });
        navigate("/");
      } else {
        setScanError(data.error || null);
        setScanFailed(true);
      }
    },
    onError: (err: unknown) => {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      setScanError(msg || null);
      setScanFailed(true);
    },
  });

  const createLoanMutation = useMutation({
    mutationFn: (data: Record<string, unknown>) => api.post("/api/loans", data),
    onSuccess: () => {
      addToast({ type: "success", message: t("scanner.loanCreated") });
      queryClient.invalidateQueries({ queryKey: ["loans"] });
      navigate("/");
    },
  });

  const onDrop = useCallback((files: File[]) => {
    if (files[0]) {
      setScanFailed(false);
      setScanError(null);
      uploadMutation.mutate(files[0]);
    }
  }, []);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: {
      "application/pdf": [".pdf"],
      "image/png": [".png"],
      "image/jpeg": [".jpg", ".jpeg"],
    },
    maxSize: 10 * 1024 * 1024,
    maxFiles: 1,
  });

  const handleManualSubmit = (e: React.FormEvent) => {
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

    createLoanMutation.mutate({
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
    <div className="max-w-2xl mx-auto space-y-6 animate-fade-up">
      <h1 className="text-xl font-bold text-[var(--color-text-primary)]">{t("nav.addLoan")}</h1>

      {/* Upload Zone — shown when not scanning and not showing manual form exclusively */}
      {!uploadMutation.isPending && !scanFailed && !showManualForm && (
        <div
          {...getRootProps()}
          className={`border-2 border-dashed rounded-xl p-12 text-center cursor-pointer transition-colors ${
            isDragActive ? "border-blue-400 bg-[var(--color-accent-subtle)]" : "border-[var(--color-border-strong)] hover:border-blue-300 hover:bg-[var(--color-bg-subtle)]"
          }`}
        >
          <input {...getInputProps()} />
          <FileText className="w-12 h-12 text-[var(--color-text-tertiary)] mx-auto mb-4" />
          <p className="font-medium text-[var(--color-text-primary)] mb-1">
            {isDragActive ? t("scanner.dropActive") : t("scanner.dropPrompt")}
          </p>
          <p className="text-sm text-[var(--color-text-tertiary)]">{t("scanner.formatHint")}</p>
        </div>
      )}

      {/* Scanning Animation */}
      {uploadMutation.isPending && (
        <div className="bg-[var(--color-bg-card)] rounded-xl p-8 text-center shadow-card border border-[var(--color-border-subtle)]">
          <div className="w-16 h-16 bg-[var(--color-accent-subtle)] rounded-full flex items-center justify-center mx-auto mb-4">
            <Sparkles className="w-8 h-8 text-blue-500 animate-pulse" />
          </div>
          <p className="text-lg font-medium text-[var(--color-text-primary)]">{t("scanner.scanning")}</p>
          <p className="text-sm text-[var(--color-text-secondary)] mt-1">{t("scanner.scanningDesc")}</p>
          <div className="mt-4 w-48 mx-auto h-1.5 bg-[var(--color-bg-inset)] rounded-full overflow-hidden">
            <div className="h-full bg-blue-500 rounded-full animate-pulse" style={{ width: "70%" }} />
          </div>
        </div>
      )}

      {/* Scan Failed — friendly error */}
      {scanFailed && !showManualForm && (
        <div className="bg-[var(--color-bg-card)] rounded-xl p-8 text-center shadow-card border border-[var(--color-border-subtle)]">
          <div className="w-16 h-16 bg-orange-50 rounded-full flex items-center justify-center mx-auto mb-4">
            <AlertCircle className="w-8 h-8 text-orange-500" />
          </div>
          <p className="text-lg font-medium text-[var(--color-text-primary)]">{t("scanner.scanFailed")}</p>
          <p className="text-sm text-[var(--color-text-secondary)] mt-1">{t("scanner.scanFailedDesc")}</p>
          {scanError && (
            <p className="text-xs text-[var(--color-text-tertiary)] mt-2 font-mono">{scanError}</p>
          )}
          <div className="flex gap-3 justify-center mt-5">
            <button
              onClick={() => setScanFailed(false)}
              className="flex items-center gap-2 px-4 py-2 bg-[var(--color-bg-card)] text-[var(--color-text-primary)] rounded-lg text-sm font-medium border border-[var(--color-border-strong)] hover:bg-[var(--color-bg-subtle)]"
            >
              <RotateCcw className="w-4 h-4" />
              {t("scanner.tryAgain")}
            </button>
            <button
              onClick={() => setShowManualForm(true)}
              className="flex items-center gap-2 px-4 py-2 bg-[var(--color-accent)] text-white rounded-lg text-sm font-medium hover:bg-[var(--color-accent-hover)]"
            >
              <PenLine className="w-4 h-4" />
              {t("scanner.orEnterManually")}
            </button>
          </div>
        </div>
      )}

      {/* Manual Form — 5 fields */}
      {showManualForm && (
        <div className="bg-[var(--color-bg-card)] rounded-xl p-6 shadow-card border border-[var(--color-border-subtle)]">
          <h2 className="text-lg font-semibold text-[var(--color-text-primary)] mb-4">{t("loanForm.quickAdd")}</h2>
          <form onSubmit={handleManualSubmit} className="space-y-4">
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-[var(--color-text-primary)] mb-1">{t("loans.bank")}</label>
                <select
                  value={form.bank_name}
                  onChange={(e) => setForm((p) => ({ ...p, bank_name: e.target.value }))}
                  className="w-full px-3 py-2 border border-[var(--color-border-strong)] rounded-lg text-sm"
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
                  onChange={(e) => setForm((p) => ({ ...p, loan_type: e.target.value }))}
                  className="w-full px-3 py-2 border border-[var(--color-border-strong)] rounded-lg text-sm capitalize"
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
                onChange={(e) => setForm((p) => ({ ...p, loan_amount: e.target.value }))}
                className="w-full px-3 py-2 border border-[var(--color-border-strong)] rounded-lg text-sm"
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
                  onChange={(e) => setForm((p) => ({ ...p, interest_rate: e.target.value }))}
                  className="w-full px-3 py-2 border border-[var(--color-border-strong)] rounded-lg text-sm"
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
                  onChange={(e) => setForm((p) => ({ ...p, emi_amount: e.target.value }))}
                  className="w-full px-3 py-2 border border-[var(--color-border-strong)] rounded-lg text-sm"
                  required
                  min="1"
                  placeholder="e.g. 22000"
                />
              </div>
            </div>

            <button
              type="submit"
              disabled={createLoanMutation.isPending}
              className="w-full py-2.5 bg-[var(--color-accent)] text-white rounded-lg font-medium hover:bg-[var(--color-accent-hover)] disabled:opacity-50"
            >
              {createLoanMutation.isPending ? t("loanForm.saving") : t("loanForm.saveLoan")}
            </button>
          </form>
        </div>
      )}

      {/* Footer link — always visible when scan zone is shown */}
      {!showManualForm && !uploadMutation.isPending && !scanFailed && (
        <button
          onClick={() => setShowManualForm(true)}
          className="block w-full text-center text-sm text-[var(--color-text-secondary)] hover:text-[var(--color-accent)] transition-colors"
        >
          {t("scanner.orEnterManually")}
        </button>
      )}
    </div>
  );
}
