import { useQuery } from "@tanstack/react-query";
import { fetchDiscover } from "../lib/api";
import type { DiscoverParams } from "../types/api";

export function useDiscover(params: DiscoverParams) {
  return useQuery({
    queryKey: ["discover", params],
    queryFn: () => fetchDiscover(params),
  });
}
