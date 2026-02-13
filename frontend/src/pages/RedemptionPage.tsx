import { useEffect, useState } from "react";
import { CreditCard, Gift, Building2, Smartphone, Loader2, CheckCircle, XCircle, Clock, ArrowRight } from "lucide-react";
import { createRedemption, fetchRedemptions, cancelRedemption, fetchCreatorWallet } from "../lib/api";
import { formatUSD } from "../lib/format";
import type { RedemptionRequest } from "../types/api";
import PageHeader from "../components/PageHeader";
import Badge from "../components/Badge";
import AnimatedCounter from "../components/AnimatedCounter";

interface Props {
  token: string;
}

const METHODS = [
  { type: "api_credits", label: "API Credits", icon: CreditCard, min: 0.10, time: "Instant", desc: "Convert to API call credits" },
  { type: "gift_card", label: "Gift Card", icon: Gift, min: 1.00, time: "24 hours", desc: "Amazon gift card delivery" },
  { type: "upi", label: "UPI Transfer", icon: Smartphone, min: 5.00, time: "Minutes", desc: "Direct to your UPI ID (India)" },
  { type: "bank_withdrawal", label: "Bank Transfer", icon: Building2, min: 10.00, time: "3-7 days", desc: "Wire to your bank account" },
];

const STATUS_ICONS: Record<string, any> = {
  pending: Clock,
  processing: Loader2,
  completed: CheckCircle,
  failed: XCircle,
  rejected: XCircle,
};

const STATUS_VARIANTS: Record<string, "yellow" | "blue" | "green" | "red" | "gray"> = {
  pending: "yellow",
  processing: "blue",
  completed: "green",
  failed: "red",
  rejected: "red",
};

