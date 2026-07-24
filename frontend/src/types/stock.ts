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
  recommendation: string;
  confidence_score: number;
  reasons: string[];
  warnings: string[];
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
