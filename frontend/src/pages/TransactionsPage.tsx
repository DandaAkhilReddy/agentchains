import { useState } from "react";
import { useTransactions } from "../hooks/useTransactions";
import { useAuth } from "../hooks/useAuth";
import DataTable, { type Column } from "../components/DataTable";
import Badge, { statusVariant } from "../components/Badge";
import CopyButton from "../components/CopyButton";
import { truncateId, formatUSDC, relativeTime } from "../lib/format";
import type { Transaction, TransactionStatus } from "../types/api";

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
                  ? "border border-red-500/30 bg-red-500/10 text-red-400"
                  : isComplete
                    ? "bg-emerald-500 text-white"
                    : isCurrent
                      ? "border-2 border-blue-400 text-blue-400"
                      : "border border-zinc-700 text-zinc-600"
              }`}
              title={step.label}
            >
              {isComplete ? "\u2713" : i + 1}
            </div>
            {i < PIPELINE_STEPS.length - 1 && (
              <div
                className={`h-0.5 w-4 ${
                  !isFailed && currentStep > i ? "bg-emerald-500" : "bg-zinc-700"
                }`}
              />
            )}
          </div>
        );
      })}
    </div>
  );
}

const columns: Column<Transaction>[] = [
  {
    key: "id",
    header: "ID",
    render: (tx) => (
      <span className="flex items-center gap-1">
        <span className="text-zinc-400" style={{ fontFamily: "var(--font-mono)" }}>
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
      <span style={{ fontFamily: "var(--font-mono)" }}>
        {formatUSDC(tx.amount_usdc)}
      </span>
    ),
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
        <span className="text-zinc-500" style={{ fontFamily: "var(--font-mono)" }}>
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
      <span className="text-zinc-500">{relativeTime(tx.initiated_at)}</span>
    ),
  },
];

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

  // Token input view
  if (!token) {
    return (
      <div className="flex flex-col items-center py-20">
        <div className="w-full max-w-md space-y-4">
          <div className="text-center">
            <h3 className="text-lg font-medium">Connect Agent</h3>
            <p className="mt-1 text-sm text-zinc-500">
              Paste your agent JWT to view transactions
            </p>
          </div>
          <input
            type="text"
            value={inputToken}
            onChange={(e) => setInputToken(e.target.value)}
            placeholder="eyJhbGciOi..."
            className="w-full rounded-lg border border-zinc-700 bg-zinc-900 px-4 py-3 text-sm text-white placeholder-zinc-600 outline-none focus:border-emerald-500/50"
            style={{ fontFamily: "var(--font-mono)" }}
          />
          <button
            onClick={handleConnect}
            disabled={!inputToken.trim()}
            className="w-full rounded-lg bg-emerald-600 px-4 py-2.5 text-sm font-medium text-white transition-colors hover:bg-emerald-500 disabled:opacity-30"
          >
            Connect
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Header bar */}
      <div className="flex flex-wrap items-center gap-3">
        <select
          value={statusFilter}
          onChange={(e) => { setStatusFilter(e.target.value); setPage(1); }}
          className="rounded-lg border border-zinc-700 bg-zinc-900 px-3 py-2 text-sm text-white outline-none"
        >
          <option value="">All Status</option>
          <option value="initiated">Initiated</option>
          <option value="payment_pending">Payment Pending</option>
          <option value="payment_confirmed">Payment Confirmed</option>
          <option value="delivered">Delivered</option>
          <option value="completed">Completed</option>
          <option value="failed">Failed</option>
          <option value="disputed">Disputed</option>
        </select>
        <button
          onClick={logout}
          className="ml-auto rounded-lg border border-zinc-700 px-3 py-1.5 text-sm text-zinc-400 transition-colors hover:bg-zinc-800"
        >
          Disconnect
        </button>
      </div>

      {error && (
        <div className="rounded-lg border border-red-500/20 bg-red-500/5 px-4 py-3 text-sm text-red-400">
          {(error as Error).message}
        </div>
      )}

      <DataTable
        columns={columns}
        data={data?.transactions ?? []}
        isLoading={isLoading}
        keyFn={(tx) => tx.id}
        emptyMessage="No transactions found"
      />

      {data && data.total > 20 && (
        <div className="flex items-center justify-end gap-2">
          <button
            disabled={page <= 1}
            onClick={() => setPage((p) => p - 1)}
            className="rounded-lg border border-zinc-700 px-3 py-1.5 text-sm text-zinc-400 transition-colors hover:bg-zinc-800 disabled:opacity-30"
          >
            Prev
          </button>
          <button
            disabled={page * 20 >= data.total}
            onClick={() => setPage((p) => p + 1)}
            className="rounded-lg border border-zinc-700 px-3 py-1.5 text-sm text-zinc-400 transition-colors hover:bg-zinc-800 disabled:opacity-30"
          >
            Next
          </button>
        </div>
      )}
    </div>
  );
}
