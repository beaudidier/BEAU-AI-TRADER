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
