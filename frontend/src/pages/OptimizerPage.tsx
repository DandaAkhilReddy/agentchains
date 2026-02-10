import { useEffect } from "react";
import { useQuery } from "@tanstack/react-query";
import api from "../lib/api";
import { LoadingSpinner } from "../components/shared/LoadingSpinner";
import { EmptyState } from "../components/shared/EmptyState";
import { OptimizerWizard } from "../components/optimizer/OptimizerWizard";
import { useCountryStore } from "../store/countryStore";
import { COUNTRY_CONFIGS } from "../lib/countryConfig";
import type { Loan } from "../types";

const US_BANKS = new Set(COUNTRY_CONFIGS.US.banks.map((b) => b.toLowerCase()));

export function OptimizerPage() {
  const { data: loans, isLoading } = useQuery<Loan[]>({
    queryKey: ["loans"],
    queryFn: () => api.get("/api/loans?status=active").then((r) => r.data),
  });

  const setCountry = useCountryStore((s) => s.setCountry);

  // Auto-detect country from loan bank names
  useEffect(() => {
    if (!loans || loans.length === 0) return;
    const usCount = loans.filter((l) =>
      US_BANKS.has(l.bank_name.toLowerCase()) ||
      l.bank_name.toLowerCase().includes("chase") ||
      l.bank_name.toLowerCase().includes("wells fargo") ||
      l.bank_name.toLowerCase().includes("bank of america")
    ).length;
    if (usCount > loans.length / 2) {
      setCountry("US");
    }
  }, [loans, setCountry]);

  if (isLoading) return <LoadingSpinner size="lg" />;

  const activeLoans = loans?.filter((l) => l.status === "active") || [];

  if (activeLoans.length === 0) {
    return (
      <EmptyState
        title="No active loans"
        description="Add at least one loan to use the Smart Optimizer"
        action={{ label: "Add Loan", onClick: () => window.location.href = "/loans?add=true" }}
      />
    );
  }

  return <OptimizerWizard loans={activeLoans} />;
}
