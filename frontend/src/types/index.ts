export interface Loan {
  id: string;
  user_id: string;
  bank_name: string;
  loan_type: "home" | "personal" | "car" | "education" | "gold" | "credit_card";
  principal_amount: number;
  outstanding_principal: number;
  interest_rate: number;
  interest_rate_type: "floating" | "fixed" | "hybrid";
  tenure_months: number;
  remaining_tenure_months: number;
  emi_amount: number;
  emi_due_date: number | null;
  prepayment_penalty_pct: number;
  foreclosure_charges_pct: number;
  eligible_80c: boolean;
  eligible_24b: boolean;
  eligible_80e: boolean;
  eligible_80eea: boolean;
  disbursement_date: string | null;
  status: "active" | "closed";
  source: "manual" | "scan" | "account_aggregator";
  source_scan_id: string | null;
  created_at: string;
  updated_at: string;
}

export interface AmortizationEntry {
  month: number;
  emi: number;
  principal: number;
  interest: number;
  balance: number;
  prepayment: number;
  cumulative_interest: number;
}

export interface LoanResult {
  loan_id: string;
  bank_name: string;
  loan_type: string;
  original_balance: number;
  payoff_month: number;
  months_saved: number;
}

export interface StrategyResult {
  strategy_name: string;
  strategy_description: string;
  total_interest_paid: number;
  total_months: number;
  interest_saved_vs_baseline: number;
  months_saved_vs_baseline: number;
  payoff_order: string[];
  loan_results: LoanResult[];
  debt_free_date_months: number;
}

export interface OptimizationResult {
  baseline_total_interest: number;
  baseline_total_months: number;
  strategies: StrategyResult[];
  recommended_strategy: string;
}

export interface ScanJob {
  job_id: string;
  status: "uploaded" | "processing" | "completed" | "review_needed" | "failed";
  extracted_fields: ExtractedField[] | null;
  error_message: string | null;
  processing_time_ms: number | null;
  created_at: string;
}

export interface ExtractedField {
  field_name: string;
  value: string;
  confidence: number;
}

export interface EMIResult {
  emi: number;
  total_interest: number;
  total_payment: number;
  interest_saved: number;
  months_saved: number;
}

export interface DashboardSummary {
  has_loans: boolean;
  loan_count: number;
  total_debt: number;
  total_emi: number;
  suggested_extra: number;
  recommended_strategy: string;
  interest_saved: number;
  months_saved: number;
  debt_free_months: number;
  baseline_months: number;
  strategies_preview: { name: string; interest_saved: number; months_saved: number }[];
}

export interface LoanInsight {
  loan_id: string;
  text: string;
}

export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  text: string;
  timestamp: Date;
}

export interface TaxImpact {
  old_regime_tax: number;
  new_regime_tax: number;
  recommended: string;
  savings: number;
  explanation: string;
  deductions: Record<string, number>;
}

export interface Review {
  id: string;
  user_id: string;
  user_display_name: string | null;
  review_type: "feedback" | "testimonial" | "feature_request";
  rating: number | null;
  title: string;
  content: string;
  status: string;
  admin_response: string | null;
  is_public: boolean;
  created_at: string;
  updated_at: string;
}

export interface AdminStats {
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

export interface UsageSummary {
  total_cost_30d: number;
  total_calls_30d: number;
  by_service: Record<string, { call_count: number; total_cost: number; tokens_input: number; tokens_output: number }>;
  daily_costs: { date: string; service: string; call_count: number; total_cost: number }[];
}

export interface SensitivityPoint {
  rate_delta_pct: number;
  total_interest_paid: number;
  total_months: number;
  interest_saved_vs_baseline: number;
}

export interface SensitivityResult {
  strategy_name: string;
  points: SensitivityPoint[];
}
