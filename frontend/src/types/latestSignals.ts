export type LatestSignalLevels = {
  ema20: number;
  ema50: number;
  pullback_entry: number;
  swing_low: number;
  stop: number;
  tp1: number;
  tp2: number;
};

export type LatestSignalEvidence = {
  id: string;
  ticker: string;
  company_name: string;
  sector: string;
  signal_date: string;
  data_timestamp: string;
  signal_timestamp: string;
  market_regime: string;
  market_regime_score: number;
  signal_price: number;
  confidence: number;
  risk_percent: number;
  risk_reward_target_1: number;
  risk_reward_target_2: number;
  levels: LatestSignalLevels;
  qualification_reasons: string[];
  strategy_version: string;
  chart: {
    public_url: string;
    window_start: string;
    window_end: string;
  };
  checks: Record<string, boolean>;
};

export type LatestSignalEvidenceSummary = {
  schema_version: number;
  generated_at: string;
  classification: string;
  replay_date: string;
  strategy: {
    name: string;
    version: string;
    status: string;
    asset_class: string;
  };
  methodology: {
    source: string;
    execution: string;
    notice: string;
    look_ahead_data_used: boolean;
  };
  signal_count: number;
  sectors: string[];
  tickers: string[];
  missing_raw_data: string[];
  mismatches: Array<{ ticker: string; fields: string[] }>;
  duplicate_signals: string[];
  checks: Record<string, boolean>;
  all_checks_passed: boolean;
  signals: LatestSignalEvidence[];
};
