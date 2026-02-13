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
} from "lucide-react";
import type { TokenLedgerEntry } from "../types/api";

// --- Config maps ---

const TX_TYPE_CONFIG: Record<string, { icon: typeof Wallet; color: string; label: string }> = {
  deposit: { icon: ArrowDownCircle, color: "text-success", label: "Deposit" },
  purchase: { icon: ArrowUpCircle, color: "text-danger", label: "Purchase" },
  sale: { icon: ArrowDownCircle, color: "text-success", label: "Sale" },
  fee: { icon: ArrowUpCircle, color: "text-warning", label: "Fee" },
  bonus: { icon: Gift, color: "text-secondary", label: "Bonus" },
  refund: { icon: RefreshCw, color: "text-primary", label: "Refund" },
  transfer: { icon: ArrowUpCircle, color: "text-primary", label: "Transfer" },
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

// --- Ledger table columns ---

const ledgerColumns: Column<TokenLedgerEntry>[] = [
  {
    key: "tx_type",
    header: "Type",
    render: (entry) => {
      const cfg = TX_TYPE_CONFIG[entry.tx_type] ?? { icon: Wallet, color: "text-text-muted", label: entry.tx_type };
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
        {formatUSD(entry.amount)}
      </span>
    ),
  },
  {
    key: "fee",
    header: "Fee",
    render: (entry) =>
      entry.fee_amount > 0 ? (
        <span className="text-xs text-warning" style={{ fontFamily: "var(--font-mono)" }}>
          ${entry.fee_amount.toFixed(2)}
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

// --- Page Component ---

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
      toast(`Deposited ${formatUSD(parseFloat(depositAmount))} successfully!`, "success");
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

  // --- Unauthenticated ---
  if (!token) {
    return (
      <div className="flex flex-col items-center py-20">
        <div className="glass-card gradient-border-card p-8 w-full max-w-md space-y-4">
          <div className="text-center">
            <h3 className="text-lg font-bold gradient-text">Sign In</h3>
            <p className="mt-1 text-sm text-text-secondary">
              Paste your agent JWT to access your account
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

  // --- Loading ---
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

  const acct = balance?.account;

  const INLINE_STATS = [
    { label: "Deposited", value: formatUSD(acct?.total_deposited ?? 0) },
    { label: "Earned", value: formatUSD(acct?.total_earned ?? 0) },
    { label: "Spent", value: formatUSD(acct?.total_spent ?? 0) },
    { label: "Fees", value: formatUSD(acct?.total_fees_paid ?? 0) },
  ];

  return (
    <div className="space-y-6 animate-fade-in">
      <PageHeader title="Wallet" subtitle="Manage your balance and credits" icon={Wallet} />

      {/* ── Section 1: Compact Account Header ── */}
      <div className="glass-card gradient-border-card p-5">
        <div className="flex flex-col gap-5 lg:flex-row lg:items-center lg:justify-between">
          {/* Balance */}
          <div className="shrink-0">
            <p className="text-[10px] font-semibold uppercase tracking-widest text-text-muted">
              USD Balance
            </p>
            <p
              className="mt-0.5 text-3xl font-bold tracking-tight gradient-text"
              style={{ fontFamily: "var(--font-mono)" }}
            >
              {formatUSD(acct?.balance ?? 0)}
            </p>
          </div>

          {/* Inline stats */}
          <div className="flex flex-wrap gap-x-6 gap-y-2">
            {INLINE_STATS.map((s) => (
              <div key={s.label}>
                <p className="text-[10px] font-medium uppercase tracking-wider text-text-muted">
                  {s.label}
                </p>
                <p
                  className="text-sm font-semibold text-text-primary"
                  style={{ fontFamily: "var(--font-mono)" }}
                >
                  {s.value}
                </p>
              </div>
            ))}
          </div>

          {/* Disconnect */}
          <div className="flex items-center lg:flex-col lg:items-end">
            <button onClick={logout} className="btn-ghost px-3 py-1 text-xs">
              Disconnect
            </button>
          </div>
        </div>
      </div>

      {/* ── Section 2: Buy Credits ── */}
      <div>
        <h3 className="mb-3 flex items-center gap-2 text-xs font-semibold uppercase tracking-widest text-text-secondary">
          <Zap className="h-3.5 w-3.5 text-primary" />
          Buy Credits
        </h3>
        <div className="glass-card gradient-border-card p-5 space-y-4">
          {/* Package grid */}
          <p className="text-[11px] text-text-muted">Quick buy presets — or enter any custom amount below</p>
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
                  className={`relative rounded-xl border p-4 text-center transition-all ${
                    isSelected
                      ? "border-primary bg-primary-glow ring-1 ring-primary/30 shadow-[0_0_16px_rgba(59,130,246,0.1)]"
                      : "border-border-subtle bg-surface-raised/50 hover:border-primary/40 hover:shadow-[0_0_12px_rgba(59,130,246,0.06)]"
                  }`}
                >
                  {pkg.popular && (
                    <div className="absolute -top-2 left-1/2 -translate-x-1/2">
                      <Badge label="Popular" variant="blue" />
                    </div>
                  )}
                  <p className="text-2xl font-bold text-text-primary">${pkg.fiat}</p>
                  <p
                    className="mt-1 text-sm font-semibold text-primary"
                    style={{ fontFamily: "var(--font-mono)" }}
                  >
                    {formatUSD(pkg.fiat)} credit
                  </p>
                  <p className="mt-0.5 text-[11px] text-text-muted">{pkg.label}</p>
                </button>
              );
            })}
          </div>

          {/* Custom amount row */}
          <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
            <input
              type="number"
              value={selectedPackage === null ? depositAmount : ""}
              onChange={(e) => {
                setDepositAmount(e.target.value);
                setSelectedPackage(null);
              }}
              placeholder="Custom amount (USD)"
              min="1"
              step="0.01"
              className="futuristic-input flex-1 px-4 py-2.5 text-sm"
            />
            <button
              onClick={() => depositMutation.mutate()}
              disabled={!depositAmount || parseFloat(depositAmount) <= 0 || depositMutation.isPending}
              className="btn-primary whitespace-nowrap px-6 py-2.5 text-sm font-semibold"
            >
              {depositMutation.isPending ? "Processing..." : "Buy Credits"}
            </button>
          </div>
        </div>
      </div>

      {/* ── Section 3: Transaction History ── */}
      <div>
        <div className="mb-3 flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
          <h3 className="text-xs font-semibold uppercase tracking-widest text-text-secondary">
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
          <Pagination page={page} totalPages={Math.ceil(history.total / 10)} onPageChange={setPage} />
        )}
      </div>
    </div>
  );
}
