import math

import pandas as pd

from decision_rules import recommendation_for_score
from .engine_utils import safe_float
from .explainability_engine import build_explanation


def calculate_trade_plan(
    ticker: str,
    df: pd.DataFrame,
    account_size: float,
    risk_percent: float,
    confidence_output: dict[str, int],
    support: float,
    resistance: float,
    atr: float,
) -> dict:
    """Build a risk-managed trade plan from validated daily market data."""

    current_price = safe_float(df["Close"].iloc[-1])
    account_size = safe_float(account_size)
    risk_percent = safe_float(risk_percent)
    support = safe_float(support)
    resistance = safe_float(resistance)
    atr = safe_float(atr)
    confidence = safe_float(confidence_output.get("confidence"))

    if any(value is None for value in (current_price, account_size, risk_percent, support, resistance, atr, confidence)):
        raise ValueError("Missing or invalid market data")
    if current_price <= 0 or account_size <= 0 or risk_percent <= 0 or atr <= 0:
        raise ValueError("Price, account size, risk percentage, and ATR must be positive")
    if support <= 0 or resistance <= support:
        raise ValueError("Support and resistance levels are invalid")

    entry = min(current_price, support + (atr * 0.25))
    stop_loss = min(support - (atr * 0.5), entry - (atr * 1.5))

    if entry <= 0 or stop_loss <= 0 or stop_loss >= entry:
        raise ValueError("Unable to calculate a safe stop loss")

    risk_per_share = entry - stop_loss
    target_1 = max(resistance, entry + (risk_per_share * 1.5))
    target_2 = max(resistance + risk_per_share, entry + (risk_per_share * 3))
    reward_target_1 = max(0.0, target_1 - entry)
    reward_target_2 = max(0.0, target_2 - entry)
    risk_reward_target_1 = reward_target_1 / risk_per_share if risk_per_share > 0 else 0.0
    risk_reward_target_2 = reward_target_2 / risk_per_share if risk_per_share > 0 else 0.0

    maximum_risk = account_size * (risk_percent / 100)
    risk_limited_shares = math.floor(maximum_risk / risk_per_share) if risk_per_share > 0 else 0
    cash_limited_shares = math.floor(account_size / entry) if entry > 0 else 0
    position_size = max(0, min(risk_limited_shares, cash_limited_shares))
    total_position_value = position_size * entry

    reasons = [
        f"Confidence score is {round(confidence)}",
        f"Target 1 offers {risk_reward_target_1:.2f}R",
        f"Risk is capped at {risk_percent:.2f}% of the account",
    ]
    warnings = []

    if risk_reward_target_1 < 1.5:
        warnings.append("Target 1 risk/reward is below the 1.5 minimum")
    if confidence < 90:
        warnings.append("Confidence is below the 90 threshold for STRONG BUY")
    if position_size == 0:
        warnings.append("Account size and risk settings do not allow a position")
    if current_price > entry + atr:
        warnings.append("Current price is above the suggested entry; wait for a pullback")

    recommendation = recommendation_for_score(confidence)

    result = {
        "ticker": ticker.upper(),
        "current_price": round(current_price, 2),
        "entry": round(entry, 2),
        "stop_loss": round(stop_loss, 2),
        "target_1": round(target_1, 2),
        "target_2": round(target_2, 2),
        "risk_per_share": round(risk_per_share, 2),
        "reward_to_target_1": round(reward_target_1, 2),
        "reward_to_target_2": round(reward_target_2, 2),
        "risk_reward_target_1": round(risk_reward_target_1, 2),
        "risk_reward_target_2": round(risk_reward_target_2, 2),
        "position_size": position_size,
        "total_position_value": round(total_position_value, 2),
        "maximum_risk": round(risk_per_share * position_size, 2),
        "account_risk_percent": round(risk_percent, 2),
        "recommendation": recommendation,
        "confidence_score": round(confidence),
        "reasons": reasons,
        "warnings": warnings,
    }
    result["explanation"] = build_explanation(confidence, support=support, resistance=resistance, plan=result)
    return result
