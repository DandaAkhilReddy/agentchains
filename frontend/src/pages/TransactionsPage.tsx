import { useState } from "react";
import { useTransactions } from "../hooks/useTransactions";
import { useAuth } from "../hooks/useAuth";
import DataTable, { type Column } from "../components/DataTable";
import Badge, { statusVariant } from "../components/Badge";
import CopyButton from "../components/CopyButton";
import PageHeader from "../components/PageHeader";
import SubTabNav from "../components/SubTabNav";
import Pagination from "../components/Pagination";
import { truncateId, formatUSD, relativeTime } from "../lib/format";
import { ArrowLeftRight, LogIn, Shield, Clock, AlertTriangle } from "lucide-react";
import type { Transaction, TransactionStatus } from "../types/api";

/* ── Pipeline Steps ──────────────────────────────────────── */

const PIPELINE_STEPS: { key: TransactionStatus; label: string }[] = [
  { key: "initiated", label: "Initiated" },
  { key: "payment_confirmed", label: "Payment" },
  { key: "delivered", label: "Delivered" },
  { key: "completed", label: "Completed" },
];

const STATUS_ORDER: Record<string, number> = {
  initiated: 0,
  payment_pending: 0,
  payment_confirmed: 1,
  delivered: 2,
  verified: 3,
  completed: 3,
  failed: -1,
  disputed: -1,
};

/* ── Status Color Helpers ────────────────────────────────── */

function statusDotColor(status: TransactionStatus): string {
  const map: Record<string, string> = {
    completed: "#34d399",
    verified: "#34d399",
    delivered: "#22d3ee",
    payment_confirmed: "#60a5fa",
    initiated: "#94a3b8",
    payment_pending: "#fbbf24",
    failed: "#f87171",
    disputed: "#fb923c",
  };
  return map[status] ?? "#94a3b8";
}

function amountColor(status: TransactionStatus): string {
  if (status === "failed" || status === "disputed") return "text-[#f87171]";
  if (status === "completed" || status === "verified") return "text-[#34d399]";
  return "text-[#60a5fa]";
}

/* ── Pipeline ────────────────────────────────────────────── */

function Pipeline({ status }: { status: TransactionStatus }) {
  const currentStep = STATUS_ORDER[status] ?? -1;
  const isFailed = status === "failed" || status === "disputed";

  return (
    <div className="flex items-center gap-1">
      {PIPELINE_STEPS.map((step, i) => {
        const isComplete = !isFailed && currentStep >= i;
        const isCurrent = !isFailed && currentStep === i;
        return (
          <div key={step.key} className="flex items-center gap-1">
            <div
              className={`flex h-6 w-6 items-center justify-center rounded-full text-[10px] font-bold transition-colors ${
                isFailed
                  ? "border border-[rgba(248,113,113,0.3)] bg-[rgba(248,113,113,0.1)] text-[#f87171]"
                  : isComplete
                    ? "bg-[#60a5fa] text-[#0a0e1a] shadow-[0_0_8px_rgba(96,165,250,0.3)]"
                    : isCurrent
                      ? "border-2 border-[#60a5fa] text-[#60a5fa] animate-pulse"
                      : "border border-[rgba(255,255,255,0.08)] text-[#64748b]"
              }`}
              title={step.label}
            >
              {isComplete ? "\u2713" : i + 1}
            </div>
            {i < PIPELINE_STEPS.length - 1 && (
              <div
                className={`h-0.5 w-4 rounded-full transition-colors ${
                  !isFailed && currentStep > i
                    ? "bg-[#60a5fa] shadow-[0_0_4px_rgba(96,165,250,0.3)]"
                    : "bg-[rgba(255,255,255,0.06)]"
                }`}
              />
            )}
          </div>
        );
      })}
    </div>
  );
}

/* ── Filter Tabs ─────────────────────────────────────────── */

const FILTER_TABS = [
  { id: "", label: "All" },
  { id: "initiated", label: "Pending" },
  { id: "completed", label: "Completed" },
  { id: "failed", label: "Failed" },
];

/* ── Table Columns ───────────────────────────────────────── */

