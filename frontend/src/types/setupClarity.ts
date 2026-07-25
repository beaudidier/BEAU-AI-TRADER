export type SetupStatus =
  | "waiting_for_entry"
  | "entry_triggered"
  | "expired"
  | "invalidated"
  | "completed";

export type SetupClarity = {
  status: SetupStatus;
  instruction: string;
  actionable_at_market: boolean;
  current_price: number | null;
  current_price_timestamp: string | null;
  planned_entry: number | null;
  distance_to_entry_percent: number | null;
  distance_to_entry_label: string;
  expiry_date: string | null;
  invalidation: string;
  beginner_explanation: {
    why_setup_exists: string;
    why_waiting_matters: string;
    if_price_never_reaches_entry: string;
    why_buying_early_changes_risk_reward: string;
  };
};

export type SectorConcentration = {
  active_signal_count: number;
  sectors: Array<{
    sector: string;
    count: number;
    percentage: number;
  }>;
  dominant_sector_warning: boolean;
  related_sector_warning: boolean;
  related_theme: {
    theme: string;
    sectors: string[];
    count: number;
    percentage: number;
  } | null;
  warnings: string[];
  has_warning: boolean;
  thresholds: {
    single_sector_percent: number;
    two_related_sectors_percent: number;
  };
};
