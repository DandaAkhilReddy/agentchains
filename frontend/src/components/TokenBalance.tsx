import { useQuery } from "@tanstack/react-query";
import { Wallet } from "lucide-react";
import { useAuth } from "../hooks/useAuth";
import { fetchWalletBalance } from "../lib/api";
import { formatARD } from "../lib/format";

export default function TokenBalance() {
  const { token } = useAuth();
  const { data } = useQuery({
    queryKey: ["wallet-balance"],
    queryFn: () => fetchWalletBalance(token!),
    enabled: !!token,
    refetchInterval: 30_000,
  });

  if (!token || !data) return null;

  const tierColors: Record<string, string> = {
    bronze: "text-[#cd7f32]",
    silver: "text-[#c0c0c0]",
    gold: "text-[#ffd700]",
    platinum: "text-primary",
  };

  return (
    <div className="flex items-center gap-2 rounded-full border border-border-glow bg-surface-raised/50 px-3 py-1">
      <Wallet className="h-3.5 w-3.5 text-primary" />
      <span className="text-xs font-semibold text-text-primary" style={{ fontFamily: "var(--font-mono)" }}>
        {formatARD(data.account.balance)}
      </span>
      <span className={`text-[10px] font-bold uppercase ${tierColors[data.account.tier] ?? "text-text-muted"}`}>
        {data.account.tier}
      </span>
    </div>
  );
}
