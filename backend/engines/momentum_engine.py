import pandas as pd
import ta

from .engine_utils import clamp_score, has_valid_market_data, safe_float


def calculate_momentum_score(df: pd.DataFrame) -> int:
    """Score momentum from RSI health and MACD direction."""

    return analyze_momentum(df)["score"]


def analyze_momentum(df: pd.DataFrame) -> dict:
    """Assess RSI and MACD momentum with an explanatory institutional result."""

    if not has_valid_market_data(df, minimum_rows=35):
        return {"score": 50, "explanation": "Insufficient valid data for RSI and MACD.", "confidence": 0}

    close = pd.to_numeric(df["Close"], errors="coerce").dropna()
    if len(close) < 35:
        return {"score": 50, "explanation": "Insufficient closing-price history for momentum.", "confidence": 0}

    rsi = safe_float(ta.momentum.rsi(close=close, window=14).iloc[-1])
    macd = ta.trend.MACD(close=close)
    macd_line = safe_float(macd.macd().iloc[-1])
    macd_signal = safe_float(macd.macd_signal().iloc[-1])

    if rsi is None or macd_line is None or macd_signal is None:
        return {"score": 50, "explanation": "Momentum indicators are not yet available.", "confidence": 0}

    if 55 <= rsi <= 70:
        rsi_score = 50
    elif 50 <= rsi < 55 or 70 < rsi <= 75:
        rsi_score = 40
    elif 45 <= rsi < 50:
        rsi_score = 25
    else:
        rsi_score = 10

    if macd_line > macd_signal and macd_line > 0:
        macd_score = 50
    elif macd_line > macd_signal or macd_line > 0:
        macd_score = 30
    else:
        macd_score = 10

    score = clamp_score(rsi_score + macd_score)
    macd_state = "positive" if macd_line > macd_signal else "weakening"
    return {"score": score, "explanation": f"RSI is {rsi:.1f} and MACD momentum is {macd_state}.", "confidence": 100 if len(close) >= 50 else 65}
