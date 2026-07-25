import type { PaperPortfolio } from "../types/database";
import type { TradePlan } from "../types/stock";

export function paperTradeAdmissionReasons(
  portfolio: PaperPortfolio | null,
  plan: TradePlan,
): string[] {
  if (!portfolio) {
    return ["Portfolio risk capacity is still loading. Please wait before opening a paper trade."];
  }
  const risk = portfolio.portfolio_risk;
  const limits = risk.limits;
  const proposedRiskR =
    risk.risk_unit_currency > 0
      ? plan.maximum_risk / risk.risk_unit_currency
      : Number.POSITIVE_INFINITY;
  const reasons = [...risk.blocked_reasons];

  if (
    risk.open_positions + 1 >
    limits.maximum_concurrent_positions
  ) {
    reasons.push(
      `Opening ${plan.ticker} would exceed the ${limits.maximum_concurrent_positions}-position limit.`,
    );
  }
  if (
    risk.open_risk_r + proposedRiskR >
    limits.maximum_total_open_risk_r + 1e-9
  ) {
    reasons.push(
      `Opening ${plan.ticker} would exceed the ${limits.maximum_total_open_risk_r.toFixed(0)}R open-risk limit.`,
    );
  }
  if (
    risk.daily_new_risk_used_r + proposedRiskR >
    limits.maximum_daily_new_risk_r + 1e-9
  ) {
    reasons.push(
      `Opening ${plan.ticker} would exceed today's ${limits.maximum_daily_new_risk_r.toFixed(0)}R new-risk budget. Capacity resets ${new Date(risk.capacity_resets_at).toLocaleString()}.`,
    );
  }
  if (
    portfolio.open_positions.some(
      (trade) => trade.ticker === plan.ticker,
    )
  ) {
    reasons.push(
      `An open ${plan.ticker} paper position already exists.`,
    );
  }
  return [...new Set(reasons)];
}
