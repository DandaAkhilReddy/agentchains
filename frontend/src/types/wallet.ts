export interface TokenAccount {
  id: string;
  agent_id: string | null;
  balance: number;
  total_deposited: number;
  total_earned: number;
  total_spent: number;
  total_fees_paid: number;
  created_at: string;
  updated_at: string;
}

export interface TokenLedgerEntry {
  id: string;
  from_account_id: string | null;
  to_account_id: string | null;
  amount: number;
  fee_amount: number;
  tx_type: string;
  reference_id: string | null;
  reference_type: string | null;
  memo: string;
  created_at: string;
}

export interface TokenLedgerResponse {
  entries: TokenLedgerEntry[];
  total: number;
  page: number;
  page_size: number;
}

export interface TokenDeposit {
  id: string;
  agent_id: string;
  amount_usd: number;
  status: "pending" | "completed" | "failed" | "refunded";
  payment_method: string;
  payment_ref: string | null;
  created_at: string;
  completed_at: string | null;
}

export interface WalletBalanceResponse {
  balance: number;
  total_earned: number;
  total_spent: number;
  total_deposited: number;
  total_fees_paid: number;
}

export interface DepositResponse {
  id: string;
  agent_id: string;
  amount_usd: number;
  currency: string;
  status: string;
  payment_method: string;
  payment_ref: string | null;
  created_at: string | null;
  completed_at: string | null;
  checkout_url?: string | null;
}

export interface TransferResponse {
  id: string;
  amount: number;
  fee_amount: number;
  tx_type: string;
  memo: string | null;
  created_at: string | null;
}
