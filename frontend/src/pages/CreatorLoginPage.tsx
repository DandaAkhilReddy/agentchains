import { useState } from "react";
import { LogIn, UserPlus, Loader2, AlertCircle } from "lucide-react";

interface Props {
  onLogin: (email: string, password: string) => Promise<void>;
  onRegister: (data: { email: string; password: string; display_name: string; phone?: string; country?: string }) => Promise<void>;
  loading: boolean;
  error: string | null;
}

export default function CreatorLoginPage({ onLogin, onRegister, loading, error }: Props) {
  const [mode, setMode] = useState<"login" | "register">("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [phone, setPhone] = useState("");
  const [country, setCountry] = useState("IN");

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (mode === "login") {
      await onLogin(email, password);
    } else {
      await onRegister({ email, password, display_name: displayName, phone: phone || undefined, country: country || undefined });
    }
  };

  return (
    <div className="flex min-h-[70vh] items-center justify-center">
      <div className="w-full max-w-md rounded-xl border border-border-subtle bg-surface-raised p-8 shadow-2xl">
        <div className="mb-6 text-center">
          <h1 className="text-2xl font-bold text-text-primary">
            {mode === "login" ? "Creator Login" : "Create Account"}
          </h1>
          <p className="mt-1 text-sm text-text-muted">
            {mode === "login"
              ? "Sign in to manage your agents and earnings"
              : "Join AgentChains and start earning ARD tokens"}
          </p>
        </div>

        {error && (
          <div className="mb-4 flex items-center gap-2 rounded-lg bg-red-500/10 border border-red-500/20 px-4 py-3 text-sm text-red-400">
            <AlertCircle className="h-4 w-4 shrink-0" />
            {error}
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-4">
          {mode === "register" && (
            <div>
              <label className="mb-1 block text-xs font-medium text-text-secondary">Display Name</label>
              <input
                type="text"
                value={displayName}
                onChange={(e) => setDisplayName(e.target.value)}
                required
                className="w-full rounded-lg border border-border-subtle bg-surface-raised px-3 py-2.5 text-sm text-text-primary outline-none focus:border-primary transition-colors"
                placeholder="Your Name"
              />
            </div>
          )}

          <div>
            <label className="mb-1 block text-xs font-medium text-text-secondary">Email</label>
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
              className="w-full rounded-lg border border-border-subtle bg-surface-raised px-3 py-2.5 text-sm text-text-primary outline-none focus:border-primary transition-colors"
              placeholder="you@example.com"
            />
          </div>

          <div>
            <label className="mb-1 block text-xs font-medium text-text-secondary">Password</label>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              minLength={8}
              className="w-full rounded-lg border border-border-subtle bg-surface-raised px-3 py-2.5 text-sm text-text-primary outline-none focus:border-primary transition-colors"
              placeholder="Min. 8 characters"
            />
          </div>

          {mode === "register" && (
            <>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="mb-1 block text-xs font-medium text-text-secondary">Phone (optional)</label>
                  <input
                    type="tel"
                    value={phone}
                    onChange={(e) => setPhone(e.target.value)}
                    className="w-full rounded-lg border border-border-subtle bg-surface-raised px-3 py-2.5 text-sm text-text-primary outline-none focus:border-primary transition-colors"
                    placeholder="+91..."
                  />
                </div>
                <div>
                  <label className="mb-1 block text-xs font-medium text-text-secondary">Country</label>
                  <select
                    value={country}
                    onChange={(e) => setCountry(e.target.value)}
                    className="w-full rounded-lg border border-border-subtle bg-surface-raised px-3 py-2.5 text-sm text-text-primary outline-none focus:border-primary transition-colors"
                  >
                    <option value="IN">India</option>
                    <option value="US">United States</option>
                    <option value="GB">United Kingdom</option>
                    <option value="DE">Germany</option>
                    <option value="JP">Japan</option>
                  </select>
                </div>
              </div>
            </>
          )}

          <button
            type="submit"
            disabled={loading}
            className="flex w-full items-center justify-center gap-2 rounded-lg bg-primary px-4 py-2.5 text-sm font-semibold text-black transition-colors hover:bg-primary-hover disabled:opacity-50"
          >
            {loading ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : mode === "login" ? (
              <LogIn className="h-4 w-4" />
            ) : (
              <UserPlus className="h-4 w-4" />
            )}
            {mode === "login" ? "Sign In" : "Create Account"}
          </button>
        </form>

        <div className="mt-6 text-center">
          <button
            onClick={() => setMode(mode === "login" ? "register" : "login")}
            className="text-sm text-primary hover:underline"
          >
            {mode === "login" ? "Don't have an account? Sign up" : "Already have an account? Sign in"}
          </button>
        </div>

        <div className="mt-4 rounded-lg bg-primary/5 border border-primary/20 px-4 py-3">
          <p className="text-xs text-text-muted">
            <span className="font-semibold text-primary">100 ARD signup bonus!</span>{" "}
            Create your agents via OpenClaw, link them here, and earn ARD tokens every time they sell data.
            Redeem for API credits, gift cards, or bank withdrawal.
          </p>
        </div>
      </div>
    </div>
  );
}
