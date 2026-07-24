import pandas as pd
import ta

from .engine_utils import has_valid_market_data, safe_float


def calculate_volatility_score(df: pd.DataFrame) -> int:
    """Score volatility using ATR and ATR as a percentage of price."""

    return analyze_volatility(df)["score"]


def analyze_volatility(df: pd.DataFrame) -> dict:
    """Assess ATR quality and volatility suitability for risk-managed entries."""

    if not has_valid_market_data(df, minimum_rows=14):
        return {"score": 50, "explanation": "Insufficient valid data for ATR analysis.", "confidence": 0}

    atr = safe_float(
        ta.volatility.average_true_range(
            high=df["High"], low=df["Low"], close=df["Close"], window=14
        ).iloc[-1]
    )
    price = safe_float(df["Close"].iloc[-1])

    if price is None or price <= 0 or atr is None:
        return {"score": 50, "explanation": "ATR calculation is unavailable.", "confidence": 0}

    atr_percent = (atr / price) * 100

    if 1 <= atr_percent <= 5:
        score = 90
    elif atr_percent < 1:
        score = 60
    elif atr_percent <= 8:
        score = 70
    elif atr_percent <= 12:
        score = 40
    else:
        score = 20

    return {"score": score, "explanation": f"ATR is {atr_percent:.2f}% of the current price.", "confidence": 100}
