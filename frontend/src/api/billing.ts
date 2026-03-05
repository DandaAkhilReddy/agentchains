/** Billing API client — typed fetch functions for subscription endpoints. */

import type {
  CancelResponse,
  CheckoutResponse,
  InvoiceListResponse,
  InvoicePdfResponse,
  PlanResponse,
  RecommendationResponse,
  SubscriptionResponse,
  UsageForecastResponse,
  UsageMeterResponse,
} from "../types/billing";

const BASE_V2 = "/api/v2";

async function request<T>(
  path: string,
  opts: { method?: string; token?: string; body?: unknown } = {},
): Promise<T> {
  const { method = "GET", token, body } = opts;
  const url = `${BASE_V2}${path}`;
  const headers: Record<string, string> = {};
  if (token) headers["Authorization"] = `Bearer ${token}`;
  if (body !== undefined) headers["Content-Type"] = "application/json";

  const res = await fetch(url, {
    method,
    headers,
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });

  if (!res.ok) {
    const text = await res.text();
    throw new Error(`API ${res.status}: ${text}`);
  }
  return res.json();
}

// ── Plans ──

export function fetchPlans(tier?: string): Promise<PlanResponse[]> {
  const qs = tier ? `?tier=${encodeURIComponent(tier)}` : "";
  return request<PlanResponse[]>(`/billing/plans${qs}`);
}

export function fetchPlan(planId: string): Promise<PlanResponse> {
  return request<PlanResponse>(`/billing/plans/${planId}`);
}

export function fetchPlanRecommendation(token: string): Promise<RecommendationResponse> {
  return request<RecommendationResponse>("/billing/plans/recommend", { token });
}

// ── Subscriptions ──

export function fetchMySubscription(token: string): Promise<SubscriptionResponse | null> {
  return request<SubscriptionResponse | null>("/billing/subscriptions/me", { token });
}

export function createSubscription(
  token: string,
  planId: string,
  cycle: "monthly" | "yearly" = "monthly",
): Promise<CheckoutResponse> {
  return request<CheckoutResponse>("/billing/subscriptions", {
    method: "POST",
    token,
    body: { plan_id: planId, billing_cycle: cycle },
  });
}

export function cancelSubscription(
  token: string,
  immediate: boolean = false,
): Promise<CancelResponse> {
  return request<CancelResponse>("/billing/subscriptions/me/cancel", {
    method: "POST",
    token,
    body: { immediate },
  });
}

export function changePlan(
  token: string,
  newPlanId: string,
): Promise<CheckoutResponse> {
  return request<CheckoutResponse>("/billing/subscriptions/me/change-plan", {
    method: "POST",
    token,
    body: { new_plan_id: newPlanId },
  });
}

// ── Usage ──

export function fetchUsage(token: string): Promise<UsageMeterResponse[]> {
  return request<UsageMeterResponse[]>("/billing/usage/me", { token });
}

export function fetchUsageForecast(token: string): Promise<UsageForecastResponse[]> {
  return request<UsageForecastResponse[]>("/billing/usage/me/forecast", { token });
}

// ── Invoices ──

export function fetchInvoices(
  token: string,
  page: number = 1,
  pageSize: number = 20,
): Promise<InvoiceListResponse> {
  return request<InvoiceListResponse>(
    `/billing/invoices/me?page=${page}&page_size=${pageSize}`,
    { token },
  );
}

export function fetchInvoicePdf(
  token: string,
  invoiceId: string,
): Promise<InvoicePdfResponse> {
  return request<InvoicePdfResponse>(`/billing/invoices/${invoiceId}/pdf`, { token });
}
