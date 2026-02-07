import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { Plus, ScanLine, Zap } from "lucide-react";
import api from "../lib/api";
import { formatMonths } from "../lib/format";
import { CurrencyDisplay } from "../components/shared/CurrencyDisplay";
import { LoadingSpinner } from "../components/shared/LoadingSpinner";
import { EmptyState } from "../components/shared/EmptyState";
import type { Loan } from "../types";

const LOAN_TYPE_COLORS: Record<string, string> = {
  home: "bg-blue-100 text-blue-700",
  personal: "bg-purple-100 text-purple-700",
  car: "bg-green-100 text-green-700",
  education: "bg-yellow-100 text-yellow-700",
  gold: "bg-amber-100 text-amber-700",
  credit_card: "bg-red-100 text-red-700",
};

export function DashboardPage() {
  const { t } = useTranslation();
  const navigate = useNavigate();

  const { data: loans, isLoading } = useQuery<Loan[]>({
    queryKey: ["loans"],
    queryFn: () => api.get("/api/loans").then((r) => r.data),
  });

  if (isLoading) return <LoadingSpinner size="lg" />;

  const activeLoans = loans?.filter((l) => l.status === "active") || [];

  if (activeLoans.length === 0) {
    return (
      <EmptyState
        title="No loans yet"
        description="Add your first loan to get started with smart repayment optimization"
        action={{ label: t("dashboard.addLoan"), onClick: () => navigate("/loans?add=true") }}
      />
    );
  }

  const totalDebt = activeLoans.reduce((sum, l) => sum + l.outstanding_principal, 0);
  const totalEMI = activeLoans.reduce((sum, l) => sum + l.emi_amount, 0);
  const maxTenure = Math.max(...activeLoans.map((l) => l.remaining_tenure_months));

  return (
    <div className="space-y-6">
      {/* Summary Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="bg-white rounded-xl p-5 shadow-sm border border-gray-100">
          <p className="text-sm text-gray-500 mb-1">{t("dashboard.totalDebt")}</p>
          <CurrencyDisplay amount={totalDebt} className="text-2xl font-bold text-gray-900" />
          <p className="text-xs text-gray-400 mt-1">{activeLoans.length} active loan{activeLoans.length > 1 ? "s" : ""}</p>
        </div>
        <div className="bg-white rounded-xl p-5 shadow-sm border border-gray-100">
          <p className="text-sm text-gray-500 mb-1">{t("dashboard.monthlyEmi")}</p>
          <CurrencyDisplay amount={totalEMI} className="text-2xl font-bold text-gray-900" />
          <p className="text-xs text-gray-400 mt-1">per month</p>
        </div>
        <div className="bg-white rounded-xl p-5 shadow-sm border border-gray-100">
          <p className="text-sm text-gray-500 mb-1">{t("dashboard.debtFreeBy")}</p>
          <p className="text-2xl font-bold text-gray-900">{formatMonths(maxTenure)}</p>
          <p className="text-xs text-gray-400 mt-1">longest remaining loan</p>
        </div>
      </div>

      {/* Quick Actions */}
      <div className="flex flex-wrap gap-3">
        <button
          onClick={() => navigate("/loans?add=true")}
          className="flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg text-sm font-medium hover:bg-blue-700"
        >
          <Plus className="w-4 h-4" />
          {t("dashboard.addLoan")}
        </button>
        <button
          onClick={() => navigate("/scanner")}
          className="flex items-center gap-2 px-4 py-2 bg-white text-gray-700 rounded-lg text-sm font-medium border border-gray-300 hover:bg-gray-50"
        >
          <ScanLine className="w-4 h-4" />
          {t("dashboard.scanDoc")}
        </button>
        <button
          onClick={() => navigate("/optimizer")}
          className="flex items-center gap-2 px-4 py-2 bg-gradient-to-r from-indigo-500 to-purple-600 text-white rounded-lg text-sm font-medium hover:from-indigo-600 hover:to-purple-700"
        >
          <Zap className="w-4 h-4" />
          {t("dashboard.runOptimizer")}
        </button>
      </div>

      {/* Loan Cards */}
      <div>
        <h2 className="text-lg font-semibold text-gray-900 mb-3">Your Loans</h2>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {activeLoans.map((loan) => (
            <div
              key={loan.id}
              onClick={() => navigate(`/loans/${loan.id}`)}
              className="bg-white rounded-xl p-4 shadow-sm border border-gray-100 cursor-pointer hover:shadow-md transition-shadow"
            >
              <div className="flex items-center justify-between mb-3">
                <span className="font-medium text-gray-900">{loan.bank_name}</span>
                <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${LOAN_TYPE_COLORS[loan.loan_type] || "bg-gray-100 text-gray-600"}`}>
                  {loan.loan_type}
                </span>
              </div>
              <div className="space-y-2 text-sm">
                <div className="flex justify-between">
                  <span className="text-gray-500">Outstanding</span>
                  <CurrencyDisplay amount={loan.outstanding_principal} className="font-medium text-gray-900" />
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-500">Rate</span>
                  <span className="font-medium text-gray-900">{loan.interest_rate}%</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-500">EMI</span>
                  <CurrencyDisplay amount={loan.emi_amount} className="font-medium text-gray-900" />
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-500">Remaining</span>
                  <span className="font-medium text-gray-900">{formatMonths(loan.remaining_tenure_months)}</span>
                </div>
              </div>
              {/* Progress bar */}
              <div className="mt-3">
                <div className="h-1.5 bg-gray-100 rounded-full overflow-hidden">
                  <div
                    className="h-full bg-blue-500 rounded-full"
                    style={{ width: `${Math.max(5, (1 - loan.outstanding_principal / loan.principal_amount) * 100)}%` }}
                  />
                </div>
                <p className="text-xs text-gray-400 mt-1">
                  {Math.round((1 - loan.outstanding_principal / loan.principal_amount) * 100)}% paid
                </p>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
