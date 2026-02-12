import { useQuery } from "@tanstack/react-query";
import { fetchSystemMetrics, fetchCDNStats } from "../lib/api";

export function useSystemMetrics() {
  return useQuery({
    queryKey: ["system-metrics"],
    queryFn: fetchSystemMetrics,
    staleTime: 15_000,
    refetchInterval: 30_000,
  });
}

export function useCDNStats() {
  return useQuery({
    queryKey: ["cdn-stats"],
    queryFn: fetchCDNStats,
    staleTime: 5_000,
    refetchInterval: 15_000,
  });
}
