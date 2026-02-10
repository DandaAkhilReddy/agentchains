import { useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Plus } from "lucide-react";
import api from "../lib/api";
import { formatCurrency } from "../lib/format";
import { useCountryConfig } from "../hooks/useCountryConfig";
import { LoadingSpinner } from "../components/shared/LoadingSpinner";
import { EmptyState } from "../components/shared/EmptyState";
import { LoanForm } from "../components/loans/LoanForm";
import type { Loan } from "../types";

export function LoansPage() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const config = useCountryConfig();
  const [searchParams] = useSearchParams();
  const [showForm, setShowForm] = useState(searchParams.get("add") === "true");
  const [filterType, setFilterType] = useState<string>("");
  const queryClient = useQueryClient();
  const fmt = (n: number) => formatCurrency(n, config.code);

  const { data: loans, isLoading } = useQuery<Loan[]>({
    queryKey: ["loans"],
    queryFn: () => api.get("/api/loans").then((r) => r.data),
  });

  const createLoan = useMutation({
    mutationFn: (data: any) => api.post("/api/loans", data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["loans"] });
      setShowForm(false);
    },
  });

  if (isLoading) return <LoadingSpinner size="lg" />;

  const filtered = filterType
    ? loans?.filter((l) => l.loan_type === filterType)
    : loans;

  const loanTypes = [...new Set(loans?.map((l) => l.loan_type) || [])];

  return (
    <div className="space-y-6 animate-fade-up">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-bold text-[var(--color-text-primary)]">{t("nav.loans")}</h1>
        <button
          onClick={() => setShowForm(true)}
          className="flex items-center gap-2 px-4 py-2 bg-[var(--color-accent)] text-white rounded-lg text-sm font-medium hover:bg-[var(--color-accent-hover)]"
        >
          <Plus className="w-4 h-4" />
          {t("loans.addLoan")}
        </button>
      </div>

      {/* Filters */}
      {loanTypes.length > 1 && (
        <div className="flex gap-2 flex-wrap">
          <button
            onClick={() => setFilterType("")}
            className={`px-3 py-1.5 rounded-lg text-sm font-medium ${!filterType ? "bg-blue-100 text-[var(--color-accent-text)]" : "bg-[var(--color-bg-inset)] text-[var(--color-text-secondary)] hover:bg-gray-200"}`}
          >
            {t("loans.all")}
          </button>
          {loanTypes.map((type) => (
            <button
              key={type}
              onClick={() => setFilterType(type)}
              className={`px-3 py-1.5 rounded-lg text-sm font-medium capitalize ${filterType === type ? "bg-blue-100 text-[var(--color-accent-text)]" : "bg-[var(--color-bg-inset)] text-[var(--color-text-secondary)] hover:bg-gray-200"}`}
            >
              {type}
            </button>
          ))}
        </div>
      )}

      {/* Loan List Table */}
      {!filtered?.length ? (
        <EmptyState
          title={t("loans.noLoansFound")}
          description={t("loans.noLoansDesc")}
          action={{ label: t("loans.addLoan"), onClick: () => setShowForm(true) }}
        />
      ) : (
        <div className="bg-[var(--color-bg-card)] rounded-xl shadow-card border border-[var(--color-border-subtle)] overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-[var(--color-bg-app)] border-b border-[var(--color-border-subtle)]">
                <tr>
                  <th className="text-left px-4 py-3 font-medium text-[var(--color-text-secondary)]">{t("loans.bank")}</th>
                  <th className="text-left px-4 py-3 font-medium text-[var(--color-text-secondary)]">{t("loans.type")}</th>
                  <th className="text-right px-4 py-3 font-medium text-[var(--color-text-secondary)]">{t("loans.outstanding")}</th>
                  <th className="text-right px-4 py-3 font-medium text-[var(--color-text-secondary)]">{t("loans.rate")}</th>
                  <th className="text-right px-4 py-3 font-medium text-[var(--color-text-secondary)]">{t("loans.emi")}</th>
                  <th className="text-right px-4 py-3 font-medium text-[var(--color-text-secondary)]">{t("loans.remaining")}</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-50">
                {filtered.map((loan) => (
                  <tr
                    key={loan.id}
                    onClick={() => navigate(`/loans/${loan.id}`)}
                    className="hover:bg-[var(--color-bg-subtle)] cursor-pointer"
                  >
                    <td className="px-4 py-3 font-medium text-[var(--color-text-primary)]">{loan.bank_name}</td>
                    <td className="px-4 py-3 capitalize text-[var(--color-text-secondary)]">{loan.loan_type}</td>
                    <td className="px-4 py-3 text-right font-medium">{fmt(loan.outstanding_principal)}</td>
                    <td className="px-4 py-3 text-right">{loan.interest_rate}%</td>
                    <td className="px-4 py-3 text-right">{fmt(loan.emi_amount)}</td>
                    <td className="px-4 py-3 text-right text-[var(--color-text-secondary)]">{loan.remaining_tenure_months}m</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Add Loan Modal */}
      {showForm && (
        <LoanForm
          onSubmit={(data) => createLoan.mutate(data)}
          onClose={() => setShowForm(false)}
          isLoading={createLoan.isPending}
        />
      )}
    </div>
  );
}