const columns: Column<Transaction>[] = [
  {
    key: "status_dot",
    header: "",
    render: (tx) => (
      <span className="flex items-center justify-center">
        <span className="relative flex h-2.5 w-2.5">
          {(tx.status === "initiated" || tx.status === "payment_pending") && (
            <span
              className="absolute inline-flex h-full w-full animate-ping rounded-full opacity-40"
              style={{ backgroundColor: statusDotColor(tx.status) }}
            />
          )}
          <span
            className="relative inline-flex h-2.5 w-2.5 rounded-full"
            style={{ backgroundColor: statusDotColor(tx.status) }}
          />
        </span>
      </span>
    ),
    className: "w-8",
  },
  {
    key: "id",
    header: "ID",
    render: (tx) => (
      <span className="flex items-center gap-1">
        <span className="text-[#94a3b8] font-mono text-xs">
          {truncateId(tx.id)}
        </span>
        <CopyButton value={tx.id} />
      </span>
    ),
  },
  {
    key: "pipeline",
    header: "Progress",
    render: (tx) => <Pipeline status={tx.status} />,
  },
  {
    key: "amount",
    header: "Amount",
    render: (tx) => (
      <span className={`text-sm font-semibold font-mono ${amountColor(tx.status)}`}>
        {formatUSD(tx.amount_usdc)}
      </span>
    ),
  },
  {
    key: "payment_method",
    header: "Payment",
    render: (tx) => {
      const method = tx.payment_method ?? "simulated";
      const cfg: Record<string, { label: string; variant: "cyan" | "green" | "gray" }> = {
        balance: { label: "Balance", variant: "cyan" },
        fiat: { label: "Fiat", variant: "green" },
        simulated: { label: "Simulated", variant: "gray" },
      };
      const { label, variant } = cfg[method] ?? cfg.simulated;
      return <Badge label={label} variant={variant} />;
    },
  },
  {
    key: "status",
    header: "Status",
    render: (tx) => (
      <Badge
        label={tx.status.replace(/_/g, " ")}
        variant={statusVariant(tx.status)}
      />
    ),
  },
  {
    key: "buyer",
    header: "Buyer",
    render: (tx) => (
      <span className="flex items-center gap-1">
        <span className="text-[#64748b] font-mono text-xs">
          {truncateId(tx.buyer_id)}
        </span>
        <CopyButton value={tx.buyer_id} />
      </span>
    ),
  },
  {
    key: "verification",
    header: "Verified",
    render: (tx) => (
      <Badge
        label={tx.verification_status}
        variant={tx.verification_status === "verified" ? "green" : "gray"}
      />
    ),
  },
  {
    key: "initiated",
    header: "Initiated",
    render: (tx) => (
      <span className="text-xs text-[#64748b] flex items-center gap-1">
        <Clock className="h-3 w-3" />
        {relativeTime(tx.initiated_at)}
      </span>
    ),
  },
];

/* ── Auth Gate ────────────────────────────────────────────── */

function AuthGate({
  inputToken,
  setInputToken,
  onConnect,
}: {
  inputToken: string;
  setInputToken: (v: string) => void;
  onConnect: () => void;
}) {
  return (
    <div className="flex flex-col items-center py-20">
      <div className="relative w-full max-w-md overflow-hidden rounded-2xl border border-[rgba(255,255,255,0.06)] bg-[#141928]">
        {/* Top glow accent */}
        <div className="absolute inset-x-0 top-0 h-[2px] bg-gradient-to-r from-transparent via-[#60a5fa] to-transparent opacity-60" />

        <div className="p-8 space-y-6">
          <div className="text-center">
            <div className="mx-auto mb-4 flex h-14 w-14 items-center justify-center rounded-2xl bg-[rgba(96,165,250,0.1)] shadow-[0_0_24px_rgba(96,165,250,0.1)]">
              <LogIn className="h-6 w-6 text-[#60a5fa]" />
            </div>
            <h3 className="text-lg font-bold gradient-text">Connect Agent</h3>
            <p className="mt-1 text-sm text-[#94a3b8]">
              Paste your agent JWT to view transactions
            </p>
          </div>

          <div className="space-y-3">
            <input
              type="text"
              value={inputToken}
              onChange={(e) => setInputToken(e.target.value)}
              placeholder="eyJhbGciOi..."
              className="w-full rounded-xl border border-[rgba(255,255,255,0.06)] bg-[#0a0e1a] px-4 py-3 text-sm text-[#e2e8f0] font-mono placeholder-[#64748b] outline-none transition-all duration-200 focus:border-[rgba(96,165,250,0.3)] focus:shadow-[0_0_16px_rgba(96,165,250,0.06)]"
            />
            <button
              onClick={onConnect}
              disabled={!inputToken.trim()}
              className="w-full rounded-xl bg-[#60a5fa] px-4 py-2.5 text-sm font-semibold text-[#0a0e1a] transition-all duration-200 hover:bg-[#93c5fd] hover:shadow-[0_0_20px_rgba(96,165,250,0.2)] disabled:opacity-30 disabled:cursor-not-allowed"
            >
              Connect
            </button>
          </div>

          <div className="flex items-center gap-2 justify-center">
            <Shield className="h-3.5 w-3.5 text-[#64748b]" />
            <span className="text-[11px] text-[#64748b]">
              JWT is stored locally and never sent to third parties
            </span>
          </div>
        </div>
      </div>
    </div>
  );
}

/* ── Transaction Summary Stats ───────────────────────────── */

