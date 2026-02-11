import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useAuth } from "../hooks/useAuth";
import { useToast } from "../components/Toast";
import StatCard from "../components/StatCard";
import DataTable, { type Column } from "../components/DataTable";
import { SkeletonCard } from "../components/Skeleton";
import {
  fetchWalletBalance,
  fetchWalletHistory,
  fetchTokenSupply,
  fetchSupportedCurrencies,
  createDeposit,
} from "../lib/api";
import { formatAXN, axnToUSD } from "../lib/format";
import { relativeTime } from "../lib/format";
import {
  Wallet,
  ArrowDownCircle,
  ArrowUpCircle,
  Flame,
  Gift,
  RefreshCw,
  Coins,
  TrendingUp,
  ShieldCheck,
} from "lucide-react";
import type { TokenLedgerEntry } from "../types/api";

const TX_TYPE_CONFIG: Record<string, { icon: typeof Wallet; color: string; label: string }> = {
  deposit: { icon: ArrowDownCircle, color: "text-success", label: "Deposit" },
  purchase: { icon: ArrowUpCircle, color: "text-danger", label: "Purchase" },
  sale: { icon: ArrowDownCircle, color: "text-success", label: "Sale" },
  fee: { icon: Coins, color: "text-warning", label: "Fee" },
  burn: { icon: Flame, color: "text-[#ff6b6b]", label: "Burn" },
  bonus: { icon: Gift, color: "text-secondary", label: "Bonus" },
  refund: { icon: RefreshCw, color: "text-primary", label: "Refund" },
  transfer: { icon: ArrowUpCircle, color: "text-primary", label: "Transfer" },
};

const TIER_CONFIG: Record<string, { color: string; glow: string; next: string; nextVolume: number }> = {
  bronze: { color: "#cd7f32", glow: "rgba(205,127,50,0.2)", next: "Silver", nextVolume: 10_000 },
  silver: { color: "#c0c0c0", glow: "rgba(192,192,192,0.2)", next: "Gold", nextVolume: 100_000 },
  gold: { color: "#ffd700", glow: "rgba(255,215,0,0.2)", next: "Platinum", nextVolume: 1_000_000 },
  platinum: { color: "#00d4ff", glow: "rgba(0,212,255,0.3)", next: "", nextVolume: 0 },
};

const ledgerColumns: Column<TokenLedgerEntry>[] = [
  {
    key: "tx_type",
    header: "Type",
    render: (entry) => {
      const cfg = TX_TYPE_CONFIG[entry.tx_type] ?? { icon: Coins, color: "text-text-muted", label: entry.tx_type };
      const Icon = cfg.icon;
      return (
        <span className={`flex items-center gap-2 ${cfg.color}`}>
          <Icon className="h-3.5 w-3.5" />
          <span className="text-xs font-medium">{cfg.label}</span>
        </span>
      );
    },
  },
  {
    key: "amount",
    header: "Amount",
    render: (entry) => (
      <span className="text-sm font-semibold text-text-primary" style={{ fontFamily: "var(--font-mono)" }}>
        {formatAXN(entry.amount)}
      </span>
    ),
  },
  {
    key: "fee",
    header: "Fee",
    render: (entry) =>
      entry.fee_amount > 0 ? (
        <span className="text-xs text-warning" style={{ fontFamily: "var(--font-mono)" }}>
          {entry.fee_amount.toFixed(2)}
        </span>
      ) : (
        <span className="text-xs text-text-muted">—</span>
      ),
  },
  {
    key: "memo",
    header: "Memo",
    render: (entry) => (
      <span className="max-w-[200px] truncate text-xs text-text-muted">{entry.memo || "—"}</span>
    ),
  },
  {
    key: "created_at",
    header: "Date",
    render: (entry) => <span className="text-xs text-text-muted">{relativeTime(entry.created_at)}</span>,
  },
];

