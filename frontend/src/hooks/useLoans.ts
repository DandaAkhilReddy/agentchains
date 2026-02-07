import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import api from "../lib/api";
import type { Loan, OptimizationResult, ScanJob } from "../types";

export function useLoans() {
  return useQuery<Loan[]>({
    queryKey: ["loans"],
    queryFn: () => api.get("/api/loans").then((r) => r.data),
  });
}

export function useLoan(id: string) {
  return useQuery<Loan>({
    queryKey: ["loan", id],
    queryFn: () => api.get(`/api/loans/${id}`).then((r) => r.data),
    enabled: !!id,
  });
}

export function useCreateLoan() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: any) => api.post("/api/loans", data).then((r) => r.data),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["loans"] }),
  });
}

export function useDeleteLoan() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => api.delete(`/api/loans/${id}`),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["loans"] }),
  });
}

export function useOptimizer() {
  return useMutation<OptimizationResult, Error, any>({
    mutationFn: (data) => api.post("/api/optimizer/analyze", data).then((r) => r.data),
  });
}

export function useQuickCompare() {
  return useMutation({
    mutationFn: (data: { loan_ids: string[]; monthly_extra: number }) =>
      api.post("/api/optimizer/quick-compare", data).then((r) => r.data),
  });
}

export function useDocumentScan() {
  return useMutation({
    mutationFn: (file: File) => {
      const formData = new FormData();
      formData.append("file", file);
      return api.post("/api/scanner/upload", formData, {
        headers: { "Content-Type": "multipart/form-data" },
      }).then((r) => r.data);
    },
  });
}

export function useScanStatus(jobId: string | null) {
  return useQuery<ScanJob>({
    queryKey: ["scan-status", jobId],
    queryFn: () => api.get(`/api/scanner/status/${jobId}`).then((r) => r.data),
    enabled: !!jobId,
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      return status === "processing" || status === "uploaded" ? 2000 : false;
    },
  });
}

export function useAIExplanation() {
  return useMutation({
    mutationFn: (data: { loan_id?: string; text?: string }) =>
      api.post("/api/ai/explain-loan", data).then((r) => r.data),
  });
}

export function useSavePlan() {
  return useMutation({
    mutationFn: (data: any) => api.post("/api/optimizer/save-plan", data).then((r) => r.data),
  });
}
