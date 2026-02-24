export type TransactionStatus =
  | "initiated"
  | "payment_pending"
  | "payment_confirmed"
  | "delivered"
  | "verified"
  | "completed"
  | "failed"
  | "disputed";

export interface Transaction {
  id: string;
  listing_id: string;
  buyer_id: string;
  seller_id: string;
  amount_usdc: number;
  status: TransactionStatus;
  payment_tx_hash: string | null;
  payment_network: string | null;
  content_hash: string;
  delivered_hash: string | null;
  verification_status: string;
  error_message: string | null;
  initiated_at: string;
  paid_at: string | null;
  delivered_at: string | null;
  verified_at: string | null;
  completed_at: string | null;
  payment_method?: "balance" | "fiat" | "simulated";
}

export interface TransactionListResponse {
  total: number;
  page: number;
  page_size: number;
  transactions: Transaction[];
}
