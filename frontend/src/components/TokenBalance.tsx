import { useQuery } from "@tanstack/react-query";
import { Wallet } from "lucide-react";
import { useAuth } from "../hooks/useAuth";
import { fetchWalletBalance } from "../lib/api";
import { formatUSD } from "../lib/format";

export default function TokenBalance() {
  const { token } = useAuth();
  const { data } = useQuery({
    queryKey: ["wallet-balance"],
    queryFn: () => fetchWalletBalance(token!),
    enabled: !!token,
    refetchInterval: 30_000,
  });

  if (!token || !data) return null;

  return (
    <div className="flex items-center gap-2 rounded-full border border-border-glow bg-surface-raised/50 px-3 py-1">
      <Wallet className="h-3.5 w-3.5 text-primary" />
      <span className="text-xs font-semibold text-text-primary" style={{ fontFamily: "var(--font-mono)" }}>
        {formatUSD(data.account.balance)}
      </span>
    </div>
  );
}
