import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useAuth } from "../hooks/useAuth";
import { useToast } from "../components/Toast";
import PageHeader from "../components/PageHeader";
import Pagination from "../components/Pagination";
import DataTable, { type Column } from "../components/DataTable";
import Badge from "../components/Badge";
import { SkeletonCard } from "../components/Skeleton";
import {
  fetchRedemptions,
  fetchRedemptionMethods,
  createRedemption,
  cancelRedemption,
} from "../lib/api";
import { formatUSD, relativeTime } from "../lib/format";
import {
  Gift,
  Zap,
  CreditCard,
  Building2,
  Smartphone,
  KeyRound,
  ArrowDownCircle,
  Clock,
  CheckCircle2,
  XCircle,
  AlertCircle,
  Loader2,
} from "lucide-react";
import type { RedemptionRequest, RedemptionMethodInfo } from "../types/api";

/* ─── Redemption method config ─── */

const METHOD_ICONS: Record<string, typeof Gift> = {
  api_credits: Zap,
  gift_card: CreditCard,
  bank_withdrawal: Building2,
  upi: Smartphone,
};

const METHOD_COLORS: Record<string, { bg: string; border: string; glow: string; text: string }> = {
  api_credits: {
    bg: "rgba(96,165,250,0.06)",
    border: "rgba(96,165,250,0.15)",
    glow: "rgba(96,165,250,0.08)",
    text: "#60a5fa",
  },
  gift_card: {
    bg: "rgba(167,139,250,0.06)",
    border: "rgba(167,139,250,0.15)",
    glow: "rgba(167,139,250,0.08)",
    text: "#a78bfa",
  },
  bank_withdrawal: {
    bg: "rgba(52,211,153,0.06)",
    border: "rgba(52,211,153,0.15)",
    glow: "rgba(52,211,153,0.08)",
    text: "#34d399",
  },
  upi: {
    bg: "rgba(251,191,36,0.06)",
    border: "rgba(251,191,36,0.15)",
    glow: "rgba(251,191,36,0.08)",
    text: "#fbbf24",
  },
};

const METHOD_DESCRIPTIONS: Record<string, string> = {
  api_credits: "Convert balance to API usage credits instantly",
  gift_card: "Redeem as digital gift card vouchers",
  bank_withdrawal: "Direct bank transfer to your account",
  upi: "Instant UPI transfer to your linked ID",
};

const METHOD_MINIMUMS: Record<string, number> = {
  api_credits: 0.1,
  gift_card: 1.0,
  bank_withdrawal: 10.0,
  upi: 5.0,
};

/* ─── Status badge map ─── */

const STATUS_CONFIG: Record<
  string,
  { icon: typeof CheckCircle2; color: string; variant: string; label: string }
> = {
  pending: { icon: Clock, color: "text-[#fbbf24]", variant: "amber", label: "Pending" },
  processing: { icon: Loader2, color: "text-[#60a5fa]", variant: "blue", label: "Processing" },
  completed: { icon: CheckCircle2, color: "text-[#34d399]", variant: "green", label: "Completed" },
  failed: { icon: XCircle, color: "text-[#f87171]", variant: "red", label: "Failed" },
  rejected: { icon: AlertCircle, color: "text-[#f87171]", variant: "red", label: "Rejected" },
};

/* ─── Redemption history columns ─── */

const redemptionColumns: Column<RedemptionRequest>[] = [
  {
    key: "redemption_type",
    header: "Method",
    render: (entry) => {
      const Icon = METHOD_ICONS[entry.redemption_type] ?? Gift;
      const colors = METHOD_COLORS[entry.redemption_type];
      return (
        <span className="flex items-center gap-2" style={{ color: colors?.text ?? "#94a3b8" }}>
          <Icon className="h-4 w-4" />
          <span className="text-xs font-semibold capitalize">
            {entry.redemption_type.replace(/_/g, " ")}
          </span>
        </span>
      );
    },
  },
  {
    key: "amount_usd",
    header: "Amount",
    render: (entry) => (
      <span
        className="text-sm font-bold text-[#e2e8f0]"
        style={{ fontFamily: "var(--font-mono)" }}
      >
        {formatUSD(entry.amount_usd)}
      </span>
    ),
  },
  {
    key: "status",
    header: "Status",
    render: (entry) => {
      const cfg = STATUS_CONFIG[entry.status] ?? STATUS_CONFIG.pending;
      return <Badge label={cfg.label} variant={cfg.variant as any} />;
    },
  },
  {
    key: "created_at",
    header: "Requested",
    render: (entry) => (
      <span className="text-xs text-[#64748b]">{relativeTime(entry.created_at)}</span>
    ),
  },
  {
    key: "completed_at",
    header: "Completed",
    render: (entry) => (
      <span className="text-xs text-[#64748b]">
        {entry.completed_at ? relativeTime(entry.completed_at) : "--"}
      </span>
    ),
  },
];

/* ─── Page Component ─── */