export default function WalletPage() {
  const { token, login, logout } = useAuth();
  const { toast } = useToast();
  const queryClient = useQueryClient();
  const [inputToken, setInputToken] = useState("");
  const [depositAmount, setDepositAmount] = useState("");
  const [depositCurrency, setDepositCurrency] = useState("USD");
  const [page, setPage] = useState(1);

  const { data: balance, isLoading: balLoading } = useQuery({
    queryKey: ["wallet-balance"],
    queryFn: () => fetchWalletBalance(token!),
    enabled: !!token,
    refetchInterval: 15_000,
  });

  const { data: history, isLoading: histLoading } = useQuery({
    queryKey: ["wallet-history", page],
    queryFn: () => fetchWalletHistory(token!, { page, page_size: 10 }),
    enabled: !!token,
  });

  const { data: supply } = useQuery({
    queryKey: ["token-supply"],
    queryFn: fetchTokenSupply,
    staleTime: 60_000,
  });

  const { data: currencies } = useQuery({
    queryKey: ["supported-currencies"],
    queryFn: fetchSupportedCurrencies,
    staleTime: 300_000,
  });

  const depositMutation = useMutation({
    mutationFn: () => createDeposit(token!, { amount_fiat: parseFloat(depositAmount), currency: depositCurrency }),
    onSuccess: (data) => {
      toast(`Deposited ${formatAXN(data.new_balance >= 0 ? parseFloat(depositAmount) / 0.001 : 0)} successfully!`, "success");
      setDepositAmount("");
      queryClient.invalidateQueries({ queryKey: ["wallet-balance"] });
      queryClient.invalidateQueries({ queryKey: ["wallet-history"] });
      queryClient.invalidateQueries({ queryKey: ["token-supply"] });
    },
    onError: (err) => toast((err as Error).message, "error"),
  });

  const handleConnect = () => {
    const t = inputToken.trim();
    if (t) login(t);
  };

  if (!token) {
    return (
      <div className="flex flex-col items-center py-20">
        <div className="glass-card gradient-border-card p-8 w-full max-w-md space-y-4">
          <div className="text-center">
            <h3 className="text-lg font-bold gradient-text">Connect Wallet</h3>
            <p className="mt-1 text-sm text-text-secondary">
              Paste your agent JWT to access your AXN wallet
            </p>
          </div>
          <input
            type="text"
            value={inputToken}
            onChange={(e) => setInputToken(e.target.value)}
            placeholder="eyJhbGciOi..."
            className="futuristic-input w-full px-4 py-3 text-sm"
            style={{ fontFamily: "var(--font-mono)" }}
          />
          <button onClick={handleConnect} disabled={!inputToken.trim()} className="btn-primary w-full px-4 py-2.5 text-sm">
            Connect
          </button>
        </div>
      </div>
    );
  }

  if (balLoading) {
    return (
      <div className="space-y-6">
        <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
          {Array.from({ length: 4 }).map((_, i) => <SkeletonCard key={i} />)}
        </div>
      </div>
    );
  }

  const acct = balance?.account;
  const tier = acct?.tier ?? "bronze";
  const tierCfg = TIER_CONFIG[tier] ?? TIER_CONFIG.bronze;
  const lifetimeVolume = (acct?.total_earned ?? 0) + (acct?.total_spent ?? 0);

  return (
    <div className="space-y-6 animate-fade-in">
      {/* Balance + Tier Hero */}
      <div className="glass-card gradient-border-card glow-hover relative overflow-hidden p-6">
        <div className="absolute -right-8 -top-8 h-32 w-32 rounded-full opacity-20" style={{ background: `radial-gradient(circle, ${tierCfg.color}, transparent)` }} />
        <div className="flex items-start justify-between">
          <div>
            <p className="text-xs font-semibold uppercase tracking-widest text-text-muted">AXN Balance</p>
            <p className="mt-1 text-4xl font-bold tracking-tight gradient-text" style={{ fontFamily: "var(--font-mono)" }}>
              {formatAXN(acct?.balance ?? 0)}
            </p>
            <p className="mt-1 text-sm text-text-secondary" style={{ fontFamily: "var(--font-mono)" }}>
              ≈ {axnToUSD(acct?.balance ?? 0)}
            </p>
          </div>
          <div className="flex flex-col items-end gap-2">
            <span
              className="rounded-full px-3 py-1 text-xs font-bold uppercase tracking-wider"
              style={{ color: tierCfg.color, backgroundColor: tierCfg.glow, boxShadow: `0 0 12px ${tierCfg.glow}` }}
            >
              {tier}
            </span>
            <button onClick={logout} className="btn-ghost px-3 py-1 text-xs">Disconnect</button>
          </div>
        </div>

        {/* Tier progress */}
        {tierCfg.next && (
          <div className="mt-4">
            <div className="flex items-center justify-between text-xs text-text-muted">
              <span>Progress to {tierCfg.next}</span>
              <span style={{ fontFamily: "var(--font-mono)" }}>{formatAXN(lifetimeVolume)} / {formatAXN(tierCfg.nextVolume)}</span>
            </div>
            <div className="mt-1 h-1.5 w-full overflow-hidden rounded-full bg-surface-overlay">
              <div
                className="h-full rounded-full animate-grow-bar"
                style={{
                  width: `${Math.min((lifetimeVolume / tierCfg.nextVolume) * 100, 100)}%`,
                  background: `linear-gradient(90deg, ${tierCfg.color}, #00d4ff)`,
                }}
              />
            </div>
          </div>
        )}
      </div>

      {/* Stats row */}
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        <StatCard label="Total Deposited" value={formatAXN(acct?.total_deposited ?? 0)} icon={ArrowDownCircle} />
        <StatCard label="Total Earned" value={formatAXN(acct?.total_earned ?? 0)} icon={TrendingUp} />
        <StatCard label="Total Spent" value={formatAXN(acct?.total_spent ?? 0)} icon={ArrowUpCircle} />
        <StatCard label="Fees Paid" value={formatAXN(acct?.total_fees_paid ?? 0)} icon={Coins} />
      </div>

      {/* Deposit + Supply */}
      <div className="grid gap-6 lg:grid-cols-2">
        {/* Deposit form */}
        <div className="glass-card gradient-border-card glow-hover p-5">
          <h3 className="mb-4 flex items-center gap-2 text-sm font-semibold text-text-primary">
            <ArrowDownCircle className="h-4 w-4 text-success" />
            Buy AXN Tokens
          </h3>
          <div className="space-y-3">
            <div className="flex gap-2">
              <input
                type="number"
                value={depositAmount}
                onChange={(e) => setDepositAmount(e.target.value)}
                placeholder="Amount"
                min="1"
                step="0.01"
                className="futuristic-input flex-1 px-3 py-2 text-sm"
              />
              <select
                value={depositCurrency}
                onChange={(e) => setDepositCurrency(e.target.value)}
                className="futuristic-select px-3 py-2 text-sm"
              >
                {(currencies?.currencies ?? [{ code: "USD", name: "US Dollar" }]).map((c) => (
                  <option key={c.code} value={c.code}>{c.code}</option>
                ))}
              </select>
            </div>
            {depositAmount && parseFloat(depositAmount) > 0 && (
              <p className="text-xs text-text-secondary" style={{ fontFamily: "var(--font-mono)" }}>
                ≈ {formatAXN(parseFloat(depositAmount) / 0.001)} at 1 AXN = $0.001
              </p>
            )}
            <button
              onClick={() => depositMutation.mutate()}
              disabled={!depositAmount || parseFloat(depositAmount) <= 0 || depositMutation.isPending}
              className="btn-primary w-full px-4 py-2.5 text-sm"
            >
              {depositMutation.isPending ? "Processing..." : "Deposit"}
            </button>
          </div>
        </div>

        {/* Supply stats */}
        <div className="glass-card gradient-border-card glow-hover p-5">
          <h3 className="mb-4 flex items-center gap-2 text-sm font-semibold text-text-primary">
            <ShieldCheck className="h-4 w-4 text-primary" />
            Token Supply
          </h3>
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <span className="text-xs text-text-muted">Circulating</span>
              <span className="text-sm font-semibold text-text-primary" style={{ fontFamily: "var(--font-mono)" }}>
                {formatAXN(supply?.circulating ?? 0)}
              </span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-xs text-text-muted">Total Burned</span>
              <span className="text-sm font-semibold text-[#ff6b6b]" style={{ fontFamily: "var(--font-mono)" }}>
                {formatAXN(supply?.total_burned ?? 0)}
              </span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-xs text-text-muted">Platform Reserve</span>
              <span className="text-sm font-semibold text-secondary" style={{ fontFamily: "var(--font-mono)" }}>
                {formatAXN(supply?.platform_balance ?? 0)}
              </span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-xs text-text-muted">Total Minted</span>
              <span className="text-sm font-semibold text-text-secondary" style={{ fontFamily: "var(--font-mono)" }}>
                {formatAXN(supply?.total_minted ?? 0)}
              </span>
            </div>
            <div className="mt-2 h-2 w-full overflow-hidden rounded-full bg-surface-overlay">
              <div
                className="h-full rounded-full bg-gradient-to-r from-primary to-secondary"
                style={{ width: `${supply ? ((supply.circulating / supply.total_minted) * 100) : 100}%` }}
              />
            </div>
            <p className="text-center text-[10px] text-text-muted">
              {supply ? ((supply.circulating / supply.total_minted) * 100).toFixed(4) : "100.0000"}% circulating
            </p>
          </div>
        </div>
      </div>

      {/* Transaction History */}
      <div>
        <h3 className="mb-3 text-xs font-semibold uppercase tracking-widest text-text-secondary">
          Token History
        </h3>
        <DataTable
          columns={ledgerColumns}
          data={history?.entries ?? []}
          isLoading={histLoading}
          keyFn={(e) => e.id}
          emptyMessage="No token transactions yet"
        />
        {history && history.total > 10 && (
          <div className="mt-3 flex items-center justify-end gap-2">
            <button disabled={page <= 1} onClick={() => setPage((p) => p - 1)} className="btn-ghost px-3 py-1.5 text-sm disabled:opacity-30">
              Prev
            </button>
            <span className="text-sm text-text-secondary">Page {page}</span>
            <button disabled={page * 10 >= history.total} onClick={() => setPage((p) => p + 1)} className="btn-ghost px-3 py-1.5 text-sm disabled:opacity-30">
              Next
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
