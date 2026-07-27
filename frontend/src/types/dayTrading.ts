export type DayTradingTimeframe = "1m" | "5m" | "15m";

export type DayTradingStatus = {
  status: "connected" | "configured" | "credentials_required";
  paper_only: true;
  live_money_enabled: false;
  recommendations_enabled: false;
  provider: {
    provider: string;
    configured: boolean;
    feed: "iex" | "sip";
    source: string;
    coverage: "partial-market" | "full-market";
    coverage_warning: string | null;
  };
  stream: StreamHealth;
  market_clock: MarketClock;
  risk_controls: {
    maximum_account_risk_per_trade_percent: number;
    maximum_open_day_trades: number;
    maximum_daily_loss_percent: number;
    maximum_spread_percent: number;
    no_averaging_down: boolean;
    no_overnight_positions: boolean;
    stale_quote_orders_blocked: boolean;
  };
};

export type MarketClock = {
  status: "premarket" | "regular" | "after-hours" | "closed";
  timestamp: string;
  timezone: string;
  is_trading_day: boolean;
  is_early_close: boolean;
  regular_open: string;
  regular_close: string;
  next_transition: string;
};

export type StreamHealth = {
  state: string;
  configured: boolean;
  feed: "iex" | "sip";
  source: string;
  coverage: "partial-market" | "full-market";
  last_event_at: string | null;
  reconnect_attempts: number;
  duplicate_events: number;
  out_of_order_events: number;
  invalid_events: number;
  messages_received: number;
  last_error: string | null;
  stale: boolean;
};

export type DayTradingQuote = {
  ticker: string;
  bid: number;
  ask: number;
  bid_size: number;
  ask_size: number;
  midpoint: number;
  spread: number;
  spread_percent: number;
  timestamp: string;
  source: string;
  coverage: "partial-market" | "full-market";
  stale: boolean;
};

export type DayTradingBar = {
  ticker: string;
  timeframe: DayTradingTimeframe;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
  vwap: number | null;
  timestamp: string;
  source: string;
  completeness: "incomplete" | "closed" | "gap";
};

export type DayTradingBars = {
  ticker: string;
  timeframe: DayTradingTimeframe;
  source: string;
  coverage: string;
  bars: DayTradingBar[];
  gaps: Array<{ from: string; to: string }>;
};

export type PaperAccount = {
  starting_balance: number;
  cash: number;
  equity: number;
  realized_pnl: number;
  unrealized_pnl: number;
  daily_pnl: number;
  daily_loss_limit: number;
  daily_loss_locked: boolean;
  paper_orders_enabled: boolean;
  open_positions: number;
  maximum_open_positions: number;
  maximum_risk_per_trade_percent: number;
  maximum_daily_loss_percent: number;
  paper_only: true;
  live_money_enabled: false;
};

export type PaperPosition = {
  ticker: string;
  quantity: number;
  entry_price: number;
  protective_stop: number;
  opened_at: string;
  current_price: number;
  unrealized_pnl: number;
};

export type PaperPositions = {
  open: PaperPosition[];
  closed: Array<{
    ticker: string;
    quantity: number;
    entry_price: number;
    exit_price: number;
    opened_at: string;
    closed_at: string;
    realized_pnl: number;
    reason: string;
  }>;
};

export type PaperOrderInput = {
  ticker: string;
  side: "buy" | "sell";
  order_type: "market" | "limit" | "stop";
  quantity: number;
  idempotency_key: string;
  limit_price?: number;
  stop_price?: number;
  protective_stop?: number;
};
