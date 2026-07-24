import pandas as pd
import ta


def calculate_volatility_score(df: pd.DataFrame) -> int:
    """Score volatility using ATR and ATR as a percentage of price."""

    atr = float(
        ta.volatility.average_true_range(
            high=df["High"], low=df["Low"], close=df["Close"], window=14
        ).iloc[-1]
    )
    price = float(df["Close"].iloc[-1])

    if price <= 0 or pd.isna(atr):
        return 50

    atr_percent = (atr / price) * 100

    if 1 <= atr_percent <= 5:
        return 90
    if atr_percent < 1:
        return 60
    if atr_percent <= 8:
        return 70
    if atr_percent <= 12:
        return 40
    return 20
