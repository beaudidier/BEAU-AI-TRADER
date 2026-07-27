import type { SectorConcentration, SetupClarity, SetupStatus } from "./setupClarity";

export type Profile = { id: string; display_name: string | null; avatar_url: string | null; timezone: string; trading_experience: string | null; risk_profile: string | null; created_at: string; updated_at: string };
export type Subscription = { id: string; user_id: string; plan: "FREE" | "PRO" | "ELITE"; status: string; trial_ends_at: string | null; current_period_end: string | null };
export type Watchlist = { id: string; user_id: string; name: string; created_at: string; updated_at: string };
export type WatchlistItem = { id: string; watchlist_id: string; ticker: string; created_at: string };
export type SavedAnalysis = { id: string; user_id: string; ticker: string; analysis_json: Record<string, unknown>; created_at: string };
export type BacktestRun = { id: string; user_id: string; ticker: string; parameters: Record<string, unknown>; results: Record<string, unknown>; created_at: string };
export type Trade = { id: string; user_id: string; ticker: string; side: "BUY" | "SELL"; entry_price: number; stop_price: number | null; target_price: number | null; quantity: number; status: string; pnl: number | null };
export type UserSettings = { user_id: string; default_account_size: number; default_risk_percent: number; preferred_currency: string; theme: string };
export type PaperTrade = { id: string; ticker: string; side: "BUY" | "SELL"; status: "OPEN" | "CLOSED"; entry_price: number; exit_price: number | null; stop_loss: number; target_1: number; target_2: number; quantity: number; confidence_score: number; recommendation: string; realized_pnl: number | null; unrealized_pnl?: number; market_price?: number; opened_at: string; closed_at: string | null; initial_risk_amount?: number; initial_risk_r?: number; remaining_risk_r?: number; remaining_fraction?: number; risk_admitted_at?: string; trade_source?: "manual" | "forward_validation"; portfolio_signal_rank?: number | null; coach_analysis?: Record<string, unknown> | null };
export type PortfolioRiskDashboard = { limits: { maximum_concurrent_positions: number; maximum_total_open_risk_r: number; maximum_daily_new_risk_r: number; ranking: string }; open_positions: number; open_risk_r: number; open_risk_currency: number; risk_unit_currency: number; daily_new_risk_used_r: number; remaining_daily_risk_budget_r: number; current_equity: number; peak_equity: number; current_drawdown: number; current_drawdown_r: number; risk_status: "NORMAL" | "CAUTION" | "BLOCKED"; blocked_reasons: string[]; capacity_resets_at: string; limiting_positions: Array<{ id: string; ticker: string; remaining_risk_r: number }>; as_of: string };
export type PortfolioRiskRejection = { id: string; source: "forward_validation_signal" | "paper_trade_automatic" | "paper_trade_manual"; ticker: string; rejection_reason: string; current_open_positions: number; current_open_risk_r: number; daily_new_risk_r: number; proposed_risk_r: number; signal_rank: number; limiting_reference?: string | null; capacity_resets_at: string; rejected_at: string };
export type PaperPortfolio = { initial_balance: number; cash_balance: number; portfolio_balance: number; unrealized_pnl: number; realized_pnl: number; today_pnl: number; win_rate: number; open_positions: PaperTrade[]; closed_positions: PaperTrade[]; recent_trades: PaperTrade[]; portfolio_risk: PortfolioRiskDashboard; risk_rejections: PortfolioRiskRejection[] };
export type PaperClosePreview = { trade_id: string; ticker: string; side: "BUY" | "SELL"; latest_quote: number; quote_timestamp: string; estimated_exit_value: number; realized_pnl_estimate: number };
export type LearningMetric = { label: string; trades: number; win_rate: number; average_rr: number };
export type LearningDashboard = { personal_statistics: { total_trades: number; wins: number; losses: number; win_rate: number; average_rr: number; average_holding_minutes: number }; winrate_by_confidence: LearningMetric[]; winrate_by_market_regime: LearningMetric[]; winrate_by_holding_time: LearningMetric[]; best_performing_setups: LearningMetric[]; worst_performing_setups: LearningMetric[]; most_common_mistakes: Array<{ mistake: string; count: number }>; ai_recommendations: string[]; monthly_progress: Array<{ month: string; trades: number; win_rate: number; pnl: number }> };
export type ForwardValidationStatus = "waiting_for_entry" | "entered" | "expired" | "TP1_hit" | "TP2_hit" | "stopped" | "completed" | "data_error" | "portfolio_blocked";
export type ForwardValidationOutcome = { status: ForwardValidationStatus; entry_price?: number | null; entry_timestamp?: string | null; completed_at?: string | null; tp1_hit?: boolean; tp2_hit?: boolean; stop_hit?: boolean; open_pl?: number; open_r?: number; realized_r?: number; double_cost_realized_r?: number | null; mfe_r?: number; mae_r?: number; holding_days?: number; costs?: number; slippage?: number; remaining_fraction?: number; last_evaluated_at?: string | null };
export type ForwardValidationSignal = { id: string; ticker: string; sector?: string; signal_timestamp: string; signal_price: number; proposed_pullback_entry: number; expected_entry_fill: number; stop_loss: number; target_1: number; target_2: number; market_regime: string; market_regime_score: number; confidence: number; strategy_version: string; data_timestamp: string; expiry_date?: string | null; initial_status?: "waiting_for_entry"; setup?: SetupClarity; outcome: ForwardValidationOutcome & { setup_status?: SetupStatus; current_price?: number | null; current_price_timestamp?: string | null; invalidation_reason?: string | null } };
export type ForwardValidationMetrics = { expectancy: number; profit_factor: number | null; win_rate: number; maximum_drawdown: number; total_sample_size: number; double_cost_expectancy: number; double_cost_profit_factor: number | null; approval: { minimum_completed_trades: boolean; positive_expectancy: boolean; profit_factor_above_one: boolean; acceptable_drawdown: boolean; positive_after_double_costs: boolean; approved: boolean } };
export type ForwardValidationSymbolStatus = "completed" | "insufficient_history" | "invalid_symbol" | "provider_failure" | "timeout" | "stale_data" | "incomplete_data";
export type ForwardValidationSymbolDiagnostic = { status: ForwardValidationSymbolStatus; reason: string };
export type ForwardValidationRun = { id: string; runner_version: string; trigger: "manual" | "scheduled"; status: "running" | "success" | "partial" | "failed" | "skipped"; started_at: string; completed_at?: string | null; data_timestamp?: string | null; symbols_requested: string[]; symbols_completed: string[]; symbols_failed: string[]; provider_errors: Record<string, string>; signals_created: number; duplicates_prevented: number; outcomes_updated: number; universe_id?: string; universe_snapshot_version?: string | null; expected_symbols?: number; eligible_symbols?: string[]; completed_eligible_symbols?: string[]; excluded_symbols?: Record<string, ForwardValidationSymbolDiagnostic>; genuine_failures?: Record<string, ForwardValidationSymbolDiagnostic>; symbol_outcomes?: Record<string, ForwardValidationSymbolDiagnostic>; scanned_symbols?: number; cached_symbols?: number; provider_request_count?: number; retry_count?: number; runtime_seconds?: number; batches_completed?: number; total_batches?: number; completion_percentage?: number; provider_health?: "waiting" | "running" | "healthy" | "degraded" | "failed"; last_complete_market_date?: string | null; rejection_reasons?: Record<string, number>; message?: string | null };
export type ForwardValidationReplay = { replay_date: string; expected_symbols: number; completed_symbols: number; eligible_symbols: number; completed_eligible_symbols: number; excluded_symbols: Record<string, ForwardValidationSymbolDiagnostic>; genuine_failures: Record<string, ForwardValidationSymbolDiagnostic>; completion_percentage: number; health: "healthy" | "degraded" | "failed"; signals_found: number; runtime_seconds: number; last_complete_market_date: string };
export type ForwardValidationRunner = { health: "waiting" | "healthy" | "running" | "degraded" | "failed"; last_run: ForwardValidationRun | null; last_successful_run: ForwardValidationRun | null; next_scheduled_run: string; schedule: string; runner_version: string; latest_replay: ForwardValidationReplay | null; active_universe: { id: string; name: string; expected_symbols: number; snapshot_version: string } };
export type ForwardValidationDashboard = { strategy: { name: string; status: string; asset_class: string; trading_style: string; direction: string; strategy_version: string; disclaimer: string }; active_signals: ForwardValidationSignal[]; expired_signals: ForwardValidationSignal[]; open_paper_trades: ForwardValidationSignal[]; completed_trades: ForwardValidationSignal[]; blocked_signals?: ForwardValidationSignal[]; concentration?: SectorConcentration; setup_statuses?: SetupStatus[]; metrics: ForwardValidationMetrics; runner: ForwardValidationRunner; sample_progress: { completed: number; required: number; percentage: number }; portfolio_risk: PortfolioRiskDashboard; portfolio_risk_rejections: PortfolioRiskRejection[] };
export type FeedbackCategory = "strategy logic" | "entry/stop/target" | "chart" | "risk" | "data quality" | "usability" | "bug" | "missing context";
export type FeedbackSeverity = "low" | "medium" | "high" | "critical";
export type BetaFeedback = { id: string; user_id: string; page: string; ticker: string | null; category: FeedbackCategory; severity: FeedbackSeverity; message: string; screenshot_reference: string | null; created_at: string };
export type ProfessionalSignalReview = { id: string; user_id: string; signal_id: string | null; ticker: string; would_take_setup: boolean; entry_logical: boolean; stop_structurally_correct: boolean; targets_realistic: boolean; relevant_context_missing: boolean; market_regime_makes_sense: boolean; setup_confidence: number; notes: string | null; created_at: string };
export type BetaInviteStatus = "active" | "used" | "revoked" | "expired";
export type BetaInvite = { id: string; status: BetaInviteStatus; created_at: string; expires_at: string; max_uses: number; use_count: number; remaining_uses: number; label: string | null };
export type CreatedBetaInvite = BetaInvite & { invite_url: string };
export type PrivateBetaReadiness = {
  system_status: "operational" | "monitoring" | "degraded" | "waiting";
  latest_complete_market_date: string | null;
  latest_scan_time: string | null;
  market_data_health:
    | "healthy"
    | "running"
    | "degraded"
    | "failed"
    | "waiting";
  scheduler_health:
    | "on_schedule"
    | "running"
    | "attention_required"
    | "delayed"
    | "awaiting_first_run";
  next_scheduled_run: string | null;
  scan_completion_percentage: number;
  failed_symbol_count: number;
  partial_scan: boolean;
  paper_trading_only_warning: string;
};
