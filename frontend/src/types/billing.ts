/** Billing TypeScript interfaces matching backend Pydantic schemas. */

export interface PlanResponse {
  id: string;
  name: string;
  description: string;
  tier: string;
  price_monthly: number;
  price_yearly: number;
  api_calls_limit: number;
  storage_gb_limit: number;
  agents_limit: number;
  features: string[];
}

export interface PlanScoredResponse {
  plan: PlanResponse;
  score: number;
  label: "good_fit" | "overpaying" | "at_risk" | "exceeds_limits";
}

export interface SubscriptionResponse {
  id: string;
  plan: PlanResponse;
  status: string;
  current_period_start: string | null;
  current_period_end: string | null;
  cancel_at_period_end: boolean;
}

export interface CreateSubscriptionRequest {
  plan_id: string;
  billing_cycle: "monthly" | "yearly";
}

export interface ChangePlanRequest {
  new_plan_id: string;
}

export interface CancelSubscriptionRequest {
  immediate: boolean;
}

export interface UsageMeterResponse {
  metric_name: string;
  current: number;
  limit: number;
  percent_used: number;
}

export interface UsageForecastResponse {
  metric_name: string;
  current: number;
  projected_end_of_period: number;
  limit: number;
  percent_projected: number;
  exceeds_limit: boolean;
}

export interface InvoiceResponse {
  id: string;
  amount_usd: number;
  tax_usd: number;
  total_usd: number;
  status: string;
  issued_at: string | null;
  due_at: string | null;
  paid_at: string | null;
  pdf_url: string;
}

export interface InvoiceListResponse {
  items: InvoiceResponse[];
  total: number;
  page: number;
  page_size: number;
}

export interface RecommendationResponse {
  recommended_plan: PlanResponse;
  reasoning: string;
  savings_estimate_monthly: number;
  all_plans_scored: PlanScoredResponse[];
}

export interface CheckoutResponse {
  subscription_id: string | null;
  checkout_url: string | null;
  checkout_session_id?: string;
}

export interface CancelResponse {
  id: string;
  status: string;
  cancel_at_period_end: boolean;
}

export interface InvoicePdfResponse {
  invoice_id: string;
  pdf_url: string;
}
