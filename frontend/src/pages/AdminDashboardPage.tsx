import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  AlertTriangle,
  DollarSign,
  Shield,
  Users,
  Activity,
  Clock,
} from "lucide-react";

import PageHeader from "../components/PageHeader";
import {
  fetchAdminOverviewV2,
  fetchAdminFinanceV2,
  fetchAdminUsageV2,
  fetchAdminPendingPayoutsV2,
  fetchAdminSecurityEventsV2,
} from "../lib/api";
import { formatUSD } from "../lib/format";

interface Props {
  token: string;
  creatorName: string;
}

export default function AdminDashboardPage({ token, creatorName }: Props) {
  const overview = useQuery({
    queryKey: ["admin-overview-v2", token],
    queryFn: () => fetchAdminOverviewV2(token),
  });
  const finance = useQuery({
    queryKey: ["admin-finance-v2", token],
    queryFn: () => fetchAdminFinanceV2(token),
  });
  const usage = useQuery({
    queryKey: ["admin-usage-v2", token],
    queryFn: () => fetchAdminUsageV2(token),
  });
  const payouts = useQuery({
    queryKey: ["admin-payouts-pending-v2", token],
    queryFn: () => fetchAdminPendingPayoutsV2(token, 20),
  });
  const security = useQuery({
    queryKey: ["admin-security-events-v2", token],
    queryFn: () => fetchAdminSecurityEventsV2(token, { page: 1, page_size: 15 }),
  });

  const loading = overview.isLoading || finance.isLoading || usage.isLoading;

  const totalAlerts = useMemo(
    () => security.data?.events.filter((event) => event.severity !== "info").length ?? 0,
    [security.data],
  );

  if (overview.error) {
    return (
      <div className="rounded-2xl border border-[rgba(248,113,113,0.3)] bg-[#141928] p-6">
        <div className="flex items-center gap-2 text-[#f87171]">
          <AlertTriangle className="h-4 w-4" />
          <span className="text-sm font-semibold">Admin access required or token invalid.</span>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="Admin Dashboard"
        subtitle={`Platform operations and security controls - ${creatorName}`}
        icon={Shield}
      />

      {loading || !overview.data || !finance.data || !usage.data ? (
        <div className="text-sm text-[#94a3b8]">Loading admin dashboard...</div>
      ) : (
        <>
          <div className="grid gap-4 md:grid-cols-4">
            <div className="rounded-xl bg-[#141928] p-4">
              <div className="text-xs text-[#64748b]">Platform Volume</div>
              <div className="mt-1 text-2xl font-semibold text-[#34d399]">
                {formatUSD(finance.data.platform_volume_usd)}
              </div>
            </div>
            <div className="rounded-xl bg-[#141928] p-4">
              <div className="text-xs text-[#64748b]">Completed Transactions</div>
              <div className="mt-1 text-2xl font-semibold text-[#60a5fa]">
                {overview.data.completed_transactions}
              </div>
            </div>
            <div className="rounded-xl bg-[#141928] p-4">
              <div className="text-xs text-[#64748b]">Pending Payouts</div>
              <div className="mt-1 text-2xl font-semibold text-[#fbbf24]">
                {payouts.data?.count ?? 0}
              </div>
              <div className="text-xs text-[#94a3b8]">
                {formatUSD(payouts.data?.total_pending_usd ?? 0)}
              </div>
            </div>
            <div className="rounded-xl bg-[#141928] p-4">
              <div className="text-xs text-[#64748b]">Security Alerts</div>
              <div className="mt-1 text-2xl font-semibold text-[#f87171]">{totalAlerts}</div>
            </div>
          </div>

          <div className="grid gap-4 md:grid-cols-2">
            <div className="rounded-xl bg-[#141928] p-4">
              <div className="mb-3 flex items-center gap-2 text-sm text-[#94a3b8]">
                <Users className="h-4 w-4 text-[#60a5fa]" />
                Agent Stats
              </div>
              <div className="space-y-2 text-sm text-[#e2e8f0]">
                <div>Total agents: {overview.data.total_agents}</div>
                <div>Active agents: {overview.data.active_agents}</div>
                <div>Total listings: {overview.data.total_listings}</div>
                <div>Active listings: {overview.data.active_listings}</div>
              </div>
            </div>

            <div className="rounded-xl bg-[#141928] p-4">
              <div className="mb-3 flex items-center gap-2 text-sm text-[#94a3b8]">
                <Activity className="h-4 w-4 text-[#a78bfa]" />
                Trust + Savings
              </div>
              <div className="space-y-2 text-sm text-[#e2e8f0]">
                <div>Trust-weighted revenue: {formatUSD(overview.data.trust_weighted_revenue_usd)}</div>
                <div>Info used count: {usage.data.info_used_count}</div>
                <div>Data served: {usage.data.data_served_bytes.toLocaleString()} bytes</div>
                <div>Money saved for buyers: {formatUSD(usage.data.money_saved_for_others_usd)}</div>
              </div>
            </div>
          </div>

          <div className="rounded-xl bg-[#141928] p-4">
            <div className="mb-3 flex items-center gap-2 text-sm text-[#94a3b8]">
              <DollarSign className="h-4 w-4 text-[#34d399]" />
              Top sellers by revenue
            </div>
            <div className="space-y-2">
              {finance.data.top_sellers_by_revenue.slice(0, 8).map((row) => (
                <div key={row.agent_id} className="flex items-center justify-between rounded-lg bg-[#0a0e1a] px-3 py-2 text-sm">
                  <span className="text-[#e2e8f0]">{row.agent_name}</span>
                  <span className="text-[#34d399]">{formatUSD(row.money_received_usd)}</span>
                </div>
              ))}
            </div>
          </div>

          <div className="rounded-xl bg-[#141928] p-4">
            <div className="mb-3 flex items-center gap-2 text-sm text-[#94a3b8]">
              <Clock className="h-4 w-4 text-[#fbbf24]" />
              Recent security events
            </div>
            <div className="space-y-2">
              {(security.data?.events ?? []).map((event) => (
                <div key={event.id} className="rounded-lg bg-[#0a0e1a] px-3 py-2 text-xs">
                  <div className="flex items-center justify-between">
                    <span className="font-semibold text-[#e2e8f0]">{event.event_type}</span>
                    <span className="text-[#94a3b8]">{event.severity}</span>
                  </div>
                  <div className="mt-1 text-[#64748b]">{new Date(event.created_at).toLocaleString()}</div>
                </div>
              ))}
            </div>
          </div>
        </>
      )}
    </div>
  );
}
