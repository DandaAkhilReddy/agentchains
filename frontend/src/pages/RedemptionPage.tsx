import { useEffect, useState } from "react";
import { CreditCard, Gift, Building2, Smartphone, Loader2, CheckCircle, XCircle, Clock } from "lucide-react";
import { createRedemption, fetchRedemptions, cancelRedemption, fetchCreatorWallet } from "../lib/api";

interface Props {
  token: string;
}

interface Redemption {
  id: string;
  redemption_type: string;
  amount_ard: number;
  amount_fiat: number | null;
  currency: string;
  status: string;
  created_at: string;
  completed_at: string | null;
}

const METHODS = [
  { type: "api_credits", label: "API Credits", icon: CreditCard, min: 100, time: "Instant", desc: "Convert ARD to API call credits" },
  { type: "gift_card", label: "Gift Card", icon: Gift, min: 1000, time: "24 hours", desc: "Amazon gift card delivery" },
  { type: "upi", label: "UPI Transfer", icon: Smartphone, min: 5000, time: "Minutes", desc: "Direct to your UPI ID (India)" },
  { type: "bank_withdrawal", label: "Bank Transfer", icon: Building2, min: 10000, time: "3-7 days", desc: "Wire to your bank account" },
];

const STATUS_ICONS: Record<string, any> = {
  pending: Clock,
  processing: Loader2,
  completed: CheckCircle,
  failed: XCircle,
  rejected: XCircle,
};

const STATUS_COLORS: Record<string, string> = {
  pending: "text-yellow-400",
  processing: "text-blue-400",
  completed: "text-[var(--accent)]",
  failed: "text-red-400",
  rejected: "text-red-400",
};

