export type Profile = { id: string; display_name: string | null; avatar_url: string | null; timezone: string; trading_experience: string | null; risk_profile: string | null; created_at: string; updated_at: string };
export type Subscription = { id: string; user_id: string; plan: "FREE" | "PRO" | "ELITE"; status: string; trial_ends_at: string | null; current_period_end: string | null };
export type Watchlist = { id: string; user_id: string; name: string; created_at: string; updated_at: string };
export type WatchlistItem = { id: string; watchlist_id: string; ticker: string; created_at: string };
export type SavedAnalysis = { id: string; user_id: string; ticker: string; analysis_json: Record<string, unknown>; created_at: string };
export type BacktestRun = { id: string; user_id: string; ticker: string; parameters: Record<string, unknown>; results: Record<string, unknown>; created_at: string };
export type Trade = { id: string; user_id: string; ticker: string; side: "BUY" | "SELL"; entry_price: number; stop_price: number | null; target_price: number | null; quantity: number; status: string; pnl: number | null };
export type UserSettings = { user_id: string; default_account_size: number; default_risk_percent: number; preferred_currency: string; theme: string };
