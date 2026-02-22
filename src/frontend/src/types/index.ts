/** Bot entity — mirrors GET /bots response */
export interface Bot {
  id: number;
  handle: string;
  balance: number;
  status: string;
  owner_id: number | null;
  is_verified: boolean;
  created_at: string;
  last_action_at: string | null;
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

/** Market entity — mirrors GET /markets/active response */
export interface Market {
  id: string;
  description: string;
  source_type: 'GITHUB' | 'NEWS' | 'WEATHER' | 'RESEARCH';
  status: 'OPEN' | 'LOCKED' | 'RESOLVED';
  bounty: number;
  deadline: string;
  created_at: string;
}

/** API error shape */
export interface ApiError {
  detail: string;
}

/** GET /insights/{agent_id} response */
export interface AgentInsights {
  agent_id: number;
  handle: string;
  status: string;
  enforcement_mode: string;
  balance_snapshot: number;
  aggregate: {
    total_ticks_observed: number;
    idle_rate: number;
    avg_phantom_entropy_fee: number;
    would_have_been_liquidated_count: number;
  };
  recent_metrics: Array<{
    tick_id: string;
    outcome: string;
    enforcement_mode: string;
    phantom_fee: number;
    would_liquidate: boolean;
    balance: number;
    created_at: string | null;
    details: Record<string, unknown> | null;
  }>;
}

/** Per-agent entry in viability_log.json "agents" map */
export interface ViabilityAgent {
  total_ticks: number;
  research_wins: number;
  tool_uses: number;
  deaths: number;
  phantom_liquidations: number;
  phantom_fee_total: number;
  portfolio_bets: number;
  idle_streak_max: number;
  idle_streak_avg: number;
  viability_score: number;
  viability_label: 'VIABLE' | 'MARGINAL' | 'AT_RISK';
}

/** Root shape of viability_log.json */
export interface ViabilityLog {
  version: string;
  logfile: string;
  agent_count: number;
  metrics: Record<string, number>;
  viability_score: number;
  viability_label: 'VIABLE' | 'MARGINAL' | 'AT_RISK';
  agents: Record<string, ViabilityAgent>;
}