export default function RedemptionPage({ token }: Props) {
  const [balance, setBalance] = useState(0);
  const [balanceUsd, setBalanceUsd] = useState(0);
  const [selectedType, setSelectedType] = useState("");
  const [amount, setAmount] = useState("");
  const [loading, setLoading] = useState(false);
  const [history, setHistory] = useState<Redemption[]>([]);
  const [msg, setMsg] = useState<{ type: "ok" | "err"; text: string } | null>(null);

  const loadData = async () => {
    try {
      const wallet = await fetchCreatorWallet(token);
      setBalance(wallet.balance);
      setBalanceUsd(wallet.balance_usd);
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
        amount_ard: parseFloat(amount),
      });
      setMsg({ type: "ok", text: "Redemption request created successfully!" });
      setAmount("");
      setSelectedType("");
      loadData();
    } catch (e: any) {
      setMsg({ type: "err", text: e.message || "Redemption failed" });
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

  const fmtARD = (n: number) => n >= 1000 ? `${(n / 1000).toFixed(1)}K` : n.toFixed(0);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-[var(--text-primary)]">Redeem ARD Tokens</h1>
        <p className="text-sm text-[var(--text-muted)]">
          Convert your earnings to real value — API credits, gift cards, or cash
        </p>
      </div>

      {/* Balance Banner */}
      <div className="rounded-xl border border-[var(--accent)]/30 bg-[var(--accent)]/5 p-5">
        <div className="flex items-center justify-between">
          <div>
            <p className="text-sm text-[var(--text-muted)]">Available Balance</p>
            <p className="text-3xl font-bold text-[var(--accent)]">{fmtARD(balance)} ARD</p>
            <p className="text-sm text-[var(--text-secondary)]">${balanceUsd.toFixed(2)} USD</p>
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
              className={`rounded-xl border p-4 text-left transition-all ${
                active
                  ? "border-[var(--accent)] bg-[var(--accent)]/10"
                  : eligible
                  ? "border-[var(--border-default)] bg-[var(--bg-card)] hover:border-[var(--accent)]/50"
                  : "border-[var(--border-default)] bg-[var(--bg-card)] opacity-40 cursor-not-allowed"
              }`}
            >
              <m.icon className={`mb-2 h-6 w-6 ${active ? "text-[var(--accent)]" : "text-[var(--text-secondary)]"}`} />
              <p className="font-semibold text-[var(--text-primary)]">{m.label}</p>
              <p className="text-xs text-[var(--text-muted)]">{m.desc}</p>
              <div className="mt-2 flex items-center justify-between">
                <span className="text-xs text-[var(--text-muted)]">Min: {fmtARD(m.min)} ARD</span>
                <span className="text-xs text-[var(--text-secondary)]">{m.time}</span>
              </div>
            </button>
          );
        })}
      </div>

      {/* Amount Input */}
      {selectedType && (
        <div className="rounded-xl border border-[var(--border-default)] bg-[var(--bg-card)] p-5">
          <h3 className="mb-3 font-semibold text-[var(--text-primary)]">Enter Amount</h3>
          <div className="flex gap-3">
            <div className="flex-1">
              <input
                type="number"
                value={amount}
                onChange={(e) => setAmount(e.target.value)}
                min={METHODS.find(m => m.type === selectedType)?.min || 0}
                max={balance}
                placeholder="Amount in ARD"
                className="w-full rounded-lg border border-[var(--border-default)] bg-[var(--bg-card)] px-4 py-3 text-lg text-[var(--text-primary)] outline-none focus:border-[var(--accent)] transition-colors"
              />
              {amount && (
                <p className="mt-1 text-sm text-[var(--text-muted)]">
                  = ${(parseFloat(amount) * 0.001).toFixed(2)} USD
                </p>
              )}
            </div>
            <button
              onClick={() => setAmount(String(balance))}
              className="rounded-lg border border-[var(--border-default)] px-4 text-sm text-[var(--text-secondary)] hover:text-[var(--accent)]"
            >
              Max
            </button>
          </div>
          <button
            onClick={handleRedeem}
            disabled={loading || !amount || parseFloat(amount) <= 0}
            className="mt-4 flex w-full items-center justify-center gap-2 rounded-lg bg-[var(--accent)] py-3 text-sm font-bold text-black hover:bg-[var(--accent-hover)] disabled:opacity-50 transition-colors"
          >
            {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
            Redeem {amount ? `${fmtARD(parseFloat(amount))} ARD` : ""}
          </button>
          {msg && (
            <p className={`mt-2 text-sm ${msg.type === "ok" ? "text-[var(--accent)]" : "text-red-400"}`}>
              {msg.text}
            </p>
          )}
        </div>
      )}

      {/* History */}
      <div className="rounded-xl border border-[var(--border-default)] bg-[var(--bg-card)] p-5">
        <h2 className="mb-4 text-lg font-semibold text-[var(--text-primary)]">Redemption History</h2>
        {history.length === 0 ? (
          <p className="text-sm text-[var(--text-muted)]">No redemptions yet.</p>
        ) : (
          <div className="space-y-2">
            {history.map((r) => {
              const StatusIcon = STATUS_ICONS[r.status] || Clock;
              return (
                <div key={r.id} className="flex items-center justify-between rounded-lg border border-[var(--border-default)] p-3">
                  <div className="flex items-center gap-3">
                    <StatusIcon className={`h-5 w-5 ${STATUS_COLORS[r.status] || ""} ${r.status === "processing" ? "animate-spin" : ""}`} />
                    <div>
                      <p className="text-sm font-medium text-[var(--text-primary)]">
                        {r.redemption_type.replace("_", " ")} — {fmtARD(r.amount_ard)} ARD
                      </p>
                      <p className="text-xs text-[var(--text-muted)]">
                        {new Date(r.created_at).toLocaleDateString()} — {r.status}
                      </p>
                    </div>
                  </div>
                  {r.status === "pending" && (
                    <button
                      onClick={() => handleCancel(r.id)}
                      className="text-xs text-red-400 hover:underline"
                    >
                      Cancel
                    </button>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
