import { describe, expect, it } from "vitest";

import { beginnerSafety, paperTradePayload, selectBestSetup } from "./beginnerMode";
import type { PaperPortfolio } from "../types/database";
import type { LatestSignalEvidence } from "../types/latestSignals";
import type { TradePlan } from "../types/stock";

const now = new Date("2026-07-28T12:00:00Z");

function signal(status: LatestSignalEvidence["setup_status"], overrides: Partial<LatestSignalEvidence> = {}): LatestSignalEvidence {
  return {
    id: "signal-1", ticker: "TEST", company_name: "Test Company", sector: "Technology",
    signal_date: "2026-07-28", setup_status: status, current_price: 100, planned_entry: 100,
    distance_to_entry_percent: 0, expiry_date: "2026-07-31", invalidation: "Price broke the setup.",
    data_timestamp: "2026-07-28T11:00:00Z", signal_timestamp: "2026-07-28T10:00:00Z",
    market_regime: "bullish", market_regime_score: 1, signal_price: 101, confidence: 80,
    risk_percent: 2, risk_reward_target_1: 2, risk_reward_target_2: 3,
    levels: { ema20: 100, ema50: 98, pullback_entry: 100, swing_low: 96, stop: 98, tp1: 104, tp2: 106 },
    qualification_reasons: ["Trend and pullback rules passed."], strategy_version: "frozen",
    chart: { public_url: "", window_start: "", window_end: "" }, checks: {},
    setup: {
      status, instruction: "", actionable_at_market: status === "entry_triggered",
      current_price: 100, current_price_timestamp: "2026-07-28T11:00:00Z", planned_entry: 100,
      distance_to_entry_percent: 0, distance_to_entry_label: "at entry", expiry_date: "2026-07-31",
      invalidation: "Price broke the setup.",
      beginner_explanation: {
        why_setup_exists: "The trend and pullback rules passed.",
        why_waiting_matters: "Wait for the planned price.",
        if_price_never_reaches_entry: "No trade opens.",
        why_buying_early_changes_risk_reward: "Buying early changes the risk.",
      },
    },
    ...overrides,
  };
}

const plan = {
  ticker: "TEST", signal_price: 101, current_price: 100, proposed_executable_entry: 100,
  entry: 100, stop_loss: 98, target_1: 104, target_2: 106, risk_per_share: 2,
  reward_to_target_1: 4, reward_to_target_2: 6, risk_reward_target_1: 2, risk_reward_target_2: 3,
  position_size: 10, total_position_value: 1000, maximum_risk: 20, account_risk_percent: 1,
  recommendation: "BUY", confidence_score: 80, reasons: [], warnings: [], trade_allowed: true,
  rejection_reasons: [],
  explanation: { verdict: "", summary: "", strengths: [], weaknesses: [], risks: ["The trend may reverse."], invalidation: "", next_trigger: "", confidence_explanation: "" },
} satisfies TradePlan;

function portfolio(blockedReasons: string[] = []): PaperPortfolio {
  return {
    initial_balance: 10000, cash_balance: 10000, portfolio_balance: 10000,
    unrealized_pnl: 0, realized_pnl: 0, today_pnl: 0, win_rate: 0,
    open_positions: [], closed_positions: [], recent_trades: [], risk_rejections: [],
    portfolio_risk: {
      risk_status: blockedReasons.length ? "BLOCKED" : "NORMAL",
      blocked_reasons: blockedReasons, open_positions: 0, open_risk_r: 0, daily_new_risk_used_r: 0,
      risk_unit_currency: 100, capacity_resets_at: "2026-07-29T00:00:00Z",
      limits: { maximum_concurrent_positions: 10, maximum_total_open_risk_r: 10, maximum_daily_new_risk_r: 1 },
    },
  } as unknown as PaperPortfolio;
}

describe("Beginner Mode safety", () => {
  it("shows Wait for entry and never permits a waiting setup", () => {
    expect(beginnerSafety(signal("waiting_for_entry"), plan, portfolio(), now)).toMatchObject({ action: "Wait for entry", canReview: false });
  });

  it("allows review only after entry is triggered", () => {
    expect(beginnerSafety(signal("entry_triggered"), plan, portfolio(), now)).toMatchObject({ status: "ready", action: "Review paper trade", canReview: true });
  });

  it("blocks invalidated setups", () => {
    expect(beginnerSafety(signal("invalidated"), plan, portfolio(), now)).toMatchObject({ status: "blocked", action: "Setup blocked", canReview: false });
  });

  it("blocks expired setups", () => {
    expect(beginnerSafety(signal("expired"), plan, portfolio(), now)).toMatchObject({ status: "expired", action: "Setup expired", canReview: false });
  });

  it("blocks stale data", () => {
    const result = beginnerSafety(signal("entry_triggered", { data_timestamp: "2026-07-20T00:00:00Z" }), plan, portfolio(), now);
    expect(result.canReview).toBe(false);
    expect(result.reasons.join(" ")).toContain("stale");
  });

  it("preserves portfolio-risk blocks", () => {
    const result = beginnerSafety(signal("entry_triggered"), plan, portfolio(["Daily risk limit reached."]), now);
    expect(result).toMatchObject({ action: "Setup blocked", canReview: false });
    expect(result.reasons).toContain("Daily risk limit reached.");
  });

  it("builds paper-only confirmation values from the unchanged trade plan", () => {
    expect(paperTradePayload(plan)).toEqual({
      ticker: "TEST", side: "BUY", current_price: 100, entry_price: 100, stop_loss: 98,
      target_1: 104, target_2: 106, quantity: 10, confidence_score: 80,
      recommendation: "BUY", risk_reward_target_1: 2,
    });
  });

  it("shows one best setup, prioritizing a triggered entry", () => {
    const selected = selectBestSetup([signal("waiting_for_entry", { id: "high", confidence: 99 }), signal("entry_triggered", { id: "ready", confidence: 70 })]);
    expect(selected?.id).toBe("ready");
  });
});
