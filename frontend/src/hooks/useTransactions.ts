import { useQuery } from "@tanstack/react-query";
import { fetchTransactions } from "../lib/api";

export function useTransactions(
  token: string | null,
  params: { status?: string; page?: number },
) {
  return useQuery({
    queryKey: ["transactions", token, params],
    queryFn: () => fetchTransactions(token!, params),
    enabled: !!token,
  });
}
