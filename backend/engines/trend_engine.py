import pandas as pd


def calculate_trend_score(df: pd.DataFrame) -> int:
    """Score the current trend using EMA alignment and price position."""

    close = df["Close"]
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

    return int(score)
