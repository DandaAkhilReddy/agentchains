import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useAuth } from "../hooks/useAuth";
import { useToast } from "../components/Toast";
import PageHeader from "../components/PageHeader";
import Pagination from "../components/Pagination";
import DataTable, { type Column } from "../components/DataTable";
import SubTabNav from "../components/SubTabNav";
import Badge from "../components/Badge";
import { SkeletonCard } from "../components/Skeleton";
import {
  fetchWalletBalance,
  fetchWalletHistory,
  createDeposit,
} from "../lib/api";
import { formatUSD, relativeTime } from "../lib/format";
import {
  Wallet,
  ArrowDownCircle,
  ArrowUpCircle,
  Gift,
  RefreshCw,
  Zap,
  DollarSign,
  LogOut,
  KeyRound,
} from "lucide-react";
import type { TokenLedgerEntry } from "../types/api";

/* ─── Config maps ─── */

const TX_TYPE_CONFIG: Record<
  string,
  { icon: typeof Wallet; color: string; label: string }
> = {
  deposit: { icon: ArrowDownCircle, color: "text-[#34d399]", label: "Deposit" },
  purchase: { icon: ArrowUpCircle, color: "text-[#f87171]", label: "Purchase" },
  sale: { icon: ArrowDownCircle, color: "text-[#34d399]", label: "Sale" },
  fee: { icon: ArrowUpCircle, color: "text-[#fbbf24]", label: "Fee" },
  bonus: { icon: Gift, color: "text-[#a78bfa]", label: "Bonus" },
  refund: { icon: RefreshCw, color: "text-[#60a5fa]", label: "Refund" },
  transfer: { icon: ArrowUpCircle, color: "text-[#60a5fa]", label: "Transfer" },
};

const CREDIT_PACKAGES = [
  { label: "Starter", fiat: 5, popular: false },
  { label: "Builder", fiat: 10, popular: true },
  { label: "Pro", fiat: 25, popular: false },
  { label: "Scale", fiat: 50, popular: false },
];

const TX_TABS = [
  { id: "all", label: "All" },
  { id: "deposit", label: "Deposits" },
  { id: "purchase", label: "Purchases" },
  { id: "sale", label: "Sales" },
  { id: "fee", label: "Fees" },
];

/* ─── Stat colors ─── */

const STAT_COLORS: Record<string, string> = {
  Deposited: "#60a5fa",
  Earned: "#34d399",
  Spent: "#f87171",
  Fees: "#fbbf24",
};

/* ─── Ledger table columns ─── */

const ledgerColumns: Column<TokenLedgerEntry>[] = [
  {
    key: "tx_type",
    header: "Type",
    render: (entry) => {
      const cfg = TX_TYPE_CONFIG[entry.tx_type] ?? {
        icon: Wallet,
        color: "text-[#64748b]",
        label: entry.tx_type,
      };
      const Icon = cfg.icon;
      return (
        <span className={`flex items-center gap-2 ${cfg.color}`}>
          <Icon className="h-4 w-4" />
          <span className="text-xs font-semibold">{cfg.label}</span>
        </span>
      );
    },
  },
  {
    key: "amount",
    header: "Amount",
    render: (entry) => {
      const isIncome = ["deposit", "sale", "bonus", "refund"].includes(
        entry.tx_type
      );
      return (
        <span
          className={`text-sm font-bold ${
            isIncome ? "text-[#34d399]" : "text-[#f87171]"
          }`}
          style={{ fontFamily: "var(--font-mono)" }}
        >
          {isIncome ? "+" : "-"}
          {formatUSD(entry.amount)}
        </span>
      );
    },
  },
  {
    key: "fee",
    header: "Fee",
    render: (entry) =>
      entry.fee_amount > 0 ? (
        <span
          className="text-xs text-[#fbbf24]"
          style={{ fontFamily: "var(--font-mono)" }}
        >
          ${entry.fee_amount.toFixed(2)}
        </span>
      ) : (
        <span className="text-xs text-[#64748b]">--</span>
      ),
  },
  {
    key: "memo",
    header: "Memo",
    render: (entry) => (
      <span className="max-w-[200px] truncate text-xs text-[#94a3b8]">
        {entry.memo || "--"}
      </span>
    ),
  },
  {
    key: "created_at",
    header: "Date",
    render: (entry) => (
      <span className="text-xs text-[#64748b]">
        {relativeTime(entry.created_at)}
      </span>
    ),
  },
];

/* ─── Page Component ─── */

