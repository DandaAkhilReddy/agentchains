import { useQuery } from "@tanstack/react-query";
import { fetchCreatorDashboard } from "../lib/api";

export function useCreatorDashboard(token: string) {
  return useQuery({
    queryKey: ["creatorDashboard", token],
    queryFn: () => fetchCreatorDashboard(token),
    enabled: !!token,
  });
}
