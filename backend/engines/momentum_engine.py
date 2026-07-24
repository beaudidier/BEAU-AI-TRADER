import pandas as pd
import ta


def calculate_momentum_score(df: pd.DataFrame) -> int:
    """Score momentum from RSI health and MACD direction."""

    close = df["Close"]
    rsi = float(ta.momentum.rsi(close=close, window=14).iloc[-1])
    macd = ta.trend.MACD(close=close)
    macd_line = float(macd.macd().iloc[-1])
    macd_signal = float(macd.macd_signal().iloc[-1])

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

    return int(rsi_score + macd_score)
