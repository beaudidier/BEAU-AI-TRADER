import { paperTradeAdmissionReasons } from "./portfolioRisk";
import type { PaperPortfolio } from "../types/database";
import type { LatestSignalEvidence } from "../types/latestSignals";
import type { TradePlan } from "../types/stock";

export type BeginnerStatus = "waiting" | "ready" | "blocked" | "expired";

export type BeginnerSafety = {
  status: BeginnerStatus;
  action: "Wait for entry" | "Review paper trade" | "Setup blocked" | "Setup expired";
  canReview: boolean;
  reasons: string[];
};

export const educationTerms = {
  entry: "The planned price where the paper trade may be opened after the setup triggers.",
  "stop loss": "The price used to estimate where the trade idea is wrong and limit the planned loss.",
  target: "A planned price where some or all of a profitable paper trade may be closed.",
  "risk/reward": "A comparison of the amount you could lose with the amount you aim to gain.",
  "position size": "The number of shares chosen so the planned loss stays within your risk limit.",
  pullback: "A temporary price move against the main trend that may offer a planned entry.",
  "market regime": "The broad market environment, such as rising, falling, or moving sideways.",
  confidence: "A model score showing how strongly the setup matches its rules; it is not a probability of profit.",
  "paper trading": "Practice trading with simulated money; no real money is invested.",
} as const;

export function isDataStale(timestamp: string, now = new Date()): boolean {
  const time = new Date(timestamp).getTime();
  return !Number.isFinite(time) || now.getTime() - time > 72 * 60 * 60 * 1000;
}

export function selectBestSetup(signals: LatestSignalEvidence[]): LatestSignalEvidence | null {
  const rank = { entry_triggered: 0, waiting_for_entry: 1, invalidated: 2, expired: 3, completed: 4 };
  return [...signals]
    .filter((signal) => signal.setup_status !== "completed")
    .sort((left, right) => rank[left.setup_status] - rank[right.setup_status] || right.confidence - left.confidence)[0] ?? null;
}

export function beginnerSafety(
  signal: LatestSignalEvidence,
  plan: TradePlan | null,
  portfolio: PaperPortfolio | null,
  now = new Date(),
): BeginnerSafety {
  if (signal.setup_status === "expired") return { status: "expired", action: "Setup expired", canReview: false, reasons: ["The setup's fixed entry window has ended."] };
  if (signal.setup_status === "invalidated") return { status: "blocked", action: "Setup blocked", canReview: false, reasons: [signal.invalidation || "The strategy invalidated this setup."] };
  if (signal.setup_status !== "entry_triggered") return { status: "waiting", action: "Wait for entry", canReview: false, reasons: ["Price has not triggered the planned entry. Buying early would change the risk/reward."] };
  const reasons: string[] = [];
  if (isDataStale(signal.data_timestamp, now)) reasons.push("Market data is stale. Wait for a fresh strategy update.");
  if (!plan) reasons.push("The paper trade plan is still loading.");
  if (plan && !plan.trade_allowed) reasons.push(...plan.rejection_reasons);
  if (plan) reasons.push(...paperTradeAdmissionReasons(portfolio, plan));
  const uniqueReasons = [...new Set(reasons)];
  return uniqueReasons.length
    ? { status: "blocked", action: "Setup blocked", canReview: false, reasons: uniqueReasons }
    : { status: "ready", action: "Review paper trade", canReview: true, reasons: [] };
}

export function paperTradePayload(plan: TradePlan) {
  return {
    ticker: plan.ticker,
    side: "BUY" as const,
    current_price: plan.current_price,
    entry_price: plan.entry,
    stop_loss: plan.stop_loss,
    target_1: plan.target_1,
    target_2: plan.target_2,
    quantity: plan.position_size,
    confidence_score: plan.confidence_score,
    recommendation: plan.recommendation,
    risk_reward_target_1: plan.risk_reward_target_1,
  };
}