export default function RedemptionPage({ token }: Props) {
  const [balance, setBalance] = useState(0);
  const [selectedType, setSelectedType] = useState("");
  const [amount, setAmount] = useState("");
  const [loading, setLoading] = useState(false);
  const [history, setHistory] = useState<RedemptionRequest[]>([]);
  const [msg, setMsg] = useState<{ type: "ok" | "err"; text: string } | null>(null);

  const loadData = async () => {
    try {
      const wallet = await fetchCreatorWallet(token);
      setBalance(wallet.balance);
    } catch {}
    try {
      const res = await fetchRedemptions(token);
      setHistory(res.redemptions || []);
    } catch {}
  };

  useEffect(() => { loadData(); }, [token]);

  const handleRedeem = async () => {
    if (!selectedType || !amount) return;
    setLoading(true);
    setMsg(null);
    try {
      await createRedemption(token, {
        redemption_type: selectedType,
        amount_usd: parseFloat(amount),
      });
      setMsg({ type: "ok", text: "Withdrawal request created successfully!" });
      setAmount("");
      setSelectedType("");
      loadData();
    } catch (e: any) {
      setMsg({ type: "err", text: e.message || "Withdrawal failed" });
    } finally {
      setLoading(false);
    }
  };

  const handleCancel = async (id: string) => {
    try {
      await cancelRedemption(token, id);
      loadData();
    } catch {}
  };

  return (
    <div className="space-y-6">
      <PageHeader
        title="Withdraw Funds"
        subtitle="Convert your earnings to API credits, gift cards, or cash"
        icon={Gift}
      />

      {/* Balance Banner */}
      <div className="glass-card gradient-border-card p-6">
        <div className="flex items-center justify-between">
          <div>
            <p className="text-xs font-semibold uppercase tracking-widest text-text-secondary">Available Balance</p>
            <p className="mt-1 text-3xl font-bold gradient-text" style={{ fontFamily: "var(--font-mono)" }}>
              $<AnimatedCounter value={balance} decimals={2} />
            </p>
          </div>
        </div>
      </div>

      {/* Method Selection */}
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
        {METHODS.map((m) => {
          const eligible = balance >= m.min;
          const active = selectedType === m.type;
          return (
            <button
              key={m.type}
              onClick={() => eligible && setSelectedType(m.type)}
              disabled={!eligible}
              className={`glass-card rounded-xl p-4 text-left transition-all ${
                active
                  ? "border-primary bg-primary-glow ring-1 ring-primary/30"
                  : eligible
                    ? "border-border-subtle hover:border-primary/40 glow-hover"
                    : "border-border-subtle opacity-40 cursor-not-allowed"
              }`}
            >
              <m.icon className={`mb-2 h-6 w-6 ${active ? "text-primary" : "text-text-secondary"}`} />
              <p className="font-semibold text-text-primary">{m.label}</p>
              <p className="text-xs text-text-muted">{m.desc}</p>
              <div className="mt-2 flex items-center justify-between">
                <span className="text-xs text-text-muted">Min: {formatUSD(m.min)}</span>
                <span className="text-xs text-text-secondary">{m.time}</span>
              </div>
            </button>
          );
        })}
      </div>

      {/* Amount Input */}
      {selectedType && (
        <div className="glass-card gradient-border-card p-5 animate-scale-in">
          <h3 className="mb-3 text-xs font-semibold uppercase tracking-widest text-text-secondary">Enter Amount</h3>
          <div className="flex gap-3">
            <div className="flex-1">
              <input
                type="number"
                value={amount}
                onChange={(e) => setAmount(e.target.value)}
                min={METHODS.find((m) => m.type === selectedType)?.min || 0}
                max={balance}
                placeholder="Amount in USD"
                className="futuristic-input w-full px-4 py-3 text-lg"
                style={{ fontFamily: "var(--font-mono)" }}
              />
            </div>
            <button
              onClick={() => setAmount(String(balance))}
              className="btn-ghost rounded-lg px-4 text-sm"
            >
              Max
            </button>
          </div>
          <button
            onClick={handleRedeem}
            disabled={loading || !amount || parseFloat(amount) <= 0}
            className="btn-primary mt-4 flex w-full items-center justify-center gap-2 py-3 text-sm font-bold disabled:opacity-50"
          >
            {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <ArrowRight className="h-4 w-4" />}
            Withdraw {amount ? formatUSD(parseFloat(amount)) : ""}
          </button>
          {msg && (
            <p className={`mt-2 text-sm ${msg.type === "ok" ? "text-success" : "text-danger"}`}>
              {msg.text}
            </p>
          )}
        </div>
      )}

      {/* History */}
      <div className="glass-card gradient-border-card p-5">
        <h2 className="mb-4 text-xs font-semibold uppercase tracking-widest text-text-secondary">Withdrawal History</h2>
        {history.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-8 text-text-muted">
            <Gift className="mb-3 h-8 w-8 opacity-40" />
            <p className="text-sm">No withdrawals yet.</p>
          </div>
        ) : (
          <div className="space-y-2">
            {history.map((r) => {
              const StatusIcon = STATUS_ICONS[r.status] || Clock;
              return (
                <div
                  key={r.id}
                  className="flex items-center justify-between rounded-xl border border-border-subtle bg-surface-raised/50 p-3 transition-colors hover:border-primary/20"
                >
                  <div className="flex items-center gap-3">
                    <StatusIcon
                      className={`h-5 w-5 ${
                        r.status === "completed" ? "text-success" :
                        r.status === "processing" ? "text-primary animate-spin" :
                        r.status === "pending" ? "text-warning" :
                        "text-danger"
                      }`}
                    />
                    <div>
                      <p className="text-sm font-medium text-text-primary">
                        {r.redemption_type.replace("_", " ")} — {formatUSD(r.amount_usd)}
                      </p>
                      <p className="text-xs text-text-muted">
                        {new Date(r.created_at).toLocaleDateString()}
                      </p>
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    <Badge label={r.status} variant={STATUS_VARIANTS[r.status] || "gray"} />
                    {r.status === "pending" && (
                      <button
                        onClick={() => handleCancel(r.id)}
                        className="text-xs text-danger hover:underline"
                      >
                        Cancel
                      </button>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
