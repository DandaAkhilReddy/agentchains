import { useState } from "react";
import { useTransactions } from "../hooks/useTransactions";
import DataTable, { type Column } from "../components/DataTable";
import Badge, { statusVariant } from "../components/Badge";
import { truncateId, formatUSDC, relativeTime } from "../lib/format";
import type { Transaction } from "../types/api";

const columns: Column<Transaction>[] = [
  {
    key: "id",
    header: "ID",
    render: (tx) => (
      <span className="text-zinc-400" style={{ fontFamily: "var(--font-mono)" }}>
        {truncateId(tx.id)}
      </span>
    ),
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
      <span className="text-zinc-500" style={{ fontFamily: "var(--font-mono)" }}>
        {truncateId(tx.buyer_id)}
      </span>
    ),
  },
  {
    key: "seller",
    header: "Seller",
    render: (tx) => (
      <span className="text-zinc-500" style={{ fontFamily: "var(--font-mono)" }}>
        {truncateId(tx.seller_id)}
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
  const [token, setToken] = useState(() => localStorage.getItem("agent_jwt") ?? "");
  const [inputToken, setInputToken] = useState(token);
  const [statusFilter, setStatusFilter] = useState("");
  const [page, setPage] = useState(1);

  const { data, isLoading, error } = useTransactions(token || null, {
    status: statusFilter || undefined,
    page,
  });

  const handleConnect = () => {
    const t = inputToken.trim();
    setToken(t);
    if (t) localStorage.setItem("agent_jwt", t);
    else localStorage.removeItem("agent_jwt");
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
          onClick={() => { setToken(""); setInputToken(""); localStorage.removeItem("agent_jwt"); }}
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
