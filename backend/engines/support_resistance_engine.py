import pandas as pd

from support_resistance import calculate_support_resistance

from .engine_utils import has_valid_market_data, safe_float


def analyze_support_resistance(df: pd.DataFrame) -> dict:
    """Assess nearby support, resistance, and the available upside/risk profile."""

    if not has_valid_market_data(df, minimum_rows=20):
        return {"score": 50, "explanation": "Insufficient valid data for support and resistance.", "confidence": 0}

    levels = calculate_support_resistance(df)
    price = safe_float(df["Close"].iloc[-1])
    support = safe_float(levels["support"])
    resistance = safe_float(levels["resistance"])
    if price is None or price <= 0 or support is None or resistance is None or resistance <= support:
        return {"score": 50, "explanation": "Support and resistance levels are invalid.", "confidence": 0}

    downside = price - support
    upside = resistance - price
    if downside <= 0 or upside <= 0:
        return {"score": 20, "explanation": "Price is outside the current support/resistance range.", "confidence": 100}

    risk_reward = upside / downside
    if risk_reward >= 3:
        score = 100
    elif risk_reward >= 2:
        score = 85
    elif risk_reward >= 1.5:
        score = 70
    elif risk_reward >= 1:
        score = 50
    else:
        score = 25

    return {"score": score, "explanation": f"Recent support is ${support:.2f}, resistance is ${resistance:.2f}, and the range offers {risk_reward:.2f}R.", "confidence": 100}
