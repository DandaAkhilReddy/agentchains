export interface Creator {
  id: string;
  email: string;
  display_name: string;
  phone: string | null;
  country: string | null;
  payout_method: "none" | "upi" | "bank" | "gift_card";
  status: "active" | "suspended" | "pending_verification";
  created_at: string;
  updated_at: string;
}

export interface CreatorAuthResponse {
  creator: Creator;
  token: string;
}

export interface CreatorAgent {
  agent_id: string;
  agent_name: string;
  agent_type: string;
  status: string;
  total_earned: number;
  total_spent: number;
  balance: number;
}

export interface CreatorDashboard {
  creator_balance: number;
  creator_total_earned: number;
  agents_count: number;
  agents: CreatorAgent[];
  total_agent_earnings: number;
  total_agent_spent: number;
}

export interface CreatorWallet {
  balance: number;
  total_earned: number;
  total_spent: number;
  total_deposited: number;
  total_fees_paid: number;
}

export interface RedemptionRequest {
  id: string;
  creator_id: string;
  redemption_type: "api_credits" | "gift_card" | "bank_withdrawal" | "upi";
  amount_usd: number;
  currency: string;
  status: "pending" | "processing" | "completed" | "failed" | "rejected";
  payout_ref: string | null;
  admin_notes: string;
  rejection_reason: string;
  created_at: string;
  processed_at: string | null;
  completed_at: string | null;
}

export interface RedemptionMethodInfo {
  type: string;
  label: string;
  min_usd: number;
  processing_time: string;
  available: boolean;
}
