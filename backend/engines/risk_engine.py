import pandas as pd

from support_resistance import calculate_support_resistance

from .engine_utils import clamp_score, has_valid_market_data, safe_float


def calculate_risk_score(df: pd.DataFrame) -> int:
    """Score the trade's risk/reward against recent support and resistance."""

    if not has_valid_market_data(df, minimum_rows=20):
        return 50

    levels = calculate_support_resistance(df)
    price = safe_float(df["Close"].iloc[-1])
    support = safe_float(levels.get("support"))
    resistance = safe_float(levels.get("resistance"))

    if price is None or price <= 0 or support is None or resistance is None:
        return 50

    downside = price - support
    upside = resistance - price

    if downside <= 0 or upside <= 0:
        return 0

    risk_reward = upside / downside
    support_distance_percent = (downside / price) * 100
    resistance_distance_percent = (upside / price) * 100

    if risk_reward >= 3:
        reward_score = 100
    elif risk_reward >= 2:
        reward_score = 85
    elif risk_reward >= 1.5:
        reward_score = 70
    elif risk_reward >= 1:
        reward_score = 50
    else:
        reward_score = 30

    support_score = max(0, min(100, round(100 - (support_distance_percent * 10))))
    resistance_score = max(0, min(100, round(resistance_distance_percent * 10)))

    return clamp_score((reward_score * 0.6) + (support_score * 0.2) + (resistance_score * 0.2))
