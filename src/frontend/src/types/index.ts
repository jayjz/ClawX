/** Bot entity — mirrors GET /bots response */
export interface Bot {
  id: number;
  handle: string;
  balance: number;
  status: string;
  owner_id: number | null;
  is_verified: boolean;
  created_at: string;
}

/** Activity entry — mirrors GET /posts/feed response */
export interface ActivityEntry {
  id: number;
  bot_id: number;
  author_handle: string;
  content: string;
  parent_id: number | null;
  repost_of_id: number | null;
  prediction_id: number | null;
  reasoning: string | null;
  created_at: string;
}

/** POST /bots request payload */
export interface BotCreatePayload {
  handle: string;
  persona_yaml: string;
  api_key: string;
}

/** POST /bots success response */
export interface BotCreateResponse {
  id: number;
  handle: string;
  balance: number;
  api_key: string;
  api_secret: string;
  message: string;
}

/** GET /health response */
export interface HealthResponse {
  status: string;
  mode: string;
}

/** API error shape */
export interface ApiError {
  detail: string;
}
