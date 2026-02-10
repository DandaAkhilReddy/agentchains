import { useTranslation } from "react-i18next";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Users, FileText, ScanLine, DollarSign, Star, Trash2 } from "lucide-react";
import api from "../lib/api";
import { formatUSD } from "../lib/format";

interface AdminStats {
  user_count: number;
  new_users_7d: number;
  new_users_30d: number;
  total_loans: number;
  loans_by_type: Record<string, number>;
  total_scans: number;
  scans_today: number;
  scan_success_rate: number;
  total_reviews: number;
}

interface UsageSummary {
  total_cost_30d: number;
  total_calls_30d: number;
  by_service: Record<string, { call_count: number; total_cost: number; tokens_input: number; tokens_output: number }>;
  daily_costs: { date: string; service: string; call_count: number; total_cost: number }[];
}

interface AdminUser {
  id: string;
  email: string | null;
  display_name: string | null;
  created_at: string;
  loan_count: number;
}

interface Review {
  id: string;
  user_id: string;
  user_display_name: string | null;
  review_type: string;
  rating: number | null;
  title: string;
  content: string;
  status: string;
  admin_response: string | null;
  is_public: boolean;
  created_at: string;
}

export function AdminDashboardPage() {
  const { t } = useTranslation();
  const queryClient = useQueryClient();

  const { data: stats } = useQuery<AdminStats>({
    queryKey: ["admin-stats"],
    queryFn: () => api.get("/api/admin/stats").then((r) => r.data),
  });

  const { data: usage } = useQuery<UsageSummary>({
    queryKey: ["admin-usage"],
    queryFn: () => api.get("/api/admin/usage").then((r) => r.data),
  });

  const { data: users } = useQuery<AdminUser[]>({
    queryKey: ["admin-users"],
    queryFn: () => api.get("/api/admin/users").then((r) => r.data),
  });

  const { data: reviews } = useQuery<Review[]>({
    queryKey: ["admin-reviews"],
    queryFn: () => api.get("/api/admin/reviews").then((r) => r.data),
  });

  const updateReview = useMutation({
    mutationFn: ({ id, ...data }: { id: string; status?: string; admin_response?: string; is_public?: boolean }) =>
      api.put(`/api/admin/reviews/${id}`, data),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["admin-reviews"] }),
  });

  const deleteReview = useMutation({
    mutationFn: (id: string) => api.delete(`/api/admin/reviews/${id}`),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["admin-reviews"] }),
  });

  const metricCards = [
    { label: t("admin.totalUsers"), value: stats?.user_count ?? 0, sub: `+${stats?.new_users_7d ?? 0} ${t("admin.thisWeek")}`, icon: Users, color: "bg-blue-50 text-blue-600" },
    { label: t("admin.totalLoans"), value: stats?.total_loans ?? 0, sub: Object.entries(stats?.loans_by_type ?? {}).map(([k, v]) => `${k}: ${v}`).join(", "), icon: FileText, color: "bg-green-50 text-green-600" },
    { label: t("admin.docsScanned"), value: stats?.total_scans ?? 0, sub: `${stats?.scan_success_rate ?? 0}% ${t("admin.successRate")}`, icon: ScanLine, color: "bg-purple-50 text-purple-600" },
    { label: t("admin.estCost30d"), value: formatUSD(usage?.total_cost_30d ?? 0, 4), sub: `${usage?.total_calls_30d ?? 0} ${t("admin.apiCalls")}`, icon: DollarSign, color: "bg-orange-50 text-orange-600" },
  ];

  // Group daily costs by date
  const dailyAgg: Record<string, { date: string; cost: number; calls: number }> = {};
  (usage?.daily_costs ?? []).forEach((d) => {
    if (!dailyAgg[d.date]) dailyAgg[d.date] = { date: d.date, cost: 0, calls: 0 };
    dailyAgg[d.date].cost += d.total_cost;
    dailyAgg[d.date].calls += d.call_count;
  });
  const dailyRows = Object.values(dailyAgg).sort((a, b) => b.date.localeCompare(a.date)).slice(0, 14);

  const feedbackReviews = (reviews ?? []).filter((r) => r.review_type !== "feature_request");
  const featureRequests = (reviews ?? []).filter((r) => r.review_type === "feature_request");

  return (
    <div className="max-w-6xl mx-auto space-y-6">
      <h1 className="text-2xl font-bold">{t("admin.title")}</h1>

      {/* Metric Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {metricCards.map((card) => (
          <div key={card.label} className="bg-white rounded-xl border p-4 shadow-sm">
            <div className="flex items-center gap-3 mb-2">
              <div className={`p-2 rounded-lg ${card.color}`}>
                <card.icon className="w-5 h-5" />
              </div>
              <span className="text-sm text-gray-500">{card.label}</span>
            </div>
            <div className="text-2xl font-bold">{card.value}</div>
            <div className="text-xs text-gray-400 mt-1 truncate">{card.sub}</div>
          </div>
        ))}
      </div>

      {/* Usage by Service */}
      {usage?.by_service && Object.keys(usage.by_service).length > 0 && (
        <div className="bg-white rounded-xl border p-4 shadow-sm">
          <h2 className="text-lg font-semibold mb-3">{t("admin.usageByService")}</h2>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b text-left text-gray-500">
                  <th className="py-2 pr-4">{t("admin.service")}</th>
                  <th className="py-2 pr-4">{t("admin.calls")}</th>
                  <th className="py-2 pr-4">{t("admin.tokensIn")}</th>
                  <th className="py-2 pr-4">{t("admin.tokensOut")}</th>
                  <th className="py-2">{t("admin.cost")}</th>
                </tr>
              </thead>
              <tbody>
                {Object.entries(usage.by_service).map(([svc, data]) => (
                  <tr key={svc} className="border-b last:border-0">
                    <td className="py-2 pr-4 font-medium">{svc}</td>
                    <td className="py-2 pr-4">{data.call_count}</td>
                    <td className="py-2 pr-4">{data.tokens_input.toLocaleString()}</td>
                    <td className="py-2 pr-4">{data.tokens_output.toLocaleString()}</td>
                    <td className="py-2">{formatUSD(data.total_cost, 4)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Daily Costs */}
      {dailyRows.length > 0 && (
        <div className="bg-white rounded-xl border p-4 shadow-sm">
          <h2 className="text-lg font-semibold mb-3">{t("admin.dailyCosts")}</h2>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b text-left text-gray-500">
                  <th className="py-2 pr-4">{t("admin.date")}</th>
                  <th className="py-2 pr-4">{t("admin.calls")}</th>
                  <th className="py-2">{t("admin.cost")}</th>
                </tr>
              </thead>
              <tbody>
                {dailyRows.map((row) => (
                  <tr key={row.date} className="border-b last:border-0">
                    <td className="py-2 pr-4">{row.date}</td>
                    <td className="py-2 pr-4">{row.calls}</td>
                    <td className="py-2">{formatUSD(row.cost, 4)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Users */}
      <div className="bg-white rounded-xl border p-4 shadow-sm">
        <h2 className="text-lg font-semibold mb-3">{t("admin.users")}</h2>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b text-left text-gray-500">
                <th className="py-2 pr-4">{t("admin.name")}</th>
                <th className="py-2 pr-4">{t("admin.email")}</th>
                <th className="py-2 pr-4">{t("admin.joined")}</th>
                <th className="py-2">{t("admin.loans")}</th>
              </tr>
            </thead>
            <tbody>
              {(users ?? []).map((u) => (
                <tr key={u.id} className="border-b last:border-0">
                  <td className="py-2 pr-4">{u.display_name || "-"}</td>
                  <td className="py-2 pr-4">{u.email || "-"}</td>
                  <td className="py-2 pr-4">{new Date(u.created_at).toLocaleDateString()}</td>
                  <td className="py-2">{u.loan_count}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Reviews / Feedback */}
      <div className="bg-white rounded-xl border p-4 shadow-sm">
        <h2 className="text-lg font-semibold mb-3">{t("admin.reviewsTitle")}</h2>
        {feedbackReviews.length === 0 ? (
          <p className="text-sm text-gray-400">{t("admin.noReviews")}</p>
        ) : (
          <div className="space-y-3">
            {feedbackReviews.map((r) => (
              <div key={r.id} className="border rounded-lg p-3">
                <div className="flex items-center justify-between mb-1">
                  <div className="flex items-center gap-2">
                    <span className="font-medium text-sm">{r.user_display_name || "User"}</span>
                    {r.rating && (
                      <span className="flex items-center gap-0.5 text-yellow-500">
                        {Array.from({ length: r.rating }).map((_, i) => (
                          <Star key={i} className="w-3.5 h-3.5 fill-current" />
                        ))}
                      </span>
                    )}
                    <span className={`text-xs px-2 py-0.5 rounded-full ${
                      r.status === "approved" ? "bg-green-100 text-green-700" :
                      r.status === "rejected" ? "bg-red-100 text-red-700" :
                      "bg-gray-100 text-gray-600"
                    }`}>{r.status}</span>
                  </div>
                  <div className="flex gap-1">
                    {r.review_type === "testimonial" && r.status === "pending" && (
                      <>
                        <button onClick={() => updateReview.mutate({ id: r.id, status: "approved", is_public: true })}
                          className="text-xs px-2 py-1 bg-green-50 text-green-700 rounded hover:bg-green-100">
                          {t("admin.approve")}
                        </button>
                        <button onClick={() => updateReview.mutate({ id: r.id, status: "rejected" })}
                          className="text-xs px-2 py-1 bg-red-50 text-red-700 rounded hover:bg-red-100">
                          {t("admin.reject")}
                        </button>
                      </>
                    )}
                    <button onClick={() => deleteReview.mutate(r.id)}
                      className="text-xs p-1 text-gray-400 hover:text-red-500">
                      <Trash2 className="w-3.5 h-3.5" />
                    </button>
                  </div>
                </div>
                <p className="text-sm font-medium">{r.title}</p>
                <p className="text-sm text-gray-600">{r.content}</p>
                <p className="text-xs text-gray-400 mt-1">{new Date(r.created_at).toLocaleDateString()}</p>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Feature Requests */}
      <div className="bg-white rounded-xl border p-4 shadow-sm">
        <h2 className="text-lg font-semibold mb-3">{t("admin.featureRequests")}</h2>
        {featureRequests.length === 0 ? (
          <p className="text-sm text-gray-400">{t("admin.noFeatureRequests")}</p>
        ) : (
          <div className="space-y-3">
            {featureRequests.map((r) => (
              <div key={r.id} className="border rounded-lg p-3">
                <div className="flex items-center justify-between mb-1">
                  <div className="flex items-center gap-2">
                    <span className="font-medium text-sm">{r.title}</span>
                    <select
                      value={r.status}
                      onChange={(e) => updateReview.mutate({ id: r.id, status: e.target.value })}
                      className="text-xs border rounded px-1.5 py-0.5"
                    >
                      <option value="new">{t("admin.statusNew")}</option>
                      <option value="acknowledged">{t("admin.statusAcknowledged")}</option>
                      <option value="planned">{t("admin.statusPlanned")}</option>
                      <option value="done">{t("admin.statusDone")}</option>
                    </select>
                  </div>
                  <button onClick={() => deleteReview.mutate(r.id)}
                    className="text-xs p-1 text-gray-400 hover:text-red-500">
                    <Trash2 className="w-3.5 h-3.5" />
                  </button>
                </div>
                <p className="text-sm text-gray-600">{r.content}</p>
                <p className="text-xs text-gray-400 mt-1">{r.user_display_name || "User"} &middot; {new Date(r.created_at).toLocaleDateString()}</p>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
