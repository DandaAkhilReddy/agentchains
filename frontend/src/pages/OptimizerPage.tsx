import { useQuery } from "@tanstack/react-query";
import api from "../lib/api";
import { LoadingSpinner } from "../components/shared/LoadingSpinner";
import { EmptyState } from "../components/shared/EmptyState";
import { OptimizerWizard } from "../components/optimizer/OptimizerWizard";
import type { Loan } from "../types";

export function OptimizerPage() {
  const { data: loans, isLoading } = useQuery<Loan[]>({
    queryKey: ["loans"],
    queryFn: () => api.get("/api/loans?status=active").then((r) => r.data),
  });

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
