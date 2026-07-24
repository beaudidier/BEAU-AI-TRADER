import pandas as pd

from support_resistance import calculate_support_resistance


def calculate_risk_score(df: pd.DataFrame) -> int:
    """Score the trade's risk/reward against recent support and resistance."""

    levels = calculate_support_resistance(df)
    price = float(df["Close"].iloc[-1])
    downside = price - levels["support"]
    upside = levels["resistance"] - price

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

    return round((reward_score * 0.6) + (support_score * 0.2) + (resistance_score * 0.2))
