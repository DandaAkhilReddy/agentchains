import { useState, useEffect } from "react";
import { useTranslation } from "react-i18next";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import api from "../lib/api";
import { useLanguageStore } from "../store/languageStore";
import { useCountryStore } from "../store/countryStore";
import { useCountryConfig } from "../hooks/useCountryConfig";

export function SettingsPage() {
  const { t } = useTranslation();
  const { language, setLanguage } = useLanguageStore();
  const { country, setCountry } = useCountryStore();
  const config = useCountryConfig();
  const queryClient = useQueryClient();

  const { data: profile } = useQuery({
    queryKey: ["profile"],
    queryFn: () => api.get("/api/auth/me").then((r) => r.data),
  });

  const [form, setForm] = useState({
    display_name: profile?.display_name || "",
    tax_regime: profile?.tax_regime || "old",
    filing_status: profile?.filing_status || "single",
    annual_income: profile?.annual_income || "",
  });

  useEffect(() => {
    if (profile) {
      setForm({
        display_name: profile.display_name || "",
        tax_regime: profile.tax_regime || "old",
        filing_status: profile.filing_status || "single",
        annual_income: profile.annual_income || "",
      });
    }
  }, [profile]);

  const updateProfile = useMutation({
    mutationFn: (data: any) => api.put("/api/auth/me", data),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["profile"] }),
  });

  const exportData = useMutation({
    mutationFn: async () => {
      const res = await api.post("/api/user/export-data", {}, { responseType: "blob" });
      const url = URL.createObjectURL(res.data);
      const a = document.createElement("a");
      a.href = url;
      a.download = `loan-data-export-${new Date().toISOString().slice(0, 10)}.json`;
      a.click();
      URL.revokeObjectURL(url);
    },
  });

  const handleSave = () => {
    updateProfile.mutate({
      display_name: form.display_name || undefined,
      preferred_language: language,
      country,
      tax_regime: config.hasTaxSections ? form.tax_regime : undefined,
      filing_status: config.hasFilingStatus ? form.filing_status : undefined,
      annual_income: form.annual_income ? Number(form.annual_income) : undefined,
    });
  };

  return (
    <div className="max-w-lg mx-auto space-y-6 animate-fade-up">
      <h1 className="text-xl font-bold text-[var(--color-text-primary)]">{t("nav.settings")}</h1>

      <div className="bg-[var(--color-bg-card)] rounded-xl p-6 shadow-card border border-[var(--color-border-subtle)] space-y-4">
        <div>
          <label className="block text-sm font-medium text-[var(--color-text-primary)] mb-1">{t("settings.displayName")}</label>
          <input
            value={form.display_name}
            onChange={(e) => setForm((p) => ({ ...p, display_name: e.target.value }))}
            className="w-full px-3 py-2 border border-[var(--color-border-strong)] rounded-lg text-sm"
          />
        </div>

        <div>
          <label className="block text-sm font-medium text-[var(--color-text-primary)] mb-1">{t("settings.country")}</label>
          <select
            value={country}
            onChange={(e) => setCountry(e.target.value as "IN" | "US")}
            className="w-full px-3 py-2 border border-[var(--color-border-strong)] rounded-lg text-sm"
          >
            <option value="IN">India</option>
            <option value="US">United States</option>
          </select>
        </div>

        <div>
          <label className="block text-sm font-medium text-[var(--color-text-primary)] mb-1">{t("settings.language")}</label>
          <select value={language} onChange={(e) => setLanguage(e.target.value)} className="w-full px-3 py-2 border border-[var(--color-border-strong)] rounded-lg text-sm">
            <option value="en">English</option>
            <option value="hi">हिन्दी (Hindi)</option>
            <option value="te">తెలుగు (Telugu)</option>
            <option value="es">Español (Spanish)</option>
          </select>
        </div>

        {/* India: Tax Regime */}
        {config.hasTaxSections && (
          <div>
            <label className="block text-sm font-medium text-[var(--color-text-primary)] mb-1">{t("settings.taxRegime")}</label>
            <select value={form.tax_regime} onChange={(e) => setForm((p) => ({ ...p, tax_regime: e.target.value }))} className="w-full px-3 py-2 border border-[var(--color-border-strong)] rounded-lg text-sm">
              <option value="old">{t("settings.oldRegime")}</option>
              <option value="new">{t("settings.newRegime")}</option>
            </select>
          </div>
        )}

        {/* US: Filing Status */}
        {config.hasFilingStatus && (
          <div>
            <label className="block text-sm font-medium text-[var(--color-text-primary)] mb-1">{t("settings.filingStatus")}</label>
            <select value={form.filing_status} onChange={(e) => setForm((p) => ({ ...p, filing_status: e.target.value }))} className="w-full px-3 py-2 border border-[var(--color-border-strong)] rounded-lg text-sm">
              <option value="single">{t("settings.single")}</option>
              <option value="married_jointly">{t("settings.marriedJointly")}</option>
              <option value="married_separately">{t("settings.marriedSeparately")}</option>
              <option value="head_of_household">{t("settings.headOfHousehold")}</option>
            </select>
          </div>
        )}

        <div>
          <label className="block text-sm font-medium text-[var(--color-text-primary)] mb-1">{t("settings.annualIncome")} ({config.currencySymbol})</label>
          <input
            type="number"
            value={form.annual_income}
            onChange={(e) => setForm((p) => ({ ...p, annual_income: e.target.value }))}
            className="w-full px-3 py-2 border border-[var(--color-border-strong)] rounded-lg text-sm"
            placeholder={t("settings.forTaxOptimization")}
          />
        </div>

        <button
          onClick={handleSave}
          disabled={updateProfile.isPending}
          className="w-full py-2.5 bg-[var(--color-accent)] text-white rounded-lg font-medium hover:bg-[var(--color-accent-hover)] disabled:opacity-50"
        >
          {updateProfile.isPending ? t("common.saving") : t("common.save")}
        </button>
      </div>

      {/* Data Management */}
      <div className="bg-[var(--color-bg-card)] rounded-xl p-6 shadow-card border border-[var(--color-border-subtle)] space-y-4">
        <h2 className="font-semibold text-[var(--color-text-primary)]">{t("settings.dataManagement")}</h2>
        <button
          onClick={() => exportData.mutate()}
          className="w-full py-2 border border-[var(--color-border-strong)] rounded-lg text-sm text-[var(--color-text-primary)] hover:bg-[var(--color-bg-subtle)]"
        >
          {t("settings.exportData")} ({t(config.privacyLawKey)})
        </button>
        <button
          onClick={async () => {
            if (confirm(t("settings.deleteWarning"))) {
              try {
                await api.delete("/api/user/delete-account");
                const { auth } = await import("../lib/firebase");
                await auth.signOut();
                window.location.href = "/login";
              } catch {
                // Error toast already shown by response interceptor
              }
            }
          }}
          className="w-full py-2 border border-red-300 dark:border-red-800 rounded-lg text-sm text-red-600 dark:text-red-400 hover:bg-red-50 dark:hover:bg-red-900/20"
        >
          {t("settings.deleteAccount")}
        </button>
        <p className="text-xs text-[var(--color-text-tertiary)]">{t("settings.appVersion")}: 0.2.0</p>
      </div>
    </div>
  );
}