export default function RedeemPage() {
  const { token, login } = useAuth();
  const { toast } = useToast();
  const queryClient = useQueryClient();
  const [inputToken, setInputToken] = useState("");
  const [selectedMethod, setSelectedMethod] = useState<string | null>(null);
  const [amount, setAmount] = useState("");
  const [page, setPage] = useState(1);

  /* ── Data fetching ── */

  const { data: methods, isLoading: methodsLoading } = useQuery({
    queryKey: ["redemption-methods"],
    queryFn: fetchRedemptionMethods,
  });

  const { data: history, isLoading: histLoading } = useQuery({
    queryKey: ["redemptions", page],
    queryFn: () =>
      fetchRedemptions(token!, { page, page_size: 10 }),
    enabled: !!token,
  });

  const redeemMutation = useMutation({
    mutationFn: () =>
      createRedemption(token!, {
        redemption_type: selectedMethod!,
        amount_usd: parseFloat(amount),
      }),
    onSuccess: () => {
      toast(`Withdrawal of ${formatUSD(parseFloat(amount))} requested!`, "success");
      setAmount("");
      setSelectedMethod(null);
      queryClient.invalidateQueries({ queryKey: ["redemptions"] });
      queryClient.invalidateQueries({ queryKey: ["wallet-balance"] });
    },
    onError: (err) => toast((err as Error).message, "error"),
  });

  const cancelMutation = useMutation({
    mutationFn: (id: string) => cancelRedemption(token!, id),
    onSuccess: () => {
      toast("Redemption cancelled", "success");
      queryClient.invalidateQueries({ queryKey: ["redemptions"] });
      queryClient.invalidateQueries({ queryKey: ["wallet-balance"] });
    },
    onError: (err) => toast((err as Error).message, "error"),
  });

  const handleConnect = () => {
    const t = inputToken.trim();
    if (t) login(t);
  };

  /* Validation */
  const minAmount = selectedMethod ? METHOD_MINIMUMS[selectedMethod] ?? 0 : 0;
  const parsedAmount = parseFloat(amount);
  const isValidAmount = !isNaN(parsedAmount) && parsedAmount >= minAmount;

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
              Paste your agent JWT token to access withdrawals
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
  if (methodsLoading) {
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

  /* Build method cards from API data or fallback */
  const methodList: {
    type: string;
    label: string;
    min: number;
    processing: string;
    available: boolean;
  }[] = methods?.methods?.map((m: RedemptionMethodInfo) => ({
    type: m.type,
    label: m.label,
    min: m.min_usd,
    processing: m.processing_time,
    available: m.available,
  })) ?? [
    { type: "api_credits", label: "API Credits", min: 0.10, processing: "Instant", available: true },
    { type: "gift_card", label: "Gift Card", min: 1.00, processing: "1-2 hours", available: true },
    { type: "bank_withdrawal", label: "Bank Transfer", min: 10.00, processing: "2-5 days", available: true },
    { type: "upi", label: "UPI Transfer", min: 5.00, processing: "Instant", available: true },
  ];

  /* Columns with cancel action */
  const columnsWithAction: Column<RedemptionRequest>[] = [
    ...redemptionColumns,
    {
      key: "actions",
      header: "",
      render: (entry) =>
        entry.status === "pending" ? (
          <button
            onClick={(e) => {
              e.stopPropagation();
              cancelMutation.mutate(entry.id);
            }}
            disabled={cancelMutation.isPending}
            className="rounded-lg border border-[rgba(248,113,113,0.2)] bg-[rgba(248,113,113,0.06)] px-2.5 py-1 text-[10px] font-semibold text-[#f87171] transition-all duration-200 hover:border-[rgba(248,113,113,0.4)] hover:bg-[rgba(248,113,113,0.12)]"
          >
            Cancel
          </button>
        ) : null,
    },
  ];

  return (
    <div className="space-y-6 animate-fade-in">
      <PageHeader
        title="Withdraw Funds"
        subtitle="Choose a redemption method and request a withdrawal"
        icon={Gift}
      />

      {/* ── Redemption Methods ── */}
      <div>
        <h3 className="mb-3 flex items-center gap-2 text-xs font-bold uppercase tracking-[0.15em] text-[#94a3b8]">
          <ArrowDownCircle className="h-3.5 w-3.5 text-[#60a5fa]" />
          Redemption Methods
        </h3>

        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
          {methodList.map((method) => {
            const isSelected = selectedMethod === method.type;
            const colors = METHOD_COLORS[method.type] ?? METHOD_COLORS.api_credits;
            const Icon = METHOD_ICONS[method.type] ?? Gift;

            return (
              <button
                key={method.type}
                onClick={() => {
                  setSelectedMethod(method.type);
                  setAmount("");
                }}
                disabled={!method.available}
                className="group relative rounded-2xl border p-5 text-left transition-all duration-300 disabled:cursor-not-allowed disabled:opacity-40"
                style={{
                  background: isSelected
                    ? `linear-gradient(135deg, ${colors.bg} 0%, transparent 100%)`
                    : "#0a0e1a",
                  borderColor: isSelected ? colors.border : "rgba(255,255,255,0.06)",
                  boxShadow: isSelected
                    ? `0 0 24px ${colors.glow}, inset 0 1px 0 ${colors.border}`
                    : "none",
                }}
              >
                {/* Icon */}
                <div
                  className="mb-3 flex h-10 w-10 items-center justify-center rounded-xl transition-all duration-200"
                  style={{
                    background: isSelected ? colors.bg : "rgba(255,255,255,0.04)",
                    boxShadow: isSelected ? `0 0 12px ${colors.glow}` : "none",
                  }}
                >
                  <Icon
                    className="h-5 w-5 transition-colors duration-200"
                    style={{ color: isSelected ? colors.text : "#64748b" }}
                  />
                </div>

                {/* Label */}
                <p
                  className="text-sm font-bold transition-colors duration-200"
                  style={{ color: isSelected ? colors.text : "#e2e8f0" }}
                >
                  {method.label}
                </p>

                {/* Description */}
                <p className="mt-1 text-[11px] leading-relaxed text-[#64748b]">
                  {METHOD_DESCRIPTIONS[method.type] ?? "Withdraw your balance"}
                </p>

                {/* Min + processing */}
                <div className="mt-3 flex items-center gap-3">
                  <span
                    className="text-[10px] font-semibold"
                    style={{ color: colors.text }}
                  >
                    Min ${method.min.toFixed(2)}
                  </span>
                  <span className="text-[10px] text-[#64748b]">
                    {method.processing}
                  </span>
                </div>

                {/* Not available overlay */}
                {!method.available && (
                  <div className="absolute inset-0 flex items-center justify-center rounded-2xl bg-[rgba(10,14,26,0.7)]">
                    <span className="text-xs font-medium text-[#64748b]">
                      Unavailable
                    </span>
                  </div>
                )}
              </button>
            );
          })}
        </div>
      </div>

      {/* ── Amount Input + Submit ── */}
      {selectedMethod && (
        <div
          className="space-y-4 rounded-2xl border border-[rgba(255,255,255,0.06)] p-6"
          style={{
            background:
              "linear-gradient(180deg, #141928 0%, rgba(26,32,53,0.8) 100%)",
            boxShadow: "0 0 30px rgba(0,0,0,0.2)",
          }}
        >
          <div className="flex items-center gap-3">
            <h4 className="text-sm font-bold text-[#e2e8f0]">
              Withdrawal Amount
            </h4>
            <span className="text-[10px] text-[#64748b]">
              Min: ${minAmount.toFixed(2)}
            </span>
          </div>

          <div className="flex flex-col gap-3 sm:flex-row sm:items-start">
            {/* Amount input */}
            <div className="flex-1">
              <div className="relative">
                <span className="pointer-events-none absolute left-4 top-1/2 -translate-y-1/2 text-sm font-bold text-[#64748b]">
                  $
                </span>
                <input
                  type="number"
                  value={amount}
                  onChange={(e) => setAmount(e.target.value)}
                  placeholder={`${minAmount.toFixed(2)} or more`}
                  min={minAmount}
                  step="0.01"
                  className="w-full rounded-xl border border-[rgba(255,255,255,0.06)] bg-[#0a0e1a] py-3 pl-8 pr-4 text-sm text-[#e2e8f0] placeholder-[#64748b] outline-none transition-all duration-300 focus:border-[rgba(96,165,250,0.4)] focus:ring-1 focus:ring-[rgba(96,165,250,0.3)]"
                  style={{
                    fontFamily: "var(--font-mono)",
                    boxShadow: "inset 0 2px 4px rgba(0,0,0,0.2)",
                  }}
                />
              </div>
              {/* Validation message */}
              {amount && !isValidAmount && (
                <p className="mt-1.5 text-[11px] text-[#f87171]">
                  Minimum withdrawal is ${minAmount.toFixed(2)}
                </p>
              )}
            </div>

            {/* Submit */}
            <button
              onClick={() => redeemMutation.mutate()}
              disabled={!isValidAmount || redeemMutation.isPending}
              className="whitespace-nowrap rounded-xl px-8 py-3 text-sm font-bold text-white transition-all duration-300 hover:shadow-[0_0_24px_rgba(96,165,250,0.2)] disabled:cursor-not-allowed disabled:opacity-40"
              style={{
                background: "linear-gradient(135deg, #60a5fa 0%, #a78bfa 100%)",
                boxShadow: "0 4px 16px rgba(96,165,250,0.15)",
              }}
            >
              {redeemMutation.isPending ? (
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
                "Request Withdrawal"
              )}
            </button>
          </div>
        </div>
      )}

      {/* ── Redemption History ── */}
      <div>
        <h3 className="mb-3 text-xs font-bold uppercase tracking-[0.15em] text-[#94a3b8]">
          Redemption History
        </h3>
        <DataTable
          columns={columnsWithAction}
          data={history?.redemptions ?? []}
          isLoading={histLoading}
          keyFn={(e) => e.id}
          emptyMessage="No redemptions yet"
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