export default function WalletPage() {
  const { token, login, logout } = useAuth();
  const { toast } = useToast();
  const queryClient = useQueryClient();
  const [inputToken, setInputToken] = useState("");
  const [depositAmount, setDepositAmount] = useState("");
  const [page, setPage] = useState(1);
  const [selectedPackage, setSelectedPackage] = useState<number | null>(null);
  const [txFilter, setTxFilter] = useState("all");

  const { data: balance, isLoading: balLoading } = useQuery({
    queryKey: ["wallet-balance"],
    queryFn: () => fetchWalletBalance(token!),
    enabled: !!token,
    refetchInterval: 15_000,
  });

  const { data: history, isLoading: histLoading } = useQuery({
    queryKey: ["wallet-history", page, txFilter],
    queryFn: () =>
      fetchWalletHistory(token!, {
        page,
        page_size: 10,
        tx_type: txFilter === "all" ? undefined : txFilter,
      }),
    enabled: !!token,
  });

  const depositMutation = useMutation({
    mutationFn: () =>
      createDeposit(token!, { amount_usd: parseFloat(depositAmount) }),
    onSuccess: () => {
      toast(
        `Deposited ${formatUSD(parseFloat(depositAmount))} successfully!`,
        "success"
      );
      setDepositAmount("");
      setSelectedPackage(null);
      queryClient.invalidateQueries({ queryKey: ["wallet-balance"] });
      queryClient.invalidateQueries({ queryKey: ["wallet-history"] });
    },
    onError: (err) => toast((err as Error).message, "error"),
  });

  const handleConnect = () => {
    const t = inputToken.trim();
    if (t) login(t);
  };

  /* ── Auth Gate ── */
  if (!token) {
    return (
      <div className="flex min-h-[60vh] flex-col items-center justify-center px-4">
        <div
          className="w-full max-w-md space-y-6 rounded-2xl border border-[rgba(255,255,255,0.06)] p-8"
          style={{
            background:
              "linear-gradient(135deg, #141928 0%, #1a2035 50%, #1e2844 100%)",
            boxShadow:
              "0 0 40px rgba(96,165,250,0.06), 0 20px 60px rgba(0,0,0,0.4)",
          }}
        >
          {/* Icon */}
          <div className="flex justify-center">
            <div
              className="flex h-14 w-14 items-center justify-center rounded-2xl"
              style={{
                background: "rgba(96,165,250,0.1)",
                boxShadow: "0 0 20px rgba(96,165,250,0.15)",
              }}
            >
              <KeyRound className="h-6 w-6 text-[#60a5fa]" />
            </div>
          </div>

          {/* Title */}
          <div className="text-center">
            <h3
              className="text-xl font-bold"
              style={{
                background: "linear-gradient(135deg, #60a5fa, #a78bfa)",
                WebkitBackgroundClip: "text",
                WebkitTextFillColor: "transparent",
              }}
            >
              Sign In
            </h3>
            <p className="mt-1.5 text-sm text-[#94a3b8]">
              Paste your agent JWT token to access your wallet
            </p>
          </div>

          {/* Input */}
          <input
            type="text"
            value={inputToken}
            onChange={(e) => setInputToken(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && handleConnect()}
            placeholder="eyJhbGciOi..."
            className="w-full rounded-xl border border-[rgba(255,255,255,0.06)] bg-[#0a0e1a] px-4 py-3.5 text-sm text-[#e2e8f0] placeholder-[#64748b] outline-none transition-all duration-300 focus:border-[rgba(96,165,250,0.4)] focus:ring-1 focus:ring-[rgba(96,165,250,0.3)]"
            style={{
              fontFamily: "var(--font-mono)",
              boxShadow: "inset 0 2px 4px rgba(0,0,0,0.2)",
            }}
          />

          {/* Button */}
          <button
            onClick={handleConnect}
            disabled={!inputToken.trim()}
            className="w-full rounded-xl px-4 py-3 text-sm font-bold text-white transition-all duration-300 hover:shadow-[0_0_24px_rgba(96,165,250,0.25)] disabled:cursor-not-allowed disabled:opacity-40"
            style={{
              background: "linear-gradient(135deg, #60a5fa, #3b82f6)",
              boxShadow: "0 4px 16px rgba(96,165,250,0.2)",
            }}
          >
            Sign In
          </button>
        </div>
      </div>
    );
  }

  /* ── Loading ── */
  if (balLoading) {
    return (
      <div className="space-y-6">
        <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
          {Array.from({ length: 4 }).map((_, i) => (
            <SkeletonCard key={i} />
          ))}
        </div>
      </div>
    );
  }

  const acct = balance;

  const INLINE_STATS = [
    { label: "Deposited", value: formatUSD(acct?.total_deposited ?? 0) },
    { label: "Earned", value: formatUSD(acct?.total_earned ?? 0) },
    { label: "Spent", value: formatUSD(acct?.total_spent ?? 0) },
    { label: "Fees", value: formatUSD(acct?.total_fees_paid ?? 0) },
  ];

  return (
    <div className="space-y-6 animate-fade-in">
      <PageHeader
        title="Wallet"
        subtitle="Manage your balance and credits"
        icon={Wallet}
      />

      {/* ── Section 1: Balance Hero Card ── */}
      <div
        className="relative overflow-hidden rounded-2xl border border-[rgba(255,255,255,0.06)] p-6"
        style={{
          background: "linear-gradient(135deg, #141928 0%, #1a2035 100%)",
          boxShadow:
            "0 0 40px rgba(0,0,0,0.3), inset 0 1px 0 rgba(255,255,255,0.04)",
        }}
      >
        {/* Background glow */}
        <div
          className="pointer-events-none absolute -right-20 -top-20 h-60 w-60 rounded-full opacity-30"
          style={{
            background:
              "radial-gradient(circle, rgba(96,165,250,0.15) 0%, transparent 70%)",
          }}
        />

        <div className="relative flex flex-col gap-6 lg:flex-row lg:items-center lg:justify-between">
          {/* Balance */}
          <div className="flex items-center gap-4">
            <div
              className="flex h-14 w-14 shrink-0 items-center justify-center rounded-2xl"
              style={{
                background: "rgba(52,211,153,0.1)",
                boxShadow: "0 0 20px rgba(52,211,153,0.15)",
              }}
            >
              <DollarSign className="h-7 w-7 text-[#34d399]" />
            </div>
            <div>
              <p className="text-[10px] font-semibold uppercase tracking-[0.15em] text-[#64748b]">
                USD Balance
              </p>
              <p
                className="mt-0.5 text-4xl font-bold tracking-tight text-[#e2e8f0]"
                style={{
                  fontFamily: "var(--font-mono)",
                  textShadow: "0 0 20px rgba(226,232,240,0.15)",
                }}
              >
                {formatUSD(acct?.balance ?? 0)}
              </p>
            </div>
          </div>

          {/* Inline stats */}
          <div className="flex flex-wrap gap-x-8 gap-y-3">
            {INLINE_STATS.map((s) => (
              <div key={s.label}>
                <p className="text-[10px] font-medium uppercase tracking-[0.12em] text-[#64748b]">
                  {s.label}
                </p>
                <p
                  className="mt-0.5 text-sm font-bold"
                  style={{
                    fontFamily: "var(--font-mono)",
                    color: STAT_COLORS[s.label] ?? "#e2e8f0",
                  }}
                >
                  {s.value}
                </p>
              </div>
            ))}
          </div>

          {/* Disconnect */}
          <div className="flex shrink-0 items-center">
            <button
              onClick={logout}
              className="flex items-center gap-1.5 rounded-lg border border-[rgba(255,255,255,0.06)] bg-[rgba(255,255,255,0.03)] px-3 py-1.5 text-xs font-medium text-[#94a3b8] transition-all duration-200 hover:border-[rgba(248,113,113,0.3)] hover:bg-[rgba(248,113,113,0.06)] hover:text-[#f87171]"
            >
              <LogOut className="h-3.5 w-3.5" />
              Disconnect
            </button>
          </div>
        </div>
      </div>

      {/* ── Section 2: Add Funds ── */}
      <div>
        <h3 className="mb-3 flex items-center gap-2 text-xs font-bold uppercase tracking-[0.15em] text-[#94a3b8]">
          <Zap className="h-3.5 w-3.5 text-[#60a5fa]" />
          Add Funds
        </h3>

        <div
          className="space-y-5 rounded-2xl border border-[rgba(255,255,255,0.06)] p-6"
          style={{
            background:
              "linear-gradient(180deg, #141928 0%, rgba(26,32,53,0.8) 100%)",
            boxShadow: "0 0 30px rgba(0,0,0,0.2)",
          }}
        >
          {/* Subtext */}
          <p className="text-[11px] text-[#64748b]">
            Quick buy presets -- or enter any custom amount below
          </p>

          {/* Package grid */}
          <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
            {CREDIT_PACKAGES.map((pkg, i) => {
              const isSelected = selectedPackage === i;
              return (
                <button
                  key={pkg.label}
                  onClick={() => {
                    setSelectedPackage(i);
                    setDepositAmount(String(pkg.fiat));
                  }}
                  className="group relative rounded-xl border p-5 text-center transition-all duration-300"
                  style={{
                    background: isSelected
                      ? "linear-gradient(135deg, rgba(96,165,250,0.08) 0%, rgba(96,165,250,0.04) 100%)"
                      : "#0a0e1a",
                    borderColor: isSelected
                      ? "rgba(96,165,250,0.4)"
                      : pkg.popular
                        ? "rgba(167,139,250,0.3)"
                        : "rgba(255,255,255,0.06)",
                    boxShadow: isSelected
                      ? "0 0 20px rgba(96,165,250,0.12), inset 0 1px 0 rgba(96,165,250,0.1)"
                      : pkg.popular
                        ? "0 0 16px rgba(167,139,250,0.08)"
                        : "none",
                  }}
                >
                  {/* Popular badge */}
                  {pkg.popular && (
                    <div className="absolute -top-2.5 left-1/2 -translate-x-1/2">
                      <Badge label="Popular" variant="purple" />
                    </div>
                  )}

                  <p
                    className="text-3xl font-bold text-[#e2e8f0] transition-colors duration-200 group-hover:text-[#60a5fa]"
                    style={{ fontFamily: "var(--font-mono)" }}
                  >
                    ${pkg.fiat}
                  </p>
                  <p
                    className="mt-1.5 text-sm font-semibold text-[#60a5fa]"
                    style={{ fontFamily: "var(--font-mono)" }}
                  >
                    {formatUSD(pkg.fiat)} credit
                  </p>
                  <p className="mt-1 text-[11px] font-medium text-[#64748b]">
                    {pkg.label}
                  </p>
                </button>
              );
            })}
          </div>

          {/* Custom amount + buy button */}
          <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
            {/* Dollar prefix input */}
            <div className="relative flex-1">
              <span className="pointer-events-none absolute left-4 top-1/2 -translate-y-1/2 text-sm font-bold text-[#64748b]">
                $
              </span>
              <input
                type="number"
                value={selectedPackage === null ? depositAmount : ""}
                onChange={(e) => {
                  setDepositAmount(e.target.value);
                  setSelectedPackage(null);
                }}
                placeholder="Custom amount"
                min="1"
                step="0.01"
                className="w-full rounded-xl border border-[rgba(255,255,255,0.06)] bg-[#0a0e1a] py-3 pl-8 pr-4 text-sm text-[#e2e8f0] placeholder-[#64748b] outline-none transition-all duration-300 focus:border-[rgba(96,165,250,0.4)] focus:ring-1 focus:ring-[rgba(96,165,250,0.3)]"
                style={{
                  fontFamily: "var(--font-mono)",
                  boxShadow: "inset 0 2px 4px rgba(0,0,0,0.2)",
                }}
              />
            </div>

            <button
              onClick={() => depositMutation.mutate()}
              disabled={
                !depositAmount ||
                parseFloat(depositAmount) <= 0 ||
                depositMutation.isPending
              }
              className="whitespace-nowrap rounded-xl px-8 py-3 text-sm font-bold text-white transition-all duration-300 hover:shadow-[0_0_24px_rgba(52,211,153,0.2)] disabled:cursor-not-allowed disabled:opacity-40"
              style={{
                background:
                  "linear-gradient(135deg, #60a5fa 0%, #34d399 100%)",
                boxShadow: "0 4px 16px rgba(52,211,153,0.15)",
              }}
            >
              {depositMutation.isPending ? (
                <span className="flex items-center gap-2">
                  <svg
                    className="h-4 w-4 animate-spin"
                    viewBox="0 0 24 24"
                    fill="none"
                  >
                    <circle
                      cx="12"
                      cy="12"
                      r="10"
                      stroke="currentColor"
                      strokeWidth="3"
                      strokeDasharray="60"
                      strokeDashoffset="20"
                      strokeLinecap="round"
                    />
                  </svg>
                  Processing...
                </span>
              ) : (
                "Buy Credits"
              )}
            </button>
          </div>
        </div>
      </div>

      {/* ── Section 3: Transaction History ── */}
      <div>
        <div className="mb-3 flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
          <h3 className="text-xs font-bold uppercase tracking-[0.15em] text-[#94a3b8]">
            Transaction History
          </h3>
          <SubTabNav
            tabs={TX_TABS}
            active={txFilter}
            onChange={(id) => {
              setTxFilter(id);
              setPage(1);
            }}
          />
        </div>
        <DataTable
          columns={ledgerColumns}
          data={history?.entries ?? []}
          isLoading={histLoading}
          keyFn={(e) => e.id}
          emptyMessage="No transactions yet"
        />
        {history && history.total > 10 && (
          <Pagination
            page={page}
            totalPages={Math.ceil(history.total / 10)}
            onPageChange={setPage}
          />
        )}
      </div>
    </div>
  );
}
