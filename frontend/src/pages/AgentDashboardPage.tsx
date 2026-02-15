import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  Bot,
  DollarSign,
  KeyRound,
  LogOut,
  Database,
  Activity,
} from "lucide-react";

import PageHeader from "../components/PageHeader";
import { useAuth } from "../hooks/useAuth";
import { fetchDashboardAgentMeV2 } from "../lib/api";
import { formatUSD } from "../lib/format";

export default function AgentDashboardPage() {
  const { token, login, logout } = useAuth();
  const [inputToken, setInputToken] = useState("");

  const { data, isLoading } = useQuery({
    queryKey: ["agent-dashboard-v2", token],
    queryFn: () => fetchDashboardAgentMeV2(token!),
    enabled: !!token,
  });

  if (!token) {
    return (
      <div className="mx-auto mt-16 max-w-xl rounded-2xl border border-[rgba(255,255,255,0.08)] bg-[#141928] p-8">
        <div className="mb-4 flex h-12 w-12 items-center justify-center rounded-xl bg-[rgba(96,165,250,0.1)]">
          <KeyRound className="h-6 w-6 text-[#60a5fa]" />
        </div>
        <h2 className="text-xl font-semibold text-[#e2e8f0]">Agent Login</h2>
        <p className="mt-2 text-sm text-[#94a3b8]">
          Paste your agent JWT token to open your dashboard.
        </p>
        <input
          value={inputToken}
          onChange={(e) => setInputToken(e.target.value)}
          placeholder="Bearer token"
          className="mt-4 w-full rounded-xl border border-[rgba(255,255,255,0.08)] bg-[#0a0e1a] px-4 py-3 text-sm text-[#e2e8f0] outline-none"
        />
        <button
          onClick={() => login(inputToken.trim())}
          className="mt-4 rounded-xl bg-[#2563eb] px-4 py-2 text-sm font-semibold text-white"
        >
          Sign In
        </button>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="Agent Dashboard"
        subtitle="Revenue, usage, trust, and buyer savings"
        icon={Bot}
        actions={(
          <button
            onClick={logout}
            className="flex items-center gap-2 rounded-xl border border-[rgba(255,255,255,0.08)] px-3 py-2 text-sm text-[#f87171]"
          >
            <LogOut className="h-4 w-4" /> Logout
          </button>
        )}
      />

      {isLoading || !data ? (
        <div className="text-sm text-[#94a3b8]">Loading dashboard...</div>
      ) : (
        <>
          <div className="grid gap-4 md:grid-cols-4">
            <div className="rounded-xl bg-[#141928] p-4">
              <div className="text-xs text-[#64748b]">Money Received</div>
              <div className="mt-1 text-2xl font-semibold text-[#34d399]">
                {formatUSD(data.money_received_usd)}
              </div>
            </div>
            <div className="rounded-xl bg-[#141928] p-4">
              <div className="text-xs text-[#64748b]">Info Used</div>
              <div className="mt-1 text-2xl font-semibold text-[#60a5fa]">
                {data.info_used_count}
              </div>
            </div>
            <div className="rounded-xl bg-[#141928] p-4">
              <div className="text-xs text-[#64748b]">Other Agents Served</div>
              <div className="mt-1 text-2xl font-semibold text-[#a78bfa]">
                {data.other_agents_served_count}
              </div>
            </div>
            <div className="rounded-xl bg-[#141928] p-4">
              <div className="text-xs text-[#64748b]">Money Saved For Buyers</div>
              <div className="mt-1 text-2xl font-semibold text-[#fbbf24]">
                {formatUSD(data.savings.money_saved_for_others_usd)}
              </div>
            </div>
          </div>

          <div className="grid gap-4 md:grid-cols-3">
            <div className="rounded-xl bg-[#141928] p-4">
              <div className="mb-2 flex items-center gap-2 text-sm text-[#94a3b8]">
                <DollarSign className="h-4 w-4 text-[#34d399]" />
                Money Spent
              </div>
              <div className="text-xl font-semibold text-[#e2e8f0]">{formatUSD(data.money_spent_usd)}</div>
            </div>
            <div className="rounded-xl bg-[#141928] p-4">
              <div className="mb-2 flex items-center gap-2 text-sm text-[#94a3b8]">
                <Database className="h-4 w-4 text-[#60a5fa]" />
                Data Served
              </div>
              <div className="text-xl font-semibold text-[#e2e8f0]">{data.data_served_bytes.toLocaleString()} bytes</div>
            </div>
            <div className="rounded-xl bg-[#141928] p-4">
              <div className="mb-2 flex items-center gap-2 text-sm text-[#94a3b8]">
                <Activity className="h-4 w-4 text-[#a78bfa]" />
                Trust
              </div>
              <div className="text-xl font-semibold text-[#e2e8f0]">
                {data.trust_status} ({data.trust_tier}) - {data.trust_score}
              </div>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
