import { useQuery } from "@tanstack/react-query";
import { fetchLeaderboard, fetchReputation } from "../lib/api";

export function useLeaderboard(limit = 20) {
  return useQuery({
    queryKey: ["leaderboard", limit],
    queryFn: () => fetchLeaderboard(limit),
  });
}

export function useReputation(agentId: string | null) {
  return useQuery({
    queryKey: ["reputation", agentId],
    queryFn: () => fetchReputation(agentId!),
    enabled: !!agentId,
  });
}
