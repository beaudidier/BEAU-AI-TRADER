export type Stock = {
  ticker: string;
  price: number;
  ema20: number;
  ema50: number;
  rsi: number;
  atr: number;
  support: number;
  resistance: number;
  score: number;
  recommendation: string;
  reasons: string[];
};

export type ScanJob = {
  job_id: string;
  status: "queued" | "running" | "completed";
  market: "stocks" | "crypto";
  universe: string;
  total_symbols: number;
  completed_symbols: number;
  failed_symbols: number;
  progress_percentage: number;
  started_at: string | null;
  completed_at: string | null;
};

export type Timeframe = "1D" | "1W" | "1M" | "3M" | "6M" | "1Y";

export type Candle = {
  time: number;
  open: number;
  high: number;
  low: number;
  close: number;
};

export type LinePoint = {
  time: number;
  value: number;
};

export type StockChartData = {
  ticker: string;
  timeframe: Timeframe;
  candles: Candle[];
  ema20: LinePoint[];
  ema50: LinePoint[];
  support: number;
  resistance: number;
  latest_timestamp: string;
};

export type TradePlan = {
  ticker: string;
  current_price: number;
  entry: number;
  stop_loss: number;
  target_1: number;
  target_2: number;
  risk_per_share: number;
  reward_to_target_1: number;
  reward_to_target_2: number;
  risk_reward_target_1: number;
  risk_reward_target_2: number;
  position_size: number;
  total_position_value: number;
  maximum_risk: number;
  account_risk_percent: number;
  recommendation: string;
  confidence_score: number;
  reasons: string[];
  warnings: string[];
  explanation: ExplainableRecommendation;
};

export type ExplainableRecommendation = {
  verdict: string;
  summary: string;
  strengths: string[];
  weaknesses: string[];
  risks: string[];
  invalidation: string;
  next_trigger: string;
  confidence_explanation: string;
};

export type BacktestRequest = {
  ticker: string;
  start_date: string;
  end_date: string;
  minimum_confidence: number;
  account_size: number;
  risk_percent: number;
};

export type BacktestSummary = {
  total_trades: number;
  wins: number;
  losses: number;
  win_rate: number;
  average_rr: number;
  average_confidence: number;
  max_drawdown: number;
  profit_factor: number;
  expectancy: number;
  starting_equity: number;
  ending_equity: number;
  net_profit: number;
};

export type BacktestTrade = {
  ticker: string;
  entry_date: string;
  exit_date: string;
  entry: number;
  exit: number;
  stop_loss: number;
  target_1: number;
  target_2: number;
  shares: number;
  pnl: number;
  realized_rr: number;
  confidence_score: number;
  recommendation: string;
  exit_reason: string;
};

export type BacktestResult = {
  summary: BacktestSummary;
  equity_curve: Array<{ time: string; value: number }>;
  trades: BacktestTrade[];
};

export type CoachAnalysis = {
  grade: "A" | "B" | "C" | "D" | "F";
  score: number;
  summary: string;
  mistakes: string[];
  positives: string[];
  improvements: string[];
  confidence_alignment: string;
  emotional_bias: string;
  discipline_score: number;
  explanation: ExplainableRecommendation;
};

export type InstitutionalEngineResult = {
  score: number;
  explanation: string;
  confidence: number;
};

export type InstitutionalAnalysis = {
  overall_score: number;
  recommendation: string;
  engines: Record<string, InstitutionalEngineResult>;
  strengths: string[];
  weaknesses: string[];
  warnings: string[];
  explanation: ExplainableRecommendation;
};

export type DailyBriefing = { market_summary: { sentiment: string; confidence: number; explanation: string }; opportunities: Array<{ ticker: string; confidence: number; recommendation: string; rr: number; trend: string; price: number; explanation: ExplainableRecommendation }>; watchlist_summary: { biggest_winner: { ticker: string; change_percent: number } | null; biggest_loser: { ticker: string; change_percent: number } | null; new_buy_signals: string[]; new_strong_buy_signals: string[] }; market_health: Record<string, { label: string; value: string }>; daily_opportunities: string; upcoming_events: Array<{ title: string; detail: string }> };
