import { useQuery } from "@tanstack/react-query";

import {
  fetchTrending,
  fetchDemandGaps,
  fetchOpportunities,
  fetchMyEarnings,
  fetchMyStats,
  fetchAgentProfile,
  fetchMultiLeaderboard,
} from "../lib/api";

export function useTrending(limit = 20, hours = 6) {
  return useQuery({
    queryKey: ["trending", limit, hours],
    queryFn: () => fetchTrending(limit, hours),
    refetchInterval: 30_000,
  });
}

export function useDemandGaps(limit = 20, category?: string) {
  return useQuery({
    queryKey: ["demand-gaps", limit, category],
    queryFn: () => fetchDemandGaps(limit, category),
  });
}

export function useOpportunities(limit = 20, category?: string) {
  return useQuery({
    queryKey: ["opportunities", limit, category],
    queryFn: () => fetchOpportunities(limit, category),
  });
}

export function useMyEarnings(token: string | null) {
  return useQuery({
    queryKey: ["my-earnings", token],
    queryFn: () => fetchMyEarnings(token!),
    enabled: !!token,
  });
}

export function useMyStats(token: string | null) {
  return useQuery({
    queryKey: ["my-stats", token],
    queryFn: () => fetchMyStats(token!),
    enabled: !!token,
  });
}

export function useAgentProfile(agentId: string | null) {
  return useQuery({
    queryKey: ["agent-profile", agentId],
    queryFn: () => fetchAgentProfile(agentId!),
    enabled: !!agentId,
  });
}

export function useMultiLeaderboard(boardType: string, limit = 20) {
  return useQuery({
    queryKey: ["multi-leaderboard", boardType, limit],
    queryFn: () => fetchMultiLeaderboard(boardType, limit),
  });
}
