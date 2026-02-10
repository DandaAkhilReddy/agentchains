import { useQuery } from "@tanstack/react-query";
import { fetchAgents } from "../lib/api";

export function useAgents(params: {
  agent_type?: string;
  status?: string;
  page?: number;
}) {
  return useQuery({
    queryKey: ["agents", params],
    queryFn: () => fetchAgents(params),
  });
}
