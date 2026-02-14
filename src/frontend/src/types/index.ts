export interface PostData {
  id: number;
  bot_id: number;
  author_handle: string;
  content: string;
  parent_id: number | null;
  repost_of_id: number | null;
  created_at: string;
  reasoning?: string | null;
  prediction_id?: number | null;
}

export interface LedgerEntry {
  id: number;
  bot_id: number;
  amount: number;
  transaction_type: string;
  reference_id: string | null;
  previous_hash: string;
  hash: string;
  timestamp: string;
}

export interface BotData {
  id: number;
  handle: string;
  balance: number;
  status: string;
  owner_id: number | null;
  is_verified: boolean;
  created_at: string;
}

export interface UserData {
  id: number;
  username: string;
  balance: number;
  created_at: string;
}

export interface PredictionData {
  id: number;
  bot_id: number | null;
  user_id: number | null;
  claim_text: string;
  direction: string;
  confidence: number;
  wager_amount: number;
  start_price: number | null;
  reasoning: string | null;
  status: string;
  created_at: string;
}
