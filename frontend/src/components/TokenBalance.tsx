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
    <div className="flex items-center gap-2 rounded-full border border-[rgba(255,255,255,0.06)] bg-[rgba(20,25,40,0.6)] px-3 py-1 backdrop-blur-sm">
      <span className="flex h-5 w-5 items-center justify-center rounded-full bg-[rgba(96,165,250,0.15)]">
        <Wallet className="h-3 w-3 text-[#60a5fa]" />
      </span>
      <span
        className="text-xs font-semibold text-[#34d399]"
        style={{
          fontFamily: "var(--font-mono)",
          textShadow: "0 0 8px rgba(52,211,153,0.3)",
        }}
      >
        {formatUSD(data.account.balance)}
      </span>
    </div>
  );
}
