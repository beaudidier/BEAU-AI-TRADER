export type EvidenceOutcome = "WINNER" | "LOSER" | "EXPIRED" | "REJECTED";

export type EvidenceExitLeg = {
  leg: string;
  exit_date: string;
  shares: number;
  reference_price: number;
  exit_price: number;
  pnl: number;
  r_multiple: number;
};

export type EvidenceExample = {
  id: string;
  category: EvidenceOutcome;
  ticker: string;
  company_name: string;
  sector: string;
  classification: {
    label: string;
    retrospective_holdout: boolean;
    out_of_sample: boolean;
    forward_validation: boolean;
  };
  signal_date: string;
  data_timestamp: string;
  market_regime: {
    historical_label: string;
    engine_score: number;
    engine_explanation: string;
  };
  confidence: number;
  recommendation: string;
  signal_price: number;
  levels: {
    ema20: number;
    ema50: number;
    proposed_pullback_entry: number;
    expected_entry_fill: number;
    swing_low_20: number;
    stop_loss: number;
    target_1: number;
    target_2: number;
  };
  actual_entry_date: string | null;
  actual_entry_price: number | null;
  holding_period_candles: number;
  exit_legs: EvidenceExitLeg[];
  costs_and_slippage: {
    total_transaction_cost_gbp: number;
    total_slippage_gbp: number;
  };
  final_r_result: number | null;
  maximum_favourable_excursion_r: number | null;
  maximum_adverse_excursion_r: number | null;
  exact_qualification_reasons: string[];
  rejection_or_expiry_reason: string | null;
  position_sizing: {
    position_size_shares: number;
    maximum_monetary_risk_gbp: number;
  };
  chart: {
    public_url: string;
  };
};

export type EvidenceSummary = {
  schema_version: number;
  classification: {
    retrospective_holdout: boolean;
    out_of_sample: boolean;
    forward_validation: boolean;
    holdout_window: { start: string; end: string };
  };
  strategy: {
    name: string;
    version: string;
    rules: {
      entry_wait_candles: number;
      entry: string;
      regime_gate: string;
      stop: string;
      target_1_r: number;
      target_2_r: number;
      tp1_portion: number;
      stop_management: string;
      same_candle_rule: string;
      slippage_bps_per_side: number;
      transaction_cost_bps_per_side: number;
    };
  };
  selection: {
    algorithm: string;
    seed: string;
    candidate_population: number;
    candidate_distribution: Record<EvidenceOutcome, number>;
    quotas: Record<EvidenceOutcome, number>;
    strata: string[];
    selected_keys_sha256: string;
    deterministic_replay_verified: boolean;
    milestone_34_audit: {
      finding: string;
      resolution: string;
      manual_record_ids_used: boolean;
    };
  };
  population_statistics: {
    classification: string;
    candidate_signals: number;
    accepted_trades: number;
    rejected_signals: number;
    wins: number;
    losses: number;
    win_rate: number;
    expectancy_r: number;
    profit_factor: number;
    maximum_drawdown_r: number;
    expectancy_95_ci: [number, number];
    tp1_rate: number;
    tp2_rate: number;
    stop_rate: number;
  };
  example_count: number;
  distribution: Record<EvidenceOutcome, number>;
  coverage: {
    sectors: string[];
    market_regimes: string[];
    years: number[];
    tickers: string[];
  };
  all_audit_checks_passed: boolean;
  future_profitability_guaranteed: boolean;
  examples: EvidenceExample[];
};
