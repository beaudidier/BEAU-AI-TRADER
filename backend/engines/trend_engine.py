import pandas as pd

from .engine_utils import clamp_score, has_valid_market_data


def calculate_trend_score(df: pd.DataFrame) -> int:
    """Score the current trend using EMA alignment and price position."""

    return analyze_trend(df)["score"]


def analyze_trend(df: pd.DataFrame) -> dict:
    """Assess EMA alignment and price position for institutional trend context."""

    if not has_valid_market_data(df):
        return {"score": 50, "explanation": "Insufficient valid price data for trend analysis.", "confidence": 0}

    close = pd.to_numeric(df["Close"], errors="coerce").dropna()
    if close.empty:
        return {"score": 50, "explanation": "No usable closing prices for trend analysis.", "confidence": 0}
    ema20 = close.ewm(span=20, adjust=False).mean().iloc[-1]
    ema50 = close.ewm(span=50, adjust=False).mean().iloc[-1]
    ema200 = close.ewm(span=200, adjust=False).mean().iloc[-1]
    price = close.iloc[-1]

    score = 0
    score += 30 if ema20 > ema50 else 15
    score += 25 if ema50 > ema200 else 10
    score += 25 if price > ema20 else 0
    score += 10 if price > ema50 else 0
    score += 10 if price > ema200 else 0

    score = clamp_score(score)
    alignment = "bullish" if ema20 > ema50 > ema200 else "mixed"
    position = "above" if price > ema20 else "below"
    return {"score": score, "explanation": f"{alignment.capitalize()} EMA alignment with price {position} the 20-day EMA.", "confidence": 100 if len(close) >= 200 else 60}