function TransactionStats({ transactions }: { transactions: Transaction[] }) {
  const completed = transactions.filter(
    (t) => t.status === "completed" || t.status === "verified",
  ).length;
  const pending = transactions.filter(
    (t) =>
      t.status === "initiated" ||
      t.status === "payment_pending" ||
      t.status === "payment_confirmed" ||
      t.status === "delivered",
  ).length;
  const failed = transactions.filter(
    (t) => t.status === "failed" || t.status === "disputed",
  ).length;
  const totalVolume = transactions.reduce((s, t) => s + t.amount_usdc, 0);

  return (
    <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
      <div className="rounded-xl border border-[rgba(255,255,255,0.06)] bg-[#141928] p-4">
        <div className="text-[11px] text-[#64748b] mb-1">Total Volume</div>
        <div className="text-lg font-mono font-bold text-[#e2e8f0]">
          {formatUSD(totalVolume)}
        </div>
      </div>
      <div className="rounded-xl border border-[rgba(52,211,153,0.12)] bg-[#141928] p-4">
        <div className="text-[11px] text-[#64748b] mb-1">Completed</div>
        <div className="text-lg font-mono font-bold text-[#34d399]">{completed}</div>
      </div>
      <div className="rounded-xl border border-[rgba(251,191,36,0.12)] bg-[#141928] p-4">
        <div className="text-[11px] text-[#64748b] mb-1">Pending</div>
        <div className="text-lg font-mono font-bold text-[#fbbf24]">{pending}</div>
      </div>
      <div className="rounded-xl border border-[rgba(248,113,113,0.12)] bg-[#141928] p-4">
        <div className="text-[11px] text-[#64748b] mb-1">Failed</div>
        <div className="text-lg font-mono font-bold text-[#f87171]">{failed}</div>
      </div>
    </div>
  );
}

/* ── Main Page ───────────────────────────────────────────── */

export default function TransactionsPage() {
  const { token, login, logout } = useAuth();
  const [inputToken, setInputToken] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [page, setPage] = useState(1);

  const { data, isLoading, error } = useTransactions(token || null, {
    status: statusFilter || undefined,
    page,
  });

  const handleConnect = () => {
    const t = inputToken.trim();
    if (t) login(t);
  };

  // Auth gate
  if (!token) {
    return (
      <div className="space-y-6">
        <PageHeader
          title="Transactions"
          subtitle="Track purchases and deliveries"
          icon={ArrowLeftRight}
        />
        <AuthGate
          inputToken={inputToken}
          setInputToken={setInputToken}
          onConnect={handleConnect}
        />
      </div>
    );
  }

  const transactions = data?.transactions ?? [];

  return (
    <div className="space-y-5">
      <PageHeader
        title="Transactions"
        subtitle="Track purchases and deliveries"
        icon={ArrowLeftRight}
        actions={
          <button
            onClick={logout}
            className="rounded-xl border border-[rgba(255,255,255,0.06)] bg-[#1a2035] px-4 py-2 text-xs font-medium text-[#94a3b8] transition-all duration-200 hover:border-[rgba(248,113,113,0.2)] hover:text-[#f87171] hover:bg-[rgba(248,113,113,0.05)]"
          >
            Disconnect
          </button>
        }
      />

      {/* ── Summary Stats ────────────────────────────── */}
      {transactions.length > 0 && <TransactionStats transactions={transactions} />}

      {/* ── Filter Tabs ──────────────────────────────── */}
      <div className="flex items-center justify-between">
        <SubTabNav
          tabs={FILTER_TABS}
          active={statusFilter}
          onChange={(id) => {
            setStatusFilter(id);
            setPage(1);
          }}
        />
        {data && (
          <span className="text-xs text-[#64748b]">
            {data.total} transaction{data.total !== 1 ? "s" : ""}
          </span>
        )}
      </div>

      {/* ── Error ────────────────────────────────────── */}
      {error && (
        <div className="flex items-center gap-3 rounded-xl border border-[rgba(248,113,113,0.2)] bg-[rgba(248,113,113,0.05)] px-4 py-3">
          <AlertTriangle className="h-4 w-4 text-[#f87171] flex-shrink-0" />
          <span className="text-sm text-[#f87171]">{(error as Error).message}</span>
        </div>
      )}

      {/* ── Data Table ───────────────────────────────── */}
      <DataTable
        columns={columns}
        data={transactions}
        isLoading={isLoading}
        keyFn={(tx) => tx.id}
        emptyMessage="No transactions found"
      />

      {/* ── Pagination ───────────────────────────────── */}
      {data && data.total > 20 && (
        <Pagination
          page={page}
          totalPages={Math.ceil(data.total / 20)}
          onPageChange={setPage}
        />
      )}
    </div>
  );
}
